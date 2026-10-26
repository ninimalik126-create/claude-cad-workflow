# Freie Skripte und frei-Features

Der Bauplan deckt prismatische Teile, Drehteile, Gehäuse, Bohrbilder, Fasen und Radien ab. Für alles andere gibt es Code – aber **nur so viel wie nötig**, weil Plan-Features in beiden Programmen getestet sind und weniger Kontingent kosten.

## Welcher Weg? (vor dem Bau entscheiden und dem Nutzer in einem Satz sagen)

| Lage | Weg |
|---|---|
| Alles mit block, tasche, drehteil, drehnut, bohrung, fase, verrundung, schale abbildbar | **Bauplan** |
| 1–2 Operationen fehlen (Loft, Sweep/Rohr, Helix, Gravur/Text, modelliertes Gewinde, geneigte Rippe, Muster entlang Kurve) | **Bauplan + `frei`-Feature** an der passenden Stelle |
| Geometrie wird *berechnet* (Zahnrad-Evolvente, Kühlkörper mit n Rippen, Kurvenscheibe, Parameterfamilie) oder mehr als etwa ein Drittel ist nicht im Plan abbildbar | **Freies Skript** (`--skript`), das `feature()` für die normalen Schritte nutzt |
| Organische Freiform (Griffmulden nach Hand, Karosserie, Figur) | nicht automatisch: Grundkörper bauen, Rest von Hand – offen sagen |

Berechnete Konturen gehören meist trotzdem in `feature()`: z. B. Evolvente als Punktliste in eine `kontur` → `block`. Dann bleibt das Teil in beiden Programmen gleich.

## Aufruf

```
python -I modell.py bauen teil.json --cad freecad --skript teil_freecad.py --formate step,stl
```
`teil.json` enthält dann nur `name`, `werkstoff`, `soll` (Features optional, sie werden vor dem Skript gebaut). Für beide Programme je ein Skript schreiben, wenn beide gebraucht werden.

Danach laufen dieselben Prüfungen (Soll-Hülle, gültige Geometrie, ein Körper), Exporte und die Vorschau wie beim Plan.

## Namensraum in FreeCAD (`freecad`-Code / Skript)

| Name | Inhalt |
|---|---|
| `feature(dict)` | baut ein Plan-Feature mit allen Prüfungen, gibt das FreeCAD-Objekt zurück |
| `bau.skizze(ebene, versatz, schleifen, name)` | Skizze in Planebene; `schleifen` aus `bp.form_zu_schleifen({...})` oder `[[("linie", p, q), ("bogen", p, mitte, q), ("kreis", c, r)]]` |
| `bau.kanten(auswahl)` / `bau.flaechen(auswahl)` | Auswahl wie im Plan → `["Edge3", …]` |
| `body`, `doc`, `App`, `Part`, `Sketcher`, `bp`, `math`, `V` | PartDesign-Körper, Dokument, Module, Bauplan-Modul, Vektor-Hilfe |

Regeln:
- Neue Features mit `body.newObject("PartDesign::…", "Name")` anlegen, damit sie im Baum stehen (AdditiveLoft, AdditivePipe, AdditiveHelix, SubtractiveLoft …).
- `body.Tip` **vor** `newObject` merken, wenn ein Feature eine Basis braucht – danach ist das neue Feature die Spitze.
- Am Ende `doc.recompute()`.
- Beidseitige Extrusion: `o.SideType = "Symmetric"` (nicht `Midplane`, das ist ab 1.1 veraltet).

Beispiel Loft (Knopf, getestet):
```python
feature({"id": "Fuss", "typ": "block", "ebene": "XY", "profil": [{"kreis": 30, "mitte": [0, 0]}], "hoehe": 4})
sk1 = bau.skizze("XY", 4, [[("kreis", (0, 0), 15)]], "Loft_unten")
sk2 = bau.skizze("XY", 32, bp.form_zu_schleifen({"vieleck": 8, "d": 20, "mitte": [0, 0]}), "Loft_oben")
loft = body.newObject("PartDesign::AdditiveLoft", "Knopf")
loft.Profile = sk1
loft.Sections = [sk2]
loft.Ruled = True
doc.recompute()
feature({"id": "Gewinde", "typ": "bohrung", "ebene": "XY", "richtung": "+", "mitte": [0, 0], "gewinde": "M6", "tiefe": 12})
```

## Namensraum in SolidWorks (`solidworks`-Code / Skript)

| Name | Inhalt |
|---|---|
| `feature(dict)` | wie oben |
| `bau.skizze(ebene, schleifen, achse=None)` | Skizze auf der Standardebene (ohne Versatz; Versatz über Start-Offset oder Referenzebene) |
| `bau.waehle_kanten(auswahl)` / `bau.waehle_flaechen(auswahl)` | wählt in SolidWorks aus, gibt Anzahl zurück |
| `sw`, `part`, `fm`, `sm`, `bp`, `math`, `M`, `liste`, `m` | Anwendung, Teil, FeatureManager, SketchManager, Hilfen; `m(mm)` rechnet in Meter |

Regeln:
- **Jeder COM-Zugriff mit Klammern**: `part.Extension().CustomPropertyManager("")`, `fm.FeatureExtrusion3(...)`. Eigenschaften setzen per Zuweisung: `feat.Name = "Rippe"`.
- **Längen in Metern** (`m(12)` = 0,012), Winkel in Radiant.
- Vor jeder Auswahl `part.ClearSelection2(True)`.
- Signaturen nicht raten: `python -I modell.py api InsertProtrusionBlend2` liest sie aus der SolidWorks-Typbibliothek.
- Letztes Feature: `part.FeatureByPositionReverse(0)`.

## Prüfen

Freier Code ist ungetestet: Bericht lesen (Fehler 0, Soll-Hülle erfüllt), Vorschau ansehen. Bei Freiformflächen ist die FreeCAD-Hülle exakt (optimalBoundingBox), die Soll-Hülle also auch dort verlässlich.
