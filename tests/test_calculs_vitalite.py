from datetime import date

import pandas as pd
import pytest

import indice as I
import locaux as L
import offre as O

ZONE = "Écusson (cœur historique)"
JOUR = date(2026, 11, 1)


def _etab(siret, naf, numero, voie, creation="2015-01-01", fermeture="", independant=True, enseigne="X"):
    return {"siret": siret, "siren": siret, "nom": f"SOC {siret}", "enseigne": enseigne, "naf": naf,
            "adresse": f"{numero} {voie} 34000 MONTPELLIER", "numero": numero, "voie": voie,
            "latitude": "43.6105", "longitude": "3.8775", "date_creation": creation, "date_fermeture": fermeture,
            "actif": str(not fermeture), "independant": str(independant), "zone": ZONE}


def _stock():
    loge = "RUE DE LA LOGE"
    lignes = [_etab(f"r{i}", "56.10A", str(i), loge) for i in range(1, 5)]              # 4 restaurants
    lignes += [_etab(f"v{i}", "47.71Z", str(10 + i), loge, independant=False) for i in range(1, 4)]  # 3 chaînes
    lignes += [_etab("b1", "47.24Z", "20", loge, creation="2026-03-01")]               # ouverture récente
    lignes += [_etab("f1", "96.02A", "30", loge, fermeture="2026-05-01")]               # fermeture récente
    lignes += [_etab("f2", "47.77Z", "40", loge, fermeture="2026-06-01"),               # fermé puis repris
               _etab("n2", "47.71Z", "40", loge, creation="2026-08-01")]
    return pd.DataFrame(lignes)


# --- offre ----------------------------------------------------------------------
@pytest.mark.parametrize("naf,fam", [("56.10C", "Restauration et bars"), ("47.78A", "Santé et optique"),
                                      ("47.78C", "Maison, culture et loisirs"), ("47.24Z", "Alimentaire"),
                                      ("62.01Z", O.AUTRE)])
def test_famille_prefixe_le_plus_precis(naf, fam):
    assert O.famille(naf) == fam


def test_actifs_et_mouvements_reconstitues_a_une_date():
    df = _stock()
    assert len(O.actifs_a(df, JOUR)) == 9                    # 11 lignes − 2 fermées
    assert len(O.actifs_a(df, date(2026, 2, 1))) == 9        # avant l'ouverture de b1 et n2, f1 et f2 encore là
    assert O.mouvements(df, date(2025, 11, 1), JOUR) == (2, 2)


def test_diversite_bornes():
    une = pd.DataFrame({"naf": ["56.10A"] * 5})
    assert O.diversite(une) == 0
    assert O.diversite(pd.DataFrame({"naf": []})) is None
    variee = pd.DataFrame({"naf": ["56.10A", "47.71Z", "47.24Z", "96.02A", "47.73Z", "47.59A", "68.31Z", "55.10Z"]})
    assert 0.9 < O.diversite(variee) <= 1


def test_part_independants_et_familles_rares():
    actifs = O.actifs_a(_stock(), JOUR)
    assert O.part_independants(actifs) == round(6 / 9, 3)   # 4 restaurants + boulangerie + boutique reprise
    rue = actifs[actifs["naf"] == "56.10A"]
    assert "Équipement de la personne" in O.familles_rares(rue, actifs)


# --- locaux -----------------------------------------------------------------------
def test_locaux_liberes_sans_reprise():
    proc = pd.DataFrame([{"type": "Liquidation judiciaire (ouverture)", "date_jugement": "2026-09-10",
                          "adresse": "50 rue de la Loge 34000 Montpellier", "zone": ZONE, "latitude": None,
                          "longitude": None, "enseigne": "PAMPA", "nom": "PAMPA II", "secteur": "Restauration"}])
    lib = L.liberes(_stock(), proc, JOUR)
    assert set(lib["cle"]) == {"30|RUE DE LA LOGE", "50|RUE DE LA LOGE"}   # le 40 a été repris
    assert set(lib["source"]) == {"Fermeture (Sirene)", "Liquidation (BODACC)"}


def test_feuille_des_locaux_controlee():
    csv = "Adresse,Surface m2,Loyer mensuel,Contact,Disponible depuis,Commentaire\n" \
          "12 rue de l'Université,45 m²,\"1 200 €\",agence,2026-10,vitrine\n,,,,,\n"
    df = L.lire_feuille(csv)
    assert len(df) == 1 and df["surface_m2"].iat[0] == 45 and df["loyer_mensuel"].iat[0] == 1200
    assert df["voie"].iat[0] == "RUE DE L'UNIVERSITE"
    with pytest.raises(ValueError):
        L.lire_feuille("adresse,prix\n1 rue X,3\n")


# --- indice -------------------------------------------------------------------------
def test_score_borne_et_inverse():
    solde, defaillances = I.COMPOSANTES[0], I.COMPOSANTES[1]
    assert I.score(solde, 0) == 50 and I.score(solde, 0.2) == 100 and I.score(solde, -1) == 0
    assert I.score(defaillances, 0) == 100 and I.score(defaillances, 0.03) == 50
    assert I.score(solde, None) is None


def test_poids_recalcules_si_composante_absente():
    complet = {c.cle: 50.0 for c in I.COMPOSANTES}
    assert I.indice(complet) == 50
    sans_prix = {**{c.cle: 100.0 for c in I.COMPOSANTES}, "prix": None, "solde": 0.0}
    assert I.indice(sans_prix) == round(100 * (1 - 0.30 / 0.90), 1)
    assert I.indice({c.cle: None for c in I.COMPOSANTES}) is None
    assert sum(c.poids for c in I.COMPOSANTES) == pytest.approx(1)


def test_calculer_centre_zone_et_rue():
    donnees = {"etablissements": _stock(), "procedures": pd.DataFrame(columns=["type", "date_jugement", "adresse",
               "zone", "voie", "latitude", "longitude", "enseigne", "nom", "secteur"]),
               "dvf": pd.DataFrame(columns=["date", "prix_m2", "zone", "voie"])}
    res = I.calculer(donnees, JOUR)
    assert list(res["niveau"]) == ["centre", "zone", "rue"]
    centre = res.iloc[0]
    assert centre["brut_stock"] == 9 and centre["brut_ouvertures"] == 2 and centre["brut_fermetures"] == 2
    assert pd.isna(centre["score_prix"]) and 0 <= centre["indice"] <= 100


def test_historique_reconstitue_puis_remplace_le_mois():
    donnees = {"etablissements": _stock(), "procedures": pd.DataFrame(columns=["type", "date_jugement", "adresse",
               "zone", "voie", "latitude", "longitude", "enseigne", "nom", "secteur"]),
               "dvf": pd.DataFrame(columns=["date", "prix_m2", "zone", "voie"])}
    premier = I.mettre_a_jour_historique(None, donnees, JOUR)
    assert premier["mois"].nunique() == 13 and set(premier["methode"]) == {"mesuré", "reconstitué"}
    second = I.mettre_a_jour_historique(premier, donnees, JOUR)
    assert len(second) == len(premier)          # le mois courant est remplacé, pas dupliqué


def test_lissage_rapproche_les_petites_rues_de_leur_zone():
    zone = {"stock": 1000, "solde": 0.0, "defaillances": 0.02, "vacance": 0.05, "diversite": 0.8}
    petite = {"stock": 10, "solde": -0.10, "defaillances": 0.0, "vacance": 0.0, "diversite": 0.3}
    grande = {**petite, "stock": 400}
    lp, lg = I.lisser(petite, zone), I.lisser(grande, zone)
    assert lp["solde"] == pytest.approx(-0.10 * 10 / 30)      # 10 commerces de la rue, 20 « empruntés » à la zone
    assert lg["solde"] < lp["solde"]                            # une grande rue garde davantage sa propre valeur
    assert lp["diversite"] == 0.3                               # la diversité n'est pas lissée


def test_locaux_liberes_ignores_hors_rue_commercante():
    stock = pd.concat([_stock(), pd.DataFrame([_etab("x1", "96.02A", "5", "RUE DES LILAS", fermeture="2026-04-01")])])
    vide = pd.DataFrame(columns=["type", "date_jugement", "adresse", "zone", "latitude", "longitude", "enseigne",
                                 "nom", "secteur"])
    assert "5|RUE DES LILAS" not in set(L.liberes(stock, vide, JOUR)["cle"])   # rue sans autre commerce
