# 05 Maximum-/Minimum-Material-Bedingung (ISO 2692:2021)

## Begriffe

| Begriff | Welle (Außenelement) | Bohrung (Innenelement) |
|---|---|---|
| MMS – Maximum-Material-Grenzmaß | Höchstmaß | Mindestmaß |
| LMS – Minimum-Material-Grenzmaß | Mindestmaß | Höchstmaß |
| MMVS – Maximum-Material-Wirkungsgrenzmaß | MMS + t | MMS − t |
| LMVS – Minimum-Material-Wirkungsgrenzmaß | LMS − t | LMS + t |

## Ⓜ – Maximum-Material-Bedingung (MMR)

**Funktion: Fügbarkeit** (Schrauben durch Bohrungen, Stifte in Bohrungen, Wellen in Gehäuse).
- Definiert ein Wirkungsgrenzmaß (MMVS), das nicht verletzt werden darf, plus die Grenzmaße des Elements (LP).
- **Bonus:** Weicht das Maß vom MMS Richtung LMS ab, darf die Geometrieabweichung um diesen Betrag größer werden.
- Prüfbar mit **Funktionslehre** (fester Lehrdorn mit MMVS an Soll-Lage) + Zweipunktmessung der Grenzmaße → ideal für Werkstattprüfung ohne KMG.
- Nur an **Maßelementen** und deren abgeleiteten Elementen (Achse, Mittelebene). Nie an ebenen Flächen.
- Typisch bei: Position, Rechtwinkligkeit, Parallelität, Neigung, Geradheit der Achse, Koaxialität, Symmetrie.

**Nullbetrag:** `|⌖|⌀0 Ⓜ|A|B|` – gesamte Toleranz aus dem Maß, maximale Flexibilität für die Fertigung bei gleicher Funktion; Maßtoleranz entsprechend erweitern.

**Beispiel Schraubverbindung (Durchgangsbohrung, beide Teile mit Bohrungen):**
Schraube M6 (⌀ max. 6,0), Bohrung ⌀6,6 (ISO 273 mittel), H = MMS der Bohrung = 6,6, F = 6,0.
- **Schwimmende Verbindung** (Schraube + Mutter, beide Teile mit Durchgangsbohrung): je Teil t = H − F = 0,6 → `4× ⌀6,6 +0,2/0` + `|⌖|⌀0,6 Ⓜ|A|B|C|` an beiden Teilen.
- **Feste Verbindung** (ein Teil mit Gewinde): t_Bohrung + t_Gewinde = H − F = 0,6, z. B. Durchgangsteil `|⌖|⌀0,3 Ⓜ|A|B|C|`, Gewindeteil `|⌖|⌀0,3 Ⓟ 10|A|B|C|` (projizierte Zone = Dicke des Durchgangsteils).
- Formeln setzen gleiche Bezugssysteme in beiden Teilen voraus (Anlage = A in beiden).

## Ⓛ – Minimum-Material-Bedingung (LMR)

**Funktion: Mindestwandstärke, Mindestüberdeckung** (Bohrung nahe Kante, Rohrwand, Dichtfläche).
- Bonus wenn Maß vom LMS Richtung MMS abweicht.
- Nicht mit Lehre prüfbar → KMG/rechnerisch.

## Ⓡ – Reziprozitätsbedingung

Zusätzlich zu Ⓜ oder Ⓛ: Nutzt die Fertigung die Geometrietoleranz nicht aus, darf die Maßtoleranz entsprechend überschritten werden (MMVS bleibt). Angabe `⌀0,1 Ⓜ Ⓡ`.

## Ⓜ am Bezug

`|⌖|⌀0,2 Ⓜ|A|BⓂ|` – der Bezug B (Maßelement) wird mit seinem MMVS in der Lehre abgebildet; Spiel des Bezugselements darf ausgenutzt werden (Bezugsverschiebung). Nur sinnvoll, wenn im Einbau dasselbe Spiel existiert.

## Entscheidungshilfe

| Frage | → |
|---|---|
| Geht es um Fügen/Montierbarkeit? | Ⓜ |
| Geht es um Mindestmaterial, Wandstärke, Festigkeit? | Ⓛ |
| Geht es um exakte Lage (Zentrierung, Passstift, Lager, Dichtung, Zahnradeingriff)? | **ohne** Modifikator (RFS) |
| Wird nur mit Handmessmitteln/Lehren geprüft? | Ⓜ ermöglicht Lehrenprüfung |
