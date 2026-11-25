"""Fiche d'aide d'un commerce en difficulté, lue dans le texte du jugement BODACC.

Le BODACC publie le jugement d'ouverture sous une forme très régulière :
« … date de cessation des paiements le 15 Juillet 2026 , désignant administrateur X
avec les pouvoirs : …, mandataire judiciaire Y . Les créances sont à adresser, dans
les deux mois de la présente publication, … ». On en tire les interlocuteurs et les dates.
"""
import re
from dataclasses import dataclass
from datetime import date

from periode import mois_avant

MOIS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "décembre": 12, "decembre": 12,
}
NOMBRES = {"un": 1, "deux": 2, "trois": 3, "quatre": 4, "six": 6}

_CESSATION_RE = re.compile(r"cessation des paiements (?:le |au )?(\d{1,2})(?:er)? ([a-zéû]+) (\d{4})", re.I)
# Le rôle est suivi de son titulaire, jusqu'aux pouvoirs, au rôle suivant ou à la fin de phrase
_FIN_TITULAIRE = r"(?= avec les pouvoirs| ?, (?:mandataire judiciaire|administrateur)|\s\.(?:\s|$)|\.\s+Les créances|\s*$)"
_MANDATAIRE_RE = re.compile(r"mandataire judiciaire\s*:?\s*(.+?)" + _FIN_TITULAIRE, re.I)
_ADMINISTRATEUR_RE = re.compile(r"administrateur(?: judiciaire)?\s*:?\s*(.+?)" + _FIN_TITULAIRE, re.I)
_POUVOIRS_RE = re.compile(r"avec les pouvoirs\s*:\s*(.+?)(?= ?, mandataire judiciaire|\s\.(?:\s|$)|\s*$)", re.I)
# Délai de déclaration des créances, pris seulement dans la phrase qui l'annonce
_DECLARATION_RE = re.compile(
    r"créances (?:sont à adresser|doivent être déclarées)[^.]*?\b(dans [^,.]*?publication)", re.I
)
_DELAI_RE = re.compile(r"dans (?:le délai d'|les? )?(\w+) mois (?:de|à compter de) la présente publication", re.I)
# « Me Prénom NOM », « Maître NOM Prénom » : deux mots, plus les mots en capitales qui suivent
_PERSONNE_RE = re.compile(r"\b(?:Me|Maître)\s+[^\W\d]\S*\s+[^\W\d]\S*(?:\s+[A-ZÀ-Ÿ'’-]{2,}(?=\s))*")
_DEBUT_ADRESSE_RE = re.compile(r"\s(?=\d)")


@dataclass(frozen=True)
class Intervenant:
    nom: str
    adresse: str


@dataclass(frozen=True)
class FicheAide:
    mandataire: Intervenant | None = None
    administrateur: Intervenant | None = None
    pouvoirs_administrateur: str = ""
    date_cessation: str = ""          # AAAA-MM-JJ
    delai_creances: str = ""          # tel que publié
    date_limite_creances: str = ""    # AAAA-MM-JJ, estimation à partir de la date de parution

    @property
    def est_vide(self) -> bool:
        return self == FicheAide()


@dataclass(frozen=True)
class Contact:
    nom: str
    role: str
    ou_trouver: str


# Contacts d'aide : formulés prudemment, sans numéro (à vérifier avant tout envoi)
CONTACTS_AIDE = (
    Contact(
        "CCI Hérault",
        "Accompagnement des entreprises en difficulté : orientation, aide pour préparer "
        "les échanges avec le mandataire ou l'administrateur.",
        "Site de la CCI Hérault (herault.cci.fr) ou accueil de la CCI à Montpellier.",
    ),
    Contact(
        "Centre d'information sur la prévention des difficultés des entreprises (CIP)",
        "Entretiens gratuits et confidentiels avec d'anciens juges consulaires, un avocat "
        "et un expert-comptable, pour comprendre la procédure et ses suites.",
        "Réseau national des CIP (cip-national.fr), qui oriente vers le CIP le plus proche.",
    ),
    Contact(
        "Médiateur des entreprises",
        "Médiation gratuite et confidentielle en cas de différend avec un client, un "
        "fournisseur ou un acheteur public (retards de paiement, contrats).",
        "Saisine en ligne sur economie.gouv.fr/mediateur-des-entreprises.",
    ),
    Contact(
        "Tribunal de commerce de Montpellier — prévention",
        "Entretiens de prévention avec un juge, confidentiels, surtout utiles avant une "
        "procédure. Une fois la procédure ouverte, l'interlocuteur est le juge-commissaire, "
        "par l'intermédiaire du mandataire judiciaire.",
        "Greffe du tribunal de commerce de Montpellier (service prévention).",
    ),
)


def _espaces(texte: str) -> str:
    return re.sub(r"\s+", " ", texte).strip(" ,.")


def separer_nom_adresse(titulaire: str) -> Intervenant:
    """« SELARL X prise en la personne de Me Prénom NOM 27, rue … » → nom et adresse."""
    t = _espaces(titulaire)
    personnes = list(_PERSONNE_RE.finditer(t))
    if personnes:
        coupe = personnes[-1].end()
    else:
        debut = _DEBUT_ADRESSE_RE.search(t)
        coupe = debut.start() if debut else len(t)
    return Intervenant(nom=t[:coupe].strip(" ,"), adresse=t[coupe:].strip(" ,-"))


def lire_date_fr(jour: str, mois: str, annee: str) -> str:
    """« 04 », « Août », « 2026 » → « 2026-08-04 » (chaîne vide si la date est impossible)."""
    numero = MOIS.get(mois.lower())
    if numero is None:
        return ""
    try:
        return date(int(annee), numero, int(jour)).isoformat()
    except ValueError:
        return ""


def date_limite(date_parution: str, delai: str) -> str:
    """Date de parution + le nombre de mois du délai (« dans les deux mois … »)."""
    m = _DELAI_RE.search(delai)
    if not m or not date_parution:
        return ""
    mot = m[1].lower()
    mois = int(mot) if mot.isdigit() else NOMBRES.get(mot)
    if not mois:
        return ""
    try:
        parution = date.fromisoformat(date_parution)
    except ValueError:
        return ""
    return mois_avant(parution, -mois).isoformat()


def _intervenant(regex: re.Pattern[str], texte: str) -> Intervenant | None:
    m = regex.search(texte)
    return separer_nom_adresse(m[1]) if m else None


def extraire_fiche(complement: str, date_parution: str = "") -> FicheAide:
    """Fiche d'aide tirée du texte du jugement (champs vides si l'information manque)."""
    texte = _espaces(complement)
    cessation = _CESSATION_RE.search(texte)
    pouvoirs = _POUVOIRS_RE.search(texte)
    declaration = _DECLARATION_RE.search(texte)
    delai_txt = _espaces(declaration[1]) if declaration else ""
    return FicheAide(
        mandataire=_intervenant(_MANDATAIRE_RE, texte),
        administrateur=_intervenant(_ADMINISTRATEUR_RE, texte),
        pouvoirs_administrateur=_espaces(pouvoirs[1]) if pouvoirs else "",
        date_cessation=lire_date_fr(*cessation.groups()) if cessation else "",
        delai_creances=delai_txt,
        date_limite_creances=date_limite(date_parution, delai_txt),
    )
