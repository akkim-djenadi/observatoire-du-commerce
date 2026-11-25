"""Page « Centre-ville » : commerces en procédure collective, carte, tendances, fiches."""
import calendar
import io
import logging
import time
from dataclasses import replace
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

import ui_charts
import vue_synthese
from ui_brand import ENTETE
from vue_vitalite import donnees as donnees_vitalite
from classify import FILTRES_LIBELLES
from config import ZONE_ORDER
from export_excel import write_excel
from ouverture import avec_dates_ouverture
from fiche_aide import CONTACTS_AIDE, extraire_fiche
from vitalite_data import date_fr
from http_client import SourceIndisponible
from periode import mois_avant
from pipeline import Rapport, run
from ui_data import (COLONNES_COMMERCES, ORDRE_STATUTS, STATUTS_A_ACCOMPAGNER, Filtres, annonces_df, appliquer_filtres,
                     commerces_df, indicateurs, types_depuis_cles)

ICI = Path(__file__).resolve().parent
CACHE = ICI / "cache" / "entreprises.json"
PREMIERE_ANNEE_BODACC = 2008
MOIS_NOMS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
             "septembre", "octobre", "novembre", "décembre"]
LONGUE_PERIODE_MOIS = 24
CACHE_TTL_S = 6 * 3600
VUES = ["Synthèse", "Carte", "Tendances", "Commerces", "Annonces"]
COLONNES_ANNONCES = {
    "date_parution": "Parution", "date_jugement": "Jugement", "type": "Type", "nom": "Raison sociale",
    "zone": "Zone", "activite": "Activité", "adresse": "Adresse", "texte": "Texte du jugement", "url": "BODACC",
}


class EtapesHandler(logging.Handler):
    """Affiche dans l'interface les étapes de la recherche au fil de l'eau."""

    def __init__(self, zone) -> None:
        super().__init__(level=logging.INFO)
        self.zone = zone

    def emit(self, record: logging.LogRecord) -> None:
        self.zone.write(self.format(record))


@st.cache_resource
def _resultats_memorises() -> dict[tuple[str, date, date], tuple[float, Rapport]]:
    """Recherches déjà faites, partagées entre les visiteurs (6 h de validité)."""
    return {}


def charger(ville: str, debut: date, fin: date) -> Rapport:
    memo = _resultats_memorises()
    cle = (ville.strip().lower(), debut, fin)
    if cle in memo and time.time() - memo[cle][0] < CACHE_TTL_S:
        logging.getLogger("veille").info("Résultat déjà en mémoire, affiché immédiatement.")
        return memo[cle][1]
    rapport = run(ville, debut, fin, CACHE)
    memo[cle] = (time.time(), rapport)
    return rapport


def choisir_periode() -> tuple[date, date]:
    aujourd_hui = date.today()
    mode = st.radio("Période", ["Derniers mois", "De tel mois à tel mois"], horizontal=True)
    if mode == "Derniers mois":
        n = st.slider("Nombre de mois", 1, 36, 6)
        return mois_avant(aujourd_hui, n), aujourd_hui
    annees = list(range(aujourd_hui.year, PREMIERE_ANNEE_BODACC - 1, -1))
    c1, c2 = st.columns(2)
    m1 = c1.selectbox("Mois de début", range(1, 13), index=0, format_func=lambda m: MOIS_NOMS[m - 1])
    a1 = c2.selectbox("Année de début", annees, index=0)
    c3, c4 = st.columns(2)
    m2 = c3.selectbox("Mois de fin", range(1, 13), index=aujourd_hui.month - 1, format_func=lambda m: MOIS_NOMS[m - 1])
    a2 = c4.selectbox("Année de fin", annees, index=0)
    fin = date(a2, m2, calendar.monthrange(a2, m2)[1])
    return date(a1, m1, 1), min(fin, aujourd_hui)


def barre_laterale() -> tuple[str, date, date, list[str], bool]:
    with st.sidebar:
        st.markdown("### Recherche")
        ville = st.text_input("Ville", "Montpellier")
        debut, fin = choisir_periode()
        st.caption(f"Du {debut:%d/%m/%Y} au {fin:%d/%m/%Y}")
        cles = st.multiselect("Types d'annonce", list(FILTRES_LIBELLES), placeholder="Tous les types",
                              format_func=lambda c: FILTRES_LIBELLES[c].capitalize())
        lancer = st.button("Lancer la recherche", type="primary", width="stretch")
        if (fin.year - debut.year) * 12 + fin.month - debut.month > LONGUE_PERIODE_MOIS:
            st.info("Période longue : la première recherche peut prendre plusieurs minutes.")
    return ville, debut, fin, cles, lancer


def lancer_recherche(ville: str, debut: date, fin: date) -> None:
    if debut > fin:
        st.error("La période commence après sa fin.")
        return
    with st.status("Recherche en cours…", expanded=True) as status:
        handler = EtapesHandler(status)
        racine = logging.getLogger()
        racine.addHandler(handler)
        racine.setLevel(logging.INFO)
        try:
            st.session_state["rapport"] = charger(ville, debut, fin)
            status.update(label="Recherche terminée", state="complete", expanded=False)
        except (SourceIndisponible, ValueError) as exc:
            status.update(label="Recherche impossible", state="error")
            st.error(f"{exc}")
        finally:
            racine.removeHandler(handler)


def filtres_affichage(rap: Rapport, cles: list[str]) -> Filtres:
    zones = sorted({c.zone for c in rap.commerces}, key=lambda z: ZONE_ORDER.get(z, 9))
    secteurs = sorted({c.secteur for c in rap.commerces})
    statuts = [s for s in ORDRE_STATUTS if s in {c.statut for c in rap.commerces}]
    c1, c2, c3, c4 = st.columns([1.2, 1.2, 1.4, 1])
    return Filtres(
        types=types_depuis_cles(cles),
        zones=tuple(c1.multiselect("Zones", zones, placeholder="Toutes")),
        secteurs=tuple(c2.multiselect("Secteurs", secteurs, placeholder="Tous")),
        statuts=tuple(c3.multiselect("Statuts", statuts, placeholder="Tous")),
        recherche=c4.text_input("Rechercher", placeholder="nom, rue, SIREN…"),
    )


def bandeau_indicateurs(rap: Rapport) -> None:
    ind = indicateurs(rap)
    cols = st.columns(5)
    cols[0].metric("Commerces", ind.commerces)
    cols[1].metric("Annonces", ind.annonces)
    cols[2].metric("Sauvables", ind.a_accompagner, help="Redressement, sauvegarde ou plan en cours")
    cols[3].metric("Liquidation", ind.liquidations)
    cols[4].metric("Écusson", f"{ind.part_ecusson:.0%}", help="Part des commerces situés dans l'Écusson")


def onglet_commerces(df: pd.DataFrame, annonces: pd.DataFrame) -> None:
    vue = df[list(COLONNES_COMMERCES)].rename(columns=COLONNES_COMMERCES)
    for col in ("Ouverture", "Dernier jugement", "Dernière parution"):
        vue[col] = pd.to_datetime(vue[col], errors="coerce")
    event = st.dataframe(
        vue, hide_index=True, width="stretch", height=460, on_select="rerun",
        selection_mode="single-row", key="table_commerces",
        column_config={
            "BODACC": st.column_config.LinkColumn("BODACC", display_text="Voir l'annonce"),
            "Ouverture": st.column_config.DateColumn(
                format="DD/MM/YYYY", help="Date d'ouverture de l'établissement (Sirene). À défaut, date de création "
                "de l'entreprise : voir la colonne « Date de »."),
            "Date de": st.column_config.TextColumn(
                width="medium", help="« Établissement » : ouverture de la boutique ; « Entreprise » : création de "
                "la société, quand l'établissement n'a pas pu être retrouvé."),
            "Dernier jugement": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Dernière parution": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Annonces": st.column_config.NumberColumn(width="small"),
        },
    )
    lignes = event.selection.rows if event and event.selection else []
    if not lignes:
        st.caption("Cliquez sur une ligne pour afficher l'historique complet du commerce.")
        return
    c = df.iloc[lignes[0]]
    st.markdown(f"#### {c['nom']}" + (f" · {c['enseigne']}" if c["enseigne"] else ""))
    st.markdown(f"**{c['statut']}** · {c['activite']} · {c['adresse']}")
    detail = annonces[(annonces["siren"] == c["siren"]) & (annonces["nom"] == c["nom"])] if c["siren"] else \
        annonces[annonces["nom"] == c["nom"]]
    for _, a in detail.sort_values("date_parution").iterrows():
        with st.expander(f"{a['date_parution']} · {a['type']}"):
            st.write(a["nature"])
            st.write(a["texte"] or "Pas de texte complémentaire.")
            st.link_button("Ouvrir sur bodacc.fr", a["url"])
    if c["statut"] in STATUTS_A_ACCOMPAGNER:
        _fiche_aide(detail)


def _fiche_aide(annonces_commerce: pd.DataFrame) -> None:
    """Qui contacter et quelles dates retenir, pour accompagner un commerce encore sauvable."""
    fiches = [extraire_fiche(a["texte"] or "", a["date_parution"])
              for _, a in annonces_commerce.sort_values("date_parution", ascending=False).iterrows()]
    fiche = next((f for f in fiches if not f.est_vide), None)
    with st.container(border=True):
        st.markdown("##### Fiche d'aide · commerce encore sauvable")
        if fiche:
            for role, i in (("Mandataire judiciaire", fiche.mandataire), ("Administrateur judiciaire", fiche.administrateur)):
                if i:
                    st.markdown(f"- **{role}** : {i.nom}" + (f" — {i.adresse}" if i.adresse else ""))
            if fiche.date_cessation:
                st.markdown(f"- **Date de cessation des paiements** : {date_fr(fiche.date_cessation)}")
            if fiche.delai_creances:
                st.markdown(f"- **Déclaration des créances** : {fiche.delai_creances}"
                            + (f" (au plus tard vers le {date_fr(fiche.date_limite_creances)})" if fiche.date_limite_creances else ""))
        else:
            st.caption("Le texte publié ne précise pas les intervenants : voir l'annonce sur bodacc.fr.")
        st.markdown("**Où orienter le commerçant**")
        for contact in CONTACTS_AIDE:
            st.markdown(f"- **{contact.nom}** : {contact.role} *{contact.ou_trouver}*")


def page() -> None:
    ville, debut, fin, cles, lancer = barre_laterale()
    st.markdown(ENTETE, unsafe_allow_html=True)
    st.title("Commerces en difficulté au centre-ville")
    if lancer:
        lancer_recherche(ville, debut, fin)
    rap: Rapport | None = st.session_state.get("rapport")
    if rap is None:
        st.markdown("Choisissez une période dans le panneau de gauche, puis **Lancer la recherche**. "
                    "Les annonces viennent du BODACC (procédures collectives), complétées par les données "
                    "publiques des entreprises et de la Base Adresse Nationale.")
        return
    st.caption(f"{rap.ville} · parutions du {rap.debut:%d/%m/%Y} au {rap.fin:%d/%m/%Y} · "
               f"{rap.nb_annonces_ville} annonces de procédures collectives dans la ville, toutes activités")
    f = filtres_affichage(rap, cles)
    vue = avec_dates_ouverture(replace(appliquer_filtres(rap, f), filtre=", ".join(cles)),
                               donnees_vitalite().etablissements)
    bandeau_indicateurs(vue)
    df, annonces = commerces_df(vue), annonces_df(vue)
    if df.empty:
        st.warning("Aucun commerce ne correspond à ces filtres.")
        return
    # Sélecteur mémorisé : la vue reste la même quand on clique dans un tableau
    choix = st.segmented_control("Vue", VUES, default=VUES[0], key="vue", label_visibility="collapsed") or VUES[0]
    if choix == "Synthèse":
        vue_synthese.afficher(vue)
    elif choix == "Carte":
        st.plotly_chart(ui_charts.carte(df), width="stretch")
        manquants = int(df["latitude"].isna().sum())
        if manquants:
            st.caption(f"{manquants} commerce(s) sans coordonnées fiables ne figurent pas sur la carte "
                       "(voir la vue Commerces).")
    elif choix == "Tendances":
        c1, c2 = st.columns(2)
        c1.markdown("##### Par zone et statut")
        c1.plotly_chart(ui_charts.par_zone(df), width="stretch")
        c2.markdown("##### Par secteur")
        c2.plotly_chart(ui_charts.par_secteur(df), width="stretch")
        st.markdown("##### Évolution mois par mois")
        st.plotly_chart(ui_charts.evolution(annonces, rap.debut, rap.fin), width="stretch")
        if ui_charts.mois_incomplets(rap.debut, rap.fin):
            st.caption("\\* Mois couvert en partie seulement par la période : sa valeur est forcément plus basse.")
        st.caption("Pour suivre l'évolution sur plusieurs années et la comparer à d'autres villes, "
                   "ouvrez la page « Comparer les villes ».")
        st.markdown("##### Annonces publiées par mois, par type")
        st.plotly_chart(ui_charts.chronologie(annonces), width="stretch")
    elif choix == "Commerces":
        onglet_commerces(df, annonces)
    else:
        st.dataframe(annonces[list(COLONNES_ANNONCES)].rename(columns=COLONNES_ANNONCES), hide_index=True,
                     width="stretch", height=520,
                     column_config={"BODACC": st.column_config.LinkColumn("BODACC", display_text="Voir")})
    buffer = io.BytesIO()
    write_excel(vue, buffer)
    st.sidebar.download_button("Télécharger l'Excel (vue filtrée)", buffer.getvalue(),
                               file_name=f"veille_bodacc_{rap.ville}_{rap.debut}_{rap.fin}.xlsx",
                               width="stretch")
