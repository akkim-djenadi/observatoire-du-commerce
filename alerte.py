"""Alerte hebdomadaire : commerces du centre-ville placés en redressement ou en sauvegarde.

Exemples :
    python3 alerte.py                       # les 7 derniers jours
    python3 alerte.py --depuis 2026-11-01   # depuis le 1er novembre
    python3 alerte.py --sec                 # affiche aussi l'alerte à l'écran

S'il y a au moins un commerce, l'alerte est écrite en Markdown dans alerte.md
(le workflow GitHub en fait un ticket). Sinon rien n'est écrit et le code retour vaut 0.
"""
import argparse
import logging
import re
import sys
from collections.abc import Sequence
from datetime import date, timedelta
from pathlib import Path

import classify
from config import ZONE_ORDER
from fiche_aide import CONTACTS_AIDE, FicheAide, Intervenant, extraire_fiche
from http_client import SourceIndisponible
from pipeline import Resultat, run

ICI = Path(__file__).resolve().parent
CACHE = ICI / "cache" / "entreprises.json"
SORTIE = ICI / "alerte.md"
VILLE = "Montpellier"
JOURS_PAR_DEFAUT = 7
FILTRES = ["redressement", "sauvegarde"]
TYPES_ALERTE = classify.types_pour_filtres(FILTRES)

log = logging.getLogger("alerte")

_MD_SPECIAUX = re.compile(r"([\\`*_\[\]<>#|~])")


def _md(texte: str) -> str:
    """Texte BODACC sûr en Markdown : caractères spéciaux échappés, pas de mention @."""
    return _MD_SPECIAUX.sub(r"\\\1", texte).replace("@", "@​")


def _jjmmaaaa(iso: str) -> str:
    try:
        return f"{date.fromisoformat(iso):%d/%m/%Y}"
    except ValueError:
        return iso


def est_ouverture(r: Resultat) -> bool:
    """Jugement d'ouverture de redressement ou de sauvegarde (pas une liste de créances, ni un plan)."""
    return r.type_procedure in TYPES_ALERTE and r.annonce.nature.lower().startswith("jugement d'ouverture")


def _cle(r: Resultat) -> str:
    return r.annonce.siren or r.annonce.nom


def selectionner(resultats: Sequence[Resultat]) -> list[Resultat]:
    """Ouvertures à signaler, une par commerce (la plus récente), triées par zone puis par nom."""
    dernieres: dict[str, Resultat] = {}
    for r in sorted((r for r in resultats if est_ouverture(r)), key=lambda r: r.annonce.date_parution):
        dernieres[_cle(r)] = r
    return sorted(dernieres.values(), key=lambda r: (ZONE_ORDER.get(r.zone, 9), r.annonce.nom.lower()))


def _intervenant(role: str, i: Intervenant | None, precision: str = "") -> list[str]:
    if i is None:
        return []
    adresse = f" — {_md(i.adresse)}" if i.adresse else ""
    suite = f" (pouvoirs : {_md(precision)})" if precision else ""
    return [f"- **{role}** : {_md(i.nom)}{adresse}{suite}"]


def _estimation(date_limite: str, fin: date) -> str:
    if not date_limite:
        return ""
    if date_limite < fin.isoformat():
        return f" (soit vers le {_jjmmaaaa(date_limite)} : délai probablement écoulé)"
    return f" (soit vers le {_jjmmaaaa(date_limite)}, à vérifier)"


def _lignes_fiche(fiche: FicheAide, fin: date) -> list[str]:
    if fiche.est_vide:
        return ["- **Fiche d'aide** : le texte du jugement publié au BODACC ne précise pas les intervenants."]
    lignes = []
    if fiche.date_cessation:
        lignes.append(f"- **Cessation des paiements** : {_jjmmaaaa(fiche.date_cessation)}")
    lignes += _intervenant("Administrateur judiciaire", fiche.administrateur, fiche.pouvoirs_administrateur)
    lignes += _intervenant("Mandataire judiciaire", fiche.mandataire)
    if fiche.delai_creances:
        estimation = _estimation(fiche.date_limite_creances, fin)
        lignes.append(f"- **Déclaration des créances** : {_md(fiche.delai_creances)}{estimation}")
    return lignes


def _section(numero: int, r: Resultat, fin: date) -> list[str]:
    a = r.annonce
    enseigne = f" — enseigne « {_md(r.enseigne)} »" if r.enseigne and r.enseigne != a.nom else ""
    lignes = [
        f"## {numero}. {_md(a.nom or 'Nom non précisé')}{enseigne}",
        "",
        f"- **Activité** : {_md(r.activite or 'non précisée')}",
        f"- **Adresse** : {_md(r.adresse or 'non précisée')}",
        f"- **Zone** : {_md(r.zone)}",
        f"- **Procédure** : {_md(r.type_procedure)}",
        f"- **Date du jugement** : {_jjmmaaaa(a.date_jugement) or 'non précisée'}"
        + (f" (publié au BODACC le {_jjmmaaaa(a.date_parution)})" if a.date_parution else ""),
    ]
    if a.siren:
        lignes.append(f"- **SIREN** : {a.siren}")
    lignes += _lignes_fiche(extraire_fiche(a.complement, a.date_parution), fin)
    if a.url:
        lignes.append(f"- **Annonce BODACC** : [voir l'annonce officielle]({a.url})")
    return lignes + [""]


def _contacts() -> list[str]:
    lignes = ["## Contacts d'aide à proposer aux commerçants", ""]
    for c in CONTACTS_AIDE:
        lignes.append(f"- **{c.nom}** : {c.role} *{c.ou_trouver}*")
    return lignes + [""]


def rediger_alerte(resultats: Sequence[Resultat], debut: date, fin: date) -> str:
    """Alerte Markdown pour les commerces donnés (chaîne vide s'il n'y en a aucun)."""
    if not resultats:
        return ""
    periode = "Semaine" if (fin - debut).days < JOURS_PAR_DEFAUT else "Période"
    nombre = len(resultats)
    pluriel = "s" if nombre > 1 else ""
    lignes = [
        f"# Alerte commerces du centre-ville — {periode} du {debut:%d/%m/%Y} au {fin:%d/%m/%Y}",
        "",
        f"**{nombre} commerce{pluriel}** du centre-ville de {VILLE} placé{pluriel} en redressement "
        "judiciaire ou en procédure de sauvegarde (annonces publiées au BODACC sur la période).",
        "",
    ]
    for numero, r in enumerate(resultats, start=1):
        lignes += _section(numero, r, fin)
    lignes += _contacts()
    lignes += [
        "---",
        "*Alerte produite automatiquement par l'Observatoire du Commerce à partir des annonces publiques "
        "du BODACC. Les délais indiqués sont des estimations : seule la publication officielle fait foi. "
        "Ces informations ne remplacent pas un conseil juridique.*",
        "",
    ]
    return "\n".join(lignes)


def parse_args(argv: list[str], aujourd_hui: date) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Alerte : commerces du centre-ville en redressement ou en sauvegarde.")
    p.add_argument("--depuis", metavar="AAAA-MM-JJ",
                   help=f"Début de la période (défaut : les {JOURS_PAR_DEFAUT} derniers jours)")
    p.add_argument("--sec", action="store_true", help="Afficher aussi l'alerte sur la sortie standard")
    p.add_argument("--sortie", type=Path, default=SORTIE, help="Fichier Markdown produit (défaut : alerte.md)")
    args = p.parse_args(argv)
    args.fin = aujourd_hui
    try:
        args.debut = (date.fromisoformat(args.depuis) if args.depuis
                      else aujourd_hui - timedelta(days=JOURS_PAR_DEFAUT - 1))
    except ValueError:
        p.error(f"Date invalide pour --depuis : {args.depuis!r} (format attendu : AAAA-MM-JJ)")
    if args.debut > args.fin:
        p.error(f"--depuis ({args.debut:%d/%m/%Y}) est postérieur à aujourd'hui.")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv, date.today())
    logging.basicConfig(level=logging.INFO, format="%(message)s")  # sur stderr : stdout reste au Markdown
    log.info("Alerte : du %s au %s", f"{args.debut:%d/%m/%Y}", f"{args.fin:%d/%m/%Y}")
    try:
        rapport = run(VILLE, args.debut, args.fin, CACHE, TYPES_ALERTE, ", ".join(FILTRES))
    except (SourceIndisponible, ValueError) as exc:
        log.error("Recherche impossible : %s", exc)
        return 1
    choisis = selectionner(rapport.retenus)
    if not choisis:
        if args.sortie.exists():
            args.sortie.unlink()  # ne pas republier l'alerte d'une semaine précédente
        log.info("Aucun commerce du centre-ville en redressement ou en sauvegarde : rien à signaler.")
        return 0
    texte = rediger_alerte(choisis, args.debut, args.fin)
    args.sortie.write_text(texte, encoding="utf-8")
    log.info("%d commerce(s) signalé(s). Fichier : %s", len(choisis), args.sortie)
    if args.sec:
        sys.stdout.write(texte)
    return 0


if __name__ == "__main__":
    sys.exit(main())
