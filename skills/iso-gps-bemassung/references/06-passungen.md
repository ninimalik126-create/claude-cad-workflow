# 06 Passungen (ISO 286-1/-2)

**Grenzabmaße immer berechnen:** `python -I scripts/passung.py <Nennmaß> <Feld>` oder `<Bohrung>/<Welle>`. Hinterlegt: IT3–IT14, Grundabmaße d e f g h js k m n p (Wellen) und D E F G H JS K M N P (Bohrungen), Nennmaße bis 500 mm. Andere Felder (a, b, c, r, s, t, u, x, z …) in ISO 286-2 nachschlagen und kennzeichnen.

## Systeme

- **Einheitsbohrung (H):** Standard im Maschinenbau – Bohrungen mit H, Wellen variieren. Weniger Reibahlen/Lehrdorne.
- **Einheitswelle (h):** bei gezogenem Blankstahl, langen Wellen mit mehreren Passungen, Normteilen mit h-Toleranz (Passstifte m6/h8, Wälzlager-Außenring bezogen auf Gehäuse).

## Empfohlene Passungen nach Funktion

| Funktion | Passung | Art |
|---|---|---|
| Teile leicht verschiebbar, großes Spiel (Landmaschinen, Scharniere grob) | H11/c11, H11/d9 | Spiel |
| Gleitlager allgemein, Lauf mit Schmierfilm | H8/f7, H7/f7 | Spiel |
| Genaue Führung, Gleitsitz, Zentrierung lösbar | H7/g6 | Spiel |
| Zentrierung, von Hand fügbar, Schiebesitz | H7/h6 | Spiel (Mindestspiel 0) |
| Zentrierung, leichter Übergang, mit Gummihammer | H7/js6 | Übergang |
| Zahnräder, Riemenscheiben auf Welle mit Passfeder | H7/k6 | Übergang |
| Fester Sitz, Ausbau mit Abzieher | H7/m6, H7/n6 | Übergang |
| Presssitz, Drehmoment ohne Passfeder (begrenzt) | H7/p6 | Übermaß |
| Starker Presssitz, Schrumpfen | H7/s6, H7/u6 (ISO 286-2) | Übermaß |
| Passstift in Stahlbohrung | ⌀ H7 / Stift m6 (ISO 8734) | Übergang–Übermaß |
| Zylinderstift lösbar (ISO 2338 h8) | H7 | Spiel |

## Wälzlager (Richtwerte, Herstellerkatalog maßgebend)

| Ring | Lastfall | Typisches Feld (normale Last) |
|---|---|---|
| Innenring auf Welle | Umfangslast (Welle dreht, Lastrichtung steht) | k5, k6, m5, m6 je nach Größe/Last |
| Innenring auf Welle | Punktlast (Welle steht oder Last läuft mit) | g6, h6 |
| Außenring im Gehäuse | Punktlast (Gehäuse steht, Lastrichtung steht) | H7, J7 |
| Außenring im Gehäuse | Umfangslast (Gehäuse/Nabe dreht) | N7, P7 |

Bei Kegelrollen- und Präzisionslagern stets nach Herstellerangabe. Zusätzlich Form- und Lauftoleranzen der Sitze nach Herstellerkatalog (typisch Zylinderform IT5/2, Planlauf Schulter IT5).

## Grade nach Fertigungsverfahren (Richtwerte)

| IT | Verfahren |
|---|---|
| IT4–IT5 | Feinschleifen, Läppen, Honen |
| IT6 | Schleifen, Feindrehen |
| IT7 | Feindrehen, Reiben, Feinfräsen |
| IT8–IT9 | Drehen, Fräsen, Bohren mit Nacharbeit |
| IT10–IT11 | Bohren, Fräsen, Hobeln |
| IT12–IT14 | Sägen, Laser, Stanzen, Kanten |

## Eintragung

- `⌀25 H7` – reicht nach ISO; für Werkstattzeichnungen **mit Grenzabmaßen in Klammern**: `⌀25 H7 (+0,021/0)`.
- Passungsangabe in Baugruppenzeichnungen: `⌀25 H7/g6`.
- **Hüllbedingung:** ISO 8015 ⇒ Formabweichung nicht durch Passung begrenzt. Bei Fügefunktion `⌀25 H7 Ⓔ` oder geeignete Form-/Richtungstoleranz ergänzen.
- Bei Beschichtung (Eloxal, Verzinken, Hartchrom): Maß ausdrücklich „vor/nach Beschichtung“ angeben; Schichtdicke wirkt am Durchmesser doppelt.
