"""Vectorise le nom « Observatoire du Commerce » en Montserrat et compose les versions du logo.

Usage : python3 vectoriser_nom.py <police-variable.ttf> <dossier-final>
"""
import sys
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

SYMBOLE = "M0 160V0H184V160H156V51A25 25 0 0 0 106 51V160H78V51A25 25 0 0 0 28 51V160Z"
# Version inversée : piliers affinés d'une unité (une forme claire sur fond sombre paraît plus grasse)
SYMBOLE_INVERSE = "M0 160V0H184V160H157V51A26 26 0 0 0 105 51V160H79V51A26 26 0 0 0 27 51V160Z"
SYM_L, SYM_H, PILIER = 184, 160, 28
LIGNE1, LIGNE2 = "OBSERVATOIRE", "DU COMMERCE"
NOM = "Observatoire du Commerce"
PREFIXE = "observatoire"
HAUTEUR_CAPITALES = 38          # hauteur des capitales, en unités du logo
APPROCHE_LIGNE1 = 0.015         # interlettrage de la ligne 1, en fraction du corps
MARGE = 20
TERRACOTTA, ANTHRACITE, SABLE = "#BB502E", "#2B2B2B", "#F6ECE4"


def instance(chemin: str, graisse: int) -> TTFont:
    return instantiateVariableFont(TTFont(chemin), {"wght": graisse}, inplace=False)


def ligne(font: TTFont, texte: str, corps: float, approche: float) -> tuple[list[tuple[str, float]], float]:
    """Glyphes et position x de chacun ; renvoie aussi la largeur de la ligne (sans approche finale)."""
    cmap, hmtx = font.getBestCmap(), font["hmtx"]
    echelle = corps / font["head"].unitsPerEm
    x, glyphes = 0.0, []
    for i, car in enumerate(texte):
        nom = cmap[ord(car)]
        glyphes.append((nom, x))
        x += hmtx[nom][0] * echelle + (approche if i < len(texte) - 1 else 0)
    return glyphes, x


def tracer(font: TTFont, glyphes, corps: float, x0: float, ligne_base: float) -> str:
    gs = font.getGlyphSet()
    echelle = corps / font["head"].unitsPerEm
    morceaux = []
    for nom, x in glyphes:
        pen = SVGPathPen(gs)
        gs[nom].draw(TransformPen(pen, (echelle, 0, 0, -echelle, x0 + x, ligne_base)))
        morceaux.append(pen.getCommands())
    return " ".join(m for m in morceaux if m)


def composer(chemin_police: str) -> dict:
    gras, demi = instance(chemin_police, 800), instance(chemin_police, 600)
    corps = HAUTEUR_CAPITALES * gras["head"].unitsPerEm / gras["OS/2"].sCapHeight
    base = corps * APPROCHE_LIGNE1
    _, l1 = ligne(gras, LIGNE1, corps, base)
    _, l2 = ligne(demi, LIGNE2, corps, base)
    # Justification : la ligne la plus courte est espacée pour atteindre la largeur de l'autre
    cible = max(l1, l2)
    a1 = base + (cible - l1) / (len(LIGNE1) - 1)
    a2 = base + (cible - l2) / (len(LIGNE2) - 1)
    g1, l1 = ligne(gras, LIGNE1, corps, a1)
    g2, l2 = ligne(demi, LIGNE2, corps, a2)
    return {"gras": gras, "demi": demi, "corps": corps, "g1": g1, "g2": g2, "largeur": max(l1, l2)}


def svg(viewbox: str, corps_svg: str, titre: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}">\n'
            f"  <title>{titre}</title>\n{corps_svg}</svg>\n")


def horizontal(c: dict, couleur_symbole: str, couleur_texte: str, symbole: str = SYMBOLE) -> str:
    haut_bloc = MARGE + PILIER                                 # capitales de la ligne 1 alignées sous la marge + 1 pilier
    base1 = haut_bloc + HAUTEUR_CAPITALES
    base2 = base1 + PILIER + HAUTEUR_CAPITALES                 # interligne = largeur d'un pilier
    x_texte = MARGE + SYM_L + int(PILIER * 1.5)
    largeur = x_texte + c["largeur"] + MARGE
    d1 = tracer(c["gras"], c["g1"], c["corps"], x_texte, base1)
    d2 = tracer(c["demi"], c["g2"], c["corps"], x_texte, base2)
    corps_svg = (f'  <path fill="{couleur_symbole}" transform="translate({MARGE} {MARGE})" d="{symbole}"/>\n'
                 f'  <path fill="{couleur_texte}" d="{d1} {d2}"/>\n')
    return svg(f"0 0 {largeur:.0f} {SYM_H + 2 * MARGE}", corps_svg, NOM)


def empile(c: dict, couleur_symbole: str, couleur_texte: str, symbole: str = SYMBOLE) -> str:
    largeur = c["largeur"] + 2 * MARGE
    x_sym = (largeur - SYM_L) / 2
    base1 = MARGE + SYM_H + PILIER * 2 + HAUTEUR_CAPITALES
    base2 = base1 + PILIER + HAUTEUR_CAPITALES
    d1 = tracer(c["gras"], c["g1"], c["corps"], MARGE, base1)
    d2 = tracer(c["demi"], c["g2"], c["corps"], MARGE, base2)
    corps_svg = (f'  <path fill="{couleur_symbole}" transform="translate({x_sym:.2f} {MARGE})" d="{symbole}"/>\n'
                 f'  <path fill="{couleur_texte}" d="{d1} {d2}"/>\n')
    return svg(f"0 0 {largeur:.0f} {base2 + MARGE:.0f}", corps_svg, NOM)


def main() -> None:
    police, sortie = sys.argv[1], Path(sys.argv[2])
    c = composer(police)
    fichiers = {
        f"{PREFIXE}-horizontal.svg": horizontal(c, TERRACOTTA, ANTHRACITE),
        f"{PREFIXE}-horizontal-inverse.svg": horizontal(c, SABLE, SABLE, SYMBOLE_INVERSE),
        f"{PREFIXE}-horizontal-noir.svg": horizontal(c, "#000000", "#000000"),
        f"{PREFIXE}-empile.svg": empile(c, TERRACOTTA, ANTHRACITE),
        f"{PREFIXE}-empile-inverse.svg": empile(c, SABLE, SABLE, SYMBOLE_INVERSE),
    }
    for nom, contenu in fichiers.items():
        (sortie / nom).write_text(contenu, encoding="utf-8")
        print("écrit", sortie / nom)


if __name__ == "__main__":
    main()
