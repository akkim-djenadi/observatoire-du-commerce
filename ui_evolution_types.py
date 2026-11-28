"""Liquidations, redressements, sauvegardes : courbe de l'année X à l'année Y et taux d'évolution."""
from dataclasses import dataclass
from datetime import date

import pandas as pd
import plotly.graph_objects as go

from evolution_annuelle import Fenetre, compteur_dates, fenetre_commune, taux_evolution
from ui_charts import ANTHRACITE, COULEURS_TYPE, TERRACOTTA, _style
from ui_evolution import VERT, _dates, _texte_pct, est_defaillance

TOUTES = "Toutes les défaillances"
LIQUIDATIONS = "Liquidations judiciaires"
REDRESSEMENTS = "Redressements judiciaires"
SAUVEGARDES = "Sauvegardes"
CONVERSIONS = "Conversions en liquidation"

# Les trois premières, additionnées, donnent « Toutes les défaillances » (jugements d'ouverture).
# Une conversion est un redressement qui échoue : ce n'est pas une nouvelle défaillance.
TYPES_CATEGORIE = {
    LIQUIDATIONS: "Liquidation judiciaire (ouverture)",
    REDRESSEMENTS: "Redressement judiciaire (ouverture)",
    SAUVEGARDES: "Sauvegarde",
    CONVERSIONS: "Liquidation judiciaire (conversion)",
}
COULEURS = {TOUTES: ANTHRACITE} | {c: COULEURS_TYPE[t] for c, t in TYPES_CATEGORIE.items()}
COL_CATEGORIE = "Procédure"
COL_EVOLUTION = "Évolution (%)"
MARGE_HAUT = 1.15
MARGE_ETIQUETTES = 0.3


@dataclass(frozen=True)
class CourbeCategories:
    """Nombre de chaque procédure, année par année, sur les mêmes jours de chaque année."""
    fenetre: Fenetre
    annees: tuple[int, ...]
    valeurs: dict[str, tuple[int, ...]]

    def valeur(self, categorie: str, annee: int) -> int:
        return self.valeurs[categorie][self.annees.index(annee)]

    def taux(self, categorie: str, depart: int, arrivee: int) -> float | None:
        return taux_evolution(self.valeur(categorie, arrivee), self.valeur(categorie, depart))


def selections(annonces: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Annonces de chaque catégorie (vide si aucune annonce)."""
    if annonces.empty:
        return {c: annonces for c in COULEURS}
    ouvertures = annonces["nature"].map(est_defaillance)
    resultat = {TOUTES: annonces[ouvertures]}
    for categorie, type_ in TYPES_CATEGORIE.items():
        masque = annonces["type"] == type_
        resultat[categorie] = annonces[masque & (ouvertures if categorie != CONVERSIONS else True)]
    return resultat


def courbe_categories(annonces: pd.DataFrame, debut: date, fin: date, depart: int,
                      arrivee: int) -> CourbeCategories | None:
    """Chaque année de `depart` à `arrivee` (dans un sens ou dans l'autre), sur les jours communs."""
    annees = tuple(range(min(depart, arrivee), max(depart, arrivee) + 1))
    fenetre = fenetre_commune(debut, fin, annees)
    if fenetre is None:
        return None
    valeurs = {}
    for categorie, selection in selections(annonces).items():
        compter = compteur_dates(_dates(selection))
        valeurs[categorie] = tuple(int(compter(*fenetre.bornes(a))) for a in annees)
    return CourbeCategories(fenetre, annees, valeurs)


def graphique_courbe(courbe: CourbeCategories) -> go.Figure:
    """Une courbe par procédure, de la première à la dernière année choisie."""
    fig = go.Figure()
    libelles = [str(a) for a in courbe.annees]
    for categorie, valeurs in courbe.valeurs.items():
        toutes = categorie == TOUTES
        fig.add_trace(go.Scatter(
            x=libelles, y=list(valeurs), name=categorie, mode="lines+markers+text" if toutes else "lines+markers",
            text=[str(v) for v in valeurs] if toutes else None, textposition="top center",
            line=dict(color=COULEURS[categorie], width=2 if toutes else 2.5, dash="dot" if toutes else "solid"),
            marker=dict(size=8, line=dict(color="white", width=2)),
            hovertemplate="%{y}<extra>" + categorie + "</extra>",
        ))
    plus_haut = max((v for valeurs in courbe.valeurs.values() for v in valeurs), default=0)
    fig.update_traces(cliponaxis=False)
    fig = _style(fig, 400)
    fig.update_layout(hovermode="x unified", showlegend=True, legend=dict(orientation="h", y=-0.15),
                      margin=dict(t=30, b=40))
    fig.update_yaxes(range=[0, max(plus_haut, 1) * MARGE_HAUT])  # place pour l'étiquette du point le plus haut
    fig.update_xaxes(type="category")  # sinon « 2025 » est lu comme un nombre
    return fig


def graphique_taux(courbe: CourbeCategories, depart: int, arrivee: int) -> go.Figure:
    """Taux d'évolution de chaque procédure : rouge quand elle augmente, vert quand elle recule."""
    categories = [c for c in courbe.valeurs if courbe.taux(c, depart, arrivee) is not None][::-1]
    taux = [courbe.taux(c, depart, arrivee) for c in categories]
    fig = go.Figure(go.Bar(
        y=categories, x=taux, orientation="h", text=[_texte_pct(t) for t in taux], textposition="outside",
        cliponaxis=False, textfont=dict(size=16),
        marker=dict(color=[TERRACOTTA if t > 0 else VERT for t in taux], line=dict(width=0)),
        customdata=[[courbe.valeur(c, depart), courbe.valeur(c, arrivee)] for c in categories],
        hovertemplate="%{y} : %{text}<br>" + f"{depart} : " + "%{customdata[0]} · " + f"{arrivee} : "
                      + "%{customdata[1]}<extra></extra>",
    ))
    fig = _style(fig, 60 + 55 * max(len(categories), 1))
    fig.add_vline(x=0, line=dict(color=ANTHRACITE, width=1))
    # Place de part et d'autre pour les étiquettes : « -100,0 % » ne doit pas recouvrir le nom de la procédure
    bas, haut = min(taux + [0]), max(taux + [0])
    marge = max(haut - bas, 10) * MARGE_ETIQUETTES
    fig.update_xaxes(ticksuffix=" %", range=[bas - (marge if bas < 0 else 0), haut + (marge if haut > 0 else 0)])
    fig.update_layout(margin=dict(l=10, r=70))
    return fig


def tableau(courbe: CourbeCategories, depart: int, arrivee: int) -> pd.DataFrame:
    """Une ligne par procédure : la valeur de chaque année de la courbe, puis le taux de départ à arrivée."""
    return pd.DataFrame([
        {COL_CATEGORIE: c} | {str(a): v for a, v in zip(courbe.annees, valeurs)}
        | {COL_EVOLUTION: courbe.taux(c, depart, arrivee)}
        for c, valeurs in courbe.valeurs.items()
    ])
