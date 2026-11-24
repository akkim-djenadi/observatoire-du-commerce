"""Identité visuelle de l'Observatoire du Commerce dans l'application."""
from pathlib import Path

DOSSIER_LOGO = Path(__file__).resolve().parent / "assets" / "logo" / "final"
LOGO_SYMBOLE_PNG = DOSSIER_LOGO / "renders" / "observatoire-symbole-recadre.png"
FAVICON_PNG = DOSSIER_LOGO / "web" / "favicon-48.png"

# Symbole « Les Arcades » (même tracé que ocm-symbole.svg, recadré sur sa forme)
_SYMBOLE_SVG = (
    '<svg viewBox="0 0 184 160" width="34" height="30" aria-hidden="true" focusable="false">'
    '<path fill="#BB502E" d="M0 160V0H184V160H156V51A25 25 0 0 0 106 51V160H78V51A25 25 0 0 0 28 51V160Z"/>'
    "</svg>"
)

ENTETE = (
    '<div class="ocm-marque">'
    f"{_SYMBOLE_SVG}"
    '<span class="ocm-marque-nom">Observatoire<br><span>du Commerce</span></span>'
    "</div>"
)
