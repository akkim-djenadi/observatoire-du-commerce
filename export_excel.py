"""Mise en forme du rapport en fichier Excel (5 onglets)."""
from collections import Counter
from pathlib import Path
from typing import Any, BinaryIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from config import HYPERCENTRE_MAX_M, FAUBOURGS_MAX_M, ZONE_ORDER
from pipeline import Rapport

BLEU = "1F3A5F"
ZONE_FILL = {0: "FDECEC", 1: "FFF4E0", 2: "EEF4FB"}
LIEN = Font(color="1155CC", underline="single")
BORDURE = Border(bottom=Side(style="thin", color="D0D5DD"))


def _table(ws: Worksheet, headers: list[str], rows: list[list[Any]], widths: list[int],
           zone_col: int | None = None, link_col: int | None = None) -> None:
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=BLEU)
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    for row in rows:
        ws.append(row)
    for i, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            cell.border = BORDURE
        if zone_col is not None and row[zone_col].value in ZONE_ORDER:
            row[zone_col].fill = PatternFill("solid", fgColor=ZONE_FILL[ZONE_ORDER[row[zone_col].value]])
        if link_col is not None and row[link_col].value:
            row[link_col].hyperlink = row[link_col].value
            row[link_col].font = LIEN
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


def _synthese(ws: Worksheet, rap: Rapport) -> None:
    ws.title = "Synthèse"
    ws["A1"] = f"Procédures collectives BODACC : commerces du centre-ville de {rap.ville}"
    ws["A1"].font = Font(bold=True, size=14, color=BLEU)
    ws["A2"] = (f"Parutions du {rap.debut:%d/%m/%Y} au {rap.fin:%d/%m/%Y}. "
                "Source : BODACC (DILA), API référencée sur data.gouv.fr.")
    ws["A2"].font = Font(italic=True, color="555555")
    ws["A3"] = f"Types d'annonce : {rap.filtre or 'tous'}"
    ws["A3"].font = Font(italic=True, color="555555")
    blocs = [
        ("Chiffres clés", [
            (f"Annonces « procédures collectives » à {rap.ville} (toutes activités)", rap.nb_annonces_ville),
            ("Annonces retenues (commerces du centre-ville)", len(rap.retenus)),
            ("Commerces distincts concernés", len(rap.commerces)),
        ]),
        ("Commerces par zone", sorted(Counter(c.zone for c in rap.commerces).items(), key=lambda t: ZONE_ORDER[t[0]])),
        ("Commerces par statut (dernier jugement publié)", Counter(c.statut for c in rap.commerces).most_common()),
        ("Commerces par secteur", Counter(c.secteur for c in rap.commerces).most_common()),
    ]
    row = 5
    for titre, lignes in blocs:
        ws.cell(row, 1, titre).font = Font(bold=True, color=BLEU)
        row += 1
        for libelle, valeur in lignes:
            ws.cell(row, 1, libelle)
            ws.cell(row, 2, valeur)
            row += 1
        row += 1
    ws.column_dimensions["A"].width = 78
    ws.column_dimensions["B"].width = 12


def _methode(ws: Worksheet, rap: Rapport) -> None:
    lignes = [
        "SOURCES",
        "• BODACC, annonces commerciales, famille « Procédures collectives » (DILA), API bodacc-datadila.opendatasoft.com référencée sur data.gouv.fr.",
        "• API Recherche d'entreprises (recherche-entreprises.api.gouv.fr, INSEE / RNE) : code NAF, état administratif, date de création.",
        "• Base Adresse Nationale, Géoplateforme IGN (data.geopf.fr/geocodage) : géolocalisation des adresses.",
        "",
        "PÉRIMÈTRE",
        f"• Parutions du {rap.debut:%d/%m/%Y} au {rap.fin:%d/%m/%Y}. Types d'annonce : {rap.filtre or 'tous les jugements de procédure collective'}.",
        "• Avec un filtre, l'onglet « Annonces détaillées » ne montre que les annonces de ces types ; l'historique et le statut d'un commerce tiennent compte de toutes ses annonces de la période.",
        "• « Commerce » : détail, restauration, bars, hôtellerie, alimentaire, coiffure, beauté, services à la personne, agences immobilières, auto-école. Exclus : BTP, conseil, informatique, holdings, SCI, libéraux, vente à distance, gros.",
        "• Écusson : intérieur des boulevards. Hypercentre : moins de %d m de la Comédie. Faubourgs : de %d à %d m." % (HYPERCENTRE_MAX_M, HYPERCENTRE_MAX_M, FAUBOURGS_MAX_M),
        "",
        "LIMITES",
        "• Le BODACC publie souvent l'adresse du siège : un commerce domicilié ailleurs peut manquer.",
        "• Une clôture publiée dans la période peut concerner une liquidation ouverte avant.",
        "• Les litiges civils (baux, prud'hommes) ne sont pas publiés au BODACC.",
    ]
    for ligne in lignes:
        ws.append([ligne])
    ws.column_dimensions["A"].width = 150
    for row in ws.iter_rows():
        row[0].alignment = Alignment(wrap_text=True)
        if row[0].value and row[0].value.isupper():
            row[0].font = Font(bold=True, color=BLEU)


def write_excel(rap: Rapport, path: Path | BinaryIO) -> Path | BinaryIO:
    """Écrit le rapport dans un fichier, ou dans un flux mémoire (téléchargement)."""
    wb = Workbook()
    _synthese(wb.active, rap)
    _table(wb.create_sheet("Commerces"),
           ["Zone", "Raison sociale / nom", "Enseigne", "SIREN", "Forme", "Secteur", "Activité", "Adresse",
            "Statut (dernier jugement)", "Date dernier jugement", "Dernière parution", "Nb annonces",
            "Historique des annonces", "État INSEE", "Création", "Lien BODACC", "Distance Comédie (m)"],
           [[c.zone, c.nom, c.enseigne, c.siren, c.forme, c.secteur, c.activite, c.adresse, c.statut,
             c.date_jugement, c.derniere_parution, c.nb_annonces, c.historique, c.etat_insee,
             c.date_creation, c.url, c.distance_m] for c in rap.commerces],
           [22, 28, 16, 13, 22, 22, 30, 38, 30, 13, 13, 8, 60, 10, 11, 30, 10], zone_col=0, link_col=15)
    annonces = sorted(rap.retenus, key=lambda r: r.annonce.date_parution, reverse=True)
    _table(wb.create_sheet("Annonces détaillées"),
           ["Date parution", "Date jugement", "Type", "Nature exacte du jugement", "Zone", "Raison sociale / nom",
            "SIREN", "Activité", "Adresse", "Texte du jugement", "Lien BODACC"],
           [[r.annonce.date_parution, r.annonce.date_jugement, r.type_procedure, r.annonce.nature, r.zone,
             r.annonce.nom, r.annonce.siren, r.activite, r.adresse, r.annonce.complement, r.annonce.url]
            for r in annonces],
           [12, 12, 26, 36, 22, 28, 13, 30, 38, 80, 30], zone_col=4, link_col=10)
    _table(wb.create_sheet("Exclus (contrôle)"),
           ["Raison sociale", "SIREN", "Activité", "Adresse", "Motif d'exclusion", "Lien BODACC"],
           [[r.annonce.nom, r.annonce.siren, r.activite, r.adresse, r.motif_exclusion, r.annonce.url]
            for r in rap.exclus],
           [28, 13, 30, 40, 50, 30], link_col=5)
    _methode(wb.create_sheet("Méthode & sources"), rap)
    if isinstance(path, Path):
        path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path
