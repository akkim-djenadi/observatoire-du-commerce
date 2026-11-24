from datetime import date

import pandas as pd
import pytest

import comparaison as C

MTP = C.Commune("Montpellier", "34172", "34", 300_000, ("34000", "34070"))


def _brut(lignes):
    return pd.DataFrame(lignes, columns=["mois", "familleavis", "n", "ville"])


def test_clause_commune_codes_postaux_et_nom():
    clause = C.clause_commune(MTP)
    assert "cp like '34000*' OR cp like '34070*'" in clause
    assert 'search(ville, "Montpellier")' in clause


def test_clause_commune_nom_avec_apostrophe():
    c = C.Commune("Villeneuve-d'Ascq", "59009", "59", 62_000, ("59491",))
    assert "search(ville, \"Villeneuve-d'Ascq\")" in C.clause_commune(c)


def test_clause_commune_sans_code_postal_refusee():
    with pytest.raises(ValueError):
        C.clause_commune(C.Commune("X", "0", "0", 1, ()))


def test_clause_commerces_exclut_vente_en_ligne():
    clause = C.clause_commerces()
    assert 'search(listeetablissements, "boulangerie")' in clause
    assert 'NOT (search(listeetablissements, "internet")' in clause


def test_completer_mois_ajoute_les_mois_vides():
    brut = _brut([("2026-01", "ouverture", 4, "Montpellier"), ("2026-03", "creation", 10, "Montpellier")])
    large = C.completer_mois(brut, date(2026, 1, 1), date(2026, 3, 31))
    assert len(large) == 3
    assert large["ouverture"].tolist() == [4, 0, 0]
    assert large["creation"].tolist() == [0, 0, 10]
    assert large["radiation"].sum() == 0


def test_completer_mois_vide():
    assert C.completer_mois(_brut([]), date(2026, 1, 1), date(2026, 2, 28)).empty


def _large():
    lignes = []
    for i, m in enumerate(["2026-01", "2026-02", "2026-03"]):
        lignes += [(m, "ouverture", [2, 4, 6][i], "Montpellier"), (m, "creation", [10, 20, 30][i], "Montpellier")]
    return C.completer_mois(_brut(lignes), date(2026, 1, 1), date(2026, 3, 31))


def test_indicateur_pour_10000_habitants():
    s = C.indicateur(_large(), {"Montpellier": 20_000}, "ouverture", True, 1)
    assert s["valeur"].tolist() == [1.0, 2.0, 3.0]


def test_indicateur_lissage_moyenne_mobile():
    s = C.indicateur(_large(), {"Montpellier": 20_000}, "ouverture", False, 3)
    assert s["valeur"].tolist() == [2.0, 3.0, 4.0]


def test_ratio_sur_mois_cumules():
    s = C.indicateur(_large(), {}, "ratio", False, 3)
    assert s["valeur"].iloc[-1] == 5.0  # 60 créations / 12 défaillances


def test_ratio_sans_defaillance_vaut_vide():
    brut = _brut([("2026-01", "creation", 10, "Montpellier")])
    large = C.completer_mois(brut, date(2026, 1, 1), date(2026, 1, 31))
    assert C.indicateur(large, {}, "ratio", False, 1)["valeur"].isna().all()


def test_synthese_evolution_sur_12_mois():
    mois = pd.period_range("2024-01", "2025-12", freq="M").strftime("%Y-%m")
    lignes = [(m, "ouverture", 1 if i < 12 else 2, "Montpellier") for i, m in enumerate(mois)]
    large = C.completer_mois(_brut(lignes), date(2024, 1, 1), date(2025, 12, 31))
    ligne = C.synthese(large, {"Montpellier": 10_000}).iloc[0]
    assert ligne["Défaillances"] == 36
    assert ligne["Défaillances / 10 000 hab."] == 36.0
    assert ligne[C.COL_EVOLUTION] == 100.0


def test_synthese_evolution_absente_si_moins_de_24_mois():
    ligne = C.synthese(_large(), {"Montpellier": 10_000}).iloc[0]
    assert pd.isna(ligne[C.COL_EVOLUTION])


def test_couleurs_stables_quand_on_retire_une_ville():
    palette = ("#a", "#b", "#c")
    c1 = C.attribuer_couleurs(["Montpellier", "Toulouse", "Nîmes"], {}, palette, ("Montpellier", "#m"))
    c2 = C.attribuer_couleurs(["Montpellier", "Nîmes"], c1, palette, ("Montpellier", "#m"))
    assert c1["Montpellier"] == "#m" and c2["Nîmes"] == c1["Nîmes"]


def test_couleurs_nouvelle_ville_prend_une_couleur_libre():
    palette = ("#a", "#b")
    c = C.attribuer_couleurs(["Toulouse", "Lyon"], {"Toulouse": "#a"}, palette)
    assert c["Lyon"] == "#b"


def test_charger_villes_isole_les_erreurs(monkeypatch):
    def faux_chercher(nom):
        if nom == "Inconnue":
            raise ValueError("Commune introuvable : Inconnue")
        return MTP

    monkeypatch.setattr(C, "chercher_commune", faux_chercher)
    monkeypatch.setattr(C, "series_commune", lambda c, d, f, p: _brut([("2026-01", "ouverture", 1, c.nom)]))
    res = C.charger_villes(("Montpellier", "Inconnue"), date(2026, 1, 1), date(2026, 1, 31))
    assert [r.demande for r in res] == ["Montpellier", "Inconnue"]
    assert res[0].series is not None and res[1].erreur.startswith("Commune introuvable")
