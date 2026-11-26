# Preisradar

Prüft stündlich (7–23 Uhr) per GitHub Action die Preise für das MacBook Air M5 (16 GB/512 GB, Mitternacht, MDHE4D/A) und schreibt sie in `übersicht.md` (privates Repo, lesbar in der GitHub-App).

- `preise.py`: liest die Quellen aus `config.json`, schreibt `data/prices.json`. Erfindet nichts: Was nicht lesbar ist, steht als „nicht prüfbar“ mit Grund drin.
- `.github/workflows/preise.yml`: Zeitplan, speichert die Ergebnisse, legt bei Preis ≤ Zielpreis oder neuem Tiefstwert ein Issue an (GitHub schickt dann eine Benachrichtigung).
- `übersicht.md`: die Übersicht (wird bei jedem Lauf neu geschrieben).
- `index.html`: optionale Webseite, nur für GitHub Pages bei öffentlichem Repo.

Vorlage aus dem Skill **preis-alarm** in Lauras Skillsammlung.
