"""
dax2200.py - DAX-Schlusskurse um 22:00 Uhr Berlin direkt von Dukascopy.

Yahoo liefert fuer ^GDAXI nur den Xetra-Schluss 17:30. Das Dip-Signal wurde aber
auf dem 22:00-Schluss validiert und kippt mit 17:30 ins Negative. Dieses Modul
holt die Tick-Rohdaten des CFD DEUIDXEUR - exakt die Quelle des Backtests.

Format der .bi5-Dateien: LZMA-komprimiert, Datensaetze zu 20 Byte
(uint32 Millisekunden-Offset, uint32 Ask, uint32 Bid, float32 AskVol, float32 BidVol).
Preise sind mit 1000 skaliert. Ein Abruf pro Handelstag.
"""

from __future__ import annotations

import logging
import lzma
import struct
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)

BERLIN = ZoneInfo("Europe/Berlin")
UTC = ZoneInfo("UTC")
INSTRUMENT = "DEUIDXEUR"
SKALA = 1000.0
TIMEOUT = 20


def _stunde(dt_utc: datetime) -> list[tuple[int, float]]:
    """Alle Ticks einer UTC-Stunde. Leere Liste, wenn nichts vorliegt."""
    url = (f"http://datafeed.dukascopy.com/datafeed/{INSTRUMENT}/"
           f"{dt_utc.year}/{dt_utc.month - 1:02d}/{dt_utc.day:02d}/"
           f"{dt_utc.hour:02d}h_ticks.bi5")
    try:
        raw = urllib.request.urlopen(url, timeout=TIMEOUT).read()
    except Exception as exc:
        log.debug(f"Dukascopy {dt_utc:%Y-%m-%d %H}h nicht abrufbar: {exc}")
        return []
    if not raw:
        return []
    try:
        data = lzma.LZMADecompressor().decompress(raw)
    except Exception:
        return []
    ticks = []
    for i in range(0, len(data) - 19, 20):
        ms, ask, bid, _av, _bv = struct.unpack(">IIIff", data[i:i + 20])
        ticks.append((ms, bid / SKALA))
    return ticks


def schlusskurse_2200(tage: int = 14, jetzt: datetime | None = None) -> dict:
    """Letzte Schlusskurse um 22:00 Berlin, aelteste zuerst.

    Der Schluss eines Tages ist der letzte Tick in der Stunde 21:00-22:00 Berlin.
    Tage ohne Daten (Wochenende, Feiertag) fallen still heraus.
    """
    jetzt = jetzt or datetime.now(BERLIN)
    out: dict = {}
    tag = jetzt.date()
    # Der heutige Schluss existiert erst nach 22:00 Uhr
    if jetzt.hour < 22:
        tag -= timedelta(days=1)

    versuche = 0
    while len(out) < tage and versuche < tage * 2 + 10:
        versuche += 1
        if tag.weekday() < 5:
            start = datetime(tag.year, tag.month, tag.day, 21, tzinfo=BERLIN)
            ticks = _stunde(start.astimezone(UTC))
            if ticks:
                out[tag] = ticks[-1][1]
        tag -= timedelta(days=1)

    return dict(sorted(out.items()))


def rote_serie(closes: dict) -> int:
    """Aufeinanderfolgende fallende Schlusskurse am Reihenende."""
    werte = list(closes.values())
    n = 0
    for i in range(len(werte) - 1, 0, -1):
        if werte[i] < werte[i - 1]:
            n += 1
        else:
            break
    return n
