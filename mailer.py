"""
mailer.py – E-Mail-Versand (nur smtplib, kein API-Key nötig)
Wortmann & Wember GmbH · Swing Trade Screener
"""

import smtplib, logging, os
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

log = logging.getLogger(__name__)

def get_cfg():
    return {
        "host": os.environ.get("MAIL_SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.environ.get("MAIL_SMTP_PORT", "587")),
        "user": os.environ.get("MAIL_USER", ""),
        "pw":   os.environ.get("MAIL_PASS", ""),
        "from": os.environ.get("MAIL_FROM", os.environ.get("MAIL_USER", "")),
        "to":   os.environ.get("MAIL_TO", ""),
    }

def _top(results):
    t = next((r for r in results if r.get("score") and r["score"]["pct"] >= 60), None)
    return f"Bestes Signal: {t['instrument']['symbol']} {t['score']['pct']}%" if t else "Kein Signal ≥60%"

def build_body(results):
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    rows = ""
    for r in results:
        sym  = r["instrument"]["symbol"]
        name = r["instrument"]["name"]
        pct  = r["score"]["pct"] if r["score"] else 0
        rt   = r["rating"]
        pr   = f"{r['data'].price:.2f}" if r["data"] else "–"
        c    = {"STARK":"#00e676","MODERAT":"#ffd740","SCHWACH":"#ff9100"}.get(rt,"#555")
        md   = r["data"]
        def d(ok): return "✓" if ok else "✗"
        direction = r.get("best_direction","LONG")
        sig = (f"EMA200:{d(md.above_ema200 if direction=='LONG' else md.below_ema200)} "
               f"EMA50:{d(md.near_ema50 if direction=='LONG' else md.near_ema50_from_above)} "
               f"RSI:{d(md.rsi_in_range_long if direction=='LONG' else md.rsi_in_range_short)} "
               f"BB:{d(md.low_bb_width)} VOL:{d(md.high_volume)} "
               f"KERZE:{d(md.candle_bullish if direction=='LONG' else md.candle_bearish)} "
               f"SAISON:{d(r['seasonal']>=65 if direction=='LONG' else r['seasonal']<=45)}") if md else "–"
        rows += f"""<tr>
          <td style="padding:7px 11px;font-weight:bold;color:#e0e0e0">{sym}</td>
          <td style="padding:7px 11px;color:#777">{name}</td>
          <td style="padding:7px 11px;color:#777;font-family:monospace">{pr}</td>
          <td style="padding:7px 11px"><span style="color:{c};font-weight:bold">{pct}% · {rt}</span></td>
          <td style="padding:7px 11px;font-family:monospace;font-size:10px;color:#444">{sig}</td></tr>"""

    t = next((r for r in results if r.get("score") and r["score"]["pct"] >= 60), None)
    tb = ""
    if t:
        ts = t["instrument"]["symbol"]; tp = t["score"]["pct"]
        tc = "#00e676" if tp >= 80 else "#ffd740"
        tb = f'<div style="background:rgba(0,230,118,0.04);border:1px solid rgba(0,230,118,0.15);border-radius:6px;padding:11px 15px;margin-bottom:18px;font-family:monospace"><div style="color:{tc};font-size:8px;letter-spacing:.1em">STÄRKSTES SIGNAL</div><div style="color:#e0e0e0;font-size:14px;font-weight:bold">{t["instrument"]["name"]} ({ts}) — Score: {tp}%</div></div>'

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="background:#0a0a0a;color:#ccc;font-family:'Courier New',monospace;padding:22px;max-width:800px;margin:0 auto">
  <div style="border-bottom:1px solid rgba(255,255,255,0.05);padding-bottom:12px;margin-bottom:18px">
    <div style="color:#00e676;font-size:8px;letter-spacing:.22em;margin-bottom:3px">WORTMANN &amp; WEMBER GMBH</div>
    <h1 style="color:#e0e0e0;font-size:17px;margin:0">SWING TRADE SCREENER</h1>
    <div style="color:#2a2a2a;font-size:9px;margin-top:2px">Tagesreport · {now}</div>
  </div>
  {tb}
  <table style="width:100%;border-collapse:collapse;margin-bottom:18px">
    <thead><tr style="border-bottom:1px solid rgba(255,255,255,0.05)">
      {"".join(f'<th style="padding:5px 11px;color:#2a2a2a;font-size:8px;letter-spacing:.1em;text-align:left">{h}</th>' for h in ["SYM","NAME","KURS","SCORE","SIGNALE"])}
    </tr></thead><tbody>{rows}</tbody>
  </table>
  <div style="color:#1a1a1a;font-size:8px;line-height:1.6;border-top:1px solid rgba(255,255,255,0.04);padding-top:10px">
    ⚠ Keine Anlageberatung. Vollständiger Report im Anhang. Daten via Yahoo Finance (~15 Min. verzögert).
  </div>
</body></html>"""

    plain = f"SWING TRADE SCREENER – Wortmann & Wember GmbH\n{now}\n\n"
    for r in results:
        sc = r["score"]["pct"] if r["score"] else 0
        plain += f"{r['instrument']['symbol']:6s}  {r['instrument']['name']:12s}  {sc:3d}%  [{r['rating']}]\n"
    plain += f"\n{_top(results)}\nReport im Anhang.\n\nKeine Anlageberatung."
    return plain, html

def send_report(results, report_path):
    cfg = get_cfg()
    missing = [k for k in ("user","pw","to") if not cfg.get(k)]
    if missing:
        log.warning(f"E-Mail übersprungen – fehlende Umgebungsvariablen: MAIL_{', MAIL_'.join(k.upper() for k in missing)}")
        return False

    recipients = [x.strip() for x in cfg["to"].split(",") if x.strip()]
    plain, html_body = build_body(results)

    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"Swing Trade Report – {datetime.now().strftime('%d.%m.%Y')} | {_top(results)}"
    msg["From"]    = cfg["from"]
    msg["To"]      = ", ".join(recipients)

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(plain, "plain", "utf-8"))
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)

    rp = Path(report_path)
    if rp.exists():
        with open(rp, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{rp.name}"')
        msg.attach(part)

    try:
        log.info(f"Sende E-Mail an: {', '.join(recipients)}")
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as s:
            s.ehlo(); s.starttls(); s.login(cfg["user"], cfg["pw"])
            s.sendmail(cfg["from"], recipients, msg.as_string())
        log.info("  → E-Mail versendet ✓")
        return True
    except smtplib.SMTPAuthenticationError:
        log.error("SMTP-Auth fehlgeschlagen – MAIL_USER / MAIL_PASS prüfen. Gmail: App-Passwort verwenden.")
        return False
    except Exception as e:
        log.error(f"E-Mail-Fehler: {e}")
        return False
