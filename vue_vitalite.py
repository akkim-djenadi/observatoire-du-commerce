"""Page « Vitalité des rues » : indice par zone et par rue, composantes, offre, mouvements, prix des locaux."""
from datetime import date

from adresses import joli_nom_rue
import pandas as pd
import streamlit as st

import offre
import ui_vitalite as UV
import vitalite_data as VD
from indice import COMPOSANTES, LISSAGE_RUE
from periode import mois_avant
from resume_vitalite import evolution_12_mois
from ui_brand import ENTETE
from ui_charts import ZONES_COURTES

CACHE_TTL_S = 3600
NIVEAU_FILTRES = ["Dynamique", "À surveiller", "Fragile"]


@st.cache_data(ttl=CACHE_TTL_S, show_spinner=False)
def donnees() -> VD.DonneesVitalite:
    return VD.charger()


def _bandeau(d: VD.DonneesVitalite, courant: pd.DataFrame) -> None:
    lignes = courant[courant["niveau"].isin(["centre", "zone"])]
    cols = st.columns(len(lignes))
    for col, (_, l) in zip(cols, lignes.iterrows()):
        delta = evolution_12_mois(d.historique, l["nom"], d.dernier_mois)
        col.metric(ZONES_COURTES.get(l["nom"], l["nom"]), f"{l['indice']:.0f}/100",
                   delta=None if delta is None else f"{delta:+.0f} pts sur 12 mois",
                   help=f"Niveau : {UV.niveau(l['indice'])}")


def _tableau_rues(rues: pd.DataFrame):
    vue = pd.DataFrame({
        "Rue": rues["nom"].map(joli_nom_rue), "Zone": rues["zone"].map(ZONES_COURTES), "Indice": rues["indice"],
        "Niveau": rues["indice"].map(UV.niveau), "Commerces": rues["brut_stock"].astype(int),
        "Ouvertures": rues["brut_ouvertures"].astype(int), "Fermetures": rues["brut_fermetures"].astype(int),
        "Défaillances": rues["brut_nb_defaillances"].astype(int),
        "Diversité": (rues["brut_diversite"] * 100).round(), "Indépendants": (rues["brut_independants"] * 100).round(),
    })
    return st.dataframe(vue, hide_index=True, width="stretch", height=470, on_select="rerun",
                        selection_mode="single-row", key="table_rues", column_config={
                            "Indice": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f"),
                            "Diversité": st.column_config.NumberColumn(format="%.0f %%"),
                            "Indépendants": st.column_config.NumberColumn(format="%.0f %%"),
                        })


def _detail_rue(d: VD.DonneesVitalite, rue: pd.Series) -> None:
    voie = rue["nom"]
    jour = date.today()
    etab = d.etablissements[d.etablissements["voie"] == voie]
    actifs = offre.actifs_a(etab, jour)
    actifs_zone = offre.actifs_a(d.etablissements[d.etablissements["zone"] == rue["zone"]], jour)
    st.markdown(f"#### {joli_nom_rue(voie)} · {rue['indice']:.0f}/100 ({UV.niveau(rue['indice'])})")
    c1, c2 = st.columns([1.15, 1])
    c1.markdown("##### Ce qui compose l'indice")
    c1.plotly_chart(UV.barres_composantes(rue), width="stretch")
    c2.markdown("##### L'offre de la rue")
    c2.plotly_chart(UV.barres_offre(offre.repartition(actifs)), width="stretch")
    rares = offre.familles_rares(actifs, actifs_zone)
    if rares:
        c2.caption("Bien présent dans la zone mais absent de la rue : " + ", ".join(rares).lower() + ".")
    debut = mois_avant(jour, 12).isoformat()
    mouv = etab[(etab["date_creation"] >= debut) | (etab["date_fermeture"] >= debut)]
    if not mouv.empty:
        st.markdown("##### Ouvertures et fermetures des 12 derniers mois")
        st.dataframe(pd.DataFrame({
            "Commerce": mouv["enseigne"].where(mouv["enseigne"] != "", mouv["nom"]), "N°": mouv["numero"],
            "Activité": mouv["naf"].map(offre.famille),
            "Mouvement": ["Fermeture" if f else "Ouverture" for f in mouv["date_fermeture"]],
            "Date": mouv["date_fermeture"].where(mouv["date_fermeture"] != "", mouv["date_creation"]),
        }).sort_values("Date", ascending=False), hide_index=True, width="stretch")
    ventes = d.dvf[d.dvf["voie"] == voie]
    if not ventes.empty:
        prix = ventes["prix_m2"].dropna()
        st.caption(f"{len(ventes)} vente(s) de locaux commerciaux dans la rue sur 5 ans"
                   + (f", prix médian {prix.median():,.0f} €/m²".replace(",", " ") if len(prix) else "") + ".")


def _methode() -> None:
    with st.expander("Comment l'indice est calculé"):
        st.markdown("L'indice résume six mesures, chacune ramenée sur 100 par des bornes fixes, puis pondérée :")
        st.table(pd.DataFrame([{
            "Composante": c.libelle, "Poids": f"{round(c.poids * 100)} %",
            "0 point si": f"{c.zero:+.0%}" if c.unite != "indice 0-1" and c.cle != "independants" else f"{c.zero:.0%}",
            "100 points si": f"{c.cent:+.0%}" if c.unite != "indice 0-1" and c.cle != "independants" else f"{c.cent:.0%}",
        } for c in COMPOSANTES]))
        st.markdown(
            f"- **Dynamique** à partir de 60, **à surveiller** de 40 à 60, **fragile** en dessous de 40.\n"
            f"- Une rue n'a d'indice qu'à partir de 8 commerces. Pour les petites rues, les taux d'ouverture, de "
            f"défaillance et de vacance sont rapprochés de ceux de la zone (poids de {LISSAGE_RUE} commerces), pour "
            "qu'une seule fermeture ne fasse pas chuter le score.\n"
            "- Une composante sans données suffisantes (souvent le prix des locaux dans une rue) est retirée et les "
            "autres sont repondérées.\n"
            "- Les 12 premiers mois de la courbe sont **reconstitués** à partir des dates d'ouverture et de fermeture.\n"
            "- Limites : les franchises comptent comme des indépendants ; les commerces enregistrés au domicile du "
            "gérant peuvent gonfler le stock d'une rue résidentielle.")


def page() -> None:
    st.markdown(ENTETE, unsafe_allow_html=True)
    st.title("Vitalité des rues")
    d = donnees()
    if d.historique.empty:
        st.info("Les données mensuelles ne sont pas encore collectées. Lancez `python3 collecte.py` "
                "(ou le workflow « Collecte mensuelle » sur GitHub).")
        return
    st.caption(f"Indice de {VD.mois_fr(d.dernier_mois)} · données collectées le {VD.date_fr(d.collecte_le)} · sources : "
               "Sirene (INSEE), BODACC, DVF (data.gouv.fr)")
    courant = d.indice_du_mois()
    _bandeau(d, courant)
    st.markdown("##### L'indice mois par mois")
    st.plotly_chart(UV.courbe_indice(d.historique), width="stretch")
    rues = courant[courant["niveau"] == "rue"].copy()
    c1, c2, c3 = st.columns([1.3, 1.3, 1])
    zones = c1.multiselect("Zones", sorted(rues["zone"].unique()), format_func=lambda z: ZONES_COURTES.get(z, z),
                           placeholder="Toutes")
    niveaux = c2.multiselect("Niveaux", NIVEAU_FILTRES, placeholder="Tous")
    texte = c3.text_input("Rechercher une rue", placeholder="loge, jean moulin…")
    if zones:
        rues = rues[rues["zone"].isin(zones)]
    if niveaux:
        rues = rues[rues["indice"].map(UV.niveau).isin(niveaux)]
    if texte.strip():
        rues = rues[rues["nom"].str.contains(VD.sans_accents_maj(texte), regex=False)]
    rues = rues.sort_values("indice").reset_index(drop=True)
    st.markdown(f"##### {len(rues)} rues d'au moins 8 commerces")
    carte, tableau = st.columns([1, 1.25])
    carte.plotly_chart(UV.carte_rues(rues.rename(columns={"brut_stock": "stock"})), width="stretch")
    with tableau:
        evenement = _tableau_rues(rues)
    lignes = evenement.selection.rows if evenement and evenement.selection else []
    if lignes:
        _detail_rue(d, rues.iloc[lignes[0]])
    else:
        st.caption("Cliquez sur une rue du tableau pour voir le détail de son indice, de son offre et de ses mouvements.")
    _methode()
