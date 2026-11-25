"""Lecture des données mensuelles de vitalité (`data/`), pour l'interface et la note de conjoncture."""
import json
import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from adresses import sans_accents

ICI = Path(__file__).resolve().parent
DATA = ICI / "data"
RAPPORTS = ICI / "rapports"
NUMERIQUES_ETAB = ("latitude", "longitude", "distance_m")
NUMERIQUES_DVF = ("valeur", "surface", "prix_m2", "latitude", "longitude", "nb_locaux")
NUMERIQUES_PROC = ("latitude", "longitude")


@dataclass(frozen=True)
class DonneesVitalite:
    etablissements: pd.DataFrame
    dvf: pd.DataFrame
    procedures: pd.DataFrame
    historique: pd.DataFrame
    collecte_le: str

    @property
    def dernier_mois(self) -> str:
        return self.historique["mois"].max() if not self.historique.empty else ""

    def indice_du_mois(self, mois: str | None = None) -> pd.DataFrame:
        h = self.historique
        return h[h["mois"] == (mois or self.dernier_mois)] if not h.empty else h

    def as_dict(self) -> dict[str, pd.DataFrame]:
        return {"etablissements": self.etablissements, "dvf": self.dvf, "procedures": self.procedures}


def _lire(nom: str, numeriques: tuple[str, ...] = ()) -> pd.DataFrame:
    chemin = DATA / nom
    if not chemin.exists():
        return pd.DataFrame()
    df = pd.read_csv(chemin, dtype=str, keep_default_na=False)
    for c in numeriques:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _historique() -> pd.DataFrame:
    h = _lire("indice_historique.csv")
    for c in h.columns:
        if c.startswith(("indice", "brut_", "score_")):
            h[c] = pd.to_numeric(h[c], errors="coerce")
    return h


def charger() -> DonneesVitalite:
    meta = DATA / "collecte.json"
    infos = json.loads(meta.read_text(encoding="utf-8")) if meta.exists() else {}
    dates = [v.get("collecte", "") for v in infos.values() if isinstance(v, dict)]
    return DonneesVitalite(
        etablissements=_lire("etablissements.csv", NUMERIQUES_ETAB), dvf=_lire("dvf_locaux.csv", NUMERIQUES_DVF),
        procedures=_lire("procedures.csv", NUMERIQUES_PROC), historique=_historique(),
        collecte_le=max(dates)[:10] if dates else "",
    )


def derniere_note() -> Path | None:
    notes = sorted(RAPPORTS.glob("note-*.pdf"))
    return notes[-1] if notes else None


def url_feuille_locaux(secrets: dict | None = None) -> str:
    """Adresse CSV de la feuille Google des locaux confirmés (secrets Streamlit, sinon variable d'environnement)."""
    if secrets and secrets.get("LOCAUX_SHEET_CSV_URL"):
        return str(secrets["LOCAUX_SHEET_CSV_URL"])
    return os.environ.get("LOCAUX_SHEET_CSV_URL", "")


def date_fr(iso: str) -> str:
    """« 2026-11-25 » → « 25/11/2026 » (texte laissé tel quel s'il n'est pas une date)."""
    morceaux = (iso or "").split("-")
    return f"{morceaux[2]}/{morceaux[1]}/{morceaux[0]}" if len(morceaux) == 3 else (iso or "")


def mois_fr(mois: str) -> str:
    """« 2026-11 » → « nov. 2026 »."""
    noms = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
    try:
        a, m = mois.split("-")
        return f"{noms[int(m) - 1]} {a}"
    except (ValueError, IndexError):
        return mois


def sans_accents_maj(texte: str) -> str:
    """Texte saisi par l'utilisateur, mis au format des noms de rue normalisés (majuscules sans accents)."""
    return sans_accents(texte).upper().replace("’", "'").replace("-", " ").strip()
