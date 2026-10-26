# 07 Oberflächenbeschaffenheit (ISO 21920-1:2021, früher ISO 1302:2002)

## Grundsymbol

```
        Text (Kenngröße, Wert, Verfahren …)
    ____________
   \    /           ✓  Grundsymbol: jedes Verfahren zulässig
    \  /            mit Querbalken (geschlossenes Dreieck): materialabtrennend gefordert
     \/             mit Kreis im Winkel: materialabtrennend unzulässig (Oberfläche bleibt wie geliefert/urgeformt)
```

- Kurzer Schenkel ≈ 1,4 h, langer Schenkel ≈ 2,8 h bis 3 h (h = Schrifthöhe), Schenkelwinkel 60°.
- Symbol berührt die Fläche von außerhalb des Materials (Spitze auf Kontur, Maßhilfslinie oder Hinweislinie mit Pfeil).
- **Lesbar von unten oder rechts** (wie Maßzahlen). Ist das nicht möglich: Hinweislinie mit Pfeil verwenden.
- Rundum-Kreis am Knick: Anforderung gilt für alle Flächen der dargestellten Kontur.

## Angaben am Symbol (Positionen)

| Position | Inhalt |
|---|---|
| a | Kenngröße mit Wert, z. B. `Ra 1,6` oder `Rz 6,3` (ggf. Filter/Übertragungscharakteristik und Auswertelänge) |
| b | zweite Anforderung (z. B. `Rz 10` zusätzlich) |
| c | Fertigungsverfahren, Behandlung, Beschichtung („geschliffen“, „verchromt“) |
| d | Rillenrichtung: `=` parallel, `⟂` senkrecht, `X` gekreuzt, `M` vielfach, `C` kreisförmig, `R` radial, `P` nicht-rillig/punktförmig |
| e | Bearbeitungszugabe in mm |

Grenzwert-Konvention: Einzelner Wert = oberer Grenzwert. Unterer Grenzwert mit `L`, oberer explizit `U`: `U Ra 3,2` / `L Ra 0,8`.
Annahmeregel: Normstandard (16 %-Regel in ISO 1302/ISO 4288) oder `max` explizit („Ra max 0,8“). **In ISO 21920 haben sich Standards (Auswertelänge, Annahmeregel, Filter) gegenüber ISO 1302 geändert** – auf der Zeichnung die angewendete Norm nennen und im Zweifel Annahmeregel ausdrücklich angeben.

## Sammelangaben

Im Schriftfeld-Bereich: Hauptsymbol mit Wert + in Klammern Grundsymbol (oder die abweichenden Werte):
```
✓ Ra 3,2 ( ✓ )        → alle Flächen Ra 3,2 außer den einzeln gekennzeichneten
✓ Ra 3,2 ( ✓ Ra 0,8   ✓ Ra 1,6 )
```
Vereinfachte Angabe mit Buchstaben (`✓ z = ✓ Ra 0,8`) bei Platzmangel.

## Typische Werte

| Ra (µm) | Rz ca. (µm) | Erreichbar mit | Anwendung |
|---|---|---|---|
| 25 / 12,5 | 100 / 50 | Sägen, Brennschneiden, Schruppen | Nicht-Funktionsflächen |
| 6,3 | 25 | Schruppfräsen, Drehen grob | Freiflächen |
| 3,2 | 16 | Fräsen, Drehen | allgemeine Bearbeitung, Anlageflächen unkritisch |
| 1,6 | 6,3–10 | Schlichtfräsen, Feindrehen, Reiben | Passflächen IT7, Dichtflächen statisch |
| 0,8 | 4 | Feindrehen, Schleifen | Lagersitze, Passungen IT6, O-Ring-Nuten (Flanken) |
| 0,4 | 2 | Schleifen, Honen | Gleitflächen, dynamische Dichtungen |
| 0,2–0,1 | 1–0,5 | Feinschleifen, Läppen, Polieren | Messflächen, Präzisionsgleitflächen |

Faustregel: Rz ≤ ca. 1/3 bis 1/4 der Maßtoleranz (IT) an Passflächen; Ra ≈ Rz/4…7 (nur grobe Umrechnung, keine Norm).

Radial-Wellendichtringe (DIN 3760 / ISO 6194): Lauffläche Ra 0,2–0,8, Rz 1–5, drallfrei (Einstechschleifen) – Herstellerangaben.
