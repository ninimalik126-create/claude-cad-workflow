---
name: iso-gps-bemassung
description: Normgerechtes Bemaßen und Tolerieren technischer Zeichnungen nach ISO GPS (ISO 8015, ISO 1101, ISO 5459, ISO 2692, ISO 14405, ISO 286, ISO 129-1, ISO 22081/2768, ISO 21920/1302, ISO 13715, ISO 7200, ISO 128) – direkt in SolidWorks oder FreeCAD (Inventor, CATIA V5 vorbereitet) oder ohne CAD. Laden, sobald eine Fertigungszeichnung bemaßt, toleriert, geprüft, korrigiert oder erzeugt werden soll, sobald Form- und Lagetoleranzen, Bezüge, Passungen, Allgemeintoleranzen, Oberflächenangaben, Gewinde- oder Bohrungsangaben, Schriftfeld oder Zeichnungsnormen zur Sprache kommen, wenn eine SolidWorks-, FreeCAD-, Inventor- oder CATIA-Datei (.SLDPRT, .SLDDRW, .FCStd, .ipt, .idw, .CATPart, .CATDrawing) bemaßt oder gezeichnet werden soll, wenn nach dem Bau eines Teils mit cad-modellierung eine Zeichnung gewünscht ist, und wenn ein CAD-Zeichnungs-PDF oder ein Screenshot einer Zeichnung beurteilt werden soll. Gilt für Dreh-, Fräs-, Blech-, Guss-, Kunststoff- und Schweißteile.
---

# ISO GPS: Zeichnungen funktions-, fertigungs- und prüfgerecht bemaßen

Ziel jeder Zeichnung: **Eine einzige, eindeutige Auslegung.** Jedes Merkmal ist vollständig spezifiziert, nichts ist doppelt bestimmt, und jede Angabe ist mit einem genannten Messverfahren prüfbar. Eine „schöne“ Zeichnung mit mehrdeutiger Tolerierung ist eine falsche Zeichnung.

## Arbeitsweise

0. **Weg wählen: CAD oder neutral.** Arbeitet der Nutzer mit SolidWorks, FreeCAD, Inventor oder CATIA (Teildatei genannt, CAD läuft, oder er sagt es), geschieht alles **im CAD**: `python -I scripts/cad/cad.py erkennen`, dann Analyse des 3D-Teils, Tolerierungskonzept, Zeichnungsauftrag, native CAD-Zeichnung + PDF. Ablauf und Formate: `references/15-cad-workflow.md`. Ohne CAD: neutraler Generator (`references/14-generator.md`). Im Zweifel einmal fragen, welches CAD genutzt wird.
1. **Funktion vor Zeichnen.** Bevor ein Maß gesetzt wird, kläre (oder frage, wenn nicht ableitbar):
   - Was macht das Teil? Mit welchen Flächen liegt es an, wird es zentriert, gegen Verdrehen gesichert, verschraubt, gedichtet, gelagert?
   - Fertigungsverfahren (Drehen, Fräsen, Laser/Kanten, Guss, Spritzguss, Schweißen, additiv) und Werkstoff.
   - Wie wird geprüft? Handmessmittel, Lehren, Messuhr/Prisma, KMG. Wenn unklar oder gemischt: Tolerierung so wählen, dass sie mit Handmessmitteln prüfbar bleibt, und für KMG-pflichtige Merkmale ausdrücklich darauf hinweisen.
   - Stückzahl und Kostenrahmen (enger als nötig = teurer).
2. **Bezugssystem festlegen** aus der Funktion (Anlage → primär, Zentrierung → sekundär, Verdrehsicherung → tertiär). Siehe `references/04-bezuege.md`.
3. **Funktionsmaße zuerst** mit Toleranzen aus Funktion/Passung, dann **Geometrietoleranzen** (Form → Richtung → Ort → Lauf), dann **Restmaße** über Allgemeintoleranzen.
4. **Eintragen** nach ISO 129-1 und den Regeln in `references/02-masseintragung.md`.
5. **Selbstprüfung** mit `references/13-pruefliste.md`, bevor das Ergebnis ausgegeben wird. Jeder Befund wird behoben oder ausdrücklich als offene Frage genannt.

## Unverhandelbare Grundregeln

- **Tolerierungsgrundsatz angeben:** Im Schriftfeld oder Hinweisfeld „Tolerierung ISO 8015“. Damit gilt das **Unabhängigkeitsprinzip**: Maßtoleranzen begrenzen keine Formabweichung. Wo Passungsfunktion die Hülle braucht: Ⓔ ans Maß (ISO 14405-1) oder gezielte Formtoleranz.
- **Keine Mehrfachbemaßung, keine geschlossenen Maßketten.** Ein Kettenglied bleibt frei (oder wird als Hilfsmaß in Klammern eingetragen).
- **Jedes Geometrieelement vollständig bestimmt** in Größe, Form, Richtung und Lage, entweder einzeln toleriert oder über Allgemeintoleranzen abgedeckt. Bei theoretisch genauen Maßen (TED, eingerahmt) muss ein Geometrietoleranzrahmen die Abweichung begrenzen; ein TED ohne zugehörige Toleranz ist ein Fehler.
- **Bezüge nur dort, wo sie Funktion haben**, mit vollständig bestimmter Reihenfolge (primär, sekundär, tertiär). Ein Bezug, der nie in einem Toleranzrahmen verwendet wird, ist zu entfernen.
- **Allgemeintoleranzen immer angeben** (ISO 22081 oder ISO 2768-1/-2 mit Hinweis zum Normstand). Siehe `references/08-allgemeintoleranzen.md`.
- **Dezimalkomma** auf deutschsprachigen Zeichnungen (ISO 129-1 erlaubt beides, Firmenstandard folgen). Einheit mm wird nicht geschrieben.
- **Prüfbarkeit:** Jede enge Toleranz muss zu einem realen Messmittel passen (Faustregel: Messunsicherheit ≤ 1/10 bis 1/5 der Toleranz). Siehe `references/11-pruefplanung.md`.
- **Nicht raten bei Normwerten.** Passungsgrenzmaße mit `scripts/passung.py` berechnen, nicht aus dem Gedächtnis. Werte, die nicht in den Referenzen stehen und nicht berechnet werden können, als „in Norm X nachschlagen“ kennzeichnen.

## Referenzen (bei Bedarf lesen)

| Datei | Inhalt |
|---|---|
| `references/01-grundlagen.md` | ISO 8015 Prinzipien, GPS-Matrix, Normenstand, alte vs. neue Zeichnungen |
| `references/02-masseintragung.md` | ISO 129-1: Maßlinien, Anordnung, Bezugs-/Ketten-/Koordinatenbemaßung, Sonderzeichen, Fertigungs- und Prüfgerechtheit |
| `references/03-geometrische-toleranzen.md` | ISO 1101: alle Eigenschaften, Rahmensyntax, Modifikatoren, Toleranzzonen, Beispiele |
| `references/04-bezuege.md` | ISO 5459: Bezüge, Bezugssysteme, Bezugsstellen, gemeinsame Bezüge, Freiheitsgrade |
| `references/05-materialbedingungen.md` | ISO 2692: Ⓜ Ⓛ Ⓡ, Funktionslehren, Bonus-Toleranz |
| `references/06-passungen.md` | ISO 286: IT-Grade, Passungssysteme, empfohlene Passungen nach Funktion |
| `references/07-oberflaechen.md` | ISO 21920-1 / ISO 1302: Oberflächensymbol, Kenngrößen, typische Werte je Verfahren |
| `references/08-allgemeintoleranzen.md` | ISO 22081, ISO 2768-1/-2, ISO 13920, ISO 8062-3, DIN 16742 |
| `references/09-features.md` | Gewinde, Bohrungen, Senkungen, Freistiche, Zentrierbohrungen, Kanten (ISO 13715), Fasen, Nuten |
| `references/10-verfahren.md` | Verfahrensspezifisch: Drehteile, Frästeile, Blech, Schweißen (ISO 2553), Guss, Kunststoff |
| `references/11-pruefplanung.md` | Messmittel ↔ Spezifikation, ISO 14253-1, KMG vs. Handmessung |
| `references/12-zeichnungsformat.md` | ISO 5457, ISO 7200, ISO 128, ISO 5456, ISO 3098, Maßstäbe, Schnitte |
| `references/13-pruefliste.md` | Vollständige Prüfliste für jede Zeichnung |
| `references/14-generator.md` | Format der Zeichnungsbeschreibung für `scripts/zeichnung.py` (ohne CAD) |
| `references/15-cad-workflow.md` | CAD-Weg: Adapterstand, Merkmalsmodell, Zeichnungsauftrag, Platzierungsregeln, Fehlerbilder |

## Werkzeuge

- `scripts/passung.py` – ISO-286-Grenzabmaße und Passungsspiel, z. B. `python scripts/passung.py 25 H7/g6` oder `python scripts/passung.py 40 k6`.
- `scripts/zeichnung.py` – erzeugt aus einer JSON-Beschreibung eine normgerechte Zeichnung (SVG, optional PDF/PNG) mit Rahmen, Schriftfeld, Ansichten, Maßen, Toleranzrahmen, Bezügen, Oberflächenzeichen und prüft die Beschreibung auf typische Fehler. Format in `references/14-generator.md`.
- `scripts/cad/cad.py` – CAD-Anbindung: `erkennen`, `analysieren <teil>`, `zeichnen <auftrag.json>`, `export <zeichnung>`, `schliessen`, `selbsttest`. SolidWorks und FreeCAD getestet; Inventor und CATIA V5 ungetestet (CATIA teilautomatisch mit Eintrageliste). Details in `references/15-cad-workflow.md`.

Pfade sind relativ zu diesem Skill-Ordner. Python immer mit `python -I` aufrufen.

## Ausgabeformen

- **Prüfung einer vorhandenen Zeichnung:** Befundliste, sortiert nach Schwere (Fehler: mehrdeutig/unvollständig/funktionswidrig → Verbesserung → Stil). Jeder Befund: Ort auf der Zeichnung, was falsch ist, Normbezug, konkrete korrigierte Eintragung.
- **Tolerierungskonzept:** Tabelle Merkmal → Funktion → Spezifikation (exakt so, wie sie auf der Zeichnung stehen soll) → Prüfmittel.
- **Erzeugte Zeichnung (neutral):** JSON-Beschreibung + gerenderte Datei, nach `scripts/zeichnung.py` ohne Fehler. Nach dem Rendern das PNG ansehen und Überlappungen, Lesbarkeit und Vollständigkeit selbst kontrollieren.
- **Erzeugte Zeichnung (CAD):** Zeichnungsauftrag + native CAD-Zeichnung + PDF, Protokoll mit 0 Fehlern, PDF mit dem Read-Werkzeug gesichtet. Bei ungetesteten Adaptern das ausdrücklich sagen.

Schreibweise der Rahmen in Text: `|⌖|⌀0,1 Ⓜ|A|B|C|` (Zellen durch `|` getrennt).
