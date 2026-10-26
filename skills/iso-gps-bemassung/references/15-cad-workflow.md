# 15 CAD-Arbeitsablauf (SolidWorks, FreeCAD, Inventor, CATIA V5)

Arbeitet der Nutzer mit einem 3D-CAD, läuft alles **im CAD**: Claude liest das 3D-Teil aus, legt das Tolerierungskonzept fest und erzeugt die native Zeichnung (bearbeitbar, mit echten CAD-Maßen, Toleranzrahmen, Bezügen, Oberflächenzeichen, Schriftfeld). Ohne CAD läuft der neutrale Weg über `scripts/zeichnung.py` (14-generator.md).

## Welcher Weg?

```
python -I scripts/cad/cad.py erkennen
```

| Situation | Weg |
|---|---|
| Nutzer nennt eine `.SLDPRT` / `.FCStd` / `.ipt` / `.CATPart` oder arbeitet erkennbar im CAD, Adapter installiert | **CAD-Weg** |
| Teil wurde mit dem Skill `cad-modellierung` gebaut | **CAD-Weg** im selben Programm |
| CAD-Zeichnung (`.SLDDRW` / `.idw` / `.CATDrawing`) soll geprüft werden | `cad.py export <zeichnung>` → PDF → `/zeichnung-pruefen` |
| Kein CAD, nur Beschreibung/Skizze/Maße | neutraler Generator |
| CAD vorhanden, aber Nutzer will nur Beratung | Tolerierungskonzept + Eintrageliste für das CAD |

Adapterstand:

| CAD | Stand | Umfang |
|---|---|---|
| SolidWorks (2020+; getestet 2026 dt.) | **getestet** | Analyse, Zeichnung, Ansichten, Mittellinien, Maße (Abstand, ⌀ in Längs- und Stirnansicht, Kanten, Punkte), Toleranzen (±, Abmaße, ISO-Passung mit Abmaßen, TED, Hilfsmaß, Ersatztext), Toleranzrahmen (an Fläche oder Maß), Bezüge, Oberflächen, Hinweise, Schriftfeld-Eigenschaften, SLDDRW, PDF, DXF |
| FreeCAD 1.1 (TechDraw) | **getestet** | Analyse, Blatt mit deutschem ISO-7200-Schriftfeld, Ansichten, Mittellinien (Bohrungen, Wellen, Bögen ≥ 180°), Maße (Abstand, ⌀ längs und Stirnansicht mit Hinweislinie, Punkte, Radius), Toleranzen (±, Abmaße, ISO-Passung mit Abmaßen über `passung.py`, TED, Hilfsmaß, Ersatztext), Toleranzrahmen, Bezüge, Oberflächen, Hinweise, FCStd, PDF, DXF. Rahmen/Bezüge/Oberflächen sind Symbole mit Hinweislinie (nicht an Kanten gebunden). |
| Autodesk Inventor | ungetestet | wie SolidWorks über die Inventor-API; beim ersten Einsatz Protokoll genau prüfen |
| CATIA V5 | ungetestet, teilautomatisch | Analyse, Blatt, Ansichten, Hinweise; Maße/Toleranzen als **Eintrageliste** (V5-Automation gibt generierte Kanten nicht heraus) |
| NX, Creo, Fusion, Solid Edge | kein Adapter | neutraler Weg + Eintrageliste aus dem Tolerierungskonzept; STEP/PDF des Nutzers für Geometrie |

Voraussetzungen: Windows, Python; für SolidWorks/Inventor/CATIA COM-Schnittstelle und `pywin32`. FreeCAD braucht nichts weiter (eigener Prozess, ca. 30 s je Zeichnung).

**Ansichtsrichtungen** (`richtung`) bedeuten in allen Adaptern dasselbe, wenn das Teil aus dem Bauplan stammt: Z ist oben, `vorne` = Blick auf die −Y-Seite, `oben` = Blick von +Z, `rechts` = Blick von +X, `iso` von (+X, −Y, +Z). SolidWorks-Teile aus dem Bauplan enthalten dafür benannte Ansichten „Plan vorne“ …, die der Adapter vorrangig nimmt; bei anderen SolidWorks-Teilen gelten die SolidWorks-Normansichten (Y oben). FreeCAD akzeptiert zusätzlich `{"blick": [x, y, z], "x": [x, y, z]}`.

**Flächen-IDs** gelten nur für die Analyse im jeweiligen Programm (FreeCAD und SolidWorks nummerieren unterschiedlich) – vor jedem Auftrag im Zielprogramm analysieren.

## Ablauf CAD-Weg

1. **Analysieren:** `python -I scripts/cad/cad.py analysieren <teil> -o <teil>-merkmale.json`
   Liefert jede Fläche mit ID (`F1` …), Typ, Lage und Maß in mm, plus `merkmale` (Rotationsteil, Achsen, Durchmesser). Die IDs bleiben gültig, solange das Teil nicht umkonstruiert wird; nach Änderungen neu analysieren.
2. **Verstehen:** Flächen den Funktionen zuordnen (Lagersitz, Anlage, Zentrierung …). Unklares beim Nutzer erfragen (siehe /tolerieren).
3. **Tolerierungskonzept** wie gewohnt (Bezüge, Passungen mit `passung.py`, Rahmen, Oberflächen).
4. **Auftrag schreiben** (JSON, Format unten), neben das Teil oder in einen Projektordner. Pfade unter ~250 Zeichen (SolidWorks-Grenze).
5. **Zeichnen:** `python -I scripts/cad/cad.py zeichnen <auftrag.json>` → Protokoll (JSON) mit jedem Schritt; `fehler` muss 0 sein.
6. **Sichtprüfung:** Das erzeugte PDF mit dem Read-Werkzeug ansehen und gegen 13-pruefliste.md prüfen (Überlappungen, Lage der Maße, Hinweislinien auf der richtigen Fläche). Positionen im Auftrag anpassen, erneut zeichnen. Vorher `cad.py schliessen`, damit keine alten Dokumente offen sind.
7. Ergebnis: Pfad der CAD-Zeichnung + PDF an den Nutzer. Die Zeichnung ist im CAD voll editierbar.

Das Teil selbst wird nie gespeichert. Schriftfeld-Eigenschaften, die das Blattformat aus dem Modell liest ($PRPSHEET), werden nur im geöffneten Teil gesetzt – soll das dauerhaft sein, den Nutzer fragen und im CAD speichern.

## Merkmalsmodell (Analyse-Ausgabe)

```json
{"cad": "solidworks", "einheit": "mm", "werkstoff": "...", "masse_kg": 0.094,
 "huelle_mm": [xmin, ymin, zmin, xmax, ymax, zmax],
 "flaechen": [
   {"id": "F1", "typ": "ebene", "normale": [-1, 0, 0], "normale_achse": "-X", "x": 0.0, "lage": 0.0, "flaeche_mm2": 254.5},
   {"id": "F5", "typ": "zylinder", "art": "aussen", "d": 25.0,
    "achse": {"punkt": [0, 0, 0], "richtung": [1, 0, 0], "name": "X"}, "bereich": [20.0, 40.0]},
   {"id": "F2", "typ": "kegel", "art": "aussen", "halber_winkel_grad": 45.0, "bereich": [0.0, 1.0], "achse": {...}}],
 "merkmale": {"rotationsteil": true, "achsen": [...], "durchmesser": [{"art": "aussen", "d": 16.0}, ...]}}
```
- `normale` zeigt aus dem Material heraus. `art`: `aussen` = Welle/Bund, `innen` = Bohrung.
- `bereich`: Ausdehnung entlang der Achse (mm, in Achsrichtung gemessen).

## Zeichnungsauftrag

Blattkoordinaten im Auftrag: **mm, Ursprung links unten, y nach oben** (CAD-Konvention; anders als beim neutralen Generator). A3 quer = 420 × 297. Das SolidWorks-ISO-Schriftfeld belegt rechts unten etwa x 230–410, y 10–80.

```json
{
  "cad": "solidworks",
  "teil": "Welle.SLDPRT",
  "ausgabe": {"name": "MF-1001-01", "ordner": ".", "pdf": true, "dxf": false},
  "blatt": {"format": "A3", "massstab": "2:1", "vorlage": null, "blattformat": null},
  "eigenschaften": {"Benennung": "...", "Zeichnungsnummer": "...", "Werkstoff": "...", "Masse": "auto",
                    "Gezeichnet": "...", "Geprueft": "...", "Genehmigt": "...", "Datum": "JJJJ-MM-TT",
                    "Index": "A", "Eigentuemer": "..."},
  "ansichten": [{"id": "V", "richtung": "vorne", "pos": [200, 175], "massstab": null}],
  "mittellinien": "auto",
  "masse": [...], "bezuege": [...], "rahmen": [...], "oberflaechen": [...], "hinweise": [...]
}
```
- `blatt.vorlage` (.drwdot / .idw-Vorlage) und `blatt.blattformat` (.slddrt) für Firmenvorlagen; sonst CAD-Standard „ISO“ der installierten Sprache. **Firmenvorlage nutzen, wenn vorhanden** – das Standard-Schriftfeld von SolidWorks enthält Texte wie „Zeichnung nicht skalieren“, die nicht ISO 7200 entsprechen.
- `richtung`: `vorne`, `hinten`, `oben`, `unten`, `links`, `rechts`, `iso` (Modellansichten des CAD).
- `mittellinien: "auto"`: für jede Rotationsachse, die in der Ansichtsebene liegt, eine durchgehende Mittellinie.

**Maße** (`masse`):

| typ | Felder | Wirkung |
|---|---|---|
| `abstand` | `von`, `bis` (Flächen-IDs, Ebenen in Kantenansicht), `lage` (`unten`/`oben`/`links`/`rechts`), `abstand` (mm Papier vom Ansichtsrand) oder `pos` [x, y] | Längenmaß zwischen zwei Flächen |
| `durchmesser` | `flaeche` (Zylinder), `bei` (axiale Lage in mm, Standard Mitte), `textpos` | ⌀ in Längsansicht (zwischen den Mantellinien) oder Stirnansicht (Kreis) |
| `punkte` | `a`, `b` (Modellpunkte mm auf den Kanten), `pos` | freies Maß zwischen zwei Kanten |
| `kante` / `radius` | `punkt` (Modellpunkt auf Kreis/Bogen), `pos` | Radius/Durchmesser einer Kante |

Gemeinsame Felder: `id` (für Bezüge/Rahmen), `ansicht`, `tol` (`"g6"`, `"H7"`, `"±0,05"`, `"+0,1/-0,05"`), `abmasse` (Passung mit Abmaßen, Standard true), `ted`, `hilfsmass`, `vor`, `nach` (z. B. `"Ⓔ"`), `text` (Ersatztext, z. B. `"M16"`).

**Bezüge** (`bezuege`): `buchstabe`, `an` (Maß-ID → Achsbezug in Verlängerung der Maßlinie) **oder** `flaeche` (Bezugsfläche), `versatz` [dx, dy] mm, `seite` (`oben`/`unten`).

**Toleranzrahmen** (`rahmen`): `zellen` (wie im Generator: `["lauf", "0,02", "A-B"]`, `["position", "⌀0,1 Ⓜ", "A", "B", "C"]`, mehrzeilig als Liste von Listen), `an` (Maß-ID → abgeleitetes Element/Achse) **oder** `flaeche` (+ `bei`, `anteil` 0…1 für Ebenen, `seite`), `versatz` / `pos`, `darueber` (z. B. `"4× ⌀6,6"`).

**Oberflächen**: `text` (`"Ra 0,8"`), `art` (`abtragen`/`beliebig`/`ohne`), `flaeche` + `bei`, `versatz`, `verfahren`.

**Hinweise**: `text` (Liste von Zeilen), `pos` [x, y] mm.

Sonderzeichen wie im Generator: `⌀ Ⓜ Ⓛ Ⓟ Ⓔ Ⓕ Ⓣ □ ⌴ ⌵ ↧ ± °` bzw. `{D}`, `{M}` … – der Adapter setzt sie in CAD-Symbolcodes um.

## Platzierungsregeln (aus dem SolidWorks-Test)

- Ansicht so legen, dass oben ≥ 60 mm (Rahmen, Bezüge, Oberflächen) und unten ≥ 40 mm (Maßketten) frei sind.
- Längenmaße einer Kette mit gleichem `abstand` (10), weitere Reihen +10 mm.
- Durchmesser in der Längsansicht mit `bei` mittig auf den Absatz, sodass Bezüge (`an`) und Rahmen (`flaeche` + abweichendes `bei`) nicht kollidieren.
- Rahmen: `versatz` so wählen, dass Hinweislinien sich nicht kreuzen; für Planflächen (Schultern) `anteil` 0,85–0,95, damit der Pfeil auf der Schulterfläche endet.
- Nach jedem Lauf das PDF ansehen; Abstände nachjustieren.

## Fehlerbilder

| Meldung | Ursache / Abhilfe |
|---|---|
| `an Blattpunkt … nichts auswählbar` | Fläche in dieser Ansicht nicht sichtbar (verdeckt, Blickrichtung) → andere Ansicht oder `bei`/`anteil` ändern |
| `Pfad zu lang` | Ausgabeordner kürzer wählen |
| Maß mit falschem Wert im Protokoll | Auswahl hat Nachbarkante getroffen → `bei` verschieben oder `punkte`-Maß verwenden |
| `Fläche … nicht in der Analyse` | Teil wurde geändert → neu analysieren, IDs im Auftrag anpassen |
| Bezug „nicht angehängt“ | Fläche/Maß nicht auswählbar → `flaeche` statt `an` |
| FreeCAD: `keine sichtbare Ecke auf Fläche …` | Fläche steht in dieser Ansicht nicht auf Kante → andere Ansicht |
| FreeCAD: `Mantellinien … nicht sichtbar` | Zylinder verdeckt oder Blick entlang der Achse → Stirnansicht nehmen |
| FreeCAD: Maßzahl/Rahmen überlappen | `pos`/`versatz` anpassen; Protokoll erkennt Überlappungen nicht, darum PDF ansehen |
