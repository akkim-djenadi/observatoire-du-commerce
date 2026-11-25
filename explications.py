"""Explications en langage simple pour la page « Comparer les villes ».

Deux parties : une lecture automatique des chiffres affichés, et des textes fixes
(glossaire, mode d'emploi, pièges à éviter).
"""
import math
from dataclasses import dataclass

import pandas as pd

from comparaison import COL_EVOLUTION, PAR_HABITANTS

COL_TAUX = "Défaillances / 10 000 hab."
COL_RATIO = "Créations pour 1 défaillance"
SEUIL_ECART_NOTABLE = 5.0      # en %, sous ce seuil on parle de « niveau proche »
SEUIL_EVOLUTION_STABLE = 3.0   # en %, sous ce seuil on parle de stabilité


def nombre(x: float, decimales: int = 0) -> str:
    """Nombre à la française : virgule décimale, espace insécable pour les milliers."""
    texte = f"{x:,.{decimales}f}".replace(",", " ").replace(".", ",")
    return texte.replace(" ", " ")


def _valide(x) -> bool:
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def _ecart_pct(valeur: float, reference: float) -> float:
    return (valeur / reference - 1) * 100


def phrase_taux(ville: str, ligne: pd.Series, autres: pd.DataFrame) -> str:
    taux = ligne[COL_TAUX]
    base = (f"À **{ville}**, sur la période, **{nombre(taux, 1)} entreprises sur 10 000 habitants** ont connu "
            f"une défaillance (redressement, sauvegarde ou liquidation)")
    taux_autres = autres[COL_TAUX].dropna()
    if taux_autres.empty:
        return base + "."
    moyenne = taux_autres.mean()
    ecart = _ecart_pct(taux, moyenne)
    if abs(ecart) < SEUIL_ECART_NOTABLE:
        return base + f", un niveau proche de la moyenne des autres villes ({nombre(moyenne, 1)})."
    sens = "de plus" if ecart > 0 else "de moins"
    return base + f", soit **{nombre(abs(ecart))} % {sens}** que la moyenne des autres villes ({nombre(moyenne, 1)})."


def phrase_ratio(ville: str, ligne: pd.Series, synth: pd.DataFrame) -> str | None:
    ratio = ligne[COL_RATIO]
    if not _valide(ratio):
        return None
    texte = (f"Pour **1 entreprise en difficulté**, **{nombre(ratio, 1)} entreprises ont été créées** à {ville}. "
             f"{'Le tissu économique se renouvelle : il naît plus d’entreprises qu’il n’en tombe en difficulté.' if ratio >= 1 else 'Attention : il y a plus de défaillances que de créations.'}")
    classement = synth.dropna(subset=[COL_RATIO]).sort_values(COL_RATIO, ascending=False)["Ville"].tolist()
    if len(classement) > 1:
        rang = classement.index(ville) + 1
        if rang == 1:
            texte += " C'est **le meilleur renouvellement** des villes comparées."
        elif rang == len(classement):
            texte += " C'est **le renouvellement le plus faible** des villes comparées."
        else:
            texte += f" {ville} se classe **{rang}e sur {len(classement)}**."
    return texte


def phrase_evolution(ville: str, ligne: pd.Series, synth: pd.DataFrame) -> str | None:
    evol = ligne[COL_EVOLUTION]
    if not _valide(evol):
        return None
    if abs(evol) < SEUIL_EVOLUTION_STABLE:
        texte = f"Sur les 12 derniers mois, les défaillances sont **stables** à {ville} ({evol:+.1f} %)."
    else:
        sens = "augmenté" if evol > 0 else "baissé"
        texte = (f"Sur les 12 derniers mois, les défaillances ont **{sens} de {nombre(abs(evol))} %** à {ville} "
                 f"par rapport aux 12 mois précédents.")
    autres = synth[(synth["Ville"] != ville)].dropna(subset=[COL_EVOLUTION])
    if not autres.empty:
        hausse = autres[autres[COL_EVOLUTION] >= SEUIL_EVOLUTION_STABLE]["Ville"].tolist()
        baisse = autres[autres[COL_EVOLUTION] <= -SEUIL_EVOLUTION_STABLE]["Ville"].tolist()
        morceaux = []
        if hausse:
            morceaux.append(f"en hausse à {_liste(hausse)}")
        if baisse:
            morceaux.append(f"en baisse à {_liste(baisse)}")
        if morceaux:
            texte += " Ailleurs, elles sont " + " et ".join(morceaux) + "."
    return texte


def phrase_taille(synth: pd.DataFrame) -> str | None:
    """Rappelle pourquoi on divise par la population, avec la plus grande et la plus petite ville."""
    s = synth.dropna(subset=[COL_TAUX]).sort_values("Population", ascending=False)
    if len(s) < 2:
        return None
    grande, petite = s.iloc[0], s.iloc[-1]
    return (f"En nombre brut, {grande['Ville']} compte {nombre(grande['Défaillances'])} défaillances et "
            f"{petite['Ville']} {nombre(petite['Défaillances'])}. Mais {grande['Ville']} a "
            f"{nombre(grande['Population'] / petite['Population'], 1)} fois plus d'habitants : c'est pourquoi on compare "
            f"des taux **pour 10 000 habitants**, et non des nombres bruts.")


def _liste(villes: list[str]) -> str:
    return villes[0] if len(villes) == 1 else ", ".join(villes[:-1]) + " et " + villes[-1]


def lecture_simple(synth: pd.DataFrame, reference: str) -> list[str]:
    """Trois à quatre phrases qui résument la comparaison pour la ville de référence."""
    lignes = synth[synth["Ville"] == reference]
    if lignes.empty or not _valide(lignes.iloc[0][COL_TAUX]):
        return []
    ligne = lignes.iloc[0]
    autres = synth[synth["Ville"] != reference]
    phrases = [phrase_taux(reference, ligne, autres), phrase_ratio(reference, ligne, synth),
               phrase_evolution(reference, ligne, synth), phrase_taille(synth)]
    return [p for p in phrases if p]


@dataclass(frozen=True)
class ExempleCalcul:
    ville: str
    defaillances: int
    population: int
    taux: float


def exemple_calcul(synth: pd.DataFrame, reference: str) -> ExempleCalcul | None:
    lignes = synth[synth["Ville"] == reference]
    if lignes.empty or not lignes.iloc[0]["Population"]:
        return None
    l = lignes.iloc[0]
    return ExempleCalcul(reference, int(l["Défaillances"]), int(l["Population"]),
                         l["Défaillances"] * PAR_HABITANTS / l["Population"])


# --- Textes fixes ---------------------------------------------------------------

GLOSSAIRE = [
    ("BODACC", "Le Bulletin officiel des annonces civiles et commerciales. Chaque fois qu'un tribunal prend une "
               "décision sur une entreprise (difficultés, fermeture, vente…), elle y est publiée. C'est la source "
               "officielle et gratuite de tous les chiffres de cette page."),
    ("Défaillance", "Une entreprise qui ne peut plus payer ses dettes et pour laquelle le tribunal ouvre une "
                    "procédure. Ce n'est pas forcément une fermeture : beaucoup d'entreprises s'en sortent."),
    ("Sauvegarde", "Le chef d'entreprise anticipe : il demande lui-même la protection du tribunal **avant** de ne plus "
                   "pouvoir payer. C'est la procédure la plus précoce, et souvent la plus efficace."),
    ("Redressement judiciaire", "L'entreprise ne peut plus payer, mais elle peut encore être sauvée. Elle continue de "
                                "travailler pendant que le tribunal cherche une solution (étalement des dettes, reprise…)."),
    ("Liquidation judiciaire", "Le sauvetage n'est pas possible : l'activité s'arrête et les biens sont vendus pour "
                               "rembourser ce qui peut l'être."),
    ("Création", "Une nouvelle entreprise immatriculée et publiée au BODACC : un commerce qui ouvre, un artisan qui "
                 "s'installe, une société qui se crée."),
    ("Radiation", "Une entreprise qui disparaît du registre. Ce n'est pas toujours un échec : départ à la retraite, "
                  "déménagement, fusion, fin volontaire d'activité."),
]

COMMENT_LIRE = [
    "**Chaque courbe est une ville.** Montpellier est toujours en terracotta, le trait le plus épais.",
    "**L'axe horizontal, c'est le temps**, mois par mois. **L'axe vertical, c'est la valeur** de l'indicateur choisi.",
    "**Plus la courbe des défaillances est haute, plus il y a d'entreprises en difficulté** par rapport à la population.",
    "**Pour la courbe de dynamisme, c'est l'inverse : plus elle est haute, mieux c'est** (beaucoup de créations pour "
    "peu de défaillances).",
    "**Passez la souris sur le graphique** pour lire les valeurs exactes de toutes les villes à un mois donné.",
    "**Le lissage** remplace chaque mois par la moyenne des derniers mois : la courbe montre la tendance au lieu des "
    "à-coups d'un mois sur l'autre.",
]

PIEGES = [
    ("Comparer des nombres bruts", "Une grande ville a mécaniquement plus de défaillances qu'une petite. "
                                   "Gardez l'option « Pour 10 000 habitants » activée pour comparer des villes."),
    ("Surinterpréter un seul mois", "Les tribunaux tournent au ralenti en août et pendant les fêtes : un creux ce "
                                    "mois-là ne veut pas dire que tout va mieux. Regardez la tendance, avec le lissage "
                                    "sur 3 ou 12 mois."),
    ("Confondre défaillance et fermeture", "Une partie des entreprises en sauvegarde ou en redressement continue son "
                                           "activité. Le nombre de défaillances n'est pas un nombre de rideaux baissés."),
    ("Prendre le périmètre « Commerces » pour un décompte exact", "Il repose sur des mots-clés dans l'activité "
                                                                 "déclarée. Il est fiable pour comparer des villes "
                                                                 "entre elles, pas pour compter au commerce près."),
    ("Oublier le décalage de publication", "Une annonce paraît au BODACC quelques jours à quelques semaines après le "
                                           "jugement. Les derniers mois peuvent encore légèrement augmenter."),
]

FAQ = [
    ("D'où viennent les chiffres ?", "Du BODACC, publié par l'État et diffusé sur data.gouv.fr, et de la population "
                                     "INSEE la plus récente. Le BODACC paraît plusieurs fois par semaine, et la page "
                                     "interroge les données à jour à chaque recherche."),
    ("Pourquoi la ville entière et pas seulement le centre-ville ?", "Pour comparer des villes entre elles, il faut "
     "la même règle partout. Le détail du centre-ville de Montpellier est sur la page « Centre-ville »."),
    ("Un chiffre en hausse, est-ce forcément mauvais ?", "Pour les défaillances, oui, c'est un signal d'alerte. Pour "
     "les créations, c'est plutôt bon signe. Pour les radiations, il faut regarder en même temps les créations : "
     "beaucoup de départs compensés par beaucoup d'arrivées, c'est un tissu qui se renouvelle."),
]
