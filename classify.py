"""Règles métier : commerce ou non, type de procédure, secteur, statut, exclusions."""
import re

from config import (
    ACTIVITE_INCONNUE, COMMERCE_ACTIVITE_RE, COMMERCE_NAF_RE, COPROPRIETE_RE, DOMICILIATION_RE,
)

CREANCES = "État / liste des créances"
AUTRE = "Autre jugement / ordonnance"
FAILLITE = "Faillite personnelle"
CLOTURE_IA = "Clôture pour insuffisance d'actif"

STATUTS = {
    CLOTURE_IA: "Liquidation clôturée (insuffisance d'actif)",
    "Clôture (extinction du passif)": "Procédure clôturée (passif payé)",
    "Liquidation judiciaire (conversion)": "En liquidation judiciaire",
    "Liquidation judiciaire (ouverture)": "En liquidation judiciaire",
    "Redressement judiciaire (ouverture)": "En redressement judiciaire",
    "Sauvegarde": "En sauvegarde",
    "Plan (redressement / cession)": "Plan adopté / modifié",
    FAILLITE: "Liquidation clôturée + faillite personnelle du dirigeant",
}
STATUT_CREANCES = "Procédure en cours (état des créances déposé)"

# Filtres par type d'annonce : mot-clé tapé par l'utilisateur → types de procédure
FILTRES_ANNONCE = {
    "redressement": {"Redressement judiciaire (ouverture)"},
    "liquidation": {"Liquidation judiciaire (ouverture)", "Liquidation judiciaire (conversion)"},
    "sauvegarde": {"Sauvegarde"},
    "plan": {"Plan (redressement / cession)"},
    "cloture": {CLOTURE_IA, "Clôture (extinction du passif)"},
    "creances": {CREANCES},
    "faillite": {FAILLITE},
    "autre": {AUTRE},
}
FILTRES_LIBELLES = {
    "redressement": "ouverture de redressement judiciaire",
    "liquidation": "liquidation judiciaire (ouverture ou conversion)",
    "sauvegarde": "procédure de sauvegarde",
    "plan": "plan de redressement ou de cession",
    "cloture": "clôture de la procédure",
    "creances": "état ou liste des créances",
    "faillite": "faillite personnelle",
    "autre": "autres jugements et ordonnances",
}


def types_pour_filtres(filtres: list[str]) -> frozenset[str]:
    """Types de procédure correspondant aux mots-clés (« redressement,liquidation »…)."""
    cles = [c.strip().lower() for f in filtres for c in f.split(",") if c.strip()]
    inconnus = [c for c in cles if c not in FILTRES_ANNONCE]
    if inconnus:
        raise ValueError(
            f"Type d'annonce inconnu : {', '.join(inconnus)}. Choix possibles : {', '.join(FILTRES_ANNONCE)}"
        )
    return frozenset(t for c in cles for t in FILTRES_ANNONCE[c])


def activite_connue(activite: str) -> bool:
    return activite.strip().lower() not in ACTIVITE_INCONNUE


def is_commerce(activite: str, naf: str = "") -> bool:
    """Commerce de centre-ville ? L'activité BODACC prime, le code NAF sert de secours."""
    if activite_connue(activite):
        return bool(COMMERCE_ACTIVITE_RE.search(activite))
    return bool(COMMERCE_NAF_RE.match(naf))


def type_procedure(nature: str) -> str:
    n = nature.lower()
    if "clôture" in n:
        return CLOTURE_IA if "insuffisance" in n else "Clôture (extinction du passif)"
    if "conversion en liquidation" in n or "résolution du plan" in n:
        return "Liquidation judiciaire (conversion)"
    if "ouverture de liquidation" in n or "extension de liquidation" in n:
        return "Liquidation judiciaire (ouverture)"
    if "redressement" in n and "ouverture" in n:
        return "Redressement judiciaire (ouverture)"
    if "sauvegarde" in n:
        return "Sauvegarde"
    if "plan" in n:
        return "Plan (redressement / cession)"
    if "créances" in n:
        return CREANCES
    if "faillite" in n:
        return FAILLITE
    return AUTRE


def secteur(activite: str) -> str:
    a = activite.lower()
    if re.search(r"restauration|d[ée]bits|h[ôo]tel|traiteur|56\.", a):
        return "Restauration / bars / hôtellerie"
    if re.search(r"boulang|alimentation|alimentaire|boissons en magasin|plats|47\.2", a):
        return "Alimentaire"
    if re.search(r"habillement|chaussure|parfumerie|textiles|[ée]ventaires|joaill", a):
        return "Équipement de la personne"
    if re.search(r"coiffure|beaut|corporel|personnels|culture physique|r[ée]paration de chaussures|96\.0", a):
        return "Beauté / services à la personne"
    if re.search(r"immobili|conduite|68\.31", a):
        return "Services (agence immo, auto-école)"
    return "Maison / loisirs / culture"


def statut(types_chronologiques: list[str]) -> str:
    """Statut d'une entreprise d'après la suite chronologique de ses annonces."""
    if FAILLITE in types_chronologiques:
        return STATUTS[FAILLITE]
    decisifs = [t for t in types_chronologiques if t not in (CREANCES, AUTRE)]
    if not decisifs:
        return STATUT_CREANCES
    return STATUTS.get(decisifs[-1], STATUT_CREANCES)


def motif_exclusion(nom: str, adresse: str) -> str:
    """Motif d'écart d'un commerce pourtant situé au centre (chaîne vide si on le garde)."""
    if COPROPRIETE_RE.search(nom):
        return "Copropriété (non commerce)"
    if DOMICILIATION_RE.search(adresse):
        return "Adresse de domiciliation (pas de local commercial identifié)"
    return ""
