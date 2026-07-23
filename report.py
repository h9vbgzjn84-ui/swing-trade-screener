"""
report.py - erzeugt die statische Signaltafel (docs/index.html)
"""

from __future__ import annotations

import html
from pathlib import Path

from signals import Board, MAX_REPORT_AGE_H, de, evaluate, regime, thresholds

CSS = """
:root{
  --papier:#EFF1EC; --karte:#FFFFFF; --linie:#D6DAD1; --tinte:#12171C;
  --grau:#5C6670; --frei:#1F6B54; --ruhe:#4A5560; --boost:#B8791A; --alarm:#A33A2A;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--papier);color:var(--tinte);
  font-family:"IBM Plex Sans",-apple-system,Segoe UI,sans-serif;
  font-size:16px;line-height:1.5;padding:28px 20px 60px;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:960px;margin:0 auto}
.mono{font-family:"IBM Plex Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums}
.disp{font-family:"Barlow Condensed","IBM Plex Sans",sans-serif;text-transform:uppercase;
  letter-spacing:.045em;font-weight:600}

/* Kopf */
header{border-bottom:2px solid var(--tinte);padding-bottom:14px;margin-bottom:8px}
.eyebrow{font-size:12px;letter-spacing:.16em;color:var(--grau);text-transform:uppercase}
h1{font-family:"Barlow Condensed",sans-serif;font-size:clamp(38px,7vw,62px);
  font-weight:700;letter-spacing:.01em;line-height:.95;text-transform:uppercase;margin:4px 0 2px}
.sub{font-size:14px;color:var(--grau)}
.stand{display:flex;flex-wrap:wrap;gap:6px 22px;font-size:13px;color:var(--grau);
  padding:10px 0 22px;border-bottom:1px solid var(--linie);margin-bottom:26px}
.stand b{color:var(--tinte);font-weight:600}
#alt.warn{color:var(--alarm);font-weight:600}
.zone-ok{color:var(--frei)!important}
.zone-warn{color:var(--alarm)!important}

/* Schaltfelder */
.raster{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}
.feld{background:var(--karte);border:1px solid var(--linie);border-left:5px solid var(--ruhe);
  padding:16px 18px 15px;display:flex;flex-direction:column}
.feld.frei{border-left-color:var(--frei)}
.feld.boost{border-left-color:var(--boost)}
.feld .kopf{display:flex;justify-content:space-between;align-items:baseline;gap:12px}
.feld h2{font-family:"Barlow Condensed",sans-serif;font-size:21px;font-weight:600;
  text-transform:uppercase;letter-spacing:.03em}
.fenster{font-size:12.5px;color:var(--grau);white-space:nowrap}
.urteil{font-family:"Barlow Condensed",sans-serif;font-size:clamp(30px,5vw,40px);font-weight:700;
  letter-spacing:.02em;line-height:1.05;margin:10px 0 2px;color:var(--ruhe)}
.frei .urteil{color:var(--frei)}
.boost .urteil{color:var(--boost)}
.grund{font-size:14px;font-weight:500;margin-bottom:8px}
.detail{font-size:13.5px;color:var(--grau);flex:1}
.warnung{font-size:13px;color:var(--alarm);font-weight:500;margin-top:10px;
  padding:8px 10px;background:#FBF0EE;border-left:3px solid var(--alarm)}
.fakten{display:flex;flex-wrap:wrap;gap:4px 16px;margin-top:12px;padding-top:10px;
  border-top:1px solid var(--linie);font-size:12.5px}
.fakten span{color:var(--grau)}
.fakten b{color:var(--tinte);font-weight:600;margin-left:5px}

/* Schwellen */
.block{margin-top:34px}
.block h3{font-family:"Barlow Condensed",sans-serif;font-size:15px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--grau);border-bottom:1px solid var(--linie);
  padding-bottom:7px;margin-bottom:2px}
.zeile{display:flex;align-items:baseline;gap:14px;padding:11px 0;border-bottom:1px solid var(--linie)}
.zeile .nm{font-weight:600;min-width:112px}
.zeile .tx{color:var(--grau);font-size:14px;flex:1}
.zeile .wt{font-size:19px;font-weight:600}
.watch .wt{color:var(--boost)}
.on .wt,.on .nm{color:var(--frei)}
.na .tx{color:var(--alarm)}

/* Regeln */
.regeln{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:0 26px;margin-top:4px}
.regeln li{list-style:none;font-size:13.5px;padding:9px 0;border-bottom:1px solid var(--linie);
  color:var(--grau)}
.regeln li b{color:var(--tinte)}
.nein li b{color:var(--alarm)}
footer{margin-top:30px;font-size:12px;color:var(--grau);line-height:1.6}
@media (prefers-reduced-motion:no-preference){.feld{animation:auf .4s ease both}
  .feld:nth-child(2){animation-delay:.05s}.feld:nth-child(3){animation-delay:.1s}
  .feld:nth-child(4){animation-delay:.15s}
  @keyframes auf{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}}
"""

JS = """
(function(){
  var g = new Date(document.body.dataset.generated);
  var h = (Date.now() - g.getTime())/36e5;
  var el = document.getElementById('alt');
  el.textContent = h < 1 ? 'gerade eben' : Math.round(h) + ' Std. alt';
  if (h > %d) {
    el.classList.add('warn');
    el.textContent += ' \\u2014 Lauf pruefen';
  }
})();
""" % MAX_REPORT_AGE_H

REGELN_JA = [
    ("Long", "ist die einzige Seite mit Rückenwind."),
    ("Daytrading nur in VIX 16\u201323.", "Darunter \u2212100.800 \u20ac, dar\u00fcber \u2212144.800 \u20ac \u2014 au\u00dferhalb halbe Gr\u00f6\u00dfe, nur Einzeleinstiege, weiterer KO-Abstand. Die Regelstrategien oben gelten unabh\u00e4ngig davon."),
    ("VIX ab 25:", "kein Overnight. Intraday bleibt erlaubt, aber reduziert."),
    ("VIX steigt \u00fcber 10\u201315 % im laufenden Trade:", "schlie\u00dfen oder auf Einstand absichern."),
    ("Montag", "ist im Nasdaq und Dow der beste Tag; im DAX liegt Mittwoch gleichauf."),
    ("16\u201317 Uhr", "ist die schwächste Stunde \u2014 Limits legen statt kaufen."),
    ("17\u201318 Uhr", "ist in allen Indizes positiv, aber klein (0,01\u20130,02 %/Tag)."),
    ("Größe", "aus dem Risikobudget, nicht aus dem Bauch."),
    ("Vor FOMC, CPI, NFP", "Größe halbieren, nicht aussetzen."),
]
REGELN_NEIN = [
    ("Keine Gewinnziele", "\u2014 sie kappen die Tage, die alles tragen."),
    ("Keine Kerzenfarben", "\u2014 weder Stunde noch Nacht noch 5\u2011Min\u2011Kerze prognostizieren."),
    ("Mehrtägige Positionen freitags nicht glattstellen", "\u2014 Freitag auf Montag war der bestbezahlte Zeitraum. Gilt für Core und Dip-Overlay, nicht für die Tagesfenster (die sind abends ohnehin flat)."),
    ("Kein MACD, kein RSI\u2011Score", "\u2014 im Split\u2011Sample durchgefallen."),
    ("Kein Overnight", "im Dow und im DAX."),
    ("Neue Regel?", "Erst Split\u2011Sample\u2011Test, dann Geld."),
]


def _feld(c: dict) -> str:
    cls = "boost" if "GRÖSSE" in c["verdict"] else ("frei" if c["free"] else "")
    warn = (f'<p class="warnung">{html.escape(c["warn"])}</p>' if c.get("warn") else "")
    fakten = "".join(
        f'<span>{html.escape(k)}<b class="mono">{html.escape(v)}</b></span>'
        for k, v in c["facts"]
    )
    return f"""
    <article class="feld {cls}">
      <div class="kopf"><h2>{html.escape(c['title'])}</h2>
        <span class="fenster mono">{html.escape(c['window'])}</span></div>
      <p class="urteil">{html.escape(c['verdict'])}</p>
      <p class="grund">{html.escape(c['reason'])}</p>
      <p class="detail">{html.escape(c['detail'])}</p>
      {warn}
      <div class="fakten">{fakten}</div>
    </article>"""


def _zeile(t: dict) -> str:
    wert = f'<span class="wt mono">{html.escape(t["value"])}</span>' if t["value"] else ""
    return f"""<div class="zeile {t['kind']}"><span class="nm">{html.escape(t['name'])}</span>
      <span class="tx">{html.escape(t['text'])}</span>{wert}</div>"""


def generate(board: Board, path: str) -> None:
    cards = evaluate(board)
    schwellen = thresholds(board)
    gen = board.generated_at

    doc = f"""<!doctype html>
<html lang="de"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Signaltafel · {gen:%d.%m.%Y}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>{CSS}</style></head>
<body data-generated="{gen.isoformat()}">
<div class="wrap">
  <header>
    <p class="eyebrow">Index-Regelwerk v2 &middot; validierte Regeln</p>
    <h1>Signaltafel</h1>
    <p class="sub">Was heute erlaubt ist &mdash; und was nicht.</p>
  </header>

  <div class="stand">
    <span>Erstellt <b>{gen:%d.%m.%Y, %H:%M}</b> Uhr</span>
    <span>Stand <b id="alt">&mdash;</b></span>
    <span>Letzter Schluss <b>{board.indices['NQ'].last_close_date:%d.%m.%Y}</b></span>
    <span>VIX <b class="mono">{de(board.vix, 2)}</b> ({board.vix_date:%d.%m.})</span>
    <span>Daytrading-Regime <b class="{'zone-ok' if regime(board.vix)[0]=='GEWINNZONE' else 'zone-warn'}">{regime(board.vix)[0]}</b></span>
  </div>

  <section class="raster">{''.join(_feld(c) for c in cards)}</section>

  <section class="block">
    <h3>Schwellen für heute Abend</h3>
    {''.join(_zeile(t) for t in schwellen)}
  </section>

  <section class="block">
    <h3>Immer gültig</h3>
    <ul class="regeln">{''.join(f'<li><b>{a}</b> {b}</li>' for a, b in REGELN_JA)}</ul>
  </section>

  <section class="block">
    <h3>Beachten</h3>
    <ul class="regeln nein">{''.join(f'<li><b>{a}</b> {b}</li>' for a, b in REGELN_NEIN)}</ul>
  </section>

  <footer>
    Regeln aus Dukascopy-5-Minuten-Daten 2016&ndash;2026, in beiden Zeithälften
    (2016&ndash;21 / 2021&ndash;26) getrennt validiert. Kurse: Yahoo Finance, Tagesschluss.
    VIX: Schluss des Vortages, kein Look-ahead.<br>
    Keine Anlageberatung. Historische Wahrscheinlichkeiten sind keine Garantie.
  </footer>
</div>
<script>{JS}</script>
</body></html>"""

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(doc, encoding="utf-8")
