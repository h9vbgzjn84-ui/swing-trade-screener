"""
run.py - Index-Signaltafel
Wortmann & Wember GmbH

Bricht ab, wenn die Datenlage unvollstaendig ist. Ein fehlgeschlagener Lauf ist
besser als eine Seite, die veraltete Zahlen als aktuell ausgibt.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def run() -> int:
    now = datetime.now(BERLIN)
    log.info("=" * 58)
    log.info(f"INDEX-SIGNALTAFEL - {now:%d.%m.%Y %H:%M:%S} Uhr (Europe/Berlin)")
    log.info("=" * 58)

    from signals import build_board, evaluate, thresholds
    from report import generate

    try:
        board = build_board()
    except Exception as exc:
        log.error(f"Datenabruf fehlgeschlagen: {exc}")
        log.error("Report wird NICHT ueberschrieben - die alte Seite bleibt stehen.")
        return 1

    if len(board.indices) < 3:
        log.error(f"Nur {len(board.indices)}/3 Indizes geladen - Abbruch.")
        return 1

    log.info("-" * 58)
    for card in evaluate(board):
        log.info(f"  {card['title']:<20} {card['verdict']:<14} {card['reason']}")
    for t in thresholds(board):
        log.info(f"  Schwelle {t['name']:<12} {t['value'] or '-':>10}  {t['text']}")

    Path("docs").mkdir(exist_ok=True)
    generate(board, "docs/index.html")
    generate(board, f"docs/tafel_{now:%Y%m%d}.html")
    log.info("-" * 58)
    log.info("  docs/index.html geschrieben")
    log.info("=" * 58)
    return 0


if __name__ == "__main__":
    sys.exit(run())
