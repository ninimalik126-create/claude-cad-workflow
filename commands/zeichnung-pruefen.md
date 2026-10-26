---
description: Prüft eine technische Zeichnung (PDF, Bild oder Beschreibung) vollständig nach ISO GPS und liefert eine Befundliste mit korrigierten Eintragungen.
argument-hint: <Pfad zu PDF/PNG/SVG oder Beschreibung> [Funktion/Fertigung/Prüfung]
---

Lade zuerst die Skill `iso-gps-bemassung` und lies `references/13-pruefliste.md` vollständig, dazu die Referenzen, die für das Teil relevant sind (Drehteil → 10-verfahren.md Abschnitt Drehteile usw.).

Zu prüfen: $ARGUMENTS

Vorgehen:
0. CAD-Zeichnung (.SLDDRW, .idw, .CATDrawing)? Erst als PDF ausgeben: `python -I "${CLAUDE_PLUGIN_ROOT}/skills/iso-gps-bemassung/scripts/cad/cad.py" export <zeichnung>`. Korrekturen lassen sich danach direkt im CAD umsetzen (Auftrag nach `references/15-cad-workflow.md` oder Eintrageliste).
1. Zeichnung lesen (PDF mit dem Read-Werkzeug, bei mehrseitigen PDFs alle Blätter; Bilder ansehen; bei SVG aus `scripts/zeichnung.py` die JSON-Beschreibung lesen). Wenn Details unlesbar sind, sag das, statt zu raten.
2. Teil verstehen: Fertigungsverfahren, Werkstoff, vermutete Funktion. Fehlt die Funktion und ist sie nicht aus der Zeichnung ableitbar, nenne deine Annahme ausdrücklich und frage am Ende nach (die Prüfung trotzdem vollständig durchführen).
3. Jeden Punkt der Prüfliste (A–G) abarbeiten.
4. Passungen mit `python -I "${CLAUDE_PLUGIN_ROOT}/skills/iso-gps-bemassung/scripts/passung.py"` nachrechnen, wenn Abmaße angegeben sind.
5. Ergebnis ausgeben:
   - Kurzbewertung (2–3 Sätze, freigabefähig ja/nein).
   - Befundtabelle `Nr | Ort (Ansicht/Merkmal) | Befund | Norm | Korrektur (exakte neue Eintragung) | Schwere`. Sortiert: Fehler → Verbesserung → Stil.
   - Offene Fragen zur Funktion, falls Annahmen nötig waren.
6. Biete an, die korrigierte Zeichnung mit `/zeichnung-erstellen` neu zu erzeugen oder ein Tolerierungskonzept mit `/tolerieren` auszuarbeiten.
