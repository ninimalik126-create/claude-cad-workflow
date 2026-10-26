# 02 Maßeintragung (ISO 129-1, ISO 14405-1/-2/-3)

## Elemente einer Maßangabe (ISO 129-1)

- **Maßhilfslinie:** schmale Volllinie, beginnt mit kleinem sichtbarem Abstand (ca. 1 mm) zur Kontur oder ohne Abstand, ragt ca. 2 mm über die Maßlinie hinaus. Senkrecht zum bemaßten Element; schräg (ca. 60°) nur wenn nötig.
- **Maßlinie:** schmale Volllinie, parallel zum bemaßten Element. Abstand erste Maßlinie zur Kontur ≈ 10 mm (Papier), zwischen parallelen Maßlinien ≈ 7–8 mm, gleichmäßig.
- **Begrenzung:** gefüllter Pfeil (Standard, ca. 15°–30° Öffnung, Länge ≈ 10 × Linienbreite / ≈ 3 mm bei h = 3,5), alternativ Schrägstrich (Bauwesen) oder Punkt (bei Platzmangel in Kettenmaßen). Auf einer Zeichnung einheitlich.
- **Maßzahl:** Schrifthöhe nach ISO 3098, typisch 3,5 mm (A4/A3), mittig über der Maßlinie, ohne die Linie zu berühren; lesbar von unten oder von rechts (Methode 1). Nie von Linien geschnitten – Linien unterbrechen.
- **Hinweislinie/Bezugslinie:** schmale Volllinie, endet mit Pfeil auf Kontur, Punkt in Fläche, ohne Begrenzung auf Maßlinie/Mittellinie.

## Kennzeichen vor der Maßzahl

| Zeichen | Bedeutung | Beispiel |
|---|---|---|
| ⌀ | Durchmesser | ⌀25 |
| R | Radius | R5 |
| S⌀ / SR | Kugeldurchmesser / Kugelradius | S⌀10, SR5 |
| □ | Quadrat (Seitenlänge) | □12 |
| CR | kontrollierter Radius (ohne Umkehrpunkte, ISO 129-1:2018) | CR10 |
| ⌒ über Zahl | Bogenlänge | ⌒35 |
| t= | Dicke (Blech) | t=2 |
| ⌴ / ⌵ / ↧ | Flachsenkung / Kegelsenkung / Tiefe (ISO 129-1 Anhang) | ⌴⌀11 ↧6,4 |
| 4× | Anzahl gleicher Elemente | 4× ⌀6,6 |
| (25) | Hilfsmaß, nicht toleriert, nur Information | (120) |
| [25] / eingerahmt | Theoretisch genaues Maß (TED) | |25| |
| 25 unterstrichen | nicht maßstäbliches Maß | |

Durchmesserzeichen ⌀ immer angeben, auch wenn die Kreisform in der Ansicht sichtbar ist (ISO 129-1: bei Kreisansicht darf es entfallen, Firmenstandard: immer setzen).

## Toleranzangabe am Maß

| Form | Beispiel | Hinweis |
|---|---|---|
| Symmetrisch | 40 ±0,1 | gleiche Schriftgröße |
| Grenzabmaße | 40 +0,1 / −0,05 (gestapelt, oberes oben) | Abmaß 0 ohne Vorzeichen; beide Abmaße gleiche Dezimalstellen |
| Grenzmaße | 40,1 / 39,95 gestapelt | Höchstmaß oben |
| Einseitig | 40 max. / 40 min. | z. B. Fasen, Radien |
| ISO 286 Kurzzeichen | ⌀25 H7 | bei Bedarf mit Abmaßen in Klammern: ⌀25 H7 (+0,021/0) |
| Zuordnung Ⓔ | ⌀25 h6 Ⓔ | Hüllbedingung |

## ISO 14405-1: Spezifikationsmodifikatoren für Längenmaße

Standard (ohne Modifikator): **Zweipunktmaß (LP)** an jeder Stelle des Maßelements.

| Modifikator | Bedeutung | Typische Verwendung |
|---|---|---|
| (LP) | Zweipunktmaß (Standard) | allgemein |
| (LS) | örtliches Maß aus Kugel | |
| (GG) | Gauß-Ausgleichselement (kleinste Fehlerquadrate) | KMG-gemessene Durchmesser |
| (GX) | größtes einbeschriebenes Element (Pferch) | Bohrung für Welle |
| (GN) | kleinstes umschriebenes Element (Hülle) | Welle für Bohrung |
| (GC) | Tschebyscheff (Minimum-Zone) | |
| (CC) / (CA) / (CV) | Umfangs- / Flächen- / Volumendurchmesser | dünnwandige, verformbare Teile |
| (SX) (SN) (SA) (SM) (SD) (SR) (SQ) | Rangordnungsmaße: Max, Min, Mittel, Median, Mittenbereich, Spannweite, Standardabw. | statistische Bewertung von örtlichen Maßen |
| Ⓔ | Hüllbedingung = (LP) für das Minimum-Material-Maß + (GN) bzw. (GX) für das Maximum-Material-Maß | Passungen, die Fügen sicherstellen müssen |
| ACS | beliebiger Querschnitt | Ⓔ oder (GG) je Schnitt |
| SCS | bestimmter Querschnitt | |
| ALS | beliebiger Längsschnitt | |
| /Länge | beliebiger begrenzter Bereich | ⌀20 ±0,1 (GG) /10 |
| CT | gemeinsam toleriertes Maßelement (mehrere Elemente gemeinsam) | 2× ⌀10 ±0,1 (GX) CT |
| ⟷ zwischen Elementen | Gültigkeitsbereich | ⌀20 h7 A↔B |
| (LP)(SX) Kombination | Max. Wert aller Zweipunktmaße | |

Unterschiedliche Anforderungen an oberes und unteres Grenzmaß: `⌀20 +0,1/0 (GX)(LP)` – die erste Angabe gilt für das obere, die zweite für das untere Grenzmaß.

**ISO 14405-2:** Maße, die **keine** Maßelemente sind (z. B. Stufenmaße, Abstand Kante–Bohrung, Radien, Fasen) sind mit ± mehrdeutig. Für Lage zwischen nicht-gegenüberliegenden Elementen bevorzugt **Profil- oder Positionstoleranz mit TED und Bezug** verwenden. Wird ± trotzdem genutzt (Allgemeinmaße, unkritisch), ist das als bewusster Kompromiss zu sehen.

**ISO 14405-3:** Winkelmaße (Keil, Kegel) – Modifikatoren analog (LC, LS, GG …).

## Bemaßungsarten

| Art | Wann | Regel |
|---|---|---|
| **Parallelbemaßung** (Bezugsbemaßung) | Funktionsbezug an einer Fläche; Fertigung von einer Fläche aus | Alle Maße von einer Bezugskante. Keine Fehlerfortpflanzung. |
| **Steigende Bemaßung** | wie Parallelbemaßung, platzsparend | Ein Ursprungspunkt (Kreis), Maßzahlen an den Maßhilfslinien. |
| **Kettenbemaßung** | nur wenn Einzelabstände funktional sind | Toleranzen addieren sich; nie geschlossen. |
| **Koordinatenbemaßung** (Tabelle) | viele Bohrungen, CNC | Ursprung kennzeichnen, Tabelle mit Pos., X, Y, ⌀. |
| **Kombiniert** | | Funktionsmaße direkt, Rest von Bezug. |

## Funktions-, fertigungs- und prüfgerecht

**Funktionsgerecht:**
- Funktionsmaße direkt eintragen (das Maß, das die Funktion bestimmt, steht auf der Zeichnung – nicht aus anderen Maßen errechenbar).
- Bezugsflächen der Bemaßung = Anlage-/Zentrierflächen in der Baugruppe = Bezüge des Toleranzrahmens.
- Toleranz aus Maßkette der Baugruppe ableiten (arithmetisch Worst Case oder statistisch mit Begründung).

**Fertigungsgerecht:**
- Drehteile: Längen von der Planseite/Spannseite aus, Durchmesser immer als ⌀ in der Längsansicht.
- Frästeile: Bezugskante = Spann-/Anschlagkanten; Taschen mit Tiefe und Eckenradius (Fräserradius!).
- Keine Maße auf Kanten, die nach dem Prozess nicht existieren (z. B. Schnittpunkte von Fasen) – stattdessen theoretischer Schnittpunkt mit Hilfslinien.
- Bohrbilder: Teilkreis ⌀ + Winkel oder Lochabstand mit TED + Positionstoleranz.

**Prüfgerecht:**
- Maße auf messbare Elemente (reale Flächen), nicht auf Mittellinien von nicht vorhandenen Elementen.
- Maß zwischen zwei Flächen statt zwischen Fläche und Achse, wenn mit Handmessmittel geprüft wird – oder Positionstoleranz mit Bezug für KMG.
- Messbarkeit der Toleranz mit vorgesehenem Messmittel (siehe 11-pruefplanung.md).

## Anordnungsregeln (Lesbarkeit)

1. Maße bevorzugt **außerhalb** der Kontur, in der Ansicht, in der die Form am deutlichsten ist.
2. Kurze Maße innen, lange außen – **Maßhilfslinien kreuzen keine Maßlinien**.
3. Keine Maße an verdeckten Kanten.
4. Mittellinien, Konturen und Maßhilfslinien nicht als Maßlinien verwenden.
5. Maße eines Elements (z. B. Nut: Breite, Tiefe, Lage) möglichst in einer Ansicht zusammen.
6. Maßzahlen nicht im Schraffurbereich; falls unvermeidbar Schraffur unterbrechen.
7. Bei Platzmangel: Pfeile außen, Maßzahl außen oder über Hinweislinie.
8. Symmetrische Teile: Symmetrie durch Mittellinie zeigen und Gesamtmaße symmetrisch bemaßen, nicht von der Mittellinie aus (Ausnahme: Mittelebene als Bezug mit TED).
9. Gleiche Elemente einmal bemaßen mit Anzahl (6× …), Bezug zum Muster eindeutig.
10. Fasen: „1×45°“ (ISO 129-1: Fasenbreite × Winkel); bei anderen Winkeln Länge und Winkel.

## Sonderfälle

- **Kegel:** Kegelverhältnis 1:x mit Symbol oder Kegelwinkel; bevorzugt Profiltoleranz Fläche mit TED.
- **Neigung/Keil:** Neigungssymbol mit 1:x.
- **Bogen und Radien:** Mittelpunkt nur bemaßen, wenn funktional; Radius ohne Mittelpunktsmaß wird durch Tangentenbedingung bestimmt.
- **Symmetrische Halbschnitte:** Maßlinie über die Mittellinie hinaus mit nur einem Pfeil.
- **Unterbrochene Darstellung:** Maß trotzdem in voller Länge, Maßlinie nicht unterbrechen.
