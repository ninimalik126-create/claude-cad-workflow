---
description: Erzeugt eine vollständige, normgerecht bemaßte Fertigungszeichnung nach ISO GPS – direkt im CAD (SolidWorks, Inventor, CATIA V5) aus dem 3D-Teil, oder ohne CAD als SVG/PDF/PNG.
argument-hint: <3D-Teil (.SLDPRT/.ipt/.CATPart) oder Bauteilbeschreibung/Skizze> [Format A4/A3] [Zielordner]
---

Lade zuerst die Skill `iso-gps-bemassung`. Lies `references/02-masseintragung.md`, `references/12-zeichnungsformat.md`, `references/13-pruefliste.md` und die passenden Abschnitte aus `03`–`10`.

Bauteil: $ARGUMENTS

## 1. Weg wählen

- Ist eine CAD-Teildatei genannt oder arbeitet der Nutzer mit einem CAD: `python -I "${CLAUDE_PLUGIN_ROOT}/skills/iso-gps-bemassung/scripts/cad/cad.py" erkennen` und `references/15-cad-workflow.md` lesen → **CAD-Weg**.
- Sonst → **neutraler Weg** (`references/14-generator.md`, Vorlage `beispiele/welle.json`).
- Ist ein CAD installiert, aber keine Datei genannt, kurz fragen: „Liegt das Teil im CAD vor? Dann zeichne ich direkt dort.“

## 2a. CAD-Weg

1. `cad.py analysieren <teil> -o <teil>-merkmale.json` – Flächen-IDs, Durchmesser, Ebenen, Achsen lesen.
2. Funktion klären (gebündelte Rückfrage, falls nötig) und Tolerierungskonzept festlegen; Passungen mit `scripts/passung.py`. Konzept kurz als Tabelle zeigen.
3. Zeichnungsauftrag `<teil>-auftrag.json` neben das Teil schreiben (Vorlage: `scripts/cad/selbsttest-auftrag.json`). Firmenvorlage/Blattformat des Nutzers verwenden, falls genannt oder im Projekt vorhanden.
4. `cad.py schliessen`, dann `cad.py zeichnen <auftrag.json>`. Protokoll muss `"fehler": 0` haben; Fehler beheben (Fehlerbilder in 15-cad-workflow.md).
5. PDF mit dem Read-Werkzeug ansehen, gegen Prüfliste 13 (B, C, G) kontrollieren, Positionen im Auftrag nachjustieren, neu zeichnen – bis sauber.
6. Ergebnis: Pfad der CAD-Zeichnung und PDF (per SendUserFile), Merkmalstabelle, offene Annahmen. Bei Inventor/CATIA sagen, dass der Adapter ungetestet ist; bei CATIA auf die Eintrageliste hinweisen.

## 2b. Neutraler Weg

1. Geometrie und Funktion klären (gebündelte Rückfrage).
2. Tolerierungskonzept festlegen (Passungen mit `scripts/passung.py`).
3. Blatt, Maßstab nach ISO 5455, Ansichten, Schnitte, Einzelheiten planen.
4. JSON nach `references/14-generator.md` schreiben, z. B. `zeichnungen/<teil>.json`.
5. `python -I "${CLAUDE_PLUGIN_ROOT}/skills/iso-gps-bemassung/scripts/zeichnung.py" <json> --png --pdf`
6. Alle FEHLER und WARNUNGEN beheben, PNG ansehen, gegen Prüfliste 13 kontrollieren, wiederholen.
7. PDF/PNG per SendUserFile zeigen, Merkmalstabelle und Annahmen nennen.
