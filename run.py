"""
run.py – Swing Trade Screener für GitHub Actions
Wortmann & Wember GmbH
Läuft täglich auf GitHub's Servern – kein lokaler Rechner nötig.
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
    Path("reports").mkdir(exist_ok=True)
    path = generate_report(results, f"reports/report_{datetime.now().strftime('%Y%m%d_%H%M')}.html")
    log.info(f"  → {path}")

    log.info("SCHRITT 3: E-Mail senden…")
    from mailer import send_report
    ok = send_report(results, path)
    if not ok:
        log.error("E-Mail-Versand fehlgeschlagen!")
        sys.exit(1)

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
