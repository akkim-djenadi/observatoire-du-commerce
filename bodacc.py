"""Récupération et lecture des annonces de procédures collectives du BODACC."""
import json
import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from config import BODACC_EXPORT_URL
from http_client import get_json

log = logging.getLogger(__name__)

_VILLE_RE = re.compile(r"[A-Za-zÀ-ÿ\s\-]{2,60}")


@dataclass(frozen=True)
class Annonce:
    id: str
    date_parution: str
    date_jugement: str
    nature: str
    nom: str
    enseigne: str
    siren: str
    forme: str
    activite: str
    adresse: str
    cp: str
    complement: str
    url: str


def fetch_annonces(ville: str, debut: date, fin: date) -> list[dict[str, Any]]:
    """Toutes les annonces « procédures collectives » d'une ville entre deux dates."""
    if not _VILLE_RE.fullmatch(ville):
        raise ValueError(f"Nom de ville invalide : {ville!r}")
    if debut > fin:
        raise ValueError("La date de début doit précéder la date de fin.")
    where = (
        f"familleavis='collective' AND dateparution>='{debut.isoformat()}' "
        f"AND dateparution<='{fin.isoformat()}' AND search(ville,'{ville}')"
    )
    data = get_json(BODACC_EXPORT_URL, params={"where": where})
    if not isinstance(data, list):
        raise ValueError(f"Réponse BODACC inattendue : {str(data)[:200]}")
    log.info("BODACC : %d annonces trouvées pour %s", len(data), ville)
    return data


def _load(raw: Any) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        log.warning("Champ JSON illisible ignoré : %.80s", raw)
        return {}
    return value if isinstance(value, dict) else {}


def _first(value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        return value[0] if value else {}
    return value if isinstance(value, dict) else {}


def _texte(value: Any) -> str:
    """Le BODACC donne parfois une liste (plusieurs prénoms) au lieu d'un texte."""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value if v)
    return str(value) if value else ""


def format_adresse(adr: dict[str, Any] | None) -> str:
    if not adr:
        return ""
    keys = ("numeroVoie", "typeVoie", "nomVoie", "complGeographique", "codePostal", "ville")
    return " ".join(str(adr[k]) for k in keys if adr.get(k)).strip()


def parse_annonce(raw: dict[str, Any]) -> Annonce:
    personne = _first(_load(raw.get("listepersonnes")).get("personne"))
    etab = _first(_load(raw.get("listeetablissements")).get("etablissement"))
    jugement = _load(raw.get("jugement"))
    nom = (
        _texte(personne.get("denomination"))
        or " ".join(filter(None, [_texte(personne.get("nom")), _texte(personne.get("prenom"))]))
        or _texte(raw.get("commercant"))
    )
    registre = raw.get("registre") or [""]
    return Annonce(
        id=raw.get("id", ""),
        date_parution=raw.get("dateparution", ""),
        date_jugement=jugement.get("date", ""),
        nature=jugement.get("nature", ""),
        nom=nom,
        enseigne=_texte(personne.get("nomCommercial")) or _texte(etab.get("enseigne")),
        siren=re.sub(r"\D", "", str(registre[0])),
        forme=_texte(personne.get("formeJuridique")),
        activite=_texte(personne.get("activite")) or _texte(etab.get("activite")),
        adresse=format_adresse(personne.get("adresseSiegeSocial") or personne.get("adressePP")),
        cp=raw.get("cp") or "",
        complement=jugement.get("complementJugement", ""),
        url=raw.get("url_complete", ""),
    )
