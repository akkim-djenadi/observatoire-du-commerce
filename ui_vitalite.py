"""Graphiques de la vitalité commerciale (indice, composantes, cartes des rues et des locaux)."""
from adresses import joli_nom_rue
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from config import COMEDIE, ZONE_ORDER
from indice import COMPOSANTES
from ui_charts import ANTHRACITE, TERRACOTTA, ZONES_COURTES, _style
from vitalite_data import mois_fr

NIVEAUX = (  # (seuil minimal, libellé, couleur) — couleur toujours accompagnée du libellé
    (60, "Dynamique", "#5E8A3A"),
    (40, "À surveiller", "#D9952F"),
    (0, "Fragile", TERRACOTTA),
)
COULEURS_NIVEAU = {libelle: couleur for _, libelle, couleur in NIVEAUX}
COULEURS_LIGNES = {"Centre-ville": ANTHRACITE, "Écusson": TERRACOTTA, "Hypercentre": "#2a78d6", "Faubourgs": "#1baf7a"}
COULEURS_LOCAUX = {"Confirmé par l'Observatoire": "#D9952F", "Probablement libéré (à vérifier)": "#6B6460"}


def niveau(valeur: float | None) -> str:
    if valeur is None or pd.isna(valeur):
        return "Non calculé"
    return next(libelle for seuil, libelle, _ in NIVEAUX if valeur >= seuil)


def _nom_court(nom: str) -> str:
    return ZONES_COURTES.get(nom, nom)


def courbe_indice(historique: pd.DataFrame) -> go.Figure:
    """Indice du centre et des trois zones, mois par mois. La période reconstituée est grisée."""
    h = historique[historique["niveau"].isin(["centre", "zone"])].copy()
    h["serie"] = h["nom"].map(_nom_court)
    mois = sorted(h["mois"].unique())
    etiquettes = [mois_fr(m) for m in mois]
    fig = go.Figure()
    for serie in sorted(h["serie"].unique(), key=lambda s: (s != "Centre-ville", ZONE_ORDER.get(s, 9))):
        d = h[h["serie"] == serie].set_index("mois").reindex(mois)
        fig.add_trace(go.Scatter(
            x=etiquettes, y=d["indice"], name=serie, mode="lines+markers",
            line=dict(color=COULEURS_LIGNES.get(serie, ANTHRACITE), width=3.5 if serie == "Centre-ville" else 2),
            marker=dict(size=8, line=dict(color="white", width=2)),
            hovertemplate="%{y:.0f}/100<extra>" + serie + "</extra>"))
    reconstitues = [i for i, m in enumerate(mois) if (h.loc[h["mois"] == m, "methode"] == "reconstitué").all()]
    if reconstitues:
        fig.add_vrect(x0=-0.5, x1=max(reconstitues) + 0.5, fillcolor="#EADFD6", opacity=0.45, line_width=0,
                      annotation_text="reconstitué", annotation_position="top left",
                      annotation_font=dict(size=11, color="#6B6460"))
    fig = _style(fig, 380)
    fig.update_layout(hovermode="x unified")
    fig.update_yaxes(range=[0, 100], dtick=20)
    return fig


def barres_composantes(ligne: pd.Series) -> go.Figure:
    """Score de chaque composante (0-100), avec la valeur brute au survol."""
    noms, scores, couleurs, survols = [], [], [], []
    for c in COMPOSANTES:
        s = ligne.get(f"score_{c.cle}")
        noms.append(f"{c.libelle} ({round(c.poids * 100)} %)")
        scores.append(None if pd.isna(s) else s)
        couleurs.append(COULEURS_NIVEAU.get(niveau(s), "#CCCCCC"))
        brut = ligne.get(f"brut_{c.cle}")
        survols.append("données insuffisantes" if pd.isna(brut) else f"valeur brute : {brut:.3f} ({c.unite})")
    fig = go.Figure(go.Bar(x=scores, y=noms, orientation="h", marker=dict(color=couleurs, line=dict(width=0)),
                           text=["—" if s is None else f"{s:.0f}" for s in scores], textposition="outside",
                           cliponaxis=False, customdata=survols, hovertemplate="%{customdata}<extra></extra>"))
    fig = _style(fig, 320)
    fig.update_xaxes(range=[0, 110], dtick=20)
    fig.update_yaxes(autorange="reversed")
    return fig


def carte_rues(rues: pd.DataFrame) -> go.Figure:
    """Une bulle par rue : taille = nombre de commerces, couleur = niveau de vitalité."""
    d = rues.dropna(subset=["latitude", "longitude"]).assign(niveau=lambda x: x["indice"].map(niveau))
    fig = px.scatter_map(d, lat="latitude", lon="longitude", size="stock", size_max=26, color="niveau",
                         color_discrete_map=COULEURS_NIVEAU, category_orders={"niveau": list(COULEURS_NIVEAU)},
                         hover_name="nom", hover_data={"indice": ":.0f", "stock": True, "latitude": False,
                                                       "longitude": False, "niveau": False},
                         labels={"indice": "Indice", "stock": "Commerces"},
                         zoom=14.4, center={"lat": COMEDIE[0], "lon": COMEDIE[1] - 0.002}, map_style="carto-positron")
    return _style(fig, 520)


def carte_locaux(locaux: pd.DataFrame) -> go.Figure:
    d = locaux.dropna(subset=["latitude", "longitude"])
    fig = px.scatter_map(d, lat="latitude", lon="longitude", color="statut", color_discrete_map=COULEURS_LOCAUX,
                         hover_name="adresse", hover_data={"detail": True, "latitude": False, "longitude": False,
                                                           "statut": False},
                         labels={"detail": ""}, zoom=14.4, center={"lat": COMEDIE[0], "lon": COMEDIE[1] - 0.002},
                         map_style="carto-positron")
    fig.update_traces(marker=dict(size=13, opacity=0.9))
    return _style(fig, 520)


def classement_rues(rues: pd.DataFrame, n: int = 8) -> go.Figure:
    """Les rues les plus dynamiques et les plus fragiles, côte à côte sur une même échelle."""
    tri = rues.dropna(subset=["indice"]).sort_values("indice")
    d = pd.concat([tri.head(n), tri.tail(n)]).drop_duplicates("nom")
    fig = go.Figure(go.Bar(
        x=d["indice"], y=d["nom"].map(joli_nom_rue), orientation="h", text=d["indice"].round().astype(int),
        textposition="outside", cliponaxis=False,
        marker=dict(color=[COULEURS_NIVEAU[niveau(v)] for v in d["indice"]], line=dict(width=0)),
        customdata=d["indice"].map(niveau), hovertemplate="%{y} : %{x:.0f}/100 (%{customdata})<extra></extra>"))
    fig = _style(fig, 60 + 26 * len(d))
    fig.update_xaxes(range=[0, 105], dtick=20)
    return fig


def barres_offre(repartition: pd.Series) -> go.Figure:
    d = repartition.sort_values()
    fig = go.Figure(go.Bar(x=d.values, y=d.index, orientation="h", text=d.values, textposition="outside",
                           cliponaxis=False, marker=dict(color=TERRACOTTA, line=dict(width=0)),
                           hovertemplate="%{y} : %{x} commerces<extra></extra>"))
    return _style(fig, 60 + 34 * len(d))
