---
description: Erarbeitet aus Funktion, Fertigung und Prüfmöglichkeiten ein vollständiges ISO-GPS-Tolerierungskonzept (Bezüge, Maße, Passungen, Form- und Lagetoleranzen, Oberflächen) für ein Bauteil.
argument-hint: <Bauteilbeschreibung, Skizze, CAD-Screenshot oder Pfad>
---

Lade zuerst die Skill `iso-gps-bemassung`. Lies `references/01-grundlagen.md`, `03-geometrische-toleranzen.md`, `04-bezuege.md`, `05-materialbedingungen.md`, `11-pruefplanung.md` und die zum Verfahren passenden Abschnitte aus `10-verfahren.md`.

Bauteil: $ARGUMENTS

Vorgehen:
0. **CAD-Teil?** Ist eine Teildatei (.SLDPRT, .ipt, .CATPart) genannt, zuerst `python -I "${CLAUDE_PLUGIN_ROOT}/skills/iso-gps-bemassung/scripts/cad/cad.py" analysieren <teil>` ausführen und die Spezifikationen in der Merkmalstabelle auf die Flächen-IDs (F1 …) beziehen. Dann lässt sich das Konzept direkt mit `/zeichnung-erstellen` im CAD umsetzen (`references/15-cad-workflow.md`).
1. **Funktionsanalyse.** Kläre: Einbausituation, Anlage-, Zentrier-, Verdrehsicherungsflächen, Passungen und Gegenstücke, Lasten, Dichtungen, Bewegungen, Fertigungsverfahren, Werkstoff, Stückzahl, verfügbare Messmittel. Was nicht aus den Angaben hervorgeht, frage gebündelt in **einer** Rückfrage (höchstens 5 Punkte, mit Vorschlag als Standardantwort). Wenn genug klar ist, mit begründeten Annahmen weitermachen.
2. **Bezugssystem** festlegen und begründen (Rang, gesperrte Freiheitsgrade).
3. **Merkmalstabelle** erstellen:
   `Nr | Merkmal | Funktion | Spezifikation (exakt wie auf der Zeichnung) | Begründung | Prüfmittel | KMG?`
   - Passungen mit `python -I "${CLAUDE_PLUGIN_ROOT}/skills/iso-gps-bemassung/scripts/passung.py"` berechnen und Grenzabmaße angeben.
   - Maßketten der Funktion (Spiel, Überdeckung, Wandstärke) nachrechnen (Worst Case; statistisch nur mit Begründung).
4. **Schriftfeld-/Hinweisangaben**: Tolerierungsgrundsatz, Allgemeintoleranzen, Oberflächen-Sammelangabe, Kanten, Werkstoff, Behandlung.
5. **Selbstprüfung** mit `references/13-pruefliste.md` (Abschnitte B–F) und Befunde sofort einarbeiten.
6. Biete an, daraus mit `/zeichnung-erstellen` die Zeichnung zu erzeugen, oder liefere eine Eintrageliste für das CAD (je Ansicht: welche Maße/Rahmen wo).
