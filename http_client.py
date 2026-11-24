"""Appels HTTP avec reprises automatiques."""
import logging
import time
from typing import Any

import requests

from config import HTTP_RETRIES, HTTP_TIMEOUT_S, USER_AGENT

log = logging.getLogger(__name__)


class SourceIndisponible(RuntimeError):
    """Une source de données n'a pas répondu après plusieurs essais."""


def _request(method: str, url: str, **kwargs: Any) -> requests.Response:
    headers = {"User-Agent": USER_AGENT}
    last_error: Exception | None = None
    for attempt in range(1, HTTP_RETRIES + 1):
        try:
            resp = requests.request(method, url, headers=headers, timeout=HTTP_TIMEOUT_S, **kwargs)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise requests.HTTPError(f"HTTP {resp.status_code}")
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last_error = exc
            log.warning("Essai %d/%d échoué pour %s : %s", attempt, HTTP_RETRIES, url, exc)
            time.sleep(2 * attempt)
    raise SourceIndisponible(f"{url} ne répond pas : {last_error}")


def get_json(url: str, params: dict[str, str] | None = None) -> Any:
    return _request("GET", url, params=params).json()


def post_csv(url: str, csv_bytes: bytes, fields: dict[str, str]) -> str:
    files = {"data": ("adresses.csv", csv_bytes, "text/csv")}
    return _request("POST", url, data=fields, files=files).text
