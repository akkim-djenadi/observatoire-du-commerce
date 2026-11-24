"""Page « Comparer les villes » : défaillances, créations et dynamisme, sur plusieurs années."""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import comparaison as C
from ui_brand import ENTETE
from ui_charts_comparaison import COULEUR_MONTPELLIER, MAX_VILLES, PALETTE_VILLES, classement, courbes

VILLES_PROPOSEES = [
    "Montpellier", "Toulouse", "Nîmes", "Perpignan", "Béziers", "Marseille", "Nice", "Bordeaux",
    "Nantes", "Rennes", "Lille", "Strasbourg", "Lyon", "Grenoble", "Dijon", "Tours", "Angers", "Avignon",
]
VILLES_DEFAUT = ["Montpellier", "Toulouse", "Nîmes", "Bordeaux"]
PREMIERE_ANNEE = 2017
CACHE_TTL_S = 6 * 3600

MESURES = {
    "Défaillances (ouvertures de procédure)": ("ouverture", "défaillances"),
    "Créations d'entreprises": ("creation", "créations"),
    "Radiations": ("radiation", "radiations"),
    "Dynamisme : créations pour 1 défaillance": ("ratio", "créations pour 1 défaillance"),
}
LISSAGES = {"Aucun": 1, "3 mois": 3, "12 mois": 12}


@st.cache_data(ttl=CACHE_TTL_S, show_spinner=False)
def _donnees(villes: tuple[str, ...], debut: date, fin: date, perimetre: str) -> list[C.DonneesVille]:
    return C.charger_villes(villes, debut, fin, perimetre)


def _controles() -> tuple[list[str], date, date, str, str, bool, int]:
    aujourd_hui = date.today()
    c1, c2 = st.columns([2.4, 1])
    villes = c1.multiselect(
        "Villes à comparer", VILLES_PROPOSEES, default=VILLES_DEFAUT, max_selections=MAX_VILLES,
        accept_new_options=True, placeholder="Choisir ou taper une ville…",
        help=f"Jusqu'à {MAX_VILLES} villes. Tapez un nom absent de la liste puis Entrée pour l'ajouter.",
    )
    annees = list(range(PREMIERE_ANNEE, aujourd_hui.year + 1))
    a1, a2 = c2.select_slider("Années", options=annees, value=(aujourd_hui.year - 5, aujourd_hui.year))
    c3, c4, c5, c6 = st.columns([1.6, 1.3, 0.9, 1])
    mesure = c3.selectbox("Indicateur", list(MESURES))
    perimetre = c4.radio("Périmètre", [C.PERIMETRE_TOUT, C.PERIMETRE_COMMERCES], horizontal=False)
    lissage = LISSAGES[c5.radio("Lissage", list(LISSAGES), index=1)]
    par_hab = c6.toggle("Pour 10 000 habitants", value=True, disabled=MESURES[mesure][0] == "ratio",
                        help="Rend comparables des villes de tailles différentes.")
    # Le mois en cours est incomplet : on s'arrête à la fin du mois précédent
    fin = min(date(a2, 12, 31), aujourd_hui.replace(day=1) - timedelta(days=1))
    return villes, date(a1, 1, 1), fin, mesure, perimetre, par_hab, lissage


def _charger(villes: list[str], debut: date, fin: date, perimetre: str) -> tuple[pd.DataFrame, dict[str, int]]:
    with st.spinner("Récupération des annonces BODACC…"):
        donnees = _donnees(tuple(villes), debut, fin, perimetre)
    frames = [d.series.assign(ville=d.commune.nom) for d in donnees if d.commune is not None]
    populations = {d.commune.nom: d.commune.population for d in donnees if d.commune is not None}
    for d in donnees:
        if d.erreur:
            st.warning(f"{d.demande} : {d.erreur}")
    brut = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["mois", "familleavis", "n", "ville"])
    return C.completer_mois(brut, debut, fin), populations


def _couleurs(villes: list[str]) -> dict[str, str]:
    couleurs = C.attribuer_couleurs(villes, st.session_state.get("couleurs_villes", {}), PALETTE_VILLES,
                                    reservee=("Montpellier", COULEUR_MONTPELLIER))
    st.session_state["couleurs_villes"] = couleurs
    return couleurs


def page() -> None:
    st.markdown(ENTETE, unsafe_allow_html=True)
    st.title("Comparer les villes")
    st.markdown("Défaillances, créations et radiations publiées au BODACC, mois par mois. "
                "Ramenées à la population, elles permettent de comparer le **dynamisme** de villes de tailles "
                "différentes.")
    villes, debut, fin, mesure, perimetre, par_hab, lissage = _controles()
    if not villes:
        st.info("Choisissez au moins une ville.")
        return
    large, populations = _charger(villes, debut, fin, perimetre)
    if large.empty:
        st.warning("Aucune donnée pour ces villes.")
        return
    cle, unite = MESURES[mesure]
    ratio = cle == "ratio"
    unite_affichee = unite + ("" if ratio or not par_hab else " pour 10 000 hab.")
    serie = C.indicateur(large, populations, cle, par_hab and not ratio, lissage)
    couleurs = _couleurs(list(populations))
    st.caption(f"Du {debut:%m/%Y} au {fin:%m/%Y} · {perimetre} · lissage : "
               f"{'aucun' if lissage == 1 else f'moyenne sur {lissage} mois'}"
               + (" (ratio calculé sur les mois cumulés)" if ratio and lissage > 1 else ""))
    st.markdown(f"##### {mesure}" + ("" if ratio or not par_hab else " · pour 10 000 habitants"))
    st.plotly_chart(courbes(serie, couleurs, unite_affichee), width="stretch")

    synth = C.synthese(large, populations)
    g1, g2 = st.columns(2)
    g1.markdown("##### Défaillances pour 10 000 habitants")
    g1.plotly_chart(classement(synth, "Défaillances / 10 000 hab.", couleurs), width="stretch")
    g2.markdown("##### Créations pour 1 défaillance (dynamisme)")
    g2.plotly_chart(classement(synth, "Créations pour 1 défaillance", couleurs), width="stretch")

    st.markdown("##### Tableau récapitulatif de la période")
    st.dataframe(synth, hide_index=True, width="stretch", column_config={
        "Population": st.column_config.NumberColumn(format="localized"),
        C.COL_EVOLUTION: st.column_config.NumberColumn(
            format="%+.1f", help="12 derniers mois de la période comparés aux 12 mois précédents"),
    })
    st.download_button("Télécharger les séries mensuelles (CSV)",
                       large.to_csv(index=False, sep=";").encode("utf-8-sig"),
                       file_name=f"comparaison_villes_{debut:%Y-%m}_{fin:%Y-%m}.csv")
    with st.expander("Comment lire ces chiffres"):
        st.markdown(
            "- **Défaillances** : jugements d'ouverture de redressement, de sauvegarde ou de liquidation judiciaire. "
            "C'est la définition usuelle de la défaillance d'entreprise.\n"
            "- **Créations pour 1 défaillance** : au-dessus de 1, il naît plus d'entreprises qu'il n'en tombe en "
            "difficulté. Plus le chiffre est haut, plus le tissu économique se renouvelle.\n"
            "- **Pour 10 000 habitants** : population municipale INSEE la plus récente (API Découpage administratif).\n"
            "- **Périmètre « Commerces »** : estimation par mots-clés dans l'activité déclarée (restaurant, boulangerie, "
            "coiffure, vêtements…), vente en ligne exclue. À utiliser pour comparer des villes entre elles, pas comme "
            "un décompte exact.\n"
            "- Une ville est délimitée par ses codes postaux **et** son nom : Sainte-Foy-lès-Lyon n'est pas comptée "
            "dans Lyon. Les adresses en « cedex » peuvent manquer.\n"
            "- Le mois en cours, incomplet, est exclu."
        )

