"""Extraction de la fiche d'aide sur de vrais textes de jugement BODACC (Montpellier, 2026)."""
import pytest

from fiche_aide import (
    CONTACTS_AIDE, FicheAide, Intervenant, date_limite, extraire_fiche, lire_date_fr, separer_nom_adresse,
)

# KWESTMI, redressement judiciaire, publié le 2026-09-10
KWESTMI = (
    "Jugement prononçant l'ouverture d'une procédure de redressement judiciaire , date de cessation "
    "des paiements le 15 Juillet 2026 , désignant mandataire judiciaire SELARL AEGIS prise en la personne "
    "de Me Souad HADDANI-AGDAY 996, rue de Las Sorbès - Résidence le Cythère - 34000 Montpellier . Les "
    "créances sont à adresser, dans les deux mois de la présente publication, auprès du Mandataire "
    "Judiciaire ou sur le portail électronique prévu par les articles L. 814-2 et L. 814-13 du code de commerce."
)
# SAM RENOVATION : administrateur et mandataire, publié le 2026-07-07
SAM_RENOVATION = (
    "Jugement prononçant l'ouverture d'une procédure de redressement judiciaire , date de cessation des "
    "paiements le 01 Février 2026 , désignant administrateur SELARL AMAJ représentée par Maître ANTOINE "
    "MANENT 110, impasse John Locke - 34470 Pérols avec les pouvoirs : d'assister le débiteur pour tous les "
    "actes relatifs à la gestion, mandataire judiciaire SELARL AEGIS prise en la personne de Me Souad "
    "HADDANI-AGDAY 996, rue de Las Sorbès - Résidence le Cythère - 34000 Montpellier . Les créances sont à "
    "adresser, dans les deux mois de la présente publication, auprès du Mandataire Judiciaire ou sur le "
    "portail électronique prévu par les articles L. 814-2 et L. 814-13 du code de commerce."
)
# Triton : sauvegarde, sans date de cessation des paiements
TRITON = (
    "Jugement prononçant l'ouverture d'une procédure de sauvegarde et désignant administrateur SELARL FHBX "
    "représentée par Me Jean-François BLANC 22, rue des Chasseurs - 34070 Montpellier avec les pouvoirs : de "
    "surveiller le débiteur dans sa gestion, mandataire judiciaire Me Christine Dauverchain 2, rue "
    "Saint-Come - 34000 Montpellier . Les créances sont à adresser, dans les deux mois de la présente "
    "publication, auprès du Mandataire Judiciaire ou sur le portail électronique prévu par les articles "
    "L. 814-2 et L. 814-13 du code de commerce."
)
# DTL : l'adresse commence par un nom d'immeuble
DTL = (
    "Jugement prononçant l'ouverture d'une procédure de redressement judiciaire , date de cessation des "
    "paiements le 29 Mai 2026 , désignant mandataire judiciaire Me Vincent AUSSEL Arche Jacques Coeur - 222, "
    "place Ernest Granier - 34000 Montpellier . Les créances sont à adresser, dans les deux mois de la "
    "présente publication, auprès du Mandataire Judiciaire ou sur le portail électronique prévu par les "
    "articles L. 814-2 et L. 814-13 du code de commerce."
)
# NARIN Aden : « Maître NOM Prénom », adresse « 44 bis », pas de date de cessation
NARIN = (
    "Jugement prononçant l'ouverture d'une procédure de redressement judiciaire, en application du II de "
    "l'article L. 681-2 du code de commerce, , désignant mandataire judiciaire Maître MARTINEAU Laetitia "
    "44 bis, rue de l'Hôtel de Ville - 81100 Castres . Les créances sont à adresser, dans les deux mois de "
    "la présente publication, auprès du Mandataire Judiciaire ou sur le portail électronique prévu par les "
    "articles L. 814-2 et L. 814-13 du code de commerce."
)
# MESCLUB.BG : liste des créances, pas un jugement d'ouverture
MESCLUB_CREANCES = (
    "La liste des créances de l'article L 622-17 du code de commerce est déposée au greffe où tout intéressé "
    "peut contester cette liste devant le juge-commissaire dans le délai d'un mois à compter de la présente "
    "publication."
)
AEGIS = Intervenant(
    "SELARL AEGIS prise en la personne de Me Souad HADDANI-AGDAY",
    "996, rue de Las Sorbès - Résidence le Cythère - 34000 Montpellier",
)


def test_kwestmi_mandataire_cessation_et_delai():
    fiche = extraire_fiche(KWESTMI, "2026-09-10")
    assert fiche.mandataire == AEGIS
    assert fiche.administrateur is None
    assert fiche.date_cessation == "2026-07-15"
    assert fiche.delai_creances == "dans les deux mois de la présente publication"
    assert fiche.date_limite_creances == "2026-11-10"


def test_administrateur_et_mandataire_distincts():
    fiche = extraire_fiche(SAM_RENOVATION, "2026-07-07")
    assert fiche.administrateur == Intervenant(
        "SELARL AMAJ représentée par Maître ANTOINE MANENT", "110, impasse John Locke - 34470 Pérols"
    )
    assert fiche.pouvoirs_administrateur == "d'assister le débiteur pour tous les actes relatifs à la gestion"
    assert fiche.mandataire == AEGIS
    assert fiche.date_cessation == "2026-02-01"


def test_sauvegarde_sans_date_de_cessation():
    fiche = extraire_fiche(TRITON, "2026-06-11")
    assert fiche.administrateur == Intervenant(
        "SELARL FHBX représentée par Me Jean-François BLANC", "22, rue des Chasseurs - 34070 Montpellier"
    )
    assert fiche.pouvoirs_administrateur == "de surveiller le débiteur dans sa gestion"
    assert fiche.mandataire == Intervenant("Me Christine Dauverchain", "2, rue Saint-Come - 34000 Montpellier")
    assert fiche.date_cessation == ""
    assert fiche.date_limite_creances == "2026-08-11"


def test_adresse_commencant_par_un_nom_d_immeuble():
    fiche = extraire_fiche(DTL)
    assert fiche.mandataire == Intervenant(
        "Me Vincent AUSSEL", "Arche Jacques Coeur - 222, place Ernest Granier - 34000 Montpellier"
    )
    assert fiche.date_cessation == "2026-05-29"
    assert fiche.date_limite_creances == ""  # sans date de parution, pas d'estimation


def test_maitre_nom_prenom_et_numero_bis():
    fiche = extraire_fiche(NARIN, "2026-07-02")
    assert fiche.mandataire == Intervenant("Maître MARTINEAU Laetitia", "44 bis, rue de l'Hôtel de Ville - 81100 Castres")
    assert fiche.date_cessation == ""


def test_texte_sans_jugement_d_ouverture():
    fiche = extraire_fiche(MESCLUB_CREANCES, "2026-11-02")
    assert fiche.mandataire is None and fiche.administrateur is None
    assert fiche.date_cessation == ""
    assert fiche.delai_creances == ""


def test_texte_vide():
    fiche = extraire_fiche("")
    assert fiche == FicheAide()
    assert fiche.est_vide


@pytest.mark.parametrize("titulaire,nom,adresse", [
    ("SELAS OCMJ représentée par Maître Olivier CHAUFFOUR 18, rue Marcel de Serres - 34000 Montpellier",
     "SELAS OCMJ représentée par Maître Olivier CHAUFFOUR", "18, rue Marcel de Serres - 34000 Montpellier"),
    ("Me Jean DE LA FONTAINE 3, rue Foch - 34000 Montpellier",
     "Me Jean DE LA FONTAINE", "3, rue Foch - 34000 Montpellier"),
    ("SCP DUPONT 12, rue Foch - 34000 Montpellier", "SCP DUPONT", "12, rue Foch - 34000 Montpellier"),
    ("SCP DUPONT", "SCP DUPONT", ""),
])
def test_separer_nom_adresse(titulaire, nom, adresse):
    assert separer_nom_adresse(titulaire) == Intervenant(nom, adresse)


@pytest.mark.parametrize("jour,mois,annee,attendu", [
    ("04", "Août", "2026", "2026-08-04"),
    ("1", "décembre", "2025", "2025-12-01"),
    ("31", "Février", "2026", ""),   # date impossible
    ("12", "Brumaire", "2026", ""),  # mois inconnu
])
def test_lire_date_fr(jour, mois, annee, attendu):
    assert lire_date_fr(jour, mois, annee) == attendu


@pytest.mark.parametrize("parution,delai,attendu", [
    ("2026-11-24", "dans les deux mois de la présente publication", "2027-01-24"),
    ("2026-12-31", "dans les deux mois de la présente publication", "2027-02-28"),
    ("2026-11-02", "dans le délai d'un mois à compter de la présente publication", "2026-12-02"),
    ("", "dans les deux mois de la présente publication", ""),
    ("pas une date", "dans les deux mois de la présente publication", ""),
    ("2026-11-24", "dans les quinze jours", ""),
])
def test_date_limite(parution, delai, attendu):
    assert date_limite(parution, delai) == attendu


def test_contacts_sans_numero_de_telephone():
    assert len(CONTACTS_AIDE) == 4
    noms = " ".join(c.nom for c in CONTACTS_AIDE)
    for attendu in ("CCI Hérault", "(CIP)", "Médiateur des entreprises", "Tribunal de commerce de Montpellier"):
        assert attendu in noms
    for c in CONTACTS_AIDE:
        assert not any(ch.isdigit() for ch in c.role + c.ou_trouver)
