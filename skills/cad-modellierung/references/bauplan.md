# Bauplan-Format (JSON)

Ein Bauplan beschreibt ein Einzelteil als Folge von Features. Dieselbe Datei baut in FreeCAD **und** SolidWorks dasselbe Teil (in Tests volumengleich).

```json
{
  "name": "Halter",
  "werkstoff": "S235",
  "features": [ … ],
  "soll": {"huelle": [0, 0, 0, 80, 40, 10]}
}
```

| Feld | Pflicht | Bedeutung |
|---|---|---|
| `name` | ja | Teilename = Dateiname |
| `werkstoff` | nein | Text; bekannte Werkstoffe liefern die Dichte für die Masse (Stahl, S235, C45, 1.4301, Alu, EN AW-6082, Messing, PLA, PETG, ABS, ASA, PA12, POM …) |
| `dichte` | nein | g/cm³, überschreibt den Werkstoff |
| `features` | ja | Liste, wird in dieser Reihenfolge gebaut |
| `soll.huelle` | **immer angeben** | `[xmin, ymin, zmin, xmax, ymax, zmax]` (oder `[dx, dy, dz]`). Wird nach dem Bau auf 0,01 mm geprüft und findet Lage- und Richtungsfehler. |
| `soll.volumen` | nein | mm³, Toleranz `soll.toleranz_volumen_prozent` (Standard 0,5) |

## Koordinaten

Alle Maße in mm. Z ist oben. Jedes Feature, das skizziert, nennt eine **Ebene** und optional einen **Versatz**:

| `ebene` | u → | v → | Plus-Richtung / Versatz entlang |
|---|---|---|---|
| `XY` | X | Y | +Z |
| `XZ` | X | Z | +Y |
| `YZ` | Y | Z | +X |

`versatz: 10` auf `XY` heißt: Skizze liegt bei z = 10. `richtung`: `"+"` (zur Plus-Richtung), `"-"` oder `"beide"` (symmetrisch, Gesamtmaß).
Skizzenpunkte sind `[u, v]` in dieser Ebene. Beispiel `XZ`: `[40, 5]` ist x = 40, z = 5.

Tipp: Den Nullpunkt so legen, dass die Hauptmaße einfache Zahlen werden (Teil ab 0 aufbauen oder symmetrisch um 0).

## Profile (`profil`: Liste von Formen)

Jede Form ergibt eine oder mehrere geschlossene Konturen. Innere Konturen in einer äußeren werden zu Löchern (wie im CAD).

| Form | Felder |
|---|---|
| Rechteck | `{"rechteck": [b, h], "mitte": [u, v]}` oder `"ecke": [u, v]` (links unten); optional `"r"` (Eckenradius), `"winkel"` |
| Kreis | `{"kreis": d, "mitte": [u, v]}` |
| Langloch | `{"langloch": [länge gesamt, breite], "mitte": [u, v], "winkel": 0}` |
| Vieleck | `{"vieleck": n, "sw": schlüsselweite}` oder `"d"` (Umkreis), `"mitte"`, `"winkel"` |
| Kontur | `{"kontur": [[u, v], [u, v], {"bis": [u, v], "r": R}, {"bis": [u, v], "durch": [u, v]}, …]}` – schließt sich selbst. Bogen: `r > 0` wölbt links in Laufrichtung, `r < 0` rechts, `"gross": true` für den langen Bogen. |

**Mehrere Positionen** (bei rechteck, kreis, langloch, vieleck und bei `bohrung`):
- `"mitte": [[u1, v1], [u2, v2]]`
- `"muster": {"raster": {"start": [u, v], "anzahl": [nx, ny], "abstand": [dx, dy]}}`
- `"muster": {"kreis": {"mitte": [u, v], "r": R, "anzahl": n, "start_winkel": 0, "teilung": 360/n}}`

## Features

Jedes Feature hat `typ` und sollte eine sprechende `id` haben (wird Name im Feature-Baum).

| typ | Felder | Wirkung |
|---|---|---|
| `block` | `ebene`, `versatz`, `profil`, `hoehe`, `richtung` (Std. `+`) | Extrusion, fügt Material hinzu |
| `tasche` | `ebene`, `versatz`, `profil`, `tiefe` **oder** `durch: true`, `richtung` (Std. `-`) | Extrusionsschnitt |
| `drehteil` | `ebene`, `achse` (in der Ebene, durch 0), `profil` (halbe Kontur, eine Seite der Achse), `winkel` (Std. 360) | Rotation |
| `drehnut` | wie `drehteil` | Rotationsschnitt (Einstich, Freistich, Nut) |
| `bohrung` | `ebene`, `versatz` (= Oberfläche), `mitte`/`muster`, `d` **oder** `gewinde: "M6"` / `"M10x1"` **oder** `durchgang: "M6"`, `tiefe` oder `durch`, `richtung` (Std. `-`), optional `gewindetiefe`, `flachsenkung: {"d", "tiefe"}`, `senkung: {"d", "winkel": 90}` | Bohrung mit flachem Grund. Gewinde: Kernloch d − P und kosmetisches Gewinde. `durchgang`: ISO 273 mittel. |
| `fase` | `kanten` (Auswahl), `laenge`, optional `winkel` (45) | Fase |
| `verrundung` | `kanten`, `r` | Verrundung |
| `schale` | `flaechen` (zu öffnende Flächen), `dicke`, `nach` (`innen`) | Aushöhlen |
| `frei` | `beschreibung`, `freecad` (Code), `solidworks` (Code) | Programmcode für Sonderfälle, siehe freie-skripte.md |

Fase und Verrundung nehmen tangential anschließende Kanten automatisch mit (`"tangential": false` schaltet das ab). Ohne Tangentenfortsetzung scheitern Fasen an gerundeten Ecken in jedem CAD.

## Kanten- und Flächenauswahl

Auswahl über Geometrie, nicht über interne Namen. Alle Bedingungen eines Objekts müssen zutreffen; eine Liste von Objekten ist die Vereinigung.

**Kanten** (`kanten`):

| Schlüssel | Bedeutung |
|---|---|
| `"alle"` | alle Kanten |
| `"parallel": "Z"` | gerade Kanten parallel zur Achse |
| `"in_ebene": {"Z": 10}` | Kante liegt ganz in der Ebene z = 10 |
| `"kreis": true`, `"d": 6.6` | Kreiskanten (mit Durchmesser) |
| `"box": [xmin, ymin, zmin, xmax, ymax, zmax]` | Kantenmitte im Quader |
| `"nahe": [[x, y, z], …]` | je Punkt die nächstgelegene Kante unter den übrigen Treffern |

Beispiele: äußere Oberkante einer Platte `{"in_ebene": {"Z": 10}, "nahe": [[40, 0, 10], [80, 20, 10], [40, 40, 10], [0, 20, 10]]}` (mit Tangentenfortsetzung reicht ein Punkt je gerader Seite). Senkrechte Ecken `{"parallel": "Z"}`. Wellenende `{"d": 20, "in_ebene": {"X": 0}}`.

**Flächen** (`flaechen`): `"normale": "+Z"` (zeigt aus dem Material) mit `"lage": "max" | "min" | Wert`, `"zylinder": d`, `"box"`, `"nahe"`.

## Prüfungen beim Bau

Jedes Feature wird gebaut und geprüft. Fehler stehen mit Feature-ID im Bericht:
- Feature ließ sich nicht bilden → wird entfernt, die Vorschau zeigt den letzten guten Stand
- Volumen ändert sich nicht in die erwartete Richtung (Tasche schneidet nichts = falsche Richtung/Lage)
- Körper zerfällt in mehrere Teile
- Schale wächst nach außen
- Soll-Hülle / Soll-Volumen weicht ab
- STL-Hülle weicht vom Modell ab (Exporteinheit)

Bei Fehlern entstehen keine Austauschdateien (nur die native Datei zur Diagnose).

## Konstruktionsregeln, die die Prüfung meldet

- Außenradius ≤ Wandstärke einer späteren Schale → innen entsteht eine entartete Kante. Radius > Wandstärke wählen.

## Beispiel: Welle

```json
{"name": "Welle", "werkstoff": "C45",
 "features": [
  {"id": "Rohteil", "typ": "drehteil", "ebene": "XZ", "achse": "X",
   "profil": [{"kontur": [[0,0],[0,10],[30,10],[30,15],[90,15],[90,12.5],[120,12.5],[120,0]]}]},
  {"id": "Einstich", "typ": "drehnut", "ebene": "XZ", "achse": "X", "profil": [{"rechteck": [2, 1.5], "ecke": [60, 13.5]}]},
  {"id": "Zentrierung", "typ": "bohrung", "ebene": "YZ", "mitte": [0, 0], "gewinde": "M8", "tiefe": 20, "gewindetiefe": 16, "richtung": "+"},
  {"id": "Passfedernut", "typ": "tasche", "ebene": "XY", "versatz": 12.5, "profil": [{"langloch": [22, 8], "mitte": [105, 0]}], "tiefe": 4},
  {"id": "Endfasen", "typ": "fase", "kanten": [{"d": 20, "in_ebene": {"X": 0}}, {"d": 25, "in_ebene": {"X": 120}}], "laenge": 1},
  {"id": "Schulterradius", "typ": "verrundung", "kanten": {"kreis": true, "in_ebene": {"X": 30}, "d": 20}, "r": 0.8}],
 "soll": {"huelle": [0, -15, -15, 120, 15, 15]}}
```

## Beispiel: Gehäuse (3D-Druck)

```json
{"name": "Gehaeuse", "werkstoff": "PETG",
 "features": [
  {"id": "Grundkoerper", "typ": "block", "ebene": "XY", "profil": [{"rechteck": [60, 40], "mitte": [0, 0], "r": 4}], "hoehe": 25},
  {"id": "Bodenradius", "typ": "verrundung", "kanten": {"in_ebene": {"Z": 0}}, "r": 3},
  {"id": "Aushoehlung", "typ": "schale", "flaechen": {"normale": "+Z", "lage": "max"}, "dicke": 2},
  {"id": "Kabelausschnitt", "typ": "tasche", "ebene": "YZ", "versatz": 30, "profil": [{"rechteck": [12, 6], "mitte": [0, 15], "r": 1}], "tiefe": 5},
  {"id": "Bodenschrauben", "typ": "bohrung", "ebene": "XY", "richtung": "+", "muster": {"kreis": {"mitte": [0, 0], "r": 12, "anzahl": 4, "start_winkel": 45}},
   "d": 3.4, "durch": true, "senkung": {"d": 6.5, "winkel": 90}}],
 "soll": {"huelle": [-30, -20, 0, 30, 20, 25]}}
```
