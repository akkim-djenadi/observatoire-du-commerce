"""Appels HTTP avec reprises automatiques."""
import logging
import time
from typing import Any

import requests

from config import HTTP_RETRIES, HTTP_TIMEOUT_S, USER_AGENT

log = logging.getLogger(__name__)
ESSAIS_MAX_429 = 8          # un refus pour excès de débit se règle en patientant : on insiste davantage
ATTENTE_MAX_429_S = 60.0


class SourceIndisponible(RuntimeError):
    """Une source de données n'a pas répondu après plusieurs essais."""


class RessourceIntrouvable(SourceIndisponible):
    """La ressource demandée n'existe pas (HTTP 404) : inutile de réessayer."""


def attente_429(resp: requests.Response, essai: int) -> float:
    """Pause après un refus pour excès de débit : l'en-tête Retry-After s'il existe, sinon 2, 4, 8… s (max 60)."""
    try:
        demande = float(resp.headers.get("Retry-After", ""))
    except ValueError:
        demande = 0.0
    return min(max(demande, 2.0 ** essai), ATTENTE_MAX_429_S)


def _request(method: str, url: str, **kwargs: Any) -> requests.Response:
    """Requête avec reprises : 3 essais en cas d'erreur, jusqu'à 8 si l'API limite le débit (HTTP 429)."""
    headers = {"User-Agent": USER_AGENT}
    last_error: Exception | None = None
    erreurs = 0
    for essai in range(1, ESSAIS_MAX_429 + 1):
        try:
            resp = requests.request(method, url, headers=headers, timeout=HTTP_TIMEOUT_S, **kwargs)
        except requests.RequestException as exc:
            resp, last_error = None, exc
        if resp is not None:
            if resp.status_code == 404:
                raise RessourceIntrouvable(f"{url} : ressource introuvable (404)")
            if resp.status_code == 429:
                last_error = requests.HTTPError("HTTP 429")
                pause = attente_429(resp, essai)
                log.warning("Débit limité par %s (essai %d), nouvel essai dans %.0f s", url, essai, pause)
                time.sleep(pause)
                continue
            if resp.status_code < 500:
                resp.raise_for_status()
                return resp
            last_error = requests.HTTPError(f"HTTP {resp.status_code}")
        erreurs += 1
        log.warning("Essai %d/%d échoué pour %s : %s", erreurs, HTTP_RETRIES, url, last_error)
        if erreurs >= HTTP_RETRIES:
            break
        time.sleep(2 * erreurs)
    raise SourceIndisponible(f"{url} ne répond pas : {last_error}")


def get_json(url: str, params: dict[str, str] | None = None) -> Any:
    return _request("GET", url, params=params).json()


def get_text(url: str, encodage: str = "utf-8") -> str:
    """Texte de la réponse, décodé explicitement (les serveurs omettent souvent le jeu de caractères)."""
    return _request("GET", url).content.decode(encodage)


def ouvrir_flux(url: str) -> requests.Response:
    """Réponse en flux, pour lire un gros fichier sans le charger en mémoire (à fermer par l'appelant)."""
    return _request("GET", url, stream=True)


def post_csv(url: str, csv_bytes: bytes, fields: dict[str, str]) -> str:
    files = {"data": ("adresses.csv", csv_bytes, "text/csv")}
    return _request("POST", url, data=fields, files=files).text
