"""Synthèse des commerces en difficulté : répartitions en pourcentage et durée d'exploitation.

Durée d'exploitation = de la date d'ouverture (établissement, sinon entreprise) jusqu'au premier jugement
publié sur la période, c'est-à-dire jusqu'au moment où le commerce tombe en difficulté.
"""
from dataclasses import dataclass

import pandas as pd

from pipeline import Rapport

TRANCHES = ((1, "Moins d'1 an"), (3, "1 à 3 ans"), (5, "3 à 5 ans"), (10, "5 à 10 ans"),
            (float("inf"), "Plus de 10 ans"))
JOURS_PAR_AN = 365.25


@dataclass(frozen=True)
class ResumeDurees:
    nb: int                 # commerces dont la durée est connue
    moyenne: float | None   # en années
    mediane: float | None
    part_moins_3_ans: float | None
    sans_date: int          # commerces sans date d'ouverture connue


def duree_annees(ouverture: str, fin: str) -> float | None:
    """Années entre deux dates ISO ; None si une date manque ou si elles sont incohérentes."""
    debut, f = pd.to_datetime(ouverture or None, errors="coerce"), pd.to_datetime(fin or None, errors="coerce")
    if pd.isna(debut) or pd.isna(f) or f < debut:
        return None
    return round((f - debut).days / JOURS_PAR_AN, 2)


def tranche(duree: float | None) -> str | None:
    if duree is None or pd.isna(duree):
        return None
    return next(libelle for borne, libelle in TRANCHES if duree < borne)


def tableau_durees(rap: Rapport) -> pd.DataFrame:
    """Une ligne par commerce : zone, secteur, statut, ouverture, premier jugement, durée et tranche."""
    premiers: dict[str, str] = {}
    for r in rap.retenus:
        cle, jour = r.annonce.siren or r.annonce.nom, r.annonce.date_jugement or r.annonce.date_parution
        if jour and (cle not in premiers or jour < premiers[cle]):
            premiers[cle] = jour
    lignes = []
    for c in rap.commerces:
        premier = premiers.get(c.siren or c.nom, c.date_jugement)
        duree = duree_annees(c.date_ouverture, premier)
        lignes.append({"nom": c.nom, "zone": c.zone, "secteur": c.secteur, "statut": c.statut,
                       "date_ouverture": c.date_ouverture, "source_ouverture": c.source_ouverture,
                       "premier_jugement": premier, "duree_ans": duree, "tranche": tranche(duree)})
    return pd.DataFrame(lignes, columns=["nom", "zone", "secteur", "statut", "date_ouverture", "source_ouverture",
                                         "premier_jugement", "duree_ans", "tranche"])


def repartition(valeurs: pd.Series, ordre: list[str] | None = None) -> pd.DataFrame:
    """Nombre et pourcentage de chaque modalité (les valeurs vides sont ignorées)."""
    v = valeurs.dropna()
    v = v[v.astype(str) != ""]
    comptes = v.value_counts()
    if ordre:
        comptes = comptes.reindex([o for o in ordre if o in comptes.index])
    total = int(comptes.sum())
    return pd.DataFrame({"modalite": comptes.index, "nombre": comptes.values.astype(int),
                         "pourcentage": (comptes.values / total * 100).round(1) if total else 0.0})


def durees_par(df: pd.DataFrame, colonne: str) -> pd.DataFrame:
    """Durée moyenne et médiane d'exploitation par modalité, avec le nombre de commerces pris en compte."""
    d = df.dropna(subset=["duree_ans"])
    if d.empty:
        return pd.DataFrame(columns=[colonne, "nombre", "moyenne", "mediane"])
    g = d.groupby(colonne)["duree_ans"].agg(nombre="count", moyenne="mean", mediane="median").reset_index()
    return g.round({"moyenne": 1, "mediane": 1}).sort_values("moyenne", ascending=False).reset_index(drop=True)


def resume(df: pd.DataFrame) -> ResumeDurees:
    d = df["duree_ans"].dropna()
    return ResumeDurees(
        nb=int(len(d)), moyenne=round(float(d.mean()), 1) if len(d) else None,
        mediane=round(float(d.median()), 1) if len(d) else None,
        part_moins_3_ans=round(float((d < 3).mean() * 100), 1) if len(d) else None,
        sans_date=int(df["duree_ans"].isna().sum()),
    )


def ordre_tranches() -> list[str]:
    return [libelle for _, libelle in TRANCHES]
