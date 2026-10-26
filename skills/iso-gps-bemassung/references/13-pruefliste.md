# 13 Prüfliste (jede Zeichnung, vor Ausgabe)

Jeden Punkt abarbeiten. Ergebnis: ✔ erfüllt, ✘ Befund (mit Korrektur), – nicht zutreffend.

## A Grundlagen und Schriftfeld
1. „Tolerierung ISO 8015“ angegeben?
2. Allgemeintoleranzen angegeben (ISO 22081 oder ISO 2768-1 Klasse, ggf. Verfahrensnorm)?
3. Oberflächen-Sammelangabe vorhanden und Norm (ISO 21920-1 / ISO 1302) erkennbar?
4. Kantenzustand (ISO 13715) angegeben?
5. Werkstoff mit Normbezeichnung (z. B. `1.0503 C45+N`, `EN AW-6082 T6`), Halbzeug, Wärmebehandlung, Beschichtung (mit „Maße gelten vor/nach Beschichtung“)?
6. Pflichtfelder ISO 7200, Maßstab, Projektionssymbol, Blattnummer, Änderungsindex?

## B Vollständigkeit
7. Jedes Geometrieelement ist in Größe, Form, Richtung und Lage bestimmt (einzeln oder durch Allgemeintoleranz)?
8. Gesamtmaße (Länge, Breite, Höhe / ⌀ × L) vorhanden?
9. Alle Bohrungen: ⌀, Tiefe, Lage, Anzahl, Gewinde mit Kernloch- und Gewindetiefe, Senkungen?
10. Radien, Fasen, Freistiche, Nuten vollständig?
11. Jedes TED wird von einer Geometrietoleranz genutzt?

## C Eindeutigkeit / keine Überbestimmung
12. Keine geschlossenen Maßketten, keine Doppelbemaßung über Ansichten hinweg?
13. Keine Lage, die sowohl über ±-Maß als auch Positionstoleranz bestimmt ist?
14. Pfeilposition Toleranzrahmen: Integral- vs. abgeleitetes Element eindeutig?
15. Bezugsdreieck: Fläche vs. Achse eindeutig (in/neben Maßlinie)?
16. ⌀-Zeichen in der Toleranzzone dort und nur dort, wo zylindrische Zone gemeint ist?
17. ISO 14405-2-Problemfälle (Stufenmaße, Abstand Fläche–Kante bei Funktion) mit GPS-Toleranz gelöst?

## D Funktion
18. Bezugssystem entspricht Einbau (Anlage → A, Zentrierung → B, Verdrehsicherung → C)?
19. Funktionsmaße direkt eingetragen, Toleranzen aus Funktion/Maßkette begründbar?
20. Passungen passend zur Funktion; Hüllbedingung Ⓔ oder Formtoleranz, wo Fügen gesichert werden muss?
21. Ⓜ bei Fügefunktion, Ⓛ bei Mindestwand, ohne Modifikator bei exakter Lage?
22. Formtoleranzen kleiner als übergeordnete Richtungs-/Ortstoleranzen (sonst entfernen)?

## E Normkonformität der Syntax
23. Formtoleranzen ohne Bezug; Richtung/Ort/Lauf mit Bezug?
24. Bezugsbuchstaben definiert, einmalig, alle verwendet, keine I/O/Q/X?
25. Modifikatoren in korrekter Reihenfolge und am richtigen Element (Ⓜ nur an Maßelementen)?
26. Toleranzangaben: gleiche Dezimalstellen bei Abmaßen, Abmaß 0 ohne Vorzeichen, Dezimalkomma einheitlich?
27. Oberflächensymbole von unten/rechts lesbar, auf Material außen?

## F Fertigung und Prüfung
28. Toleranzen mit dem Verfahren erreichbar (Richtwerte 03/06/10)? Engste Toleranz begründet?
29. Werkzeugzugänglichkeit, Eckradien, Bohrtiefen, Auslauf?
30. Jedes Merkmal mit verfügbarem Messmittel prüfbar? KMG-Merkmale gekennzeichnet?
31. Bezugselemente real antastbar/aufnehmbar?

## G Darstellung und Lesbarkeit
32. Ansichten nach Projektionsmethode angeordnet, nötige Schnitte/Einzelheiten vorhanden, keine überflüssigen?
33. Linienarten und -breiten nach ISO 128?
34. Keine Maßzahl gekreuzt oder überdeckt; Maßlinienabstände gleichmäßig; Maßhilfslinien kreuzen keine Maßlinien?
35. Maße nicht an verdeckten Kanten; zusammengehörige Maße gruppiert?
36. Schraffur korrekt, Wellen/Schrauben/Rippen nicht längs geschnitten?
37. Schrifthöhen nach ISO 3098, Rahmenhöhe = 2 h?

**Ausgabe der Prüfung:** Tabelle `Nr | Ort | Befund | Norm | Korrektur | Schwere (Fehler/Verbesserung/Stil)`. Zuletzt eine Gesamtbewertung: freigabefähig ja/nein.
