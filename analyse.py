#!/usr/bin/env python3
"""Lädt Seiten für die Analyse herunter (nur manuell gestartet). URLs aus der Umgebungsvariable URLS, durch Leerzeichen getrennt."""
import os, re, urllib.request
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
os.makedirs("debug", exist_ok=True)
for i, url in enumerate(os.environ.get("URLS", "").split()):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read().decode("utf-8", "replace")
            ziel = r.geturl()
    except Exception as e:
        data, ziel = f"FEHLER: {e}", url
    name = f"debug/{i:02d}-" + re.sub(r"[^a-z0-9]+", "-", url.lower())[8:70] + ".html"
    open(name, "w", encoding="utf-8").write(f"<!-- {url} -> {ziel} -->\n" + data)
    print(name, len(data))
