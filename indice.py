"""Indice de vitalité commerciale sur 100, par zone, pour le centre et par rue.

Six composantes, chacune ramenée sur 100 par des bornes fixes (un score ne dépend pas des autres rues).
Une composante sans données suffisantes est retirée et les poids restants sont recalculés.
"""
from dataclasses import dataclass
from datetime import date

import pandas as pd

import locaux
import offre
from config import RUE_MIN_COMMERCES, ZONE_ORDER
from periode import mois_avant

TYPES_DEFAILLANCE = ("Redressement judiciaire (ouverture)", "Sauvegarde", "Liquidation judiciaire (ouverture)")
VENTES_MIN = 5          # ventes avec prix par période pour comparer les prix
LISSAGE_RUE = 20        # poids (en commerces) de la zone dans le taux d'une rue : une petite rue tend vers sa zone
TAUX_LISSES = ("solde", "defaillances", "vacance")
MOIS_RECONSTITUES = 12  # à la première collecte, on reconstitue l'indice des 12 derniers mois
CENTRE = "Centre-ville"


@dataclass(frozen=True)
class Composante:
    cle: str
    libelle: str
    poids: float
    zero: float      # valeur brute qui vaut 0 point
    cent: float      # valeur brute qui vaut 100 points
    unite: str


COMPOSANTES = (
    Composante("solde", "Solde ouvertures − fermetures (12 mois)", 0.30, -0.05, 0.05, "% du stock"),
    Composante("defaillances", "Défaillances (12 mois)", 0.25, 0.06, 0.0, "% du stock"),
    Composante("diversite", "Diversité de l'offre", 0.15, 0.0, 1.0, "indice 0-1"),
    Composante("independants", "Part d'indépendants", 0.10, 0.0, 1.0, "part"),
    Composante("vacance", "Locaux probablement libérés", 0.10, 0.15, 0.0, "% du stock"),
    Composante("prix", "Évolution du prix des locaux au m²", 0.10, -0.20, 0.20, "variation"),
)


def score(c: Composante, valeur: float | None) -> float | None:
    if valeur is None or pd.isna(valeur):
        return None
    part = (valeur - c.zero) / (c.cent - c.zero)
    return round(100 * min(max(part, 0.0), 1.0), 1)


def indice(scores: dict[str, float | None]) -> float | None:
    """Moyenne pondérée des composantes disponibles."""
    dispo = [(c.poids, scores[c.cle]) for c in COMPOSANTES if scores.get(c.cle) is not None]
    poids = sum(p for p, _ in dispo)
    return round(sum(p * s for p, s in dispo) / poids, 1) if poids else None


def _evolution_prix(dvf: pd.DataFrame, jour: date) -> float | None:
    if dvf.empty:
        return None
    d = dvf.assign(date=pd.to_datetime(dvf["date"], errors="coerce"),
                   prix_m2=pd.to_numeric(dvf["prix_m2"], errors="coerce")).dropna(subset=["prix_m2", "date"])
    t, t12, t24 = (pd.Timestamp(x) for x in (jour, mois_avant(jour, 12), mois_avant(jour, 24)))
    recent, avant = d[(d["date"] > t12) & (d["date"] <= t)], d[(d["date"] > t24) & (d["date"] <= t12)]
    if len(recent) < VENTES_MIN or len(avant) < VENTES_MIN:
        return None
    return round(recent["prix_m2"].median() / avant["prix_m2"].median() - 1, 3)


def valeurs_brutes(etab: pd.DataFrame, proc: pd.DataFrame, dvf: pd.DataFrame, liberes: pd.DataFrame,
                   jour: date) -> dict[str, float | None]:
    """Valeurs brutes des six composantes pour un groupe de commerces (zone, rue…) à une date."""
    actifs = offre.actifs_a(etab, jour)
    stock = len(actifs)
    debut = mois_avant(jour, 12)
    ouvertures, fermetures = offre.mouvements(etab, debut, jour)
    jugements = proc["date_jugement"].fillna("").astype(str) if not proc.empty else pd.Series(dtype=str)
    defaillances = int((proc["type"].isin(TYPES_DEFAILLANCE)
                        & jugements.between(debut.isoformat(), jour.isoformat())).sum()) if not proc.empty else 0
    return {
        "stock": stock,
        "solde": (ouvertures - fermetures) / stock if stock else None,
        "defaillances": defaillances / stock if stock else None,
        "diversite": offre.diversite(actifs),
        "independants": offre.part_independants(actifs),
        "vacance": len(liberes) / stock if stock else None,
        "prix": _evolution_prix(dvf, jour),
        "ouvertures": ouvertures, "fermetures": fermetures, "nb_defaillances": defaillances,
    }


def lisser(brutes_rue: dict, brutes_zone: dict, poids_zone: int = LISSAGE_RUE) -> dict:
    """Rapproche les taux d'une rue de ceux de sa zone, d'autant plus que la rue compte peu de commerces.

    Sans cela, une seule fermeture dans une rue de 10 commerces ferait chuter son indice (lissage bayésien).
    """
    n = brutes_rue["stock"] or 0
    lisses = dict(brutes_rue)
    for cle in TAUX_LISSES:
        r, z = brutes_rue.get(cle), brutes_zone.get(cle)
        if r is not None and z is not None:
            lisses[cle] = (n * r + poids_zone * z) / (n + poids_zone)
    return lisses


def _ligne(niveau: str, nom: str, zone: str, brutes: dict, jour: date, methode: str) -> dict:
    scores = {c.cle: score(c, brutes[c.cle]) for c in COMPOSANTES}
    return {"mois": jour.strftime("%Y-%m"), "niveau": niveau, "nom": nom, "zone": zone,
            "indice": indice(scores), "methode": methode, **{f"brut_{k}": v for k, v in brutes.items()},
            **{f"score_{k}": v for k, v in scores.items()}}


def _filtre(df: pd.DataFrame, colonne: str, valeur: str) -> pd.DataFrame:
    return df[df[colonne] == valeur] if not df.empty else df


def calculer(donnees: dict[str, pd.DataFrame], jour: date, methode: str = "mesuré") -> pd.DataFrame:
    """Indice du centre, de chaque zone et de chaque rue d'au moins 8 commerces, à une date."""
    etab, proc, dvf = donnees["etablissements"], donnees["procedures"], donnees["dvf"]
    lib = locaux.liberes(etab, proc, jour)
    lignes = [_ligne("centre", CENTRE, "", valeurs_brutes(etab, proc, dvf, lib, jour), jour, methode)]
    par_zone = {}
    for zone in sorted(etab["zone"].dropna().unique(), key=lambda z: ZONE_ORDER.get(z, 9)):
        f = lambda df: _filtre(df, "zone", zone)  # noqa: E731
        par_zone[zone] = valeurs_brutes(f(etab), f(proc), f(dvf), f(lib), jour)
        lignes.append(_ligne("zone", zone, zone, par_zone[zone], jour, methode))
    actifs = offre.actifs_a(etab, jour)
    rues = actifs.groupby("voie").size()
    for voie in sorted(rues[rues >= RUE_MIN_COMMERCES].index):
        f = lambda df: _filtre(df, "voie", voie)  # noqa: E731
        zone = actifs.loc[actifs["voie"] == voie, "zone"].mode().iat[0]
        brutes = lisser(valeurs_brutes(f(etab), f(proc), f(dvf), f(lib), jour), par_zone[zone])
        ligne = _ligne("rue", voie, zone, brutes, jour, methode)
        position = actifs.loc[actifs["voie"] == voie, ["latitude", "longitude"]].astype(float).median()
        lignes.append({**ligne, "latitude": position["latitude"], "longitude": position["longitude"]})
    return pd.DataFrame(lignes)


def mettre_a_jour_historique(historique: pd.DataFrame | None, donnees: dict[str, pd.DataFrame],
                             aujourd_hui: date) -> pd.DataFrame:
    """Ajoute (ou remplace) le mois en cours. À la première collecte, reconstitue les 12 mois précédents."""
    nouveaux = [calculer(donnees, aujourd_hui)]
    if historique is None or historique.empty:
        nouveaux += [calculer(donnees, mois_avant(aujourd_hui, m), "reconstitué")
                     for m in range(1, MOIS_RECONSTITUES + 1)]
    frais = pd.concat(nouveaux, ignore_index=True)
    if historique is not None and not historique.empty:
        historique = historique[~historique["mois"].isin(frais["mois"])]
        frais = pd.concat([historique, frais], ignore_index=True)
    return frais.sort_values(["mois", "niveau", "nom"]).reset_index(drop=True)
