"""Champ « Ville » : on tape les premières lettres, on choisit la commune dans la base officielle."""
import streamlit as st

import comparaison as C
from http_client import SourceIndisponible

MIN_LETTRES = 2
CACHE_TTL_S = 24 * 3600
AIDE = ("Les communes viennent de l'API officielle du découpage administratif (geo.api.gouv.fr, "
        "référencée sur data.gouv.fr).")


@st.cache_data(ttl=CACHE_TTL_S, show_spinner=False)
def _suggestions(debut_nom: str) -> list[C.Commune]:
    return C.suggerer_communes(debut_nom)


def choisir_ville(defaut: str = "Montpellier", cle: str = "ville") -> str:
    """Nom de la commune choisie ; le texte tapé tel quel si l'API ne répond pas ou ne trouve rien."""
    saisie = st.text_input("Ville", defaut, key=f"{cle}_saisie", placeholder="Tapez les premières lettres…",
                           help=AIDE).strip()
    if len(saisie) < MIN_LETTRES:
        st.caption(f"Tapez au moins {MIN_LETTRES} lettres.")
        return saisie
    try:
        communes = _suggestions(C.normaliser_nom(saisie))
    except SourceIndisponible:
        st.caption("Suggestions indisponibles pour le moment : la ville est cherchée telle que tapée.")
        return saisie
    if not communes:
        st.warning(f"Aucune commune ne commence par « {saisie} ».")
        return saisie
    choix = st.selectbox("Commune", communes, format_func=C.libelle_commune,
                         key=f"{cle}_choix_{C.normaliser_nom(saisie)}")
    return choix.nom
