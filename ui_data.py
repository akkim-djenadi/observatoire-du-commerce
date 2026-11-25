"""Préparation des données pour l'interface : tableaux, filtres, indicateurs."""
from dataclasses import asdict, dataclass, replace

import pandas as pd

from classify import FILTRES_ANNONCE
from config import ZONE_ORDER
from pipeline import Rapport, filtrer_par_type

STATUTS_A_ACCOMPAGNER = frozenset({"En redressement judiciaire", "En sauvegarde", "Plan adopté / modifié"})
STATUTS_LIQUIDATION = frozenset({"En liquidation judiciaire"})

# Couleurs : chaque statut garde la même couleur sur la carte et les graphiques
COULEURS_STATUT = {
    "En redressement judiciaire": "#E2A24A",
    "En sauvegarde": "#7A9A4E",
    "Plan adopté / modifié": "#3F7C8C",
    "Procédure en cours (état des créances déposé)": "#C9B29B",
    "En liquidation judiciaire": "#BB502E",
    "Liquidation clôturée (insuffisance d'actif)": "#6B6460",
    "Liquidation clôturée + faillite personnelle du dirigeant": "#2B2B2B",
    "Procédure clôturée (passif payé)": "#9BB59A",
}
ORDRE_STATUTS = list(COULEURS_STATUT)

COLONNES_COMMERCES = {
    "zone": "Zone", "nom": "Raison sociale", "enseigne": "Enseigne", "statut": "Statut",
    "secteur": "Secteur", "activite": "Activité", "adresse": "Adresse",
    "date_ouverture": "Ouverture", "source_ouverture": "Date de",
    "date_jugement": "Dernier jugement", "derniere_parution": "Dernière parution",
    "nb_annonces": "Annonces", "siren": "SIREN", "url": "BODACC",
}


@dataclass(frozen=True)
class Filtres:
    types: frozenset[str] = frozenset()
    zones: tuple[str, ...] = ()
    secteurs: tuple[str, ...] = ()
    statuts: tuple[str, ...] = ()
    recherche: str = ""


@dataclass(frozen=True)
class Indicateurs:
    commerces: int
    annonces: int
    a_accompagner: int
    liquidations: int
    part_ecusson: float


def commerces_df(rap: Rapport) -> pd.DataFrame:
    df = pd.DataFrame([asdict(c) for c in rap.commerces])
    if df.empty:
        return pd.DataFrame(columns=[*COLONNES_COMMERCES, "latitude", "longitude", "historique"])
    df["ordre_zone"] = df["zone"].map(ZONE_ORDER)
    return df.sort_values(["ordre_zone", "adresse"]).drop(columns="ordre_zone").reset_index(drop=True)


def annonces_df(rap: Rapport) -> pd.DataFrame:
    rows = [{
        "date_parution": r.annonce.date_parution, "date_jugement": r.annonce.date_jugement,
        "type": r.type_procedure, "nature": r.annonce.nature, "zone": r.zone, "nom": r.annonce.nom,
        "siren": r.annonce.siren, "secteur": r.secteur, "activite": r.activite, "adresse": r.adresse,
        "texte": r.annonce.complement, "url": r.annonce.url,
    } for r in rap.retenus]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["mois"] = pd.to_datetime(df["date_parution"]).dt.to_period("M").dt.to_timestamp()
    return df.sort_values("date_parution", ascending=False).reset_index(drop=True)


def _cle(nom: str, siren: str) -> str:
    return siren or nom


def appliquer_filtres(rap: Rapport, f: Filtres) -> Rapport:
    """Nouveau rapport réduit aux annonces et commerces correspondant aux filtres."""
    annonces, commerces = filtrer_par_type(list(rap.retenus), f.types)
    terme = f.recherche.strip().lower()

    def garde(c) -> bool:
        texte = " ".join([c.nom, c.enseigne, c.adresse, c.activite, c.siren]).lower()
        return ((not f.zones or c.zone in f.zones)
                and (not f.secteurs or c.secteur in f.secteurs)
                and (not f.statuts or c.statut in f.statuts)
                and (not terme or terme in texte))

    gardes = [c for c in commerces if garde(c)]
    cles = {_cle(c.nom, c.siren) for c in gardes}
    annonces = [r for r in annonces if _cle(r.annonce.nom, r.annonce.siren) in cles]
    return replace(rap, retenus=tuple(annonces), commerces=tuple(gardes))


def indicateurs(rap: Rapport) -> Indicateurs:
    statuts = [c.statut for c in rap.commerces]
    n = len(statuts)
    ecusson = sum(1 for c in rap.commerces if ZONE_ORDER.get(c.zone) == 0)
    return Indicateurs(
        commerces=n, annonces=len(rap.retenus),
        a_accompagner=sum(s in STATUTS_A_ACCOMPAGNER for s in statuts),
        liquidations=sum(s in STATUTS_LIQUIDATION for s in statuts),
        part_ecusson=ecusson / n if n else 0.0,
    )


def types_depuis_cles(cles: list[str]) -> frozenset[str]:
    return frozenset(t for c in cles for t in FILTRES_ANNONCE[c])
