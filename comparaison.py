"""Comparaison entre villes : séries mensuelles BODACC agrégées, ramenées à la population."""
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date

import pandas as pd

from http_client import SourceIndisponible, get_json

log = logging.getLogger(__name__)

BODACC_AGREGATS_URL = (
    "https://bodacc-datadila.opendatasoft.com/api/explore/v2.1/"
    "catalog/datasets/annonces-commerciales/exports/json"
)
COMMUNES_URL = "https://geo.api.gouv.fr/communes"

FAMILLES = {
    "ouverture": "Défaillances (ouvertures de procédure)",
    "collective": "Procédures collectives (toutes annonces)",
    "creation": "Créations",
    "radiation": "Radiations",
}
FAMILLES_BODACC = ("collective", "creation", "radiation")
PAR_HABITANTS = 10_000
COL_EVOLUTION = "Évolution des défaillances sur 12 mois (%)"

# Estimation « commerces » : mots-clés recherchés dans l'activité déclarée
MOTS_COMMERCE = (
    "restauration", "restaurant", "boissons", "bar", "boulangerie", "pâtisserie", "coiffure", "coiffeur",
    "beauté", "esthétique", "épicerie", "alimentation", "boutique", "prêt-à-porter", "vêtements", "chaussures",
    "fleuriste", "fleurs", "hôtel", "snack", "traiteur", "pizzeria", "librairie", "bijouterie", "opticien",
    "caviste", "fromagerie", "boucherie", "commerce de détail", "vente au détail",
)
MOTS_EXCLUS = ("internet", "ligne", "distance")  # vente en ligne : pas un commerce de centre-ville

PERIMETRE_TOUT = "Toutes activités"
PERIMETRE_COMMERCES = "Commerces (estimation par mots-clés)"


@dataclass(frozen=True)
class Commune:
    nom: str
    code_insee: str
    departement: str
    population: int
    codes_postaux: tuple[str, ...]


def chercher_commune(nom: str) -> Commune:
    """Commune la plus peuplée portant ce nom (API Découpage administratif)."""
    resultats = get_json(COMMUNES_URL, params={
        "nom": nom, "fields": "nom,code,codeDepartement,population,codesPostaux", "boost": "population", "limit": "1",
    })
    if not resultats:
        raise ValueError(f"Commune introuvable : {nom}")
    r = resultats[0]
    return Commune(r["nom"], r["code"], r.get("codeDepartement", ""), int(r.get("population") or 0),
                   tuple(r.get("codesPostaux") or ()))


def _texte_odsql(valeur: str) -> str:
    return '"' + valeur.replace('"', "") + '"'


def clause_commune(c: Commune) -> str:
    """Filtre BODACC d'une commune : ses codes postaux ET son nom (exclut les voisines homonymes)."""
    if not c.codes_postaux:
        raise ValueError(f"Aucun code postal connu pour {c.nom}")
    cps = " OR ".join(f"cp like '{cp}*'" for cp in c.codes_postaux if re.fullmatch(r"\d{5}", cp))
    return f"({cps}) AND search(ville, {_texte_odsql(c.nom)})"


def clause_commerces() -> str:
    champs = ("listepersonnes", "listeetablissements")
    inclus = " OR ".join(f"search({f}, {_texte_odsql(m)})" for m in MOTS_COMMERCE for f in champs)
    exclus = " OR ".join(f"search(listeetablissements, {_texte_odsql(m)})" for m in MOTS_EXCLUS)
    return f"({inclus}) AND NOT ({exclus})"


def series_commune(c: Commune, debut: date, fin: date, perimetre: str = PERIMETRE_TOUT) -> pd.DataFrame:
    """Nombre d'annonces par mois et par famille (procédures collectives, créations, radiations)."""
    familles = ", ".join(f"'{f}'" for f in FAMILLES_BODACC)
    base = (f"{clause_commune(c)} AND dateparution >= '{debut.isoformat()}' "
            f"AND dateparution <= '{fin.isoformat()}'")
    if perimetre == PERIMETRE_COMMERCES:
        base += f" AND {clause_commerces()}"
    requetes = [
        (f"{base} AND familleavis in ({familles})", "date_format(dateparution, 'yyyy-MM') as mois, familleavis"),
        # Défaillances : seuls les jugements d'ouverture (redressement, liquidation, sauvegarde)
        (f"{base} AND familleavis = 'collective' AND search(jugement, 'ouverture')",
         "date_format(dateparution, 'yyyy-MM') as mois"),
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        par_famille, ouvertures = pool.map(lambda r: _agreger(*r), requetes)
    ouvertures = ouvertures.assign(familleavis="ouverture")
    df = pd.concat([par_famille, ouvertures], ignore_index=True)
    log.info("%s : %d lignes agrégées", c.nom, len(df))
    return df.assign(ville=c.nom)


@dataclass(frozen=True)
class DonneesVille:
    demande: str
    commune: Commune | None
    series: pd.DataFrame | None
    erreur: str = ""


def charger_villes(noms: tuple[str, ...], debut: date, fin: date,
                   perimetre: str = PERIMETRE_TOUT) -> list[DonneesVille]:
    """Interroge toutes les villes en parallèle ; une ville en erreur n'empêche pas les autres."""
    def une(nom: str) -> DonneesVille:
        try:
            c = chercher_commune(nom)
            return DonneesVille(nom, c, series_commune(c, debut, fin, perimetre))
        except (SourceIndisponible, ValueError) as exc:
            return DonneesVille(nom, None, None, str(exc))

    if not noms:
        return []
    with ThreadPoolExecutor(max_workers=min(6, len(noms))) as pool:
        return list(pool.map(une, noms))


def _agreger(where: str, group_by: str) -> pd.DataFrame:
    rows = get_json(BODACC_AGREGATS_URL, params={"select": "count(*) as n", "group_by": group_by, "where": where})
    colonnes = ["mois", "familleavis", "n"] if "familleavis" in group_by else ["mois", "n"]
    return pd.DataFrame(rows, columns=colonnes)


def completer_mois(df: pd.DataFrame, debut: date, fin: date) -> pd.DataFrame:
    """Une ligne par ville × mois avec une colonne par famille ; les mois sans annonce valent 0."""
    mois = pd.period_range(debut, fin, freq="M").to_timestamp()
    villes = sorted(df["ville"].unique()) if not df.empty else []
    base = pd.MultiIndex.from_product([villes, mois], names=["ville", "mois"]).to_frame(index=False)
    if df.empty:
        return base.assign(**{f: 0 for f in FAMILLES})
    d = df.assign(mois=pd.to_datetime(df["mois"]).dt.to_period("M").dt.to_timestamp())
    large = d.pivot_table(index=["ville", "mois"], columns="familleavis", values="n", aggfunc="sum").reset_index()
    out = base.merge(large, on=["ville", "mois"], how="left")
    for f in FAMILLES:
        out[f] = out.get(f, 0)
    return out.fillna({f: 0 for f in FAMILLES}).astype({f: int for f in FAMILLES})


def indicateur(large: pd.DataFrame, populations: dict[str, int], mesure: str,
               par_habitants: bool, lissage_mois: int) -> pd.DataFrame:
    """Série ville × mois de la mesure demandée, éventuellement pour 10 000 hab. et lissée."""
    d = large.sort_values(["ville", "mois"]).copy()
    if mesure == "ratio":
        fenetre = max(lissage_mois, 1)
        num = d.groupby("ville")["creation"].transform(lambda s: s.rolling(fenetre, min_periods=1).sum())
        den = d.groupby("ville")["ouverture"].transform(lambda s: s.rolling(fenetre, min_periods=1).sum())
        d["valeur"] = (num / den.where(den > 0)).round(2)
        return d[["ville", "mois", "valeur"]]
    d["valeur"] = d[mesure].astype(float)
    if par_habitants:
        d["valeur"] = d["valeur"] * PAR_HABITANTS / d["ville"].map(populations)
    if lissage_mois > 1:
        d["valeur"] = d.groupby("ville")["valeur"].transform(lambda s: s.rolling(lissage_mois, min_periods=1).mean())
    return d[["ville", "mois", "valeur"]]


def synthese(large: pd.DataFrame, populations: dict[str, int]) -> pd.DataFrame:
    """Totaux par ville, taux pour 10 000 habitants et évolution sur 12 mois glissants."""
    lignes = []
    for ville, g in large.sort_values("mois").groupby("ville"):
        pop = populations.get(ville) or 0
        tot = {f: int(g[f].sum()) for f in FAMILLES}
        der, avant = g.tail(12), g.iloc[-24:-12] if len(g) >= 24 else g.iloc[0:0]
        evol = ((der["ouverture"].sum() / avant["ouverture"].sum() - 1) * 100
                if len(avant) == 12 and avant["ouverture"].sum() else None)
        lignes.append({
            "Ville": ville, "Population": pop,
            "Défaillances": tot["ouverture"], "Créations": tot["creation"], "Radiations": tot["radiation"],
            "Défaillances / 10 000 hab.": round(tot["ouverture"] * PAR_HABITANTS / pop, 1) if pop else None,
            "Créations / 10 000 hab.": round(tot["creation"] * PAR_HABITANTS / pop, 1) if pop else None,
            "Créations pour 1 défaillance": round(tot["creation"] / tot["ouverture"], 2) if tot["ouverture"] else None,
            COL_EVOLUTION: round(evol, 1) if evol is not None else None,
        })
    return pd.DataFrame(lignes).sort_values("Défaillances / 10 000 hab.", ascending=False, na_position="last")


def attribuer_couleurs(villes: list[str], deja: dict[str, str], palette: tuple[str, ...],
                       reservee: tuple[str, str] | None = None) -> dict[str, str]:
    """Couleur stable par ville : une ville garde sa couleur quand on en ajoute ou retire d'autres."""
    couleurs = dict(deja)
    if reservee:
        couleurs[reservee[0]] = reservee[1]
    libres = [c for c in palette if c not in couleurs.values()]
    for v in villes:
        if v not in couleurs and libres:
            couleurs[v] = libres.pop(0)
    return couleurs
