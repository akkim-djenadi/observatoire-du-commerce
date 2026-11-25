"""Composition de l'offre commerciale : familles d'activité, diversité, indépendants, ouvertures et fermetures.

Toutes les fonctions prennent le tableau des établissements (`data/etablissements.csv`) et une date de référence :
l'état « à une date » est reconstitué à partir des dates d'ouverture et de fermeture.
"""
import math
from datetime import date

import pandas as pd

FAMILLES = {
    "Alimentaire": ("47.11", "47.21", "47.22", "47.23", "47.24", "47.25", "47.26", "47.29"),
    "Restauration et bars": ("56.",),
    "Hôtellerie": ("55.",),
    "Équipement de la personne": ("47.71", "47.72", "47.77", "47.79"),
    "Beauté et soins": ("96.02", "96.04", "47.75"),
    "Santé et optique": ("47.73", "47.74", "47.78A"),
    "Maison, culture et loisirs": ("47.19", "47.4", "47.5", "47.6", "47.76", "47.78"),
    "Services": ("68.31", "79.11", "85.53", "96.01", "95.2", "93.13", "47.30"),
}
AUTRE = "Autres commerces"


def famille(naf: str) -> str:
    """Famille d'activité d'un code NAF. Les préfixes les plus précis sont testés en premier."""
    candidats = [(p, f) for f, prefixes in FAMILLES.items() for p in prefixes if str(naf).startswith(p)]
    return max(candidats, key=lambda c: len(c[0]))[1] if candidats else AUTRE


def _dates(df: pd.DataFrame, colonne: str) -> pd.Series:
    return pd.to_datetime(df[colonne].replace("", pd.NA), errors="coerce")


def actifs_a(df: pd.DataFrame, jour: date) -> pd.DataFrame:
    """Établissements ouverts à une date : créés avant, et pas encore fermés."""
    if df.empty:
        return df
    t = pd.Timestamp(jour)
    creation, fermeture = _dates(df, "date_creation"), _dates(df, "date_fermeture")
    return df[(creation.isna() | (creation <= t)) & (fermeture.isna() | (fermeture > t))]


def mouvements(df: pd.DataFrame, debut: date, fin: date) -> tuple[int, int]:
    """Ouvertures et fermetures d'établissements entre deux dates (bornes incluses)."""
    if df.empty:
        return 0, 0
    d, f = pd.Timestamp(debut), pd.Timestamp(fin)
    creation, fermeture = _dates(df, "date_creation"), _dates(df, "date_fermeture")
    return int(creation.between(d, f).sum()), int(fermeture.between(d, f).sum())


def repartition(actifs: pd.DataFrame) -> pd.Series:
    """Nombre de commerces par famille d'activité."""
    if actifs.empty:
        return pd.Series(dtype=int)
    return actifs["naf"].map(famille).value_counts()


def diversite(actifs: pd.DataFrame) -> float | None:
    """Indice de Shannon normalisé entre 0 (une seule activité) et 1 (toutes les familles à parts égales)."""
    comptes = repartition(actifs)
    total = comptes.sum()
    if total == 0:
        return None
    entropie = -sum((n / total) * math.log(n / total) for n in comptes if n > 0)
    return round(entropie / math.log(len(FAMILLES) + 1), 3)


def part_independants(actifs: pd.DataFrame) -> float | None:
    if actifs.empty:
        return None
    return round(actifs["independant"].astype(str).str.lower().isin(["true", "1"]).mean(), 3)


def familles_rares(actifs_rue: pd.DataFrame, actifs_zone: pd.DataFrame, seuil_zone: float = 0.08) -> list[str]:
    """Familles bien présentes dans la zone (au moins 8 % des commerces) mais absentes de la rue."""
    zone, rue = repartition(actifs_zone), repartition(actifs_rue)
    if zone.sum() == 0:
        return []
    frequentes = zone[zone / zone.sum() >= seuil_zone].index
    return [f for f in frequentes if rue.get(f, 0) == 0]
