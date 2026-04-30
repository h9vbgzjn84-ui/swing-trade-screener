"""
data_fetcher.py – Marktdaten + Long/Short Scoring
Wortmann & Wember GmbH · Swing Trade Screener
"""

import yfinance as yf
import logging
from typing import Optional, Tuple
from engine import MarketData, compute_indicators, calc_score_long, calc_score_short, get_rating, calc_levels

log = logging.getLogger(__name__)

# ─── Instrumente ─────────────────────────────────────────────────────────────
INSTRUMENTS = [
    # Indizes
    {"symbol": "SPX",   "yahoo": "^GSPC",  "name": "S&P 500",      "type": "Index"},
    {"symbol": "DJI",   "yahoo": "^DJI",   "name": "Dow Jones",     "type": "Index"},
    {"symbol": "DAX",   "yahoo": "^GDAXI", "name": "DAX 40",        "type": "Index"},
    {"symbol": "NQ",    "yahoo": "^NDX",   "name": "Nasdaq 100",    "type": "Index"},
    {"symbol": "SX5E",  "yahoo": "^STOXX50E", "name": "Euro Stoxx 50","type": "Index"},
    {"symbol": "NKY",   "yahoo": "^N225",  "name": "Nikkei 225",    "type": "Index"},
    # Rohstoffe
    {"symbol": "GOLD",  "yahoo": "GC=F",   "name": "Gold",          "type": "Rohstoff"},
    {"symbol": "WTI",   "yahoo": "CL=F",   "name": "WTI Rohöl",     "type": "Rohstoff"},
    {"symbol": "BRENT", "yahoo": "BZ=F",   "name": "Brent Rohöl",   "type": "Rohstoff"},
    {"symbol": "SILBER","yahoo": "SI=F",   "name": "Silber",        "type": "Rohstoff"},
    {"symbol": "KUPFER","yahoo": "HG=F",   "name": "Kupfer",        "type": "Rohstoff"},
    # Krypto
    {"symbol": "BTC",   "yahoo": "BTC-USD","name": "Bitcoin",       "type": "Krypto"},
]

# ─── Saisonalität (historische monatl. Bullwahrscheinlichkeit %) ──────────────
SEASONAL = {
    "SPX":   {1:68,2:58,3:62,4:72,5:45,6:52,7:65,8:48,9:42,10:55,11:74,12:78},
    "DJI":   {1:67,2:57,3:63,4:71,5:46,6:51,7:64,8:49,9:43,10:54,11:73,12:77},
    "DAX":   {1:65,2:60,3:63,4:70,5:42,6:50,7:62,8:47,9:40,10:53,11:72,12:75},
    "NQ":    {1:70,2:60,3:65,4:75,5:48,6:55,7:68,8:50,9:44,10:57,11:76,12:80},
    "SX5E":  {1:64,2:59,3:62,4:69,5:43,6:50,7:61,8:47,9:41,10:52,11:71,12:74},
    "NKY":   {1:62,2:60,3:65,4:68,5:52,6:55,7:60,8:50,9:45,10:57,11:68,12:72},
    "GOLD":  {1:72,2:68,3:65,4:60,5:58,6:55,7:52,8:63,9:70,10:65,11:58,12:62},
    "WTI":   {1:55,2:65,3:70,4:68,5:62,6:58,7:60,8:55,9:50,10:48,11:52,12:56},
    "BRENT": {1:54,2:64,3:69,4:67,5:61,6:57,7:59,8:54,9:50,10:48,11:52,12:55},
    "SILBER":{1:65,2:62,3:60,4:58,5:55,6:52,7:50,8:60,9:68,10:63,11:57,12:60},
    "KUPFER":{1:60,2:65,3:68,4:63,5:58,6:52,7:55,8:58,9:52,10:55,11:60,12:58},
    "BTC":   {1:75,2:70,3:65,4:60,5:45,6:52,7:62,8:55,9:48,10:65,11:72,12:78},
}


def fetch_ohlcv(yahoo_ticker: str, period: str = "12mo") -> Optional[Tuple]:
    try:
        df = yf.Ticker(yahoo_ticker).history(period=period, interval="1d", auto_adjust=True)
        if df.empty:
            log.warning(f"Keine Daten: {yahoo_ticker}")
            return None
        df = df.dropna(subset=["Open","High","Low","Close"])
        return (df["Open"].tolist(), df["High"].tolist(),
                df["Low"].tolist(),  df["Close"].tolist(),
                df["Volume"].fillna(0).tolist())
    except Exception as e:
        log.error(f"Fehler {yahoo_ticker}: {e}")
        return None


def fetch_all() -> list[dict]:
    from datetime import datetime
    month   = datetime.now().month
    results = []

    for inst in INSTRUMENTS:
        log.info(f"Lade {inst['symbol']} ({inst['yahoo']})…")
        ohlcv = fetch_ohlcv(inst["yahoo"])

        if ohlcv is None:
            results.append({
                "instrument": inst, "data": None,
                "seasonal": SEASONAL.get(inst["symbol"],{}).get(month,50),
                "score_long": None, "score_short": None,
                "best_score": None, "best_direction": None,
                "rating": "FEHLER", "error": "Datenabruf fehlgeschlagen",
            })
            continue

        md = compute_indicators(inst["symbol"], inst["name"], *ohlcv)
        seasonal = SEASONAL.get(inst["symbol"],{}).get(month, 50)

        sl = calc_score_long(md, seasonal)
        ss = calc_score_short(md, seasonal)

        # Bestes Signal gewinnt
        if sl["pct"] >= ss["pct"]:
            best, direction = sl, "LONG"
        else:
            best, direction = ss, "SHORT"

        results.append({
            "instrument":    inst,
            "data":          md,
            "seasonal":      seasonal,
            "score_long":    sl,
            "score_short":   ss,
            "best_score":    best,
            "best_direction": direction,
            "score":         best,          # Kompatibilität mit Report
            "rating":        get_rating(best["pct"]),
            "error":         None,
            "levels":        calc_levels(md, direction, best["pct"]),
        })

    results.sort(key=lambda x: x["best_score"]["pct"] if x["best_score"] else -1, reverse=True)
    return results
