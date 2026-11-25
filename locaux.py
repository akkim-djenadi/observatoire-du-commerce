"""Locaux commerciaux disponibles : déduits automatiquement, ou confirmés par l'Observatoire (feuille Google).

Un local est « probablement libéré » si un commerce y a fermé (Sirene) ou a été liquidé (BODACC) récemment,
et qu'aucun commerce ne s'est installé depuis à la même adresse. C'est une déduction : à vérifier sur place.
"""
import io
import logging
from datetime import date

import pandas as pd

from adresses import cle_adresse, normaliser_voie, numero
from offre import actifs_a, famille
from periode import mois_avant

log = logging.getLogger(__name__)
LIBERES_MOIS = 24
RUE_COMMERCANTE_MIN = 3   # un local n'est retenu que dans une rue d'au moins 3 commerces actifs (vitrines)
TYPES_LIQUIDATION = ("Liquidation judiciaire (ouverture)", "Liquidation judiciaire (conversion)",
                     "Clôture pour insuffisance d'actif")
COLONNES_FEUILLE = {"adresse": "adresse", "surface_m2": "surface_m2", "loyer_mensuel": "loyer_mensuel",
                    "contact": "contact", "disponible_depuis": "disponible_depuis", "commentaire": "commentaire"}
COLONNES_LIBERES = ["cle", "adresse", "voie", "zone", "latitude", "longitude", "derniere_activite", "famille",
                    "depuis", "source"]


def _cles(df: pd.DataFrame) -> pd.Series:
    return df["numero"].fillna("").astype(str).combine(df["voie"].fillna(""), cle_adresse)


def _occupees(etab: pd.DataFrame, jour: date) -> set[str]:
    actifs = actifs_a(etab, jour)
    return set(_cles(actifs)) if not actifs.empty else set()


def _depuis_sirene(etab: pd.DataFrame, debut: date, jour: date) -> pd.DataFrame:
    fermes = etab[etab["date_fermeture"].fillna("").astype(str).between(debut.isoformat(), jour.isoformat())]
    fermes = fermes[fermes["date_fermeture"].fillna("") != ""]
    if fermes.empty:
        return pd.DataFrame(columns=COLONNES_LIBERES)
    return pd.DataFrame({
        "cle": _cles(fermes), "adresse": fermes["adresse"], "voie": fermes["voie"], "zone": fermes["zone"],
        "latitude": fermes["latitude"], "longitude": fermes["longitude"],
        "derniere_activite": fermes["enseigne"].fillna("").where(fermes["enseigne"].fillna("") != "", fermes["nom"]),
        "famille": fermes["naf"].map(famille), "depuis": fermes["date_fermeture"], "source": "Fermeture (Sirene)",
    })


def _depuis_bodacc(proc: pd.DataFrame, debut: date, jour: date) -> pd.DataFrame:
    p = proc[proc["type"].isin(TYPES_LIQUIDATION)
             & proc["date_jugement"].fillna("").astype(str).between(debut.isoformat(), jour.isoformat())]
    if p.empty:
        return pd.DataFrame(columns=COLONNES_LIBERES)
    voies = p["adresse"].fillna("").map(normaliser_voie)
    return pd.DataFrame({
        "cle": [cle_adresse(numero(a), v) for a, v in zip(p["adresse"].fillna(""), voies)],
        "adresse": p["adresse"], "voie": voies, "zone": p["zone"], "latitude": p["latitude"],
        "longitude": p["longitude"], "derniere_activite": p["enseigne"].fillna("").where(
            p["enseigne"].fillna("") != "", p["nom"]),
        "famille": p["secteur"], "depuis": p["date_jugement"], "source": "Liquidation (BODACC)",
    })


def liberes(etab: pd.DataFrame, proc: pd.DataFrame, jour: date) -> pd.DataFrame:
    """Locaux probablement libérés à une date : fermés depuis moins de 24 mois, sans nouveau commerce depuis,
    dans une rue commerçante (au moins 3 commerces actifs : écarte les activités exercées à domicile)."""
    debut = mois_avant(jour, LIBERES_MOIS)
    candidats = pd.concat([_depuis_sirene(etab, debut, jour), _depuis_bodacc(proc, debut, jour)], ignore_index=True)
    if candidats.empty:
        return candidats
    candidats = candidats[candidats["cle"].str.match(r"^\d+\|.+")]          # adresse précise exigée
    candidats = candidats[~candidats["cle"].isin(_occupees(etab, jour))]   # personne ne s'y est réinstallé
    actifs = actifs_a(etab, jour)
    commerces_par_rue = actifs.groupby("voie").size() if not actifs.empty else pd.Series(dtype=int)
    candidats = candidats[candidats["voie"].map(commerces_par_rue).fillna(0) >= RUE_COMMERCANTE_MIN]
    return (candidats.sort_values("depuis", ascending=False)
            .drop_duplicates("cle").reset_index(drop=True))


def normaliser_feuille(brut: pd.DataFrame) -> pd.DataFrame:
    """Contrôle la feuille des locaux confirmés : colonnes attendues, adresse obligatoire, nombres propres."""
    colonnes = {c: c.strip().lower().replace(" ", "_") for c in brut.columns}
    df = brut.rename(columns=colonnes)
    manquantes = [c for c in COLONNES_FEUILLE if c not in df.columns]
    if manquantes:
        raise ValueError(f"Colonnes manquantes dans la feuille des locaux : {', '.join(manquantes)}")
    df = df[list(COLONNES_FEUILLE)].copy()
    df = df[df["adresse"].fillna("").astype(str).str.strip() != ""]
    for c in ("surface_m2", "loyer_mensuel"):
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(r"[^\d,.]", "", regex=True).str.replace(",", "."),
                              errors="coerce")
    df["voie"] = df["adresse"].map(normaliser_voie)
    return df.reset_index(drop=True)


def lire_feuille(texte_csv: str) -> pd.DataFrame:
    return normaliser_feuille(pd.read_csv(io.StringIO(texte_csv), dtype=str))
