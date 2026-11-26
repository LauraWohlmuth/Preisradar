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
