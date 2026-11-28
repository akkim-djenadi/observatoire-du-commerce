from datetime import date

import pandas as pd
import pytest

from evolution_annuelle import (
    LigneAnnee, compteur_dates, compteur_mensuel, compteur_ratio, evolution_annuelle, taux_evolution, un_an_avant,
)


def test_annees_entieres_comparees_a_l_annee_precedente():
    dates = [date(2024, 3, 1)] * 10 + [date(2025, 6, 1)] * 12 + [date(2026, 2, 1)] * 9
    lignes = evolution_annuelle(compteur_dates(dates), date(2024, 1, 1), date(2026, 12, 31))
    assert [(l.annee, l.valeur, l.precedent, l.evolution_pct) for l in lignes] == [
        (2024, 10, None, None),   # pas de données pour 2023
        (2025, 12, 10, 20.0),
        (2026, 9, 12, -25.0),
    ]
    assert not any(l.partielle for l in lignes)


def test_annee_en_cours_comparee_a_la_meme_periode():
    # 2025 : 4 annonces avant le 28/11, 6 après ; 2026 : 5 annonces jusqu'au 28/11
    dates = [date(2025, 5, 1)] * 4 + [date(2025, 12, 15)] * 6 + [date(2026, 4, 1)] * 5
    lignes = evolution_annuelle(compteur_dates(dates), date(2025, 1, 1), date(2026, 11, 28))
    en_cours = lignes[-1]
    assert (en_cours.debut, en_cours.fin) == (date(2026, 1, 1), date(2026, 11, 28))
    assert en_cours.precedent == 4      # 01/01/2025 → 28/11/2025, et non l'année 2025 entière (10)
    assert en_cours.evolution_pct == 25.0
    assert en_cours.partielle and en_cours.libelle == "2026 (du 01/01 au 28/11)"
    assert lignes[0].libelle == "2025"


def test_debut_en_cours_d_annee_sans_donnees_precedentes():
    lignes = evolution_annuelle(compteur_dates([date(2026, 6, 1)]), date(2025, 3, 15), date(2026, 11, 28))
    assert lignes[0].libelle == "2025 (du 15/03 au 31/12)"
    assert lignes[1].precedent is None   # le 01/01/2025 est hors des données
    assert lignes[1].evolution_pct is None


def test_periode_sur_une_seule_annee():
    lignes = evolution_annuelle(compteur_dates([]), date(2026, 5, 28), date(2026, 11, 28))
    assert len(lignes) == 1 and lignes[0].evolution_pct is None


def test_periode_inversee():
    with pytest.raises(ValueError):
        evolution_annuelle(compteur_dates([]), date(2026, 2, 1), date(2026, 1, 1))


@pytest.mark.parametrize("valeur,precedent,attendu", [
    (12, 10, 20.0), (10, 12, -16.7), (5, 5, 0.0), (3, 0, None), (None, 4, None), (4, None, None),
])
def test_taux_evolution(valeur, precedent, attendu):
    assert taux_evolution(valeur, precedent) == attendu


def test_un_an_avant_29_fevrier():
    assert un_an_avant(date(2024, 2, 29)) == date(2023, 2, 28)
    assert un_an_avant(date(2026, 11, 28)) == date(2025, 11, 28)


def test_compteur_mensuel_et_annee_en_cours():
    mois = pd.period_range("2025-01", "2026-10", freq="M").to_timestamp()
    serie = pd.Series([1] * 12 + [2] * 10, index=mois)
    lignes = evolution_annuelle(compteur_mensuel(serie), date(2025, 1, 1), date(2026, 10, 31))
    assert lignes[1] == LigneAnnee(2026, date(2026, 1, 1), date(2026, 10, 31), 20.0, 10.0, 100.0)


def test_compteur_ratio():
    creations = compteur_dates([date(2025, 1, 1)] * 6)
    defaillances = compteur_dates([date(2025, 1, 1)] * 4)
    assert compteur_ratio(creations, defaillances)(date(2025, 1, 1), date(2025, 12, 31)) == 1.5
    assert compteur_ratio(creations, compteur_dates([]))(date(2025, 1, 1), date(2025, 12, 31)) is None
