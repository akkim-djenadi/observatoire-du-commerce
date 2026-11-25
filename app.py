"""Tableau de bord Streamlit de la veille BODACC de l'Observatoire du Commerce (cinq pages).

Lancement :  python3 -m streamlit run app.py
"""
import streamlit as st

import vue_centre
import vue_chiffres
import vue_comparaison
import vue_installer
import vue_vitalite
from ui_brand import FAVICON_PNG, LOGO_SYMBOLE_PNG

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700;800&family=Open+Sans:wght@400;600&display=swap');
body, p, li, label, input, textarea, button p, [data-testid="stMetricLabel"] p { font-family: 'Open Sans', sans-serif; }
h1, h2, h3, h4, h5, [data-testid="stMetricValue"] { font-family: 'Montserrat', sans-serif !important; letter-spacing: -0.01em; }
h1 { text-transform: uppercase; font-weight: 800 !important; color: #8A3A20; }
[data-testid="stMetric"] { background: #F6ECE4; border-left: 5px solid #BB502E; padding: 0.8rem 1rem; border-radius: 0.4rem; }
[data-testid="stMetricValue"] { color: #8A3A20; font-weight: 800; }
.ocm-marque { display: flex; align-items: center; gap: 0.7rem; margin-bottom: 0.2rem; }
.ocm-marque-nom { font-family: 'Montserrat', sans-serif; font-weight: 800; font-size: 0.78rem; line-height: 1.15;
  letter-spacing: 0.06em; text-transform: uppercase; color: #2B2B2B; }
.ocm-marque-nom span { font-weight: 600; letter-spacing: 0.2em; color: #8A3A20; }
.ocm-footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #E6D7CB; color: #6B6460; font-size: 0.85rem; line-height: 1.7; }
.ocm-footer a { color: #8A3A20; font-weight: 600; text-decoration: none; border-bottom: 1px solid #E2A24A; }
.ocm-footer a:hover, .ocm-footer a:focus-visible { color: #BB502E; border-bottom-color: #BB502E; }
</style>
"""

FOOTER = """
<footer class="ocm-footer">
  Une application développée par
  <a href="https://www.linkedin.com/in/adjenadi/" target="_blank" rel="noopener noreferrer">Akkim Djenadi</a>
  · Données issues de
  <a href="https://www.data.gouv.fr" target="_blank" rel="noopener noreferrer">data.gouv.fr</a>
  et de <a href="https://www.pappers.fr" target="_blank" rel="noopener noreferrer">pappers.fr</a>
</footer>
"""

st.set_page_config(page_title="Veille BODACC · Observatoire du Commerce",
                   page_icon=str(FAVICON_PNG) if FAVICON_PNG.exists() else "🏛️", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)
# Intégré dans un article (?embed=true&graphique=…) : ni menu ni logo, seulement le graphique demandé.
# Streamlit garde « embed » pour lui (absent de st.query_params) : on se fie au paramètre « graphique ».
INTEGRE = "graphique" in st.query_params
if LOGO_SYMBOLE_PNG.exists() and not INTEGRE:
    st.logo(str(LOGO_SYMBOLE_PNG), size="large")

navigation = st.navigation([
    # La page par défaut n'a pas d'adresse propre : les pages à intégrer ou à partager ont chacune la leur.
    st.Page(vue_centre.page, title="Commerces en difficulté", icon=":material/storefront:", default=True),
    st.Page(vue_chiffres.page, title="Chiffres clés", icon=":material/insights:", url_path=vue_chiffres.URL_PAGE),
    st.Page(vue_vitalite.page, title="Vitalité des rues", icon=":material/monitor_heart:", url_path="vitalite"),
    st.Page(vue_installer.page, title="S'installer", icon=":material/key:", url_path="s-installer"),
    st.Page(vue_comparaison.page, title="Comparer les villes", icon=":material/compare_arrows:",
            url_path="comparer"),
], position="hidden" if INTEGRE else "sidebar")
navigation.run()
st.markdown(FOOTER, unsafe_allow_html=True)
