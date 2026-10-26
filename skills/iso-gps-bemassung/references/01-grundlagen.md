# 01 Grundlagen ISO GPS (ISO 8015, ISO 14638, ISO 17450)

## Das GPS-System

ISO GPS (Geometrical Product Specifications) ist das von ISO/TC 213 gepflegte Normensystem für die Spezifikation und Verifikation der Geometrie von Werkstücken: Maß, Abstand, Form, Richtung, Ort, Lauf, Oberflächenbeschaffenheit, Kanten.

- **ISO 14638** – GPS-Matrixmodell: ordnet jede Norm einer Eigenschaft (Zeile) und einer Kettengliedstufe (Spalte: Symbole/Angaben → Anforderungen an Merkmale → Merkmale realer Elemente → Konformität → Messung → Messgeräte → Kalibrierung) zu. Grundnormen (ISO 8015, ISO 17450) gelten für alle.
- **ISO 17450-1/-2** – Begriffe: nominelle, reale, extrahierte, assoziierte Elemente; Operationen (Zerlegung, Extraktion, Filterung, Assoziation, Kollektion, Konstruktion); Spezifikationsunsicherheit, Mehrdeutigkeit.
- **ISO 14253-1** – Entscheidungsregeln für Konformität unter Messunsicherheit (Standard: Nachweis der Konformität liegt beim Lieferanten, Nachweis der Nichtkonformität beim Kunden; jeweils Toleranzzone um die erweiterte Messunsicherheit verkleinert bzw. vergrößert).

## ISO 8015:2011 – die Grundprinzipien

| Prinzip | Bedeutung für die Zeichnung |
|---|---|
| **Aufrufprinzip** (Invocation) | Sobald irgendein Teil des ISO-GPS-Systems aufgerufen wird (z. B. ein Rahmen nach ISO 1101), gilt das gesamte System. |
| **Hierarchieprinzip** | Globale Normen < allgemeine GPS-Normen; Angaben in der Zeichnung gehen den Standardregeln vor. |
| **Prinzip der definierenden Zeichnung** | Nur was spezifiziert ist, ist gefordert. Was fehlt, ist nicht gefordert, auch wenn es „üblich“ wäre. |
| **Merkmalprinzip** (Feature) | Ein Werkstück besteht aus Geometrieelementen; jede Anforderung bezieht sich auf ein Element oder eine Beziehung zwischen Elementen. |
| **Unabhängigkeitsprinzip** | Jede GPS-Anforderung gilt unabhängig von anderen, außer ein Modifikator (Ⓔ, Ⓜ, Ⓛ, CZ …) oder eine Norm verknüpft sie ausdrücklich. **Ein Maß ⌀20±0,1 begrenzt nicht die Rundheit, Geradheit oder Zylinderform.** |
| **Dezimalprinzip** | Werte sind mathematisch genau; 25 bedeutet 25,000… (keine Zusatznullen-Regeln für Genauigkeit). |
| **Standard-Bedingungsprinzip** | Referenztemperatur 20 °C (ISO 1), saubere Oberfläche, keine Einspannkräfte, sofern nichts anderes angegeben. |
| **Starres-Werkstück-Prinzip** | Werkstück gilt als unendlich steif, außer anders angegeben (für nicht formstabile Teile: ISO 10579, Angabe „ISO 10579-NR“ und Einspannbedingungen). |
| **Dualitätsprinzip** | Die Spezifikation ist unabhängig vom Messverfahren; das Verifikationsverfahren muss die Spezifikation abbilden. |
| **Funktionsbeherrschungsprinzip** | Jede Spezifikation soll die Funktion beschreiben; die Funktionsfähigkeit innerhalb der Toleranzen ist Aufgabe des Konstrukteurs. |
| **Allgemeine Spezifikation** | Allgemeintoleranzen gelten für alle nicht einzeln tolerierten Elemente (Angabe im Schriftfeld). |
| **Verantwortungsprinzip** | Mehrdeutigkeiten der Spezifikation (Spezifikationsunsicherheit) liegen in der Verantwortung des Konstrukteurs. |

## Was im Schrift-/Hinweisfeld stehen muss

```
Tolerierung ISO 8015
Allgemeintoleranzen ISO 22081 – … (oder ISO 2768-mK / -mH mit Normstandhinweis)
Werkstückkanten ISO 13715  (Symbol mit Standardwerten)
Oberflächen ISO 21920-1 (oder ISO 1302) – Sammelangabe, z. B. Ra 3,2 (✓)
Maße ohne Angabe gelten für den Endzustand (nach Beschichtung / vor Beschichtung angeben!)
```

## Alte Zeichnungen und Umstellung

| Situation | Bedeutung | Handlung |
|---|---|---|
| „Tolerierung DIN 7167“ oder kein Hinweis auf alter deutscher Zeichnung | Hüllprinzip galt für alle Maßelemente (Formabweichung innerhalb der Maßtoleranz). | Bei Überarbeitung auf ISO 8015 umstellen und **funktionsrelevante Hüllbedingungen mit Ⓔ ergänzen**, sonst geht die Formbegrenzung verloren. DIN 7167 ist zurückgezogen. |
| „ISO 2768-mK“ | ISO 2768-2 (Klassen H, K, L) ist zurückgezogen, wird aber vielfach weiter verwendet. Nach ISO 2768-2 ist die allgemeine Rundheitstoleranz gleich der Durchmessertoleranz, höchstens aber die allgemeine Lauftoleranz. | Neu: ISO 22081 bevorzugen; wenn Kunde ISO 2768 verlangt, Ausgabestand nennen (z. B. „ISO 2768-2:1989“). |
| „ISO 2768-mK-E“ | Zusätzlich Hüllprinzip für alle Maßelemente. | Bewusst entscheiden; meist nur Ⓔ an einzelnen Passmaßen sinnvoll. |
| ISO 1101:2004 / 2012 vs. 2017 | 2017 hat u. a. Profiltoleranz ISO 1660 integriert, neue Modifikatoren (CZ, SZ, UZ, OZ, VA, ><, Schnittebenen, Richtungselemente, Kollektionsebenen, ⓕ etc.). | Ausgabestand im Schriftfeld nennen, wenn neue Modifikatoren genutzt werden. |
| ISO 1302 vs. ISO 21920-1 | ISO 21920 ersetzt ISO 1302 / 4287 / 4288 (Profilverfahren). Standardwerte (Auswertelänge, Filter, Annahmeregel) wurden teils geändert. | Auf der Zeichnung festlegen, welche Norm gilt; bei ISO 21920 die dort definierten Standards beachten. |

## Begriffe (kurz)

- **Maßelement (feature of size):** Element, dessen Maß durch eine Größe beschrieben wird: Zylinder (⌀), Kugel, zwei gegenüberliegende parallele Ebenen (Breite), Kegel/Keil (Winkel). Nur Maßelemente können Ⓔ, Ⓜ, Ⓛ tragen und als Maßelement-Bezug dienen.
- **Abgeleitetes Element:** Achse, Mittelebene, Mittelpunkt – aus Maßelement abgeleitet. Pfeil des Rahmens **in Verlängerung der Maßlinie** → Toleranz gilt für das abgeleitete Element. Pfeil **deutlich versetzt von der Maßlinie** → Toleranz gilt für das Integralelement (Oberfläche).
- **TED (theoretisch genaues Maß):** Eingerahmtes Maß ohne Toleranz; beschreibt die ideale Lage/Form einer Toleranzzone. Nur zusammen mit Geometrietoleranz sinnvoll.
- **Toleranzzone:** Raum, in dem das tolerierte Element liegen muss (Breite t zwischen zwei parallelen Linien/Ebenen, Zylinder ⌀t, Kugel S⌀t, …).
