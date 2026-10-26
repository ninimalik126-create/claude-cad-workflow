# Infophase: was für ein Modell gebraucht wird

Der Nutzer schreibt, was er hat (Text, Skizze, Foto, Zeichnung, altes Teil). Erst danach diese Liste abgleichen und **nur das Fehlende** fragen – gesammelt in **einer** Nachricht. Was sich vernünftig festlegen lässt, nicht fragen, sondern als Annahme nennen.

## Muss vorhanden sein (sonst fragen)

| # | Information | Woran man merkt, dass sie fehlt |
|---|---|---|
| 1 | **Funktion** in einem Satz (was hält, führt, verbindet das Teil?) | Nur „mach mir ein Teil wie …“ |
| 2 | **Hauptmaße** (L × B × H, Ø, Länge) | Keine Zahl für eine Richtung |
| 3 | **Funktionsmaße**: Lochabstände, Bohrungs-Ø, Gewinde, Sitz-Ø, Wandstärken an Schnittstellen | Bohrungen/Gewinde erwähnt, aber ohne Größe oder Lage |
| 4 | **Fertigung**: 3D-Druck (FDM/SLA), Fräsen, Drehen, egal | Nicht genannt und nicht aus dem Werkstoff ableitbar |

Ein Foto oder eine Skizze **mit Maßen** ersetzt meist alle Rückfragen. Ein Foto ohne Maße: nach einem Referenzmaß fragen (Messschieber, bekannte Schraube, Lineal im Bild).

## Bei Bedarf (nur fragen, wenn es das Teil wirklich ändert)

| Information | Annahme, wenn nicht genannt |
|---|---|
| Werkstoff | 3D-Druck: PLA; Fräsen: Aluminium EN AW-6082; Drehen: Stahl C45 |
| Gegenstücke / Normteile (Schraube, Lager, Welle) | aus dem Text ableiten, z. B. „M5“ → Durchgang 5,5 (ISO 273 mittel) |
| Passungsstellen („muss auf 8-mm-Welle“) | Druck: Spiel siehe unten; Metall: Passung nach ISO 286 festlegen (`passung.py`) und nennen |
| Kanten | Metall: Außenkanten Fase 0,5 × 45°; Druck: Unterkante Fase statt Radius, sonst Radius 1 |
| Nullpunkt / Ausrichtung | Auflagefläche auf XY, Teil ab Ursprung oder symmetrisch um Z |
| Anzahl / Wichtigkeit | Einzelteil, keine Sonderanforderung |

## Richtwerte je Fertigung (als Annahme nennen, nicht als Norm)

**FDM-3D-Druck (Düse 0,4 mm)**
- Wandstärke ≥ 1,2 mm (3 Bahnen), tragend 2–3 mm
- Bohrungen fallen etwas kleiner aus: +0,2 mm auf den Nenn-Ø
- Spiel für Steck-/Gleitpassung 0,2–0,3 mm je Seite; Presssitz 0–0,1 mm (am Probedruck prüfen)
- Überhänge bis 45° ohne Stützen; Unterkanten fasen statt runden
- Gewinde unter M6 nicht drucken: Durchgangsbohrung + Mutter oder Gewindeeinsatz (Bohrungsmaß laut Hersteller des Einsatzes erfragen)
- Außenradius > Wandstärke, wenn später ausgehöhlt wird

**Fräsen**
- Innenecken mit Radius ≥ Fräserradius (z. B. r ≥ 3 bei Ø6-Fräser)
- Taschentiefe ≤ 3–4 × Fräser-Ø
- Gewinde: Kernloch d − P (rechnet der Bauplan), Gewindetiefe ca. 1,5 × d
- Dünne Wände Alu ≥ 1 mm

**Drehen**
- Schultern mit Passung: Freistich (DIN 509) oder Radius vorsehen
- Enden fasen; Zentrierbohrung bei langen Wellen

**Nicht automatisch abbildbar**: Blechteile mit Abwicklung (werden als Volumenteil gebaut), organische Freiformen (Ergonomiegriffe, Karosserie) – dafür Grundkörper liefern und das sagen.

## Ergebnis der Infophase

Vor dem Bau eine kurze Liste „So baue ich es“ (5–10 Zeilen): Hauptmaße, Features in Stichworten, getroffene Annahmen. Keine extra Bestätigung abwarten, außer bei großen Unsicherheiten – die Karte mit Programm und Ausgaben (siehe SKILL.md) ist der Bestätigungsschritt.
