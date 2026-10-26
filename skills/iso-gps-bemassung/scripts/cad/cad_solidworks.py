"""SolidWorks-Adapter (COM-API, getestet mit SolidWorks 2026 deutsch).

Alle Längen der SolidWorks-API sind in Metern; nach außen wird in mm gearbeitet.
"""
import math
import os
import re
import winreg

import pythoncom
import win32com.client
from win32com.client import VARIANT

from cad_basis import (MM, Adapter, CadFehler, M, O, achsname, b64, dot, liste, norm, roh, runde, unb64,
                       zusammenfassen)

DOC_PART, DOC_ASM, DOC_DRW = 1, 2, 3
VIEW_EDGE, VIEW_SILHOUETTE = 1, 4
TOL = {"keine": 0, "basis": 1, "bilateral": 2, "grenzmass": 3, "symmetrisch": 4, "passung": 7,
       "passung_mit_abmassen": 8, "nur_abmasse": 9}
GTOL_SYM = {
    "geradheit": "<IGTOL-STRAIGHT>", "ebenheit": "<IGTOL-FLAT>", "rundheit": "<IGTOL-CIRC>",
    "zylinderform": "<IGTOL-CYL>", "linienprofil": "<IGTOL-LPROF>", "flaechenprofil": "<IGTOL-SPROF>",
    "parallelitaet": "<IGTOL-PARA>", "rechtwinkligkeit": "<IGTOL-PERP>", "neigung": "<IGTOL-ANGULAR>",
    "position": "<IGTOL-POSI>", "koaxialitaet": "<IGTOL-CONC>", "symmetrie": "<IGTOL-SYMMETRY>",
    "lauf": "<IGTOL-SRUN>", "gesamtlauf": "<IGTOL-TRUN>",
}
# Sonderzeichen im Text -> SolidWorks-Symbolcodes
SYM_TEXT = [("⌀", "<MOD-DIAM>"), ("{D}", "<MOD-DIAM>"), ("Ⓜ", "<MOD-MMC>"), ("{M}", "<MOD-MMC>"),
            ("Ⓛ", "<MOD-LMC>"), ("{L}", "<MOD-LMC>"), ("Ⓟ", "<MOD-PTZ>"), ("{P}", "<MOD-PTZ>"),
            ("Ⓔ", "<MOD-EP>"), ("{E}", "<MOD-EP>"), ("Ⓕ", "<MOD-FREES>"), ("{F}", "<MOD-FREES>"),
            ("Ⓣ", "<MOD-TANP>"), ("{T}", "<MOD-TANP>"), ("□", "<MOD-BOX>"), ("{SQ}", "<MOD-BOX>"),
            ("⌴", "<HOLE-SPOT>"), ("{CB}", "<HOLE-SPOT>"), ("⌵", "<HOLE-SINK>"), ("{CS}", "<HOLE-SINK>"),
            ("↧", "<HOLE-DEPTH>"), ("{DP}", "<HOLE-DEPTH>"), ("±", "<MOD-PM>"), ("°", "<MOD-DEG>")]
VIEW_NAMES = {  # Normansicht -> mögliche Namen (englisch/deutsch)
    "vorne": ["*Front", "*Vorderseite", "*Vorne"], "hinten": ["*Back", "*Rückseite", "*Hinten"],
    "oben": ["*Top", "*Oben", "*Draufsicht"], "unten": ["*Bottom", "*Unten", "*Unterseite"],
    "links": ["*Left", "*Links"], "rechts": ["*Right", "*Rechts"],
    "iso": ["*Isometric", "*Isometrisch"],
}
PAPER = {"A4H": (5, 0.210, 0.297), "A4": (5, 0.210, 0.297), "A3": (8, 0.420, 0.297), "A2": (9, 0.594, 0.420),
         "A1": (10, 0.841, 0.594), "A0": (11, 1.189, 0.841)}


def sw_text(s):
    s = str(s)
    for a, b in SYM_TEXT:
        s = s.replace(a, b)
    return s


def byref_int():
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)


class SolidWorks(Adapter):
    name = "solidworks"
    getestet = True
    endung_teil = ".SLDPRT"

    @classmethod
    def verfuegbar(cls):
        try:
            winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "SldWorks.Application").Close()
        except OSError:
            return False, False, "nicht installiert"
        laeuft = False
        try:
            win32com.client.GetActiveObject("SldWorks.Application")
            laeuft = True
        except Exception:
            pass
        return True, laeuft, "COM SldWorks.Application"

    # ------------------------------------------------------------------ Verbindung
    def verbinden(self, sichtbar=True):
        pythoncom.CoInitialize()
        self.sw = O(win32com.client.Dispatch("SldWorks.Application"))
        self.sw.Visible = sichtbar
        self.mu = self.sw.GetMathUtility()
        self.version = self.sw.RevisionNumber()
        return self.version

    def schliessen(self):
        self.sw.CloseAllDocuments(True)

    def oeffnen(self, pfad):
        pfad = os.path.abspath(pfad)
        ext = os.path.splitext(pfad)[1].lower()
        typ = {".sldprt": DOC_PART, ".sldasm": DOC_ASM, ".slddrw": DOC_DRW}.get(ext)
        if typ is None:
            raise CadFehler(f"Dateityp {ext} wird von SolidWorks nicht direkt geöffnet")
        if not os.path.exists(pfad):
            raise CadFehler(f"Datei nicht gefunden: {pfad}")
        err, warn = byref_int(), byref_int()
        doc = self.sw.OpenDoc6(pfad, typ, 1, "", err, warn)
        if doc is None:
            raise CadFehler(f"SolidWorks konnte {pfad} nicht öffnen (Fehlercode {err.value})")
        self.sw.ActivateDoc3(M(doc, "GetTitle"), False, 0, byref_int())
        return doc

    # ------------------------------------------------------------------ Testteil
    def testteil(self, pfad):
        """Welle aus beispiele/welle.json als Rotationsteil (Achse = X)."""
        part = self.sw.NewDocument(self.sw.GetUserPreferenceStringValue(8), 0, 0, 0)
        if part is None:
            raise CadFehler("Neues Teil konnte nicht angelegt werden (Teilevorlage prüfen)")
        planes = []
        f = M(part, "FirstFeature")
        while f is not None:
            if M(f, "GetTypeName2") == "RefPlane":
                planes.append(f)
            f = M(f, "GetNextFeature")
        planes[0].Select2(False, 0)
        sm = M(part, "SketchManager")
        sm.InsertSketch(True)
        sm.AddToDB = True
        prof = [(0, 0), (0, 9), (1, 10), (20, 10), (20, 12.5), (40, 12.5), (40, 16), (120, 16), (120, 12.5),
                (140, 12.5), (140, 8), (159, 8), (160, 7), (160, 0), (0, 0)]
        for (x1, y1), (x2, y2) in zip(prof, prof[1:]):
            sm.CreateLine(x1 / MM, y1 / MM, 0, x2 / MM, y2 / MM, 0)
        sm.CreateCenterLine(-5 / MM, 0, 0, 165 / MM, 0, 0)
        sm.AddToDB = False
        sm.InsertSketch(True)
        feat = M(part, "FeatureManager").FeatureRevolve2(True, True, False, False, False, False, 0, 0,
                                                          2 * math.pi, 0, False, False, 0, 0, 0, 0, 0,
                                                          True, True, True)
        if feat is None:
            raise CadFehler("Rotation fehlgeschlagen")
        feat.Name = "Welle"
        cpm = M(part, "Extension").CustomPropertyManager("")
        for k, v in (("Benennung", "Antriebswelle"), ("Zeichnungsnummer", "MF-1001-01"),
                     ("Werkstoff", "C45+N (1.0503)"), ("Ersteller", "N. N.")):
            cpm.Add3(k, 30, v, 2)
        os.makedirs(os.path.dirname(os.path.abspath(pfad)), exist_ok=True)
        part.SaveAs3(os.path.abspath(pfad), 0, 1)
        return os.path.abspath(pfad)

    # ------------------------------------------------------------------ Analyse
    def analysieren(self, pfad):
        doc = self.oeffnen(pfad)
        if M(doc, "GetType") != DOC_PART:
            raise CadFehler("Analyse ist für Einzelteile (.SLDPRT) ausgelegt")
        ext = M(doc, "Extension")
        bodies = liste(doc.GetBodies2(0, True))
        if not bodies:
            raise CadFehler("Teil enthält keinen Volumenkörper")
        flaechen = []
        n = 0
        for bi, body in enumerate(bodies):
            for face in liste(M(body, "GetFaces")):
                n += 1
                flaechen.append(self._flaeche(ext, face, f"F{n}", bi))
        feats = []
        f = M(doc, "FirstFeature")
        while f is not None:
            t = M(f, "GetTypeName2")
            if t not in ("RefPlane", "OriginProfileFeature", "MaterialFolder", "SensorFolder", "DocsFolder",
                         "DetailCabinet", "SurfaceBodyFolder", "SolidBodyFolder", "CommentsFolder",
                         "HistoryFolder", "EnvFolder", "InkMarkupFolder", "EqnFolder", "SelectionSetFolder",
                         "FavoriteFolder", "AmbientLight", "DirectionLight", "MBD3DPMI", "BlockFolder",
                         "DimXpertManager", "MateReferenceGroupFolder"):
                feats.append({"name": f.Name(), "typ": t})
            f = M(f, "GetNextFeature")
        mp = M(ext, "CreateMassProperty")
        props = {}
        try:
            cpm = ext.CustomPropertyManager("")
            for k in liste(M(cpm, "GetNames")):
                props[k] = cpm.Get(k)
        except Exception:
            pass
        box = liste(doc.GetPartBox(True)) if hasattr(doc, "GetPartBox") else []
        modell = {
            "cad": "solidworks",
            "datei": os.path.abspath(pfad),
            "einheit": "mm",
            "werkstoff": self._werkstoff(doc),
            "masse_kg": runde(mp.Mass(), 4) if mp else None,
            "volumen_mm3": runde(mp.Volume() * 1e9, 1) if mp else None,
            "huelle_mm": runde([v * MM for v in box], 3) if box else None,
            "eigenschaften": props,
            "features": feats,
            "flaechen": flaechen,
        }
        modell["merkmale"] = zusammenfassen(flaechen)
        self._flaechen_cache = {f["id"]: f for f in flaechen}
        return modell

    def _werkstoff(self, doc):
        try:
            v = M(doc, "MaterialIdName")
            return v.split("|")[1] if v and "|" in v else (v or None)
        except Exception:
            return None

    def _flaeche(self, ext, face, fid, body_index):
        surf = M(face, "GetSurface")
        box = [v * MM for v in liste(M(face, "GetBox"))]
        rec = {"id": fid, "koerper": body_index, "flaeche_mm2": runde(M(face, "GetArea") * 1e6, 2),
               "kanten": M(face, "GetEdgeCount"), "box": runde(box, 3)}
        if M(surf, "IsPlane"):
            p = liste(M(surf, "PlaneParams"))
            nrm = norm(liste(M(face, "Normal")))  # zeigt aus dem Material heraus
            pt = [v * MM for v in p[3:6]]
            rec.update(typ="ebene", normale=runde(nrm, 6), lage=runde(dot(pt, nrm), 4))
            ax = achsname(nrm)
            if ax:
                rec["normale_achse"] = ax
                rec[ax[1].lower()] = runde(pt["XYZ".index(ax[1])], 4)
        elif M(surf, "IsCylinder"):
            c = liste(M(surf, "CylinderParams"))
            a, o = self._achse(c[0:3], c[3:6])
            rec.update(typ="zylinder", art=self._art(face, o, a), d=runde(2 * c[6] * MM, 4),
                       achse={"punkt": runde(o, 4), "richtung": runde(a, 6)})
            rec["bereich"] = self._axialbereich(box, o, a)
            ax = achsname(a)
            if ax:
                rec["achse"]["name"] = ax[1]
        elif M(surf, "IsCone"):
            c = liste(M(surf, "ConeParams"))
            a, o = self._achse(c[0:3], c[3:6])
            rec.update(typ="kegel", art=self._art(face, o, a), halber_winkel_grad=runde(math.degrees(c[7]), 4),
                       achse={"punkt": runde(o, 4), "richtung": runde(a, 6)})
            rec["bereich"] = self._axialbereich(box, o, a)
        elif M(surf, "IsSphere"):
            s = liste(M(surf, "SphereParams"))
            rec.update(typ="kugel", mitte=runde([v * MM for v in s[0:3]], 4), d=runde(2 * s[3] * MM, 4))
        elif M(surf, "IsTorus"):
            t = liste(M(surf, "TorusParams"))
            rec.update(typ="torus", mitte=runde([v * MM for v in t[0:3]], 4), achse=runde(norm(t[3:6]), 6),
                       r_gross=runde(t[6] * MM, 4), r_klein=runde(t[7] * MM, 4))
        else:
            rec["typ"] = "freiform"
        try:
            rec["ref"] = b64(ext.GetPersistReference3(face))
        except Exception:
            rec["ref"] = None
        return rec

    @staticmethod
    def _achse(o_m, a_raw):
        """Achse einheitlich ausrichten (größte Komponente positiv), Punkt = Lotfußpunkt zum Ursprung, mm."""
        a = norm(a_raw)
        i = max(range(3), key=lambda k: abs(a[k]))
        if a[i] < 0:
            a = [-x for x in a]
        o = [v * MM for v in o_m]
        t = dot(o, a)
        return a, [o[k] - t * a[k] for k in range(3)]

    @staticmethod
    def _art(face, o, a):
        """'aussen' (Welle, Bund) oder 'innen' (Bohrung) aus Tessellationspunkt und -normale."""
        pts = liste(M(face, "GetTessTriangles", True))
        nrm = liste(M(face, "GetTessNorms"))
        if len(pts) < 3 or len(nrm) < 3:
            return "unbekannt"
        p = [pts[k] * MM - o[k] for k in range(3)]
        t = dot(p, a)
        radial = [p[k] - t * a[k] for k in range(3)]
        return "aussen" if dot(radial, nrm[0:3]) > 0 else "innen"

    @staticmethod
    def _axialbereich(box, o, a):
        xs = [box[0], box[3]]
        ys = [box[1], box[4]]
        zs = [box[2], box[5]]
        ts = [dot([x - o[0], y - o[1], z - o[2]], a) for x in xs for y in ys for z in zs]
        return runde([min(ts), max(ts)], 3)

    def flaeche_aus_ref(self, doc, ref):
        err = byref_int()
        pid = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_UI1, unb64(ref))
        obj = M(doc, "Extension").GetObjectByPersistReference3(pid, err)
        if obj is None:
            raise CadFehler(f"Fläche nicht mehr auffindbar (Code {err.value}) – Teil neu analysieren")
        return obj

    # ------------------------------------------------------------------ Zeichnung
    def zeichnen(self, auftrag, basis="."):
        """Erzeugt aus einem Zeichnungsauftrag eine SolidWorks-Zeichnung (.SLDDRW + PDF)."""
        prot = Protokoll()
        teil = _pfad(auftrag["teil"], basis)
        modell = self.analysieren(teil)
        self.fl = {f["id"]: f for f in modell["flaechen"]}
        part = self.oeffnen(teil)
        b = auftrag.get("blatt", {})
        fmt = str(b.get("format", "A3")).upper()
        if fmt not in PAPER:
            raise CadFehler(f"Blattformat {fmt} unbekannt ({', '.join(PAPER)})")
        paper, W, H = PAPER[fmt]
        s1, s2 = _massstab(b.get("massstab", "1:1"))
        vorlage = _pfad(b["vorlage"], basis) if b.get("vorlage") else self.sw.GetUserPreferenceStringValue(10)
        drw = self.sw.NewDocument(vorlage, paper, W, H)
        if drw is None:
            raise CadFehler(f"Zeichnung konnte nicht angelegt werden (Vorlage {vorlage})")
        self.drw = drw
        blattformat = _pfad(b["blattformat"], basis) if b.get("blattformat") else self._standard_blattformat(fmt)
        sheet = drw.GetCurrentSheet()
        drw.SetupSheet6(sheet.GetName(), paper, 12, s1, s2, True, blattformat or "", W, H, "Standard", True,
                        0, 0, 0, 0, 0, 0)
        sheet.SetProperties2(paper, 12, s1, s2, True, W, H, True)
        prot.ok("Blatt", f"{fmt}, {s1}:{s2}, Format {os.path.basename(blattformat or '(Vorlage)')}")

        # Ansichten
        self.ansichten = {}
        for va in auftrag.get("ansichten", []):
            vid = va.get("id", va.get("richtung", "vorne"))
            name = self._modellansicht(part, va.get("richtung", "vorne"))
            x, y = va.get("pos", [W * MM / 2, H * MM / 2])
            v = drw.CreateDrawViewFromModelView3(teil, name, x / MM, y / MM, 0)
            if v is None:
                prot.fehler("Ansicht", f"{vid}: '{name}' konnte nicht erzeugt werden")
                continue
            vs1, vs2 = _massstab(va["massstab"]) if va.get("massstab") else (s1, s2)
            v.ScaleDecimal = vs1 / vs2
            self.ansichten[vid] = _Ansicht(v)
            prot.ok("Ansicht", f"{vid}: {name} bei {x:.0f}/{y:.0f} mm, {vs1}:{vs2}")
        sheet.SetProperties2(paper, 12, s1, s2, True, W, H, True)  # Ansichten setzen den Blattmaßstab zurück
        drw.EditRebuild3()
        for a in self.ansichten.values():
            a.aktualisieren()

        if auftrag.get("mittellinien", "auto") == "auto":
            self._mittellinien(modell, prot)

        self.masse = {}
        self.ersatztexte = []
        for m in auftrag.get("masse", []):
            self._schritt(prot, "Maß", m, self._mass)
        for d in auftrag.get("bezuege", []):
            self._schritt(prot, "Bezug", d, self._bezug)
        for g in auftrag.get("rahmen", []):
            self._schritt(prot, "Toleranzrahmen", g, self._rahmen)
        for s in auftrag.get("oberflaechen", []):
            self._schritt(prot, "Oberfläche", s, self._oberflaeche)
        for n in auftrag.get("hinweise", []):
            self._schritt(prot, "Hinweis", n, self._hinweis)

        self._eigenschaften(part, drw, auftrag.get("eigenschaften", {}), modell, prot)
        drw.ClearSelection2(True)
        drw.ForceRebuild3(False)
        for dd, text in self.ersatztexte:  # SolidWorks ergänzt bei Durchmessern beim Neuaufbau wieder ⌀
            dd.SetText(1, text)
        drw.EditRebuild3()

        # Speichern
        aus = auftrag.get("ausgabe") or {}
        if isinstance(aus, str):
            aus = {"name": aus}
        ordner = _pfad(aus.get("ordner", os.path.dirname(teil)), basis)
        name = aus.get("name") or auftrag.get("eigenschaften", {}).get("Zeichnungsnummer") \
            or os.path.splitext(os.path.basename(teil))[0]
        os.makedirs(ordner, exist_ok=True)
        ziel = os.path.join(ordner, name + ".SLDDRW")
        if len(ziel) > 250:
            raise CadFehler(f"Pfad zu lang für SolidWorks ({len(ziel)} Zeichen): {ziel}")
        err, warn = byref_int(), byref_int()
        ok = drw.Extension().SaveAs3(ziel, 0, 1, NUL(), NUL(), err, warn)
        prot.eintrag("Speichern", ok, ziel if ok else f"Fehlercode {err.value}")
        if aus.get("pdf", True):
            pdf = os.path.splitext(ziel)[0] + ".pdf"
            err = byref_int()
            ok = drw.Extension().SaveAs3(pdf, 0, 1, self.sw.GetExportFileData(1), NUL(), err, byref_int())
            prot.eintrag("PDF", ok, pdf if ok else f"Fehlercode {err.value}")
        if aus.get("dxf"):
            dxf = os.path.splitext(ziel)[0] + ".dxf"
            err = byref_int()
            ok = drw.Extension().SaveAs3(dxf, 0, 1, NUL(), NUL(), err, byref_int())
            prot.eintrag("DXF", ok, dxf if ok else f"Fehlercode {err.value}")
        return prot.ergebnis(ziel)

    def exportieren(self, pfad, formate=("pdf",)):
        """Vorhandene Zeichnung öffnen und als PDF/DXF ausgeben (z. B. für /zeichnung-pruefen)."""
        drw = self.oeffnen(pfad)
        if drw.GetType() != DOC_DRW:
            raise CadFehler("Export ist für Zeichnungen (.SLDDRW) gedacht")
        aus = []
        for f in formate:
            ziel = os.path.splitext(os.path.abspath(pfad))[0] + "." + f
            daten = self.sw.GetExportFileData(1) if f == "pdf" else NUL()
            err = byref_int()
            if drw.Extension().SaveAs3(ziel, 0, 1 | 2, daten, NUL(), err, byref_int()):
                aus.append(ziel)
            else:
                raise CadFehler(f"Export {f} fehlgeschlagen (Code {err.value})")
        return aus

    # ---- Hilfen Zeichnung
    def _schritt(self, prot, art, spec, fn):
        try:
            info = fn(spec)
            prot.ok(art, info)
        except Exception as ex:  # einzelne Angaben dürfen scheitern, der Rest läuft weiter
            prot.fehler(art, f"{spec.get('id') or spec.get('zellen') or spec.get('text') or spec}: {ex}")
        finally:
            self.drw.ClearSelection2(True)

    def _standard_blattformat(self, fmt):
        tmpl = self.sw.GetUserPreferenceStringValue(10)
        base = os.path.dirname(os.path.dirname(tmpl)) if tmpl else ""
        sprachen = []
        try:
            sprachen.append(self.sw.GetCurrentLanguage())
        except Exception:
            pass
        sprachen += ["german", "english"]
        name = {"A4H": "a4 - iso", "A4": "a4 - iso"}.get(fmt, f"{fmt.lower()} - iso")
        for sp in sprachen:
            p = os.path.join(base, "lang", sp, "sheetformat", name + ".slddrt")
            if os.path.exists(p):
                return p
        return None

    def _modellansicht(self, part, richtung):
        vorhanden = liste(part.GetModelViewNames())
        if richtung in vorhanden:
            return richtung
        if f"Plan {richtung}" in vorhanden:  # Teil aus dem Bauplan: Ansichten mit Z oben wie in FreeCAD
            return f"Plan {richtung}"
        for n in VIEW_NAMES.get(str(richtung).lower(), [richtung]):
            if n in vorhanden:
                return n
        raise CadFehler(f"Ansicht '{richtung}' nicht gefunden (vorhanden: {', '.join(vorhanden)})")

    def _ansicht(self, spec):
        vid = spec.get("ansicht") or next(iter(self.ansichten))
        if vid not in self.ansichten:
            raise CadFehler(f"Ansicht '{vid}' existiert nicht")
        a = self.ansichten[vid]
        self.drw.ActivateView(a.name)
        return a

    def _f(self, fid):
        if fid not in self.fl:
            raise CadFehler(f"Fläche {fid} nicht in der Analyse")
        return self.fl[fid]

    def _waehle(self, punkt, typen, anhaengen=False):
        sm = self.drw.SelectionManager()
        vorher = sm.GetSelectedObjectCount2(-1) if anhaengen else 0
        # SolidWorks trifft Konturen je nach Lage nur mit bestimmtem Typ oder knapp neben der Linie
        erlaubt = {SEL_TYP[t] for t in typen if t in SEL_TYP}
        d = 0.0003
        for typ in list(typen) + [""]:
            for dx, dy in ((0, 0), (0, -d), (0, d), (-d, 0), (d, 0)):
                if not self.drw.Extension().SelectByID2("", typ, punkt[0] + dx, punkt[1] + dy, 0, anhaengen, 0,
                                                        NUL(), 0):
                    continue
                n = sm.GetSelectedObjectCount2(-1)
                if n > vorher and sm.GetSelectedObjectType3(n, -1) in erlaubt:
                    return typ
                if n > vorher:  # falsches Element erwischt: wieder abwählen
                    sm.DeSelect2(n, -1)
        raise CadFehler(f"an Blattpunkt {punkt[0] * MM:.1f}/{punkt[1] * MM:.1f} mm nichts auswählbar")

    def _anhaengepunkt(self, a, spec):
        """Blattpunkt (m) auf der sichtbaren Kontur der Fläche und passende Auswahltypen."""
        if spec.get("punkt"):
            return a.p(spec["punkt"]), ["EDGE", "SILHOUETTE", "FACE"]
        f = self._f(spec["flaeche"])
        if f["typ"] in ("zylinder", "kegel"):
            oben, unten, seitlich = a.zylinderpunkte(f, spec.get("bei"))
            if not seitlich:
                return oben, ["EDGE"]
            return (unten if spec.get("seite") == "unten" else oben), ["SILHOUETTE", "EDGE"]
        if f["typ"] == "ebene":
            p, kante = a.ebenenpunkt(f, spec.get("anteil", 0.8))
            return p, (["EDGE", "SILHOUETTE"] if kante else ["FACE"])
        return a.p(_mitte(f["box"])), ["EDGE", "FACE", "SILHOUETTE"]

    def _lage(self, a, anker, spec, standard):
        """Position einer Beschriftung in m: 'pos' absolut (mm) oder 'versatz' [dx, dy] mm zum Anker."""
        if spec.get("pos"):
            return [spec["pos"][0] / MM, spec["pos"][1] / MM]
        dx, dy = spec.get("versatz", standard)
        return [anker[0] + dx / MM, anker[1] + dy / MM]

    def _mass(self, m):
        a = self._ansicht(m)
        typ = m.get("typ", "abstand")
        if typ == "abstand":
            pa, ta = self._anhaengepunkt(a, {"flaeche": m["von"]} if "von" in m else {"punkt": m["punkt_a"]})
            pb, tb = self._anhaengepunkt(a, {"flaeche": m["bis"]} if "bis" in m else {"punkt": m["punkt_b"]})
            self._waehle(pa, ta)
            self._waehle(pb, tb, True)
            ol = a.outline()
            if m.get("pos"):
                loc = [m["pos"][0] / MM, m["pos"][1] / MM]
            else:
                seite, ab = m.get("lage", "unten"), m.get("abstand", 12) / MM
                mx, my = (pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2
                loc = {"unten": [mx, ol[1] - ab], "oben": [mx, ol[3] + ab],
                       "links": [ol[0] - ab, my], "rechts": [ol[2] + ab, my]}[seite]
            dd = self.drw.AddDimension2(loc[0], loc[1], 0)
        elif typ == "durchmesser":
            f = self._f(m["flaeche"])
            oben, unten, seitlich = a.zylinderpunkte(f, m.get("bei"))
            if seitlich:
                self._waehle(oben, ["SILHOUETTE", "EDGE"])
                self._waehle(unten, ["SILHOUETTE", "EDGE"], True)
                verschiebung = m.get("textpos", f["d"] * 0.3)
                mitte = [(oben[0] + unten[0]) / 2, (oben[1] + unten[1]) / 2]
                rich = a.richtung(f["achse"]["richtung"])
                quer = [-rich[1], rich[0]]
                loc = [mitte[0] + quer[0] * verschiebung / MM * a.s, mitte[1] + quer[1] * verschiebung / MM * a.s]
                if m.get("pos"):
                    loc = [m["pos"][0] / MM, m["pos"][1] / MM]
            else:
                self._waehle(oben, ["EDGE"])
                loc = self._lage(a, oben, m, [12, 12])
            dd = self.drw.AddDimension2(loc[0], loc[1], 0)
            if dd is not None and not m.get("text") and "<MOD-DIAM>" not in (dd.GetText(1) or ""):
                dd.SetText(1, "<MOD-DIAM>" + (dd.GetText(1) or ""))
        elif typ == "punkte":
            self._waehle(a.p(m["a"]), m.get("auswahl", ["EDGE", "SILHOUETTE"]))
            self._waehle(a.p(m["b"]), m.get("auswahl", ["EDGE", "SILHOUETTE"]), True)
            dd = self.drw.AddDimension2(m["pos"][0] / MM, m["pos"][1] / MM, 0)
        elif typ in ("radius", "kante"):
            self._waehle(a.p(m["punkt"]), ["EDGE", "SILHOUETTE"])
            dd = self.drw.AddDimension2(m["pos"][0] / MM, m["pos"][1] / MM, 0)
        else:
            raise CadFehler(f"Maßtyp '{typ}' unbekannt")
        if dd is None:
            raise CadFehler("SolidWorks hat kein Maß erzeugt (Auswahl prüfen)")
        wert = dd.GetDimension2(0).GetSystemValue2("") * MM
        self._toleranz(dd, m, wert)
        if m.get("id"):
            self.masse[m["id"]] = (dd, a, m)
        return f"{m.get('id', typ)} = {_zahl(wert)} mm"

    def _toleranz(self, dd, m, wert):
        dim = dd.GetDimension2(0)
        tol = dim.Tolerance()
        nks = _nachkomma(wert)
        tnks = -1
        t = m.get("tol")
        if m.get("ted"):
            tol.Type = TOL["basis"]
        elif isinstance(t, dict) or (isinstance(t, str) and "/" in t and re.match(r"^\s*[+\-−]", t)):
            o, u = (t["oben"], t["unten"]) if isinstance(t, dict) else [x.strip() for x in t.split("/", 1)]
            tol.Type = TOL["bilateral"]
            tol.SetValues(_wert(u) / MM, _wert(o) / MM)
            tnks = max(_nk_text(o), _nk_text(u))
        elif isinstance(t, str) and t.strip().startswith(("±", "+-")):
            x = _wert(t.strip().lstrip("±+-"))
            tol.Type = TOL["symmetrisch"]
            tol.SetValues(-x / MM, x / MM)
            tnks = _nk_text(t)
        elif isinstance(t, str) and re.match(r"^[A-Za-z]{1,2}\d{1,2}$", t.strip()):
            feld = t.strip()
            tol.Type = TOL["passung_mit_abmassen"] if m.get("abmasse", True) else TOL["passung"]
            if feld[0].isupper():
                tol.SetFitValues(feld, "")
            else:
                tol.SetFitValues("", feld)
            tnks = 3
        elif t:
            raise CadFehler(f"Toleranzangabe '{t}' nicht erkannt")
        dd.SetPrecision3(nks, -1, tnks, -1)
        if m.get("hilfsmass"):
            dd.ShowParenthesis = True
        if m.get("text"):  # vollständiger Ersatztext, z. B. "M16" oder "M16×1,5"
            dd.ShowDimensionValue = False
            dd.SetText(1, sw_text(m["text"]))
            self.ersatztexte.append((dd, sw_text(m["text"])))
        elif m.get("vor"):
            dd.SetText(1, sw_text(m["vor"]) + (dd.GetText(1) or ""))
        if m.get("nach"):
            dd.SetText(2, (dd.GetText(2) or "") + " " + sw_text(m["nach"]))

    def _anhaengen(self, spec):
        """Wählt Maß ('an') oder Fläche/Punkt; gibt Ansicht und Ankerpunkt (m) zurück."""
        if spec.get("an"):
            if spec["an"] not in self.masse:
                raise CadFehler(f"Maß '{spec['an']}' nicht vorhanden")
            dd, a, m = self.masse[spec["an"]]
            self.drw.ActivateView(a.name)
            sd = self.drw.SelectionManager().CreateSelectData()
            if not dd.GetAnnotation().Select3(False, sd):
                raise CadFehler("Maß ließ sich nicht auswählen")
            if m.get("typ") == "durchmesser":
                oben, unten, _ = a.zylinderpunkte(self._f(m["flaeche"]), m.get("bei"))
                return a, oben
            pos = liste(dd.GetAnnotation().GetPosition())
            return a, pos[0:2]
        a = self._ansicht(spec)
        p, typen = self._anhaengepunkt(a, spec)
        self._waehle(p, typen)
        return a, p

    def _bezug(self, d):
        if d.get("an") and d["an"] in self.masse and self.masse[d["an"]][2].get("typ") == "durchmesser":
            # Achsbezug: Bezugsdreieck auf der Kontur in Verlängerung der Maßlinie (ISO 5459).
            # SolidWorks hängt Bezugssymbole per API nicht an Maße; diese Darstellung ist gleichwertig.
            _, a, m = self.masse[d["an"]]
            self.drw.ActivateView(a.name)
            oben, unten, _ = a.zylinderpunkte(self._f(m["flaeche"]), m.get("bei"))
            anker = unten if d.get("seite") == "unten" else oben
            self._waehle(anker, ["SILHOUETTE", "EDGE"])
            standard = [0, -12] if d.get("seite") == "unten" else [0, 12]
        else:
            a, anker = self._anhaengen(d)
            standard = [0, 12]
        dt = self.drw.InsertDatumTag2()
        if dt is None:
            raise CadFehler("Bezugssymbol nicht eingefügt")
        dt.SetLabel(d["buchstabe"])
        an = dt.GetAnnotation()
        pos = self._lage(a, anker, d, standard)
        an.SetPosition2(pos[0], pos[1], 0)
        if an.GetAttachedEntityCount3() == 0:
            raise CadFehler("Bezugssymbol ist nicht angehängt")
        return f"{d['buchstabe']} an {d.get('an') or d.get('flaeche') or d.get('punkt')}"

    def _rahmen(self, g):
        a, anker = self._anhaengen(g)
        gt = self.drw.InsertGtol()
        if gt is None:
            raise CadFehler("Toleranzrahmen nicht eingefügt")
        reihen = g["zellen"] if isinstance(g["zellen"][0], list) else [g["zellen"]]
        for i, z in enumerate(reihen, start=1):
            art = str(z[0]).lower().replace("ä", "ae")
            if art not in GTOL_SYM:
                raise CadFehler(f"Toleranzart '{z[0]}' unbekannt")
            dia, mc, wert = _toleranzzelle(z[1] if len(z) > 1 else "")
            bez = [_bezugszelle(x) for x in (list(z[2:]) + ["", "", ""])[:3]]
            gt.SetFrameSymbols2(i, GTOL_SYM[art], dia, mc, False, "", bez[0][1], bez[1][1], bez[2][1])
            gt.SetFrameValues2(i, wert, "", bez[0][0], bez[1][0], bez[2][0])
        if g.get("darueber"):
            gt.SetText(3, sw_text(g["darueber"]))
        pos = self._lage(a, anker, g, [12, 14])
        gt.SetPosition(pos[0], pos[1], 0)
        return "|".join(str(x) for x in reihen[0])

    def _oberflaeche(self, s):
        a, anker = self._anhaengen(s)
        art = {"abtragen": 1, "beliebig": 0, "ohne": 2}[s.get("art", "abtragen")]
        pos = self._lage(a, anker, s, [10, 12])
        sf = self.drw.Extension().InsertSurfaceFinishSymbol3(art, 2, pos[0], pos[1], 0, 0, 1,
                                                            "", "", sw_text(s.get("verfahren", "")), "", "", "", "")
        if sf is None:
            raise CadFehler("Oberflächensymbol nicht eingefügt")
        sf.SetText(8, sw_text(s["text"]))  # Position a (ISO 1302 / 21920-1)
        return s["text"]

    def _hinweis(self, n):
        self.drw.ActivateSheet(self.drw.GetCurrentSheet().GetName())
        zeilen = n["text"] if isinstance(n.get("text"), list) else [n["text"]]
        note = self.drw.InsertNote(sw_text("\n".join(zeilen)))
        if note is None:
            raise CadFehler("Notiz nicht eingefügt")
        x, y = n.get("pos", [20, 60])
        note.GetAnnotation().SetPosition2(x / MM, y / MM, 0)
        return zeilen[0]

    def _mittellinien(self, modell, prot):
        for vid, a in self.ansichten.items():
            for achse in modell["merkmale"]["achsen"]:
                if abs(dot(achse["richtung"], a.normale())) > 0.1:
                    continue  # Achse zeigt in Blickrichtung: Mittelkreuz statt Mittellinie
                n = 0
                self.drw.ActivateView(a.name)
                self.drw.ClearSelection2(True)
                for fid in achse["flaechen"]:
                    f = self.fl[fid]
                    t = sum(f["bereich"]) / 2
                    p = [f["achse"]["punkt"][k] + t * f["achse"]["richtung"][k] for k in range(3)]
                    if self.drw.Extension().SelectByID2("", "FACE", *a.p(p), 0, True, 0, NUL(), 0):
                        n += 1
                if n and self.drw.InsertCenterLine2() is not None:
                    prot.ok("Mittellinie", f"{vid}: Achse über {n} Flächen")
                self.drw.ClearSelection2(True)

    def _eigenschaften(self, part, drw, eig, modell, prot):
        if not eig:
            return
        werte = dict(eig)
        if werte.get("Masse") == "auto" and modell.get("masse_kg"):
            werte["Masse"] = f"{modell['masse_kg']:.3f} kg".replace(".", ",")
        # Zeichnung: alle Felder ($PRP); Teil nur, was Schriftfelder per $PRPSHEET aus dem Modell lesen.
        # Das Teil wird dabei nicht gespeichert.
        for doc, nur in ((drw, None), (part, TEIL_EIGENSCHAFTEN)):
            cpm = doc.Extension().CustomPropertyManager("")
            for k, v in werte.items():
                if nur is not None and k not in nur:
                    continue
                for name in EIGENSCHAFTEN.get(k, [k]):
                    cpm.Add3(name, 30, str(v), 2)
        prot.ok("Eigenschaften", ", ".join(werte))


class _Ansicht:
    def __init__(self, v):
        self.v = v
        self.name = v.GetName2()
        self.aktualisieren()

    def aktualisieren(self):
        xf = liste(self.v.ModelToViewTransform().ArrayData())
        self.R, self.t, self.s = xf[0:9], xf[9:12], xf[12]

    def p(self, pm):
        """Modellpunkt (mm) -> Blattpunkt (m)."""
        q = [x / MM for x in pm]
        return [sum(q[i] * self.R[i * 3 + j] for i in range(3)) * self.s + self.t[j] for j in range(2)]

    def richtung(self, d):
        v = [sum(d[i] * self.R[i * 3 + j] for i in range(3)) for j in range(2)]
        n = math.hypot(*v) or 1.0
        return [v[0] / n, v[1] / n]

    def normale(self):
        return [self.R[2], self.R[5], self.R[8]]

    def oben(self):
        return [self.R[1], self.R[4], self.R[7]]

    def rechts(self):
        return [self.R[0], self.R[3], self.R[6]]

    def outline(self):
        return liste(self.v.GetOutline())

    def zylinderpunkte(self, f, bei=None):
        a, o = f["achse"]["richtung"], f["achse"]["punkt"]
        r = f.get("d", 2 * f.get("r_basis", 0)) / 2
        t = bei if bei is not None else sum(f["bereich"]) / 2
        z = self.normale()
        if abs(dot(a, z)) > 0.9:  # Blick entlang der Achse
            rr = self.rechts()
            c = [o[k] + t * a[k] for k in range(3)]
            return self.p([c[k] + r * rr[k] for k in range(3)]), self.p(c), False
        u = norm([z[1] * a[2] - z[2] * a[1], z[2] * a[0] - z[0] * a[2], z[0] * a[1] - z[1] * a[0]])
        if dot(u, self.oben()) < -1e-9 or (abs(dot(u, self.oben())) < 1e-9 and dot(u, self.rechts()) < 0):
            u = [-x for x in u]
        c = [o[k] + t * a[k] for k in range(3)]
        return (self.p([c[k] + r * u[k] for k in range(3)]), self.p([c[k] - r * u[k] for k in range(3)]), True)

    def ebenenpunkt(self, f, anteil=0.8):
        """Punkt auf der Projektion einer Ebene; bei Kantenansicht auf der Linie (oberer Bereich)."""
        bx = f["box"]
        ecken = [[x, y, z] for x in (bx[0], bx[3]) for y in (bx[1], bx[4]) for z in (bx[2], bx[5])]
        if abs(dot(f["normale"], self.normale())) > 0.9:
            return self.p(_mitte(bx)), False
        pts = [self.p(e) for e in ecken]
        d = self.richtung(f["normale"])
        entlang = [-d[1], d[0]]
        if entlang[1] < 0 or (abs(entlang[1]) < 1e-9 and entlang[0] < 0):
            entlang = [-entlang[0], -entlang[1]]
        ts = [p[0] * entlang[0] + p[1] * entlang[1] for p in pts]
        p0 = pts[ts.index(min(ts))]
        p1 = pts[ts.index(max(ts))]
        q = [p0[k] + (p1[k] - p0[k]) * anteil for k in range(2)]
        # auf die Linie der Ebene projizieren (Mittel der Normalkomponente)
        nm = sum(p[0] * d[0] + p[1] * d[1] for p in pts) / len(pts)
        cur = q[0] * d[0] + q[1] * d[1]
        return [q[0] + d[0] * (nm - cur), q[1] + d[1] * (nm - cur)], True


class Protokoll:
    def __init__(self):
        self.eintraege = []

    def eintrag(self, art, ok, info):
        self.eintraege.append({"art": art, "ok": bool(ok), "info": info})

    def ok(self, art, info):
        self.eintrag(art, True, info)

    def fehler(self, art, info):
        self.eintrag(art, False, info)

    def ergebnis(self, ziel):
        fehler = [e for e in self.eintraege if not e["ok"]]
        return {"zeichnung": ziel, "fehler": len(fehler), "schritte": self.eintraege}


SEL_TYP = {"EDGE": 1, "FACE": 2, "VERTEX": 3, "SILHOUETTE": 46}
TEIL_EIGENSCHAFTEN = {"Benennung", "Werkstoff", "Oberflaeche"}
EIGENSCHAFTEN = {  # Auftragsschlüssel -> Eigenschaftsnamen, die gängige Schriftfelder verwenden
    "Benennung": ["Description", "Benennung", "Beschreibung"],
    "Zeichnungsnummer": ["PartNo", "Number", "Zeichnungsnummer", "Teilenummer"],
    "Werkstoff": ["Material", "Werkstoff"],
    "Masse": ["Weight", "Gewicht", "Masse"],
    "Gezeichnet": ["DrawnBy", "Gezeichnet", "Ersteller"],
    "Datum": ["DrawnDate", "Datum"],
    "Geprueft": ["CheckedBy", "Geprueft"],
    "Genehmigt": ["EngineeringApproval", "Genehmigt"],
    "Index": ["Revision", "Index"],
    "Eigentuemer": ["COMPANYNAME", "Firma", "Eigentuemer"],
    "Oberflaeche": ["Finish", "Oberflaeche"],
}


def NUL():
    return VARIANT(pythoncom.VT_DISPATCH, None)


def _pfad(p, basis):
    return os.path.abspath(p if os.path.isabs(p) else os.path.join(basis, p))


def _massstab(s):
    a, b = str(s).replace("/", ":").split(":")
    return float(a.replace(",", ".")), float(b.replace(",", "."))


def _mitte(bx):
    return [(bx[0] + bx[3]) / 2, (bx[1] + bx[4]) / 2, (bx[2] + bx[5]) / 2]


def _wert(s):
    return float(str(s).replace("−", "-").replace(",", ".").replace(" ", ""))


def _nk_text(s):
    m = re.search(r"[,.](\d+)", str(s))
    return len(m.group(1)) if m else 0


def _nachkomma(v):
    for n in range(4):
        if abs(round(v, n) - v) < 1e-6:
            return n
    return 4


def _zahl(v):
    return f"{v:.{_nachkomma(v)}f}".replace(".", ",")


def _toleranzzelle(s):
    s = str(s).strip()
    dia = s.startswith(("⌀", "Ø", "{D}"))
    s = re.sub(r"^(⌀|Ø|\{D\})\s*", "", s)
    mc = ""
    for sym, code in (("Ⓜ", "<MOD-MMC>"), ("{M}", "<MOD-MMC>"), ("Ⓛ", "<MOD-LMC>"), ("{L}", "<MOD-LMC>")):
        if sym in s:
            mc = code
            s = s.replace(sym, "")
    return dia, mc, sw_text(s.strip())


def _bezugszelle(s):
    s = str(s).strip()
    mc = ""
    for sym, code in (("Ⓜ", "<MOD-MMC>"), ("{M}", "<MOD-MMC>"), ("Ⓛ", "<MOD-LMC>"), ("{L}", "<MOD-LMC>")):
        if sym in s:
            mc = code
            s = s.replace(sym, "")
    return s.strip(), mc
