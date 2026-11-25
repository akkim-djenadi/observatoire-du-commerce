"""Note de conjoncture mensuelle en PDF : HTML autonome imprimé par Chrome sans affichage.

    python3 note.py                 # note du dernier mois collecté → rapports/note-AAAA-MM.pdf
    python3 note.py --html-seul     # seulement le HTML (pour relire la mise en page)
"""
import argparse
import html
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd

import resume_vitalite as R
import ui_vitalite as UV
import vitalite_data as VD
from adresses import joli_nom_rue
from explications import nombre
from ui_charts import ZONES_COURTES

log = logging.getLogger("note")
CHROMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
           "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
TYPES_SIGNALES = ("Redressement judiciaire (ouverture)", "Sauvegarde", "Liquidation judiciaire (ouverture)")
SYMBOLE = ('<svg viewBox="0 0 184 160" width="38" height="33" aria-hidden="true"><path fill="#BB502E" '
           'd="M0 160V0H184V160H156V51A25 25 0 0 0 106 51V160H78V51A25 25 0 0 0 28 51V160Z"/></svg>')

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@600;800&family=Open+Sans:wght@400;600&display=swap');
@page { size: A4; margin: 14mm 14mm 16mm; }
body { font-family: 'Open Sans', sans-serif; color: #2B2B2B; font-size: 10.5pt; line-height: 1.45; margin: 0; }
h1, h2 { font-family: 'Montserrat', sans-serif; color: #8A3A20; margin: 0; }
h1 { font-size: 20pt; text-transform: uppercase; font-weight: 800; letter-spacing: -0.01em; }
h2 { font-size: 12.5pt; margin: 16px 0 6px; }
.marque { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; font-family: 'Montserrat';
  font-weight: 800; font-size: 9pt; letter-spacing: .06em; text-transform: uppercase; }
.marque span { color: #8A3A20; font-weight: 600; letter-spacing: .2em; }
.sous-titre { color: #6B6460; margin: 2px 0 12px; }
.tuiles { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin: 8px 0 4px; }
.tuile { background: #F6ECE4; border-left: 4px solid #BB502E; padding: 7px 9px; border-radius: 4px; }
.tuile b { display: block; font-family: 'Montserrat'; font-size: 14pt; color: #8A3A20; }
.tuile small { color: #6B6460; font-size: 8pt; }
ul.essentiel { padding-left: 16px; margin: 4px 0; } ul.essentiel li { margin: 3px 0; }
table { width: 100%; border-collapse: collapse; font-size: 9pt; } th { text-align: left; color: #6B6460;
  font-weight: 600; border-bottom: 1px solid #E6D7CB; } td { padding: 3px 4px; border-bottom: 1px solid #F1E7DF; }
.graphique { break-inside: avoid; }
section { break-inside: avoid; }
td.date { white-space: nowrap; }
footer { margin-top: 14px; padding-top: 6px; border-top: 1px solid #E6D7CB; color: #6B6460; font-size: 8pt; }
"""


def _md_gras(texte: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(texte))


def _tuiles(c: dict) -> str:
    prix = "—" if c["prix_m2"] is None else f"{nombre(c['prix_m2'])} €/m²"
    delta = "" if c["delta"] is None else f"{R.entier_signe(round(c['delta']))} pts sur 12 mois"
    items = [("Indice de vitalité", f"{c['indice']:.0f}/100", delta),
             ("Défaillances (12 mois)", nombre(c["defaillances"]), "redressements, sauvegardes, liquidations"),
             ("Solde de commerces", R.entier_signe(c["solde"]), f"{c['ouvertures']} ouvertures, {c['fermetures']} fermetures"),
             ("Prix médian des locaux", prix, f"{c['ventes']} ventes"),
             ("Diversité de l'offre", f"{c['diversite'] * 100:.0f} %", "100 % = offre équilibrée")]
    return "".join(f'<div class="tuile"><small>{html.escape(t)}</small><b>{html.escape(v)}</b>'
                   f"<small>{html.escape(s)}</small></div>" for t, v, s in items)


def _figure(fig, premiere: bool, hauteur: int) -> str:
    fig.update_layout(width=720, height=hauteur)
    return ('<div class="graphique">' + fig.to_html(full_html=False, include_plotlyjs="inline" if premiere else False,
                                                    config={"staticPlot": True}) + "</div>")


def _procedures_du_mois(d: VD.DonneesVitalite) -> str:
    p = d.procedures
    if p.empty:
        return "<p>Aucune.</p>"
    mois = d.dernier_mois
    p = p[p["type"].isin(TYPES_SIGNALES) & p["date_jugement"].astype(str).str.startswith(_mois_precedent(mois))]
    if p.empty:
        return "<p>Aucune nouvelle procédure publiée ce mois-ci au centre-ville.</p>"
    lignes = "".join(
        f"<tr><td>{html.escape(r['enseigne'] or r['nom'])}</td><td>{html.escape(joli_nom_rue(r['voie']))}</td>"
        f"<td>{html.escape(ZONES_COURTES.get(r['zone'], r['zone']))}</td><td>{html.escape(r['type'])}</td>"
        f"<td class=\"date\">{html.escape(VD.date_fr(r['date_jugement']))}</td></tr>" for _, r in p.sort_values("date_jugement").iterrows())
    return f"<table><tr><th>Commerce</th><th>Rue</th><th>Zone</th><th>Procédure</th><th>Jugement</th></tr>{lignes}</table>"


def _mois_precedent(mois: str) -> str:
    a, m = (int(x) for x in mois.split("-"))
    return f"{a - 1}-12" if m == 1 else f"{a}-{m - 1:02d}"


def construire_html(d: VD.DonneesVitalite, jour: date) -> str:
    c = R.chiffres(d, jour)
    rues = d.indice_du_mois()
    essentiel = "".join(f"<li>{_md_gras(p)}</li>" for p in R.phrases_essentiel(d, c))
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Note de conjoncture</title>
<style>{CSS}</style></head><body>
<div class="marque">{SYMBOLE}<div>Observatoire<br><span>du Commerce</span></div></div>
<h1>Note de conjoncture · {html.escape(VD.mois_fr(d.dernier_mois))}</h1>
<p class="sous-titre">Vitalité commerciale du centre-ville de Montpellier · {nombre(c['stock'])} commerces suivis</p>
<div class="tuiles">{_tuiles(c)}</div>
<h2>L'essentiel</h2><ul class="essentiel">{essentiel}</ul>
<section><h2>L'indice de vitalité mois par mois</h2>{_figure(UV.courbe_indice(d.historique), True, 330)}</section>
<section><h2>Rues les plus dynamiques et les plus fragiles</h2>
{_figure(UV.classement_rues(rues[rues["niveau"] == "rue"]), False, 400)}</section>
<h2>Procédures du mois écoulé ({html.escape(VD.mois_fr(_mois_precedent(d.dernier_mois)))})</h2>{_procedures_du_mois(d)}
<footer>Sources : Sirene (INSEE) via l'API Recherche d'entreprises, BODACC (DILA) et DVF, publiés sur data.gouv.fr.
Données collectées le {html.escape(VD.date_fr(d.collecte_le))}. Méthode de l'indice : page « Vitalité des rues » de l'application.
Observatoire du Commerce · application développée par Akkim Djenadi.</footer>
</body></html>"""


def trouver_chrome() -> str | None:
    if os.environ.get("CHROME"):
        return os.environ["CHROME"]
    return next((c for c in CHROMES if shutil.which(c) or Path(c).exists()), None)


def imprimer_pdf(html_doc: str, sortie: Path) -> Path:
    chrome = trouver_chrome()
    if not chrome:
        raise RuntimeError("Chrome ou Chromium introuvable : installez-le ou indiquez son chemin dans la variable CHROME.")
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "note.html"
        source.write_text(html_doc, encoding="utf-8")
        sortie.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer",
                        "--virtual-time-budget=15000", f"--print-to-pdf={sortie}", source.as_uri()],
                       check=True, capture_output=True, timeout=180)
    if not sortie.exists() or sortie.stat().st_size == 0:
        raise RuntimeError("Chrome n'a pas produit de PDF.")
    return sortie


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Note de conjoncture mensuelle (PDF).")
    p.add_argument("--html-seul", action="store_true", help="Écrire seulement le HTML, sans PDF")
    args = p.parse_args(sys.argv[1:] if argv is None else argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    d = VD.charger()
    if d.historique.empty:
        log.error("Aucune donnée : lancez d'abord python3 collecte.py")
        return 1
    doc = construire_html(d, date.today())
    base = VD.RAPPORTS / f"note-{d.dernier_mois}"
    if args.html_seul:
        base.with_suffix(".html").parent.mkdir(parents=True, exist_ok=True)
        base.with_suffix(".html").write_text(doc, encoding="utf-8")
        log.info("HTML écrit : %s", base.with_suffix(".html"))
        return 0
    try:
        log.info("PDF écrit : %s", imprimer_pdf(doc, base.with_suffix(".pdf")))
    except (RuntimeError, subprocess.SubprocessError) as exc:
        log.error("PDF impossible : %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
