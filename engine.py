"""
engine.py – Technische Indikatoren + Long/Short Scoring
Wortmann & Wember GmbH · Swing Trade Screener
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MarketData:
    symbol: str
    name: str
    price: float
    ema50: Optional[float]
    ema200: Optional[float]
    rsi: Optional[float]
    bb_width_pct: Optional[float]
    atr_pct: Optional[float]
    volume_ratio: Optional[float]
    candle_name: str
    candle_bullish: bool
    candle_bearish: bool
    dist_ema50: Optional[float]
    # Long-Flags
    above_ema200: bool = False
    near_ema50: bool = False
    rsi_in_range_long: bool = False   # 35–55
    low_bb_width: bool = False
    high_volume: bool = False
    # Short-Flags
    below_ema200: bool = False
    near_ema50_from_above: bool = False  # Kurs nahe EMA50 von oben (Short-Pullback)
    rsi_in_range_short: bool = False     # 45–65


def ema(prices: np.ndarray, period: int) -> Optional[float]:
    if len(prices) < period:
        return None
    k = 2 / (period + 1)
    val = float(np.mean(prices[:period]))
    for p in prices[period:]:
        val = float(p) * k + val * (1 - k)
    return val


def rsi(prices: np.ndarray, period: int = 14) -> Optional[float]:
    if len(prices) < period + 1:
        return None
    changes = np.diff(prices)
    gains  = np.where(changes > 0, changes, 0.0)
    losses = np.where(changes < 0, -changes, 0.0)
    ag = float(np.mean(gains[:period]))
    al = float(np.mean(losses[:period]))
    for i in range(period, len(changes)):
        ag = (ag * (period - 1) + gains[i]) / period
        al = (al * (period - 1) + losses[i]) / period
    if al == 0:
        return 100.0
    return 100 - 100 / (1 + ag / al)


def bollinger_width(prices: np.ndarray, period: int = 20) -> Optional[float]:
    if len(prices) < period:
        return None
    sl   = prices[-period:]
    mean = float(np.mean(sl))
    if mean == 0:
        return None
    std = float(np.std(sl, ddof=0))
    return (std * 2) / mean


def atr(highs, lows, closes, period: int = 14) -> Optional[float]:
    if len(highs) < period + 1:
        return None
    trs = [max(highs[i] - lows[i],
               abs(highs[i] - closes[i-1]),
               abs(lows[i]  - closes[i-1])) for i in range(1, len(highs))]
    return float(np.mean(trs[-period:]))


def percentile_rank(series: np.ndarray, value: float) -> float:
    return float(np.sum(series < value) / len(series) * 100)


def detect_candle(opens, highs, lows, closes):
    n = len(closes) - 1
    if n < 1:
        return "Unbekannt", False, False
    o, h, l, c = opens[n], highs[n], lows[n], closes[n]
    body  = abs(c - o)
    rng   = h - l
    if rng == 0:
        return "Doji", False, False
    lw = min(o, c) - l
    uw = h - max(o, c)
    br = body / rng
    po, pc = opens[n-1], closes[n-1]

    # Bullish
    if br < 0.35 and lw > body * 2 and uw < body:
        return "Hammer", True, False
    if pc < po and c > o and c > po and o < pc:
        return "Bullish Engulfing", True, False
    if c > o and br > 0.7 and lw < body * 0.1:
        return "Bullish Marubozu", True, False
    # Bearish
    if br < 0.35 and uw > body * 2 and lw < body:
        return "Shooting Star", False, True
    if pc > po and c < o and c < po and o > pc:
        return "Bearish Engulfing", False, True
    if c < o and br > 0.7 and uw < body * 0.1:
        return "Bearish Marubozu", False, True
    # Neutral
    return ("Bullish Bar", True, False) if c > o else ("Bearish Bar", False, True)


def compute_indicators(symbol, name, opens, highs, lows, closes, volumes) -> MarketData:
    o = np.array(opens,   dtype=float)
    h = np.array(highs,   dtype=float)
    l = np.array(lows,    dtype=float)
    c = np.array(closes,  dtype=float)
    v = np.array(volumes, dtype=float)

    price = float(c[-1])
    e50   = ema(c, 50)
    e200  = ema(c, 200)
    r14   = rsi(c, 14)

    bb_series = [w for i in range(20, len(c)+1)
                 if (w := bollinger_width(c[:i], 20)) is not None]
    bb_now = bb_series[-1] if bb_series else None
    bb_pct = percentile_rank(np.array(bb_series), bb_now) if bb_now and len(bb_series) > 5 else 50.0

    atr_series = [a for i in range(15, len(c))
                  if (a := atr(h[:i+1], l[:i+1], c[:i+1], 14)) is not None]
    atr_now = atr_series[-1] if atr_series else None
    atr_pct = percentile_rank(np.array(atr_series), atr_now) if atr_now and len(atr_series) > 5 else 50.0

    vol20     = float(np.mean(v[-21:-1])) if len(v) >= 21 else float(np.mean(v[:-1]))
    vol_ratio = float(v[-1]) / vol20 if vol20 > 0 else 1.0

    cname, cbull, cbear = detect_candle(o, h, l, c)
    dist_e50 = ((price - e50) / e50 * 100) if e50 else None

    return MarketData(
        symbol=symbol, name=name, price=price,
        ema50=e50, ema200=e200, rsi=r14,
        bb_width_pct=bb_pct, atr_pct=atr_pct, volume_ratio=vol_ratio,
        candle_name=cname, candle_bullish=cbull, candle_bearish=cbear,
        dist_ema50=dist_e50,
        above_ema200      = bool(e200 and price > e200),
        near_ema50        = bool(dist_e50 and abs(dist_e50) < 2.5),
        rsi_in_range_long = bool(r14 and 35 <= r14 <= 55),
        low_bb_width      = bool(bb_pct < 40),
        high_volume       = bool(vol_ratio >= 1.0),
        below_ema200         = bool(e200 and price < e200),
        near_ema50_from_above= bool(dist_e50 and -2.5 <= dist_e50 <= 0),
        rsi_in_range_short   = bool(r14 and 45 <= r14 <= 65),
    )


def calc_score_long(md: MarketData, seasonal: int) -> dict:
    """Long-Setup Score (0–110 Punkte)."""
    s, m = 0, 0
    m += 25; s += 25 if md.above_ema200 else 0
    m += 20
    if md.near_ema50: s += 20
    elif md.dist_ema50 and abs(md.dist_ema50) < 5: s += 10
    m += 20
    if md.rsi_in_range_long: s += 20
    elif md.rsi and 28 < md.rsi < 62: s += 10
    m += 15; s += 15 if md.low_bb_width  else 0
    m += 10; s += 10 if md.high_volume   else 0
    m += 10; s += 10 if md.candle_bullish else 0
    m += 10
    if seasonal >= 65: s += 10
    elif seasonal >= 55: s += 5
    return {"score": s, "max": m, "pct": round(s/m*100) if m else 0, "direction": "LONG"}


def calc_score_short(md: MarketData, seasonal: int) -> dict:
    """
    Short-Setup Score (0–110 Punkte).
    Spiegellogik: Downtrend + Rallye zum EMA50 + RSI erhöht + bearisches Muster
    """
    s, m = 0, 0
    # ① Unter EMA200 = Downtrend-Regime
    m += 25; s += 25 if md.below_ema200 else 0
    # ② Kurs nahe EMA50 von oben (Pullback im Downtrend)
    m += 20
    if md.near_ema50_from_above: s += 20
    elif md.dist_ema50 and -5 <= md.dist_ema50 <= 2: s += 10
    # ③ RSI in erhöhter Zone (45–65 = Overbought im Downtrend)
    m += 20
    if md.rsi_in_range_short: s += 20
    elif md.rsi and 40 < md.rsi < 70: s += 10
    # ④ Bollinger-Kompression
    m += 15; s += 15 if md.low_bb_width else 0
    # ⑤ Volumen
    m += 10; s += 10 if md.high_volume else 0
    # ⑥ Bearisches Kerzenmuster
    m += 10; s += 10 if md.candle_bearish else 0
    # ⑦ Saisonalität invertiert (schwache Monate = Short-Rückenwind)
    m += 10
    if seasonal <= 45: s += 10
    elif seasonal <= 55: s += 5
    return {"score": s, "max": m, "pct": round(s/m*100) if m else 0, "direction": "SHORT"}


def get_rating(pct: int) -> str:
    if pct >= 80: return "STARK"
    if pct >= 60: return "MODERAT"
    if pct >= 40: return "SCHWACH"
    return "KEIN SIGNAL"


def calc_levels(md: MarketData, direction: str, score_pct: int) -> dict:
    """
    Berechnet konkrete Handelsniveaus:
    Stop-Loss (ATR-basiert), TP1 (1.5x R), TP2 (2.5x R), Positionsgröße.
    """
    price = md.price
    if not price:
        return {}

    atr_pct = md.atr_pct or 50
    if atr_pct < 30:   atr_mult = 1.2
    elif atr_pct < 50: atr_mult = 1.5
    elif atr_pct < 70: atr_mult = 2.0
    else:              atr_mult = 2.5

    dist     = abs(md.dist_ema50) if md.dist_ema50 else 1.5
    stop_pct = max(dist * 0.8, atr_mult * 0.8)
    stop_pct = min(stop_pct, 5.0)

    if score_pct >= 80:   crv1, crv2 = 1.5, 2.5
    elif score_pct >= 65: crv1, crv2 = 1.5, 2.0
    else:                 crv1, crv2 = 1.2, 1.8

    tp1_pct = stop_pct * crv1
    tp2_pct = stop_pct * crv2

    if direction == "LONG":
        stop = round(price * (1 - stop_pct / 100), 2)
        tp1  = round(price * (1 + tp1_pct / 100), 2)
        tp2  = round(price * (1 + tp2_pct / 100), 2)
        if md.ema50:
            stop = min(stop, round(md.ema50 * 0.995, 2))
    else:
        stop = round(price * (1 + stop_pct / 100), 2)
        tp1  = round(price * (1 - tp1_pct / 100), 2)
        tp2  = round(price * (1 - tp2_pct / 100), 2)
        if md.ema50:
            stop = max(stop, round(md.ema50 * 1.005, 2))

    risk_pct  = abs(price - stop) / price * 100
    pos_size  = round(min(1.0 / risk_pct * 100, 25.0), 1) if risk_pct > 0 else 0

    return {
        "entry": price, "stop": stop, "tp1": tp1, "tp2": tp2,
        "stop_pct": round(stop_pct, 2),
        "tp1_pct":  round(tp1_pct, 2),
        "tp2_pct":  round(tp2_pct, 2),
        "crv1": round(crv1, 1), "crv2": round(crv2, 1),
        "pos_size": pos_size, "direction": direction,
    }
