"""Sélection et rédaction de l'alerte hebdomadaire (sans appel réseau)."""
from dataclasses import replace
from datetime import date

import pytest

import alerte
from bodacc import Annonce
from config import ZONE_ECUSSON, ZONE_FAUBOURGS, ZONE_HYPERCENTRE
from entreprises import FicheEntreprise
from pipeline import Resultat
from tests.test_fiche_aide import KWESTMI, MESCLUB_CREANCES, SAM_RENOVATION, TRITON

OUVERTURE_RJ = "Jugement d'ouverture d'une procédure de redressement judiciaire"
OUVERTURE_SAUVEGARDE = "Jugement d'ouverture d'une procédure de sauvegarde"
LISTE_CREANCES = "Liste des créances nées après le jugement d'ouverture d'une procédure de redressement judiciaire"
RJ = "Redressement judiciaire (ouverture)"
DEBUT, FIN = date(2026, 11, 18), date(2026, 11, 24)


def resultat(nom: str, nature: str = OUVERTURE_RJ, type_procedure: str = RJ, zone: str = ZONE_ECUSSON,
             complement: str = KWESTMI, parution: str = "2026-11-20", siren: str = "",
             enseigne: str = "") -> Resultat:
    annonce = Annonce(
        id=f"A-{nom}", date_parution=parution, date_jugement="2026-11-13", nature=nature, nom=nom,
        enseigne=enseigne, siren=siren, forme="SAS", activite="Restauration traditionnelle",
        adresse="12 rue de l'Aiguillerie 34000 Montpellier", cp="34000", complement=complement,
        url=f"https://www.bodacc.fr/annonce/{nom}",
    )
    return Resultat(
        annonce=annonce, zone=zone, distance_m=300, type_procedure=type_procedure,
        secteur="Restauration / bars / hôtellerie", activite=annonce.activite, adresse=annonce.adresse,
        enseigne=enseigne, fiche=FicheEntreprise(siren=siren),
    )


# --- sélection ------------------------------------------------------------------
def test_ne_garde_que_les_ouvertures_de_redressement_et_de_sauvegarde():
    resultats = [
        resultat("KWESTMI"),
        resultat("TRITON", OUVERTURE_SAUVEGARDE, "Sauvegarde", complement=TRITON),
        # classify range ces annonces parmi les ouvertures : l'alerte doit les écarter
        resultat("MESCLUB.BG", LISTE_CREANCES, RJ, complement=MESCLUB_CREANCES),
        resultat("ROCCO ET SA MERE", "Jugement modifiant le plan de sauvegarde", "Sauvegarde"),
        resultat("FERME", "Jugement d'ouverture de liquidation judiciaire", "Liquidation judiciaire (ouverture)"),
    ]
    assert [r.annonce.nom for r in alerte.selectionner(resultats)] == ["KWESTMI", "TRITON"]


def test_une_seule_annonce_par_commerce_la_plus_recente():
    ancienne = resultat("SAPORI", parution="2026-11-18", siren="123456789")
    recente = resultat("SAPORI", parution="2026-11-22", siren="123456789")
    choisis = alerte.selectionner([recente, ancienne])
    assert choisis == [recente]


def test_tri_par_zone_puis_par_nom():
    resultats = [
        resultat("zèbre", zone=ZONE_FAUBOURGS),
        resultat("Bistrot", zone=ZONE_HYPERCENTRE),
        resultat("Atelier", zone=ZONE_ECUSSON),
        resultat("Café", zone=ZONE_ECUSSON),
    ]
    assert [r.annonce.nom for r in alerte.selectionner(resultats)] == ["Atelier", "Café", "Bistrot", "zèbre"]


def test_selection_vide():
    assert alerte.selectionner([]) == []


# --- rédaction ------------------------------------------------------------------
def test_alerte_vide_si_aucun_commerce():
    assert alerte.rediger_alerte([], DEBUT, FIN) == ""


def test_alerte_complete_pour_un_commerce():
    texte = alerte.rediger_alerte([resultat("KWESTMI", enseigne="Le Kwest", siren="912345678")], DEBUT, FIN)
    assert texte.startswith("# Alerte commerces du centre-ville — Semaine du 18/11/2026 au 24/11/2026\n")
    assert "**1 commerce** du centre-ville de Montpellier placé en redressement" in texte
    for attendu in (
        "## 1. KWESTMI — enseigne « Le Kwest »",
        "- **Activité** : Restauration traditionnelle",
        "- **Adresse** : 12 rue de l'Aiguillerie 34000 Montpellier",
        f"- **Zone** : {ZONE_ECUSSON}",
        f"- **Procédure** : {RJ}",
        "- **Date du jugement** : 13/11/2026 (publié au BODACC le 20/11/2026)",
        "- **SIREN** : 912345678",
        "- **Cessation des paiements** : 15/07/2026",
        "- **Mandataire judiciaire** : SELARL AEGIS prise en la personne de Me Souad HADDANI-AGDAY — "
        "996, rue de Las Sorbès - Résidence le Cythère - 34000 Montpellier",
        "- **Déclaration des créances** : dans les deux mois de la présente publication "
        "(soit vers le 20/01/2027, à vérifier)",
        "- **Annonce BODACC** : [voir l'annonce officielle](https://www.bodacc.fr/annonce/KWESTMI)",
        "## Contacts d'aide à proposer aux commerçants",
        "**CCI Hérault**",
        "Médiateur des entreprises",
    ):
        assert attendu in texte, attendu
    assert "Administrateur judiciaire" not in texte


def test_administrateur_et_pouvoirs():
    texte = alerte.rediger_alerte([resultat("SAM RENOVATION", complement=SAM_RENOVATION)], DEBUT, FIN)
    assert ("- **Administrateur judiciaire** : SELARL AMAJ représentée par Maître ANTOINE MANENT — "
            "110, impasse John Locke - 34470 Pérols (pouvoirs : d'assister le débiteur pour tous les actes "
            "relatifs à la gestion)") in texte


def test_plusieurs_commerces_numerotes_et_periode_longue():
    resultats = [resultat("A"), resultat("B", OUVERTURE_SAUVEGARDE, "Sauvegarde", complement=TRITON)]
    texte = alerte.rediger_alerte(resultats, date(2026, 11, 1), FIN)
    assert "Période du 01/11/2026 au 24/11/2026" in texte
    assert "**2 commerces** du centre-ville de Montpellier placés" in texte
    assert "## 1. A" in texte and "## 2. B" in texte
    assert texte.count("## Contacts d'aide") == 1


def test_delai_deja_ecoule_signale():
    r = resultat("ANCIEN", parution="2026-09-10")
    texte = alerte.rediger_alerte([r], date(2026, 9, 1), FIN)
    assert "(soit vers le 10/11/2026 : délai probablement écoulé)" in texte


def test_texte_de_jugement_absent():
    texte = alerte.rediger_alerte([resultat("SANS TEXTE", complement="")], DEBUT, FIN)
    assert "ne précise pas les intervenants" in texte
    assert "Cessation des paiements" not in texte


def test_caracteres_markdown_et_mentions_neutralises():
    r = resultat("*SUPER*_[BAR]")
    r = replace(r, annonce=replace(r.annonce, nom="*SUPER*_[BAR] @equipe"))
    texte = alerte.rediger_alerte([r], DEBUT, FIN)
    assert r"## 1. \*SUPER\*\_\[BAR\] @" + "​" + "equipe" in texte


# --- ligne de commande -------------------------------------------------------------
def test_periode_par_defaut_sept_jours():
    args = alerte.parse_args([], date(2026, 11, 30))
    assert (args.debut, args.fin) == (date(2026, 11, 24), date(2026, 11, 30))
    assert args.sec is False


def test_option_depuis_et_sec():
    args = alerte.parse_args(["--depuis", "2026-11-01", "--sec"], date(2026, 11, 25))
    assert (args.debut, args.fin, args.sec) == (date(2026, 11, 1), date(2026, 11, 25), True)


@pytest.mark.parametrize("depuis", ["01/11/2026", "2026-13-01", "2026-12-01"])
def test_option_depuis_invalide(depuis):
    with pytest.raises(SystemExit):
        alerte.parse_args(["--depuis", depuis], date(2026, 11, 25))


class _Rapport:
    def __init__(self, retenus):
        self.retenus = tuple(retenus)


def test_main_n_ecrit_rien_sans_commerce(tmp_path, monkeypatch, capsys):
    sortie = tmp_path / "alerte.md"
    sortie.write_text("ancienne alerte", encoding="utf-8")
    monkeypatch.setattr(alerte, "run", lambda *a, **k: _Rapport([resultat("M", LISTE_CREANCES)]))
    assert alerte.main(["--sec", "--sortie", str(sortie)]) == 0
    assert not sortie.exists()
    assert capsys.readouterr().out == ""


def test_main_ecrit_l_alerte_et_l_affiche_avec_sec(tmp_path, monkeypatch, capsys):
    sortie = tmp_path / "alerte.md"
    monkeypatch.setattr(alerte, "run", lambda *a, **k: _Rapport([resultat("KWESTMI")]))
    assert alerte.main(["--sec", "--sortie", str(sortie)]) == 0
    contenu = sortie.read_text(encoding="utf-8")
    assert "## 1. KWESTMI" in contenu
    assert capsys.readouterr().out == contenu


def test_main_sans_sec_n_affiche_rien(tmp_path, monkeypatch, capsys):
    sortie = tmp_path / "alerte.md"
    monkeypatch.setattr(alerte, "run", lambda *a, **k: _Rapport([resultat("KWESTMI")]))
    assert alerte.main(["--sortie", str(sortie)]) == 0
    assert sortie.exists() and capsys.readouterr().out == ""


def test_main_source_indisponible(tmp_path, monkeypatch):
    def panne(*a, **k):
        raise alerte.SourceIndisponible("BODACC hors service")
    monkeypatch.setattr(alerte, "run", panne)
    assert alerte.main(["--sortie", str(tmp_path / "alerte.md")]) == 1
    assert not (tmp_path / "alerte.md").exists()
