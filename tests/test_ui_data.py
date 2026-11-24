from datetime import date

from bodacc import Annonce
from config import ZONE_ECUSSON, ZONE_FAUBOURGS
from entreprises import FicheEntreprise
from pipeline import Rapport, Resultat, filtrer_par_type
import classify
from ui_data import Filtres, annonces_df, appliquer_filtres, commerces_df, indicateurs, types_depuis_cles

REDRESSEMENT = "Jugement d'ouverture d'une procédure de redressement judiciaire"
CONVERSION = "Jugement de conversion en liquidation judiciaire"
CLOTURE = "Jugement de clôture pour insuffisance d'actif"


def _r(siren, jour, nature, zone=ZONE_ECUSSON, activite="Restauration traditionnelle", nom=None):
    a = Annonce(id=f"{siren}-{jour}", date_parution=jour, date_jugement=jour, nature=nature,
                nom=nom or f"SOC {siren}", enseigne="", siren=siren, forme="", activite=activite,
                adresse=f"{siren} rue de la Loge", cp="34000", complement="", url="https://bodacc.fr")
    return Resultat(annonce=a, zone=zone, distance_m=100, type_procedure=classify.type_procedure(nature),
                    secteur=classify.secteur(activite), activite=activite, adresse=a.adresse, enseigne="",
                    fiche=FicheEntreprise(siren), latitude=43.61, longitude=3.877)


def _rapport():
    rs = [
        _r("111", "2026-06-01", REDRESSEMENT),
        _r("111", "2026-08-01", CONVERSION),
        _r("222", "2026-07-01", REDRESSEMENT, zone=ZONE_FAUBOURGS, activite="Coiffure"),
        _r("333", "2026-09-01", CLOTURE, nom="BOULANGERIE DU PEYROU"),
    ]
    _, commerces = filtrer_par_type(rs, frozenset())
    return Rapport("Montpellier", date(2026, 5, 1), date(2026, 11, 30), 50, tuple(rs), (), tuple(commerces))


def test_sans_filtre_rapport_inchange():
    rap = _rapport()
    vue = appliquer_filtres(rap, Filtres())
    assert len(vue.commerces) == 3 and len(vue.retenus) == 4


def test_filtre_zone_retire_annonces_des_autres_commerces():
    vue = appliquer_filtres(_rapport(), Filtres(zones=(ZONE_FAUBOURGS,)))
    assert [c.siren for c in vue.commerces] == ["222"]
    assert {r.annonce.siren for r in vue.retenus} == {"222"}


def test_filtre_type_et_statut_combines():
    f = Filtres(types=types_depuis_cles(["redressement"]), statuts=("En redressement judiciaire",))
    vue = appliquer_filtres(_rapport(), f)
    assert [c.siren for c in vue.commerces] == ["222"]  # 111 est passé en liquidation


def test_recherche_texte_insensible_a_la_casse():
    vue = appliquer_filtres(_rapport(), Filtres(recherche="peyrou"))
    assert [c.siren for c in vue.commerces] == ["333"]


def test_filtrage_ne_modifie_pas_l_original():
    rap = _rapport()
    appliquer_filtres(rap, Filtres(zones=(ZONE_FAUBOURGS,)))
    assert len(rap.commerces) == 3


def test_indicateurs():
    ind = indicateurs(_rapport())
    assert (ind.commerces, ind.annonces, ind.a_accompagner, ind.liquidations) == (3, 4, 1, 1)
    assert round(ind.part_ecusson, 2) == 0.67


def test_indicateurs_rapport_vide():
    vide = appliquer_filtres(_rapport(), Filtres(recherche="introuvable"))
    assert indicateurs(vide).part_ecusson == 0.0
    assert commerces_df(vide).empty and annonces_df(vide).empty


def test_tableaux():
    rap = _rapport()
    df, an = commerces_df(rap), annonces_df(rap)
    assert list(df["zone"])[0] == ZONE_ECUSSON
    assert an["date_parution"].iloc[0] == "2026-09-01"  # plus récente en premier
    assert an["mois"].dt.month.tolist() == [9, 8, 7, 6]


def test_mois_incomplets():
    import pandas as pd
    from ui_charts import mois_incomplets
    assert mois_incomplets(date(2026, 5, 24), date(2026, 11, 24)) == {pd.Timestamp(2026, 5, 1), pd.Timestamp(2026, 11, 1)}
    assert mois_incomplets(date(2026, 5, 1), date(2026, 11, 30)) == set()
