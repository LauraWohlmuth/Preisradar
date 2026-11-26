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


def text(fragment):
    t = re.sub(r"<svg.*?</svg>", "", fragment, flags=re.S)
    t = re.sub(r"<[^>]+>", "|", t)
    t = html.unescape(t)
    t = re.sub(r"\s+", " ", t)
    return re.sub(r"(\|\s*)+", "| ", t)


def geizhals_angebote(seite, quelle):
    """Liest die Angebotsliste von geizhals: Händler, Preis, Versand, Verfügbarkeit, Gutschein."""
    starts = [m.start() for m in re.finditer(r'<div\s+class="offer offer--[^"]*"\s+id="offer-index-\d+"', seite)]
    angebote = []
    for i, st in enumerate(starts):
        block = seite[st: starts[i + 1] if i + 1 < len(starts) else st + 80000]
        klasse = re.search(r'class="offer ([^"]*)"', block).group(1)
        preis_m = re.search(r'class="gh_price">([^<]+)<', block)
        haendler_m = re.search(r'data-merchant-name="([^"]+)"', block)
        if not preis_m or not haendler_m:
            continue
        t = text(block)
        a = {"haendler": html.unescape(haendler_m.group(1)), "preis": euro(preis_m.group(1)), "via": "geizhals.de"}
        link = re.search(r'href="(https://geizhals\.de/redir/[^"]+)"', block)
        a["url"] = html.unescape(link.group(1)) if link else quelle["url"]
        if "GRATISVERSAND" in t.upper() or re.search(r"versandkostenfrei", t, re.I):
            a["versand"] = 0.0
        else:
            v = re.search(r"Versand[^|€]{0,30}€\s?([\d.,]+)|€\s?([\d.,]+)\s?Versand", t)
            a["versand"] = euro(v.group(1) or v.group(2)) if v else None
        a["versand_bekannt"] = a["versand"] is not None
        a["gesamtpreis"] = round(a["preis"] + (a["versand"] or 0), 2)
        lief = re.search(r"Onlineshop:\|\s*([^|]+)", t) or re.search(r"\|\s*((?:nicht )?lagernd[^|]*|Lieferzeit[^|]*|[^|]*Werktage[^|]*)", t)
        a["lieferung"] = lief.group(1).strip() if lief else None
        a["verfuegbar"] = "offer--available" in klasse
        stand = re.search(r"Preis vom:\|\s*([\d.]+, [\d:]+)", t)
        a["preis_stand"] = stand.group(1) if stand else None
        a["variante_ok"] = "MDHE4D" in block
        a["netzteil_dabei"] = False if re.search(r"kein Netzteil|ohne Netzteil", t, re.I) else None
        code = re.search(r'data-coupon-code="([^"]+)"', block)
        if code:
            beschr = re.search(r"Gutschein:\s*\|?\s*" + re.escape(code.group(1)) + r"\s*\|?\s*\(([^)]*)\)", t)
            b = beschr.group(1) if beschr else ""
            eur_m = re.search(r"([\d.]+)\s*EURO", b)
            pro_m = re.search(r"([\d.]+)\s*(?:%|PROZENT)", b, re.I)
            bis = re.search(r"gültig bis (\d{4}-\d{2}-\d{2})", b)
            a["gh_code"] = {"code": code.group(1), "rabatt_eur": float(eur_m.group(1)) if eur_m else None,
                            "rabatt_prozent": float(pro_m.group(1)) if pro_m else None,
                            "gueltig_bis": bis.group(1) if bis else None, "beschreibung": b.strip(), "quelle": "geizhals.de"}
        angebote.append(a)
    return angebote


def notebookinfo_angebote(seite, quelle):
    i = seite.find('id="preisvergleich-')
    teil = seite[i: seite.find("</table>", i)] if i >= 0 else ""
    angebote = []
    for zeile in re.findall(r"<tr>(.*?)</tr>", teil, re.S):
        h = re.search(r'aria-label="Zum Anbieter ([^"]+)"', zeile)
        p = re.search(r'<span class="price">([^<]+)<', zeile)
        if not h or not p:
            continue
        t = text(zeile)
        if re.search(r"kostenlose[rn]? Versand|versandkostenfrei", t, re.I):
            versand = 0.0
        else:
            v = re.search(r"([\d.,]+)\s*€?\s*Versand", t)
            versand = euro(v.group(1)) if v else None
        lief = re.search(r'class="shipment-status"><span[^>]*>([^<]+)<', zeile)
        preis = euro(html.unescape(p.group(1)))
        angebote.append({"haendler": html.unescape(h.group(1)), "preis": preis, "versand": versand, "versand_bekannt": versand is not None,
                         "gesamtpreis": round(preis + (versand or 0), 2), "url": quelle["url"] + "#" + teil[:0] + "preisvergleich",
                         "via": quelle["name"], "lieferung": html.unescape(lief.group(1)).strip() if lief else None,
                         "verfuegbar": "shipment-status-instant" in zeile, "variante_ok": True})
    return angebote


def mydealz_deals(seite):
    deals = []
    f = CFG.get("mydealz_filter", {"muss": [], "nicht": []})
    for roh in re.findall(r"data-vue3='(\{\"name\":\"ThreadMainListItemNormalizer\".*?)'", seite):
        try:
            th = json.loads(html.unescape(roh))["props"]["thread"]
        except (ValueError, KeyError):
            continue
        titel = th.get("title", "")
        tl = titel.lower().replace(" ", " ")
        if th.get("isExpired") or th.get("isGone") or th.get("type") != "Deal":
            continue
        if not all(m in tl for m in f["muss"]) or any(n in tl for n in f["nicht"]):
            continue
        deals.append({"titel": titel, "haendler": (th.get("merchant") or {}).get("merchantName"), "preis": th.get("price"),
                      "vorher": th.get("nextBestPrice"), "code": th.get("voucherCode") or None, "temperatur": th.get("temperature"),
                      "veroeffentlicht": dt.datetime.fromtimestamp(th.get("publishedAt", 0), ZoneInfo("Europe/Berlin")).isoformat(timespec="minutes"),
                      "url": th.get("shareableLink") or f"https://www.mydealz.de/deals/{th.get('titleSlug')}-{th.get('threadId')}"})
    return deals


def pruefe(quelle, jetzt):
    if quelle.get("typ") == "blockiert":
        return {"quelle": quelle["name"], "url": quelle["url"], "abgerufen_um": jetzt, "status": "nicht prüfbar", "grund": quelle.get("grund")}, []
    eintrag = {"quelle": quelle["name"], "url": quelle["url"], "abgerufen_um": jetzt}
    try:
        seite = hole(quelle["url"])
    except Exception as e:  # Sperre, Zeitüberschreitung, 403 ...
        eintrag.update(status="nicht prüfbar", grund=f"Seite nicht geladen: {e}")
        return eintrag, []
    if os.environ.get("DEBUG_HTML"):
        os.makedirs(os.path.join(ROOT, "debug"), exist_ok=True)
        open(os.path.join(ROOT, "debug", re.sub(r"[^a-z0-9]+", "-", quelle["name"].lower()) + ".html"), "w", encoding="utf-8").write(seite)
    print(f"[{quelle['name']}] {len(seite)} Zeichen, ld+json-Blöcke: {seite.count('application/ld+json')}, Titel: {re.search(r'<title>(.*?)</title>', seite, re.S).group(1).strip()[:80] if '<title>' in seite else '-'}")
    if quelle.get("typ") == "mydealz":
        deals = mydealz_deals(seite)
        eintrag.update(status="geprüft", grund=f"{len(deals)} aktive Deals zur Variante", deals=deals)
        return eintrag, []
    if "MDHE4D" not in seite and "mdhe4d" not in seite.lower():
        eintrag.update(status="Variante unsicher", grund="Modellnummer MDHE4D/A nicht auf der Seite gefunden")
        return eintrag, []
    if quelle.get("typ") == "notebookinfo":
        angebote = notebookinfo_angebote(seite, quelle)
        if angebote:
            eintrag.update(status="geprüft", tiefstpreis=min(a["gesamtpreis"] for a in angebote), angebote_anzahl=len(angebote))
            return eintrag, angebote
        eintrag.update(status="nicht prüfbar", grund="Angebotsliste auf der Seite nicht erkannt")
        return eintrag, []
    if "geizhals." in quelle["url"]:
        angebote = [a for a in geizhals_angebote(seite, quelle) if a["variante_ok"]]
        verf = [a for a in angebote if a["verfuegbar"]]
        if angebote:
            eintrag.update(status="geprüft", tiefstpreis=min(a["gesamtpreis"] for a in (verf or angebote)),
                           angebote_anzahl=len(angebote), grund=f"{len(verf)} lieferbar")
            return eintrag, verf
        eintrag.update(status="nicht prüfbar", grund="Angebotsliste auf der Seite nicht erkannt")
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


MYDEALZ_CODES = []


def gutscheine_anwenden(angebote, heute):
    """Zieht nur belegte, gültige Codes ab (config.json). Cashback wird getrennt ausgewiesen."""
    for a in angebote:
        a["preis_mit_code"] = a["gesamtpreis"]
        codes = list(CFG.get("gutscheine", [])) + list(MYDEALZ_CODES)
        gh = a.get("gh_code")
        if gh and gh.get("rabatt_eur"):
            # geizhals zeigt bei Gutscheinaktionen mit Betrag schon den Preis MIT Code (geprüft am 26.11. bei notebooksbilliger:
            # Shop 1.149 €, geizhals 1.119 € = mit CLICK2P). Nicht noch einmal abziehen.
            a.update(code=gh["code"], code_bedingung="bei geizhals schon im Preis enthalten; Shoppreis ohne Code " + eur(a["preis"] + gh["rabatt_eur"]),
                     code_quelle="geizhals.de", listenpreis=round(a["preis"] + gh["rabatt_eur"], 2))
            codes = []
        for g in codes:
            if g["haendler"].lower() not in (a["haendler"] or "").lower():
                continue
            if g.get("gueltig_bis") and g["gueltig_bis"] < heute:
                continue
            if a["gesamtpreis"] < g.get("mindestwert", 0):
                continue
            rabatt = g.get("rabatt_eur") or round(a["gesamtpreis"] * (g.get("rabatt_prozent") or 0) / 100, 2)
            if not rabatt:
                continue
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
    for q in quellen:
        for d in q.get("deals", []):
            if d.get("code") and d.get("haendler") and d.get("preis") and d.get("vorher") and d["vorher"] > d["preis"]:
                MYDEALZ_CODES.append({"haendler": d["haendler"].split(".")[0], "code": d["code"], "rabatt_eur": round(d["vorher"] - d["preis"], 2),
                                      "bedingung": "laut mydealz-Deal; im Warenkorb prüfen", "quelle": d["url"]})
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
