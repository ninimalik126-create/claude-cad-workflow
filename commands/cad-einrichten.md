---
description: Prüft und richtet die CAD-Anbindung ein (FreeCAD, SolidWorks; Inventor/CATIA vorbereitet), installiert fehlende Software nach Zustimmung, merkt sich auf Wunsch Standardprogramm und -ausgaben und führt einen Selbsttest durch.
argument-hint: [freecad|solidworks|inventor|catia]
---

Ziel: Feststellen, ob das Plugin auf diesem Rechner Teile bauen und Zeichnungen erzeugen kann.

1. `python -I "${CLAUDE_PLUGIN_ROOT}/skills/cad-modellierung/scripts/modell.py" umgebung --neu` – Ergebnis als kurze Tabelle zeigen (Python, FreeCAD, SolidWorks, pywin32, Vorgaben).
2. Fehlt etwas, das gebraucht wird: sagen, was installiert würde (FreeCAD über winget, ca. 500 MB; pywin32 über pip), und **erst nach Zustimmung** `modell.py installieren freecad|pywin32`.
3. Selbsttest Modellbau und Netz-Werkzeuge (FreeCAD, ohne Rückfrage, drei bis vier Minuten): `python -I "${CLAUDE_PLUGIN_ROOT}/skills/cad-modellierung/scripts/selbsttest.py"`. Ergebnis muss „OK – alles bestanden“ sein; sonst die gemeldeten Punkte nennen. Für SolidWorks vorher sagen, dass SolidWorks gestartet wird (offene Dokumente bleiben unberührt), dann den Beispielplan `beispiele/halter.json` mit `modell.py bauen … --cad solidworks --ordner <kurzer Ordner>` bauen.
4. Zeichnungsweg: `python -I "${CLAUDE_PLUGIN_ROOT}/skills/iso-gps-bemassung/scripts/cad/cad.py" erkennen`. Bei SolidWorks nach Zustimmung (schließt offene, ungespeicherte Dokumente!) `cad.py selbsttest --cad solidworks --ordner <kurzer Ordner>`; bei FreeCAD `cad.py selbsttest --cad freecad --ordner <kurzer Ordner>`. Erzeugtes PDF ansehen und per SendUserFile zeigen.
5. Vorgaben anbieten (eine Frage): Soll ein Programm mit festen Ausgaben Standard sein? Bei Ja `modell.py vorgaben --cad freecad --formate step,stl` – danach entfällt die Auswahlkarte bei jedem Teil. `modell.py vorgaben --loeschen` stellt die Karte wieder her.
6. Inventor/CATIA: kein Testteil eingebaut – um ein einfaches Teil bitten und `/zeichnung-erstellen` durchlaufen; diese Adapter sind ungetestet.
7. Zusammenfassen: womit ab jetzt gebaut und gezeichnet wird.
