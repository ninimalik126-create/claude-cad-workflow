---
description: Berechnet ISO-286-Grenzabmaße, Grenzmaße und Spiel/Übermaß einer Passung oder eines Toleranzfelds.
argument-hint: <Nennmaß> <Feld oder Bohrung/Welle>, z. B. 25 H7/g6
---

Führe aus: `python -I "${CLAUDE_PLUGIN_ROOT}/skills/iso-gps-bemassung/scripts/passung.py" $ARGUMENTS`

Gib das Ergebnis kompakt wieder (Abmaße, Grenzmaße, Passungsart, Höchst-/Mindestspiel bzw. -übermaß) und die Zeichnungseintragung. Wenn das Feld nicht hinterlegt ist, sag das und nenne ISO 286-2 als Quelle; rate keine Werte. Wenn die Anfrage eine Funktion nennt, prüfe mit `references/06-passungen.md`, ob die Passung dazu passt, und schlage gegebenenfalls eine bessere vor.
