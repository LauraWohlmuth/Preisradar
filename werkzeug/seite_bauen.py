#!/usr/bin/env python3
"""Baut aus der Seitenvorlage (gleicher Code wie die Claude-Seite) und den CSVs des Exports
eine eigenständige Webseite für GitHub Pages: python werkzeug/seite_bauen.py <csv-ordner> <ausgabe.html>

Die Daten werden in die Seite eingebettet, d3 kommt von cdnjs. Eine kleine Nachbildung von `dash`
(data, draw, calc, onData) reicht, weil die Seite alles selbst aus den Daten rechnet."""
import csv
import json
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
ordner, ziel = sys.argv[1], sys.argv[2]
NAMEN = {"amazon": "amazon_verlauf"}
IDS = ["angebote", "laeufe", "quellen", "deals", "produkte", "iphone_angebote", "iphone_laeufe", "iphone_quellen",
       "vorgaenger", "blackfriday", "amazon", "codes", "weitere_angebote", "weitere_laeufe", "fahrradcomputer"]
daten = {}
for i in IDS:
    p = os.path.join(ordner, NAMEN.get(i, i) + ".csv")
    if os.path.exists(p):
        daten[i] = [{k: (v if v != "" else None) for k, v in r.items()} for r in csv.DictReader(open(p, encoding="utf-8"))]

seite = open(os.path.join(HIER, "seite_vorlage.html"), encoding="utf-8").read()
# Öffentliche Fassung: kein Name, kein Knopf zum privaten GitHub, keine internen Kennungen
for alt, neu in [("Preisradar · privat für Laura", "Preisradar"),
                 ("Prüft stündlich automatisch. Sofort prüfen: oben rechts „Alle prüfen“.", "Wird stündlich automatisch geprüft."),
                 ("window.PR_SYNC = 'trig_01PYrmiNk7e6yVPpr4eW3CPM';", ""),
                 ("https://github.com/LauraWohlmuth/preisradar/actions/workflows/preise.yml", "#")]:
    seite = seite.replace(alt, neu)

shim = """<script>
window.__DATA = %s;
(function () {
  const draws = [], calcs = {};
  function lauf(n, f, el) {
    try { if (typeof f === 'function') f(el); else { const m = f.mount ? f.mount(el) : undefined; if (f.update) f.update(el, m); } }
    catch (e) { console.error('Zeichnung ' + n + ': ' + e.message); }
  }
  window.dash = {
    colors: ['#5b8def', '#8a96ab', '#c9a96a', '#34d399'],
    data(id) {
      if (calcs[id]) { const c = calcs[id]; return {status: 'ok', data: c.fn(...c.inputs.map((i) => dash.data(i).data))}; }
      const r = window.__DATA[id];
      return r ? {status: 'ok', data: r, columns: Object.keys(r[0] || {})} : {status: 'missing', data: []};
    },
    calc(id, o) { calcs[id] = o; }, loader() {}, onData(f) { f(); }, refresh() {},
    params() { return {}; }, setParams() {}, resetParams() {}, setLink() {},
    draw(name, f) {
      if (f === undefined) { draws.filter(([n]) => n === name).forEach(([n, g]) => document.querySelectorAll('[data-draw="' + n + '"]').forEach((el) => lauf(n, g, el))); return; }
      draws.push([name, f]);
    }
  };
  window.__alleZeichnen = () => draws.forEach(([n, f]) => document.querySelectorAll('[data-draw="' + n + '"]').forEach((el) => lauf(n, f, el)));
})();
</script>""" % json.dumps(daten, ensure_ascii=False)

css = """:root{color-scheme:dark;--color-fg:#e6edf7;--color-fg-muted:#8fa3c2;--color-bg:#05070d;--color-panel:#0b1324;--color-border-line:#1b2a46;--color-ok:#34d399;--color-warn:#fbbf24;--color-bad:#f87171;--cds-gap-xs:4px;--cds-gap-sm:8px;--cds-gap-md:12px;--cds-gap-lg:16px;--cds-gap-xl:24px;--cds-pad-xs:4px;--cds-pad-sm:8px;--cds-pad-md:12px;--cds-pad-lg:16px;--cds-pad-xl:24px;--cds-radius:10px;--cds-font-size-caption:12px;--cds-font-size-body:14px;--cds-font-size-heading:18px;--cds-font-size-title:24px;--cds-font-weight-medium:600;--font-anthropic-sans:system-ui,-apple-system,'Segoe UI',sans-serif;--font-anthropic-serif:Georgia,serif;--cds-text-secondary:#8fa3c2;--cds-chart-grid:#15223a;--cds-chart-axis:#2a3c5f;--cds-chart-muted:#5b6f93;--cds-chart-reference:#64748b;--cds-surface-popover:#0f1a30;--cds-border:#24365a;--cds-shadow-popover:0 4px 12px #000}
body{margin:0;background:#05070d;color:#e6edf7;font:14px system-ui,-apple-system,'Segoe UI',sans-serif}
#alle-pruefen,#alle-pruefen-hinweis{display:none!important}"""

html = ('<!doctype html><html lang="de"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex,nofollow">'
        '<title>Preisradar</title><style>' + css + '</style>' + shim +
        '<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script></head>'
        '<body><div id="dash-root">' + seite + '</div>'
        '<script>window.addEventListener("load",()=>{__alleZeichnen();let t;window.addEventListener("resize",()=>{clearTimeout(t);t=setTimeout(__alleZeichnen,200);});});</script>'
        '</body></html>')
os.makedirs(os.path.dirname(os.path.abspath(ziel)), exist_ok=True)
open(ziel, "w", encoding="utf-8").write(html)
print("Seite gebaut:", ziel, len(html) // 1024, "KB")
