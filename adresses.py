"""Normalisation des adresses en noms de rue comparables entre sources (Sirene, DVF, BODACC)."""
import re
import unicodedata

ABREVIATIONS = {
    "R": "RUE", "BD": "BOULEVARD", "BLD": "BOULEVARD", "AV": "AVENUE", "AVE": "AVENUE", "PL": "PLACE",
    "GR": "GRAND RUE", "GRANDE": "GRAND", "IMP": "IMPASSE", "PAS": "PASSAGE", "PASS": "PASSAGE",
    "QU": "QUAI", "QUA": "QUAI", "CRS": "COURS", "ALL": "ALLEE", "CHE": "CHEMIN", "FG": "FAUBOURG",
    "FBG": "FAUBOURG", "SQ": "SQUARE", "ESP": "ESPLANADE", "RTE": "ROUTE", "PRV": "PARVIS",
}
MOTS_ABREGES = {"ST": "SAINT", "STE": "SAINTE", "GAL": "GENERAL", "MAL": "MARECHAL", "PDT": "PRESIDENT"}
CENTRES_COMMERCIAUX = {"POLYGONE": "CENTRE COMMERCIAL LE POLYGONE", "TRIANGLE": "CENTRE COMMERCIAL LE TRIANGLE"}
_NUMERO_VOIE = re.compile(r"\b\d+[A-Z]?(?:\s*-\s*\d+)?\s*(?:BIS|TER|B|T)?\s+([A-Z][A-Z' \-]+)")
_TYPES_VOIE = {"RUE", "BOULEVARD", "AVENUE", "PLACE", "GRAND", "IMPASSE", "PASSAGE", "QUAI", "COURS", "ALLEE",
               "CHEMIN", "FAUBOURG", "SQUARE", "ESPLANADE", "ROUTE", "PARVIS", "PLAN", "TRAVERSE"}


def sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn")


def _majuscules(texte: str) -> str:
    t = sans_accents(texte).upper().replace("’", "'")
    return re.sub(r"\s+", " ", re.sub(r"[,;]", " ", t)).strip()


def normaliser_voie(adresse: str) -> str:
    """« 12 GR JEAN MOULIN 34000 MONTPELLIER » → « GRAND RUE JEAN MOULIN »."""
    if not adresse:
        return ""
    a = re.sub(r"\b\d{5}\b.*$", "", _majuscules(adresse)).strip()
    for mot, nom in CENTRES_COMMERCIAUX.items():
        if mot in a.split() or f"LE {mot}" in a:
            return nom
    correspondances = list(_NUMERO_VOIE.finditer(a))
    voie = correspondances[-1].group(1) if correspondances else a
    mots = voie.split()
    if not mots:
        return ""
    mots[0] = ABREVIATIONS.get(mots[0], mots[0])
    voie = " ".join(MOTS_ABREGES.get(m, m) for m in " ".join(mots).replace("-", " ").split())
    # On coupe ce qui suit la voie quand l'adresse enchaîne un complément (« ... LOCAL 12 »)
    voie = re.split(r"\s(?:LOCAL|LOT|CELLULE|BAT|BATIMENT|RESIDENCE|APPT|ETAGE)\b", voie)[0]
    voie = re.sub(r"\s+", " ", voie.replace("-", " ")).strip(" '")
    # « GR GRAND-RUE JEAN MOULIN » (DVF) donnerait « GRAND RUE GRAND RUE JEAN MOULIN »
    return re.sub(r"^(GRAND RUE )+", "GRAND RUE ", voie + " ").strip()


def est_voie_nommee(voie: str) -> bool:
    """Vrai si la voie commence par un type connu (rue, place…) : sert à écarter les adresses inexploitables."""
    return bool(voie) and (voie.split()[0] in _TYPES_VOIE or voie.startswith("CENTRE COMMERCIAL"))


def cle_adresse(numero: str, voie: str) -> str:
    """Clé « 12|RUE DE LA LOGE » pour reconnaître un même local d'une source à l'autre."""
    n = re.match(r"\d+", (numero or "").strip())
    return f"{n.group(0) if n else ''}|{voie}"


def numero(adresse: str) -> str:
    a = re.sub(r"\b\d{5}\b.*$", "", _majuscules(adresse or ""))
    correspondances = list(re.finditer(r"\b(\d+)[A-Z]?(?:\s*-\s*\d+)?\s*(?:BIS|TER|B|T)?\s+[A-Z]", a))
    return correspondances[-1].group(1) if correspondances else ""


_MOTS_MINUSCULES = {"DE", "DU", "DES", "LA", "LE", "LES", "ET", "AU", "AUX", "EN", "SUR", "SOUS"}


def joli_nom_rue(voie: str) -> str:
    """« BOULEVARD DU JEU DE PAUME » → « Boulevard du Jeu de Paume » ; « RUE DE L'UNIVERSITE » → « Rue de l'Universite »."""
    mots = []
    for i, mot in enumerate((voie or "").split()):
        if "'" in mot:                                   # L'UNIVERSITE, D'ALGER
            avant, apres = mot.split("'", 1)
            mots.append(f"{avant.lower()}'{apres.capitalize()}" if i else f"{avant.capitalize()}'{apres.capitalize()}")
        elif i and mot in _MOTS_MINUSCULES:
            mots.append(mot.lower())
        else:
            mots.append(mot.capitalize())
    return " ".join(mots)
