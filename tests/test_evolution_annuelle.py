from datetime import date

import pandas as pd
import pytest

from evolution_annuelle import (
    LigneAnnee, comparer_annees, compteur_dates, compteur_mensuel, compteur_ratio, evolution_annuelle, taux_evolution,
    un_an_avant,
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


def test_comparer_deux_annees_non_consecutives():
    dates = [date(2022, 3, 1)] * 8 + [date(2024, 3, 1)] * 10 + [date(2026, 2, 1)] * 12
    c = comparer_annees(compteur_dates(dates), date(2022, 1, 1), date(2026, 12, 31), 2022, 2026)
    assert (c.valeur_depart, c.valeur_arrivee, c.evolution_pct) == (8, 12, 50.0)
    assert c.annee_entiere and c.fenetre == "année entière"


def test_comparer_annee_en_cours_sur_les_memes_jours_dans_les_deux_sens():
    # 2024 : 4 annonces avant le 28/11, 6 après ; 2026 (en cours) : 5 annonces
    dates = [date(2024, 5, 1)] * 4 + [date(2024, 12, 15)] * 6 + [date(2026, 4, 1)] * 5
    compter = compteur_dates(dates)
    c = comparer_annees(compter, date(2024, 1, 1), date(2026, 11, 28), 2024, 2026)
    assert (c.debut, c.fin) == (date(2026, 1, 1), date(2026, 11, 28))
    assert (c.valeur_depart, c.valeur_arrivee, c.evolution_pct) == (4, 5, 25.0)
    assert c.fenetre == "du 01/01 au 28/11"
    inverse = comparer_annees(compter, date(2024, 1, 1), date(2026, 11, 28), 2026, 2024)
    assert (inverse.valeur_depart, inverse.valeur_arrivee, inverse.evolution_pct) == (5, 4, -20.0)
    assert (inverse.debut, inverse.fin) == (date(2024, 1, 1), date(2024, 11, 28))


def test_comparer_debut_en_cours_d_annee():
    dates = [date(2025, 2, 1)] * 3 + [date(2025, 6, 1)] * 4 + [date(2026, 6, 1)] * 2
    c = comparer_annees(compteur_dates(dates), date(2025, 3, 15), date(2026, 11, 28), 2025, 2026)
    assert c.fenetre == "du 15/03 au 28/11"
    assert (c.valeur_depart, c.valeur_arrivee) == (4, 2)   # février 2025 hors des données


def test_comparer_sans_jours_communs_ou_hors_periode():
    compter = compteur_dates([])
    assert comparer_annees(compter, date(2025, 11, 1), date(2026, 2, 28), 2025, 2026) is None
    with pytest.raises(ValueError):
        comparer_annees(compter, date(2025, 1, 1), date(2026, 2, 28), 2023, 2026)
