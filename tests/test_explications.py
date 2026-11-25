import pandas as pd

import explications as E
from comparaison import COL_EVOLUTION


def _synth(lignes):
    colonnes = ["Ville", "Population", "Défaillances", "Créations", "Radiations", E.COL_TAUX,
                "Créations / 10 000 hab.", E.COL_RATIO, COL_EVOLUTION]
    return pd.DataFrame(lignes, columns=colonnes)


SYNTH = _synth([
    ["Montpellier", 310_240, 1970, 19611, 16538, 63.5, 632.1, 9.95, 13.4],
    ["Nîmes", 151_839, 905, 8970, 3585, 59.6, 590.8, 9.91, 6.2],
    ["Toulouse", 514_819, 3040, 26962, 11600, 59.0, 523.7, 8.87, -11.3],
])


def test_nombre_a_la_francaise():
    assert E.nombre(1970) == "1 970"
    assert E.nombre(63.54, 1) == "63,5"
    assert E.nombre(310240) == "310 240"


def test_lecture_complete_pour_la_ville_de_reference():
    phrases = E.lecture_simple(SYNTH, "Montpellier")
    assert len(phrases) == 4
    assert "63,5 entreprises sur 10 000 habitants" in phrases[0]
    assert "7 % de plus" in phrases[0]                       # 63,5 contre 59,3 de moyenne
    assert "meilleur renouvellement" in phrases[1]
    assert "augmenté de 13 %" in phrases[2]
    assert "en hausse à Nîmes" in phrases[2] and "en baisse à Toulouse" in phrases[2]
    assert "Toulouse compte 3 040 défaillances" in phrases[3]


def test_ville_proche_de_la_moyenne():
    s = _synth([["A", 100_000, 600, 6000, 100, 60.0, 600.0, 10.0, 1.0],
                ["B", 100_000, 610, 5000, 100, 61.0, 500.0, 8.2, 1.0]])
    assert "proche de la moyenne" in E.lecture_simple(s, "A")[0]
    assert "stables" in E.lecture_simple(s, "A")[2]


def test_classement_intermediaire_et_dernier():
    assert "2e sur 3" in E.lecture_simple(SYNTH, "Nîmes")[1]
    assert "le plus faible" in E.lecture_simple(SYNTH, "Toulouse")[1]


def test_plus_de_defaillances_que_de_creations():
    s = _synth([["A", 10_000, 50, 30, 10, 50.0, 30.0, 0.6, None]])
    phrases = E.lecture_simple(s, "A")
    assert "plus de défaillances que de créations" in phrases[1]
    assert len(phrases) == 2                                  # pas d'évolution, pas de comparaison de taille


def test_ville_absente_ou_sans_taux():
    assert E.lecture_simple(SYNTH, "Lyon") == []
    s = _synth([["A", 0, 0, 0, 0, None, None, None, None]])
    assert E.lecture_simple(s, "A") == []


def test_exemple_calcul():
    ex = E.exemple_calcul(SYNTH, "Montpellier")
    assert (ex.defaillances, ex.population) == (1970, 310_240)
    assert round(ex.taux, 1) == 63.5
    assert E.exemple_calcul(SYNTH, "Lyon") is None


def test_textes_fixes_non_vides():
    assert all(mot and definition for mot, definition in E.GLOSSAIRE)
    assert len(E.COMMENT_LIRE) >= 4 and len(E.PIEGES) >= 4 and len(E.FAQ) >= 3
