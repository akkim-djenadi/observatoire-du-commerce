"""Veille BODACC de l'Observatoire du Commerce : procédures collectives des commerces du centre-ville.

Exemples :
    python3 main.py                                   # 6 derniers mois, toutes annonces
    python3 main.py --mois 3                          # 3 derniers mois
    python3 main.py --debut 03/2025 --fin 06/2026     # de mars 2025 à juin 2026 inclus
    python3 main.py --debut 2025 --fin 2025           # toute l'année 2025
    python3 main.py --annonces redressement,liquidation
"""
import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from classify import FILTRES_LIBELLES, types_pour_filtres
from export_excel import write_excel
from http_client import SourceIndisponible
from periode import FORMATS_AIDE, lire_date, mois_avant
from pipeline import run

ICI = Path(__file__).resolve().parent
DOSSIER_SORTIE = ICI / "exports"
CACHE = ICI / "cache" / "entreprises.json"
MOIS_PAR_DEFAUT = 6

AIDE_ANNONCES = "Types d'annonce à garder, séparés par des virgules : " + "; ".join(
    f"{cle} = {libelle}" for cle, libelle in FILTRES_LIBELLES.items()
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Procédures collectives BODACC des commerces du centre-ville.",
        epilog=f"Formats de date : {FORMATS_AIDE}. Un mois ou une année seuls sont pris en entier.",
    )
    p.add_argument("--ville", default="Montpellier", help="Ville (défaut : Montpellier)")
    p.add_argument("--mois", type=int, default=MOIS_PAR_DEFAUT,
                   help="Nombre de mois à remonter depuis la fin (défaut : 6). Ignoré si --debut est donné.")
    p.add_argument("--debut", help="Début de la période, ex. 2025, 03/2025, 15/03/2025")
    p.add_argument("--fin", help="Fin de la période, incluse (défaut : aujourd'hui)")
    p.add_argument("--annonces", action="append", default=[], metavar="TYPES", help=AIDE_ANNONCES)
    p.add_argument("--sortie", type=Path, help="Chemin du fichier Excel à produire")
    p.add_argument("-v", "--verbeux", action="store_true", help="Afficher le détail des étapes")
    args = p.parse_args(argv)
    if args.mois < 1:
        p.error("--mois doit être au moins 1")
    try:
        args.fin = lire_date(args.fin, fin_de_periode=True) if args.fin else date.today()
        args.debut = lire_date(args.debut) if args.debut else mois_avant(args.fin, args.mois)
        args.types = types_pour_filtres(args.annonces)
    except ValueError as exc:
        p.error(str(exc))
    if args.debut > args.fin:
        p.error(f"La période commence ({args.debut:%d/%m/%Y}) après sa fin ({args.fin:%d/%m/%Y}).")
    args.filtre = ", ".join(sorted({c.strip().lower() for f in args.annonces for c in f.split(",") if c.strip()}))
    return args


def nom_fichier(ville: str, debut: date, fin: date, filtre: str) -> str:
    suffixe = f"_{filtre.replace(', ', '-')}" if filtre else ""
    return f"BODACC_procedures_collectives_centre-ville_{ville}_{debut}_{fin}{suffixe}.xlsx"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    logging.basicConfig(level=logging.DEBUG if args.verbeux else logging.INFO, format="%(message)s")
    log = logging.getLogger("veille")
    log.info("Période : du %s au %s — annonces : %s", f"{args.debut:%d/%m/%Y}", f"{args.fin:%d/%m/%Y}",
             args.filtre or "toutes")
    sortie = args.sortie or DOSSIER_SORTIE / nom_fichier(args.ville, args.debut, args.fin, args.filtre)
    try:
        rapport = run(args.ville, args.debut, args.fin, CACHE, args.types, args.filtre)
    except (SourceIndisponible, ValueError) as exc:
        log.error("Recherche impossible : %s", exc)
        return 1
    write_excel(rapport, sortie)
    log.info("%d commerces (%d annonces). Fichier : %s", len(rapport.commerces), len(rapport.retenus), sortie)
    return 0


if __name__ == "__main__":
    sys.exit(main())
