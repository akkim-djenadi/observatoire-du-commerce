"""Date d'ouverture des commerces en difficulté, retrouvée dans les établissements Sirene collectés.

La fiche INSEE de l'entreprise ne donne que sa date de création, parfois bien antérieure à l'ouverture
de la boutique (déménagement, deuxième magasin…). On cherche donc l'établissement lui-même : même SIREN,
même rue. À défaut, on garde la date de création de l'entreprise, en le signalant.
"""
from dataclasses import replace

import pandas as pd

from adresses import normaliser_voie
from pipeline import Commerce, Rapport

SOURCE_ETABLISSEMENT = "Établissement"
SOURCE_ENTREPRISE = "Entreprise"


def _date_etablissement(c: Commerce, etab_siren: pd.DataFrame) -> str:
    """Date d'ouverture de l'établissement du commerce, ou chaîne vide si on ne peut pas le reconnaître."""
    if etab_siren.empty:
        return ""
    dates = etab_siren["date_creation"].fillna("").astype(str)
    meme_rue = etab_siren[etab_siren["voie"] == normaliser_voie(c.adresse)]
    if not meme_rue.empty:
        candidats = meme_rue["date_creation"].fillna("").astype(str)
        # Plusieurs établissements dans la même rue : le plus récent ouvert avant le dernier jugement
        avant = candidats[(candidats != "") & (candidats <= (c.date_jugement or "9999"))]
        return avant.max() if not avant.empty else candidats.max()
    return dates.iat[0] if len(etab_siren) == 1 else ""


def avec_dates_ouverture(rap: Rapport, etablissements: pd.DataFrame) -> Rapport:
    """Rapport dont chaque commerce porte sa date d'ouverture et la source de cette date."""
    par_siren = (dict(tuple(etablissements.groupby("siren")))
                 if not etablissements.empty and "siren" in etablissements.columns else {})
    commerces = []
    for c in rap.commerces:
        date = _date_etablissement(c, par_siren.get(c.siren, pd.DataFrame())) if c.siren else ""
        source = SOURCE_ETABLISSEMENT if date else (SOURCE_ENTREPRISE if c.date_creation else "")
        commerces.append(replace(c, date_ouverture=date or c.date_creation, source_ouverture=source))
    return replace(rap, commerces=tuple(commerces))
