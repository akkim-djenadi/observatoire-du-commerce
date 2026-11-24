"""Enrichissement par l'API Recherche d'entreprises (INSEE / RNE), avec cache local."""
import json
import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from config import ENTREPRISES_PAUSE_S, ENTREPRISES_URL
from http_client import SourceIndisponible, get_json

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FicheEntreprise:
    siren: str
    naf: str = ""
    etat: str = ""
    date_creation: str = ""
    enseignes: str = ""
    adresse: str = ""
    latitude: float | None = None
    longitude: float | None = None


def _to_fiche(siren: str, result: dict[str, Any]) -> FicheEntreprise:
    siege = result.get("siege") or {}
    enseignes = [e for e in (siege.get("liste_enseignes") or []) if e and "NON-DIFFUSIBLE" not in e]

    def coord(key: str) -> float | None:
        try:
            return float(siege[key])
        except (KeyError, TypeError, ValueError):
            return None

    return FicheEntreprise(
        siren=siren,
        naf=siege.get("activite_principale") or "",
        etat={"A": "Active", "C": "Cessée"}.get(result.get("etat_administratif", ""), ""),
        date_creation=result.get("date_creation") or "",
        enseignes=", ".join(enseignes) or (siege.get("nom_commercial") or ""),
        adresse=siege.get("adresse") or "",
        latitude=coord("latitude"),
        longitude=coord("longitude"),
    )


def fetch_fiche(siren: str) -> FicheEntreprise:
    data = get_json(ENTREPRISES_URL, params={"q": siren, "minimal": "true", "include": "siege", "per_page": "1"})
    match = [r for r in data.get("results", []) if r.get("siren") == siren]
    return _to_fiche(siren, match[0]) if match else FicheEntreprise(siren=siren)


def fetch_fiches(sirens: set[str], cache_path: Path) -> dict[str, FicheEntreprise]:
    """Fiches de chaque SIREN ; les fiches déjà connues sont relues depuis le cache."""
    cache: dict[str, dict[str, Any]] = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("Cache illisible, il sera reconstruit : %s", cache_path)
    fiches = {s: FicheEntreprise(**v) for s, v in cache.items() if s in sirens}
    manquants = sorted(s for s in sirens if s and s not in fiches)
    log.info("Entreprises : %d en cache, %d à interroger", len(fiches), len(manquants))
    for i, siren in enumerate(manquants, 1):
        try:
            fiches[siren] = fetch_fiche(siren)
        except SourceIndisponible as exc:
            log.warning("SIREN %s non enrichi : %s", siren, exc)
            continue
        if i % 50 == 0:
            log.info("  %d/%d…", i, len(manquants))
        time.sleep(ENTREPRISES_PAUSE_S)
    merged = {**cache, **{s: asdict(f) for s, f in fiches.items()}}
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(merged, ensure_ascii=False), encoding="utf-8")
    return fiches
