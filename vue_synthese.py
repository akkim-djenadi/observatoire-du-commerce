"""Vue « Synthèse » de la page Commerces en difficulté : pourcentages et durée d'exploitation."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import synthese_commerces as S
from pipeline import Rapport
from ui_charts import TERRACOTTA, ZONES_COURTES, _style
from ui_data import COULEURS_STATUT, ORDRE_STATUTS, STATUTS_A_ACCOMPAGNER, STATUTS_LIQUIDATION


def _virgule(x: float | None, suffixe: str = "") -> str:
    return "—" if x is None else f"{x:.1f}".replace(".", ",") + suffixe


def barres_pourcentages(rep: pd.DataFrame, couleurs: dict[str, str] | None = None) -> go.Figure:
    """Barres horizontales « 42 % (12) », dans l'ordre du tableau (le premier en haut)."""
    d = rep.iloc[::-1]
    fig = go.Figure(go.Bar(
        x=d["pourcentage"], y=d["modalite"], orientation="h",
        text=[f"{_virgule(p, ' %')} ({n})" for p, n in zip(d["pourcentage"], d["nombre"])],
        textposition="outside", cliponaxis=False,
        marker=dict(color=[(couleurs or {}).get(m, TERRACOTTA) for m in d["modalite"]], line=dict(width=0)),
        hovertemplate="%{y} : %{x:.1f} %<extra></extra>"))
    fig = _style(fig, 70 + 36 * len(d))
    fig.update_xaxes(range=[0, max(d["pourcentage"].max() * 1.5, 10) if len(d) else 100], ticksuffix=" %")
    return fig


def barres_durees(par: pd.DataFrame, colonne: str) -> go.Figure:
    d = par.iloc[::-1]
    fig = go.Figure(go.Bar(
        x=d["moyenne"], y=d[colonne], orientation="h", cliponaxis=False, textposition="outside",
        text=[f"{_virgule(m)} ans" for m in d["moyenne"]], marker=dict(color=TERRACOTTA, line=dict(width=0)),
        customdata=d[["mediane", "nombre"]],
        hovertemplate="%{y} : moyenne %{x:.1f} ans · médiane %{customdata[0]:.1f} ans · %{customdata[1]} commerces"
                      "<extra></extra>"))
    fig = _style(fig, 70 + 36 * len(d))
    fig.update_xaxes(range=[0, max(d["moyenne"].max() * 1.4, 1) if len(d) else 10], ticksuffix=" ans")
    return fig


def _bandeau(df: pd.DataFrame, res: S.ResumeDurees) -> None:
    n = len(df)
    pct = lambda masque: f"{masque.mean() * 100:.0f} %" if n else "—"  # noqa: E731
    c = st.columns(5)
    c[0].metric("Durée moyenne", _virgule(res.moyenne, " ans"),
                help=f"Durée moyenne d'exploitation, de l'ouverture au premier jugement. Calculée sur {res.nb} commerces dont la date est connue.")
    c[1].metric("Durée médiane", _virgule(res.mediane, " ans"),
                help="La moitié des commerces avait moins que cette ancienneté au moment de la défaillance.")
    c[2].metric("Moins de 3 ans", _virgule(res.part_moins_3_ans, " %"),
                help="Part des commerces tombés en difficulté moins de 3 ans après leur ouverture.")
    c[3].metric("Encore sauvables", pct(df["statut"].isin(STATUTS_A_ACCOMPAGNER)),
                help="Redressement, sauvegarde ou plan en cours.")
    c[4].metric("En liquidation", pct(df["statut"].isin(STATUTS_LIQUIDATION)))


def afficher(rap: Rapport) -> None:
    df = S.tableau_durees(rap)
    if df.empty:
        st.info("Aucun commerce à synthétiser avec ces filtres.")
        return
    res = S.resume(df)
    df = df.assign(zone_courte=df["zone"].map(lambda z: ZONES_COURTES.get(z, z)))
    _bandeau(df, res)
    g1, g2 = st.columns(2)
    g1.markdown("##### Situation des commerces")
    g1.plotly_chart(barres_pourcentages(S.repartition(df["statut"], ORDRE_STATUTS), COULEURS_STATUT), width="stretch")
    g2.markdown("##### Ancienneté au moment de la défaillance")
    g2.plotly_chart(barres_pourcentages(S.repartition(df["tranche"], S.ordre_tranches())), width="stretch")
    g3, g4 = st.columns(2)
    g3.markdown("##### Par secteur")
    g3.plotly_chart(barres_pourcentages(S.repartition(df["secteur"])), width="stretch")
    g4.markdown("##### Par zone")
    g4.plotly_chart(barres_pourcentages(S.repartition(df["zone_courte"], list(ZONES_COURTES.values()))),
                    width="stretch")
    st.markdown("##### Durée moyenne d'exploitation avant la défaillance")
    d1, d2 = st.columns(2)
    par_secteur, par_zone = S.durees_par(df, "secteur"), S.durees_par(df, "zone_courte")
    d1.caption("Par secteur")
    d1.plotly_chart(barres_durees(par_secteur, "secteur"), width="stretch")
    d2.caption("Par zone")
    d2.plotly_chart(barres_durees(par_zone, "zone_courte"), width="stretch")
    sources = df["source_ouverture"].value_counts()
    st.caption(
        f"Durée d'exploitation : de la date d'ouverture jusqu'au premier jugement publié sur la période. "
        f"Calculée pour {res.nb} commerces sur {len(df)} : date d'ouverture de l'établissement pour "
        f"{int(sources.get('Établissement', 0))}, date de création de l'entreprise pour "
        f"{int(sources.get('Entreprise', 0))}, inconnue pour {res.sans_date}. Les pourcentages portent sur les "
        "commerces affichés (filtres compris).")
