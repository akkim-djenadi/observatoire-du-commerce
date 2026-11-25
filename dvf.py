"""Ventes de locaux commerciaux (DVF géolocalisées, data.gouv.fr).

Source principale : le fichier par commune et par année (léger). S'il disparaît (dossier d'archive),
repli sur le fichier national de l'année, lu en flux et filtré sur la commune.
"""
import csv
import gzip
import io
import logging
from collections import defaultdict
from typing import Iterable, Iterator

import pandas as pd

from adresses import normaliser_voie
from config import DVF_COMMUNE_URL, DVF_DATASET_API, ZONE_HORS_CENTRE
from geo import Point, classify_zone
from http_client import RessourceIntrouvable, get_json, get_text, ouvrir_flux

log = logging.getLogger(__name__)
TYPE_LOCAL_COMMERCIAL = "Local industriel. commercial ou assimilé"
NATURES_RETENUES = {"Vente", "Vente en l'état futur d'achèvement", "Adjudication"}
COLONNES = ["id_mutation", "date", "valeur", "surface", "prix_m2", "adresse", "voie", "latitude", "longitude",
            "zone", "nb_locaux"]


def _lignes_commune(annee: int, dep: str, commune: str) -> list[dict[str, str]]:
    texte = get_text(DVF_COMMUNE_URL.format(annee=annee, dep=dep, commune=commune))
    return list(csv.DictReader(io.StringIO(texte)))


def _url_nationale(annee: int) -> str | None:
    """Adresse du fichier national de l'année, lue dans la fiche data.gouv (elle change à chaque mise à jour)."""
    for r in get_json(DVF_DATASET_API).get("resources", []):
        if r.get("title", "").startswith(f"DVF {annee}") and r.get("url", "").endswith(".csv.gz"):
            return r["url"]
    return None


def _lignes_nationales(annee: int, commune: str) -> Iterator[dict[str, str]]:
    url = _url_nationale(annee)
    if not url:
        log.warning("DVF %d : aucun fichier national trouvé", annee)
        return
    log.info("DVF %d : repli sur le fichier national (%s)", annee, url)
    reponse = ouvrir_flux(url)
    try:
        with gzip.open(reponse.raw, mode="rt", encoding="utf-8", newline="") as flux:
            yield from (l for l in csv.DictReader(flux) if l.get("code_commune") == commune)
    finally:
        reponse.close()


def lignes_annee(annee: int, dep: str, commune: str) -> list[dict[str, str]]:
    try:
        return _lignes_commune(annee, dep, commune)
    except RessourceIntrouvable:
        return list(_lignes_nationales(annee, commune))


def ventes_locaux(lignes: Iterable[dict[str, str]]) -> list[dict]:
    """Une ligne par vente comprenant au moins un local commercial.

    Le prix au m² n'est calculé que si la vente porte sur un seul bien bâti, un local commercial :
    sinon le prix mélange plusieurs biens et fausserait la moyenne.
    """
    par_mutation: dict[str, list[dict[str, str]]] = defaultdict(list)
    for l in lignes:
        if l.get("nature_mutation") in NATURES_RETENUES:
            par_mutation[l["id_mutation"]].append(l)
    ventes = []
    for id_mut, ls in par_mutation.items():
        locaux = [l for l in ls if l.get("type_local") == TYPE_LOCAL_COMMERCIAL]
        if not locaux:
            continue
        batis = {(l.get("type_local"), l.get("lot1_numero"), l.get("surface_reelle_bati")) for l in ls if l.get("type_local")}
        surface = sum(float(l.get("surface_reelle_bati") or 0) for l in locaux)
        valeur = float(ls[0].get("valeur_fonciere") or 0)
        seul = len(batis) == 1 and len(locaux) == 1
        l0 = locaux[0]
        adresse = f"{l0.get('adresse_numero', '')} {l0.get('adresse_nom_voie', '')}".strip()
        ventes.append({
            "id_mutation": id_mut, "date": l0.get("date_mutation", ""), "valeur": valeur, "surface": surface,
            "prix_m2": round(valeur / surface) if seul and surface > 0 and valeur > 0 else None,
            "adresse": adresse, "voie": normaliser_voie(adresse),
            "latitude": float(l0["latitude"]) if l0.get("latitude") else None,
            "longitude": float(l0["longitude"]) if l0.get("longitude") else None,
            "nb_locaux": len(locaux),
        })
    return ventes


def tableau(ventes: list[dict]) -> pd.DataFrame:
    """Ventes du centre-ville avec leur zone ; les ventes hors centre sont écartées."""
    lignes = []
    for v in ventes:
        point = Point(v["latitude"], v["longitude"]) if v["latitude"] is not None else None
        zone = classify_zone(point, v["adresse"]).zone
        if zone != ZONE_HORS_CENTRE:
            lignes.append({**v, "zone": zone})
    return pd.DataFrame(lignes, columns=COLONNES).sort_values("date").reset_index(drop=True)


def collecter(annees: Iterable[int], dep: str, commune: str) -> pd.DataFrame:
    ventes = []
    for annee in annees:
        try:
            ventes += ventes_locaux(lignes_annee(annee, dep, commune))
        except RessourceIntrouvable:
            log.info("DVF %d : pas encore publié", annee)
    log.info("DVF : %d ventes de locaux commerciaux dans la commune", len(ventes))
    return tableau(ventes)
