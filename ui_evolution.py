"""Tableaux et graphiques du taux d'évolution d'une année sur l'autre (centre-ville et comparaison)."""
from datetime import date

import pandas as pd
import plotly.graph_objects as go

from evolution_annuelle import LigneAnnee, compteur_dates, compteur_mensuel, compteur_ratio, evolution_annuelle
from ui_charts import ANTHRACITE, TERRACOTTA, _style

VERT = "#7A9A4E"
COL_ANNEE = "Année"
COL_DEFAILLANCES = "Défaillances"
COL_EVOL_DEFAILLANCES = "Évolution des défaillances (%)"
COL_ANNONCES = "Toutes les annonces"
COL_EVOL_ANNONCES = "Évolution des annonces (%)"


def _dates(df: pd.DataFrame) -> list[date]:
    return list(pd.to_datetime(df["date_parution"]).dt.date) if not df.empty else []


def est_defaillance(nature: str) -> bool:
    """Jugement d'ouverture (redressement, sauvegarde, liquidation) : pas une liste de créances ni un plan."""
    return nature.lower().startswith("jugement d'ouverture")


def lignes_centre(annonces: pd.DataFrame, debut: date, fin: date) -> tuple[list[LigneAnnee], list[LigneAnnee]]:
    """Défaillances et ensemble des annonces du centre-ville, année par année."""
    defaillances = annonces[annonces["nature"].map(est_defaillance)] if not annonces.empty else annonces
    return (evolution_annuelle(compteur_dates(_dates(defaillances)), debut, fin),
            evolution_annuelle(compteur_dates(_dates(annonces)), debut, fin))


def tableau_centre(defaillances: list[LigneAnnee], toutes: list[LigneAnnee]) -> pd.DataFrame:
    return pd.DataFrame([{
        COL_ANNEE: d.libelle, COL_DEFAILLANCES: int(d.valeur or 0), COL_EVOL_DEFAILLANCES: d.evolution_pct,
        COL_ANNONCES: int(t.valeur or 0), COL_EVOL_ANNONCES: t.evolution_pct,
    } for d, t in zip(defaillances, toutes)])


def _texte_pct(v: float) -> str:
    return f"{v:+.1f} %".replace(".", ",")


def formater_pourcentages(tableau: pd.DataFrame) -> pd.DataFrame:
    """Colonnes d'évolution en texte à la française (« +12,5 % »), « — » quand il n'y a pas de comparaison."""
    colonnes = [c for c in tableau.columns if c.endswith("(%)")]
    return tableau.assign(**{c: tableau[c].map(lambda v: "—" if pd.isna(v) else _texte_pct(v)) for c in colonnes})


def barres_centre(lignes: list[LigneAnnee]) -> go.Figure:
    """Évolution des défaillances : terracotta quand elles augmentent, vert quand elles reculent."""
    connues = [l for l in lignes if l.evolution_pct is not None]
    valeurs = [l.evolution_pct for l in connues]
    fig = go.Figure(go.Bar(
        x=[l.libelle for l in connues], y=valeurs, text=[_texte_pct(v) for v in valeurs],
        textposition="outside", cliponaxis=False,
        marker=dict(color=[TERRACOTTA if v > 0 else VERT for v in valeurs], line=dict(width=0)),
        customdata=[[int(l.valeur or 0), int(l.precedent or 0)] for l in connues],
        hovertemplate="%{x} : %{text}<br>%{customdata[0]} défaillances contre %{customdata[1]} "
                      "un an plus tôt<extra></extra>",
    ))
    fig = _style(fig, 320)
    fig.add_hline(y=0, line=dict(color=ANTHRACITE, width=1))
    fig.update_xaxes(type="category")  # sinon « 2025 » est lu comme un nombre
    fig.update_yaxes(ticksuffix=" %")
    return fig


def lignes_villes(large: pd.DataFrame, cle: str, debut: date, fin: date) -> dict[str, list[LigneAnnee]]:
    """Mesure de la comparaison (défaillances, créations, radiations ou ratio), année par année et par ville."""
    resultat = {}
    for ville, g in large.groupby("ville", sort=False):
        par_mois = g.set_index("mois")
        if cle == "ratio":
            compter = compteur_ratio(compteur_mensuel(par_mois["creation"]), compteur_mensuel(par_mois["ouverture"]))
        else:
            compter = compteur_mensuel(par_mois[cle])
        resultat[ville] = evolution_annuelle(compter, debut, fin)
    return resultat


def colonne_evolution(l: LigneAnnee) -> str:
    return f"{l.annee} vs {l.annee - 1} (%)"


def tableau_villes(par_ville: dict[str, list[LigneAnnee]]) -> pd.DataFrame:
    """Une ligne par ville : la valeur de chaque année puis son évolution sur l'année précédente."""
    lignes = []
    for ville, annees in par_ville.items():
        ligne: dict[str, object] = {"Ville": ville}
        for l in annees:
            ligne[l.libelle] = l.valeur
            if l.precedent is not None:
                ligne[colonne_evolution(l)] = l.evolution_pct
        lignes.append(ligne)
    return pd.DataFrame(lignes)


def barres_villes(par_ville: dict[str, list[LigneAnnee]], couleurs: dict[str, str]) -> go.Figure:
    """Barres groupées : pour chaque année comparable, l'évolution de chaque ville."""
    fig = go.Figure()
    for ville, annees in par_ville.items():
        connues = [l for l in annees if l.evolution_pct is not None]
        fig.add_trace(go.Bar(
            x=[l.libelle for l in connues], y=[l.evolution_pct for l in connues], name=ville,
            marker=dict(color=couleurs.get(ville, ANTHRACITE), line=dict(width=0)),
            hovertemplate="%{y:+.1f} %<extra>" + ville + "</extra>",
        ))
    fig = _style(fig, 380)
    fig.add_hline(y=0, line=dict(color=ANTHRACITE, width=1))
    fig.update_layout(barmode="group", showlegend=True, hovermode="x unified")
    fig.update_xaxes(type="category")  # sinon « 2025 » est lu comme un nombre
    fig.update_yaxes(ticksuffix=" %")
    return fig
