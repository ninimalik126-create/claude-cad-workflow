# 04 Bezüge und Bezugssysteme (ISO 5459:2011)

## Begriffe

- **Bezugselement (datum feature):** reales Element am Werkstück (Fläche, Zylinder …), gekennzeichnet mit dem Bezugsdreieck und Buchstaben im Quadrat.
- **Bezug (datum):** ideales, aus dem Bezugselement abgeleitetes Element (Ebene, Achse, Punkt, Kombination). Zuordnung standardmäßig: für Ebene „Tschebyscheff von außen, Material-außen“ (Anlage), für Zylinder kleinster umschriebener (Welle) / größter einbeschriebener (Bohrung).
- **Bezugssystem:** Folge von bis zu drei Bezügen mit Rangfolge. Reihenfolge im Rahmen von links nach rechts = Priorität.
- **Gemeinsamer Bezug:** `A-B` – zwei Elemente bilden gemeinsam einen Bezug (z. B. Achse durch zwei Lagersitze). Gleichrangig.
- **Bezugsstellen (datum targets):** Punkte, Linien, Flächenbereiche (ISO 5459 Kap. 9) für Roh-, Guss-, Schmiede-, Blechteile: `A1`, `A2`, `A3` im geteilten Kreis, Zielsymbol ✕ auf der Fläche.

## Kennzeichnung

- Bezugsdreieck (gefüllt oder leer, gleichwertig) direkt auf der Kontur oder Maßhilfslinie → **Fläche** ist Bezugselement.
- Dreieck **in Verlängerung der Maßlinie** eines Maßelements → **Achse / Mittelebene** ist Bezug.
- Buchstaben: Großbuchstaben, keine Wiederholung auf einer Zeichnung. Verwechselbare Buchstaben (I, O, Q, X) vermeiden. Nach Z: AA, AB …
- Bezugsbuchstabe nicht doppelt an verschiedene Elemente.
- Ein definierter Bezug muss mindestens in einem Rahmen verwendet werden.

## Wahl der Bezüge aus der Funktion (3-2-1)

| Rang | Sperrt | Typisch | Bezugselement |
|---|---|---|---|
| Primär | 3 Freiheitsgrade (Ebene: 1 Translation + 2 Rotationen) oder 4 (Zylinder: 2 Transl. + 2 Rot.) | größte Anlagefläche bzw. Zentrierzylinder | flächig anliegende Montagefläche; langer Zentrierzylinder |
| Sekundär | 2 bzw. 1–2 | Zentrierung/Anschlag | Passbohrung, Seitenanschlag, Stirnfläche |
| Tertiär | restliche (meist 1 Rotation) | Verdrehsicherung | Passstift, Nut, Schlüsselfläche |

Prüfen: **Ist das Teil mit dem Bezugssystem in der Messung genauso aufgenommen wie im Einbau?** Wenn nicht, ist das Bezugssystem falsch gewählt.

**Kurzer Zylinder + großer Bund:** Bund (Ebene) primär, Zylinder sekundär.
**Langer Zylinder (L/D > ~1):** Zylinder primär, Bund sekundär.
**Welle in zwei Lagern:** gemeinsamer Bezug `A-B` (beide Lagersitze).

## Modifikatoren in der Bezugszelle

| Angabe | Bedeutung |
|---|---|
| `AⓂ` | Bezugselement bei Maximum-Material (Bezug darf sich im Rahmen des Spiels „bewegen“, Lehre fest) – nur bei Maßelement-Bezug |
| `AⓁ` | Bezug bei Minimum-Material |
| `A [ACS]` | Bezug aus beliebigem Querschnitt |
| `A [PL]` / `[SL]` / `[PT]` | nur Ebene / Gerade / Punkt des Bezugs verwenden |
| `A [CF]` | Kontaktelement (z. B. Kegel, Prisma) |
| `A [DV]` | variabler Abstand (bei Bezugsstellen) |
| `A ><` | nur Richtungsbindung (Orientierung), keine Lagebindung |
| `A-B` | gemeinsamer Bezug |
| `A1-A2-A3` | Bezug aus Bezugsstellen |

## Typische Fehler

1. Bezug an einer Fläche, die im Einbau keine Funktion hat (z. B. Rohteilkante).
2. Primärbezug nicht stabil (schmale Fläche, kurzer Zylinder) → Messung nicht reproduzierbar.
3. Bezug auf Mittellinie gezeichnet (Mittellinie ist kein reales Element) – Dreieck muss am Maßelement sitzen.
4. Reihenfolge im Rahmen widerspricht der Funktion (z. B. `|⌖|⌀0,1|B|A|`, obwohl A die Anlage ist).
5. Unvollständiges Bezugssystem bei Positionstoleranzen, das Rotation nicht sperrt, obwohl die Lage rotatorisch definiert sein muss.
6. Bezugsflächen ohne eigene Formtoleranz, obwohl die Bezugsqualität kritisch ist → Primärbezug ggf. mit `|⏥|t|`, Sekundär mit `|⟂|t|A|` tolerieren.
