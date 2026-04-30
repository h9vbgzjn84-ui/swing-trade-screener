"""
mailer.py – E-Mail-Versand via Resend API
Wortmann & Wember GmbH · Swing Trade Screener
Kein Gmail App-Passwort nötig.
"""

import logging, os, json
from datetime import datetime
from pathlib import Path
try:
    from urllib.request import urlopen, Request
    from urllib.error import URLError
except ImportError:
    pass

log = logging.getLogger(__name__)


def _top(results):
    t = next((r for r in results if r.get("best_score") and r["best_score"]["pct"] >= 60), None)
    return f"Bestes Signal: {t['instrument']['symbol']} {t['best_score']['pct']}%" if t else "Kein Signal ≥60%"


def build_html_body(results):
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    rows = ""
    for r in results:
        sym  = r["instrument"]["symbol"]
        name = r["instrument"]["name"]
        pct  = r["best_score"]["pct"] if r.get("best_score") else 0
        rt   = r["rating"]
        md   = r["data"]
        direction = r.get("best_direction", "LONG")
        pr   = f"{md.price:.2f}" if md else "–"
        c    = {"STARK":"#00e676","MODERAT":"#ffd740","SCHWACH":"#ff9100"}.get(rt,"#555")
        dc   = "#00e676" if direction == "LONG" else "#f44336"
        dl   = "▲ LONG" if direction == "LONG" else "▼ SHORT"

        def d(ok): return "✓" if ok else "✗"
        sig = ""
        if md:
            if direction == "LONG":
                sig = (f"EMA200:{d(md.above_ema200)} EMA50:{d(md.near_ema50)} "
                       f"RSI:{d(md.rsi_in_range_long)} BB:{d(md.low_bb_width)} "
                       f"VOL:{d(md.high_volume)} KERZE:{d(md.candle_bullish)}")
            else:
                sig = (f"EMA200:{d(md.below_ema200)} EMA50:{d(md.near_ema50_from_above)} "
                       f"RSI:{d(md.rsi_in_range_short)} BB:{d(md.low_bb_width)} "
                       f"VOL:{d(md.high_volume)} KERZE:{d(md.candle_bearish)}")

        # Levels
        lv = r.get("levels", {})
        lv_html = ""
        if lv:
            def fv(v):
                if v is None: return "–"
                return f"{v:,.0f}".replace(",",".") if v > 999 else f"{v:.2f}"
            lv_html = f"""
            <tr><td colspan="4" style="padding:4px 11px 8px">
              <div style="background:rgba(255,255,255,0.03);border-radius:4px;padding:8px 10px;font-family:monospace;font-size:10px">
                <span style="color:#444">Einstieg: </span><span style="color:#e0e0e0">{fv(lv.get("entry"))}</span> &nbsp;
                <span style="color:#444">Stop: </span><span style="color:#f44336">{fv(lv.get("stop"))} (-{lv.get("stop_pct",0):.1f}%)</span> &nbsp;
                <span style="color:#444">TP1: </span><span style="color:#00e676">{fv(lv.get("tp1"))} (+{lv.get("tp1_pct",0):.1f}%)</span> &nbsp;
                <span style="color:#444">TP2: </span><span style="color:#00b060">{fv(lv.get("tp2"))} (+{lv.get("tp2_pct",0):.1f}%)</span> &nbsp;
                <span style="color:#444">Pos: </span><span style="color:#ffd740">{lv.get("pos_size",0)}%</span>
              </div>
            </td></tr>"""

        rows += f"""<tr style="border-bottom:1px solid rgba(255,255,255,0.04)">
          <td style="padding:7px 11px;font-weight:bold;color:#e0e0e0">{sym}</td>
          <td style="padding:7px 11px;color:#777">{name}</td>
          <td style="padding:7px 11px;color:#777;font-family:monospace">{pr}</td>
          <td style="padding:7px 11px">
            <span style="color:{c};font-weight:bold">{pct}%</span>
            <span style="color:#444"> · {rt} · </span>
            <span style="color:{dc};font-weight:bold">{dl}</span>
          </td>
        </tr>
        {lv_html}"""

    t = next((r for r in results if r.get("best_score") and r["best_score"]["pct"] >= 60), None)
    tb = ""
    if t:
        ts  = t["instrument"]["symbol"]
        tp  = t["best_score"]["pct"]
        td  = t.get("best_direction","LONG")
        tc  = "#00e676" if tp >= 80 else "#ffd740"
        tdc = "#00e676" if td == "LONG" else "#f44336"
        tdl = "▲ LONG" if td == "LONG" else "▼ SHORT"
        tb  = f'<div style="background:rgba(0,230,118,0.04);border:1px solid rgba(0,230,118,0.15);border-radius:6px;padding:11px 15px;margin-bottom:18px;font-family:monospace"><div style="color:{tc};font-size:8px;letter-spacing:.1em">STÄRKSTES SIGNAL</div><div style="color:#e0e0e0;font-size:14px;font-weight:bold">{t["instrument"]["name"]} ({ts}) <span style="color:{tdc}">{tdl}</span> — {tp}%</div></div>'

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="background:#0a0a0a;color:#ccc;font-family:'Courier New',monospace;padding:22px;max-width:860px;margin:0 auto">
  <div style="border-bottom:1px solid rgba(255,255,255,0.05);padding-bottom:12px;margin-bottom:18px">
    <div style="color:#00e676;font-size:8px;letter-spacing:.22em;margin-bottom:3px">WORTMANN &amp; WEMBER GMBH</div>
    <h1 style="color:#e0e0e0;font-size:17px;margin:0">SWING TRADE SCREENER</h1>
    <div style="color:#2a2a2a;font-size:9px;margin-top:2px">Tagesreport · {now} UTC</div>
  </div>
  {tb}
  <table style="width:100%;border-collapse:collapse;margin-bottom:18px">
    <thead><tr style="border-bottom:1px solid rgba(255,255,255,0.05)">
      {"".join(f'<th style="padding:5px 11px;color:#2a2a2a;font-size:8px;letter-spacing:.1em;text-align:left">{h}</th>' for h in ["SYM","NAME","KURS","SIGNAL"])}
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <div style="color:#1a1a1a;font-size:8px;line-height:1.6;border-top:1px solid rgba(255,255,255,0.04);padding-top:10px">
    ¹ Positionsgröße bei 1% Kapitalrisiko. Keine Anlageberatung. Daten via Yahoo Finance (~15 Min. verzögert).
  </div>
</body></html>"""


def send_report(results, report_path) -> bool:
    api_key = os.environ.get("RESEND_API_KEY", "")
    mail_to = os.environ.get("MAIL_TO", "")
    mail_from = os.environ.get("MAIL_FROM", "screener@resend.dev")

    if not api_key:
        log.warning("RESEND_API_KEY nicht gesetzt – E-Mail übersprungen")
        return False
    if not mail_to:
        log.warning("MAIL_TO nicht gesetzt – E-Mail übersprungen")
        return False

    subject = f"Swing Trade Report – {datetime.now().strftime('%d.%m.%Y')} | {_top(results)}"
    html_body = build_html_body(results)

    # Report als Anhang (base64)
    attachments = []
    rp = Path(report_path)
    if rp.exists():
        import base64
        content = base64.b64encode(rp.read_bytes()).decode()
        attachments = [{"filename": rp.name, "content": content}]

    payload = {
        "from":        mail_from,
        "to":          [mail_to],
        "subject":     subject,
        "html":        html_body,
        "attachments": attachments,
    }

    try:
        log.info(f"Sende E-Mail via Resend an: {mail_to}")
        req = Request(
            "https://api.resend.com/emails",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
            },
            method="POST",
        )
        with urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            log.info(f"  → E-Mail versendet ✓ (ID: {result.get('id','')})")
            return True
    except Exception as e:
        log.error(f"Resend Fehler: {e}")
        return False
