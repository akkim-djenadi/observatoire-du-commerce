"""Enchaînement : BODACC → enrichissement → géolocalisation → tri → regroupement."""
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import classify
from bodacc import Annonce, fetch_annonces, parse_annonce
from config import ZONE_HORS_CENTRE, ZONE_ORDER
from entreprises import FicheEntreprise, fetch_fiches
from geo import Point, classify_zone, geocode

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Resultat:
    annonce: Annonce
    zone: str
    distance_m: int | None
    type_procedure: str
    secteur: str
    activite: str
    adresse: str
    enseigne: str
    fiche: FicheEntreprise
    motif_exclusion: str = ""
    latitude: float | None = None
    longitude: float | None = None


@dataclass(frozen=True)
class Commerce:
    zone: str
    nom: str
    enseigne: str
    siren: str
    forme: str
    secteur: str
    activite: str
    adresse: str
    statut: str
    dernier_type: str
    date_jugement: str
    derniere_parution: str
    nb_annonces: int
    historique: str
    etat_insee: str
    date_creation: str
    url: str
    distance_m: int | None
    latitude: float | None = None
    longitude: float | None = None


@dataclass(frozen=True)
class Rapport:
    ville: str
    debut: date
    fin: date
    nb_annonces_ville: int
    retenus: tuple[Resultat, ...]
    exclus: tuple[Resultat, ...]
    commerces: tuple[Commerce, ...]
    filtre: str = ""  # types d'annonce demandés (vide = tous)


def _activite(a: Annonce, fiche: FicheEntreprise) -> str:
    if classify.activite_connue(a.activite):
        return a.activite
    return f"Non précisée au BODACC (NAF {fiche.naf})" if fiche.naf else "Non précisée"


def _locate(a: Annonce, fiche: FicheEntreprise, points: dict[str, Point], ville: str) -> tuple[str, Point | None]:
    """Adresse et point retenus : BODACC d'abord, adresse RNE du siège en secours."""
    if a.id in points:
        return a.adresse, points[a.id]
    if fiche.latitude is not None and ville.upper() in fiche.adresse.upper():
        return f"{fiche.adresse} (adresse RNE ; BODACC : {a.adresse or 'non précisée'})", Point(fiche.latitude, fiche.longitude)
    return a.adresse, None


def _resultat(a: Annonce, fiche: FicheEntreprise, points: dict[str, Point], ville: str) -> Resultat:
    adresse, point = _locate(a, fiche, points, ville)
    zonage = classify_zone(point, adresse)
    activite = _activite(a, fiche)
    return Resultat(
        annonce=a, zone=zonage.zone, distance_m=zonage.distance_m,
        type_procedure=classify.type_procedure(a.nature), secteur=classify.secteur(activite),
        activite=activite, adresse=adresse, enseigne=a.enseigne or fiche.enseignes, fiche=fiche,
        motif_exclusion=classify.motif_exclusion(a.nom, adresse),
        latitude=point.lat if point else None,
        longitude=point.lon if point else None,
    )


def _cle(r: Resultat) -> str:
    return r.annonce.siren or r.annonce.nom


def filtrer_par_type(resultats: list[Resultat], types: frozenset[str]) -> tuple[list[Resultat], list[Commerce]]:
    """Annonces des types demandés, et commerces concernés avec leur historique complet.

    Le statut d'un commerce reste calculé sur toutes ses annonces : filtrer sur
    « redressement » montre aussi qu'il est passé ensuite en liquidation.
    """
    tous = _regrouper(resultats)
    if not types:
        return resultats, tous
    gardees = [r for r in resultats if r.type_procedure in types]
    cles = {_cle(r) for r in gardees}
    return gardees, [c for c in tous if (c.siren or c.nom) in cles]


def _regrouper(resultats: list[Resultat]) -> list[Commerce]:
    groupes: dict[str, list[Resultat]] = defaultdict(list)
    for r in resultats:
        groupes[_cle(r)].append(r)
    commerces = []
    for items in groupes.values():
        items = sorted(items, key=lambda r: r.annonce.date_parution)
        types = [r.type_procedure for r in items]
        decisifs = [r for r in items if r.type_procedure not in (classify.CREANCES, classify.AUTRE)]
        dernier = (decisifs or items)[-1]
        premier = items[0]
        commerces.append(Commerce(
            zone=premier.zone, nom=premier.annonce.nom, enseigne=premier.enseigne,
            siren=premier.annonce.siren, forme=premier.annonce.forme, secteur=premier.secteur,
            activite=premier.activite, adresse=premier.adresse, statut=classify.statut(types),
            dernier_type=dernier.type_procedure, date_jugement=dernier.annonce.date_jugement,
            derniere_parution=items[-1].annonce.date_parution, nb_annonces=len(items),
            historique=" → ".join(f"{r.annonce.date_parution} : {r.type_procedure}" for r in items),
            etat_insee=premier.fiche.etat, date_creation=premier.fiche.date_creation,
            url=items[-1].annonce.url, distance_m=premier.distance_m,
            latitude=premier.latitude, longitude=premier.longitude,
        ))
    return sorted(commerces, key=lambda c: (ZONE_ORDER[c.zone], c.adresse))


def run(ville: str, debut: date, fin: date, cache_path: Path,
        types: frozenset[str] = frozenset(), filtre: str = "") -> Rapport:
    annonces = [parse_annonce(raw) for raw in fetch_annonces(ville, debut, fin)]
    # Candidats : activité commerce, ou activité inconnue (le code NAF tranchera)
    candidats = [a for a in annonces if classify.is_commerce(a.activite) or not classify.activite_connue(a.activite)]
    fiches = fetch_fiches({a.siren for a in candidats if a.siren}, cache_path)
    fiche_de = lambda a: fiches.get(a.siren) or FicheEntreprise(siren=a.siren)  # noqa: E731
    commerces = [a for a in candidats if classify.is_commerce(a.activite, fiche_de(a).naf)]
    points = geocode({a.id: a.adresse for a in commerces if a.adresse}, ville)
    resultats = [_resultat(a, fiche_de(a), points, ville) for a in commerces]
    au_centre = [r for r in resultats if r.zone != ZONE_HORS_CENTRE]
    retenus = [r for r in au_centre if not r.motif_exclusion]
    exclus = [r for r in au_centre if r.motif_exclusion]
    log.info("Centre-ville : %d annonces retenues, %d écartées", len(retenus), len(exclus))
    gardees, commerces_vus = filtrer_par_type(retenus, types)
    if types:
        log.info("Filtre « %s » : %d annonces, %d commerces", filtre, len(gardees), len(commerces_vus))
    return Rapport(ville, debut, fin, len(annonces), tuple(gardees), tuple(exclus), tuple(commerces_vus), filtre)
