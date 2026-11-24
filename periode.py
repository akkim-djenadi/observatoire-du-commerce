"""Lecture souple des dates : jour, mois ou année entière."""
import calendar
import re
from datetime import date

FORMATS_AIDE = "AAAA-MM-JJ, JJ/MM/AAAA, AAAA-MM, MM/AAAA ou AAAA"

_JOUR_ISO = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
_JOUR_FR = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
_MOIS_ISO = re.compile(r"(\d{4})-(\d{1,2})")
_MOIS_FR = re.compile(r"(\d{1,2})/(\d{4})")
_ANNEE = re.compile(r"(\d{4})")


def lire_date(texte: str, fin_de_periode: bool = False) -> date:
    """Convertit « 2025 », « 03/2025 », « 2025-03 » ou « 15/03/2025 » en date.

    Un mois ou une année désigne leur premier jour, ou leur dernier jour
    quand `fin_de_periode` est vrai (borne de fin incluse).
    """
    t = texte.strip()
    try:
        if m := _JOUR_ISO.fullmatch(t):
            return date(int(m[1]), int(m[2]), int(m[3]))
        if m := _JOUR_FR.fullmatch(t):
            return date(int(m[3]), int(m[2]), int(m[1]))
        if m := _MOIS_ISO.fullmatch(t) or _MOIS_FR.fullmatch(t):
            annee, mois = (int(m[1]), int(m[2])) if "-" in t else (int(m[2]), int(m[1]))
            jour = calendar.monthrange(annee, mois)[1] if fin_de_periode else 1
            return date(annee, mois, jour)
        if m := _ANNEE.fullmatch(t):
            return date(int(m[1]), 12, 31) if fin_de_periode else date(int(m[1]), 1, 1)
    except ValueError as exc:
        raise ValueError(f"Date impossible : {texte!r} ({exc})") from exc
    raise ValueError(f"Format de date non reconnu : {texte!r}. Formats acceptés : {FORMATS_AIDE}")


def mois_avant(jour: date, mois: int) -> date:
    """Même jour, `mois` mois plus tôt (ramené à la fin du mois si besoin)."""
    total = jour.year * 12 + jour.month - 1 - mois
    annee, m = divmod(total, 12)
    dernier_jour = calendar.monthrange(annee, m + 1)[1]
    return date(annee, m + 1, min(jour.day, dernier_jour))
