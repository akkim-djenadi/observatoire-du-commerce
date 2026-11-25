"""Stock des commerces d'une commune (actifs et fermés récemment), d'après l'API Recherche d'entreprises (Sirene)."""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Iterable

import pandas as pd

from adresses import cle_adresse, est_voie_nommee, normaliser_voie, numero
from config import DOMICILIATION_RE, ENTREPRISES_URL, INDEPENDANT_MAX_ETABLISSEMENTS, ZONE_HORS_CENTRE
from geo import Point, classify_zone
from http_client import SourceIndisponible, get_json

log = logging.getLogger(__name__)
PAR_PAGE = 25
PAGES_MAX = 400  # l'API plafonne à 10 000 résultats
TACHES_PARALLELES = 3        # 3 codes NAF à la fois…
REQUETES_PAR_SECONDE = 5.0   # …mais jamais plus de 5 requêtes par seconde au total (limite de l'API : 7)
DOMICILIATION_MIN_ENTREPRISES = 6  # autant d'entreprises actives à une même adresse : c'est une domiciliation


@dataclass(frozen=True)
class Etablissement:
    siret: str
    siren: str
    nom: str
    enseigne: str
    naf: str
    adresse: str
    numero: str
    voie: str
    latitude: float | None
    longitude: float | None
    date_creation: str
    date_fermeture: str
    actif: bool
    independant: bool


def _flottant(valeur: Any) -> float | None:
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def depuis_resultat(resultat: dict[str, Any], commune: str, nafs: frozenset[str],
                    fermes_depuis: date) -> list[Etablissement]:
    """Établissements « commerce » d'une entreprise situés dans la commune.

    On garde les actifs, et les fermés depuis `fermes_depuis` (pour compter les fermetures récentes).
    """
    ouverts = int(resultat.get("nombre_etablissements_ouverts") or 0)
    sortie = []
    for e in resultat.get("matching_etablissements") or []:
        if e.get("commune") != commune or e.get("activite_principale") not in nafs:
            continue
        actif = e.get("etat_administratif") == "A"
        fermeture = e.get("date_fermeture") or ""
        if not actif and (not fermeture or fermeture < fermes_depuis.isoformat()):
            continue
        enseignes = [x for x in (e.get("liste_enseignes") or []) if x and "NON-DIFFUSIBLE" not in x]
        adresse = e.get("adresse") or ""
        sortie.append(Etablissement(
            siret=e.get("siret", ""), siren=resultat.get("siren", ""), nom=resultat.get("nom_complet", ""),
            enseigne=", ".join(enseignes) or (e.get("nom_commercial") or ""), naf=e.get("activite_principale", ""),
            adresse=adresse, numero=numero(adresse), voie=normaliser_voie(adresse),
            latitude=_flottant(e.get("latitude")), longitude=_flottant(e.get("longitude")),
            date_creation=e.get("date_creation") or "", date_fermeture=fermeture, actif=actif,
            independant=ouverts <= INDEPENDANT_MAX_ETABLISSEMENTS,
        ))
    return sortie


class Cadence:
    """Espace les requêtes de tous les fils d'exécution pour ne pas dépasser un débit global."""

    def __init__(self, par_seconde: float) -> None:
        self.intervalle = 1.0 / par_seconde
        self._verrou = threading.Lock()
        self._prochaine = 0.0

    def reserver(self) -> float:
        """Réserve le prochain créneau et renvoie l'attente nécessaire (en secondes)."""
        with self._verrou:
            maintenant = time.monotonic()
            creneau = max(maintenant, self._prochaine)
            self._prochaine = creneau + self.intervalle
            return creneau - maintenant

    def attendre(self) -> None:
        attente = self.reserver()
        if attente > 0:
            time.sleep(attente)


class CollecteIncomplete(SourceIndisponible):
    """Au moins un code NAF n'a pas pu être collecté : les données seraient incomplètes."""


def _pages(commune: str, naf: str, cadence: Cadence) -> Iterable[dict[str, Any]]:
    page, total = 1, 1
    while page <= min(total, PAGES_MAX):
        cadence.attendre()
        data = get_json(ENTREPRISES_URL, params={
            "code_commune": commune, "activite_principale": naf, "per_page": str(PAR_PAGE), "page": str(page),
        })
        total = int(data.get("total_pages") or 0)
        yield from data.get("results") or []
        page += 1


def _un_code(commune: str, naf: str, nafs: frozenset[str], fermes_depuis: date,
             cadence: Cadence) -> list[Etablissement] | None:
    """Établissements d'un code NAF, ou None si la collecte de ce code a échoué."""
    try:
        return [e for r in _pages(commune, naf, cadence) for e in depuis_resultat(r, commune, nafs, fermes_depuis)]
    except SourceIndisponible as exc:
        log.error("Code NAF %s non collecté : %s", naf, exc)
        return None


def collecter(commune: str, nafs: Iterable[str], fermes_depuis: date) -> list[Etablissement]:
    """Tous les commerces de la commune (plusieurs codes NAF en parallèle), sans doublon de SIRET.

    Si un seul code NAF échoue, lève CollecteIncomplete : mieux vaut garder les données du mois précédent
    que publier un stock amputé (par exemple sans les boutiques de vêtements).
    """
    nafs = frozenset(nafs)
    cadence = Cadence(REQUETES_PAR_SECONDE)
    vus: dict[str, Etablissement] = {}
    echecs: list[str] = []
    codes = sorted(nafs)
    with ThreadPoolExecutor(max_workers=TACHES_PARALLELES) as pool:
        lots = pool.map(lambda n: _un_code(commune, n, nafs, fermes_depuis, cadence), codes)
        for i, (naf, lot) in enumerate(zip(codes, lots), 1):
            if lot is None:
                echecs.append(naf)
                continue
            for e in lot:
                vus.setdefault(e.siret, e)
            if i % 10 == 0:
                log.info("  %d/%d codes NAF, %d établissements", i, len(nafs), len(vus))
    if echecs:
        raise CollecteIncomplete(f"{len(echecs)} code(s) NAF non collecté(s) : {', '.join(echecs)}")
    log.info("Sirene : %d établissements commerce à retenir", len(vus))
    return list(vus.values())


def adresses_de_domiciliation(etablissements: list[Etablissement]) -> set[str]:
    """Adresses (hors centres commerciaux) où sont enregistrées trop d'entreprises actives pour être des boutiques."""
    entreprises: dict[str, set[str]] = {}
    for e in etablissements:
        if e.actif and e.numero and not e.voie.startswith("CENTRE COMMERCIAL"):
            entreprises.setdefault(cle_adresse(e.numero, e.voie), set()).add(e.siren)
    return {cle for cle, sirens in entreprises.items() if len(sirens) >= DOMICILIATION_MIN_ENTREPRISES}


def tableau(etablissements: list[Etablissement]) -> pd.DataFrame:
    """Tableau avec la zone du centre-ville ; les commerces hors centre et sans rue exploitable sont écartés."""
    domiciliations = adresses_de_domiciliation(etablissements)
    lignes = []
    for e in etablissements:
        if cle_adresse(e.numero, e.voie) in domiciliations or DOMICILIATION_RE.search(e.adresse):
            continue
        point = Point(e.latitude, e.longitude) if e.latitude is not None and e.longitude is not None else None
        zonage = classify_zone(point, e.adresse)
        if zonage.zone == ZONE_HORS_CENTRE or not est_voie_nommee(e.voie):
            continue
        lignes.append({**asdict(e), "zone": zonage.zone, "distance_m": zonage.distance_m})
    colonnes = [*Etablissement.__dataclass_fields__, "zone", "distance_m"]
    return pd.DataFrame(lignes, columns=colonnes).sort_values(["zone", "voie", "numero"]).reset_index(drop=True)
