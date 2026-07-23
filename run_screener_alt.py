"""
run.py – Swing Trade Screener für GitHub Actions mit GitHub Pages
Wortmann & Wember GmbH
"""

import logging, sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def run():
    log.info("=" * 55)
    log.info(f"SWING TRADE SCREENER – {datetime.now().strftime('%d.%m.%Y %H:%M:%S')} UTC")
    log.info("=" * 55)

    log.info("SCHRITT 1: Marktdaten laden (Yahoo Finance)…")
    from data_fetcher import fetch_all
    results = fetch_all()
    loaded = sum(1 for r in results if r["data"])
    log.info(f"  → {loaded}/{len(results)} Instrumente geladen")
    for r in results:
        sc = r["score"]["pct"] if r["score"] else 0
        log.info(f"  {r['instrument']['symbol']:6s}  {sc:3d}%  [{r['rating']}]  {r.get('best_direction','')}")

    log.info("SCHRITT 2: HTML-Report erstellen…")
    from report_generator import generate_report

    # Haupt-Report (mit Datum)
    Path("docs").mkdir(exist_ok=True)
    dated = f"docs/report_{datetime.now().strftime('%Y%m%d')}.html"
    generate_report(results, dated)

    # index.html = immer aktuellster Report (für GitHub Pages)
    generate_report(results, "docs/index.html")
    log.info(f"  → docs/index.html (GitHub Pages)")

    top = next((r for r in results if r.get("best_score") and r["best_score"]["pct"] >= 60), None)
    log.info("-" * 55)
    if top:
        log.info(f"  ★ {top['instrument']['name']} ({top['instrument']['symbol']}) "
                 f"{top.get('best_direction','')} – {top['best_score']['pct']}%")
    else:
        log.info("  Kein Signal ≥ 60% heute.")
    log.info("=" * 55)


if __name__ == "__main__":
    run()
