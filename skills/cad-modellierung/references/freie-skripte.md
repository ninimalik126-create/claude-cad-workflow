# Freie Skripte und frei-Features

Der Bauplan deckt prismatische Teile, Drehteile, Gehäuse, Bohrbilder, Fasen, Radien und – in FreeCAD – auch Muster, Spiegeln, Loft, Zug, Text, geneigte Ebenen und den Import fremder Teile ab. Code gibt es nur für den Rest, und dann **so wenig wie nötig**: Plan-Features sind getestet, liefern klare Fehlermeldungen und kosten weniger Kontingent.

## Welcher Weg? (vor dem Bau entscheiden und dem Nutzer in einem Satz sagen)

| Lage | Weg |
|---|---|
| Alles mit den Features aus bauplan.md abbildbar | **Bauplan** |
| 1–2 Operationen fehlen (Helix/Feder, modelliertes Außengewinde, Loft mit Leitkurve, Muster entlang Kurve, Text auf gewölbter Fläche, Verrundung mit veränderlichem Radius) | **Bauplan + `frei`-Feature** an der passenden Stelle |
| Geometrie wird *berechnet* (Zahnrad-Evolvente, Kurvenscheibe, Kühlkörper nach Formel) | zuerst prüfen, ob `parameter` und Ausdrücke reichen; die berechnete Kontur sonst als Punktliste in eine `kontur` schreiben. Nur wenn das nicht geht: **freies Skript** (`--skript`), das `feature()` für die normalen Schritte nutzt |
| Organische Freiform (Griffmulden nach Hand, Karosserie, Figur) | nicht automatisch: Grundkörper bauen oder einen Scan als Volumenkörper wandeln (scan-nachbau.md) – offen sagen |

## Aufruf

```
python -I modell.py bauen teil.json --cad freecad --skript teil_freecad.py --formate step,stl
```
`teil.json` enthält dann `name`, `werkstoff`, `parameter`, `soll` (Features optional, sie werden vor dem Skript gebaut). Für beide Programme je ein Skript schreiben, wenn beide gebraucht werden.

Danach laufen dieselben Prüfungen (Soll-Hülle, gültige Geometrie, ein Körper), Merkmalsliste, Exporte und die Vorschau wie beim Plan.

## Namensraum in FreeCAD (`freecad`-Code / Skript)

| Name | Inhalt |
|---|---|
| `feature(dict)` | baut ein Plan-Feature mit allen Prüfungen, gibt das FreeCAD-Objekt zurück |
| `P` | Parameter des Plans als Wörterbuch, z. B. `P["L"]` |
| `bau.skizze(ebene, versatz, schleifen, name)` | Skizze in Planebene; `schleifen` aus `bp.form_zu_schleifen({...})` oder `[[("linie", p, q), ("bogen", p, mitte, q), ("kreis", c, r)]]` |
| `bau.skizze_rahmen(ursprung, u, v, schleifen, name)` | Skizze in beliebiger Lage (Achsen u, v als Vektoren) |
| `bau.kanten(auswahl)` / `bau.flaechen(auswahl)` | Auswahl wie im Plan → `["Edge3", …]` |
| `bau.objekte["ID"]` | FreeCAD-Objekt eines schon gebauten Plan-Features |
| `body`, `doc`, `App`, `Part`, `Sketcher`, `bp`, `math`, `V` | PartDesign-Körper, Dokument, Module, Bauplan-Modul, Vektor-Hilfe |

Regeln:
- Neue Features mit `body.newObject("PartDesign::…", "Name")` anlegen, damit sie im Baum stehen (AdditiveHelix, SubtractiveHelix, AdditivePipe mit Leitkurve …).
- `body.Tip` **vor** `newObject` merken, wenn ein Feature eine Basis braucht – danach ist das neue Feature die Spitze.
- Muster und Spiegelungen (`PartDesign::LinearPattern`, `PolarPattern`, `Mirrored`) werden nicht von selbst zur Spitze: `body.Tip = o` setzen. In FreeCAD 1.1 beim linearen Muster `Mode = "Extent"` mit `Length` verwenden; `"Spacing"` wirkt in der zweiten Richtung nicht.
- Am Ende `doc.recompute()`.
- Beidseitige Extrusion: `o.SideType = "Symmetric"` (nicht `Midplane`, das ist ab 1.1 veraltet).
- `TaperAngle` an Pad und Pocket: positiver Winkel weitet auf.
- Bezugsachse oder -ebene an freier Stelle: `PartDesign::Line` / `PartDesign::Plane` anlegen und `Placement` setzen (Richtung bzw. Normale ist die lokale Z-Achse).

Beispiel Helix (Druckfeder als Zusatz zu Plan-Features):
```python
sk = bau.skizze("XZ", 0, [[("kreis", (P["D"] / 2, 0), P["draht"] / 2)]], "Draht")
h = body.newObject("PartDesign::AdditiveHelix", "Feder")
h.Profile = sk
h.ReferenceAxis = (sk, ["V_Axis"])
h.Mode = "pitch-height-angle"
h.Pitch = P["steigung"]
h.Height = P["hoehe"]
doc.recompute()
ergebnis = h
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

Freier Code ist ungetestet: Ausgabe lesen (Fehler 0, Soll-Hülle erfüllt, Merkmalsliste), Vorschau ansehen. Bei Freiformflächen ist die FreeCAD-Hülle exakt (optimalBoundingBox), die Soll-Hülle also auch dort verlässlich. Das alte Loft-Beispiel `beispiele/griff_freecad.py` zeigt den Aufbau eines freien Skripts; ein Loft selbst gehört heute in den Plan.
