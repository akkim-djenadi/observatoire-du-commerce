from dataclasses import replace
from datetime import date

import pandas as pd

from ouverture import SOURCE_ENTREPRISE, SOURCE_ETABLISSEMENT, avec_dates_ouverture
from pipeline import Commerce, Rapport


def _commerce(siren, adresse, creation="1998-05-01", jugement="2026-10-01"):
    return Commerce(zone="Z", nom=f"SOC {siren}", enseigne="", siren=siren, forme="", secteur="", activite="",
                    adresse=adresse, statut="", dernier_type="", date_jugement=jugement, derniere_parution=jugement,
                    nb_annonces=1, historique="", etat_insee="", date_creation=creation, url="", distance_m=None)


def _rapport(*commerces):
    return Rapport("Montpellier", date(2026, 5, 1), date(2026, 11, 30), 0, (), (), tuple(commerces))


ETAB = pd.DataFrame([
    {"siren": "111", "voie": "RUE DE LA LOGE", "date_creation": "2019-03-01"},
    {"siren": "222", "voie": "GRAND RUE JEAN MOULIN", "date_creation": "2015-01-01"},
    {"siren": "222", "voie": "GRAND RUE JEAN MOULIN", "date_creation": "2021-06-01"},
    {"siren": "222", "voie": "GRAND RUE JEAN MOULIN", "date_creation": "2027-01-01"},   # après le jugement
    {"siren": "333", "voie": "RUE DE VERDUN", "date_creation": "2022-09-01"},
    {"siren": "444", "voie": "RUE A", "date_creation": "2010-01-01"},
    {"siren": "444", "voie": "RUE B", "date_creation": "2012-01-01"},
])


def _un(c):
    return avec_dates_ouverture(_rapport(c), ETAB).commerces[0]


def test_meme_siren_et_meme_rue():
    c = _un(_commerce("111", "20 rue de la Loge 34000 Montpellier"))
    assert (c.date_ouverture, c.source_ouverture) == ("2019-03-01", SOURCE_ETABLISSEMENT)


def test_plusieurs_etablissements_dans_la_rue_le_plus_recent_avant_jugement():
    c = _un(_commerce("222", "12 GR JEAN MOULIN 34000 MONTPELLIER"))
    assert c.date_ouverture == "2021-06-01"


def test_seul_etablissement_connu_meme_si_rue_differente():
    c = _un(_commerce("333", "1 place de la Comédie 34000 Montpellier"))
    assert (c.date_ouverture, c.source_ouverture) == ("2022-09-01", SOURCE_ETABLISSEMENT)


def test_repli_sur_la_creation_de_l_entreprise():
    ambigu = _un(_commerce("444", "1 rue C 34000 Montpellier"))       # deux établissements, aucune rue ne correspond
    inconnu = _un(_commerce("999", "1 rue D 34000 Montpellier"))
    for c in (ambigu, inconnu):
        assert (c.date_ouverture, c.source_ouverture) == ("1998-05-01", SOURCE_ENTREPRISE)


def test_sans_aucune_date():
    c = _un(replace(_commerce("", "1 rue D 34000"), date_creation=""))
    assert (c.date_ouverture, c.source_ouverture) == ("", "")


def test_sans_donnees_sirene_le_rapport_reste_utilisable():
    c = avec_dates_ouverture(_rapport(_commerce("111", "20 rue de la Loge")), pd.DataFrame()).commerces[0]
    assert c.source_ouverture == SOURCE_ENTREPRISE
