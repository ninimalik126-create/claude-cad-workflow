---
description: Prüft und vermisst einen Scan oder eine STL-Datei, wandelt sie in einen STEP-Volumenkörper oder baut das Teil mit dem Bauplan nach – mit Vergleichsbild Vorlage gegen Modell.
argument-hint: [Pfad zur STL/OBJ/3MF-Datei, und was daraus werden soll]
---

Bearbeite das Netz nach `references/scan-nachbau.md` im Skill `cad-modellierung`.

Angaben des Nutzers: $ARGUMENTS

1. `python -I "${CLAUDE_PLUGIN_ROOT}/skills/cad-modellierung/scripts/modell.py" netz pruefen <datei> --bild <ordner>/pruefung.png` – Ausgabe lesen, Bild ansehen, die Form in zwei Sätzen beschreiben.
2. Weg festlegen und dem Nutzer in einem Satz nennen: **Volumenkörper** (`netz koerper`, Minuten, 1:1 zum Scan, ohne Konstruktionsverlauf) oder **Nachbau** (Bauplan aus den Maßen von `netz schnitte`). Ist nicht klar, was der Nutzer braucht, genau das fragen – sonst nichts.
3. Beim Nachbau nach jeder Bauschleife `netz vergleich` mit Bild; erst das Bild beurteilen, dann die Zahlen.
4. Übergabe: Vergleichs- oder Vorschaubild mit SendUserFile, Dateien mit Pfad, was weggelassen oder gerundet wurde.

Pfade mit Sonderzeichen (–, Umlaute) in PowerShell ausführen.
