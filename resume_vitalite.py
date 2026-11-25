"""Grands chiffres et phrases de synthèse de la vitalité commerciale (partagés par l'onglet et la note PDF)."""
from datetime import date

from adresses import joli_nom_rue
import pandas as pd

from explications import nombre
from periode import mois_avant
from vitalite_data import DonneesVitalite, mois_fr

SEUIL_STABLE_PTS = 2
ZONES_ARTICLE = {"Écusson (cœur historique)": "l'Écusson", "Hypercentre (Comédie / Gare / Polygone-Antigone)":
                 "l'hypercentre", "Faubourgs du centre": "les faubourgs"}


def _pourcent_signe(part: float) -> str:
    """−0,03 → « −3 % » (signe moins typographique, espace insécable)."""
    return f"{part * 100:+.0f}\u202f%".replace("-", "\u2212")


def entier_signe(n: int) -> str:
    """−8 / +5 / 0, avec le signe moins typographique."""
    return (f"{n:+d}" if n else "0").replace("-", "\u2212")


def evolution_12_mois(historique: pd.DataFrame, nom: str, mois: str) -> float | None:
    """Évolution de l'indice (en points) sur 12 mois, si l'historique remonte assez loin."""
    a, m = (int(x) for x in mois.split("-"))
    avant = mois_avant(date(a, m, 1), 12).strftime("%Y-%m")
    v_avant = historique[(historique["mois"] == avant) & (historique["nom"] == nom)]["indice"]
    v_mtn = historique[(historique["mois"] == mois) & (historique["nom"] == nom)]["indice"]
    return round(v_mtn.iat[0] - v_avant.iat[0], 1) if len(v_avant) and len(v_mtn) else None


def _evolution_prix_12_mois(dvf: pd.DataFrame, jour: date) -> tuple[float | None, int]:
    ventes = dvf.assign(date=pd.to_datetime(dvf["date"], errors="coerce"))
    prix = ventes.loc[ventes["date"] > pd.Timestamp(mois_avant(jour, 12)), "prix_m2"].dropna()
    return (float(prix.median()) if len(prix) else None), int(len(prix))


def chiffres(d: DonneesVitalite, jour: date) -> dict[str, float | int | None]:
    """Les grands chiffres du centre-ville sur les 12 derniers mois."""
    centre = d.indice_du_mois()
    centre = centre[centre["niveau"] == "centre"].iloc[0]
    prix, ventes = _evolution_prix_12_mois(d.dvf, jour)
    return {
        "indice": centre["indice"], "delta": evolution_12_mois(d.historique, centre["nom"], d.dernier_mois),
        "defaillances": int(centre["brut_nb_defaillances"]),
        "solde": int(centre["brut_ouvertures"] - centre["brut_fermetures"]),
        "ouvertures": int(centre["brut_ouvertures"]), "fermetures": int(centre["brut_fermetures"]),
        "prix_m2": prix, "ventes": ventes, "evolution_prix": centre["brut_prix"],
        "diversite": centre["brut_diversite"], "stock": int(centre["brut_stock"]),
    }


def _niveau(valeur: float) -> str:
    return "dynamique" if valeur >= 60 else ("à surveiller" if valeur >= 40 else "fragile")


def phrases_essentiel(d: DonneesVitalite, c: dict) -> list[str]:
    """Quatre à six phrases qui résument le mois, en langage simple."""
    p = [f"L'indice de vitalité du centre-ville s'établit à **{c['indice']:.0f}/100** en {mois_fr(d.dernier_mois)}, "
         f"un niveau **{_niveau(c['indice'])}**"
         + ("." if c["delta"] is None else (
             ", stable sur un an." if abs(c["delta"]) < SEUIL_STABLE_PTS else
             f", en {'hausse' if c['delta'] > 0 else 'baisse'} de {abs(c['delta']):.0f} points sur un an."))]
    p.append(f"Sur 12 mois, **{c['ouvertures']} commerces ont ouvert et {c['fermetures']} ont fermé** "
             f"(solde {entier_signe(c['solde'])}), sur {nombre(c['stock'])} commerces actifs.")
    p.append(f"**{c['defaillances']} commerces** sont entrés en procédure collective (redressement, sauvegarde ou "
             "liquidation) au cours des 12 derniers mois.")
    if c["prix_m2"] is not None:
        evol = c.get("evolution_prix")
        p.append(f"Le prix médian des locaux commerciaux vendus atteint **{nombre(c['prix_m2'])} €/m²** "
                 f"({c['ventes']} ventes)"
                 + ("." if evol is None or pd.isna(evol) else
                    f", {_pourcent_signe(evol)} par rapport à l'année précédente."))
    courant = d.indice_du_mois()
    zones = courant[courant["niveau"] == "zone"].sort_values("indice")
    if len(zones) >= 2:
        haut, bas = zones.iloc[-1], zones.iloc[0]
        verbe = "affichent" if ZONES_ARTICLE[haut["nom"]].startswith("les") else "affiche"
        p.append(f"Par zone, **{ZONES_ARTICLE[haut['nom']]}** {verbe} "
                 f"le meilleur indice ({haut['indice']:.0f}/100), **{ZONES_ARTICLE[bas['nom']]}** le plus faible "
                 f"({bas['indice']:.0f}/100).")
    rues = courant[courant["niveau"] == "rue"].sort_values("indice")
    if len(rues) >= 6:
        fragiles = ", ".join(joli_nom_rue(n) for n in rues["nom"].head(3))
        dynamiques = ", ".join(joli_nom_rue(n) for n in rues["nom"].tail(3)[::-1])
        p.append(f"Rues à suivre de près : {fragiles}. Rues les plus dynamiques : {dynamiques}.")
    return p
