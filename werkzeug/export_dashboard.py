import json, csv, sys
src, out = sys.argv[1], sys.argv[2]
d = json.load(open(src, encoding="utf-8"))
L = d["laeufe"]; last = L[-1]
seen = {}
for a in sorted(last.get("angebote", []), key=lambda a: a["preis_mit_code"]):
    k = a["haendler"].lower().split(".")[0].split(" ")[0]
    if k in seen: continue
    seen[k] = a
with open(f"{out}/angebote.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["haendler","preis_mit_code","preis","versand","code","code_hinweis","lieferung","cashback","quelle","link"])
    for a in seen.values():
        w.writerow([a["haendler"], a["preis_mit_code"], a["preis"], a["versand"] if a.get("versand_bekannt") else "", a.get("code") or "",
                    a.get("code_bedingung") or "", a.get("lieferung") or "", a.get("cashback") or "", a.get("via"), a.get("url")])
with open(f"{out}/laeufe.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["zeit","guenstigster"])
    for l in L:
        if l.get("guenstigster"): w.writerow([l["zeit"][:16], l["guenstigster"]])
with open(f"{out}/quellen.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["quelle","status","hinweis","link"])
    for q in last["quellen"]:
        w.writerow([q["quelle"], q["status"], q.get("grund") or (f"{q.get('angebote_anzahl')} Angebote" if q.get("angebote_anzahl") else ""), q["url"]])
with open(f"{out}/deals.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["titel","haendler","preis","code","veroeffentlicht","link"])
    for q in last["quellen"]:
        for x in q.get("deals", []):
            w.writerow([x["titel"], x.get("haendler") or "", x.get("preis") or "", x.get("code") or "", x["veroeffentlicht"][:10], x["url"]])
print("stand", last["zeit"], len(seen), "Angebote")


# ---- Zweites Produkt: iPhone 17 Pro refurbished + Kachel-Übersicht ----
import os as _os
def _trend(werte):
    if len(werte) < 2: return "–"
    d = werte[-1] - werte[-2]
    return "↓" if d < -0.5 else ("↑" if d > 0.5 else "→")

def _iphone(out):
    pfad = _os.path.join(_os.path.dirname(src), "prices-iphone-17-pro.json")
    if not _os.path.exists(pfad): return None
    if not _os.path.exists(_os.path.join(_os.path.dirname(_os.path.dirname(src)), "produkte", "iphone-17-pro.json")):
        return None  # iPhone nicht mehr beobachtet (27.11.: durch MacBook refurbished ersetzt)
    d = json.load(open(pfad, encoding="utf-8"))
    if not d["laeufe"]: return None
    last = d["laeufe"][-1]
    cfg = json.load(open(_os.path.join(_os.path.dirname(_os.path.dirname(src)), "produkte", "iphone-17-pro.json"), encoding="utf-8"))
    fokus = "/407262aa/"
    zeilen = []
    gesehen = set()
    neu_format = any("akku" in a for a in last.get("angebote", []))
    for a in last.get("angebote", []):
        u = a.get("url", "")
        if u in gesehen: continue
        gesehen.add(u)
        if neu_format:
            # Jedes Angebot mit ausgelesenem Akku und Zustand
            if "akku" not in a: continue
            lab = f"{a['haendler']}: {a.get('farbe') or '?'}, {a.get('speicher') or '?'}"
            if "offer=20894256" in u: lab = "Dein Angebot: " + lab.split(": ", 1)[1]
            art = "passt" if a.get("passt") else ("optimal" if a.get("zweite_wahl") else "pruefen")
            fehlt = [n for n, f in (("Farbe", "farbe"), ("Speicher", "speicher"), ("Zustand", "zustand"), ("Akku", "akku"))
                     if str(a.get(f) or "").lower() not in {"tiefblau", "silber", "256 gb", "512 gb", "sehr gut", "exzellent", "premium", "neu"}]
            det = {"passt": "erste Wahl: passt mit neuem Akku",
                   "optimal": "zweite Wahl: Akku optimal statt neu, zählt nicht fürs Ziel"}.get(art) or "passt nicht: " + ", ".join(fehlt)
            if a.get("code") and a["preis_mit_code"] < a["gesamtpreis"]:
                det += f" · mit Code {a['code']} (ohne Code " + f"{a['gesamtpreis']:.2f}".replace(".", ",") + " €; im Warenkorb prüfen)"
            zeilen.append([lab, a["preis_mit_code"], art, det, u, a.get("akku") or "nicht angegeben", a.get("zustand") or "nicht angegeben",
                           a.get("speicher") or "", a.get("farbe") or ""])
            continue
        ist_fokus = fokus in u
        passt = any(q["url"].split("?")[0].rstrip("/") in u for q in cfg["quellen"]) and "?offer=" not in u
        if not passt and not ist_fokus: continue
        if ist_fokus:
            lab, art, det, ak, zu = "Dein Angebot: Tiefblau, 256 GB", "passt", "lieferbar", "Neu", "Premium"
        else:
            lab, art, det, ak, zu = a["haendler"], "pruefen", "alter Lauf: Akku nicht ausgelesen", "nicht ausgelesen", "nicht ausgelesen"
        zeilen.append([lab, a["preis_mit_code"], art, det, u, ak, zu, "", ""])
    rang = {"passt": 0, "optimal": 1}
    zeilen.sort(key=lambda z: (rang.get(z[2], 2), z[1]))
    if neu_format:
        # Erst Akku neu, dann Akku optimal; falsche Farben weglassen, von den übrigen nur die 4 günstigsten
        zeilen = [z for z in zeilen if z[2] in rang] + [z for z in zeilen if z[2] not in rang and "Farbe" not in z[3]][:8]
    with open(f"{out}/iphone_angebote.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["label", "preis", "art", "detail", "link", "akku", "zustand", "speicher", "farbe"]); w.writerows(zeilen)
    # Verlauf deines Angebots und Quellenstatus
    with open(f"{out}/iphone_laeufe.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["zeit", "preis"])
        for l_ in d["laeufe"]:
            if any("akku" in a for a in l_.get("angebote", [])):
                x = l_.get("guenstigster")  # günstigstes passendes Angebot mit neuem Akku
            elif neu_format:
                x = None  # alte Läufe kannten nur dein Angebot, nicht das günstigste passende: nicht mischen
            else:
                x = next((a["preis_mit_code"] for a in l_.get("angebote", []) if fokus in a.get("url", "")), None)
            if x is not None: w.writerow([l_["zeit"][:16], x])
    with open(f"{out}/iphone_quellen.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["quelle", "status", "hinweis", "link"])
        for q in last["quellen"]:
            w.writerow([q["quelle"], q["status"], q.get("grund") or (f"{q.get('angebote_anzahl')} Angebote" if q.get("angebote_anzahl") else ""), q["url"]])
    fok = next((z for z in zeilen if z[2] == "passt"), None)
    hist = []
    with open(f"{out}/iphone_laeufe.csv", encoding="utf-8") as f:
        hist = [float(r["preis"]) for r in csv.DictReader(f) if r["preis"]]
    return {"id": "iphone", "name": "iPhone 17 Pro refurbished", "unter": "Tiefblau/Silber · 256/512 GB · Sehr gut+ · Akku neu",
            "preis": fok[1] if fok else "", "haendler": next((n for n in ("refurbed", "Swappie", "Coolblue") if fok and n.lower() in fok[4].lower()), "refurbed"), "ziel": cfg["zielpreis"], "stand": last["zeit"][:16],
            "trend": _trend(hist), "anker": "iphone", "link": fok[4] if fok else ""}

def _macbook():
    laeufe = [l for l in L if l.get("guenstigster")]
    best = sorted(last["angebote"], key=lambda a: a["preis_mit_code"])[0]
    return {"id": "macbook", "name": "MacBook Air 13\" M5", "unter": "16 GB · 512 GB · Mitternacht · neu",
            "preis": best["preis_mit_code"], "haendler": best["haendler"], "ziel": d["zielpreis"], "stand": last["zeit"][:16],
            "trend": _trend([l["guenstigster"] for l in laeufe]), "anker": "kopf", "link": best["url"]}

def _weitere(out):
    """Alle weiteren Produkte aus produkte/*.json (außer iPhone): Kachel, Angebotsliste und Verlauf."""
    import glob as _glob
    basis = _os.path.dirname(_os.path.dirname(src))
    kacheln, zeilen, verlauf = [], [], []
    for cp in sorted(_glob.glob(_os.path.join(basis, "produkte", "*.json"))):
        cfg = json.load(open(cp, encoding="utf-8"))
        pid = cfg.get("id")
        if pid in (None, "iphone-17-pro"):
            continue
        dp = _os.path.join(basis, "data", f"prices-{pid}.json")
        if not _os.path.exists(dp):
            continue
        dd = json.load(open(dp, encoding="utf-8"))
        if not dd["laeufe"]:
            continue
        la = dd["laeufe"][-1]
        ang = sorted([a for a in la.get("angebote", []) if a.get("passt", True)], key=lambda a: (a.get("verfuegbar", True) is False, a["preis_mit_code"]))
        for a in ang:
            det = []
            if a.get("verfuegbar", True) is False: det.append("derzeit ausverkauft")
            if a.get("variante"): det.append(a["variante"])
            if a.get("ausstattung"): det.append(a["ausstattung"])
            if a.get("zustand"): det.append("Zustand " + a["zustand"])
            if a.get("akku") and a["akku"] != "nicht angegeben": det.append("Akku " + a["akku"])
            det.append("Versand " + (f"{a['versand']:.2f} €".replace(".", ",") if a.get("versand") else ("frei" if a.get("versand") == 0 else "unbekannt")))
            if a.get("lieferung"): det.append(a["lieferung"])
            if a.get("code"): det.append(f"mit Code {a['code']}")
            zeilen.append([pid, a["haendler"], a["preis_mit_code"], " · ".join(det), a.get("url", "")])
        for l_ in dd["laeufe"]:
            if l_.get("guenstigster"):
                verlauf.append([pid, l_["zeit"][:16], l_["guenstigster"]])
        best = next((a for a in ang if a.get("verfuegbar", True) is not False), None)
        kurz = cfg.get("kurzname") or cfg["produkt"].split(",")[0].split("(")[0].strip()
        kacheln.append({"id": pid, "name": kurz, "unter": cfg.get("unterzeile", ""),
                        "preis": best["preis_mit_code"] if best else "", "haendler": best["haendler"] if best else "–",
                        "ziel": cfg["zielpreis"], "stand": la["zeit"][:16],
                        "trend": _trend([l_["guenstigster"] for l_ in dd["laeufe"] if l_.get("guenstigster")]),
                        "anker": "p-" + pid, "link": best["url"] if best else ""})
    with open(f"{out}/weitere_angebote.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["produkt", "haendler", "preis", "detail", "link"]); w.writerows(zeilen)
    with open(f"{out}/weitere_laeufe.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["produkt", "zeit", "preis"]); w.writerows(verlauf)
    return kacheln

_prod = [_macbook()]
_ip = _iphone(out)
if _ip: _prod.append(_ip)
_prod.extend(_weitere(out))
with open(f"{out}/produkte.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["id", "name", "unter", "preis", "haendler", "ziel", "abstand", "trend", "stand", "anker", "link"])
    for p_ in _prod:
        ab = round(max(0, float(p_["preis"]) - float(p_["ziel"])), 2) if p_["preis"] != "" else ""
        w.writerow([p_["id"], p_["name"], p_["unter"], p_["preis"], p_["haendler"], p_["ziel"], ab, p_["trend"], p_["stand"], p_["anker"], p_["link"]])
print("Produkte:", len(_prod))


# ---- Tagesaktuelle Ableitungen: Vorjahresvergleich, Black Friday 2026, Amazon-Verlauf, Codes ----
import datetime as _dt
_W = _os.path.dirname(_os.path.abspath(__file__))
_heute = last["zeit"][:10]
_alle = [l for l in L if l.get("guenstigster")]
_best_jetzt = min(a["preis_mit_code"] for a in last["angebote"])
_uvp = d.get("uvp", 1399)

# Vorjahresvergleich: feste Vorjahreswerte + M5 heute (Monate seit Marktstart März 2026)
_start = _dt.date(2026, 3, 1)
_monate = round(((_dt.date.fromisoformat(_heute) - _start).days) / 30.44, 1)
_rows = list(csv.reader(open(_os.path.join(_W, "vorjahre_vorgaenger.csv"), encoding="utf-8")))
with open(f"{out}/vorgaenger.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerows(_rows)
    w.writerow(["M5 (2026)", _monate, round((1 - _best_jetzt / _uvp) * 100), _best_jetzt, _uvp, "heute " + _heute[8:10] + "." + _heute[5:7] + ".: bester Preis aller Händler", ""])

# Black Friday 2026: Werte aus den Läufen des Preisradars
def _min_zw(von, bis):
    xs = [l["guenstigster"] for l in _alle if von <= l["zeit"][:10] <= bis]
    return min(xs) if xs else ""
_bw = _min_zw("2026-11-20", "2026-11-26")
_bf = _min_zw("2026-11-27", "2026-11-27")
_cm = _min_zw("2026-11-28", "2026-11-30")
_nach = _min_zw("2026-12-01", "2099-12-31")
_rows = list(csv.reader(open(_os.path.join(_W, "vorjahre_blackfriday.csv"), encoding="utf-8")))
with open(f"{out}/blackfriday.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerows(_rows)
    hinweis = "aus den Läufen deines Preisradars (bester Preis aller Händler); Anfang November ca. 1.199 € laut Amazon-Screenshot"
    if _cm != "": hinweis += f"; Wochenende/Cyber Monday bisher {_cm:.0f} €"
    w.writerow(["2026", "MacBook Air M5 13\" 16/512 GB (dein Modell)", 1199, _bw, _bf, _nach, hinweis, "https://github.com/LauraWohlmuth/preisradar/blob/main/data/prices.json"])

# Amazon-Verlauf: Screenshot-Monate + aktueller Amazon-Preis aus dem letzten Lauf
_amz = next((a["preis_mit_code"] for a in sorted(last["angebote"], key=lambda a: a["preis_mit_code"]) if a["haendler"].lower().startswith("amazon")), None)
_rows = list(csv.reader(open(_os.path.join(_W, "amazon_screenshot.csv"), encoding="utf-8")))
with open(f"{out}/amazon_verlauf.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerows(_rows)
    if _amz is not None:
        w.writerow([_heute, _amz, "Amazon laut Preisradar am " + _heute[8:10] + "." + _heute[5:7] + "."])

# Gültige Codes (aus config.json), abgelaufene und gesperrte weglassen
_cfg = json.load(open(_os.path.join(_os.path.dirname(_W), "config.json"), encoding="utf-8"))
with open(f"{out}/codes.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["haendler", "code", "rabatt_eur", "gueltig_bis", "bedingung"])
    for g in _cfg.get("gutscheine", []):
        if g.get("gueltig_bis", "9999") >= _heute and g["code"] not in _cfg.get("gesperrte_codes", {}):
            w.writerow([g["haendler"], g["code"], g.get("rabatt_eur", ""), g.get("gueltig_bis", ""), g.get("bedingung", "")])
print("tagesaktuell:", _heute, "BW", _bw, "BF", _bf, "Monate", _monate)
