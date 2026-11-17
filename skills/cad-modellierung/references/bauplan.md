# Bauplan-Format (JSON)

Ein Bauplan beschreibt ein Einzelteil als Folge von Features. Die Grundfeatures bauen in FreeCAD **und** SolidWorks dasselbe Teil (in Tests volumengleich); was nur FreeCAD kann, ist mit **FC** markiert.

```json
{
  "name": "Halter",
  "werkstoff": "S235",
  "fertigung": "fraesen",
  "parameter": {"L": 80, "B": 40, "t": 10, "rand": 12},
  "features": [ … ],
  "soll": {"huelle": [0, 0, 0, "=L", "=B", "=t"]}
}
```

| Feld | Pflicht | Bedeutung |
|---|---|---|
| `name` | ja | Teilename = Dateiname |
| `werkstoff` | nein | Text; bekannte Werkstoffe liefern die Dichte für die Masse (Stahl, S235, C45, 1.4301, Alu, EN AW-6082, Messing, PLA, PETG, ABS, ASA, PA12, POM …) |
| `dichte` | nein | g/cm³, überschreibt den Werkstoff |
| `fertigung` | empfohlen | `fdm`, `sla`, `fraesen` oder `drehen` – schaltet die passenden Konstruktionshinweise ein; bei `fdm` zusätzlich Überhang und Auflagefläche in der gebauten Lage (Z nach oben) |
| `parameter` | empfohlen | benannte Maße, siehe unten |
| `features` | ja | Liste, wird in dieser Reihenfolge gebaut |
| `soll.huelle` | **immer angeben** | `[xmin, ymin, zmin, xmax, ymax, zmax]` (oder `[dx, dy, dz]`). Wird nach dem Bau auf 0,01 mm geprüft und findet Lage- und Richtungsfehler. |
| `soll.volumen` | nein | mm³, Toleranz `soll.toleranz_volumen_prozent` (Standard 0,5) |
| `ansichten` | nein | Ansichten des Vorschaubilds, siehe unten |

## Parameter

Jede Zahl im Plan darf ein Ausdruck sein: eine Zeichenkette, die mit `=` beginnt. Parameter dürfen frühere Parameter verwenden (`"t": "=L/8"`).

- Rechnen: `+ - * / ** % //`, Klammern, `a if b else c`, Vergleiche.
- Funktionen: `sin cos tan asin acos atan atan2` (in **Grad**), `sqrt abs min max round floor ceil`, Konstante `pi`.
- Beispiel: `"mitte": ["=L/2 - rand", "=B/2"]`, `"d": "=dk + 0.2"`.
- Variante ohne Planänderung: `modell.py bauen plan.json --param L=100,rand=15 --name Halter-100`.
- In `frei`-Code und freien Skripten stehen die Werte als `P["L"]` bereit.

Maße, die mehrfach vorkommen oder sich ändern können, gehören in `parameter`. `soll.huelle` darf Parameter verwenden, wird aber unabhängig von den Features hingeschrieben – das hält die Kontrolle scharf.

## Koordinaten

Alle Maße in mm. Z ist oben. Jedes Feature, das skizziert, nennt eine **Ebene** und optional einen **Versatz**:

| `ebene` | u → | v → | Plus-Richtung / Versatz entlang |
|---|---|---|---|
| `XY` | X | Y | +Z |
| `XZ` | X | Z | +Y |
| `YZ` | Y | Z | +X |

`versatz: 10` auf `XY` heißt: Skizze liegt bei z = 10. `richtung`: `"+"` (zur Plus-Richtung), `"-"` oder `"beide"` (symmetrisch, Gesamtmaß).
Skizzenpunkte sind `[u, v]` in dieser Ebene. Beispiel `XZ`: `[40, 5]` ist x = 40, z = 5.

**Geneigte Ebene (FC):** statt des Namens ein Objekt
`{"basis": "XY", "ursprung": [30, 0, 10], "drehen": [["X", 60]]}` – die Grundebene wird nacheinander um globale Achsrichtungen gedreht (Rechte-Hand-Regel), u = v = 0 liegt im `ursprung`. Plus-Richtung und `versatz` drehen mit. Für schräge Bohrungen, Taschen und Anbauten.

Tipp: Den Nullpunkt so legen, dass die Hauptmaße einfache Zahlen werden (Teil ab 0 aufbauen oder symmetrisch um 0).

## Profile (`profil`: Liste von Formen)

Jede Form ergibt eine oder mehrere geschlossene Konturen. Innere Konturen in einer äußeren werden zu Löchern (wie im CAD).

| Form | Felder |
|---|---|
| Rechteck | `{"rechteck": [b, h], "mitte": [u, v]}` oder `"ecke": [u, v]` (links unten); optional `"r"` (Eckenradius), `"winkel"` |
| Kreis | `{"kreis": d, "mitte": [u, v]}` |
| Langloch | `{"langloch": [länge gesamt, breite], "mitte": [u, v], "winkel": 0}` |
| Vieleck | `{"vieleck": n, "sw": schlüsselweite}` oder `"d"` (Umkreis), `"mitte"`, `"winkel"` |
| Mutter | `{"mutter": "M5", "spiel": 0.2, "mitte": [u, v]}` – Sechskant nach ISO 4032 (M2 … M20), `spiel` wird auf die Schlüsselweite addiert (FDM 0,2–0,3). Mutterhöhe M3 2,4 · M4 3,2 · M5 4,7 · M6 5,2 · M8 6,8 |
| Kontur | `{"kontur": [[u, v], [u, v], {"bis": [u, v], "r": R}, {"bis": [u, v], "durch": [u, v]}, …]}` – schließt sich selbst. Bogen: `r > 0` wölbt links in Laufrichtung, `r < 0` rechts, `"gross": true` für den langen Bogen. |

**Mehrere Positionen** (bei rechteck, kreis, langloch, vieleck, mutter und bei `bohrung`):
- `"mitte": [[u1, v1], [u2, v2]]`
- `"muster": {"raster": {"start": [u, v], "anzahl": [nx, ny], "abstand": [dx, dy]}}`
- `"muster": {"kreis": {"mitte": [u, v], "r": R, "anzahl": n, "start_winkel": 0, "teilung": 360/n}}`

## Features

Jedes Feature hat `typ` und sollte eine sprechende `id` haben (wird Name im Feature-Baum).

| typ | Felder | Wirkung |
|---|---|---|
| `block` | `ebene`, `versatz`, `profil`, `hoehe`, `richtung` (Std. `+`), `schraege` **FC** | Extrusion, fügt Material hinzu. `schraege` in Grad: positiv verjüngt in Extrusionsrichtung (Entformungsschräge) |
| `tasche` | `ebene`, `versatz`, `profil`, `tiefe` **oder** `durch: true`, `richtung` (Std. `-`), `schraege` **FC** | Extrusionsschnitt |
| `drehteil` | `ebene`, `achse` (in der Ebene, durch 0), `profil` (halbe Kontur, eine Seite der Achse), `winkel` (Std. 360) | Rotation |
| `drehnut` | wie `drehteil` | Rotationsschnitt (Einstich, Freistich, Nut) |
| `bohrung` | `ebene`, `versatz` (= Oberfläche), `mitte`/`muster`, `d` **oder** `gewinde: "M6"` / `"M10x1"` **oder** `durchgang: "M6"`, `tiefe` oder `durch`, `richtung` (Std. `-`), optional `gewindetiefe`, `flachsenkung: {"d", "tiefe"}`, `senkung: {"d", "winkel": 90}`, `spitze: 118` **FC**, `gewinde_modelliert: true` + `gewindespiel` **FC** | Bohrung mit flachem Grund. Gewinde: Kernloch d − P und kosmetisches Gewinde. `durchgang`: ISO 273 mittel. `spitze`: Bohrkegel, `tiefe` zählt bis zur Schulter. `gewinde_modelliert`: echtes Gewindeprofil für den Druck (ab M6), `gewindespiel` z. B. 0,3 |
| `fase` | `kanten` (Auswahl), `laenge`, optional `winkel` (45) | Fase |
| `verrundung` | `kanten`, `r` | Verrundung |
| `schale` | `flaechen` (zu öffnende Flächen), `dicke`, `nach` (`innen`) | Aushöhlen |
| `muster` **FC** | `von` (ID oder Liste von IDs; Standard: das Feature davor), dazu `linear: {"richtung": "X", "anzahl": 5, "abstand": 12}` (auch Liste aus zwei Richtungen, `"-X"` oder negativer Abstand kehrt um) **oder** `kreis: {"achse": "Z", "anzahl": 6, "durch": [x, y, z], "winkel": 360}` (statt `winkel` auch `teilung`) | Wiederholt ganze Features. `anzahl` zählt das Original mit. Bei `winkel` 360 gleichmäßig verteilt |
| `spiegeln` **FC** | `von`, `ebene` (`XY`, `XZ`, `YZ`), `versatz` | Spiegelt ganze Features an der Ebene |
| `loft` **FC** | `schnitte: [{"ebene", "versatz", "profil"}, …]` (je genau eine Kontur), `abziehen`, `geregelt`, `geschlossen` | Ausformung zwischen Querschnitten, z. B. eckig auf rund |
| `zug` **FC** | `profil`, `pfad: {"ebene", "versatz", "linie": [Punkte und Bögen wie bei kontur], "geschlossen"}`, `ecken` (`scharf`/`rund`), `abziehen` | Profil entlang eines Pfads (Rohrbügel, Griff, Wulst, Dichtungsnut). Das Profil steht am Pfadanfang senkrecht zum Pfad, sein Nullpunkt liegt auf dem Pfad: u zeigt quer nach links, v in die Plus-Richtung der Pfadebene |
| `text` **FC** | `text`, `ebene`, `versatz`, `position: [u, v]`, `hoehe` (Schrifthöhe), `tiefe`, `art` (`gravur`/`erhaben`), `richtung`, `ausrichtung` (`mitte`/`links`/`rechts`), `winkel`, `schrift` (`arialbd`, `arial`, `consola` … oder Pfad zu einer TTF) | Schrift auf einer ebenen Fläche. Sie ist von der Seite lesbar, an der die Gravur beginnt bzw. zu der die Erhebung wächst (auf der Unterseite also `richtung: "+"` bei Gravur) |
| `import` **FC** | `datei` (STEP, BREP, IGES; relativ zum Plan), optional `drehen: [["Z", 90]]`, `verschieben: [x, y, z]` | Vorhandenes Teil als Ausgangskörper – nur als erstes Feature. Danach ändern alle übrigen Features das fremde Teil |
| `frei` | `beschreibung`, `freecad` (Code), `solidworks` (Code) | Programmcode für Sonderfälle, siehe freie-skripte.md |

Fase und Verrundung nehmen tangential anschließende Kanten automatisch mit (`"tangential": false` schaltet das ab). Wiederholen und spiegeln lassen sich block, tasche, bohrung, drehteil, drehnut, loft, zug und text – nicht Fasen, Radien oder Schalen (die gehören ans Ende und wählen ihre Kanten selbst).

## Rezepte

| Gesucht | So |
|---|---|
| Rippe / Versteifung | `block` mit Dreieck- oder Trapez-`kontur` auf der Ebene quer zur Rippe, `richtung: "beide"`, `hoehe` = Rippendicke; mehrere über `muster` |
| Muttertasche | `tasche` mit `{"mutter": "M4", "spiel": 0.2}`, `tiefe` = Mutterhöhe + 0,2, dazu `bohrung` mit `durchgang` |
| Schraubdom | `block` mit `kreis`, darin `bohrung`; vier Stück über `muster` oder `spiegeln` |
| Deckel mit Falz | zweites Teil, im selben Koordinatensystem gebaut; Falz um das Spiel kleiner (`"=B - 2*wand - 2*spiel"`); danach `modell.py zusammen` |
| Schnapphaken | `block` mit Haken-`kontur` auf der Ebene längs des Hakens, `richtung: "beide"` |
| Symmetrisches Teil | eine Hälfte der Features bauen, dann `spiegeln` |
| Teilkreis-Lochbild | `bohrung` mit `muster.kreis` (im Profil) – schneller als ein Feature-Muster |
| Kundenteil ändern | `import` als erstes Feature, dann Bohrungen, Taschen, Anbauten wie gewohnt |

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

Trifft eine Auswahl nichts, nennt die Fehlermeldung, was es stattdessen gibt („Kanten gibt es bei Z = 0, 4, 14.4“, „vorhandene Kreis-Ø: 4,5, 8,4“).

## Vorschaubild

Standard sind vier Ansichten (Iso, Vorne, Oben, Rechts). Von selbst kommen dazu: **Unten**, wenn ein Feature von unten arbeitet, und ein **Längsschnitt**, wenn das Teil ausgehöhlt ist. Sonst im Plan oder beim Aufruf festlegen:

```json
"ansichten": ["iso", "oben", "schnitt:Y=0", "schnitt:X=30:iso", "unten"]
```
Namen: `iso`, `vorne`, `oben`, `rechts`, `hinten`, `links`, `unten`, `iso_unten`, `iso_hinten`. Schnitt: `schnitt:X=0` blickt von +X auf die Ebene x = 0, `schnitt:Y=…` von vorne, `schnitt:Z=…` von oben; `:iso` zeigt ihn räumlich. Die Schnittfläche ist orange. Sacklöcher, Hinterschnitte und Wandstärken immer mit einem Schnitt prüfen.

## Prüfungen beim Bau

Jedes Feature wird gebaut und geprüft. Fehler stehen mit Feature-ID in der Ausgabe; nach einem Fehler baut der Lauf weiter (höchstens drei Fehler), spätere Meldungen sind dann als mögliche Folgefehler markiert.
- Feature ließ sich nicht bilden → wird entfernt, die Vorschau zeigt den letzten guten Stand
- Volumen ändert sich nicht in die erwartete Richtung (Tasche schneidet nichts = falsche Richtung/Lage)
- Körper zerfällt in mehrere Teile
- Schale wächst nach außen
- Soll-Hülle / Soll-Volumen weicht ab
- STL-Hülle weicht vom Modell ab (Exporteinheit)

Bei Fehlern entstehen keine Austauschdateien (nur die native Datei zur Diagnose).

**Merkmalsliste** (FreeCAD): Die Ausgabe nennt, was tatsächlich gebaut wurde – z. B.
`Bohrungen: 4× Ø3,4 ∥Z (Z 0…4) bei XY (-26; -16) (-26; 16) (26; -16) (26; 16)`, Außenzylinder, Senkungen (Kegel) und Radien. Gewindebohrungen erscheinen mit dem Kernloch-Ø. Diese Zeilen mit der Vorgabe vergleichen.

## Hinweise, die die Prüfung meldet

- Außenradius ≤ Wandstärke einer späteren Schale → innen entsteht eine entartete Kante. Radius > Wandstärke wählen.
- `fdm`: Gewinde unter M6, Bohrungen unter Ø2, Wandstärke unter 1,2 mm, Schrift unter 4 mm; nach dem Bau Überhänge steiler als 45° und zu kleine Auflagefläche.
- `fraesen`: Taschen mit scharfen Innenecken.

## Beispiele

Vollständige, getestete Pläne liegen in `beispiele/`: `halter.json` (Platte), `welle.json` (Drehteil), `gehaeuse.json` (Schale), `kabelclip.json` (Parameter, Spiegeln, Muster, Muttertasche, Gravur), `adapter.json` (Loft eckig auf rund, Lochbild), `buegel.json` (Zug entlang Pfad), `pruefblock.json` (Schräge, Bohrspitze, modelliertes Gewinde, geneigte Ebene, Kreismuster). Bei Bedarf **eines** davon lesen, nicht alle.

```json
{"name": "Welle", "werkstoff": "C45", "fertigung": "drehen",
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

```json
{"name": "Kabelclip", "werkstoff": "PETG", "fertigung": "fdm",
 "parameter": {"L": 60, "B": 24, "t": 4, "rand": 8, "dk": 8, "wand": 2.4},
 "features": [
  {"id": "Platte", "typ": "block", "profil": [{"rechteck": ["=L", "=B"], "mitte": [0, 0], "r": 3}], "hoehe": "=t"},
  {"id": "Schraube", "typ": "bohrung", "versatz": "=t", "mitte": ["=-L/2+rand", 0], "durchgang": "M4", "durch": true,
   "senkung": {"d": 8.4, "winkel": 90}},
  {"id": "Schraube_rechts", "typ": "spiegeln", "von": "Schraube", "ebene": "YZ"},
  {"id": "Mutter", "typ": "tasche", "richtung": "+", "profil": [{"mutter": "M4", "spiel": 0.2, "mitte": [0, 0]}], "tiefe": 2},
  {"id": "Steg", "typ": "block", "ebene": "XZ", "richtung": "beide", "hoehe": 3,
   "profil": [{"kontur": [[-14, "=t"], [-8, "=t"], [-8, "=t+dk+wand"], [-14, "=t+dk+wand"]]}]},
  {"id": "Stege", "typ": "muster", "von": "Steg", "linear": {"richtung": "X", "anzahl": 3, "abstand": 11}},
  {"id": "Schrift", "typ": "text", "text": "M4", "versatz": "=t", "position": [0, -8], "hoehe": 5, "tiefe": 0.6}],
 "soll": {"huelle": ["=-L/2", "=-B/2", 0, "=L/2", "=B/2", "=t+dk+wand"]}}
```
