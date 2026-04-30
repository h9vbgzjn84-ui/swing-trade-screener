"""
report_generator.py – HTML-Report mit Long/Short Signalen
Wortmann & Wember GmbH · Swing Trade Screener
"""

from datetime import datetime
from pathlib import Path
from engine import MarketData

EMOJI = {
    "SPX":"📈","DJI":"🏛️","DAX":"🇩🇪","NQ":"💻","SX5E":"🇪🇺","NKY":"🗾",
    "GOLD":"🥇","WTI":"🛢️","BRENT":"⛽","SILBER":"🪙","KUPFER":"🔶","BTC":"₿",
}

TYPE_COLOR = {
    "Index":    "#4fc3f7",
    "Rohstoff": "#ffb74d",
    "Krypto":   "#ce93d8",
}

def rating_color(pct):
    if pct >= 80: return "#00e676","rgba(0,230,118,0.10)"
    if pct >= 60: return "#ffd740","rgba(255,215,64,0.10)"
    if pct >= 40: return "#ff9100","rgba(255,145,0,0.10)"
    return "#555","rgba(80,80,80,0.08)"

def dir_style(direction):
    if direction == "LONG":
        return "#00e676","rgba(0,230,118,0.10)","▲ LONG"
    return "#f44336","rgba(244,67,54,0.10)","▼ SHORT"

def fmt_price(p):
    if p is None: return "–"
    return f"{p:,.0f}".replace(",",".") if p > 999 else f"{p:.2f}"

def sbadge(active, label, invert=False):
    on  = active if not invert else not active
    c   = "#00e676" if on else "#2a2a2a"
    bg  = "rgba(0,230,118,0.08)" if on else "rgba(255,255,255,0.02)"
    return f'<span class="badge" style="color:{c};background:{bg};border-color:{c}44">{"●" if on else "○"} {label}</span>'


def analyse_long(md: MarketData, seasonal: int, score: dict) -> dict:
    pct = score["pct"]
    st, ri = [], []
    if md.above_ema200: st.append("Kurs über EMA200 – intakter Aufwärtstrend")
    else:               ri.append("Kurs unter EMA200 – kein Bull-Regime")
    if md.near_ema50:   st.append(f"EMA50-Pullback ({md.dist_ema50:+.1f}%) – ideale Einstiegszone")
    elif md.dist_ema50 and md.dist_ema50 > 5: ri.append(f"Kurs {md.dist_ema50:.1f}% über EMA50 – zu weit ausgedehnt")
    elif md.dist_ema50 and md.dist_ema50 < -5: ri.append(f"Kurs {abs(md.dist_ema50):.1f}% unter EMA50 – möglicher Trendbruch")
    if md.rsi:
        if md.rsi_in_range_long: st.append(f"RSI {md.rsi:.0f} – neutrale Zone, kein Extremwert")
        elif md.rsi > 70:        ri.append(f"RSI {md.rsi:.0f} überkauft – Korrekturrisiko")
        elif md.rsi < 30:        ri.append(f"RSI {md.rsi:.0f} überverkauft – Trendbruchgefahr")
    if md.low_bb_width:  st.append(f"BB komprimiert ({md.bb_width_pct:.0f}. Pz.) – Ausbruch vorbereitet")
    else:                ri.append(f"BB ausgedehnt ({md.bb_width_pct:.0f}. Pz.) – Bewegung läuft bereits")
    if md.high_volume and md.volume_ratio: st.append(f"Volumen {md.volume_ratio:.1f}x – Bestätigung vorhanden")
    elif md.volume_ratio and md.volume_ratio < 0.7: ri.append(f"Volumen {md.volume_ratio:.1f}x – schwache Überzeugung")
    if md.candle_bullish: st.append(f"Bullishes Muster ({md.candle_name})")
    else:                 ri.append(f"Kein bullishes Muster ({md.candle_name})")
    if seasonal >= 65:    st.append(f"Saisonal {seasonal}% bullish – Rückenwind")
    elif seasonal < 50:   ri.append(f"Saisonal nur {seasonal}% bullish – Gegenwind")
    return _build_result(md, pct, st, ri, seasonal, "LONG")


def analyse_short(md: MarketData, seasonal: int, score: dict) -> dict:
    pct = score["pct"]
    st, ri = [], []
    if md.below_ema200: st.append("Kurs unter EMA200 – intakter Abwärtstrend")
    else:               ri.append("Kurs über EMA200 – kein Bear-Regime")
    if md.near_ema50_from_above: st.append(f"Kurs nahe EMA50 von oben ({md.dist_ema50:+.1f}%) – Short-Pullback-Zone")
    elif md.dist_ema50 and md.dist_ema50 < -5: ri.append(f"Kurs {abs(md.dist_ema50):.1f}% unter EMA50 – zu weit gefallen, kein Einstieg")
    if md.rsi:
        if md.rsi_in_range_short: st.append(f"RSI {md.rsi:.0f} – erhöhte Zone im Downtrend, Short-günstig")
        elif md.rsi > 70:         st.append(f"RSI {md.rsi:.0f} überkauft – Umkehrsignal für Short")
        elif md.rsi < 35:         ri.append(f"RSI {md.rsi:.0f} überverkauft – Short zu spät, Rebound möglich")
    if md.low_bb_width:  st.append(f"BB komprimiert ({md.bb_width_pct:.0f}. Pz.) – Ausbruch nach unten möglich")
    else:                ri.append(f"BB ausgedehnt ({md.bb_width_pct:.0f}. Pz.) – Bewegung läuft bereits")
    if md.high_volume and md.volume_ratio: st.append(f"Volumen {md.volume_ratio:.1f}x – Bestätigung vorhanden")
    elif md.volume_ratio and md.volume_ratio < 0.7: ri.append(f"Volumen {md.volume_ratio:.1f}x – schwache Überzeugung")
    if md.candle_bearish: st.append(f"Bearisches Muster ({md.candle_name})")
    else:                 ri.append(f"Kein bearisches Muster ({md.candle_name})")
    if seasonal <= 45:    st.append(f"Saisonal nur {seasonal}% bullish – Short-Rückenwind")
    elif seasonal >= 65:  ri.append(f"Saisonal {seasonal}% bullish – Gegenwind für Short")
    return _build_result(md, pct, st, ri, seasonal, "SHORT")


def _build_result(md, pct, st, ri, seasonal, direction):
    is_short = direction == "SHORT"
    if pct >= 80:   emp, et = ("EINSTEIGEN","Signale bestätigen sich – hohes Setup-Vertrauen.")
    elif pct >= 65: emp, et = ("BEOBACHTEN","Solides Setup, auf finale Bestätigung warten.")
    elif pct >= 45: emp, et = ("WARTEN",    "Einzelne Signale vorhanden, Bild uneinheitlich.")
    else:           emp, et = ("MEIDEN",    "Zu viele Gegenindikationen.")
    ec = {"EINSTEIGEN":"#00e676","BEOBACHTEN":"#ffd740","WARTEN":"#ff9100","MEIDEN":"#f44336"}[emp]
    sp = 1.5 if (md.atr_pct or 100) < 40 else 2.5
    crv = 2.5 if pct >= 75 else (2.0 if pct >= 60 else 1.5)
    zp  = sp * crv
    if is_short:
        stop_t = f"Über EMA50 ({md.ema50:.0f}) / +{sp:.1f}%" if md.ema50 else f"+{sp:.1f}%"
        ziel_t = f"-{zp:.1f}% vom Einstieg"
    else:
        stop_t = f"Unter EMA50 ({md.ema50:.0f}) / -{sp:.1f}%" if md.ema50 else f"-{sp:.1f}%"
        ziel_t = f"+{zp:.1f}% vom Einstieg"
    ak = sum([md.above_ema200 if not is_short else md.below_ema200,
              md.near_ema50 if not is_short else md.near_ema50_from_above,
              md.rsi_in_range_long if not is_short else md.rsi_in_range_short,
              md.low_bb_width, md.high_volume,
              md.candle_bullish if not is_short else md.candle_bearish,
              (seasonal >= 65) if not is_short else (seasonal <= 45)])
    if pct >= 75:   q = f"{ak}/7 Signale aktiv. Trend und Timing zeigen in dieselbe Richtung."
    elif pct >= 55: q = f"{ak}/7 Signale aktiv. Potenzial vorhanden, nicht alle Bedingungen erfüllt."
    else:           q = f"Nur {ak}/7 Signale aktiv. Kein klares Setup erkennbar."
    return dict(q=q, st=st[:3], ri=ri[:3], emp=emp, et=et, ec=ec,
                stop=stop_t, ziel=ziel_t, crv=f"{crv:.1f}:1", direction=direction)


def generate_report(results: list, output_path: str = None) -> str:
    now = datetime.now()
    top = next((r for r in results if r.get("best_score") and r["best_score"]["pct"] >= 60), None)

    cards = ""
    for r in results:
        inst     = r["instrument"]
        md       = r["data"]
        seasonal = r["seasonal"]
        sym      = inst["symbol"]
        itype    = inst.get("type","")
        direction= r.get("best_direction","LONG")
        sc       = r.get("best_score") or {"pct":0}
        sl       = r.get("score_long")
        ss       = r.get("score_short")
        pct      = sc["pct"]
        col, bg  = rating_color(pct)
        dc, dbg, dlabel = dir_style(direction)
        tc       = TYPE_COLOR.get(itype,"#888")

        # Metriken
        mx = ""
        if md:
            for lb,vl,ok in [
                ("KURS",       fmt_price(md.price),                              True),
                ("RSI(14)",    f"{md.rsi:.1f}" if md.rsi else "N/A",            md.rsi_in_range_long if direction=="LONG" else md.rsi_in_range_short),
                ("EMA50 DIST", f"{md.dist_ema50:+.2f}%" if md.dist_ema50 else "N/A", md.near_ema50 if direction=="LONG" else md.near_ema50_from_above),
                ("EMA200",     "BULL ✓" if md.above_ema200 else "BEAR ✗",       md.above_ema200 if direction=="LONG" else md.below_ema200),
                ("BB-BREITE",  f"{md.bb_width_pct:.0f}. Pz." if md.bb_width_pct else "N/A", md.low_bb_width),
                ("ATR",        f"{md.atr_pct:.0f}. Pz." if md.atr_pct else "N/A", (md.atr_pct or 100)<60),
                ("VOL RATIO",  f"{md.volume_ratio:.2f}x" if md.volume_ratio else "N/A", md.high_volume),
                ("KERZE",      md.candle_name,                                   md.candle_bullish if direction=="LONG" else md.candle_bearish),
                ("SAISON",     f"{seasonal}%",                                   seasonal>=65 if direction=="LONG" else seasonal<=45),
            ]:
                mc = "#00e676" if ok else "#444"
                mx += f'<div class="metric" style="border-color:{mc}22;background:{"rgba(0,230,118,0.07)" if ok else "rgba(255,255,255,0.02)"}"><div class="ml">{lb}</div><div class="mv" style="color:{mc}">{vl}</div></div>'

        # Badges
        if md:
            if direction == "LONG":
                bd = "".join([
                    sbadge(md.above_ema200,"EMA200"), sbadge(md.near_ema50,"EMA50"),
                    sbadge(md.rsi_in_range_long,"RSI"), sbadge(md.low_bb_width,"BB"),
                    sbadge(md.high_volume,"VOL"), sbadge(md.candle_bullish,"KERZE"),
                    sbadge(seasonal>=65,"SAISON"),
                ])
            else:
                bd = "".join([
                    sbadge(md.below_ema200,"EMA200↓"), sbadge(md.near_ema50_from_above,"EMA50↓"),
                    sbadge(md.rsi_in_range_short,"RSI↑"), sbadge(md.low_bb_width,"BB"),
                    sbadge(md.high_volume,"VOL"), sbadge(md.candle_bearish,"KERZE↓"),
                    sbadge(seasonal<=45,"SAISON↓",invert=False),
                ])
        else:
            bd = ""

        # Score-Vergleich Long vs Short
        score_cmp = ""
        if sl and ss:
            score_cmp = f"""<div class="sc-row">
              <span style="color:#00e676">▲ LONG {sl['pct']}%</span>
              <span style="color:#444">vs</span>
              <span style="color:#f44336">▼ SHORT {ss['pct']}%</span>
            </div>"""


        # Levels-Panel
        lv = r.get("levels", {})
        lvhtml = ""
        if lv and md:
            fp = md.price
            def fv(v):
                if v is None: return "–"
                return f"{v:,.0f}".replace(",",".") if v > 999 else f"{v:.2f}"
            is_s = direction == "SHORT"
            lvhtml = f"""<div class="lv-panel">
              <div class="lv-title">HANDELSNIVEAUS</div>
              <div class="lv-grid">
                <div class="lv-row">
                  <span class="lv-label">Einstieg</span>
                  <span class="lv-val" style="color:#e0e0e0">{fv(lv["entry"])}</span>
                  <span class="lv-pct"></span>
                </div>
                <div class="lv-row">
                  <span class="lv-label">{'▲' if not is_s else '▼'} Stop-Loss</span>
                  <span class="lv-val" style="color:#f44336">{fv(lv["stop"])}</span>
                  <span class="lv-pct" style="color:#f44336">-{lv["stop_pct"]:.1f}%</span>
                </div>
                <div class="lv-row">
                  <span class="lv-label">{'▲' if not is_s else '▼'} Take Profit 1</span>
                  <span class="lv-val" style="color:#00e676">{fv(lv["tp1"])}</span>
                  <span class="lv-pct" style="color:#00e676">+{lv["tp1_pct"]:.1f}% · CRV {lv["crv1"]}:1</span>
                </div>
                <div class="lv-row">
                  <span class="lv-label">{'▲' if not is_s else '▼'} Take Profit 2</span>
                  <span class="lv-val" style="color:#00b060">{fv(lv["tp2"])}</span>
                  <span class="lv-pct" style="color:#00b060">+{lv["tp2_pct"]:.1f}% · CRV {lv["crv2"]}:1</span>
                </div>
                <div class="lv-row lv-pos">
                  <span class="lv-label">Positionsgröße ¹</span>
                  <span class="lv-val" style="color:#ffd740">{lv["pos_size"]}%</span>
                  <span class="lv-pct" style="color:#555">bei 1% Kapitalrisiko</span>
                </div>
              </div>
            </div>"""

        # Analyse
        ab = ""
        if md and sc["pct"] > 0:
            a = analyse_long(md, seasonal, sl) if direction=="LONG" else analyse_short(md, seasonal, ss)
            sl_li = "".join(f"<li>{x}</li>" for x in a["st"])
            ri_li = "".join(f"<li>{x}</li>" for x in a["ri"])
            ab = f"""<details class="ad"><summary>Analyse einblenden</summary><div class="ab">
              <div class="as"><div class="al">SETUP-QUALITÄT</div><p>{a["q"]}</p></div>
              <div class="ac"><div><div class="al">STÄRKEN</div><ul>{sl_li}</ul></div>
              <div><div class="al">RISIKEN</div><ul>{ri_li}</ul></div></div>
              <div class="ae" style="border-color:{a["ec"]}44;background:{a["ec"]}08">
                <strong style="color:{a["ec"]}">{a["emp"]}</strong>
                <span style="color:#777;font-size:11px"> — {a["et"]}</span></div>
              <div class="ar"><div class="al">RISIKOMANAGEMENT</div>
                <div class="rr"><span>Stop-Loss:</span><span style="color:#ff9100">{a["stop"]}</span></div>
                <div class="rr"><span>Ziel 1:</span><span style="color:#00e676">{a["ziel"]}</span></div>
                <div class="rr"><span>CRV:</span><span style="color:#ffd740">{a["crv"]}</span></div>
              </div></div></details>"""

        cards += f"""<div class="card" id="c-{sym}">
          <div class="ch">
            <div class="ct"><span style="font-size:16px">{EMOJI.get(sym,"📊")}</span>
              <div><div class="sym">{sym}</div>
                <div class="nm">{inst["name"]} <span style="color:{tc};font-size:8px">{itype}</span></div>
                {f'<div class="pr">{fmt_price(md.price)}</div>' if md else ""}
              </div>
            </div>
            <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px">
              <div class="rb" style="color:{col};background:{bg};border-color:{col}44">{r["rating"]}</div>
              <div class="dir-badge" style="color:{dc};background:{dbg};border-color:{dc}44">{dlabel}</div>
            </div>
          </div>
          <div class="sw"><div class="st"><div class="sf" style="width:{pct}%;background:{col}"></div></div>
            <div class="sr"><span style="color:#2a2a2a;font-size:9px">SCORE</span>
            <span style="color:{col};font-size:13px;font-weight:bold">{pct}%</span></div></div>
          {score_cmp}
          <div class="badges">{bd}</div>
          {f'<div class="mg">{mx}</div>' if mx else ""}
          {lvhtml}
          {ab}
        </div>"""

    # Top-Banner
    tb = ""
    if top:
        ts = top["instrument"]["symbol"]
        tp = top["best_score"]["pct"]
        td = top.get("best_direction","LONG")
        tc2, _, tl = dir_style(td)
        col2,_ = rating_color(tp)
        tb = f'<div class="tb"><span style="font-size:20px">{EMOJI.get(ts,"📊")}</span><div><div style="color:{col2};font-size:8px;letter-spacing:.1em">STÄRKSTES SIGNAL</div><div style="color:#e0e0e0;font-size:14px;font-weight:bold">{top["instrument"]["name"]} ({ts}) <span style="color:{tc2}">{tl}</span> — {tp}%</div></div><a href="#c-{ts}" style="margin-left:auto;color:{col2};font-size:10px;text-decoration:none;border:1px solid {col2}44;padding:4px 12px;border-radius:3px">↓ DETAIL</a></div>'

    # Typ-Gruppen Legende
    type_leg = "".join(f'<span style="color:{v};font-size:9px;margin-right:12px">■ {k}</span>' for k,v in TYPE_COLOR.items())

    html = f"""<!DOCTYPE html><html lang="de"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Swing Trade Screener – {now.strftime("%d.%m.%Y")}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#070707;color:#ccc;font-family:'Courier New',monospace;padding:22px;max-width:1100px;margin:0 auto;line-height:1.4}}
.hdr{{border-bottom:1px solid rgba(255,255,255,0.05);padding-bottom:14px;margin-bottom:20px}}
.hr{{display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:10px}}
.brand{{color:#00e676;font-size:8px;letter-spacing:.22em;margin-bottom:4px}}
h1{{color:#e0e0e0;font-size:19px;letter-spacing:.04em}}
.sub{{color:#1e1e1e;font-size:9px;margin-top:3px}}
.di{{color:#222;font-size:9px;text-align:right;line-height:1.8}}
.tb{{background:rgba(0,230,118,0.03);border:1px solid rgba(0,230,118,0.12);border-radius:7px;padding:12px 16px;margin-bottom:18px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}}
.fi{{background:rgba(255,255,255,0.01);border:1px solid rgba(255,255,255,0.04);border-radius:5px;padding:10px 14px;margin-bottom:18px}}
.ft{{color:#1c1c1c;font-size:7px;letter-spacing:.15em;margin-bottom:8px}}
.ftags{{display:flex;gap:5px;flex-wrap:wrap}}
.ftag{{padding:3px 9px;border-radius:3px;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);color:#2e2e2e;font-size:9px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:11px}}
.card{{background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:8px;padding:14px}}
.ch{{display:flex;justify-content:space-between;margin-bottom:10px}}
.ct{{display:flex;align-items:flex-start;gap:9px}}
.sym{{color:#ddd;font-size:13px;font-weight:bold}}
.nm{{color:#333;font-size:9px;margin-top:1px}}
.pr{{color:#555;font-size:11px;margin-top:3px}}
.rb{{padding:3px 8px;border-radius:3px;font-size:8px;letter-spacing:.07em;border:1px solid}}
.dir-badge{{padding:3px 8px;border-radius:3px;font-size:9px;font-weight:bold;letter-spacing:.05em;border:1px solid}}
.sw{{margin-bottom:6px}}
.st{{height:3px;background:rgba(255,255,255,0.05);border-radius:2px;overflow:hidden}}
.sf{{height:100%;border-radius:2px}}
.sr{{display:flex;justify-content:space-between;margin-top:4px}}
.sc-row{{display:flex;gap:10px;font-size:10px;font-family:monospace;margin-bottom:8px;padding:4px 8px;background:rgba(255,255,255,0.02);border-radius:3px}}
.badges{{display:flex;gap:3px;flex-wrap:wrap;margin-bottom:9px}}
.badge{{padding:2px 6px;border-radius:3px;font-size:9px;border:1px solid;letter-spacing:.03em}}
.mg{{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin-bottom:9px}}
.metric{{border-radius:4px;padding:6px 8px;border:1px solid}}
.ml{{color:#2a2a2a;font-size:7px;letter-spacing:.1em;margin-bottom:2px}}
.mv{{font-size:11px;font-weight:bold}}
.ad summary{{color:#2a2a2a;font-size:9px;cursor:pointer;letter-spacing:.08em;padding:5px 0;list-style:none;user-select:none}}
.ad summary::before{{content:"▶ ";color:#00e676;font-size:7px}}
.ad[open] summary::before{{content:"▼ "}}
.ab{{margin-top:9px;padding-top:9px;border-top:1px solid rgba(255,255,255,0.04);font-size:12px}}
.al{{color:#00e676;font-size:8px;letter-spacing:.1em;margin-bottom:4px;font-family:'Courier New',monospace}}
.as{{margin-bottom:9px}} .as p{{color:#888;line-height:1.6;font-family:Georgia,serif}}
.ac{{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-bottom:9px}}
.ac ul{{padding-left:13px;color:#777;line-height:1.7;font-family:Georgia,serif}}
.ae{{padding:7px 11px;border-radius:4px;border:1px solid;margin-bottom:9px}}
.ar{{background:rgba(255,255,255,0.02);border-radius:4px;padding:7px 11px;border:1px solid rgba(255,255,255,0.05)}}
.rr{{display:flex;justify-content:space-between;padding:2px 0;font-size:11px;color:#444}}
.hint{{margin-top:16px;background:rgba(0,230,118,0.02);border:1px solid rgba(0,230,118,0.08);border-radius:6px;padding:12px 16px}}
.hint-t{{color:#00e676;font-size:8px;letter-spacing:.12em;margin-bottom:5px}}
.hint p{{color:#2a2a2a;font-size:11px;line-height:1.7;font-family:Georgia,serif}}
.leg{{margin-top:16px;padding:10px 14px;border:1px solid rgba(255,255,255,0.03);border-radius:5px;display:flex;gap:14px;flex-wrap:wrap;align-items:center}}
.disc{{margin-top:11px;color:#161616;font-size:8px;line-height:1.6}}
</style></head><body>
<div class="hdr"><div class="hr">
  <div><div class="brand">WORTMANN &amp; WEMBER GMBH</div>
    <h1>SWING TRADE SCREENER</h1>
    <div class="sub">Live-Daten · Yahoo Finance · Long &amp; Short · {len(results)} Instrumente</div>
  </div>
  <div class="di">Erstellt: {now.strftime("%d.%m.%Y %H:%M")}<br>Yahoo Finance (~15 Min. Verzögerung)</div>
</div></div>
{tb}
<div class="fi">
  <div class="ft">SIGNAL-FILTEREBENEN (LONG &amp; SHORT)</div>
  <div class="ftags">
    {"".join(f'<span class="ftag">{f}</span>' for f in ["① EMA200 Regime (Bull/Bear)","② EMA50 Pullback","③ RSI Zone","④ BB-Kompression","⑤ Volumen","⑥ Kerzenmuster","⑦ Saisonalität (Bonus)"])}
  </div>
  <div style="margin-top:10px">{type_leg}</div>
</div>
<div class="grid">{cards}</div>
<div class="hint"><div class="hint-t">💡 VERTIEFTE KI-ANALYSE IN CLAUDE</div>
  <p>Diesen Report in <strong style="color:#444">claude.ai</strong> hochladen und fragen:<br>
  <em>"Analysiere das beste Signal und gib eine konkrete Handelsstrategie mit Einstieg, Stop und Ziel."</em></p>
</div>
<div class="leg">
  {"".join(f'<div style="display:flex;align-items:center;gap:5px"><span style="width:6px;height:6px;border-radius:50%;background:{c};display:inline-block"></span><span style="color:#282828;font-size:8px">{l}</span></div>' for c,l in [("#00e676","STARK ≥80%"),("#ffd740","MODERAT 60%"),("#ff9100","SCHWACH 40%"),("#555","KEIN SIGNAL")])}
  <div style="margin-left:auto;display:flex;gap:10px">
    <span style="color:#00e676;font-size:9px;font-weight:bold">▲ LONG</span>
    <span style="color:#f44336;font-size:9px;font-weight:bold">▼ SHORT</span>
  </div>
</div>
<div class="disc">¹ Positionsgröße = Kapital × 1% Risiko ÷ Abstand Stop-Loss. Richtwert, keine Empfehlung.<br>⚠ Keine Anlageberatung. Historische Wahrscheinlichkeiten sind keine Garantie. Daten via Yahoo Finance.</div>
</body></html>"""

    if output_path is None:
        output_path = f"report_{now.strftime('%Y%m%d_%H%M')}.html"
    Path(output_path).write_text(html, encoding="utf-8")
    return output_path
