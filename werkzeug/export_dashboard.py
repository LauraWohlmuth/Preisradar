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
    d = json.load(open(pfad, encoding="utf-8"))
    if not d["laeufe"]: return None
    last = d["laeufe"][-1]
    cfg = json.load(open(_os.path.join(_os.path.dirname(_os.path.dirname(src)), "produkte", "iphone-17-pro.json"), encoding="utf-8"))
    fokus = "/407262aa/"
    zeilen = []
    gesehen = set()
    for a in last.get("angebote", []):
        u = a.get("url", "")
        if u in gesehen: continue
        gesehen.add(u)
        ist_fokus = fokus in u
        # nur das Hauptangebot je Quelle: Pfad der Quell-URL muss in der Angebots-URL stehen
        passt = any(q["url"].split("?")[0].rstrip("/") in u for q in cfg["quellen"]) and "?offer=" not in u
        if not passt: continue
        if ist_fokus:
            lab, art, det = "Dein Angebot: Tiefblau, 256 GB", "passt", "Zustand Premium, Akku neu, lieferbar"
        elif "/407263aa/" in u:
            lab, art, det = "refurbed: Silber, 256 GB", "pruefen", "vermutlich Premium (Endung aa), Akku nicht ausgelesen"
        elif "/407262/" in u:
            lab, art, det = "refurbed: Tiefblau, 256 GB (Voreinstellung)", "pruefen", "Zustand und Akku nicht ausgelesen"
        elif "coolblue" in u:
            lab, art, det = "Coolblue: Silber, 512 GB", "pruefen", "Zustand sehr gut laut Adresse, Akku nicht ausgelesen"
        else:
            lab, art, det = a["haendler"], "pruefen", "Zustand und Akku nicht ausgelesen"
        zeilen.append([lab, a["preis_mit_code"], art, det, u])
    zeilen.sort(key=lambda z: (z[2] != "passt", z[1]))
    with open(f"{out}/iphone_angebote.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["label", "preis", "art", "detail", "link"]); w.writerows(zeilen)
    fok = next((z for z in zeilen if z[2] == "passt"), None)
    preise = [l["guenstigster"] for l in d["laeufe"] if l.get("guenstigster")]
    return {"id": "iphone", "name": "iPhone 17 Pro refurbished", "unter": "Tiefblau/Silber · 256/512 GB · Exzellent+ · Akku neu/optimal",
            "preis": fok[1] if fok else "", "haendler": "refurbed", "ziel": cfg["zielpreis"], "stand": last["zeit"][:16],
            "trend": "–", "anker": "iphone", "link": fok[4] if fok else ""}

def _macbook():
    laeufe = [l for l in L if l.get("guenstigster")]
    best = sorted(last["angebote"], key=lambda a: a["preis_mit_code"])[0]
    return {"id": "macbook", "name": "MacBook Air 13\" M5", "unter": "16 GB · 512 GB · Mitternacht · neu",
            "preis": best["preis_mit_code"], "haendler": best["haendler"], "ziel": d["zielpreis"], "stand": last["zeit"][:16],
            "trend": _trend([l["guenstigster"] for l in laeufe]), "anker": "kopf", "link": best["url"]}

_prod = [_macbook()]
_ip = _iphone(out)
if _ip: _prod.append(_ip)
with open(f"{out}/produkte.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["id", "name", "unter", "preis", "haendler", "ziel", "abstand", "trend", "stand", "anker", "link"])
    for p_ in _prod:
        ab = round(max(0, float(p_["preis"]) - float(p_["ziel"])), 2) if p_["preis"] != "" else ""
        w.writerow([p_["id"], p_["name"], p_["unter"], p_["preis"], p_["haendler"], p_["ziel"], ab, p_["trend"], p_["stand"], p_["anker"], p_["link"]])
print("Produkte:", len(_prod))
