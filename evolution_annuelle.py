"""Taux d'évolution d'une année sur l'autre, à période comparable.

Chaque année de la période est comparée à la même fenêtre de l'année précédente : une année
en cours (janvier → octobre) est comparée à janvier → octobre de l'année d'avant, jamais à
une année entière. Sans données pour l'année précédente, l'évolution reste inconnue.
"""
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date

import pandas as pd

Compteur = Callable[[date, date], float | None]


@dataclass(frozen=True)
class LigneAnnee:
    annee: int
    debut: date
    fin: date
    valeur: float | None
    precedent: float | None        # même fenêtre, un an plus tôt (None si hors des données)
    evolution_pct: float | None    # None si l'année précédente est inconnue ou vaut 0

    @property
    def partielle(self) -> bool:
        return (self.debut, self.fin) != (date(self.annee, 1, 1), date(self.annee, 12, 31))

    @property
    def libelle(self) -> str:
        if not self.partielle:
            return str(self.annee)
        return f"{self.annee} (du {self.debut:%d/%m} au {self.fin:%d/%m})"


def en_annee(jour: date, annee: int) -> date:
    """Même jour et même mois une autre année (le 29 février devient le 28)."""
    try:
        return jour.replace(year=annee)
    except ValueError:
        return jour.replace(year=annee, day=28)


def un_an_avant(jour: date) -> date:
    """Même jour l'année précédente (le 29 février devient le 28)."""
    return en_annee(jour, jour.year - 1)


def taux_evolution(valeur: float | None, precedent: float | None) -> float | None:
    if valeur is None or not precedent:
        return None
    return round((valeur / precedent - 1) * 100, 1)


def evolution_annuelle(compter: Compteur, debut: date, fin: date) -> list[LigneAnnee]:
    """Une ligne par année entre `debut` et `fin` (inclus), comparée à la même fenêtre un an plus tôt."""
    if debut > fin:
        raise ValueError("La période commence après sa fin.")
    lignes = []
    for annee in range(debut.year, fin.year + 1):
        d, f = max(debut, date(annee, 1, 1)), min(fin, date(annee, 12, 31))
        valeur = compter(d, f)
        avant = un_an_avant(d)
        precedent = compter(avant, un_an_avant(f)) if avant >= debut else None
        lignes.append(LigneAnnee(annee, d, f, valeur, precedent, taux_evolution(valeur, precedent)))
    return lignes


def compteur_dates(dates: Iterable[date]) -> Compteur:
    """Nombre d'événements datés tombant dans la fenêtre [a, b]."""
    jours = sorted(dates)
    return lambda a, b: float(sum(1 for j in jours if a <= j <= b))


def compteur_mensuel(serie: pd.Series) -> Compteur:
    """Somme des mois (index = premier jour du mois) dont le début tombe dans la fenêtre [a, b]."""
    index = pd.to_datetime(serie.index)

    def compter(a: date, b: date) -> float:
        masque = (index >= pd.Timestamp(a)) & (index <= pd.Timestamp(b))
        return float(serie[masque].sum())
    return compter


def compteur_ratio(numerateur: Compteur, denominateur: Compteur) -> Compteur:
    """Rapport de deux compteurs sur la même fenêtre (None si le dénominateur vaut 0)."""
    def compter(a: date, b: date) -> float | None:
        bas = denominateur(a, b)
        haut = numerateur(a, b)
        return round(haut / bas, 2) if bas and haut is not None else None
    return compter


@dataclass(frozen=True)
class ComparaisonAnnees:
    """Une année comparée à une autre, sur les mêmes jours de l'année."""
    depart: int
    arrivee: int
    debut: date                    # fenêtre dans l'année d'arrivée ; la même dans l'année de départ
    fin: date
    valeur_depart: float | None
    valeur_arrivee: float | None
    evolution_pct: float | None    # de l'année de départ à l'année d'arrivée

    @property
    def annee_entiere(self) -> bool:
        return (self.debut.month, self.debut.day, self.fin.month, self.fin.day) == (1, 1, 12, 31)

    @property
    def fenetre(self) -> str:
        return "année entière" if self.annee_entiere else f"du {self.debut:%d/%m} au {self.fin:%d/%m}"


def _fenetre_annee(debut: date, fin: date, annee: int) -> tuple[date, date]:
    if not debut.year <= annee <= fin.year:
        raise ValueError(f"L'année {annee} est hors de la période.")
    return max(debut, date(annee, 1, 1)), min(fin, date(annee, 12, 31))


def comparer_annees(compter: Compteur, debut: date, fin: date, depart: int,
                    arrivee: int) -> ComparaisonAnnees | None:
    """Compare deux années de la période sur les jours couverts par les deux (None s'il n'y en a aucun).

    Une année en cours (janvier → 28 novembre) est comparée à janvier → 28 novembre de l'autre année,
    jamais à une année entière, que l'autre année soit avant ou après.
    """
    fenetres = [_fenetre_annee(debut, fin, a) for a in (depart, arrivee)]
    premier = max((d.month, d.day) for d, _ in fenetres)
    dernier = min((f.month, f.day) for _, f in fenetres)
    if premier > dernier:
        return None

    def bornes(annee: int) -> tuple[date, date]:
        return en_annee(date(2000, *premier), annee), en_annee(date(2000, *dernier), annee)

    valeur_depart, valeur_arrivee = compter(*bornes(depart)), compter(*bornes(arrivee))
    return ComparaisonAnnees(depart, arrivee, *bornes(arrivee), valeur_depart, valeur_arrivee,
                             taux_evolution(valeur_arrivee, valeur_depart))
