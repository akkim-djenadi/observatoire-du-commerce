"""Collecte mensuelle des données de vitalité commerciale, enregistrées dans `data/`.

Lancée chaque mois par GitHub Actions (et à la main) :
    python3 collecte.py                       # tout : établissements, ventes de locaux, procédures, indice
    python3 collecte.py --etapes dvf,indice   # seulement certaines étapes
"""
import argparse
import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd

import dvf
import etablissements
from adresses import normaliser_voie
from config import CODE_COMMUNE, CODE_DEPARTEMENT, DVF_ANNEES, FERMETURES_MOIS, NAF_COMMERCE
from http_client import SourceIndisponible
from periode import mois_avant
from pipeline import Rapport, run

ICI = Path(__file__).resolve().parent
DATA = ICI / "data"
CACHE = ICI / "cache" / "entreprises.json"
PROCEDURES_MOIS = 24
ETAPES = ("etablissements", "dvf", "procedures", "indice")
FICHIERS = {
    "etablissements": DATA / "etablissements.csv",
    "dvf": DATA / "dvf_locaux.csv",
    "procedures": DATA / "procedures.csv",
    "indice": DATA / "indice_historique.csv",
}
META = DATA / "collecte.json"

log = logging.getLogger("collecte")


def procedures_tableau(rap: Rapport) -> pd.DataFrame:
    """Annonces du centre-ville (commerces), une ligne par annonce, avec la rue normalisée."""
    lignes = [{
        "id": r.annonce.id, "date_parution": r.annonce.date_parution, "date_jugement": r.annonce.date_jugement,
        "type": r.type_procedure, "nature": r.annonce.nature, "nom": r.annonce.nom, "siren": r.annonce.siren,
        "enseigne": r.enseigne, "activite": r.activite, "secteur": r.secteur, "adresse": r.adresse,
        "voie": normaliser_voie(r.adresse), "zone": r.zone, "latitude": r.latitude, "longitude": r.longitude,
        "complement": r.annonce.complement, "url": r.annonce.url,
    } for r in rap.retenus]
    return pd.DataFrame(lignes)


def etape_etablissements(aujourd_hui: date) -> pd.DataFrame:
    stock = etablissements.collecter(CODE_COMMUNE, NAF_COMMERCE, mois_avant(aujourd_hui, FERMETURES_MOIS))
    return etablissements.tableau(stock)


def etape_dvf(aujourd_hui: date) -> pd.DataFrame:
    annees = range(aujourd_hui.year - DVF_ANNEES, aujourd_hui.year + 1)
    return dvf.collecter(annees, CODE_DEPARTEMENT, CODE_COMMUNE)


def etape_procedures(aujourd_hui: date) -> pd.DataFrame:
    return procedures_tableau(run("Montpellier", mois_avant(aujourd_hui, PROCEDURES_MOIS), aujourd_hui, CACHE))


def etape_indice(aujourd_hui: date) -> pd.DataFrame:
    import indice  # import tardif : l'indice ne sert qu'à cette étape
    donnees = {nom: pd.read_csv(FICHIERS[nom], dtype=str) for nom in ("etablissements", "dvf", "procedures")}
    historique = pd.read_csv(FICHIERS["indice"], dtype=str) if FICHIERS["indice"].exists() else None
    return indice.mettre_a_jour_historique(historique, donnees, aujourd_hui)


def enregistrer(nom: str, tableau: pd.DataFrame, meta: dict) -> None:
    DATA.mkdir(exist_ok=True)
    tableau.to_csv(FICHIERS[nom], index=False)
    meta[nom] = {"lignes": len(tableau), "collecte": datetime.now().isoformat(timespec="seconds")}
    log.info("%s : %d lignes enregistrées dans %s", nom, len(tableau), FICHIERS[nom].relative_to(ICI))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Collecte mensuelle de l'Observatoire du Commerce.")
    p.add_argument("--etapes", default=",".join(ETAPES), help=f"Étapes à lancer, parmi : {', '.join(ETAPES)}")
    args = p.parse_args(sys.argv[1:] if argv is None else argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    etapes = [e.strip() for e in args.etapes.split(",") if e.strip()]
    inconnues = [e for e in etapes if e not in ETAPES]
    if inconnues:
        p.error(f"Étape inconnue : {', '.join(inconnues)}")
    meta = json.loads(META.read_text(encoding="utf-8")) if META.exists() else {}
    fonctions = {"etablissements": etape_etablissements, "dvf": etape_dvf,
                 "procedures": etape_procedures, "indice": etape_indice}
    aujourd_hui = date.today()
    echecs = []
    for etape in [e for e in ETAPES if e in etapes]:   # toujours dans l'ordre : l'indice vient en dernier
        log.info("— %s —", etape)
        try:
            enregistrer(etape, fonctions[etape](aujourd_hui), meta)
        except (SourceIndisponible, FileNotFoundError, ValueError) as exc:
            log.error("Étape %s impossible : %s (les données précédentes sont conservées)", etape, exc)
            echecs.append(etape)
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
