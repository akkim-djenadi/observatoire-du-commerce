"""Paramètres de la veille BODACC : sources, zones du centre-ville, règles de tri."""
import re

# --- Sources (toutes publiques et gratuites) ---------------------------------
BODACC_EXPORT_URL = (
    "https://bodacc-datadila.opendatasoft.com/api/explore/v2.1/"
    "catalog/datasets/annonces-commerciales/exports/json"
)
GEOCODE_CSV_URL = "https://data.geopf.fr/geocodage/search/csv"
ENTREPRISES_URL = "https://recherche-entreprises.api.gouv.fr/search"
USER_AGENT = "observatoire-commerce-veille/1.0"

HTTP_TIMEOUT_S = 60
HTTP_RETRIES = 3
ENTREPRISES_PAUSE_S = 0.16  # l'API limite à ~7 requêtes/seconde

# --- Géographie du centre-ville de Montpellier --------------------------------
COMEDIE = (43.6085, 3.8798)  # place de la Comédie (lat, lon)

# Contour approximatif de l'Écusson (intérieur des boulevards)
ECUSSON_POLYGON = (
    (43.6110, 3.8718), (43.6142, 3.8735), (43.6152, 3.8780), (43.6137, 3.8832),
    (43.6092, 3.8812), (43.6077, 3.8797), (43.6073, 3.8745), (43.6088, 3.8718),
)
HYPERCENTRE_MAX_M = 750
FAUBOURGS_MAX_M = 1300
STREET_OVERRIDE_MAX_M = 800  # une rue de l'Écusson n'est reconnue qu'à moins de 800 m
MIN_GEOCODE_SCORE = 0.5

ZONE_ECUSSON = "Écusson (cœur historique)"
ZONE_HYPERCENTRE = "Hypercentre (Comédie / Gare / Polygone-Antigone)"
ZONE_FAUBOURGS = "Faubourgs du centre"
ZONE_HORS_CENTRE = "Hors centre"
ZONE_ORDER = {ZONE_ECUSSON: 0, ZONE_HYPERCENTRE: 1, ZONE_FAUBOURGS: 2}

# Rues de l'Écusson que le contour approximatif peut manquer
ECUSSON_STREETS_RE = re.compile(
    r"[ée]tuves|jean moulin|cheval[- ]blanc|en gondeau|cheval vert|horloge|ancienne poste|"
    r"jeu de paume|ledru|\bloge\b|aiguillerie|argenterie|saint[- ]guilhem|universit|"
    r"soeurs noires|bras de fer|petit saint|delpech|croix d'or|plan d'agde|saint[- ]firmin|"
    r"\bratte\b|gagne|cannau|latreilhe|saint[- ]ravy|pila saint|coquille|[ée]coles la[ïi]ques|"
    r"lonjon|p[ée]rier|place jean jaur|rue rey\b",
    re.I,
)
# Lieux de l'hypercentre souvent mal géolocalisés (centres commerciaux…)
HYPERCENTRE_RE = re.compile(
    r"pertuisanes|polygone|triangle|jules milhau|ren[ée] devic|rue de verdun|sarrail", re.I
)

# --- Règles de tri ------------------------------------------------------------
COMMERCE_ACTIVITE_RE = re.compile(
    r"commerce de d[ée]tail|restauration|d[ée]bits? de boissons|boulangerie|coiffure|"
    r"soins de beaut|alimentation g|blanchisserie|traiteur|h[ôo]tels|entretien corporel|"
    r"r[ée]paration de chaussures|culture physique|fleurs|motocycles|agences immobili|"
    r"services personnels|salon de th|conduite|location et location-bail d'articles|"
    r"r[ée]paration d'autres biens personnels|[ée]ventaires|joaillerie|r[ée]cr[ée]atives|"
    r"plats pr[ée]par|biens d'occasion|parfumerie",
    re.I,
)
# Codes NAF « commerce », utilisés quand le BODACC ne précise pas l'activité
COMMERCE_NAF_RE = re.compile(r"^(47|56|55|96\.0[24]|95\.2|93\.13|85\.53|68\.31)")
ACTIVITE_INCONNUE = {"", "non précisé", "non précisée"}

# --- Vitalité commerciale (collecte mensuelle) ---------------------------------
CODE_COMMUNE = "34172"            # Montpellier
CODE_DEPARTEMENT = "34"
DVF_COMMUNE_URL = "https://files.data.gouv.fr/geo-dvf/latest/csv/{annee}/communes/{dep}/{commune}.csv"
DVF_DATASET_API = "https://www.data.gouv.fr/api/1/datasets/5cc1b94a634f4165e96436c1/"
DVF_ANNEES = 5                    # profondeur de l'historique des ventes de locaux
FERMETURES_MOIS = 36              # on garde les établissements fermés depuis moins de 36 mois

# Codes NAF des commerces de centre-ville (vente à distance et marchés exclus : pas de local)
NAF_COMMERCE = (
    "47.11A", "47.11B", "47.11C", "47.11D", "47.11E", "47.11F", "47.19A", "47.19B",
    "47.21Z", "47.22Z", "47.23Z", "47.24Z", "47.25Z", "47.26Z", "47.29Z", "47.30Z",
    "47.41Z", "47.42Z", "47.43Z", "47.51Z", "47.52A", "47.52B", "47.53Z", "47.54Z", "47.59A", "47.59B",
    "47.61Z", "47.62Z", "47.63Z", "47.64Z", "47.65Z",
    "47.71Z", "47.72A", "47.72B", "47.73Z", "47.74Z", "47.75Z", "47.76Z", "47.77Z", "47.78A", "47.78B",
    "47.78C", "47.79Z",
    "56.10A", "56.10B", "56.10C", "56.21Z", "56.30Z", "55.10Z",
    "96.01B", "96.02A", "96.02B", "96.04Z",
    "95.21Z", "95.22Z", "95.23Z", "95.24Z", "95.25Z", "95.29Z",
    "93.13Z", "68.31Z", "79.11Z", "85.53Z",
)
INDEPENDANT_MAX_ETABLISSEMENTS = 3   # au-delà, l'entreprise est comptée comme une chaîne
RUE_MIN_COMMERCES = 8                # en dessous, pas d'indice pour la rue (trop peu fiable)
APP_URL = "https://observatoire-du-commerce.streamlit.app"  # adresse publique, pour le code d'intégration

DOMICILIATION_RE = re.compile(
    r"bureau 3|alin[ée]a|chez mbe|\bc/o\b|\bc/z\b|6 ?b(is)? boulevard berthelot", re.I
)
COPROPRIETE_RE = re.compile(r"copropri|syndicat", re.I)
