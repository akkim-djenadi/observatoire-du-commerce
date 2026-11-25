from datetime import date

import pytest
import requests

import etablissements as E
import http_client as H


class _Reponse:
    def __init__(self, statut, entetes=None):
        self.status_code = statut
        self.headers = entetes or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return {"ok": True}


@pytest.fixture
def sans_attente(monkeypatch):
    pauses = []
    monkeypatch.setattr(H.time, "sleep", pauses.append)
    return pauses


def test_attente_429_respecte_retry_after_et_double_sinon():
    assert H.attente_429(_Reponse(429, {"Retry-After": "12"}), 1) == 12
    assert H.attente_429(_Reponse(429), 1) == 2 and H.attente_429(_Reponse(429), 3) == 8
    assert H.attente_429(_Reponse(429), 10) == H.ATTENTE_MAX_429_S
    assert H.attente_429(_Reponse(429, {"Retry-After": "demain"}), 2) == 4


def test_reprise_apres_plusieurs_refus_429(monkeypatch, sans_attente):
    reponses = iter([_Reponse(429)] * 5 + [_Reponse(200)])
    monkeypatch.setattr(H.requests, "request", lambda *a, **k: next(reponses))
    assert H.get_json("https://exemple") == {"ok": True}
    assert sans_attente == [2, 4, 8, 16, 32]              # 5 refus patientés, puis succès


def test_abandon_apres_trop_de_refus_429(monkeypatch, sans_attente):
    monkeypatch.setattr(H.requests, "request", lambda *a, **k: _Reponse(429))
    with pytest.raises(H.SourceIndisponible):
        H.get_json("https://exemple")
    assert len(sans_attente) == H.ESSAIS_MAX_429


def test_erreur_serveur_limitee_a_trois_essais(monkeypatch, sans_attente):
    appels = []
    monkeypatch.setattr(H.requests, "request", lambda *a, **k: appels.append(1) or _Reponse(503))
    with pytest.raises(H.SourceIndisponible):
        H.get_json("https://exemple")
    assert len(appels) == H.HTTP_RETRIES


def test_404_sans_nouvel_essai(monkeypatch, sans_attente):
    monkeypatch.setattr(H.requests, "request", lambda *a, **k: _Reponse(404))
    with pytest.raises(H.RessourceIntrouvable):
        H.get_json("https://exemple")
    assert sans_attente == []


def test_cadence_espace_les_creneaux_entre_fils():
    cadence = E.Cadence(5.0)
    attentes = [cadence.reserver() for _ in range(5)]
    assert attentes[0] == pytest.approx(0, abs=0.01)
    assert attentes[4] == pytest.approx(0.8, abs=0.02)     # 5 requêtes réservées d'un coup : la 5e attend 0,8 s


def test_collecte_incomplete_si_un_code_echoue(monkeypatch):
    def pages(commune, naf, cadence):
        if naf == "47.71Z":
            raise H.SourceIndisponible("HTTP 429")
        return iter([])
    monkeypatch.setattr(E, "_pages", pages)
    with pytest.raises(E.CollecteIncomplete, match="47.71Z"):
        E.collecter("34172", ["56.10C", "47.71Z"], date(2023, 1, 1))
