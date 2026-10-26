"""FreeCAD-Adapter (TechDraw, getestet mit FreeCAD 1.1).

FreeCAD hat keine COM-Schnittstelle: Der Adapter startet FreeCAD mit fc_arbeiter.py – für die Analyse
ohne Oberfläche (freecadcmd), für Zeichnung und PDF unsichtbar mit Oberfläche (QT_QPA_PLATFORM=offscreen).
Die Zeichnung wird als eigene .FCStd gespeichert (Kopie des Teils mit Zeichnungsblatt); das Teil selbst
bleibt unverändert. Ansichtsrichtungen wie im Bauplan: vorne = Blick auf die −Y-Seite, Z oben.
"""
import glob
import json
import os
import re
import subprocess
import sys
import tempfile

from cad_basis import Adapter, CadFehler

HIER = os.path.dirname(os.path.abspath(__file__))
MODELL = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HIER))), "cad-modellierung", "scripts")


def _freecad():
    """Pfad zu bin/freecadcmd.exe (neueste Version) oder None."""
    if os.path.isdir(MODELL):
        sys.path.insert(0, MODELL)
        try:
            import modell
            kand = modell._freecad_kandidaten()
            return kand[0] if kand else None
        except Exception:
            pass
    muster = [os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "FreeCAD*", "bin", "freecadcmd.exe"),
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "FreeCAD*", "bin", "freecadcmd.exe")]
    gef = sorted(p for m in muster for p in glob.glob(m))
    return gef[-1] if gef else None


class FreeCAD(Adapter):
    name = "freecad"
    getestet = True
    endung_teil = ".FCStd"

    @classmethod
    def verfuegbar(cls):
        cmd = _freecad()
        if not cmd:
            return False, False, "nicht installiert"
        m = re.search(r"FreeCAD[ _-]?(\d+\.\d+)", cmd, re.I)
        return True, False, f"FreeCAD {m.group(1) if m else ''} ({cmd})"

    def verbinden(self, sichtbar=True):
        self.cmd = _freecad()
        if not self.cmd:
            raise CadFehler("FreeCAD ist nicht installiert (modell.py installieren freecad)")
        self.gui = os.path.join(os.path.dirname(self.cmd), "freecad.exe")
        return "FreeCAD"

    def _lauf(self, auftrag, gui=False, zeit=600):
        tmp = os.path.join(tempfile.gettempdir(), "ccw")
        os.makedirs(tmp, exist_ok=True)
        auftrag = dict(auftrag, skripte=HIER, ergebnis=os.path.join(tmp, "fc-ergebnis.json"))
        if os.path.exists(auftrag["ergebnis"]):
            os.remove(auftrag["ergebnis"])
        pfad = os.path.join(tmp, "fc-auftrag.json")
        json.dump(auftrag, open(pfad, "w", encoding="utf-8"), ensure_ascii=False)
        env = dict(os.environ, CCW_FC=pfad)
        if gui:
            env["QT_QPA_PLATFORM"] = "offscreen"
        try:
            r = subprocess.run([self.gui if gui else self.cmd, os.path.join(HIER, "fc_arbeiter.py")], env=env,
                               cwd=tmp, capture_output=True, text=True, errors="replace", timeout=zeit)
        except subprocess.TimeoutExpired:
            raise CadFehler(f"FreeCAD hat nach {zeit} s nicht geantwortet")
        if not os.path.exists(auftrag["ergebnis"]):
            raise CadFehler("FreeCAD lieferte kein Ergebnis: " + (r.stdout[-800:] + r.stderr[-800:]).strip())
        erg = json.load(open(auftrag["ergebnis"], encoding="utf-8"))
        if erg.get("absturz"):
            raise CadFehler("FreeCAD-Fehler:\n" + erg["absturz"])
        return erg

    def analysieren(self, pfad):
        if not pfad.lower().endswith(".fcstd"):
            raise CadFehler("Der FreeCAD-Adapter analysiert .FCStd-Dateien (STEP vorher in FreeCAD öffnen)")
        return self._lauf({"modus": "analysieren", "teil": os.path.abspath(pfad)})

    def zeichnen(self, auftrag, basis="."):
        return self._lauf({"modus": "zeichnen", "auftrag": auftrag, "basis": os.path.abspath(basis)}, gui=True)

    def exportieren(self, pfad, formate=("pdf",)):
        erg = self._lauf({"modus": "export", "zeichnung": os.path.abspath(pfad), "formate": list(formate)}, gui=True)
        return erg["dateien"]

    def schliessen(self):
        pass  # jeder Lauf ist ein eigener FreeCAD-Prozess

    def testteil(self, pfad):
        """Welle wie im SolidWorks-Selbsttest, gebaut über den Bauplan (Achse = X)."""
        if not os.path.isdir(MODELL):
            raise CadFehler("Skill cad-modellierung fehlt – Testteil kann nicht gebaut werden")
        ordner = os.path.dirname(os.path.abspath(pfad))
        os.makedirs(ordner, exist_ok=True)
        plan = {"name": os.path.splitext(os.path.basename(pfad))[0], "werkstoff": "C45",
                "features": [{"id": "Welle", "typ": "drehteil", "ebene": "XZ", "achse": "X", "profil": [{"kontur": [
                    [0, 0], [0, 9], [1, 10], [20, 10], [20, 12.5], [40, 12.5], [40, 16], [120, 16], [120, 12.5],
                    [140, 12.5], [140, 8], [159, 8], [160, 7], [160, 0]]}]}],
                "soll": {"huelle": [0, -16, -16, 160, 16, 16]}}
        pp = os.path.join(ordner, plan["name"] + ".json")
        json.dump(plan, open(pp, "w", encoding="utf-8"), ensure_ascii=False)
        r = subprocess.run([sys.executable, "-I", os.path.join(MODELL, "modell.py"), "bauen", pp, "--cad", "freecad",
                            "--ohne-vorschau"], capture_output=True, text=True, errors="replace")
        if r.returncode:
            raise CadFehler("Testteil nicht gebaut: " + r.stdout[-600:])
        return os.path.join(ordner, plan["name"] + ".FCStd")
