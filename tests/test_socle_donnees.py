from datetime import date

import pytest

import dvf
import etablissements as E
from adresses import cle_adresse, est_voie_nommee, normaliser_voie, numero
from config import ZONE_ECUSSON
from http_client import RessourceIntrouvable


# --- adresses ------------------------------------------------------------------
@pytest.mark.parametrize("adresse,voie", [
    ("12 GR JEAN MOULIN 34000 MONTPELLIER", "GRAND RUE JEAN MOULIN"),
    ("25 GR GRAND-RUE JEAN MOULIN", "GRAND RUE JEAN MOULIN"),
    ("29-31 GRAND RUE 31 GR JEAN MOULIN 34000 MONTP", "GRAND RUE JEAN MOULIN"),
    ("ANGLE DE LA RUE MASSANE 17 GR JEAN MOULIN", "GRAND RUE JEAN MOULIN"),
    ("211 CTRE COMMERC POLYGONE RUE DES PERTUISANES", "CENTRE COMMERCIAL LE POLYGONE"),
    ("20 rue de la Loge 34000 Montpellier", "RUE DE LA LOGE"),
    ("3 place Saint-Ravy 34000 Montpellier", "PLACE SAINT RAVY"),
    ("3 PL ST RAVY 34000", "PLACE SAINT RAVY"),
    ("2 R DE L'AIGUILLERIE 34000 MONTPELLIER", "RUE DE L'AIGUILLERIE"),
    ("", ""),
])
def test_normaliser_voie(adresse, voie):
    assert normaliser_voie(adresse) == voie


def test_numero_ignore_le_code_postal():
    assert numero("20 rue de la Loge 34000 Montpellier") == "20"
    assert numero("29-31 GRAND RUE 31 GR JEAN MOULIN 34000") == "31"
    assert numero("CENTRE COMMERCIAL LE POLYGONE 34000 MONTPELLIER") == ""


def test_cle_adresse_et_voie_nommee():
    assert cle_adresse("20 bis", "RUE DE LA LOGE") == "20|RUE DE LA LOGE"
    assert est_voie_nommee("RUE DE LA LOGE") and not est_voie_nommee("ZAC DU MILLENAIRE")


# --- établissements --------------------------------------------------------------
def _etab(siret, adresse, etat="A", naf="56.10C", fermeture=None, commune="34172", lat="43.6105", lon="3.8775"):
    return {"siret": siret, "commune": commune, "activite_principale": naf, "etat_administratif": etat,
            "date_fermeture": fermeture, "liste_enseignes": ["CHEZ NOUS"], "adresse": adresse,
            "latitude": lat, "longitude": lon, "date_creation": "2020-01-01"}


def test_depuis_resultat_filtre_commune_naf_et_fermetures_anciennes():
    resultat = {"siren": "1", "nom_complet": "SOC", "nombre_etablissements_ouverts": 1, "matching_etablissements": [
        _etab("a", "20 RUE DE LA LOGE 34000 MONTPELLIER"),
        _etab("b", "1 RUE X 34000", commune="34090"),
        _etab("c", "2 RUE DE LA LOGE 34000", naf="62.01Z"),
        _etab("d", "4 RUE DE LA LOGE 34000", etat="F", fermeture="2025-06-01"),
        _etab("e", "6 RUE DE LA LOGE 34000", etat="F", fermeture="2019-01-01"),
    ]}
    sortie = E.depuis_resultat(resultat, "34172", frozenset({"56.10C"}), date(2023, 11, 1))
    assert [e.siret for e in sortie] == ["a", "d"]
    assert sortie[0].voie == "RUE DE LA LOGE" and sortie[0].numero == "20" and sortie[0].independant


def test_chaine_reperee_par_le_nombre_d_etablissements():
    resultat = {"siren": "2", "nom_complet": "CHAINE", "nombre_etablissements_ouverts": 250,
                "matching_etablissements": [_etab("a", "20 RUE DE LA LOGE 34000")]}
    assert not E.depuis_resultat(resultat, "34172", frozenset({"56.10C"}), date(2023, 1, 1))[0].independant


def _stock(n_meme_adresse):
    base = dict(nom="X", enseigne="", naf="56.10C", latitude=43.6105, longitude=3.8775, date_creation="2020-01-01",
                date_fermeture="", actif=True, independant=True)
    meme = [E.Etablissement(siret=f"s{i}", siren=f"{i}", adresse="73 ALLEE KLEBER 34000", numero="73",
                            voie="ALLEE KLEBER", **base) for i in range(n_meme_adresse)]
    vraie = E.Etablissement(siret="v", siren="v", adresse="20 RUE DE LA LOGE 34000", numero="20",
                            voie="RUE DE LA LOGE", **base)
    return meme + [vraie]


def test_domiciliation_ecartee_au_dela_du_seuil():
    assert E.adresses_de_domiciliation(_stock(6)) == {"73|ALLEE KLEBER"}
    assert E.adresses_de_domiciliation(_stock(5)) == set()
    tableau = E.tableau(_stock(6))
    assert list(tableau["voie"]) == ["RUE DE LA LOGE"] and tableau["zone"].iloc[0] == ZONE_ECUSSON


# --- DVF -----------------------------------------------------------------------
def _ligne(mut, type_local, surface, valeur="300000", nature="Vente", lot="1"):
    return {"id_mutation": mut, "nature_mutation": nature, "type_local": type_local, "surface_reelle_bati": surface,
            "valeur_fonciere": valeur, "date_mutation": "2025-03-01", "adresse_numero": "20",
            "adresse_nom_voie": "RUE DE LA LOGE", "latitude": "43.6105", "longitude": "3.8775", "lot1_numero": lot}


def test_prix_m2_seulement_pour_un_local_seul():
    lignes = [
        _ligne("m1", dvf.TYPE_LOCAL_COMMERCIAL, "100"),                            # seul : 3000 €/m²
        _ligne("m2", dvf.TYPE_LOCAL_COMMERCIAL, "50"), _ligne("m2", "Appartement", "60", lot="2"),  # mixte
        _ligne("m3", "Appartement", "70"),                                            # pas de local
        _ligne("m4", dvf.TYPE_LOCAL_COMMERCIAL, "80", nature="Echange"),              # nature écartée
    ]
    ventes = {v["id_mutation"]: v for v in dvf.ventes_locaux(lignes)}
    assert set(ventes) == {"m1", "m2"}
    assert ventes["m1"]["prix_m2"] == 3000 and ventes["m1"]["voie"] == "RUE DE LA LOGE"
    assert ventes["m2"]["prix_m2"] is None and ventes["m2"]["surface"] == 50


def test_repli_national_si_fichier_commune_introuvable(monkeypatch):
    def introuvable(*_):
        raise RessourceIntrouvable("404")
    monkeypatch.setattr(dvf, "_lignes_commune", introuvable)
    monkeypatch.setattr(dvf, "_lignes_nationales", lambda annee, commune: iter([{"annee": str(annee)}]))
    assert dvf.lignes_annee(2026, "34", "34172") == [{"annee": "2026"}]
