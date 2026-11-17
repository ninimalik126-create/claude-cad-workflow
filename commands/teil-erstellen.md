---
description: Erstellt oder ändert ein 3D-CAD-Teil in FreeCAD oder SolidWorks – Infophase, Programm und Ausgaben in einer Abfrage (entfällt mit Vorgaben), Bau mit Selbstprüfung, Ausgabe als native Datei, STEP, STL, 3MF und optional Zeichnung.
argument-hint: [Beschreibung des Teils, Maße, Fertigung – oder Pfad zu einer STEP/STL-Datei]
---

Erstelle ein CAD-Teil nach dem Skill `cad-modellierung` (Ablauf Schritt 1–8).

Angaben des Nutzers: $ARGUMENTS

- Fehlen die Angaben ganz, in einem Satz um Beschreibung, Hauptmaße und Fertigung bitten (Foto oder Skizze mit Maßen ist ideal).
- Sonst direkt mit der Infophase beginnen: Fehlendes gesammelt fragen, danach die eine Karte mit Programm und Ausgaben – oder gleich bauen, wenn Vorgaben gesetzt sind oder beides schon genannt wurde.
- Nennt der Nutzer eine STEP-Datei, die geändert werden soll: als `import` in den Bauplan. Bei einem Scan oder einer STL: `/scan-nachbau`.
