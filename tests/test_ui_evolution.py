from datetime import date

import pandas as pd

import ui_evolution as U

OUVERTURE = "Jugement d'ouverture d'une procédure de redressement judiciaire"
LISTE = "Liste des créances nées après le jugement d'ouverture d'une procédure de redressement judiciaire"
CLOTURE = "Jugement de clôture pour insuffisance d'actif"


def _annonces(lignes: list[tuple[str, str]]) -> pd.DataFrame:
    return pd.DataFrame(lignes, columns=["date_parution", "nature"])


def test_defaillances_hors_listes_de_creances():
    assert U.est_defaillance(OUVERTURE)
    assert U.est_defaillance("Jugement d'ouverture de liquidation judiciaire")
    assert not U.est_defaillance(LISTE)
    assert not U.est_defaillance(CLOTURE)


def test_tableau_centre_defaillances_et_annonces():
    annonces = _annonces(
        [("2025-03-01", OUVERTURE)] * 4 + [("2025-04-01", CLOTURE)] * 2
        + [("2026-02-01", OUVERTURE)] * 5 + [("2026-02-01", LISTE)] * 3
    )
    defaillances, toutes = U.lignes_centre(annonces, date(2025, 1, 1), date(2026, 11, 28))
    t = U.tableau_centre(defaillances, toutes)
    assert list(t[U.COL_ANNEE]) == ["2025", "2026 (du 01/01 au 28/11)"]
    assert list(t[U.COL_DEFAILLANCES]) == [4, 5]
    assert t[U.COL_EVOL_DEFAILLANCES].iloc[1] == 25.0
    assert list(t[U.COL_ANNONCES]) == [6, 8]
    assert round(t[U.COL_EVOL_ANNONCES].iloc[1], 1) == 33.3
    assert pd.isna(t[U.COL_EVOL_DEFAILLANCES].iloc[0])


def test_centre_sans_annonce():
    defaillances, toutes = U.lignes_centre(pd.DataFrame(), date(2025, 1, 1), date(2026, 6, 30))
    assert [l.valeur for l in defaillances] == [0, 0]
    assert defaillances[1].evolution_pct is None   # 0 l'année précédente : taux non calculable


def _large() -> pd.DataFrame:
    mois = pd.period_range("2024-01", "2025-10", freq="M").to_timestamp()
    lignes = []
    for ville, base in (("Montpellier", 2), ("Nîmes", 1)):
        for m in mois:
            facteur = 2 if m.year == 2025 else 1
            lignes.append({"ville": ville, "mois": m, "ouverture": base * facteur, "creation": 6, "radiation": 1})
    return pd.DataFrame(lignes)


def test_lignes_villes_et_tableau():
    par_ville = U.lignes_villes(_large(), "ouverture", date(2024, 1, 1), date(2025, 10, 31))
    assert list(par_ville) == ["Montpellier", "Nîmes"]
    mtp = par_ville["Montpellier"]
    assert (mtp[1].valeur, mtp[1].precedent, mtp[1].evolution_pct) == (40, 20, 100.0)  # janv.–oct. 2025 vs 2024
    t = U.tableau_villes(par_ville)
    assert list(t.columns) == ["Ville", "2024", "2025 (du 01/01 au 31/10)", "2025 vs 2024 (%)"]
    assert list(t["2025 vs 2024 (%)"]) == [100.0, 100.0]


def test_lignes_villes_ratio():
    par_ville = U.lignes_villes(_large(), "ratio", date(2024, 1, 1), date(2025, 10, 31))
    nimes = par_ville["Nîmes"]
    assert (nimes[0].valeur, nimes[1].valeur, nimes[1].precedent) == (6.0, 3.0, 6.0)
    assert nimes[1].evolution_pct == -50.0


def test_graphiques_ignorent_les_annees_sans_comparaison():
    par_ville = U.lignes_villes(_large(), "ouverture", date(2024, 1, 1), date(2025, 10, 31))
    fig = U.barres_villes(par_ville, {"Montpellier": "#BB502E"})
    assert [list(t.x) for t in fig.data] == [["2025 (du 01/01 au 31/10)"]] * 2
    barres = U.barres_centre(par_ville["Montpellier"])
    assert list(barres.data[0].text) == ["+100,0 %"]


def test_pourcentages_a_la_francaise():
    t = pd.DataFrame({"Année": ["2024", "2025"], "Évolution (%)": [None, -22.2]})
    assert list(U.formater_pourcentages(t)["Évolution (%)"]) == ["—", "-22,2 %"]
