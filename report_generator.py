"""
report_generator.py - HTML-Report mit Long/Short Signalen + KO-Scheine
Swing Trade Screener
"""

from datetime import datetime
from pathlib import Path
from engine import MarketData

EMOJI = {
    "SPX": "&#128200;", "DJI": "&#127963;", "DAX": "&#127465;&#127466;",
    "NQ": "&#128187;", "SX5E": "&#127466;&#127482;", "NKY": "&#128510;",
    "GOLD": "&#129351;", "WTI": "&#128674;", "BRENT": "&#9981;",
    "SILBER": "&#129689;", "KUPFER": "&#128310;", "BTC": "&#8383;",
}

TYPE_COLOR = {
    "Index":    "#4fc3f7",
    "Rohstoff": "#ffb74d",
    "Krypto":   "#ce93d8",
}

def rating_color(pct):
    if pct >= 80: return "#00e676", "rgba(0,230,118,0.10)"
    if pct >= 60: return "#ffd740", "rgba(255,215,64,0.10)"
    if pct >= 40: return "#ff9100", "rgba(255,145,0,0.10)"
    return "#888", "rgba(80,80,80,0.08)"

def dir_style(direction):
    if direction == "LONG":
        return "#00e676", "rgba(0,230,118,0.10)", "&#9650; LONG"
    return "#f44336", "rgba(244,67,54,0.10)", "&#9660; SHORT"

def fmt_price(p):
    if p is None: return "-"
    return f"{p:,.0f}".replace(",", ".") if p > 999 else f"{p:.2f}"

def sbadge(active, label, invert=False):
    on  = active if not invert else not active
    c   = "#00e676" if on else "#555"
    bg  = "rgba(0,230,118,0.08)" if on else "rgba(255,255,255,0.02)"
    dot = "&#9679;" if on else "&#9675;"
    return (
        '<span class="badge" style="color:' + c + ';background:' + bg + ';border-color:' + c + '44">'
        + dot + ' ' + label + '</span>'
    )


def calc_ko_params(md: MarketData, direction: str, score_pct: int):
    if not md or not md.price or score_pct < 50:
        return None
    price   = md.price
    atr_pct = md.atr_pct or 1.5
    if atr_pct > 10:
        atr_pct = atr_pct / 20.0
    if atr_pct < 0.8:   lever_label = "6-8x"
    elif atr_pct < 1.5: lever_label = "4-6x"
    elif atr_pct < 2.5: lever_label = "3-5x"
    else:               lever_label = "2-3x"
    min_dist_pct = max(atr_pct * 2.5, 3.0)
    stop_pct     = max(atr_pct * 1.5, 2.0)
    if direction == "LONG":
        ko_level = round(price * (1 - min_dist_pct / 100), 2)
        stop_lvl = round(price * (1 - stop_pct / 100), 2)
        tp1      = round(price * (1 + stop_pct * 1.5 / 100), 2)
        tp2      = round(price * (1 + stop_pct * 2.5 / 100), 2)
    else:
        ko_level = round(price * (1 + min_dist_pct / 100), 2)
        stop_lvl = round(price * (1 + stop_pct / 100), 2)
        tp1      = round(price * (1 - stop_pct * 1.5 / 100), 2)
        tp2      = round(price * (1 - stop_pct * 2.5 / 100), 2)
    tp1_pct = round(stop_pct * 1.5, 1)
    tp2_pct = round(stop_pct * 2.5, 1)
    if score_pct >= 80:   max_days = 42
    elif score_pct >= 65: max_days = 28
    else:                 max_days = 14
    return dict(
        price=price, direction=direction, lever_label=lever_label,
        min_dist_pct=round(min_dist_pct, 1),
        ko_level=ko_level, stop_lvl=stop_lvl, stop_pct=round(stop_pct, 1),
        tp1=tp1, tp1_pct=tp1_pct, tp2=tp2, tp2_pct=tp2_pct,
        max_days=max_days, atr_pct=round(atr_pct, 2),
        vol_warning=(atr_pct >= 2.5),
    )


def generate_ko_section(results: list) -> str:
    eligible = []
    for r in results:
        md        = r["data"]
        sc        = r.get("best_score") or {"pct": 0}
        direction = r.get("best_direction", "LONG")
        pct       = sc.get("pct", 0)
        ko        = calc_ko_params(md, direction, pct)
        if ko:
            eligible.append((r, ko, pct))
    eligible.sort(key=lambda x: x[2], reverse=True)
    if not eligible:
        return ""

    cards_html = ""
    for r, ko, pct in eligible:
        inst   = r["instrument"]
        sym    = inst["symbol"]
        name   = inst["name"]
        col, _ = rating_color(pct)
        dc, _, dlabel = dir_style(ko["direction"])
        fp     = fmt_price
        em     = EMOJI.get(sym, "&#128202;")
        vol_warn = (
            '<div class="ko-warn">&#9888; Hohe Volatilitaet - Hebel reduzieren</div>'
            if ko["vol_warning"] else ""
        )
        dir_label = "Long" if ko["direction"] == "LONG" else "Short"
        tr_url    = "https://app.traderepublic.com/search?q=" + name.replace(" ", "+") + "+KO+" + dir_label

        fields = (
            '<div class="ko-grid">'
            + '<div class="ko-field"><div class="ko-label">EMPF. HEBEL</div>'
            + '<div class="ko-val" style="color:' + col + '">' + ko["lever_label"] + '</div></div>'
            + '<div class="ko-field"><div class="ko-label">MAX. HALTEDAUER</div>'
            + '<div class="ko-val" style="color:' + col + '">' + str(ko["max_days"]) + ' Tage</div></div>'
            + '<div class="ko-field"><div class="ko-label">KO-ABSTAND MIND.</div>'
            + '<div class="ko-val" style="color:#ffd740">' + str(ko["min_dist_pct"]) + '%</div></div>'
            + '<div class="ko-field"><div class="ko-label">BEISPIEL KO-NIVEAU</div>'
            + '<div class="ko-val" style="color:#ffd740">' + fp(ko["ko_level"]) + '</div></div>'
            + '<div class="ko-field"><div class="ko-label">STOP-LOSS (' + str(ko["stop_pct"]) + '%)</div>'
            + '<div class="ko-val" style="color:#f44336">' + fp(ko["stop_lvl"]) + '</div></div>'
            + '<div class="ko-field"><div class="ko-label">ATR VOLAT.</div>'
            + '<div class="ko-val" style="color:#aaa">' + str(ko["atr_pct"]) + '%</div></div>'
            + '<div class="ko-field"><div class="ko-label">TP1 (+' + str(ko["tp1_pct"]) + '%)</div>'
            + '<div class="ko-val" style="color:#00e676">' + fp(ko["tp1"]) + '</div></div>'
            + '<div class="ko-field"><div class="ko-label">TP2 (+' + str(ko["tp2_pct"]) + '%)</div>'
            + '<div class="ko-val" style="color:#00b060">' + fp(ko["tp2"]) + '</div></div>'
            + '</div>'
        )
        cards_html += (
            '<div class="ko-card">'
            + '<div class="ko-head">'
            + '<div><span class="ko-sym">' + em + ' ' + name + '</span>'
            + '<span class="ko-sub">' + sym + ' &middot; Kurs: ' + fp(ko["price"]) + '</span></div>'
            + '<div class="ko-badges">'
            + '<span class="ko-badge" style="color:' + dc + '">' + dlabel + '</span>'
            + '<span class="ko-badge" style="color:' + col + '">' + str(pct) + '%</span>'
            + '</div></div>'
            + fields
            + '<a href="' + tr_url + '" target="_blank" class="ko-tr-btn">'
            + '&#128269; Bei Trade Republic suchen &#8594;'
            + '</a>'
            + vol_warn
            + '<div class="ko-rules">'
            + 'Stop-Loss direkt nach Kauf setzen &middot; '
            + 'Kein Halten ueber Nacht bei Hebel &gt;6 &middot; '
            + 'Max. 25% KO-Budget pro Position'
            + '</div>'
            + '</div>'
        )

    return (
        '<div class="ko-section">'
        + '<div class="ko-section-head">'
        + '<div class="ko-section-title">&#128202; KO-SCHEINE</div>'
        + '<div class="ko-section-sub">Automatisch aus Screener-Signalen &middot; '
        + 'Nur Signale &ge;50% &middot; Keine Anlageberatung</div>'
        + '</div>'
        + '<div class="ko-cards">' + cards_html + '</div>'
        + '<div class="ko-disclaimer">'
        + '&sup1; KO-Niveau Beispielwert - Schein auf Trade Republic suchen und Produktblatt pruefen.<br>'
        + '&sup2; Finanzierungskosten beachten - ideal max. 4-6 Wochen.<br>'
        + '&sup3; Verluste im sonstigen Verlustverrechnungstopf (verrechenbar mit ETF-Gewinnen).'
        + '</div></div>'
    )


def analyse_long(md: MarketData, seasonal: int, score: dict) -> dict:
    pct = score["pct"]
    st, ri = [], []
    if md.above_ema200: st.append("Kurs ueber EMA200 - intakter Aufwaertstrend")
    else:               ri.append("Kurs unter EMA200 - kein Bull-Regime")
    if md.near_ema50:
        st.append("EMA50-Pullback (" + str(round(md.dist_ema50, 1)) + "%) - ideale Einstiegszone")
    elif md.dist_ema50 and md.dist_ema50 > 5:
        ri.append("Kurs " + str(round(md.dist_ema50, 1)) + "% ueber EMA50 - zu weit ausgedehnt")
    elif md.dist_ema50 and md.dist_ema50 < -5:
        ri.append("Kurs " + str(round(abs(md.dist_ema50), 1)) + "% unter EMA50 - moeglicher Trendbruch")
    if md.rsi:
        if md.rsi_in_range_long: st.append("RSI " + str(round(md.rsi)) + " - neutrale Zone")
        elif md.rsi > 70:        ri.append("RSI " + str(round(md.rsi)) + " ueberkauft - Korrekturrisiko")
        elif md.rsi < 30:        ri.append("RSI " + str(round(md.rsi)) + " ueberverkauft - Trendbruchgefahr")
    if md.low_bb_width:  st.append("BB komprimiert - Ausbruch vorbereitet")
    else:                ri.append("BB ausgedehnt - Bewegung laeuft bereits")
    if md.high_volume and md.volume_ratio:
        st.append("Volumen " + str(round(md.volume_ratio, 1)) + "x - Bestaetigung vorhanden")
    elif md.volume_ratio and md.volume_ratio < 0.7:
        ri.append("Volumen " + str(round(md.volume_ratio, 1)) + "x - schwache Ueberzeugung")
    if md.candle_bullish: st.append("Bullishes Muster (" + md.candle_name + ")")
    else:                 ri.append("Kein bullishes Muster (" + md.candle_name + ")")
    if seasonal >= 65:    st.append("Saisonal " + str(seasonal) + "% bullish - Rueckenwind")
    elif seasonal < 50:   ri.append("Saisonal nur " + str(seasonal) + "% bullish - Gegenwind")
    return _build_result(md, pct, st, ri, seasonal, "LONG")


def analyse_short(md: MarketData, seasonal: int, score: dict) -> dict:
    pct = score["pct"]
    st, ri = [], []
    if md.below_ema200: st.append("Kurs unter EMA200 - intakter Abwaertstrend")
    else:               ri.append("Kurs ueber EMA200 - kein Bear-Regime")
    if md.near_ema50_from_above:
        st.append("Kurs nahe EMA50 von oben - Short-Pullback-Zone")
    elif md.dist_ema50 and md.dist_ema50 < -5:
        ri.append("Kurs zu weit gefallen - kein Short-Einstieg")
    if md.rsi:
        if md.rsi_in_range_short: st.append("RSI " + str(round(md.rsi)) + " - Short-guenstige Zone")
        elif md.rsi > 70:         st.append("RSI " + str(round(md.rsi)) + " ueberkauft - Umkehrsignal fuer Short")
        elif md.rsi < 35:         ri.append("RSI " + str(round(md.rsi)) + " ueberverkauft - Short zu spaet")
    if md.low_bb_width:  st.append("BB komprimiert - Ausbruch nach unten moeglich")
    else:                ri.append("BB ausgedehnt - Bewegung laeuft bereits")
    if md.high_volume and md.volume_ratio:
        st.append("Volumen " + str(round(md.volume_ratio, 1)) + "x - Bestaetigung vorhanden")
    elif md.volume_ratio and md.volume_ratio < 0.7:
        ri.append("Volumen schwach - keine Ueberzeugung")
    if md.candle_bearish: st.append("Bearisches Muster (" + md.candle_name + ")")
    else:                 ri.append("Kein bearisches Muster (" + md.candle_name + ")")
    if seasonal <= 45:    st.append("Saisonal nur " + str(seasonal) + "% bullish - Short-Rueckenwind")
    elif seasonal >= 65:  ri.append("Saisonal " + str(seasonal) + "% bullish - Gegenwind fuer Short")
    return _build_result(md, pct, st, ri, seasonal, "SHORT")


def _build_result(md, pct, st, ri, seasonal, direction):
    is_short = direction == "SHORT"
    if pct >= 80:   emp, et = ("EINSTEIGEN", "Signale bestaetigen sich - hohes Setup-Vertrauen.")
    elif pct >= 65: emp, et = ("BEOBACHTEN", "Solides Setup, auf finale Bestaetigung warten.")
    elif pct >= 45: emp, et = ("WARTEN",     "Einzelne Signale vorhanden, Bild uneinheitlich.")
    else:           emp, et = ("MEIDEN",     "Zu viele Gegenindikationen.")
    ec  = {"EINSTEIGEN": "#00e676", "BEOBACHTEN": "#ffd740", "WARTEN": "#ff9100", "MEIDEN": "#f44336"}[emp]
    sp  = 1.5 if (md.atr_pct or 100) < 40 else 2.5
    crv = 2.5 if pct >= 75 else (2.0 if pct >= 60 else 1.5)
    zp  = sp * crv
    if is_short:
        stop_t = ("Ueber EMA50 (" + str(round(md.ema50)) + ") / +" + str(sp) + "%") if md.ema50 else ("+" + str(sp) + "%")
        ziel_t = "-" + str(zp) + "% vom Einstieg"
    else:
        stop_t = ("Unter EMA50 (" + str(round(md.ema50)) + ") / -" + str(sp) + "%") if md.ema50 else ("-" + str(sp) + "%")
        ziel_t = "+" + str(zp) + "% vom Einstieg"
    ak = sum([
        md.above_ema200 if not is_short else md.below_ema200,
        md.near_ema50 if not is_short else md.near_ema50_from_above,
        md.rsi_in_range_long if not is_short else md.rsi_in_range_short,
        md.low_bb_width, md.high_volume,
        md.candle_bullish if not is_short else md.candle_bearish,
        (seasonal >= 65) if not is_short else (seasonal <= 45)
    ])
    if pct >= 75:   q = str(ak) + "/7 Signale aktiv. Trend und Timing zeigen in dieselbe Richtung."
    elif pct >= 55: q = str(ak) + "/7 Signale aktiv. Potenzial vorhanden, nicht alle Bedingungen erfuellt."
    else:           q = "Nur " + str(ak) + "/7 Signale aktiv. Kein klares Setup erkennbar."
    return dict(q=q, st=st[:3], ri=ri[:3], emp=emp, et=et, ec=ec,
                stop=stop_t, ziel=ziel_t, crv=str(crv) + ":1", direction=direction)


def generate_report(results: list, output_path: str = None) -> str:
    now = datetime.now()
    top = next((r for r in results if r.get("best_score") and r["best_score"]["pct"] >= 60), None)

    cards = ""
    for r in results:
        inst      = r["instrument"]
        md        = r["data"]
        seasonal  = r["seasonal"]
        sym       = inst["symbol"]
        itype     = inst.get("type", "")
        direction = r.get("best_direction", "LONG")
        sc        = r.get("best_score") or {"pct": 0}
        sl        = r.get("score_long")
        ss        = r.get("score_short")
        pct       = sc["pct"]
        col, bg   = rating_color(pct)
        dc, dbg, dlabel = dir_style(direction)
        tc        = TYPE_COLOR.get(itype, "#888")

        mx = ""
        if md:
            dist_str = ""
            if md.dist_ema50 is not None:
                dist_str = ("+" if md.dist_ema50 >= 0 else "") + str(round(md.dist_ema50, 2)) + "%"
            for lb, vl, ok in [
                ("KURS",       fmt_price(md.price),                                          True),
                ("RSI(14)",    str(round(md.rsi, 1)) if md.rsi else "N/A",                  md.rsi_in_range_long if direction == "LONG" else md.rsi_in_range_short),
                ("EMA50 DIST", dist_str or "N/A",                                            md.near_ema50 if direction == "LONG" else md.near_ema50_from_above),
                ("EMA200",     "BULL &#10003;" if md.above_ema200 else "BEAR &#10007;",      md.above_ema200 if direction == "LONG" else md.below_ema200),
                ("BB-BREITE",  str(round(md.bb_width_pct)) + ". Pz." if md.bb_width_pct else "N/A", md.low_bb_width),
                ("ATR",        str(round(md.atr_pct)) + ". Pz." if md.atr_pct else "N/A",  (md.atr_pct or 100) < 60),
                ("VOL RATIO",  str(round(md.volume_ratio, 2)) + "x" if md.volume_ratio else "N/A", md.high_volume),
                ("KERZE",      md.candle_name,                                               md.candle_bullish if direction == "LONG" else md.candle_bearish),
                ("SAISON",     str(seasonal) + "%",                                          seasonal >= 65 if direction == "LONG" else seasonal <= 45),
            ]:
                mc  = "#00e676" if ok else "#666"
                bg2 = "rgba(0,230,118,0.07)" if ok else "rgba(255,255,255,0.03)"
                mx += (
                    '<div class="metric" style="border-color:' + mc + '22;background:' + bg2 + '">'
                    + '<div class="ml">' + lb + '</div>'
                    + '<div class="mv" style="color:' + mc + '">' + vl + '</div></div>'
                )

        if md:
            if direction == "LONG":
                bd = (sbadge(md.above_ema200, "EMA200") + sbadge(md.near_ema50, "EMA50")
                    + sbadge(md.rsi_in_range_long, "RSI") + sbadge(md.low_bb_width, "BB")
                    + sbadge(md.high_volume, "VOL") + sbadge(md.candle_bullish, "KERZE")
                    + sbadge(seasonal >= 65, "SAISON"))
            else:
                bd = (sbadge(md.below_ema200, "EMA200&#9660;") + sbadge(md.near_ema50_from_above, "EMA50&#9660;")
                    + sbadge(md.rsi_in_range_short, "RSI&#9650;") + sbadge(md.low_bb_width, "BB")
                    + sbadge(md.high_volume, "VOL") + sbadge(md.candle_bearish, "KERZE&#9660;")
                    + sbadge(seasonal <= 45, "SAISON&#9660;"))
        else:
            bd = ""

        score_cmp = ""
        if sl and ss:
            score_cmp = (
                '<div class="sc-row">'
                '<span style="color:#00e676">&#9650; LONG ' + str(sl["pct"]) + '%</span>'
                '<span style="color:#666">vs</span>'
                '<span style="color:#f44336">&#9660; SHORT ' + str(ss["pct"]) + '%</span>'
                '</div>'
            )

        lv = r.get("levels", {})
        lvhtml = ""
        if lv and md:
            def fv(v):
                if v is None: return "-"
                return f"{v:,.0f}".replace(",", ".") if v > 999 else f"{v:.2f}"
            arr = "&#9650;" if direction != "SHORT" else "&#9660;"
            lvhtml = (
                '<div class="lv-panel">'
                '<div class="lv-title">HANDELSNIVEAUS</div>'
                '<div class="lv-grid">'
                '<div class="lv-row"><span class="lv-label">Einstieg</span>'
                '<span class="lv-val" style="color:#e0e0e0">' + fv(lv["entry"]) + '</span>'
                '<span class="lv-pct"></span></div>'
                '<div class="lv-row"><span class="lv-label">' + arr + ' Stop-Loss</span>'
                '<span class="lv-val" style="color:#f44336">' + fv(lv["stop"]) + '</span>'
                '<span class="lv-pct" style="color:#f44336">-' + str(round(lv["stop_pct"], 1)) + '%</span></div>'
                '<div class="lv-row"><span class="lv-label">' + arr + ' Take Profit 1</span>'
                '<span class="lv-val" style="color:#00e676">' + fv(lv["tp1"]) + '</span>'
                '<span class="lv-pct" style="color:#00e676">+' + str(round(lv["tp1_pct"], 1)) + '% CRV ' + str(lv["crv1"]) + ':1</span></div>'
                '<div class="lv-row"><span class="lv-label">' + arr + ' Take Profit 2</span>'
                '<span class="lv-val" style="color:#00b060">' + fv(lv["tp2"]) + '</span>'
                '<span class="lv-pct" style="color:#00b060">+' + str(round(lv["tp2_pct"], 1)) + '% CRV ' + str(lv["crv2"]) + ':1</span></div>'
                '<div class="lv-row"><span class="lv-label">Positionsgroesse</span>'
                '<span class="lv-val" style="color:#ffd740">' + str(lv["pos_size"]) + '%</span>'
                '<span class="lv-pct" style="color:#888">bei 1% Kapitalrisiko</span></div>'
                '</div></div>'
            )

        ab = ""
        if md and sc["pct"] > 0:
            a = analyse_long(md, seasonal, sl) if direction == "LONG" else analyse_short(md, seasonal, ss)
            sl_li = "".join("<li>" + x + "</li>" for x in a["st"])
            ri_li = "".join("<li>" + x + "</li>" for x in a["ri"])
            ab = (
                '<details class="ad"><summary>Analyse einblenden</summary>'
                '<div class="ab">'
                '<div class="as"><div class="al">SETUP-QUALITAET</div><p>' + a["q"] + '</p></div>'
                '<div class="ac">'
                '<div><div class="al">STAERKEN</div><ul>' + sl_li + '</ul></div>'
                '<div><div class="al">RISIKEN</div><ul>' + ri_li + '</ul></div>'
                '</div>'
                '<div class="ae" style="border-color:' + a["ec"] + '44;background:' + a["ec"] + '08">'
                '<strong style="color:' + a["ec"] + '">' + a["emp"] + '</strong>'
                '<span style="color:#aaa;font-size:12px"> - ' + a["et"] + '</span>'
                '</div>'
                '<div class="ar"><div class="al">RISIKOMANAGEMENT</div>'
                '<div class="rr"><span>Stop-Loss:</span><span style="color:#ff9100">' + a["stop"] + '</span></div>'
                '<div class="rr"><span>Ziel 1:</span><span style="color:#00e676">' + a["ziel"] + '</span></div>'
                '<div class="rr"><span>CRV:</span><span style="color:#ffd740">' + a["crv"] + '</span></div>'
                '</div></div></details>'
            )

        em = EMOJI.get(sym, "&#128202;")
        cards += (
            '<div class="card" id="c-' + sym + '">'
            '<div class="ch">'
            '<div class="ct"><span style="font-size:18px">' + em + '</span>'
            '<div><div class="sym">' + sym + '</div>'
            '<div class="nm">' + inst["name"] + ' <span style="color:' + tc + ';font-size:10px">' + itype + '</span></div>'
            + ('<div class="pr">' + fmt_price(md.price) + '</div>' if md else '')
            + '</div></div>'
            '<div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px">'
            '<div class="rb" style="color:' + col + ';background:' + bg + ';border-color:' + col + '44">' + r["rating"] + '</div>'
            '<div class="dir-badge" style="color:' + dc + ';background:' + dbg + ';border-color:' + dc + '44">' + dlabel + '</div>'
            '</div></div>'
            '<div class="sw"><div class="st"><div class="sf" style="width:' + str(pct) + '%;background:' + col + '"></div></div>'
            '<div class="sr"><span style="color:#888;font-size:11px">SCORE</span>'
            '<span style="color:' + col + ';font-size:14px;font-weight:bold">' + str(pct) + '%</span></div></div>'
            + score_cmp
            + '<div class="badges">' + bd + '</div>'
            + ('<div class="mg">' + mx + '</div>' if mx else '')
            + lvhtml + ab
            + '</div>'
        )

    tb = ""
    if top:
        ts   = top["instrument"]["symbol"]
        tp   = top["best_score"]["pct"]
        td   = top.get("best_direction", "LONG")
        tc2, _, tl = dir_style(td)
        col2, _    = rating_color(tp)
        em2  = EMOJI.get(ts, "&#128202;")
        tb = (
            '<div class="tb">'
            '<span style="font-size:20px">' + em2 + '</span>'
            '<div>'
            '<div style="color:' + col2 + ';font-size:10px;letter-spacing:.1em">STAERKSTES SIGNAL</div>'
            '<div style="color:#e0e0e0;font-size:15px;font-weight:bold">'
            + top["instrument"]["name"] + ' (' + ts + ') '
            + '<span style="color:' + tc2 + '">' + tl + '</span> - ' + str(tp) + '%'
            + '</div></div>'
            '<a href="#c-' + ts + '" style="margin-left:auto;color:' + col2 + ';font-size:11px;'
            'text-decoration:none;border:1px solid ' + col2 + '44;padding:4px 12px;border-radius:3px">'
            '&#9660; DETAIL</a>'
            '</div>'
        )

    type_leg = "".join(
        '<span style="color:' + v + ';font-size:11px;margin-right:12px">&#9632; ' + k + '</span>'
        for k, v in TYPE_COLOR.items()
    )

    ko_section = generate_ko_section(results)

    legend_items = "".join(
        '<div style="display:flex;align-items:center;gap:5px">'
        '<span style="width:8px;height:8px;border-radius:50%;background:' + c + ';display:inline-block"></span>'
        '<span style="color:#aaa;font-size:11px">' + l + '</span></div>'
        for c, l in [
            ("#00e676", "STARK &ge;80%"), ("#ffd740", "MODERAT 60%"),
            ("#ff9100", "SCHWACH 40%"),   ("#888",    "KEIN SIGNAL")
        ]
    )

    css = """*{box-sizing:border-box;margin:0;padding:0}
body{background:#0a0a0a;color:#d0d0d0;font-family:'Courier New',monospace;padding:22px;max-width:1100px;margin:0 auto;line-height:1.5;font-size:13px}
.hdr{border-bottom:1px solid rgba(255,255,255,0.08);padding-bottom:14px;margin-bottom:20px}
.hr{display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:10px}
.brand{color:#00e676;font-size:10px;letter-spacing:.22em;margin-bottom:4px}
h1{color:#ffffff;font-size:20px;letter-spacing:.04em}
.sub{color:#888;font-size:11px;margin-top:3px}
.di{color:#888;font-size:11px;text-align:right;line-height:1.8}
.tb{background:rgba(0,230,118,0.04);border:1px solid rgba(0,230,118,0.15);border-radius:7px;padding:12px 16px;margin-bottom:18px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.fi{background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:5px;padding:10px 14px;margin-bottom:18px}
.ft{color:#aaa;font-size:10px;letter-spacing:.15em;margin-bottom:8px}
.ftags{display:flex;gap:5px;flex-wrap:wrap}
.ftag{padding:3px 9px;border-radius:3px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);color:#aaa;font-size:10px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:11px}
.card{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:8px;padding:14px}
.ch{display:flex;justify-content:space-between;margin-bottom:10px}
.ct{display:flex;align-items:flex-start;gap:9px}
.sym{color:#fff;font-size:14px;font-weight:bold}
.nm{color:#aaa;font-size:11px;margin-top:1px}
.pr{color:#ccc;font-size:12px;margin-top:3px}
.rb{padding:3px 8px;border-radius:3px;font-size:10px;letter-spacing:.07em;border:1px solid}
.dir-badge{padding:3px 8px;border-radius:3px;font-size:10px;font-weight:bold;letter-spacing:.05em;border:1px solid}
.sw{margin-bottom:6px}
.st{height:4px;background:rgba(255,255,255,0.08);border-radius:2px;overflow:hidden}
.sf{height:100%;border-radius:2px}
.sr{display:flex;justify-content:space-between;margin-top:4px}
.sc-row{display:flex;gap:10px;font-size:11px;font-family:monospace;margin-bottom:8px;padding:4px 8px;background:rgba(255,255,255,0.03);border-radius:3px}
.badges{display:flex;gap:3px;flex-wrap:wrap;margin-bottom:9px}
.badge{padding:2px 7px;border-radius:3px;font-size:10px;border:1px solid;letter-spacing:.03em}
.mg{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin-bottom:9px}
.metric{border-radius:4px;padding:6px 8px;border:1px solid}
.ml{color:#888;font-size:9px;letter-spacing:.1em;margin-bottom:2px}
.mv{font-size:12px;font-weight:bold}
.ad summary{color:#aaa;font-size:11px;cursor:pointer;letter-spacing:.05em;padding:5px 0;list-style:none;user-select:none}
.ad[open] summary::before{content:"\\25BC "}
.ad summary::before{content:"\\25B6 ";color:#00e676;font-size:8px}
.ab{margin-top:9px;padding-top:9px;border-top:1px solid rgba(255,255,255,0.06);font-size:12px}
.al{color:#00e676;font-size:10px;letter-spacing:.1em;margin-bottom:4px}
.as{margin-bottom:9px}
.as p{color:#bbb;line-height:1.6;font-family:Georgia,serif;font-size:13px}
.ac{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-bottom:9px}
.ac ul{padding-left:13px;color:#aaa;line-height:1.7;font-family:Georgia,serif;font-size:12px}
.ae{padding:7px 11px;border-radius:4px;border:1px solid;margin-bottom:9px}
.ar{background:rgba(255,255,255,0.02);border-radius:4px;padding:7px 11px;border:1px solid rgba(255,255,255,0.06)}
.rr{display:flex;justify-content:space-between;padding:2px 0;font-size:12px;color:#888}
.lv-panel{background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.08);border-radius:5px;padding:10px 12px;margin-bottom:9px}
.lv-title{color:#00e676;font-size:10px;letter-spacing:.12em;margin-bottom:7px}
.lv-grid{display:flex;flex-direction:column;gap:4px}
.lv-row{display:flex;justify-content:space-between;align-items:center;font-size:11px}
.lv-label{color:#888;flex:1}
.lv-val{color:#ccc;font-weight:bold;text-align:right;min-width:60px}
.lv-pct{color:#888;font-size:10px;text-align:right;min-width:90px}
.hint{margin-top:16px;background:rgba(0,230,118,0.02);border:1px solid rgba(0,230,118,0.10);border-radius:6px;padding:12px 16px}
.hint-t{color:#00e676;font-size:10px;letter-spacing:.12em;margin-bottom:5px}
.hint p{color:#aaa;font-size:12px;line-height:1.7;font-family:Georgia,serif}
.leg{margin-top:16px;padding:10px 14px;border:1px solid rgba(255,255,255,0.06);border-radius:5px;display:flex;gap:14px;flex-wrap:wrap;align-items:center}
.disc{margin-top:11px;color:#666;font-size:10px;line-height:1.7}
.ko-section{margin-top:32px;border-top:2px solid rgba(255,215,64,0.15);padding-top:22px}
.ko-section-head{margin-bottom:16px}
.ko-section-title{color:#ffd740;font-size:16px;font-weight:bold;letter-spacing:.1em;margin-bottom:5px}
.ko-section-sub{color:#888;font-size:11px}
.ko-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px;margin-bottom:14px}
.ko-card{background:rgba(255,215,64,0.02);border:1px solid rgba(255,215,64,0.12);border-radius:8px;padding:16px}
.ko-head{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,0.06)}
.ko-sym{color:#fff;font-size:13px;font-weight:bold;display:block}
.ko-sub{color:#888;font-size:11px;margin-top:2px;display:block}
.ko-badges{display:flex;gap:5px;align-items:center}
.ko-badge{padding:3px 9px;border-radius:3px;font-size:10px;font-weight:bold;border:1px solid rgba(255,255,255,0.2);letter-spacing:.05em}
.ko-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-bottom:12px}
.ko-field{background:rgba(255,255,255,0.03);border-radius:4px;padding:9px 11px}
.ko-label{color:#888;font-size:10px;letter-spacing:.08em;margin-bottom:4px}
.ko-val{font-size:14px;font-weight:bold}
.ko-tr-btn{display:block;text-align:center;padding:9px;background:rgba(255,215,64,0.08);border:1px solid rgba(255,215,64,0.30);border-radius:4px;color:#ffd740;font-size:12px;font-weight:bold;text-decoration:none;margin-bottom:9px;letter-spacing:.05em}
.ko-warn{color:#ff6b35;font-size:11px;padding:7px 11px;background:rgba(255,107,53,0.07);border:1px solid rgba(255,107,53,0.2);border-radius:4px;margin-bottom:9px}
.ko-rules{color:#888;font-size:10px;padding-top:9px;border-top:1px solid rgba(255,255,255,0.05);line-height:1.9}
.ko-disclaimer{color:#666;font-size:10px;line-height:1.9;padding:10px 14px;background:rgba(255,255,255,0.01);border-radius:4px;border:1px solid rgba(255,255,255,0.04)}"""

    ftags = "".join(
        '<span class="ftag">' + f + '</span>'
        for f in [
            "&#9312; EMA200 Regime", "&#9313; EMA50 Pullback", "&#9314; RSI Zone",
            "&#9315; BB-Kompression", "&#9316; Volumen", "&#9317; Kerzenmuster", "&#9318; Saisonalitaet"
        ]
    )

    html = (
        '<!DOCTYPE html><html lang="de"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Swing Trade Screener - ' + now.strftime("%d.%m.%Y") + '</title>'
        '<style>' + css + '</style></head><body>'
        '<div class="hdr"><div class="hr">'
        '<div><div class="brand">SWING TRADE SCREENER</div>'
        '<h1>SWING TRADE SCREENER</h1>'
        '<div class="sub">Live-Daten &middot; Yahoo Finance &middot; Long &amp; Short &middot; '
        + str(len(results)) + ' Instrumente</div></div>'
        '<div class="di">Erstellt: ' + now.strftime("%d.%m.%Y %H:%M") + '<br>'
        'Yahoo Finance (~15 Min. Verzoegerung)</div>'
        '</div></div>'
        + tb
        + '<div class="fi"><div class="ft">SIGNAL-FILTEREBENEN (LONG &amp; SHORT)</div>'
        '<div class="ftags">' + ftags + '</div>'
        '<div style="margin-top:10px">' + type_leg + '</div></div>'
        '<div class="grid">' + cards + '</div>'
        + ko_section
        + '<div class="hint"><div class="hint-t">&#128161; VERTIEFTE ANALYSE IN CLAUDE</div>'
        '<p>Report in <strong style="color:#ccc">claude.ai</strong> hochladen:<br>'
        '<em>Analysiere das beste Signal und gib eine konkrete Handelsstrategie mit Einstieg, Stop und Ziel.</em>'
        '</p></div>'
        '<div class="leg">' + legend_items
        + '<div style="margin-left:auto;display:flex;gap:10px">'
        '<span style="color:#00e676;font-size:11px;font-weight:bold">&#9650; LONG</span>'
        '<span style="color:#f44336;font-size:11px;font-weight:bold">&#9660; SHORT</span>'
        '</div></div>'
        '<div class="disc">'
        'Positionsgroesse = Kapital x 1% Risiko / Abstand Stop-Loss. Richtwert, keine Empfehlung.<br>'
        '&#9888; Keine Anlageberatung. Historische Wahrscheinlichkeiten sind keine Garantie. Daten via Yahoo Finance.'
        '</div>'
        '</body></html>'
    )

    if output_path is None:
        output_path = "report_" + now.strftime("%Y%m%d_%H%M") + ".html"
    Path(output_path).write_text(html, encoding="utf-8")
    return output_path
