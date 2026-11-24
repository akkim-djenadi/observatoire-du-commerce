"""Graphiques de la comparaison entre villes."""
import pandas as pd
import plotly.graph_objects as go

from ui_charts import ANTHRACITE, _style

# Palette validée (daltonisme, lisibilité) : Montpellier garde toujours le terracotta de l'Observatoire du Commerce
COULEUR_MONTPELLIER = "#BB502E"
PALETTE_VILLES = ("#2a78d6", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6")
MAX_VILLES = 1 + len(PALETTE_VILLES)
VILLE_REFERENCE = "Montpellier"


def courbes(serie: pd.DataFrame, couleurs: dict[str, str], unite: str) -> go.Figure:
    """Une courbe par ville. Étiquette en bout de ligne jusqu'à 4 villes, légende au-delà."""
    villes = list(dict.fromkeys(serie["ville"]))
    etiqueter = len(villes) <= 4
    fig = go.Figure()
    for ville in villes:
        d = serie[serie["ville"] == ville].sort_values("mois")
        ref = ville == VILLE_REFERENCE
        fig.add_trace(go.Scatter(
            x=d["mois"], y=d["valeur"], name=ville, mode="lines",
            line=dict(color=couleurs.get(ville, ANTHRACITE), width=3.5 if ref else 2),
            hovertemplate="%{y:.2f} " + unite + "<extra>" + ville + "</extra>",
        ))
        if etiqueter and d["valeur"].notna().any():
            dernier = d.dropna(subset=["valeur"]).iloc[-1]
            fig.add_annotation(x=dernier["mois"], y=dernier["valeur"], text=ville, showarrow=False,
                               xanchor="left", xshift=8,
                               font=dict(size=12, color=ANTHRACITE, family="Montserrat" if ref else None))
    fig = _style(fig, 440)
    fig.update_layout(hovermode="x unified", showlegend=True, margin=dict(r=110 if etiqueter else 8))
    fig.update_xaxes(tickformat="%m/%Y")
    fig.update_yaxes(title=dict(text=unite, font=dict(size=12)))
    return fig


def classement(synthese: pd.DataFrame, colonne: str, couleurs: dict[str, str]) -> go.Figure:
    d = synthese.dropna(subset=[colonne]).sort_values(colonne)
    fig = go.Figure(go.Bar(
        x=d[colonne], y=d["Ville"], orientation="h", text=d[colonne], textposition="outside", cliponaxis=False,
        marker=dict(color=[couleurs.get(v, ANTHRACITE) for v in d["Ville"]], line=dict(width=0)),
        hovertemplate="%{y} : %{x}<extra></extra>",
    ))
    fig = _style(fig, 60 + 46 * len(d))
    fig.update_xaxes(range=[0, float(d[colonne].max()) * 1.18 if len(d) else 1])
    return fig
