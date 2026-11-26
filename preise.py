#!/usr/bin/env python3
"""Liest Preise von Preisvergleichsseiten und schreibt data/prices.json.

Erfindet nichts: Was nicht gelesen werden kann, wird als "nicht prüfbar" mit Grund gespeichert.
"""
import datetime as dt
import html
import json
import os
import re
import urllib.request
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))
OUT = os.path.join(ROOT, "data", "prices.json")
MD = os.path.join(ROOT, "übersicht.md")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def hole(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def euro(text):
    t = re.sub(r"[^\d,\.]", "", text)
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return round(float(t), 2)
    except ValueError:
        return None


def jsonld_angebote(seite):
    """Liest schema.org-Daten (AggregateOffer / Offer) aus der Seite."""
    treffer = []
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', seite, re.S):
        try:
            daten = json.loads(html.unescape(block))
        except ValueError:
            continue
        stapel = daten if isinstance(daten, list) else [daten]
        while stapel:
            x = stapel.pop()
            if isinstance(x, list):
                stapel.extend(x)
                continue
            if not isinstance(x, dict):
                continue
            stapel.extend(v for v in x.values() if isinstance(v, (dict, list)))
            typ = x.get("@type")
            if typ == "AggregateOffer":
                treffer.append({"art": "aggregat", "tiefst": x.get("lowPrice"), "hoechst": x.get("highPrice"), "anzahl": x.get("offerCount")})
            elif typ == "Offer" and x.get("price") is not None:
                verk = x.get("seller") or {}
                versand = None
                sd = x.get("shippingDetails")
                for s in (sd if isinstance(sd, list) else [sd]):
                    if isinstance(s, dict) and isinstance(s.get("shippingRate"), dict):
                        versand = s["shippingRate"].get("value")
                        break
                treffer.append({"art": "angebot", "preis": x.get("price"), "versand": versand, "haendler": verk.get("name") if isinstance(verk, dict) else None, "url": x.get("url")})
    return treffer


def pruefe(quelle, jetzt):
    eintrag = {"quelle": quelle["name"], "url": quelle["url"], "abgerufen_um": jetzt}
    try:
        seite = hole(quelle["url"])
    except Exception as e:  # Sperre, Zeitüberschreitung, 403 ...
        eintrag.update(status="nicht prüfbar", grund=f"Seite nicht geladen: {e}")
        return eintrag, []
    print(f"[{quelle['name']}] {len(seite)} Zeichen, ld+json-Blöcke: {seite.count('application/ld+json')}, Titel: {re.search(r'<title>(.*?)</title>', seite, re.S).group(1).strip()[:80] if '<title>' in seite else '-'}")
    if "MDHE4D" not in seite and "mdhe4d" not in seite.lower():
        eintrag.update(status="Variante unsicher", grund="Modellnummer MDHE4D/A nicht auf der Seite gefunden")
        return eintrag, []
    daten = jsonld_angebote(seite)
    angebote = []
    for d in daten:
        if d["art"] == "angebot":
            p = euro(str(d["preis"]))
            if p:
                v = euro(str(d["versand"])) if d.get("versand") is not None else None
                angebote.append({"haendler": d.get("haendler") or quelle.get("haendler") or "unbekannt", "preis": p,
                                 "versand": v, "versand_bekannt": v is not None, "gesamtpreis": round(p + (v or 0), 2),
                                 "url": d.get("url") or quelle["url"], "via": quelle["name"]})
    agg = next((d for d in daten if d["art"] == "aggregat" and d.get("tiefst") is not None), None)
    if agg:
        eintrag.update(status="geprüft", tiefstpreis=euro(str(agg["tiefst"])), hoechstpreis=euro(str(agg.get("hoechst") or "")), angebote_anzahl=agg.get("anzahl"))
    elif angebote:
        eintrag.update(status="geprüft", tiefstpreis=min(a["gesamtpreis"] for a in angebote))
    else:
        eintrag.update(status="nicht prüfbar", grund="Keine Preisdaten (schema.org) auf der Seite gefunden")
    return eintrag, angebote


def gutscheine_anwenden(angebote, heute):
    """Zieht nur belegte, gültige Codes ab (config.json). Cashback wird getrennt ausgewiesen."""
    for a in angebote:
        a["preis_mit_code"] = a["gesamtpreis"]
        for g in CFG.get("gutscheine", []):
            if g["haendler"].lower() not in (a["haendler"] or "").lower():
                continue
            if g.get("gueltig_bis") and g["gueltig_bis"] < heute:
                continue
            if a["gesamtpreis"] < g.get("mindestwert", 0):
                continue
            rabatt = g.get("rabatt_eur") or round(a["gesamtpreis"] * g.get("rabatt_prozent", 0) / 100, 2)
            if a["gesamtpreis"] - rabatt < a["preis_mit_code"]:
                a.update(preis_mit_code=round(a["gesamtpreis"] - rabatt, 2), code=g["code"], code_bedingung=g.get("bedingung"), code_quelle=g.get("quelle"))
        for cb in CFG.get("cashback", []):
            if cb["haendler"].lower() in (a["haendler"] or "").lower():
                a["cashback"] = f'{cb["prozent"]} % über {cb["anbieter"]} ({cb.get("hinweis", "")})'
                a["effektiv_mit_cashback"] = round(a["preis_mit_code"] * (1 - cb["prozent"] / 100), 2)
    return angebote


def eur(v):
    if v is None:
        return "–"
    t = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return (t[:-3] if t.endswith(",00") else t) + " €"


def uebersicht(d):
    L = d["laeufe"]
    last = L[-1]
    mit = [l for l in L if l.get("guenstigster")]
    z = []
    zeit = last["zeit"][:16].replace("T", " ")
    z.append("# MacBook-Preisradar\n")
    z.append(f"*{d['produkt']}* · Zielpreis **{eur(d['zielpreis'])}**\n")
    g = last.get("guenstigster")
    if g is None:
        z.append(f"**Stand {zeit}:** Keine Quelle konnte geprüft werden. Details unten.\n")
    else:
        vor = mit[-2]["guenstigster"] if len(mit) > 1 and mit[-1] is last else None
        diff = "" if vor is None else f" ({'+' if g - vor > 0 else ''}{eur(g - vor)} zum Lauf davor)"
        status = "✅ **Zielpreis erreicht!**" if g <= d["zielpreis"] else f"noch {eur(g - d['zielpreis'])} über dem Ziel"
        z.append(f"**Stand {zeit}: günstigster geprüfter Preis {eur(g)}**{diff}, {status}\n")
    if mit:
        ps = [l["guenstigster"] for l in mit]
        z.append(f"Tiefstwert {eur(min(ps))} · Höchstwert {eur(max(ps))} · {len(L)} Läufe seit {L[0]['zeit'][:10]}\n")
    if last.get("angebote"):
        z.append("## Angebote\n")
        z.append("| Händler | Mit Code | Preis | Versand | Code | Cashback (später) |")
        z.append("|---|---:|---:|---:|---|---|")
        for a in last["angebote"]:
            code = f"`{a['code']}` ({a.get('code_bedingung') or ''})" if a.get("code") else "–"
            cb = f"{a['cashback']} → {eur(a['effektiv_mit_cashback'])}" if a.get("cashback") else "–"
            z.append(f"| [{a['haendler']}]({a['url']}) | **{eur(a['preis_mit_code'])}** | {eur(a['preis'])} | {eur(a['versand']) if a.get('versand_bekannt') else 'unbekannt'} | {code} | {cb} |")
        z.append("")
    z.append("## Quellen\n")
    z.append("| Quelle | ab | Status | Hinweis |")
    z.append("|---|---:|---|---|")
    for q in last["quellen"]:
        icon = {"geprüft": "✅", "Variante unsicher": "⚠️"}.get(q["status"], "❌")
        z.append(f"| [{q['quelle']}]({q['url']}) | {eur(q.get('tiefstpreis'))} | {icon} {q['status']} | {q.get('grund') or (str(q.get('angebote_anzahl')) + ' Angebote' if q.get('angebote_anzahl') else '')} |")
    z.append("")
    z.append("## Verlauf\n")
    z.append("| Zeit | günstigster Preis |")
    z.append("|---|---:|")
    for l in reversed(L[-12:]):
        z.append(f"| {l['zeit'][:16].replace('T', ' ')} | {eur(l.get('guenstigster'))} |")
    z.append("")
    z.append("_Preise werden nie geschätzt: Was nicht lesbar war, steht als „nicht prüfbar“ da. Codes nur, wenn belegt und gültig; Cashback zählt nicht zum Preis. Vor dem Kauf im Shop prüfen._\n")
    open(MD, "w", encoding="utf-8").write("\n".join(z))


def main():
    jetzt = dt.datetime.now(ZoneInfo("Europe/Berlin")).isoformat(timespec="seconds")
    alt = {"produkt": CFG["produkt"], "zielpreis": CFG["zielpreis"], "uvp": CFG["uvp"], "laeufe": []}
    if os.path.exists(OUT):
        alt = json.load(open(OUT, encoding="utf-8"))
    quellen, angebote = [], []
    for q in CFG["quellen"]:
        e, a = pruefe(q, jetzt)
        quellen.append(e)
        angebote.extend(a)
    angebote = gutscheine_anwenden(angebote, jetzt[:10])
    preise = [q["tiefstpreis"] for q in quellen if q.get("status") == "geprüft" and q.get("tiefstpreis")]
    preise += [a["preis_mit_code"] for a in angebote]
    preise = [p for p in preise if p >= CFG["warn_unter"]]  # darunter: Fake-Shop-Verdacht, zählt nicht
    lauf = {"zeit": jetzt, "quellen": quellen, "angebote": sorted(angebote, key=lambda a: a["preis_mit_code"]),
            "guenstigster": min(preise) if preise else None}
    vorher = [l["guenstigster"] for l in alt["laeufe"] if l.get("guenstigster")]
    lauf["neuer_tiefstwert"] = bool(lauf["guenstigster"] and (not vorher or lauf["guenstigster"] < min(vorher)))
    lauf["melden"] = bool(lauf["guenstigster"] and (lauf["guenstigster"] <= CFG["zielpreis"] or (vorher and lauf["neuer_tiefstwert"])))
    alt["laeufe"].append(lauf)
    alt["stand"] = jetzt
    json.dump(alt, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    uebersicht(alt)
    print(json.dumps({"guenstigster": lauf["guenstigster"], "melden": lauf["melden"], "quellen": [(q["quelle"], q["status"]) for q in quellen]}, ensure_ascii=False))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"melden={'true' if lauf['melden'] else 'false'}\n")
            f.write(f"preis={lauf['guenstigster'] or ''}\n")


if __name__ == "__main__":
    main()
