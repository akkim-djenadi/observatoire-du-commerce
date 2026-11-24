"""Géolocalisation des adresses (Base Adresse Nationale) et découpage en zones."""
import csv
import io
import logging
import math
import re
from typing import NamedTuple

from config import (
    COMEDIE, ECUSSON_POLYGON, ECUSSON_STREETS_RE, FAUBOURGS_MAX_M, GEOCODE_CSV_URL,
    HYPERCENTRE_MAX_M, HYPERCENTRE_RE, MIN_GEOCODE_SCORE, STREET_OVERRIDE_MAX_M,
    ZONE_ECUSSON, ZONE_FAUBOURGS, ZONE_HORS_CENTRE, ZONE_HYPERCENTRE,
)
from http_client import post_csv

log = logging.getLogger(__name__)

EARTH_M_PER_DEG = 111_195


class Point(NamedTuple):
    lat: float
    lon: float


class Zonage(NamedTuple):
    zone: str
    distance_m: int | None


def distance_m(a: Point, b: Point) -> float:
    dy = (a.lat - b.lat) * EARTH_M_PER_DEG
    dx = (a.lon - b.lon) * EARTH_M_PER_DEG * math.cos(math.radians(a.lat))
    return math.hypot(dx, dy)


def inside_polygon(p: Point, polygon: tuple[tuple[float, float], ...]) -> bool:
    inside = False
    n = len(polygon)
    for i in range(n):
        (y1, x1), (y2, x2) = polygon[i], polygon[(i + 1) % n]
        if (y1 > p.lat) != (y2 > p.lat) and p.lon < (x2 - x1) * (p.lat - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def classify_zone(point: Point | None, adresse: str) -> Zonage:
    """Zone du centre-ville à partir des coordonnées, corrigée par le nom de la rue."""
    dist = round(distance_m(point, Point(*COMEDIE))) if point else None
    if point is None:
        zone = ZONE_HORS_CENTRE
    elif inside_polygon(point, ECUSSON_POLYGON):
        zone = ZONE_ECUSSON
    elif dist <= HYPERCENTRE_MAX_M:
        zone = ZONE_HYPERCENTRE
    elif dist <= FAUBOURGS_MAX_M:
        zone = ZONE_FAUBOURGS
    else:
        zone = ZONE_HORS_CENTRE
    if HYPERCENTRE_RE.search(adresse):
        zone = ZONE_HYPERCENTRE
    if ECUSSON_STREETS_RE.search(adresse) and (dist is None or dist < STREET_OVERRIDE_MAX_M):
        zone = ZONE_ECUSSON
    return Zonage(zone, dist)


def _clean(adresse: str) -> tuple[str, str]:
    cp = re.search(r"\b(\d{5})\b", adresse)
    voie = re.sub(r"\b\d{5}\b.*", "", adresse).strip()
    return voie, cp.group(1) if cp else ""


def geocode(adresses: dict[str, str], ville: str) -> dict[str, Point]:
    """Géolocalise un lot d'adresses {identifiant: adresse} en une seule requête."""
    if not adresses:
        return {}
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "adresse", "postcode", "city"])
    for key, adresse in adresses.items():
        voie, cp = _clean(adresse)
        writer.writerow([key, voie, cp, ville])
    text = post_csv(GEOCODE_CSV_URL, buf.getvalue().encode("utf-8"),
                    {"columns": "adresse", "postcode": "postcode"})
    points: dict[str, Point] = {}
    for row in csv.DictReader(io.StringIO(text)):
        try:
            if float(row.get("result_score") or 0) >= MIN_GEOCODE_SCORE:
                points[row["id"]] = Point(float(row["latitude"]), float(row["longitude"]))
        except (KeyError, ValueError):
            continue
    log.info("Géolocalisation : %d/%d adresses fiables", len(points), len(adresses))
    return points
