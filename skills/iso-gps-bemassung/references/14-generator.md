# 14 Zeichnungsgenerator `scripts/zeichnung.py`

Erzeugt aus einer JSON-Beschreibung eine Zeichnung nach ISO 5457/7200/128/129-1/1101 als SVG, optional PDF und PNG (über Edge/Chrome headless). Es wird nur die Python-Standardbibliothek benötigt. Vollständiges Beispiel: `beispiele/welle.json`.

```
python -I scripts/zeichnung.py teil.json --pdf --png        # schreibt teil.svg/.pdf/.png neben die JSON
python -I scripts/zeichnung.py teil.json -o out/teil.svg --png
python -I scripts/zeichnung.py teil.json --nur-pruefen
```

Die Ausgabe enthält eine **Prüfung** mit FEHLER und WARNUNG: fehlende Pflichtangaben, falsche Rahmensyntax, undefinierte/unbenutzte Bezüge, Dezimalpunkt, ungleiche Dezimalstellen, Überlappungen, Text von Linien geschnitten, außerhalb des Rahmens, auf dem Schriftfeld. **Arbeitsablauf:** schreiben → rendern → alle Fehler und Warnungen beheben → PNG mit dem Read-Werkzeug ansehen und Layout selbst beurteilen → wiederholen, bis alles sauber ist.

## Koordinaten

- **Blatt:** mm, Ursprung links oben, y nach unten. A4 hoch 210×297, A3 quer 420×297. Zeichenfläche innerhalb des Rahmens: x 20 … B−10, y 10 … H−10. Das Schriftfeld (180×48) liegt rechts unten, Hinweise und die Oberflächen-Sammelangabe stehen links bündig darüber. Unter x ≥ B−190 und y ≥ H−100 (A3) nichts platzieren.
- **Teil:** mm in Teilkoordinaten, y nach **oben**. Jede Ansicht hat `ursprung` (Blattposition des Teilnullpunkts) und `massstab` (z. B. `"2:1"`).
- `abstand`, `versatz`, `knick`, `laenge`, `textpos` sind **Papier-mm** (unabhängig vom Maßstab). Bei `versatz`/`knick` zeigt **y nach oben** (positiv = über dem Ziel).
- Winkel in Grad, mathematisch: 0 = rechts, 90 = oben.

## Oberste Ebene

```json
{
  "blatt": {"format": "A3", "ausrichtung": "quer"},
  "schriftfeld": {"eigentuemer": "", "titel": "", "untertitel": "", "zeichnungsnummer": "", "index": "",
                  "werkstoff": "Zeile 1\nZeile 2", "massstab": "1:1", "masse": "", "erstellt": "", "genehmigt": "",
                  "datum": "JJJJ-MM-TT", "status": "Entwurf", "dokumentart": "Fertigungszeichnung", "sprache": "de",
                  "blatt": "1/1"},
  "hinweise": ["Tolerierung ISO 8015", "Allgemeintoleranzen ISO 2768-1 – m", "Werkstückkanten ISO 13715: −0,3"],
  "oberflaeche_sammel": {"art": "abtragen", "wert": "Ra 3,2", "klammer": ["Ra 0,8"]},
  "ansichten": [ { "name": "", "ursprung": [x, y], "massstab": "1:1", "titel": "A–A", "elemente": [], "masse": [] } ]
}
```

## Sonderzeichen in allen Texten

`{D}` oder `⌀` Durchmesser · `{SQ}` □ Quadrat · `{CB}` ⌴ Flachsenkung · `{CS}` ⌵ Kegelsenkung · `{DP}` ↧ Tiefe · `{E}` `{M}` `{L}` `{P}` `{F}` `{R}` `{T}` `{U}` `{A}` `{C}` `{G}` `{N}` `{X}` eingekreiste Buchstaben (Ⓔ Ⓜ … gehen auch). `-` vor Ziffern wird zu `−`. Dezimalkomma verwenden.

## Elemente (Geometrie, Teilkoordinaten)

| typ | Felder | Hinweis |
|---|---|---|
| `linie` | `p: [[x,y],…]`, `art`, `geschlossen` | Polylinie |
| `rechteck` | `p1`, `p2`, `art` | |
| `kreis` | `m`, `r`, `art` | |
| `bogen` | `m`, `r`, `von`, `bis` (Grad, gegen Uhrzeigersinn), `art` | |
| `mittellinie` | `p: [[a],[b]]`, `ueberstand` (3) | Strichpunktlinie, verlängert |
| `mittelkreuz` | `m`, `r`, `ueberstand` (3) | bei kleinen Kreisen automatisch Volllinie |
| `teilkreis` | `m`, `r` | Strichpunkt-Kreis |
| `gewindekreis` | `m`, `r`, `von` (0) | ¾-Kreis schmal (Kern bei Außengewinde, Nenn-⌀ bei Innengewinde) |
| `schraffur` | `p` (Polygon), `loecher` (Liste von Polygonen), `winkel` (45), `abstand` (2,5 Papier-mm) | |

`art`: `kontur` (breit), `schmal`, `verdeckt`, `mitte`, `phantom` (Strich-Zweipunkt), `schnitt` (breiter Strichpunkt).

## Bemaßung und Symbole (`masse`)

**Längenmaß** `laenge`
```json
{"typ": "laenge", "p1": [0, -9], "p2": [20, -10], "richtung": "h", "lage": -16, "abstand": -12,
 "vor": "⌀", "tol": "g6", "nach": "{E}", "text": null, "ted": false, "hilfsmass": false, "textpos": null}
```
- `richtung`: `h` waagerecht, `v` senkrecht, `a` parallel zu p1→p2.
- Maßlinienlage: `h` → `abstand` > 0 über dem höheren Punkt, < 0 unter dem tieferen; `v` → > 0 rechts, < 0 links; mit `lage` (Teilkoordinate y bei `h`, x bei `v`) wird von dieser Linie aus gemessen → mehrere Maßreihen sauber ausrichten. `abstand: 0` setzt die Maßlinie direkt durch die Punkte (Durchmesser in der Längsansicht).
- Erste Maßreihe ≥ 10 mm von der Kontur, weitere je 8 mm.
- `tol`: `"±0,1"`, `"H7"`, `"+0,1/−0,05"` (gestapelt), `{"oben": "+0,021", "unten": "0"}`, `"H7 (+0,021/0)"`.
- `textpos`: Verschiebung der Maßzahl entlang der Maßlinie in Papier-mm (z. B. um die Mittellinie freizuhalten). Passt die Zahl nicht zwischen die Pfeile, wird sie automatisch außen angesetzt; bei zu wenig Platz kommen die Pfeile nach außen.
- `ted: true` → eingerahmtes theoretisch genaues Maß. `hilfsmass: true` → (Klammern).

**Durchmesser am Kreis** `durchmesser`: `m`, `r`, `winkel` (45), `laenge` (8), `tol`, `nach`. Maßlinie durch den Mittelpunkt, Text auf Schulter außen. Kleine Bohrungen besser mit `hinweis` bemaßen.

**Radius** `radius`: `m`, `r`, `winkel`, `laenge`; Standard ist ein Pfeil von außen auf den Bogen. `innen: true` → Maßlinie vom Mittelpunkt mit Pfeil innen.

**Winkel** `winkel`: `s` (Scheitel), `p1`, `p2` (Punkte auf den Schenkeln), `radius` (Papier-mm), optional `text`.

**Hinweis/Hinweislinie** `hinweis`: `ziel`, `versatz` [dx, dy], `knick` [[dx,dy],…], `text` (String oder Liste von Zeilen), `ende`: `pfeil` (auf Kontur), `punkt` (in Fläche), `keins`. Für Bohrungen, Gewinde, Fasen: `"text": ["4× ⌀6,6", "⌴⌀11 ↧6,4"]`.

**Toleranzrahmen** `rahmen`
```json
{"typ": "rahmen", "ziel": [40, 14.5], "knick": [[-5, 0], [-5, 30]], "versatz": [5, 30],
 "zellen": ["lauf", "0,01", "A-B"], "darueber": "4× ⌀6,6", "rundum": false, "ende": "pfeil",
 "oberflaeche": "Ra 0,8"}
```
- `zellen`: erste Zelle Eigenschaft (`geradheit`, `ebenheit`, `rundheit`, `zylinderform`, `linienprofil`, `flaechenprofil`, `parallelitaet`, `rechtwinkligkeit`, `neigung`, `position`, `koaxialitaet`, `symmetrie`, `lauf`, `gesamtlauf` oder das Unicode-Symbol), dann Toleranz (`"⌀0,1 Ⓜ"`), dann Bezüge (`"A"`, `"A-B"`, `"BⓂ"`). Mehrere Zeilen übereinander: Liste von Listen.
- Hinweislinie: Rahmen-Anker = `ziel` + `versatz` (linke Rahmenmitte bei dx ≥ 0, rechte bei dx < 0). `knick`-Punkte relativ zum Ziel; der **letzte Abschnitt muss senkrecht auf der Fläche stehen** (Pfeilrichtung = Richtung der Toleranzzone).
- **Integralelement:** Pfeil auf Kontur, deutlich neben der Maßlinie. **Abgeleitetes Element (Achse):** Pfeil in Verlängerung der Maßlinie (Ziel = Pfeilspitze des Maßes).
- `oberflaeche`: Oberflächensymbol auf dem Rahmen (ISO 1302/21920-1), spart Platz.
- Ohne `ziel`, aber mit `pos`: frei stehender Rahmen (z. B. an Maß angehängt, dann selbst platzieren).

**Bezug** `bezug`: `buchstabe`, `ziel` (Punkt auf Kontur bzw. Maßpfeilende für Achsbezug), `richtung` (Grad, vom Ziel zum Kästchen), `laenge` (5), `gefuellt` (true).

**Oberfläche** `oberflaeche`: `ziel`, `normale` (90 oben oder 180 links; andere Richtungen mit `hinweis`), `text` (String/Liste), `art` (`abtragen`, `beliebig`, `ohne`), `verfahren`, `rundum`, `hinweis` [dx, dy] → Symbol auf Bezugslinie mit Pfeil.

**Text** `text`: `pos` (Teil) oder `blatt` [x, y], `text`, `h` (3,5), `anker` (`start`/`middle`/`end`), `drehung`.

**Schnittlinie** `schnittlinie`: `p` [[a],[b]] (Teil), `name` (`"A"`), `blick` (Grad, Blickrichtung). Die Schnittansicht bekommt `"titel": "A–A"`.

**Einzelheit** `einzelheit`: `m`, `r`, `name`, `winkel` – die vergrößerte Ansicht bekommt `"titel": "Z (5:1)"` und eigenen `massstab`.

## Layoutregeln für saubere Ergebnisse

1. Hauptansicht so platzieren, dass rundherum ≥ 35 mm Platz für Maße bleibt; Ansichten nach Projektionsmethode 1 anordnen (Draufsicht unter, Seitenansicht von links rechts neben der Vorderansicht), ≥ 30 mm Abstand.
2. Maßreihen von innen nach außen: kurze Maße innen, Gesamtmaß außen. `lage` für gleiche Höhe nutzen.
3. Durchmesser in der Längsansicht mit `abstand: 0` und `textpos`, sodass die Zahl nicht auf der Mittellinie liegt.
4. Toleranzrahmen über der Ansicht staffeln, Hinweislinien nicht kreuzen lassen. Achsbezüge in Verlängerung der Durchmesser-Maßlinie.
5. Nach jedem Rendern die PNG ansehen: Lesbarkeit, Pfeilrichtung, Abstände, Symmetrie.
6. Grenzen: keine automatische Ansichtsableitung aus 3D. Die Geometrie wird aus den Funktions- und Maßangaben selbst konstruiert. Gewindedarstellung und Schraffur sind explizit zu zeichnen.
