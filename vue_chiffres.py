"""Onglet public « Chiffres clés » : les grands chiffres de la vitalité commerciale, intégrables par la presse.

En mode intégré (`?embed=true&graphique=indice|rues`), seul le graphique demandé est affiché.
"""
from datetime import date

import streamlit as st

import offre
import ui_vitalite as UV
import vitalite_data as VD
from config import APP_URL
from ui_brand import ENTETE
from resume_vitalite import chiffres, entier_signe
from vue_vitalite import donnees

URL_PAGE = "chiffres-cles"
GRAPHIQUES = {"indice": "L'indice de vitalité mois par mois", "rues": "Les rues les plus dynamiques et les plus fragiles"}


def _nombre(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ")


def _tuiles(c: dict) -> None:
    t = st.columns(5)
    t[0].metric("Indice", f"{c['indice']:.0f}/100",
                delta=None if c["delta"] is None else f"{c['delta']:+.0f} pts sur 12 mois",
                help=f"Indice de vitalité, niveau : {UV.niveau(c['indice'])}. Méthode : page « Vitalité des rues ».")
    t[1].metric("Défaillances", _nombre(c["defaillances"]),
                help="Sur 12 mois : ouvertures de redressement, de sauvegarde ou de liquidation (BODACC).")
    t[2].metric("Solde", entier_signe(c["solde"]),
                help=f"Solde de commerces sur 12 mois : {c['ouvertures']} ouvertures, {c['fermetures']} fermetures (Sirene).")
    t[3].metric("€/m² locaux", "—" if c["prix_m2"] is None else _nombre(c["prix_m2"]),
                help=f"Prix médian au m² de {c['ventes']} ventes de locaux commerciaux en 12 mois (DVF).")
    t[4].metric("Diversité", f"{c['diversite'] * 100:.0f} %",
                help="Diversité de l'offre. 100 % : toutes les familles d'activité à parts égales ; 0 % : une seule.")


def _graphique(nom: str, d: VD.DonneesVitalite) -> None:
    if nom == "indice":
        st.plotly_chart(UV.courbe_indice(d.historique), width="stretch")
    else:
        rues = d.indice_du_mois()
        st.plotly_chart(UV.classement_rues(rues[rues["niveau"] == "rue"]), width="stretch")


def _integration() -> None:
    with st.expander("Intégrer un graphique dans un article ou un site"):
        choix = st.selectbox("Graphique", list(GRAPHIQUES), format_func=GRAPHIQUES.get)
        st.code(f'<iframe src="{APP_URL}/{URL_PAGE}?embed=true&graphique={choix}" width="100%" height="480" '
                f'style="border:0" title="{GRAPHIQUES[choix]} – Observatoire du Commerce"></iframe>', language="html")
        st.caption("Copiez ce code dans votre page. Le graphique se met à jour tout seul chaque mois. "
                   "Merci de citer « Observatoire du Commerce » comme source.")


def page() -> None:
    d = donnees()
    demande = st.query_params.get("graphique")
    if demande in GRAPHIQUES:                       # mode intégré : le graphique seul
        if not d.historique.empty:
            st.markdown(f"**{GRAPHIQUES[demande]}** · centre-ville de Montpellier")
            _graphique(demande, d)
            st.caption(f"Source : Observatoire du Commerce, d'après Sirene, BODACC et DVF · {VD.mois_fr(d.dernier_mois)}")
        return
    st.markdown(ENTETE, unsafe_allow_html=True)
    st.title("Chiffres clés")
    if d.historique.empty:
        st.info("Les données mensuelles ne sont pas encore collectées.")
        return
    c = chiffres(d, date.today())
    st.markdown(f"La vitalité commerciale du **centre-ville de Montpellier** en {VD.mois_fr(d.dernier_mois)}, "
                f"sur {_nombre(c['stock'])} commerces actifs. Mise à jour chaque mois à partir des données publiques.")
    _tuiles(c)
    for nom, titre in GRAPHIQUES.items():
        st.markdown(f"##### {titre}")
        _graphique(nom, d)
    note = VD.derniere_note()
    if note:
        st.download_button(f"Télécharger la note de conjoncture ({VD.mois_fr(note.stem[-7:])}, PDF)",
                           note.read_bytes(), file_name=note.name, mime="application/pdf")
    _integration()
    actifs = offre.actifs_a(d.etablissements, date.today())
    st.caption("Répartition de l'offre : " + ", ".join(
        f"{f.lower()} {n}" for f, n in offre.repartition(actifs).items()) + ".")
