---
name: cad-modellierung
description: Baut 3D-CAD-Modelle (Einzelteile) in FreeCAD oder SolidWorks aus einer Beschreibung, Skizze, einem Foto oder einer Zeichnung – mit Infophase, Programmauswahl, automatischer Installation fehlender Software, Bau über einen geprüften Bauplan (oder freies Skript für komplexe Geometrie), Selbstprüfung mit Vorschaubild und Ausgabe als native Datei, STEP, STL, 3MF und auf Wunsch technischer Zeichnung nach ISO GPS. Laden, sobald ein Bauteil, Ersatzteil, Halter, Gehäuse, Adapter, Welle, Platte, Flansch, 3D-Druck-Teil oder sonst ein CAD-Modell erstellt, konstruiert, modelliert oder als STEP/STL/3MF erzeugt werden soll, wenn FreeCAD- oder SolidWorks-Modellierung gefragt ist, oder wenn /teil-erstellen aufgerufen wird. Nicht für Baugruppen mit Verknüpfungen, Blechabwicklungen oder organische Freiformflächen.
---

# CAD-Modell bauen (FreeCAD / SolidWorks)

Ziel: **Ein maßhaltiges Teil im ersten Anlauf**, mit möglichst wenigen Rückfragen und wenig Kontingent. Qualität geht vor Tempo: Nichts wird übergeben, was nicht gebaut, geprüft und angesehen wurde.

Alle Pfade sind relativ zu diesem Skill-Ordner. Python immer mit `python -I` aufrufen.

## Ablauf

### 1. Infophase
Der Nutzer liefert, was er hat. Abgleichen mit `references/infophase.md` und **nur Fehlendes in einer einzigen Nachricht** fragen (Muss: Funktion, Hauptmaße, Funktionsmaße, Fertigung). Alles andere als Annahme festlegen. Bilder/Skizzen genau lesen; Maße nie schätzen, wenn sie für Funktion wichtig sind – dann fragen.

Parallel (ohne Rückfrage, dauert < 1 s, wird zwischengespeichert):
```
python -I scripts/modell.py umgebung
```

### 2. Eine Karte: Programm + Ausgaben
Mit **einem** AskUserQuestion-Aufruf, zwei Fragen:
- **Programm** (`header: "Programm"`): FreeCAD / SolidWorks. Nur anbieten, was installiert ist oder installiert werden kann (FreeCAD). Ist SolidWorks nicht installiert, diese Frage weglassen und FreeCAD nehmen.
- **Ausgaben** (`header: "Ausgaben"`, `multiSelect: true`): STEP · STL · 3MF · Zeichnung (PDF + native Zeichnung). Die native Datei (.FCStd/.SLDPRT) entsteht immer – in der Beschreibung sagen. Empfehlung an den Zweck anpassen (Druck: STL/3MF, Fertigung: STEP + Zeichnung).

Im selben Text darüber steht die kurze Liste „So baue ich es“ (Hauptmaße, Features, Annahmen) – die Karte ist zugleich die Bestätigung.

### 3. Fehlende Software installieren
Laut `umgebung`:
- FreeCAD fehlt und wurde gewählt → dem Nutzer sagen, dass FreeCAD (Open Source, ca. 500 MB, über winget) installiert wird, und **nach Zustimmung** `python -I scripts/modell.py installieren freecad`.
- pywin32 fehlt und SolidWorks gewählt → nach Zustimmung `python -I scripts/modell.py installieren pywin32`.
- SolidWorks lässt sich nicht installieren (Lizenz) – dann FreeCAD vorschlagen.

### 4. Bauweg wählen
Nach `references/freie-skripte.md`: **Bauplan** (Standard) · Bauplan + `frei`-Feature · freies Skript. Dem Nutzer in einem Satz sagen, welcher Weg und warum, wenn es nicht der Bauplan ist.

### 5. Bauplan schreiben und bauen
Format: `references/bauplan.md` (beim ersten Plan einer Sitzung ganz lesen). Regeln:
- Ablage: `CAD-Teile/<Teilname>/<Teilname>.json` im Arbeitsordner (oder wo der Nutzer will). Kurze Pfade (SolidWorks scheitert ab ca. 255 Zeichen).
- **`soll.huelle` immer von Hand aus den Maßen ausrechnen** und eintragen – das ist die wichtigste Selbstkontrolle.
- Sprechende Feature-IDs (`Grundplatte`, `Befestigung`, `Passfedernut`) – sie werden die Namen im Feature-Baum.
- Funktionsmaße exakt aus der Vorgabe, Passungen über `../iso-gps-bemassung/scripts/passung.py`.

```
python -I scripts/modell.py bauen <plan.json> --cad freecad|solidworks --formate step,stl,3mf
```
`bauen` prüft den Plan selbst (kein extra `pruefen` nötig). Die Ausgabe ist eine kurze Zusammenfassung; den Bericht (`<name>-bericht.json`) nur bei Fehlern öffnen. SolidWorks wird dabei sichtbar gestartet (erster Start ca. 30 s); offene Dokumente des Nutzers bleiben unberührt.

### 6. Selbst prüfen – vor jeder Übergabe
1. Zusammenfassung: **0 Fehler**, Hinweise beachtet, Soll-Hülle erfüllt.
2. Vorschaubild `<name>-vorschau.png` mit dem Read-Werkzeug ansehen (Iso, Vorne, Oben, Rechts mit Maßen): Stimmen Anzahl und Lage der Bohrungen, Richtung der Taschen, Ausrichtung, Proportionen mit der Vorgabe überein?
3. Bei Abweichung: Plan mit Edit gezielt ändern, neu bauen. Nach 3 erfolglosen Runden dem Nutzer den Stand zeigen und fragen.
Fehlermeldungen und Abhilfen: `references/bauplan.md` → „Prüfungen beim Bau“.

### 7. Zeichnung (wenn gewählt)
Mit dem Skill `iso-gps-bemassung` auf dem CAD-Weg weiter (`../iso-gps-bemassung/references/15-cad-workflow.md`): `cad.py analysieren <teil>` → Tolerierungskonzept aus der Funktion → Zeichnungsauftrag → `cad.py zeichnen`. Funktion, Fertigung und Prüfmittel sind aus der Infophase bekannt – nicht erneut fragen.

### 8. Übergabe
- Vorschaubild mit SendUserFile zeigen.
- Kurz: Dateien (Pfad), Größe/Masse, getroffene Annahmen, was nicht geprüft werden konnte (z. B. Passung nur rechnerisch, Druckbarkeit nicht simuliert).
- Plan-JSON nicht in den Chat kopieren – er liegt neben dem Teil und ist die Grundlage für Änderungen („mach die Bohrungen 0,2 größer“ = Plan ändern, neu bauen).

## Änderungen an einem bestehenden Teil
Plan öffnen, gezielt ändern, `bauen` erneut – die Dateien werden ersetzt. Gleicher Plan mit `--cad` des anderen Programms baut das Teil dort identisch nach.

## Grenzen
- Einzelteile; keine Baugruppen, keine Blechabwicklung, keine Freiformflächen nach Gefühl.
- Gewinde sind kosmetisch (Kernloch + Gewindedarstellung) – für den 3D-Druck kleiner Gewinde Einsätze oder Muttern vorsehen.
- Bohrungen haben einen flachen Grund (in beiden Programmen gleich).
