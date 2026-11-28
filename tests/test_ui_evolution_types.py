from datetime import date

import pandas as pd

import ui_evolution_types as T

LIQ = ("Jugement d'ouverture de liquidation judiciaire", "Liquidation judiciaire (ouverture)")
RJ = ("Jugement d'ouverture d'une procédure de redressement judiciaire", "Redressement judiciaire (ouverture)")
SAUV = ("Jugement d'ouverture d'une procédure de sauvegarde", "Sauvegarde")
CONV = ("Jugement de conversion en liquidation judiciaire", "Liquidation judiciaire (conversion)")
PLAN_SAUV = ("Jugement modifiant le plan de sauvegarde", "Sauvegarde")   # pas une ouverture


def _annonces(lignes: list[tuple[str, tuple[str, str]]]) -> pd.DataFrame:
    return pd.DataFrame([(d, n, t) for d, (n, t) in lignes], columns=["date_parution", "nature", "type"])


ANNONCES = _annonces(
    [("2023-03-01", LIQ)] * 10 + [("2023-04-01", RJ)] * 4 + [("2023-12-20", LIQ)] * 5
    + [("2024-03-01", LIQ)] * 12 + [("2024-05-01", RJ)] * 6 + [("2024-06-01", CONV)] * 3
    + [("2026-02-01", LIQ)] * 15 + [("2026-02-01", RJ)] * 2 + [("2026-03-01", SAUV)]
    + [("2026-04-01", PLAN_SAUV)] * 7 + [("2026-05-01", CONV)] * 6
)


def test_courbe_de_x_a_y_sur_les_memes_jours():
    courbe = T.courbe_categories(ANNONCES, date(2023, 1, 1), date(2026, 11, 28), 2023, 2026)
    assert courbe.annees == (2023, 2024, 2025, 2026)
    assert courbe.fenetre.libelle == "du 01/01 au 28/11"   # les 5 liquidations de décembre 2023 sont exclues
    assert courbe.valeurs[T.LIQUIDATIONS] == (10, 12, 0, 15)
    assert courbe.valeurs[T.REDRESSEMENTS] == (4, 6, 0, 2)
    assert courbe.valeurs[T.SAUVEGARDES] == (0, 0, 0, 1)      # le plan de sauvegarde n'est pas compté
    assert courbe.valeurs[T.CONVERSIONS] == (0, 3, 0, 6)
    assert courbe.valeurs[T.TOUTES] == (14, 18, 0, 18)        # liquidations + redressements + sauvegardes


def test_taux_d_evolution_par_procedure():
    courbe = T.courbe_categories(ANNONCES, date(2023, 1, 1), date(2026, 11, 28), 2023, 2026)
    assert courbe.taux(T.LIQUIDATIONS, 2023, 2026) == 50.0
    assert courbe.taux(T.REDRESSEMENTS, 2023, 2026) == -50.0
    assert courbe.taux(T.SAUVEGARDES, 2023, 2026) is None     # 0 au départ : pas de pourcentage
    assert courbe.taux(T.LIQUIDATIONS, 2026, 2023) == -33.3   # dans l'autre sens


def test_graphiques_et_tableau():
    courbe = T.courbe_categories(ANNONCES, date(2023, 1, 1), date(2026, 11, 28), 2023, 2026)
    barres = T.graphique_taux(courbe, 2023, 2026).data[0]
    assert dict(zip(barres.y, barres.text)) == {
        T.TOUTES: "+28,6 %", T.LIQUIDATIONS: "+50,0 %", T.REDRESSEMENTS: "-50,0 %"}
    assert list(barres.marker.color) == ["#7A9A4E", T.TERRACOTTA, T.TERRACOTTA]   # de bas en haut
    lignes = T.graphique_courbe(courbe).data
    assert [l.name for l in lignes] == [T.TOUTES, T.LIQUIDATIONS, T.REDRESSEMENTS, T.SAUVEGARDES, T.CONVERSIONS]
    assert list(lignes[0].x) == ["2023", "2024", "2025", "2026"]
    t = T.tableau(courbe, 2023, 2026)
    assert list(t.columns) == [T.COL_CATEGORIE, "2023", "2024", "2025", "2026", T.COL_EVOLUTION]
    assert list(t.iloc[1]) == [T.LIQUIDATIONS, 10, 12, 0, 15, 50.0]


def test_courbe_sans_jours_communs_ou_sans_annonce():
    assert T.courbe_categories(ANNONCES, date(2025, 11, 1), date(2026, 2, 28), 2025, 2026) is None
    vide = T.courbe_categories(pd.DataFrame(), date(2025, 1, 1), date(2026, 6, 30), 2025, 2026)
    assert vide.valeurs[T.TOUTES] == (0, 0)
