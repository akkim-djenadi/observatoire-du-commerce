import comparaison as C

REPONSE_API = [  # ordre et contenu tels que renvoyés par geo.api.gouv.fr pour « saint d »
    {"nom": "Saint-Denis", "code": "97411", "codeDepartement": "974", "population": 155634, "codesPostaux": ["97400"]},
    {"nom": "Saint-Denis", "code": "93066", "codeDepartement": "93", "population": 149077, "codesPostaux": ["93200"]},
    {"nom": "Sainte-Dode", "code": "32366", "codeDepartement": "32", "population": 230},
    {"nom": "Saint-Dié-des-Vosges", "code": "88413", "codeDepartement": "88", "population": 19251},
    {"nom": "Saint-Jean-de-Daye", "code": "50495", "codeDepartement": "50", "population": 656},
]


def test_suggestions_commencent_par_les_lettres_tapees(monkeypatch):
    appels = []
    monkeypatch.setattr(C, "get_json", lambda url, params: appels.append(params) or REPONSE_API)
    communes = C.suggerer_communes("saint d")
    assert [(c.nom, c.departement) for c in communes] == [
        ("Saint-Denis", "974"), ("Saint-Denis", "93"), ("Saint-Dié-des-Vosges", "88")]
    assert appels[0]["nom"] == "saint d" and appels[0]["boost"] == "population"


def test_suggestions_sans_accents_ni_tirets(monkeypatch):
    monkeypatch.setattr(C, "get_json", lambda url, params: [
        {"nom": "Béziers", "code": "34032", "codeDepartement": "34", "population": 81545},
        {"nom": "Villeneuve-lès-Béziers", "code": "34336", "codeDepartement": "34", "population": 4500},
    ])
    assert [c.nom for c in C.suggerer_communes("bez")] == ["Béziers"]
    assert C.normaliser_nom("Saint-Étienne-d’Albagnan") == "saint etienne d albagnan"


def test_suggestions_vides(monkeypatch):
    monkeypatch.setattr(C, "get_json", lambda url, params: [])
    assert C.suggerer_communes("zzq") == []
    assert C.suggerer_communes("  ") == []


def test_libelle_distingue_les_homonymes():
    c = C.Commune("Montpellier", "34172", "34", 310240, ("34000",))
    assert C.libelle_commune(c) == "Montpellier (34) · 310 240 hab."
    assert C.libelle_commune(C.Commune("Ilot", "1", "2A", 0, ())) == "Ilot (2A)"
