# 08 Allgemeintoleranzen

Allgemeintoleranzen gelten für alle Merkmale ohne Einzeltoleranz. Sie sind Pflicht; ohne sie ist die Zeichnung unvollständig (ISO 8015: Prinzip der allgemeinen Spezifikation).

## ISO 22081:2021 (aktuell, empfohlen für neue Zeichnungen)

- **Allgemeine Geometriespezifikation:** Flächenprofiltoleranz ⌓ mit Wert und Bezugssystem, gilt für alle integralen Elemente, deren Lage nicht anderweitig spezifiziert ist. Nominalgeometrie durch TED bzw. CAD-Modell. Angabe im oder nahe Schriftfeld, sinngemäß:
  `Allgemeine Geometrietoleranz ISO 22081 – |⌓|1|A|B|C|`
- **Allgemeine Maßspezifikation:** symmetrische ±-Toleranz für Maßelemente ohne Einzeltoleranz (z. B. `ISO 22081 ±0,2`) oder Verweis auf eine Tabelle/Norm.
- Voraussetzung: vollständiges Bezugssystem auf der Zeichnung; alle Lageangaben ohne Toleranz werden dann als TED gelesen.
- Genaue Schreibweise im Normtext prüfen und firmenweit einheitlich festlegen.

## ISO 2768-1 (Längen- und Winkelmaße, weiterhin gültig)

**Längenmaße (Grenzabmaße ± in mm)**

| Klasse | 0,5–3 | >3–6 | >6–30 | >30–120 | >120–400 | >400–1000 | >1000–2000 | >2000–4000 |
|---|---|---|---|---|---|---|---|---|
| f (fein) | 0,05 | 0,05 | 0,1 | 0,15 | 0,2 | 0,3 | 0,5 | – |
| m (mittel) | 0,1 | 0,1 | 0,2 | 0,3 | 0,5 | 0,8 | 1,2 | 2 |
| c (grob) | 0,2 | 0,3 | 0,5 | 0,8 | 1,2 | 2 | 3 | 4 |
| v (sehr grob) | – | 0,5 | 1 | 1,5 | 2,5 | 4 | 6 | 8 |

**Rundungshalbmesser und Fasenhöhen (±)**

| Klasse | 0,5–3 | >3–6 | >6 |
|---|---|---|---|
| f, m | 0,2 | 0,5 | 1 |
| c, v | 0,4 | 1 | 2 |

**Winkelmaße (± nach Länge des kürzeren Schenkels in mm)**

| Klasse | ≤10 | >10–50 | >50–120 | >120–400 | >400 |
|---|---|---|---|---|---|
| f, m | 1° | 0°30′ | 0°20′ | 0°10′ | 0°5′ |
| c | 1°30′ | 1° | 0°30′ | 0°15′ | 0°10′ |
| v | 3° | 2° | 1° | 0°30′ | 0°20′ |

## ISO 2768-2 (Form und Lage, Klassen H, K, L – zurückgezogen)

Zurückgezogen (ersetzt durch ISO 22081), in Bestandszeichnungen und bei Kunden weit verbreitet („ISO 2768-mK“). Wenn verwendet: Ausgabestand nennen und beachten, dass sie mit dem Unabhängigkeitsprinzip nach ISO 8015 kombiniert unklare Ergebnisse liefern kann. Werte für H/K/L aus der Norm übernehmen, nicht aus dem Gedächtnis.

## Welche Klasse?

| Fertigung | ISO 2768-1 |
|---|---|
| CNC-Zerspanung Präzision | f |
| Zerspanung allgemein, Laser-Feinschnitt | m |
| Laser/Plasma, Kanten, Schweißbaugruppen bearbeitet | m–c |
| Brennschnitt, Rohbau | c–v |

## Andere Verfahren

| Verfahren | Norm | Angabe |
|---|---|---|
| Schweißkonstruktionen | **ISO 13920** | Längen/Winkel Klassen A–D, Gerad-/Eben-/Parallelität Klassen E–H, z. B. `ISO 13920-BF` |
| Gussteile | **ISO 8062-3** | Gussmaßtoleranzgrad DCTG und Bearbeitungszugabegrad RMAG, z. B. `ISO 8062-3 – DCTG 9 – RMAG H` |
| Kunststoff-Formteile | **DIN 16742** | Toleranzgrad TG nach Werkstoff/Verfahren |
| Gesenkschmiedeteile | EN 10243-1 | Toleranzklasse F / E |
| Thermisch geschnittene Teile | ISO 9013 | Bereich für Rechtwinkligkeit u, Rauheit Rz5, Maßtoleranzklasse |
| Blech-Biegeteile | meist Firmenstandard oder ISO 2768-1 m/c, Winkel separat (z. B. ±1°) | |

Werte dieser Normen aus der Norm übernehmen; nicht schätzen.
