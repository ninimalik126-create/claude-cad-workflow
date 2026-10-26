# claude-cad-workflow

Claude-Code-Plugin, mit dem Claude **CAD-Teile baut** (FreeCAD oder SolidWorks) und **technische Zeichnungen nach ISO GPS** erstellt, prüft und toleriert.

Du beschreibst das Teil – als Text, Skizze, Foto mit Maßen oder alte Zeichnung. Claude fragt nur, was fehlt, lässt dich Programm und Ausgaben in einer Abfrage wählen, baut das Teil, prüft es selbst und gibt dir die Dateien.

## Was es kann

| Aufgabe | Ergebnis |
|---|---|
| Teil bauen | Native Datei (`.FCStd` / `.SLDPRT`) mit sauberem Feature-Baum, dazu wahlweise **STEP, STL, 3MF** |
| Selbstprüfung | Jedes Feature wird einzeln geprüft (Richtung, Volumen, ein Körper), dazu Soll-Hülle und Vorschaubild mit vier Ansichten |
| Zeichnung | Native, editierbare Zeichnung (FreeCAD TechDraw oder SolidWorks) plus PDF: Ansichten, Maße, ISO-Passungen, Form- und Lagetoleranzen, Bezüge, Oberflächen, Schriftfeld |
| Zeichnung prüfen | Befundliste nach einer 37-Punkte-Prüfliste (ISO 8015, 1101, 5459, 2692, 14405, 286, 129-1 …) |
| Passungen | ISO-286-Grenzabmaße und Spiel/Übermaß |

FreeCAD und SolidWorks bauen aus **demselben Bauplan dasselbe Teil** – in Tests volumengleich bis auf die dritte Nachkommastelle.

## Voraussetzungen

- Windows 10/11, [Claude Code](https://claude.com/claude-code)
- Python 3.10 oder neuer
- **FreeCAD 1.0+** (kostenlos) – fehlt es, installiert Claude es auf Nachfrage über winget
- optional **SolidWorks** (getestet mit 2026) mit Python-Paket `pywin32` – installiert Claude auf Nachfrage

## Installation

In Claude Code:

```
/plugin marketplace add ninimalik126-create/claude-cad-workflow
/plugin install claude-cad-workflow@claude-cad-workflow
```

Ohne GitHub-Befehl: Auf der Repository-Seite **Code → Download ZIP**, entpacken, dann:

```
/plugin marketplace add C:\Pfad\zu\claude-cad-workflow
/plugin install claude-cad-workflow@claude-cad-workflow
```

Danach einmal `/claude-cad-workflow:cad-einrichten` – prüft FreeCAD/SolidWorks, installiert Fehlendes nach Rückfrage und baut ein Testteil.

## Benutzung

```
/claude-cad-workflow:teil-erstellen Wandhalter für ein 32-mm-Rohr, 3D-Druck, zwei Schrauben M5
```

Oder einfach schreiben: „Bau mir einen Adapter von 25 auf 19 mm Innendurchmesser, 40 mm lang, für den 3D-Drucker.“ Ein Foto mit Maßen oder eine Skizze beschleunigt alles.

| Befehl | Zweck |
|---|---|
| `/claude-cad-workflow:teil-erstellen` | Teil bauen (Infophase → Programm/Ausgaben → Bau → Prüfung → Dateien) |
| `/claude-cad-workflow:zeichnung-erstellen` | Fertigungszeichnung im CAD oder neutral |
| `/claude-cad-workflow:tolerieren` | Tolerierungskonzept aus der Funktion |
| `/claude-cad-workflow:zeichnung-pruefen` | Zeichnung (PDF/Bild/CAD) prüfen |
| `/claude-cad-workflow:passung` | ISO-Passung rechnen |
| `/claude-cad-workflow:cad-einrichten` | Einrichtung und Selbsttest |

Änderungen sind einfach: „Mach die Bohrungen 0,2 mm größer“ – Claude ändert den Bauplan neben dem Teil und baut neu.

## Grenzen

- Einzelteile; keine Baugruppen, keine Blechabwicklungen, keine organischen Freiformflächen nach Gefühl
- Gewinde sind kosmetisch (Kernloch + Gewindedarstellung); kleine Gewinde im 3D-Druck besser mit Einsätzen oder Muttern
- Bohrungen mit flachem Grund
- FreeCAD-Zeichnung: Toleranzrahmen, Bezüge und Oberflächenzeichen sind Symbole mit Hinweislinie (nicht an Kanten gebunden)
- Inventor- und CATIA-Anbindung sind geschrieben, aber ungetestet

## Aufbau

| Teil | Inhalt |
|---|---|
| `skills/cad-modellierung/` | Ablauf, Bauplan-Format, Infophase, freie Skripte; `scripts/modell.py` (Steuerung), `bau_freecad.py`, `bau_solidworks.py`, `vorschau.py`, `bauplan.py`; Beispiele |
| `skills/iso-gps-bemassung/` | ISO-GPS-Wissen (15 Kapitel), Zeichnungsgenerator, Passungsrechner, CAD-Anbindung `scripts/cad/` (SolidWorks, FreeCAD, Inventor, CATIA) |
| `commands/` | die Befehle oben |

## Lizenz

MIT – siehe [LICENSE](LICENSE). Frei nutzen, ändern und weitergeben, solange Name und Lizenz dabeibleiben.

## Haftungsausschluss

Die Modelle und Zeichnungen entstehen automatisch. Maße, Toleranzen, Werkstoffe und Festigkeit müssen vor der Fertigung von einer fachkundigen Person geprüft werden. Für sicherheitsrelevante Teile (z. B. Fahrzeug, Bremse, Lenkung, Last tragen, Druck) ist das Plugin nicht gedacht. Die Normzusammenfassungen ersetzen keine Normtexte. Benutzung auf eigene Verantwortung.
