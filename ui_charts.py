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


def evolution(annonces: pd.DataFrame, debut: date, fin: date) -> go.Figure:
    """Courbes mensuelles : total, ouvertures, conversions, clôtures. Mois incomplets marqués d'un astérisque."""
    mois = pd.period_range(annonces["mois"].min(), annonces["mois"].max(), freq="M").to_timestamp()
    partiels = mois_incomplets(debut, fin)
    libelles = [_mois_fr(m) + (" *" if m in partiels else "") for m in mois]
    series = {"Toutes les annonces": annonces.groupby("mois").size()}
    for nom, types in GROUPES_EVOLUTION.items():
        series[nom] = annonces[annonces["type"].isin(types)].groupby("mois").size()
    fig = go.Figure()
    for nom, s in series.items():
        fig.add_trace(go.Scatter(
            x=libelles, y=s.reindex(mois, fill_value=0).values, name=nom, mode="lines+markers",
            line=dict(color=COULEURS_EVOLUTION[nom], width=2.5 if nom != "Toutes les annonces" else 2,
                      dash="dot" if nom == "Toutes les annonces" else "solid"),
            marker=dict(size=8, line=dict(color="white", width=2)),
            hovertemplate="%{y} annonce(s)<extra>" + nom + "</extra>",
        ))
    fig = _style(fig, 400)
    fig.update_layout(hovermode="x unified", legend=dict(y=-0.16), margin=dict(b=40))
    return fig


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


def chronologie(annonces: pd.DataFrame) -> go.Figure:
    d = annonces.groupby(["mois", "type"]).size().reset_index(name="n").sort_values("mois")
    d["mois_fr"] = d["mois"].map(_mois_fr)
    fig = px.bar(d, x="mois_fr", y="n", color="type", color_discrete_map=COULEURS_TYPE,
                 category_orders={"type": list(COULEURS_TYPE), "mois_fr": list(dict.fromkeys(d["mois_fr"]))},
                 labels={"n": "Annonces", "mois_fr": "Mois de parution", "type": "Type"})
    fig.update_traces(marker_line_width=0)
    fig = _style(fig, 400)
    fig.update_layout(legend=dict(y=-0.18), margin=dict(b=40))
    return fig
