"""Onglet « S'installer » : locaux disponibles et repères par rue, pour les porteurs de projet."""
from datetime import date

from adresses import joli_nom_rue
import pandas as pd
import streamlit as st

import locaux
import offre
import ui_vitalite as UV
import vitalite_data as VD
from geo import classify_zone, geocode
from http_client import SourceIndisponible, get_text
from ui_brand import ENTETE
from ui_charts import ZONES_COURTES
from vue_vitalite import donnees

CONFIRME, PROBABLE = list(UV.COULEURS_LOCAUX)
CACHE_FEUILLE_S = 3600


def _secrets() -> dict:
    try:
        return dict(st.secrets)
    except (FileNotFoundError, KeyError, st.errors.StreamlitSecretNotFoundError):
        return {}


@st.cache_data(ttl=CACHE_FEUILLE_S, show_spinner=False)
def _feuille(url: str) -> pd.DataFrame:
    """Locaux confirmés : feuille Google publiée en CSV, géolocalisée."""
    df = locaux.lire_feuille(get_text(url))
    if df.empty:
        return df
    points = geocode({str(i): a for i, a in df["adresse"].items()}, "Montpellier")
    df["latitude"] = [points[str(i)].lat if str(i) in points else None for i in df.index]
    df["longitude"] = [points[str(i)].lon if str(i) in points else None for i in df.index]
    df["zone"] = [classify_zone(points.get(str(i)), a).zone for i, a in df["adresse"].items()]
    return df


def _confirmes(url: str) -> pd.DataFrame:
    if not url:
        return pd.DataFrame()
    try:
        f = _feuille(url)
    except (SourceIndisponible, ValueError) as exc:
        st.warning(f"La feuille des locaux confirmés n'a pas pu être lue : {exc}")
        return pd.DataFrame()
    if f.empty:
        return f
    def detail(l: pd.Series) -> str:
        morceaux = [f"{l['surface_m2']:.0f} m²" if pd.notna(l["surface_m2"]) else "",
                    f"{l['loyer_mensuel']:,.0f} €/mois".replace(",", " ") if pd.notna(l["loyer_mensuel"]) else "",
                    f"contact : {l['contact']}" if l["contact"] else "", l["commentaire"] or ""]
        return " · ".join(m for m in morceaux if m)
    return pd.DataFrame({"adresse": f["adresse"], "voie": f["voie"], "zone": f["zone"], "latitude": f["latitude"],
                         "longitude": f["longitude"], "statut": CONFIRME, "detail": f.apply(detail, axis=1),
                         "famille": "", "depuis": f["disponible_depuis"]})


def _probables(d: VD.DonneesVitalite) -> pd.DataFrame:
    lib = locaux.liberes(d.etablissements, d.procedures, date.today())
    if lib.empty:
        return lib
    detail = ("Dernière activité : " + lib["derniere_activite"].fillna("").str.title() + " (" + lib["famille"].fillna("")
              + ") · libéré depuis " + lib["depuis"].astype(str) + " · " + lib["source"])
    adresses = [f"{cle.split('|')[0]} {joli_nom_rue(cle.split('|', 1)[1])}" for cle in lib["cle"]]
    return pd.DataFrame({"adresse": adresses, "voie": lib["voie"], "zone": lib["zone"],
                         "latitude": pd.to_numeric(lib["latitude"], errors="coerce"),
                         "longitude": pd.to_numeric(lib["longitude"], errors="coerce"),
                         "statut": PROBABLE, "detail": detail, "famille": lib["famille"], "depuis": lib["depuis"]})


def _reperes_rue(d: VD.DonneesVitalite) -> None:
    st.markdown("#### Repères pour choisir sa rue")
    rues = d.indice_du_mois()
    rues = rues[rues["niveau"] == "rue"].sort_values("nom")
    if rues.empty:
        return
    nom = st.selectbox("Rue", rues["nom"], format_func=joli_nom_rue)
    r = rues[rues["nom"] == nom].iloc[0]
    jour = date.today()
    actifs = offre.actifs_a(d.etablissements[d.etablissements["voie"] == nom], jour)
    zone = offre.actifs_a(d.etablissements[d.etablissements["zone"] == r["zone"]], jour)
    prix = d.dvf.loc[d.dvf["zone"] == r["zone"], "prix_m2"].dropna()
    c = st.columns(4)
    c[0].metric("Indice de la rue", f"{r['indice']:.0f}/100", help=UV.niveau(r["indice"]))
    c[1].metric("Commerces actifs", int(r["brut_stock"]))
    c[2].metric("Ouvertures / fermetures (12 mois)", f"{int(r['brut_ouvertures'])} / {int(r['brut_fermetures'])}")
    c[3].metric(f"Prix médian des locaux ({ZONES_COURTES.get(r['zone'], r['zone'])})",
                f"{prix.median():,.0f} €/m²".replace(",", " ") if len(prix) else "—")
    rares = offre.familles_rares(actifs, zone)
    st.markdown("**Ce qui manque dans la rue** : " + (", ".join(rares).lower() if rares else
                "rien de flagrant, l'offre ressemble à celle de la zone") + ".")
    st.caption("Repère indicatif : une activité absente peut correspondre à un vrai besoin… ou à une rue qui ne s'y "
               "prête pas. À croiser avec une visite et l'avis de l'Observatoire.")


def _mode_emploi_feuille() -> None:
    with st.expander("Ajouter des locaux confirmés (pour l'Observatoire)"):
        st.markdown(
            "1. Créer une feuille Google avec les colonnes : `adresse`, `surface_m2`, `loyer_mensuel`, `contact`, "
            "`disponible_depuis`, `commentaire` (modèle : `data/modele_locaux.csv`).\n"
            "2. **Fichier › Partager › Publier sur le web**, choisir la feuille et le format **CSV**, puis copier le lien.\n"
            "3. Dans Streamlit Cloud : **Settings › Secrets**, ajouter `LOCAUX_SHEET_CSV_URL = \"le lien copié\"`.\n\n"
            "Les locaux apparaissent alors en ocre sur la carte, au plus une heure après chaque modification de la feuille.")


def page() -> None:
    st.markdown(ENTETE, unsafe_allow_html=True)
    st.title("S'installer en centre-ville")
    st.markdown("Pour les porteurs de projet : les locaux disponibles ou probablement libérés, et des repères sur "
                "chaque rue (vitalité, offre existante, prix des locaux).")
    d = donnees()
    if d.historique.empty:
        st.info("Les données mensuelles ne sont pas encore collectées.")
        return
    url = VD.url_feuille_locaux(_secrets())
    tous = pd.concat([_confirmes(url), _probables(d)], ignore_index=True)
    c1, c2 = st.columns(2)
    statuts = c1.multiselect("Type de local", [CONFIRME, PROBABLE], placeholder="Tous")
    zones = c2.multiselect("Zones", sorted(tous["zone"].dropna().unique()) if not tous.empty else [],
                           format_func=lambda z: ZONES_COURTES.get(z, z), placeholder="Toutes")
    vue = tous
    if not tous.empty:
        masque = pd.Series(True, index=tous.index)
        if statuts:
            masque &= tous["statut"].isin(statuts)
        if zones:
            masque &= tous["zone"].isin(zones)
        vue = tous[masque]
    compte = vue["statut"].value_counts() if not vue.empty else pd.Series(dtype=int)
    n_conf, n_prob = int(compte.get(CONFIRME, 0)), int(compte.get(PROBABLE, 0))
    st.markdown(f"##### {n_conf} local(aux) confirmé(s) · {n_prob} local(aux) probablement libéré(s)")
    if not vue.empty:
        st.plotly_chart(UV.carte_locaux(vue), width="stretch")
        st.dataframe(vue[["statut", "adresse", "zone", "detail"]].rename(columns={
            "statut": "Type", "adresse": "Adresse", "zone": "Zone", "detail": "Informations"}).assign(
            Zone=lambda x: x["Zone"].map(lambda z: ZONES_COURTES.get(z, z))), hide_index=True, width="stretch")
    st.caption("Les locaux « probablement libérés » sont déduits automatiquement : un commerce y a fermé ou a été "
               "liquidé depuis moins de 2 ans, et aucun autre ne s'y est installé depuis. **À vérifier sur place.**")
    if not url:
        st.info("Aucune feuille de locaux confirmés n'est encore reliée : seuls les locaux déduits sont affichés.")
    _mode_emploi_feuille()
    _reperes_rue(d)
