# 03 Geometrische Tolerierung (ISO 1101:2017)

## Die Eigenschaften

| Gruppe | Eigenschaft | Symbol | Bezug | Zonenform typisch | Erlaubt Ⓜ/Ⓛ |
|---|---|---|---|---|---|
| Form | Geradheit | ⏤ | nein | 2 Linien t / Zylinder ⌀t (Achse) | nur bei abgeleiteter Achse |
| Form | Ebenheit | ⏥ | nein | 2 Ebenen t | nur bei abgeleiteter Mittelebene |
| Form | Rundheit | ○ | nein | 2 konzentrische Kreise t (je Querschnitt) | nein |
| Form | Zylinderform | ⌭ | nein | 2 koaxiale Zylinder t | nein |
| Form/Richtung/Ort | Linienprofil | ⌒ | optional | 2 Linien, Kreise ⌀t entlang Soll-Profil | nein |
| Form/Richtung/Ort | Flächenprofil | ⌓ | optional | 2 Flächen, Kugeln ⌀t entlang Soll-Fläche | nein |
| Richtung | Parallelität | ∥ | ja | 2 Ebenen / Zylinder ⌀t | ja (bei abgeleiteten Elementen) |
| Richtung | Rechtwinkligkeit | ⟂ | ja | 2 Ebenen / Zylinder ⌀t | ja |
| Richtung | Neigung | ∠ | ja | 2 Ebenen im TED-Winkel / ⌀t | ja |
| Ort | Position | ⌖ | meist ja (ohne Bezug nur bei Mustern zueinander) | ⌀t, 2 Ebenen t, S⌀t | ja |
| Ort | Koaxialität / Konzentrizität | ◎ | ja | Zylinder ⌀t / Kreis ⌀t (ACS) | ja |
| Ort | Symmetrie | ⌯ | ja | 2 Ebenen t um Bezugsmittelebene | ja |
| Lauf | Lauf (Rund-/Planlauf) | ↗ | ja (Achse) | je Messkreis 2 Kreise t | nein |
| Lauf | Gesamtlauf | ⌰ | ja (Achse) | 2 Zylinder / 2 Ebenen t | nein |

Profil ohne Bezug = Formtoleranz; mit Bezug = Richtung oder Ort (je nach Bezug und TED).

**Hierarchie:** Ort begrenzt Richtung und Form; Richtung begrenzt Form; Lauf begrenzt Rundheit/Koaxialität (Rundlauf) bzw. Ebenheit/Rechtwinkligkeit (Planlauf). Eine zusätzliche Formtoleranz ist nur sinnvoll, wenn sie **kleiner** ist als die übergeordnete (z. B. `⌖ 0,2 A B` und `⏥ 0,05`).

## Aufbau des Toleranzrahmens

```
| Symbol | Zone & Wert & Modifikatoren | Bezug 1 | Bezug 2 | Bezug 3 |
```

Zelle 2 (Toleranzzonen-Teil), in dieser Reihenfolge:
1. Zonenform: `⌀` (zylindrisch/kreisförmig), `S⌀` (kugelförmig), ohne Zeichen = 2 parallele Linien/Ebenen in Pfeilrichtung.
2. Toleranzwert `0,05`, ggf. variabel `0,1–0,2` (Variation entlang Element).
3. Kombinierte Zonen: `CZ` (gemeinsame Zone), `SZ` (getrennte Zonen, explizit), `CZR` (kombinierte Zone nur rotatorisch) – ISO 1101:2017/ISO 5458.
4. Versatz: `UZ+0,2` (Zone versetzt), `OZ` (unbestimmter Versatz), `VA` (unbestimmter Winkel).
5. Filter (z. B. `G0,8` Gauß-Filter) – selten.
6. Assoziation des tolerierten Elements: `Ⓒ` Tschebyscheff, `Ⓖ` Gauß, `Ⓝ` kleinstes umschriebenes, `Ⓧ` größtes einbeschriebenes, `Ⓣ` Tangentenelement.
7. Parameter: `P` (Spitze-Tal, Standard), `V` (Tal), `T` (Spitze) – Formabweichung relativ zum Referenzelement.
8. Abgeleitetes Element: `Ⓐ` (abgeleitet – ersetzt das alte Pfeil-in-Maßlinie-Konzept, wenn das Bild es nicht eindeutig macht).
9. Projizierte Zone: `Ⓟ 20` oder `Ⓟ` mit Länge in der Zeichnung.
10. Materialbedingung: `Ⓜ`, `Ⓛ`, ggf. `Ⓡ` (Reziprozität).
11. Freier Zustand `Ⓕ` (nicht formstabile Teile, ISO 10579).

Bezugszellen: Großbuchstabe, ggf. mit Modifikator (`AⓂ`, `A [PL]`, `A [ACS]`, `A-B` gemeinsamer Bezug, `[CF]` Kontaktelement, `>< ` nur Lagebindung). Siehe 04-bezuege.md.

**Zusatzangaben am Rahmen:**
- **Oberhalb des Rahmens:** Anzahl/Gültigkeit: `6×`, `2× ⌀10 H7`, `UF` (vereintes Element), Bereichsangaben „J↔K“. Das Rundum-Symbol (Kreis) sitzt dagegen am Knick der Hinweislinie, nicht über dem Rahmen.
- **Unterhalb/rechts:** Elementbezogene Angaben wie `ACS`, `LE` (Linienelement), `NC` (nicht konvex), Richtungs-/Schnittebenen-Indikatoren rechts am Rahmen: Schnittebene `| ∥ | B |`-Kästchen, Richtungselement, Kollektionsebene, Orientierungsebene (ISO 1101:2017 Kap. 13–14).

**Mehrere Anforderungen an ein Element:** Rahmen übereinander stapeln (z. B. Position zum Bezugssystem + Position der Bohrungen zueinander: „Composite“ in ISO als zwei getrennte Rahmen, der untere mit weniger Bezügen und kleinerer Toleranz; Bedeutung ISO 5458).

## Bezugspfeil (Hinweislinie) am tolerierten Element

| Pfeilspitze | Gilt für |
|---|---|
| Auf Kontur oder Maßhilfslinie, **deutlich versetzt** zur Maßlinie | Integralelement (Fläche/Linie) |
| **In Verlängerung der Maßlinie** eines Maßelements | Abgeleitetes Element (Achse, Mittelebene) |
| Auf Hinweislinie mit Punkt in der Fläche | Fläche (wenn Kontur nicht günstig) |
| Mit Kreis am Knick (Rundum-Symbol) | Alle Flächen des Profils in der Ansicht |
| Doppelkreis (rundherum, ganz) | Alle Flächen des Werkstücks (ISO 1101:2017 „all over“) |

Pfeilrichtung = Richtung der Zonenbreite (ohne ⌀-Zeichen). Bei ⌀-Zonen ist die Pfeilrichtung ohne Bedeutung.

## Häufige Anwendungen (Muster, direkt übernehmbar)

| Funktion | Spezifikation |
|---|---|
| Anlagefläche plan | `|⏥|0,05|` |
| Zweite Anlagefläche rechtwinklig zur ersten | `|⟂|0,05|A|` |
| Lagersitz Welle läuft rund zu Lagerstellen | `|↗|0,02|A-B|` an Sitz; A, B an Lagersitzen (gemeinsamer Bezug) |
| Planschulter Lageranlage | `|↗|0,02|A-B|` Pfeil auf Schulter in Achsrichtung (Planlauf) oder `|⌰|0,02|A-B|` für gesamte Fläche |
| Bohrbild für Schrauben (Durchgangsbohrungen) | `4× ⌀6,6` + `|⌖|⌀0,2 Ⓜ|A|B|C|`, Lochabstände als TED |
| Passstiftbohrungen | `2× ⌀6 H7` + `|⌖|⌀0,02|A|B|C|` (ohne Ⓜ wenn Stift Lage bestimmt) |
| Gewindebohrungen mit Durchsteckteil | `|⌖|⌀0,2 Ⓟ 10|A|B|C|` (projizierte Zone = Klemmlänge) |
| Nut mittig | `|⌯|0,05|A|` oder besser `|⌖|0,05|A|` mit TED 0 |
| Zentrierbund koaxial | `|⌖|⌀0,02|A|` (Koaxialität ist zulässig, ISO empfiehlt zunehmend Position) |
| Freiformkontur | Flächenprofil `|⌓|0,1|A|B|C|` mit TED/CAD-Modell |
| Allseitige Kontur mit Toleranz | Rundum-Symbol + `|⌒|0,2|A|B|` |
| Lage eines Elements zu Kante statt ± | `|⌓|0,2|A|B|C|` oder `|⌖|0,2|A|B|` mit TED |
| Zylindrische Passung mit Fügesicherheit | `⌀20 H7 Ⓔ` oder `⌀20 H7` + `|⌭|0,005|` |
| Welle in Bohrung (Funktionslehre) | `|⟂|⌀0,02 Ⓜ|A|` an Achse |

## Typische Fehler (immer prüfen)

1. Formtoleranz mit Bezugsbuchstaben (Form hat nie Bezug).
2. Richtungs-/Orts-/Lauftoleranz ohne Bezug.
3. Lauftoleranz bezogen auf eine Ebene statt Achse.
4. Positionstoleranz ohne TED für die Sollage (bzw. Sollmaß mit ±-Toleranz zusätzlich → Doppeltolerierung).
5. ⌀ vor Zonenwert vergessen bei Position von Bohrungen (ergibt zwei parallele Ebenen statt Zylinder) – oder ⌀ gesetzt, wo eine Breite gemeint ist.
6. Ⓜ an Flächen (Integralelemente ohne Maß) – unzulässig.
7. Untergeordnete Toleranz größer als übergeordnete (z. B. Ebenheit 0,1 bei Parallelität 0,05) → wirkungslos.
8. Bezugsbuchstabe am Rahmen, der nirgends als Bezug definiert ist.
9. Konzentrizität/Koaxialität, wo Lauf gemeint ist (Lauf ist billiger zu prüfen und erfasst auch Form).
10. Symmetrie, wo Position verständlicher wäre.
11. Toleranzwert enger als die Maßtoleranz des Elements bei Richtung ist sinnvoll; Ortstoleranz enger als Prozessfähigkeit ist teuer – Prozessfähigkeit prüfen.
12. Unklare Pfeilposition (halb in Maßlinie) → abgeleitet vs. integral mehrdeutig.

## Richtwerte erreichbarer Geometrietoleranzen (Serienfertigung, normale Bedingungen)

| Verfahren | Ebenheit/100 mm | Rundheit | Rechtwinkligkeit/100 mm | Position Bohrung (⌀-Zone) | Rund-/Planlauf |
|---|---|---|---|---|---|
| Fräsen (CNC) | 0,02–0,05 | – | 0,02–0,05 | 0,05–0,1 | – |
| Drehen (CNC) | 0,01–0,03 (Plan) | 0,005–0,02 | – | – | 0,01–0,03 (eine Aufspannung) |
| Schleifen | 0,002–0,01 | 0,001–0,005 | 0,005–0,01 | – | 0,002–0,01 |
| Laserschneiden | – | – | – | 0,1–0,2 | – |
| Kanten (Blech) | 0,5/100 (Biegeteil) | – | ±0,5°–1° | 0,2–0,5 über Biegung | – |
| Sandguss roh | 1–2 | – | – | 1–2 | – |

Richtwerte – mit dem Fertiger abstimmen. Toleranzen zwei Aufspannungen übergreifend sind deutlich teurer.
