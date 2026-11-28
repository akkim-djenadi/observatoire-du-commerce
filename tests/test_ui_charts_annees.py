from datetime import date

import pandas as pd

import ui_charts as C

OUVERTURE = "Redressement judiciaire (ouverture)"
CLOTURE = "Clôture pour insuffisance d'actif"


def _annonces(lignes: list[tuple[str, str]]) -> pd.DataFrame:
    df = pd.DataFrame(lignes, columns=["date_parution", "type"])
    df["mois"] = pd.to_datetime(df["date_parution"]).dt.to_period("M").dt.to_timestamp()
    return df


def test_courbes_par_annee():
    annonces = _annonces([("2024-03-05", OUVERTURE)] * 3 + [("2024-09-01", CLOTURE)]
                         + [("2026-02-10", OUVERTURE)] * 5)
    fig = C.evolution_par_annee(annonces, date(2024, 1, 1), date(2026, 11, 28))
    traces = {t.name: t for t in fig.data}
    assert list(traces["Toutes les annonces"].x) == ["2024", "2025", "2026 *"]
    assert list(traces["Toutes les annonces"].y) == [4, 0, 5]
    assert list(traces["Ouvertures (redressement, sauvegarde, liquidation directe)"].y) == [3, 0, 5]
    assert list(traces["Clôtures"].y) == [1, 0, 0]


def test_annees_incompletes():
    assert C.annees_incompletes(date(2024, 1, 1), date(2026, 11, 28)) == {2026}
    assert C.annees_incompletes(date(2024, 3, 15), date(2025, 12, 31)) == {2024}
    assert C.annees_incompletes(date(2024, 1, 1), date(2025, 12, 31)) == set()


def test_vue_par_annee_seulement_avec_une_annee_entiere():
    assert C.contient_annee_entiere(date(2025, 1, 1), date(2026, 11, 28))
    assert not C.contient_annee_entiere(date(2025, 12, 1), date(2026, 11, 28))   # « 12 derniers mois »
    assert not C.contient_annee_entiere(date(2026, 5, 28), date(2026, 11, 28))


def test_courbes_mensuelles_inchangees():
    annonces = _annonces([("2026-09-05", OUVERTURE), ("2026-11-02", OUVERTURE)])
    fig = C.evolution(annonces, date(2026, 9, 1), date(2026, 11, 28))
    assert list(fig.data[0].x) == ["sept. 2026", "oct. 2026", "nov. 2026 *"]
    assert list(fig.data[0].y) == [1, 0, 1]
