from datetime import date

import pandas as pd
import pytest

import synthese_commerces as S
from bodacc import Annonce
from entreprises import FicheEntreprise
from pipeline import Commerce, Rapport, Resultat


def _annonce(siren, jugement):
    return Annonce(id=f"{siren}{jugement}", date_parution=jugement, date_jugement=jugement, nature="", nom=f"S{siren}",
                   enseigne="", siren=siren, forme="", activite="", adresse="", cp="", complement="", url="")


def _resultat(siren, jugement):
    return Resultat(annonce=_annonce(siren, jugement), zone="Z", distance_m=0, type_procedure="", secteur="",
                    activite="", adresse="", enseigne="", fiche=FicheEntreprise(siren))


def _commerce(siren, ouverture, statut="En liquidation judiciaire", secteur="Restauration", zone="Écusson",
              dernier="2026-10-01"):
    return Commerce(zone=zone, nom=f"S{siren}", enseigne="", siren=siren, forme="", secteur=secteur, activite="",
                    adresse="", statut=statut, dernier_type="", date_jugement=dernier, derniere_parution=dernier,
                    nb_annonces=1, historique="", etat_insee="", date_creation="", url="", distance_m=None,
                    date_ouverture=ouverture, source_ouverture="Établissement" if ouverture else "")


def _rapport():
    commerces = (_commerce("1", "2025-10-01"), _commerce("2", "2016-06-01", statut="En redressement judiciaire"),
                 _commerce("3", "2022-06-01", secteur="Beauté", zone="Faubourgs"), _commerce("4", ""))
    retenus = (_resultat("1", "2026-04-01"), _resultat("1", "2026-09-01"),   # premier jugement : avril
               _resultat("2", "2026-06-01"), _resultat("3", "2026-06-01"), _resultat("4", "2026-07-01"))
    return Rapport("Montpellier", date(2026, 5, 1), date(2026, 11, 30), 0, retenus, (), commerces)


def test_duree_annees():
    assert S.duree_annees("2020-01-01", "2026-01-01") == pytest.approx(6.0, abs=0.01)
    assert S.duree_annees("", "2026-01-01") is None
    assert S.duree_annees("2027-01-01", "2026-01-01") is None        # ouverture après le jugement : incohérent


@pytest.mark.parametrize("duree,libelle", [(0.5, "Moins d'1 an"), (1, "1 à 3 ans"), (4.9, "3 à 5 ans"),
                                           (5, "5 à 10 ans"), (25, "Plus de 10 ans"), (None, None)])
def test_tranche(duree, libelle):
    assert S.tranche(duree) == libelle


def test_duree_jusqu_au_premier_jugement():
    df = S.tableau_durees(_rapport()).set_index("nom")
    assert df.loc["S1", "premier_jugement"] == "2026-04-01"
    assert df.loc["S1", "duree_ans"] == pytest.approx(0.5, abs=0.01)
    assert df.loc["S2", "tranche"] == "Plus de 10 ans"
    assert pd.isna(df.loc["S4", "duree_ans"])


def test_repartition_en_pourcentage():
    df = S.tableau_durees(_rapport())
    r = S.repartition(df["statut"]).set_index("modalite")
    assert r.loc["En liquidation judiciaire", "nombre"] == 3
    assert r.loc["En liquidation judiciaire", "pourcentage"] == 75.0
    assert r["pourcentage"].sum() == pytest.approx(100)
    tranches = S.repartition(df["tranche"], S.ordre_tranches())
    assert list(tranches["modalite"]) == ["Moins d'1 an", "3 à 5 ans", "Plus de 10 ans"]   # ordre logique, vides exclus


def test_durees_par_secteur_et_resume():
    df = S.tableau_durees(_rapport())
    par = S.durees_par(df, "secteur").set_index("secteur")
    assert par.loc["Restauration", "nombre"] == 2
    assert par.loc["Restauration", "moyenne"] == pytest.approx((0.5 + 10) / 2, abs=0.1)
    res = S.resume(df)
    assert (res.nb, res.sans_date) == (3, 1)
    assert res.part_moins_3_ans == pytest.approx(33.3, abs=0.1)
    assert res.mediane == pytest.approx(4.0, abs=0.1)


def test_resume_sans_aucune_date():
    vide = S.tableau_durees(Rapport("M", date(2026, 1, 1), date(2026, 2, 1), 0, (), (), (_commerce("9", ""),)))
    assert S.resume(vide).moyenne is None and S.durees_par(vide, "zone").empty
