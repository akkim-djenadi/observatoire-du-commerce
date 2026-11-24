import json
from datetime import date

import pytest

import classify
from bodacc import fetch_annonces, parse_annonce
from config import COMEDIE, ZONE_ECUSSON, ZONE_FAUBOURGS, ZONE_HORS_CENTRE, ZONE_HYPERCENTRE
from geo import Point, classify_zone, distance_m
from main import nom_fichier, parse_args
from periode import lire_date, mois_avant


# --- classify -----------------------------------------------------------------
@pytest.mark.parametrize("activite,naf,attendu", [
    ("Restauration de type rapide", "", True),
    ("Commerce de détail d'habillement en magasin spécialisé", "", True),
    ("Programmation informatique", "47.11B", False),  # l'activité BODACC prime
    ("Non précisé", "56.30Z", True),                  # NAF de secours : bar
    ("", "68.20B", False),                            # SCI
])
def test_is_commerce(activite, naf, attendu):
    assert classify.is_commerce(activite, naf) is attendu


@pytest.mark.parametrize("nature,attendu", [
    ("Jugement d'ouverture d'une procédure de redressement judiciaire", "Redressement judiciaire (ouverture)"),
    ("Jugement de conversion en liquidation judiciaire", "Liquidation judiciaire (conversion)"),
    ("Jugement d'ouverture de liquidation judiciaire", "Liquidation judiciaire (ouverture)"),
    ("Jugement de clôture pour insuffisance d'actif", classify.CLOTURE_IA),
    ("Jugement prononçant la résolution du plan de redressement et la liquidation judiciaire",
     "Liquidation judiciaire (conversion)"),
    ("Dépôt de l'état des créances", classify.CREANCES),
    ("Jugement de faillite personnelle", classify.FAILLITE),
    ("Autre jugement et ordonnance", classify.AUTRE),
])
def test_type_procedure(nature, attendu):
    assert classify.type_procedure(nature) == attendu


def test_statut_ignore_creances_apres_jugement():
    types = ["Redressement judiciaire (ouverture)", classify.CREANCES]
    assert classify.statut(types) == "En redressement judiciaire"


def test_statut_suit_dernier_jugement():
    types = ["Redressement judiciaire (ouverture)", "Liquidation judiciaire (conversion)"]
    assert classify.statut(types) == "En liquidation judiciaire"


def test_statut_faillite_prioritaire():
    assert "faillite" in classify.statut([classify.CLOTURE_IA, classify.FAILLITE])


def test_statut_seulement_creances():
    assert classify.statut([classify.CREANCES]) == classify.STATUT_CREANCES


def test_motif_exclusion():
    assert classify.motif_exclusion("COPROPRIETE 9 RUE REY", "9 rue Rey") .startswith("Copropriété")
    assert "domiciliation" in classify.motif_exclusion("X", "6B boulevard Berthelot Bureau 3 34000")
    assert classify.motif_exclusion("PAMPA II", "20 rue de la Loge 34000 Montpellier") == ""


def test_secteur():
    assert classify.secteur("Débits de boissons") == "Restauration / bars / hôtellerie"
    assert classify.secteur("Coiffure") == "Beauté / services à la personne"
    assert classify.secteur("Commerce de détail de livres en magasin spécialisé") == "Maison / loisirs / culture"


# --- géographie ---------------------------------------------------------------
def test_distance_comedie_nulle():
    assert distance_m(Point(*COMEDIE), Point(*COMEDIE)) == 0


@pytest.mark.parametrize("point,adresse,zone", [
    (Point(43.6110, 3.8770), "rue Foch", ZONE_ECUSSON),                       # Préfecture
    (Point(43.6047, 3.8807), "place Auguste Gibert", ZONE_HYPERCENTRE),       # Gare Saint-Roch
    (Point(43.6020, 3.8720), "cours Gambetta", ZONE_FAUBOURGS),
    (Point(43.6030, 3.9150), "avenue Raymond Dugrand", ZONE_HORS_CENTRE),     # Port Marianne
    (None, "1 rue des Pertuisanes Centre Commercial Polygone", ZONE_HYPERCENTRE),
    (Point(43.6075, 3.8790), "7 rue des Etuves", ZONE_ECUSSON),               # rue reconnue
])
def test_classify_zone(point, adresse, zone):
    assert classify_zone(point, adresse).zone == zone


def test_rue_ecusson_ignoree_si_loin():
    # Une « rue de la Loge » à 3 km n'est pas l'Écusson
    assert classify_zone(Point(43.6300, 3.8500), "rue de la Loge").zone == ZONE_HORS_CENTRE


# --- BODACC -------------------------------------------------------------------
def test_parse_annonce():
    raw = {
        "id": "A1", "dateparution": "2026-09-10", "registre": ["882629249", "882 629 249"], "cp": "34000",
        "url_complete": "https://www.bodacc.fr/x",
        "listepersonnes": json.dumps({"personne": {"denomination": "PAMPA II", "activite": "Restauration traditionnelle",
                                                   "adresseSiegeSocial": {"numeroVoie": "20", "typeVoie": "rue",
                                                                          "nomVoie": "de la Loge", "codePostal": "34000",
                                                                          "ville": "Montpellier"}}}),
        "jugement": json.dumps({"nature": "Jugement de conversion en liquidation judiciaire", "date": "2026-09-04"}),
    }
    a = parse_annonce(raw)
    assert (a.nom, a.siren, a.date_jugement) == ("PAMPA II", "882629249", "2026-09-04")
    assert a.adresse == "20 rue de la Loge 34000 Montpellier"


def test_parse_annonce_champs_vides():
    a = parse_annonce({"id": "A2", "commercant": "DUPONT", "listepersonnes": "pas du json"})
    assert a.nom == "DUPONT" and a.siren == "" and a.adresse == ""


def test_ville_invalide_refusee():
    with pytest.raises(ValueError):
        fetch_annonces("Montpellier' OR 1=1", date(2026, 1, 1), date(2026, 2, 1))


def test_dates_inversees_refusees():
    with pytest.raises(ValueError):
        fetch_annonces("Montpellier", date(2026, 6, 1), date(2026, 1, 1))


# --- dates --------------------------------------------------------------------
@pytest.mark.parametrize("jour,mois,attendu", [
    (date(2026, 11, 24), 6, date(2026, 5, 24)),
    (date(2026, 3, 15), 6, date(2025, 9, 15)),
    (date(2026, 8, 31), 6, date(2026, 2, 28)),
])
def test_mois_avant(jour, mois, attendu):
    assert mois_avant(jour, mois) == attendu


# --- périodes souples ---------------------------------------------------------
@pytest.mark.parametrize("texte,fin,attendu", [
    ("2025-03-15", False, date(2025, 3, 15)),
    ("15/03/2025", False, date(2025, 3, 15)),
    ("03/2025", False, date(2025, 3, 1)),
    ("3/2025", True, date(2025, 3, 31)),
    ("2024-02", True, date(2024, 2, 29)),   # année bissextile
    ("2025", False, date(2025, 1, 1)),
    ("2025", True, date(2025, 12, 31)),
])
def test_lire_date(texte, fin, attendu):
    assert lire_date(texte, fin_de_periode=fin) == attendu


@pytest.mark.parametrize("texte", ["mars 2025", "13/2025", "2025-02-30", ""])
def test_lire_date_refuse(texte):
    with pytest.raises(ValueError):
        lire_date(texte)


def test_args_periode_par_mois():
    args = parse_args(["--debut", "03/2025", "--fin", "06/2026"])
    assert (args.debut, args.fin) == (date(2025, 3, 1), date(2026, 6, 30))


def test_args_periode_inversee_refusee():
    with pytest.raises(SystemExit):
        parse_args(["--debut", "2026", "--fin", "2025"])


def test_args_filtre_annonces():
    args = parse_args(["--annonces", "redressement,liquidation", "--annonces", "sauvegarde"])
    assert args.filtre == "liquidation, redressement, sauvegarde"
    assert "Sauvegarde" in args.types and "Liquidation judiciaire (conversion)" in args.types


def test_args_filtre_inconnu_refuse():
    with pytest.raises(SystemExit):
        parse_args(["--annonces", "divorce"])


def test_nom_fichier_avec_filtre():
    nom = nom_fichier("Montpellier", date(2025, 1, 1), date(2025, 12, 31), "liquidation, redressement")
    assert nom.endswith("_2025-01-01_2025-12-31_liquidation-redressement.xlsx")


# --- filtre par type d'annonce ------------------------------------------------
def _resultat(siren, jour, nature):
    from bodacc import Annonce
    from entreprises import FicheEntreprise
    from pipeline import Resultat
    a = Annonce(id=f"{siren}{jour}", date_parution=jour, date_jugement=jour, nature=nature, nom=f"SOC {siren}",
                enseigne="", siren=siren, forme="", activite="Restauration traditionnelle", adresse="rue de la Loge",
                cp="34000", complement="", url="")
    return Resultat(annonce=a, zone=ZONE_ECUSSON, distance_m=100, type_procedure=classify.type_procedure(nature),
                    secteur="", activite=a.activite, adresse=a.adresse, enseigne="", fiche=FicheEntreprise(siren))


def test_filtre_garde_historique_complet():
    from pipeline import filtrer_par_type
    rs = [
        _resultat("111", "2026-06-01", "Jugement d'ouverture d'une procédure de redressement judiciaire"),
        _resultat("111", "2026-08-01", "Jugement de conversion en liquidation judiciaire"),
        _resultat("222", "2026-07-01", "Jugement de clôture pour insuffisance d'actif"),
    ]
    annonces, commerces = filtrer_par_type(rs, classify.types_pour_filtres(["redressement"]))
    assert [a.annonce.siren for a in annonces] == ["111"]
    assert [c.siren for c in commerces] == ["111"]
    assert commerces[0].statut == "En liquidation judiciaire"   # suite connue malgré le filtre
    assert commerces[0].nb_annonces == 2


def test_sans_filtre_tout_est_garde():
    from pipeline import filtrer_par_type
    rs = [_resultat("111", "2026-06-01", "Dépôt de l'état des créances")]
    annonces, commerces = filtrer_par_type(rs, frozenset())
    assert len(annonces) == 1 and len(commerces) == 1


def test_parse_annonce_prenoms_en_liste():
    raw = {"id": "A3", "listepersonnes": json.dumps(
        {"personne": {"nom": "MARTIN", "prenom": ["Jean", "Paul"], "activite": "Coiffure"}})}
    assert parse_annonce(raw).nom == "MARTIN Jean, Paul"
