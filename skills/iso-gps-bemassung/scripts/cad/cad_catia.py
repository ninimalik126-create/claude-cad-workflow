"""CATIA-V5-Adapter (COM-Automation) – UNGETESTET, teilautomatisch.

Geschrieben nach der CATIA-V5-Automation-Dokumentation, ohne installiertes CATIA geprüft.

Was automatisch geht: Teil öffnen, Flächen analysieren (über SPAWorkbench-Messungen, per
VBScript in CATIA ausgeführt, weil Ausgabe-Arrays über COM aus Python unzuverlässig sind),
Zeichnung mit Blatt, Maßstab, Projektionsmethode, Ansichten, Hinweistext und Schriftfeldtexten.

Was nicht zuverlässig per API geht: Maße und Form-/Lagetoleranzen an *generierter* Geometrie
(CATIA V5 gibt die erzeugten 2D-Kanten über die Automation nicht sauber heraus). Dafür schreibt
der Adapter eine Eintrageliste (Markdown) neben die Zeichnung: jedes Maß, jeder Rahmen, jeder
Bezug mit Ansicht, Fläche und exakter Angabe – zum Eintragen im Drafting-Workbench in wenigen
Minuten. Alternative für Vollautomatik: 3D-Annotationen (FT&A) im Teil und daraus generieren.
"""
import os
import winreg

import pythoncom
import win32com.client

from cad_basis import Adapter, CadFehler, O, achsname, dot, liste, norm, runde, zusammenfassen

VBS_ANALYSE = r'''
Function CATMain(refName)
  On Error Resume Next
  Set doc = CATIA.ActiveDocument
  Set prt = doc.Part
  Set ref = prt.CreateReferenceFromName(refName)
  Set spa = doc.GetWorkbench("SPAWorkbench")
  Set m = spa.GetMeasurable(ref)
  Dim a(8), p(8)
  s = "A=" & CStr(m.Area)
  r = m.Radius
  If Err.Number = 0 Then
    s = s & ";R=" & CStr(r)
    m.GetPointsOnAxis p
    s = s & ";ACHSE=" & Join(p, ",")
  End If
  Err.Clear
  m.GetPlane a
  If Err.Number = 0 Then s = s & ";EBENE=" & Join(a, ",")
  Err.Clear
  CATMain = s
End Function
'''
PAPER = {"A0": 0, "A1": 1, "A2": 2, "A3": 3, "A4": 4}  # CatPaperSize catPaperA0 … catPaperA4 (Doku prüfen)


class Catia(Adapter):
    name = "catia"
    getestet = False
    endung_teil = ".CATPart"

    @classmethod
    def verfuegbar(cls):
        try:
            winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "CATIA.Application").Close()
        except OSError:
            return False, False, "nicht installiert"
        try:
            win32com.client.GetActiveObject("CATIA.Application")
            return True, True, "COM CATIA.Application"
        except Exception:
            return True, False, "COM CATIA.Application"

    def verbinden(self, sichtbar=True):
        pythoncom.CoInitialize()
        try:
            self.cat = O(win32com.client.GetActiveObject("CATIA.Application"))
        except Exception:
            self.cat = O(win32com.client.Dispatch("CATIA.Application"))
        self.cat.Visible = sichtbar
        return "CATIA V5"

    def schliessen(self):
        docs = self.cat.Documents()
        for i in range(docs.Count(), 0, -1):
            docs.Item(i).Close()

    def oeffnen(self, pfad):
        pfad = os.path.abspath(pfad)
        if not os.path.exists(pfad):
            raise CadFehler(f"Datei nicht gefunden: {pfad}")
        return self.cat.Documents().Open(pfad)

    def testteil(self, pfad):
        raise CadFehler("Selbsttest-Teil für CATIA ist nicht hinterlegt – vorhandenes Teil mit 'zeichnen' testen")

    # ------------------------------------------------------------------ Analyse
    def analysieren(self, pfad):
        doc = self.oeffnen(pfad)
        sel = doc.Selection()
        sel.Clear()
        sel.Add(doc.Part().MainBody())
        sel.Search("Topology.CGMFace,sel")
        refs = []
        for i in range(1, sel.Count() + 1):
            v = sel.Item(i).Value()
            refs.append(v.DisplayName())
        sel.Clear()
        flaechen = []
        for n, name in enumerate(refs, start=1):
            roh = self.cat.SystemService().Evaluate(VBS_ANALYSE, 0, "CATMain", [name])
            flaechen.append(self._flaeche(f"F{n}", name, roh))
        modell = {"cad": "catia", "datei": os.path.abspath(pfad), "einheit": "mm", "werkstoff": None,
                  "masse_kg": None, "eigenschaften": {}, "features": [], "flaechen": flaechen,
                  "hinweis": "CATIA-Analyse: Flächennormalen ohne Materialseite – Innen/Außen prüfen"}
        modell["merkmale"] = zusammenfassen(flaechen)
        return modell

    @staticmethod
    def _flaeche(fid, name, roh):
        werte = dict(x.split("=", 1) for x in str(roh).split(";") if "=" in x)
        zahl = lambda s: [float(t.replace(",", ".")) for t in s.split(",") if t.strip()]  # noqa: E731
        rec = {"id": fid, "ref": name, "flaeche_mm2": runde(float(werte.get("A", "0").replace(",", ".")), 2)}
        if "R" in werte and "ACHSE" in werte:
            p = zahl(werte["ACHSE"])
            a = norm([p[6] - p[3], p[7] - p[4], p[8] - p[5]])
            i = max(range(3), key=lambda k: abs(a[k]))
            if a[i] < 0:
                a = [-x for x in a]
            o = p[0:3]
            t = dot(o, a)
            ts = sorted([dot(p[3:6], a), dot(p[6:9], a)])
            rec.update(typ="zylinder", art="unbekannt", d=runde(2 * float(werte["R"].replace(",", ".")), 4),
                       achse={"punkt": runde([o[k] - t * a[k] for k in range(3)], 4), "richtung": runde(a, 6)},
                       bereich=runde(ts, 3))
        elif "EBENE" in werte:
            e = zahl(werte["EBENE"])
            u, v = e[3:6], e[6:9]
            n = norm([u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]])
            rec.update(typ="ebene", normale=runde(n, 6), lage=runde(dot(e[0:3], n), 4))
            ax = achsname(n)
            if ax:
                rec["normale_achse"] = ax
                rec[ax[1].lower()] = runde(e["XYZ".index(ax[1])], 4)
        else:
            rec["typ"] = "sonstige"
        return rec

    # ------------------------------------------------------------------ Zeichnung
    def zeichnen(self, auftrag, basis="."):
        from cad_solidworks import Protokoll, _massstab, _pfad
        prot = Protokoll()
        teil = _pfad(auftrag["teil"], basis)
        modell = self.analysieren(teil)
        part_doc = self.oeffnen(teil)
        b = auftrag.get("blatt", {})
        s1, s2 = _massstab(b.get("massstab", "1:1"))
        drw = self.cat.Documents().Add("Drawing")
        sheet = drw.Sheets().ActiveSheet()
        try:
            fmt = str(b.get("format", "A3")).upper()
            sheet.PaperSize = PAPER.get(fmt.replace("H", ""), 2)
            sheet.Orientation = 0 if fmt == "A4H" else 1  # catPaperPortrait / catPaperLandscape
            sheet.Scale = s1 / s2
            sheet.ProjectionMethod = 0  # catFirstAngle (Projektionsmethode 1)
            prot.ok("Blatt", f"{fmt} {s1:g}:{s2:g}, Projektionsmethode 1")
        except Exception as ex:
            prot.fehler("Blatt", str(ex))
        richtungen = {"vorne": (1, 0, 0, 0, 1, 0), "oben": (1, 0, 0, 0, 0, -1), "links": (0, 0, -1, 0, 1, 0),
                      "rechts": (0, 0, 1, 0, 1, 0), "hinten": (-1, 0, 0, 0, 1, 0), "unten": (1, 0, 0, 0, 0, 1)}
        for va in auftrag.get("ansichten", []):
            vid = va.get("id", va.get("richtung", "vorne"))
            try:
                v = sheet.Views().Add(vid)
                x, y = va.get("pos", [200, 150])
                v.x, v.y = x, y
                vs1, vs2 = _massstab(va["massstab"]) if va.get("massstab") else (s1, s2)
                v.Scale = vs1 / vs2
                gb = v.GenerativeBehavior()
                gb.Document = part_doc.Part()
                gb.DefineFrontView(*richtungen[va.get("richtung", "vorne")])
                gb.Update()
                prot.ok("Ansicht", vid)
            except Exception as ex:
                prot.fehler("Ansicht", f"{vid}: {ex}")
        try:
            hintergrund = sheet.Views().Item(2)  # Hintergrundansicht (Schriftfeld)
            texte = hintergrund.Texts()
            for n in auftrag.get("hinweise", []):
                x, y = n.get("pos", [25, 70])
                texte.Add("\n".join(n["text"]) if isinstance(n["text"], list) else n["text"], x, y)
            prot.ok("Hinweise", f"{len(auftrag.get('hinweise', []))} Block/Blöcke")
        except Exception as ex:
            prot.fehler("Hinweise", str(ex))
        for k, v in auftrag.get("eigenschaften", {}).items():
            try:
                drw.Parameters().CreateString(k, str(v))
            except Exception as ex:
                prot.fehler("Eigenschaft", f"{k}: {ex}")

        aus = auftrag.get("ausgabe") or {}
        if isinstance(aus, str):
            aus = {"name": aus}
        ordner = _pfad(aus.get("ordner", os.path.dirname(teil)), basis)
        name = aus.get("name") or auftrag.get("eigenschaften", {}).get("Zeichnungsnummer") \
            or os.path.splitext(os.path.basename(teil))[0]
        ziel = os.path.join(ordner, name + ".CATDrawing")
        liste_md = os.path.join(ordner, name + "-Eintrageliste.md")
        self._eintrageliste(auftrag, modell, liste_md)
        prot.fehler("Maße/Toleranzen", f"in CATIA V5 nicht per API setzbar – Eintrageliste: {liste_md}")
        try:
            drw.SaveAs(ziel)
            prot.ok("Speichern", ziel)
            if aus.get("pdf", True):
                drw.ExportData(os.path.splitext(ziel)[0] + ".pdf", "pdf")
                prot.ok("PDF", os.path.splitext(ziel)[0] + ".pdf")
        except Exception as ex:
            prot.fehler("Speichern", str(ex))
        return prot.ergebnis(ziel)

    @staticmethod
    def _eintrageliste(auftrag, modell, pfad):
        fl = {f["id"]: f for f in modell["flaechen"]}

        def beschreibung(fid):
            f = fl.get(fid, {})
            if f.get("typ") == "zylinder":
                return f"Zylinder ⌀{f['d']:g} ({fid}, axial {f['bereich'][0]:g}…{f['bereich'][1]:g})"
            if f.get("typ") == "ebene":
                return f"Ebene {f.get('normale_achse', '')} bei {f.get('lage', 0):g} ({fid})"
            return fid

        z = [f"# Eintrageliste {auftrag.get('eigenschaften', {}).get('Zeichnungsnummer', '')}", "",
             "Im Drafting-Workbench eintragen. Reihenfolge: Maße → Bezüge → Toleranzrahmen → Oberflächen.", "",
             "## Maße", "", "| Nr | Ansicht | Art | Element(e) | Eintragung |", "|---|---|---|---|---|"]
        for i, m in enumerate(auftrag.get("masse", []), 1):
            el = beschreibung(m["flaeche"]) if m.get("flaeche") else \
                f"{beschreibung(m.get('von'))} → {beschreibung(m.get('bis'))}"
            if m.get("text"):
                text = m["text"]
            elif m.get("typ") == "durchmesser":
                text = f"⌀{fl.get(m['flaeche'], {}).get('d', '?'):g} {m.get('tol') or ''}".strip()
            else:
                text = m.get("tol") or "(Allgemeintoleranz)"
            if m.get("ted"):
                text += " (theoretisch genau, eingerahmt)"
            z.append(f"| {m.get('id', i)} | {m.get('ansicht', '')} | {m.get('typ', 'abstand')} | {el} | {text} |")
        z += ["", "## Bezüge", "", "| Buchstabe | an |", "|---|---|"]
        for d in auftrag.get("bezuege", []):
            z.append(f"| {d['buchstabe']} | {d.get('an') or beschreibung(d.get('flaeche'))} |")
        z += ["", "## Toleranzrahmen", "", "| Rahmen | an |", "|---|---|"]
        for g in auftrag.get("rahmen", []):
            zellen = g["zellen"] if isinstance(g["zellen"][0], list) else [g["zellen"]]
            z.append(f"| {' / '.join('|' + '|'.join(map(str, r)) + '|' for r in zellen)} | "
                     f"{g.get('an') or beschreibung(g.get('flaeche'))} |")
        z += ["", "## Oberflächen", ""]
        for s in auftrag.get("oberflaechen", []):
            z.append(f"- {s['text']} an {beschreibung(s.get('flaeche'))}")
        os.makedirs(os.path.dirname(pfad), exist_ok=True)
        with open(pfad, "w", encoding="utf-8") as f:
            f.write("\n".join(z) + "\n")

    def exportieren(self, pfad, formate=("pdf",)):
        doc = self.oeffnen(pfad)
        aus = []
        for f in formate:
            ziel = os.path.splitext(os.path.abspath(pfad))[0] + "." + f
            doc.ExportData(ziel, f)
            aus.append(ziel)
        return aus
