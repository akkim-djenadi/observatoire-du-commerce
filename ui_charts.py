"""Graphiques Plotly aux couleurs de l'Observatoire du Commerce."""
import calendar
from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from config import COMEDIE
from ui_data import COULEURS_STATUT, ORDRE_STATUTS

ANTHRACITE = "#2B2B2B"
TERRACOTTA = "#BB502E"
POLICE = "Open Sans, sans-serif"
MOIS_COURTS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
# Même logique de couleur que les statuts : ocre = encore sauvable, terracotta = liquidation, gris = clôturé
COULEURS_TYPE = {
    "Redressement judiciaire (ouverture)": "#E2A24A",
    "Sauvegarde": "#7A9A4E",
    "Plan (redressement / cession)": "#3F7C8C",
    "État / liste des créances": "#C9B29B",
    "Liquidation judiciaire (ouverture)": "#BB502E",
    "Liquidation judiciaire (conversion)": "#8A3A20",
    "Clôture pour insuffisance d'actif": "#6B6460",
    "Faillite personnelle": "#2B2B2B",
    "Clôture (extinction du passif)": "#9BB59A",
    "Autre jugement / ordonnance": "#D9D2CC",
}
ZONES_COURTES = {
    "Écusson (cœur historique)": "Écusson",
    "Hypercentre (Comédie / Gare / Polygone-Antigone)": "Hypercentre",
    "Faubourgs du centre": "Faubourgs",
}


def _style(fig: go.Figure, hauteur: int = 360) -> go.Figure:
    fig.update_layout(
        height=hauteur, margin=dict(l=8, r=8, t=8, b=8), font=dict(family=POLICE, color=ANTHRACITE, size=13),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="top", y=-0.12, x=0, title=None, font=dict(size=12)),
        hoverlabel=dict(font_family=POLICE, bgcolor="white"),
        separators=", ",  # virgule décimale, espace pour les milliers
    )
    fig.update_xaxes(showgrid=False, title=None)
    fig.update_yaxes(gridcolor="#EADFD6", zeroline=False, title=None)
    return fig


def carte(df: pd.DataFrame) -> go.Figure:
    pts = df.dropna(subset=["latitude", "longitude"])
    fig = px.scatter_map(
        pts, lat="latitude", lon="longitude", color="statut", color_discrete_map=COULEURS_STATUT,
        category_orders={"statut": ORDRE_STATUTS}, hover_name="nom",
        hover_data={"enseigne": True, "activite": True, "adresse": True, "date_jugement": True,
                    "latitude": False, "longitude": False, "statut": False},
        labels={"enseigne": "Enseigne", "activite": "Activité", "adresse": "Adresse",
                "date_jugement": "Dernier jugement"},
        zoom=14.6, center={"lat": COMEDIE[0], "lon": COMEDIE[1] - 0.002}, map_style="carto-positron",
    )
    fig.update_traces(marker=dict(size=13, opacity=0.9))
    return _style(fig, 560)


def par_zone(df: pd.DataFrame) -> go.Figure:
    d = df.assign(zone_c=df["zone"].map(ZONES_COURTES)).groupby(["zone_c", "statut"]).size().reset_index(name="n")
    fig = px.bar(d, y="zone_c", x="n", color="statut", orientation="h", color_discrete_map=COULEURS_STATUT,
                 category_orders={"statut": ORDRE_STATUTS, "zone_c": list(ZONES_COURTES.values())},
                 labels={"n": "Commerces", "zone_c": "Zone", "statut": "Statut"})
    fig.update_traces(marker_line_width=0)
    return _style(fig, 300)


def par_secteur(df: pd.DataFrame) -> go.Figure:
    d = df.groupby("secteur").size().sort_values().reset_index(name="n")
    fig = px.bar(d, y="secteur", x="n", orientation="h", text="n", labels={"n": "Commerces", "secteur": ""})
    fig.update_traces(marker_color=TERRACOTTA, marker_line_width=0, textposition="outside", cliponaxis=False)
    return _style(fig, 300)


GROUPES_EVOLUTION = {
    "Ouvertures (redressement, sauvegarde, liquidation directe)": (
        "Redressement judiciaire (ouverture)", "Sauvegarde", "Liquidation judiciaire (ouverture)"),
    "Conversions en liquidation": ("Liquidation judiciaire (conversion)",),
    "Clôtures": ("Clôture pour insuffisance d'actif", "Clôture (extinction du passif)"),
}
COULEURS_EVOLUTION = {
    "Toutes les annonces": "#6B6460",
    "Ouvertures (redressement, sauvegarde, liquidation directe)": "#eda100",
    "Conversions en liquidation": TERRACOTTA,
    "Clôtures": "#2a78d6",
}


def _series_evolution(annonces: pd.DataFrame, cle: pd.Series) -> dict[str, pd.Series]:
    """Nombre d'annonces par période (`cle`) : toutes, ouvertures, conversions, clôtures."""
    series = {"Toutes les annonces": annonces.groupby(cle).size()}
    for nom, types in GROUPES_EVOLUTION.items():
        filtre = annonces["type"].isin(types)
        series[nom] = annonces[filtre].groupby(cle[filtre]).size()
    return series


def _courbes(periodes: list, libelles: list[str], series: dict[str, pd.Series]) -> go.Figure:
    fig = go.Figure()
    for nom, s in series.items():
        fig.add_trace(go.Scatter(
            x=libelles, y=s.reindex(periodes, fill_value=0).values, name=nom, mode="lines+markers",
            line=dict(color=COULEURS_EVOLUTION[nom], width=2.5 if nom != "Toutes les annonces" else 2,
                      dash="dot" if nom == "Toutes les annonces" else "solid"),
            marker=dict(size=8, line=dict(color="white", width=2)),
            hovertemplate="%{y} annonce(s)<extra>" + nom + "</extra>",
        ))
    fig = _style(fig, 400)
    fig.update_layout(hovermode="x unified", legend=dict(y=-0.16), margin=dict(b=40))
    fig.update_xaxes(type="category")  # sinon « 2025 » est lu comme un nombre
    return fig


def evolution(annonces: pd.DataFrame, debut: date, fin: date) -> go.Figure:
    """Courbes mensuelles : total, ouvertures, conversions, clôtures. Mois incomplets marqués d'un astérisque."""
    mois = list(pd.period_range(annonces["mois"].min(), annonces["mois"].max(), freq="M").to_timestamp())
    partiels = mois_incomplets(debut, fin)
    libelles = [_mois_fr(m) + (" *" if m in partiels else "") for m in mois]
    return _courbes(mois, libelles, _series_evolution(annonces, annonces["mois"]))


def contient_annee_entiere(debut: date, fin: date) -> bool:
    """Vrai si la période couvre au moins une année civile complète : la vue par année a alors du sens."""
    return any(debut <= date(a, 1, 1) and date(a, 12, 31) <= fin for a in range(debut.year, fin.year + 1))


def annees_incompletes(debut: date, fin: date) -> set[int]:
    """Première et dernière année de la période, si elles ne sont pas couvertes en entier."""
    partielles = set()
    if (debut.month, debut.day) != (1, 1):
        partielles.add(debut.year)
    if (fin.month, fin.day) != (12, 31):
        partielles.add(fin.year)
    return partielles


def evolution_par_annee(annonces: pd.DataFrame, debut: date, fin: date) -> go.Figure:
    """Mêmes courbes qu'`evolution`, une valeur par année. Années incomplètes marquées d'un astérisque."""
    annees = list(range(debut.year, fin.year + 1))
    partielles = annees_incompletes(debut, fin)
    libelles = [f"{a}" + (" *" if a in partielles else "") for a in annees]
    return _courbes(annees, libelles, _series_evolution(annonces, annonces["mois"].dt.year))


def mois_incomplets(debut: date, fin: date) -> set[pd.Timestamp]:
    """Premier et dernier mois de la période, s'ils ne sont pas couverts en entier."""
    partiels = set()
    if debut.day > 1:
        partiels.add(pd.Timestamp(debut.year, debut.month, 1))
    if fin.day < calendar.monthrange(fin.year, fin.month)[1]:
        partiels.add(pd.Timestamp(fin.year, fin.month, 1))
    return partiels


def _mois_fr(ts: pd.Timestamp) -> str:
    return f"{MOIS_COURTS[ts.month - 1]} {ts.year}"


def _barres_par_type(d: pd.DataFrame, axe: str) -> go.Figure:
    """Barres empilées par type ; `d` a les colonnes periode, type, n (déjà triées)."""
    fig = px.bar(d, x="periode", y="n", color="type", color_discrete_map=COULEURS_TYPE,
                 category_orders={"type": list(COULEURS_TYPE), "periode": list(dict.fromkeys(d["periode"]))},
                 labels={"n": "Annonces", "periode": axe, "type": "Type"})
    fig.update_traces(marker_line_width=0)
    fig = _style(fig, 400)
    fig.update_layout(legend=dict(y=-0.18), margin=dict(b=40))
    fig.update_xaxes(type="category")  # sinon « 2025 » est lu comme un nombre
    return fig


def chronologie(annonces: pd.DataFrame) -> go.Figure:
    d = annonces.groupby(["mois", "type"]).size().reset_index(name="n").sort_values("mois")
    d["periode"] = d["mois"].map(_mois_fr)
    return _barres_par_type(d, "Mois de parution")


def chronologie_par_annee(annonces: pd.DataFrame, debut: date, fin: date) -> go.Figure:
    """Annonces publiées par année et par type. Années incomplètes marquées d'un astérisque."""
    partielles = annees_incompletes(debut, fin)
    d = (annonces.assign(annee=annonces["mois"].dt.year).groupby(["annee", "type"]).size()
         .reset_index(name="n").sort_values("annee"))
    d["periode"] = d["annee"].map(lambda a: f"{a}" + (" *" if a in partielles else ""))
    return _barres_par_type(d, "Année de parution")
