"""
signals.py - Regelwerk-Signale für die Index-Signaltafel

Enthaelt ausschliesslich Regeln, die im Split-Sample-Test (2016-21 / 2021-26)
in beiden Zeithaelften Bestand hatten. Keine Indikator-Scores.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)

BERLIN = ZoneInfo("Europe/Berlin")

# Nur Instrumente, für die validierte Regeln existieren.
# close_at_2200 = Yahoo-Tagesschluss entspricht dem 22:00-Berlin-Schluss.
# Für ^GDAXI ist das NICHT der Fall (Xetra 17:30) -> Dip-Signal nicht berechenbar.
INSTRUMENTS = [
    {"key": "NQ",  "yahoo": "^NDX", "name": "Nasdaq 100", "close_at_2200": True},
    {"key": "DJI", "yahoo": "^DJI", "name": "Dow Jones",  "close_at_2200": True},
    {"key": "DAX", "yahoo": "^GDAXI", "name": "DAX 40",   "close_at_2200": False},
]

VIX_TICKER = "^VIX"
HISTORY = "3y"          # 12mo reicht für eine belastbare SMA200 nicht aus
MAX_REPORT_AGE_H = 26   # danach warnt die Seite selbst (clientseitig)


@dataclass
class IndexState:
    key: str
    name: str
    price: float
    last_close_date: datetime
    sma200: Optional[float]
    above_sma200: Optional[bool]
    red_streak: int                 # aufeinanderfolgende fallende Schlusskurse
    prev_close: float               # Schwelle für den naechsten roten Tag
    dip_active: bool
    dip_threshold: Optional[float]  # Schluss darunter -> Signal aktiv
    dip_supported: bool             # False bei fehlender 22:00-Quelle
    note: str = ""


@dataclass
class Board:
    generated_at: datetime
    vix: float
    vix_date: datetime
    indices: dict[str, IndexState] = field(default_factory=dict)
    close_age_h: float = 0.0


def de(x: float, nk: int = 0) -> str:
    """Deutsche Zahlformatierung: 28.998 statt 28,998."""
    s = f"{x:,.{nk}f}"
    return s.replace(",", "#").replace(".", ",").replace("#", ".")


def _history(ticker: str) -> pd.DataFrame:
    df = yf.Ticker(ticker).history(period=HISTORY, interval="1d", auto_adjust=True)
    df = df.dropna(subset=["Close"])
    if df.empty:
        raise RuntimeError(f"Keine Daten für {ticker}")
    return df


def _last_completed(df: pd.DataFrame, now_berlin: datetime) -> tuple[pd.Series, datetime]:
    """Letzte abgeschlossene Tageskerze. Die Kerze des laufenden Handelstages
    wird verworfen, damit kein unfertiger Kurs als Schluss gewertet wird."""
    idx = df.index.tz_convert(BERLIN) if df.index.tz is not None else df.index.tz_localize(BERLIN)
    today = now_berlin.date()
    mask = idx.date < today if now_berlin.hour < 22 else idx.date <= today
    sub = df[mask]
    if sub.empty:
        sub = df.iloc[:-1] if len(df) > 1 else df
        mask = None
    row = sub.iloc[-1]
    stamp = (sub.index[-1].tz_convert(BERLIN) if sub.index.tz is not None
             else sub.index[-1].tz_localize(BERLIN))
    return row, stamp, sub


def _red_streak(closes: np.ndarray) -> int:
    """Anzahl aufeinanderfolgender fallender Schlusskurse am Reihenende."""
    n = 0
    for i in range(len(closes) - 1, 0, -1):
        if closes[i] < closes[i - 1]:
            n += 1
        else:
            break
    return n


def build_board() -> Board:
    now = datetime.now(BERLIN)

    # --- VIX: Schluss des Vortages, kein Look-ahead ---
    vdf = _history(VIX_TICKER)
    vrow, vstamp, vsub = _last_completed(vdf, now)
    vix = float(vrow["Close"])
    log.info(f"VIX {vix:.2f} (Schluss {vstamp:%d.%m.%Y})")

    board = Board(generated_at=now, vix=vix, vix_date=vstamp)
    ages = []

    for inst in INSTRUMENTS:
        df = _history(inst["yahoo"])
        row, stamp, sub = _last_completed(df, now)
        closes = sub["Close"].values.astype(float)

        sma200 = float(np.mean(closes[-200:])) if len(closes) >= 200 else None
        price = float(row["Close"])
        streak = _red_streak(closes)

        supported = inst["close_at_2200"]
        state = IndexState(
            key=inst["key"], name=inst["name"], price=price,
            last_close_date=stamp,
            sma200=sma200,
            above_sma200=(price > sma200) if sma200 else None,
            red_streak=streak if supported else 0,
            prev_close=float(closes[-2]),
            dip_active=bool(supported and streak >= 3),
            dip_threshold=float(closes[-1]) if supported and streak == 2 else None,
            dip_supported=supported,
            note="" if supported else "Xetra-Schluss 17:30 - für das Dip-Signal ist eine 22:00-Quelle nötig.",
        )
        board.indices[inst["key"]] = state
        ages.append((now - stamp).total_seconds() / 3600)
        log.info(f"{inst['key']:4s} {price:10.2f}  SMA200 {'über' if state.above_sma200 else 'unter'}  "
                 f"rote Tage: {streak}")

    board.close_age_h = min(ages) if ages else 999
    return board


# ---------------------------------------------------------------------------
# Regel-Auswertung: liefert die Freigaben, die auf der Tafel stehen
# ---------------------------------------------------------------------------

def evaluate(board: Board) -> list[dict]:
    nq = board.indices["NQ"]
    dji = board.indices["DJI"]
    dax = board.indices["DAX"]
    v = board.vix

    cards = []

    # 1) Nasdaq Overnight 21:55 -> 08:00
    if v < 25:
        size = "halbe Größe" if nq.above_sma200 is False else "volle Größe"
        cards.append(dict(
            title="Nasdaq Overnight", window="21:55 → 08:00 Uhr",
            free=True, verdict="FREI",
            reason=f"VIX {de(v,1)} unter 25",
            detail=f"{size} · KO-Hebel 8–12 · Einstieg 21:55, Ausstieg 08:00 fix. "
                   f"Nach grünem Tag ist die Nacht historisch stärker. Nicht verlängern.",
            warn=("Unter der 200-Tage-Linie: halbe Größe."
                  if nq.above_sma200 is False else ""),
            facts=[("VIX (Vortag)", de(v,2)), ("Kurs", de(nq.price)),
                   ("SMA200", "darüber" if nq.above_sma200 else "darunter")],
        ))
    else:
        cards.append(dict(
            title="Nasdaq Overnight", window="21:55 → 08:00 Uhr",
            free=False, verdict="GESPERRT",
            reason=f"VIX {de(v,1)} ab 25",
            detail="Ab VIX 25 wird das Übernacht-Risiko nicht bezahlt. Abends flat. "
                   "Der Intraday-Handel bleibt davon unberührt.",
            facts=[("VIX (Vortag)", de(v,2)), ("Schwelle", "25,00")],
        ))

    # 2) Dow US-Session 15:30 -> 22:00
    boost = v > 30
    cards.append(dict(
        title="Dow US-Session", window="15:30 → 22:00 Uhr",
        free=True, verdict="1,5× GRÖSSE" if boost else "FREI",
        reason=f"VIX {de(v,1)} über 30" if boost else f"VIX {de(v,1)} · Basisgröße",
        detail=("Aufstockung über mehr Kapital bei niedrigerem Hebel, nicht über höheren Hebel. "
                "Einstieg 15:30–16:00 oder ab 17:00, Ausstieg 22:00. Kein Gewinnziel."
                if boost else
                "Einstieg 15:30–16:00 oder ab 17:00, Ausstieg 22:00. Stark: 17–18 Uhr. "
                "Schwach: 16–17 Uhr, dort Limits legen statt kaufen. Montag ist der beste Tag. "
                "Kein Gewinnziel, kein Overnight."),
        facts=[("VIX (Vortag)", de(v,2)), ("Kurs", de(dji.price)),
               ("Boost ab", "30,00")],
    ))

    # 3) DAX Tages-Session 08:00 -> 17:30
    cards.append(dict(
        title="DAX Tages-Session", window="08:00 → 17:30 Uhr",
        free=True, verdict="FREI",
        reason="Tagesfenster, kein Overnight",
        detail="Stark: 17–18 Uhr und der US-Vorlauf ab 15:30. Schwach: 16–17 Uhr. "
               "Die Eröffnung 08:00–09:00 nur als Breakout mit engem Stop, nicht blind kaufen. "
               "Ausstieg 17:30 - über Nacht ist der DAX ein Münzwurf mit Gap-Risiko.",
        facts=[("Kurs", de(dax.price)),
               ("SMA200", "darüber" if dax.above_sma200 else "darunter")],
    ))

    # 4) Dip-Overlay
    active = [s for s in board.indices.values() if s.dip_active]
    if active:
        names = ", ".join(s.name for s in active)
        schwach = [s for s in active if s.above_sma200 is False]
        warn = ""
        if schwach:
            wn = ", ".join(s.name for s in schwach)
            warn = (f"{wn} steht unter der 200-Tage-Linie. Dort hatte das Signal historisch "
                    f"keinen Vorteil gegenüber dem Markt (+0,20 % gegen +0,21 %) - "
                    f"halbe Größe oder auslassen.")
        cards.append(dict(
            title="Dip-Overlay", window="Einstieg 22:00 Uhr",
            free=True, verdict="SIGNAL",
            reason=f"{names}: drei fallende Schlusskurse",
            detail="Einstieg zum 22:00-Schluss, halten bis zum ersten grünen Schluss, "
                   "höchstens 5 Handelstage. 3×-ETF statt KO (kein Barrier-Risiko im fallenden Markt). "
                   "Kleinstes Risikobudget der drei Bausteine.",
            warn=warn,
            facts=[(s.name, ("über SMA200" if s.above_sma200 else "unter SMA200")) for s in active],
        ))
    else:
        near = [s for s in board.indices.values() if s.dip_supported and s.red_streak == 2]
        if near:
            det = " · ".join(f"{s.name} unter {de(s.price)}" for s in near)
            reason = "Zwei rote Tage - ein weiterer löst aus"
        else:
            det = ("Kein Index steht bei zwei fallenden Schlusskursen. "
                   "Geprüft wird der 22:00-Schluss, nicht der Xetra-Schluss.")
            reason = "Kein Signal"
        cards.append(dict(
            title="Dip-Overlay", window="Prüfung 21:55 Uhr",
            free=False, verdict="KEIN SIGNAL",
            reason=reason, detail=det,
            facts=[(s.name, ("1 roter Tag" if s.red_streak==1 else f"{s.red_streak} rote Tage") if s.dip_supported else "keine 22:00-Quelle")
                   for s in board.indices.values()],
        ))

    return cards


def thresholds(board: Board) -> list[dict]:
    """Schwellen-Zettel: alles, was für den Abend schon jetzt feststeht."""
    out = []
    for s in board.indices.values():
        if not s.dip_supported:
            out.append(dict(name=s.name, text=s.note, value=None, kind="na"))
            continue
        if s.red_streak >= 3:
            txt = "Signal aktiv" + ("" if s.above_sma200 else " · Achtung: unter SMA200")
            out.append(dict(name=s.name, text=txt, value=None,
                            kind="on" if s.above_sma200 else "watch"))
        elif s.red_streak == 2:
            out.append(dict(name=s.name, text="Dip-Signal, wenn der Schluss darunter liegt",
                            value=de(s.price), kind="watch"))
        else:
            need = 3 - s.red_streak
            out.append(dict(name=s.name,
                            text=("noch 1 roter Schlusskurs nötig" if need==1
                                  else f"noch {need} rote Schlusskurse nötig"),
                            value=de(s.price), kind="off"))
    return out
