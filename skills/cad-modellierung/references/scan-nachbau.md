# Scan, STL oder fremdes Teil als Vorlage

Für Aufträge wie „Scan zu STEP“, „STL bearbeitbar machen“, „Ersatzteil nach altem Teil“. Die Werkzeuge messen und vergleichen; sie ersetzen das Hinsehen nicht.

## 1. Erst prüfen, dann den Weg wählen

```
python -I scripts/modell.py netz pruefen <netz> --bild pruefung.png
```
Liefert Größe, Dreiecke, ob das Netz dicht ist, Splitter, Auflösung, Wandstärke, größte ebene Fläche. Bild ansehen und die Form **in Worten beschreiben** („Gabel mit zwei Laschen und Endklötzen“). Stimmt die Beschreibung nicht, wird alles Weitere falsch – bei Zweifel dem Nutzer Bild und Beschreibung zeigen, bevor gebaut wird.

| Lage | Weg | Aufwand |
|---|---|---|
| Kunde braucht nur einen Körper zum Bohren, Schneiden, Anbauen; oder die Form ist Freiform | **A – Netz als Volumenkörper** | Minuten |
| Technisches Teil aus Ebenen, Bohrungen, Radien, Taschen (Halter, Gehäuse, Flansch, Clip) | **B – Nachbau mit dem Bauplan** | 1–3 Bauschleifen |
| Freiform mit Anspruch auf glatte, änderbare Flächen | nicht zusagen: A anbieten oder nur die Funktionsstellen (Anschraubpunkte, Passflächen) nach B auf einem Körper aus A | – |

Dem Nutzer den Weg und den Umfang nennen: was wird nachgebaut, was bewusst weggelassen (kleine Rippen, Prägungen, Scanrauschen).

## 2. Weg A – Netz als Volumenkörper

```
python -I scripts/modell.py netz koerper <netz> <aus.step> [--facetten 20000] [--stl aus.stl]
```
Entfernt Splitter, schließt Löcher, vereinfacht und schreibt einen STEP-Körper aus Dreiecksflächen. Endet mit „OK … gültig: ja“ oder nennt, was offen bleibt. Mehr Facetten = genauer, aber große STEP-Datei (20 000 Dreiecke ≈ 20 MB). Der Körper lässt sich als erstes Feature `import` in einen Bauplan laden und dort bohren, kürzen oder ergänzen.

## 3. Weg B – Nachbau

1. **Ausrichten**, wenn das Teil schief liegt: `netz ausrichten <netz> <aus.stl> --flaeche-unten` (größte ebene Fläche auf Z = 0) oder `--pca`. Danach mit dem ausgerichteten Netz weiterarbeiten.
2. **Maße holen**: `netz schnitte <netz> --achse Z --bei 2,8 --bild schnitte.png --json schnitte.json`. Die Ausgabe nennt Kreise (Ø, Mitte), Rechtecke (auch mit Eckenradius), Langlöcher und sonst vereinfachte Konturen. Schnitt X liegt in der Bauplan-Ebene YZ, Y in XZ, Z in XY; die `punkte` aus dem JSON passen als `kontur`. Zwei bis drei Schnitte je Hauptrichtung reichen meist. Scanmaße auf sinnvolle Nennmaße runden (6,58 → Bohrung 6,6; 39,93 → 40) und das als Annahme nennen.
3. **Bauen** mit dem Bauplan im Koordinatensystem des Netzes. Kleine Features aus Grundformen mit gemessenen Maßen bauen, nie aus Scan-Scheiben zusammensetzen.
4. **Vergleichen nach jeder Bauschleife**:
   ```
   python -I scripts/modell.py netz vergleich <netz> <modell.stl> --bild vergleich.png --grenze 0.5
   ```
   Das Bild zeigt Vorlage und Modell aus denselben vier Blickwinkeln und die Abweichung in Farbe. **Erst das Bild beurteilen** (Form, Proportionen, fehlende Details), dann die Zahlen. Die Ausgabe nennt die Stellen mit der größten Abweichung: „Vorlage → Modell“ zeigt, was im Modell fehlt, „Modell → Vorlage“, was zu viel ist. Ein guter Median allein ist keine Freigabe.
5. **Zwischenstopp**: Nach dem ersten großen Teilstück (Grundkörper) dem Nutzer das Vergleichsbild zeigen, erst dann die Details bauen.

## Regeln aus der Praxis
- Aufwand ehrlich schätzen; bei Freiformteilen doppelt.
- Arbeitsdateien (ausgerichtetes Netz, Schnitte, Plan, Vergleichsbilder) im Auftragsordner ablegen, damit eine neue Sitzung weitermachen kann.
- Netze über 1 Mio. Dreiecke: `pruefen` und `schnitte` dauern 15–30 s; für `vergleich` reicht das mit `koerper --stl` vereinfachte Netz.
