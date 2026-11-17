---
name: cad-modellierung
description: Baut 3D-CAD-Modelle in FreeCAD oder SolidWorks aus einer Beschreibung, Skizze, einem Foto, einer Zeichnung, einer vorhandenen STEP-Datei oder einem Scan (STL) – mit Infophase, Programmauswahl, automatischer Installation fehlender Software, Bau über einen geprüften Bauplan (Parameter, Muster, Spiegeln, Loft, Zug, Text, Import; freies Skript nur für Sonderfälle), Selbstprüfung mit Merkmalsliste und Vorschaubild samt Schnitt und Ausgabe als native Datei, STEP, STL, 3MF und auf Wunsch technischer Zeichnung nach ISO GPS. Laden, sobald ein Bauteil, Ersatzteil, Halter, Gehäuse, Adapter, Welle, Platte, Flansch, 3D-Druck-Teil oder sonst ein CAD-Modell erstellt, geändert, konstruiert, modelliert oder als STEP/STL/3MF erzeugt werden soll, wenn ein Scan oder eine STL vermessen, nachgebaut oder in STEP gewandelt werden soll, wenn FreeCAD- oder SolidWorks-Modellierung gefragt ist, oder wenn /teil-erstellen aufgerufen wird. Nicht für Blechabwicklungen oder Baugruppen mit beweglichen Verknüpfungen.
---

# CAD-Modell bauen (FreeCAD / SolidWorks)

Ziel: **Ein maßhaltiges Teil im ersten Anlauf**, mit möglichst wenigen Rückfragen und wenig Kontingent. Qualität geht vor Tempo: Nichts wird übergeben, was nicht gebaut, gegen die Vorgabe geprüft und angesehen wurde.

Alle Pfade sind relativ zu diesem Skill-Ordner. Python immer mit `python -I` aufrufen. Enthält ein Dateipfad Sonderzeichen (–, Umlaute), den Befehl in PowerShell ausführen – Git Bash verfälscht solche Argumente.

Was Kontingent spart: den Bauplan nutzen statt freien Code zu schreiben, Maße als Parameter anlegen, die Merkmalsliste lesen statt Maße aus dem Bild zu schätzen, den Bericht nur bei Fehlern öffnen, keine Zwischenstände erzählen.

## Ablauf

### 1. Infophase
Der Nutzer liefert, was er hat. Abgleichen mit `references/infophase.md` und **nur Fehlendes in einer einzigen Nachricht** fragen (Muss: Funktion, Hauptmaße, Funktionsmaße, Fertigung). Alles andere als Annahme festlegen. Bilder/Skizzen genau lesen; Maße nie schätzen, wenn sie für die Funktion wichtig sind – dann fragen.

Liegt ein Scan, eine STL oder ein fremdes STEP vor: erst `references/scan-nachbau.md`.

Parallel (ohne Rückfrage, dauert < 1 s, wird zwischengespeichert):
```
python -I scripts/modell.py umgebung
```

### 2. Programm und Ausgaben
- Meldet `umgebung` **Vorgaben** (z. B. „freecad, STEP + STL“) oder hat der Nutzer Programm und Ausgaben schon genannt: keine Karte. Die Liste „So baue ich es“ kurz nennen und direkt bauen.
- Sonst **ein** AskUserQuestion-Aufruf mit zwei Fragen: **Programm** (FreeCAD / SolidWorks, nur was installiert ist oder installiert werden kann) und **Ausgaben** (`multiSelect`: STEP · STL · 3MF · Zeichnung). Die native Datei entsteht immer. Darüber steht die kurze Liste „So baue ich es“ – die Karte ist zugleich die Bestätigung.
- Wählt jemand immer dasselbe, einmal anbieten: `python -I scripts/modell.py vorgaben --cad freecad --formate step,stl` (danach entfällt die Karte).

### 3. Fehlende Software installieren
Laut `umgebung`, immer **erst nach Zustimmung**: `modell.py installieren freecad` (Open Source, ca. 500 MB, über winget) oder `installieren pywin32` (für SolidWorks). SolidWorks selbst lässt sich nicht installieren – dann FreeCAD vorschlagen.

### 4. Bauweg wählen
Der **Bauplan** deckt fast alles ab (`references/bauplan.md`; beim ersten Plan einer Sitzung ganz lesen). Freier Code nur nach `references/freie-skripte.md`, und dann so wenig wie möglich. Muster, Spiegeln, Loft, Zug, Text, Import, geneigte Ebenen, Schrägen und modellierte Gewinde baut bisher nur FreeCAD – braucht das Teil so etwas und will der Nutzer SolidWorks, in FreeCAD bauen und die STEP-Datei übergeben.

### 5. Bauplan schreiben und bauen
- Ablage: `CAD-Teile/<Teilname>/<Teilname>.json` im Arbeitsordner (oder wo der Nutzer will). Kurze Pfade.
- Maße, die sich ändern können oder mehrfach vorkommen, als `parameter` anlegen und mit `"=L/2"` verwenden. Änderungen und Varianten sind dann ein Befehl.
- `fertigung` eintragen (`fdm`, `sla`, `fraesen`, `drehen`) – dann prüft der Bau Druck- und Fräsregeln mit.
- **`soll.huelle` immer selbst aus den Maßen ausrechnen** und eintragen – die wichtigste Selbstkontrolle.
- Sprechende Feature-IDs (`Grundplatte`, `Befestigung`) – sie werden die Namen im Feature-Baum.
- Funktionsmaße exakt aus der Vorgabe, Passungen über `../iso-gps-bemassung/scripts/passung.py`.

```
python -I scripts/modell.py bauen <plan.json> [--cad freecad|solidworks] [--formate step,stl,3mf]
```
Ohne `--cad`/`--formate` gelten die Vorgaben, sonst FreeCAD und nur die native Datei. `bauen` prüft den Plan selbst. Ein Lauf zeigt bis zu drei Fehler auf einmal; Meldungen zu Kanten- und Flächenauswahl nennen, was es stattdessen gibt. Den Bericht (`<name>-bericht.json`) nur bei Fehlern öffnen.

### 6. Selbst prüfen – vor jeder Übergabe
1. **0 Fehler**, Hinweise beachtet, Soll-Hülle erfüllt.
2. **Merkmalsliste** in der Ausgabe Zeile für Zeile mit der Vorgabe vergleichen: Anzahl, Ø, Lage und Tiefe der Bohrungen, Außenzylinder, Senkungen, Radien. Das ist genauer als das Bild.
3. **Vorschaubild** `<name>-vorschau.png` ansehen: Form, Proportionen, Richtung der Taschen, Schrift lesbar. Die Unterseite und ein Schnitt kommen von selbst dazu, wenn von unten gearbeitet oder ausgehöhlt wird. Innenliegendes sonst gezielt zeigen: `--ansichten iso,oben,schnitt:X=0` oder `"ansichten"` im Plan.
4. Bei `fertigung: fdm` die Zeile „Druck:“ lesen (Überhänge, Auflagefläche) und Lage oder Fasen anpassen.
5. Mehrere Teile, die zusammengehören (Gehäuse und Deckel, Welle und Nabe): in gemeinsamer Lage bauen und `python -I scripts/modell.py zusammen a.step b.step --bild zusammen.png` – Durchdringung muss 0 sein, der kleinste Abstand ist das Spiel.
6. Bei Abweichung: Plan mit Edit gezielt ändern, neu bauen. Nach 3 erfolglosen Runden dem Nutzer den Stand zeigen und fragen.

### 7. Zeichnung (wenn gewählt)
Mit dem Skill `iso-gps-bemassung` auf dem CAD-Weg weiter (`../iso-gps-bemassung/references/15-cad-workflow.md`). Funktion, Fertigung und Prüfmittel sind aus der Infophase bekannt – nicht erneut fragen.

### 8. Übergabe
- Vorschaubild mit SendUserFile zeigen.
- Kurz: Dateien (Pfad), Größe/Masse, getroffene Annahmen, was nicht geprüft werden konnte (z. B. Passung nur rechnerisch, Druck nicht simuliert).
- Plan-JSON nicht in den Chat kopieren – er liegt neben dem Teil und ist die Grundlage für Änderungen.

## Änderungen und Varianten
- Maß ändern: Parameter im Plan ändern, `bauen` erneut – die Dateien werden ersetzt.
- Variante ohne Planänderung: `bauen plan.json --param L=100,dk=10 --name Halter-100`.
- Fremdes Teil ändern: erstes Feature `import` (STEP), danach normale Features.
- Gleicher Plan mit `--cad solidworks` baut das Teil dort identisch nach, solange er nur die gemeinsamen Features nutzt.

## Grenzen
- Keine Blechabwicklung, keine beweglichen Baugruppen. Organische Freiformflächen (Karosserie, Ergonomiegriff) entstehen nicht zuverlässig per Skript: Grundkörper liefern oder den Scan als Volumenkörper wandeln und das offen sagen.
- Gewinde sind kosmetisch, außer mit `gewinde_modelliert` (FreeCAD, für den Druck ab M6). Außengewinde werden nicht modelliert.
- Bohrungen haben einen flachen Grund, außer mit `spitze`.
