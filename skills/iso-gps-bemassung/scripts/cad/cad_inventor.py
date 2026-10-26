"""Autodesk-Inventor-Adapter (COM-API) – UNGETESTET.

Geschrieben nach der Inventor-API-Dokumentation, aber ohne installiertes Inventor geprüft.
Enum-Werte werden zur Laufzeit über die Typbibliothek aufgelöst (win32com.client.constants),
damit keine Zahlen geraten werden müssen. Inventor rechnet intern in cm.
Beim ersten echten Einsatz: Selbsttest-Auftrag an einem einfachen Teil laufen lassen und
das Protokoll prüfen.
"""
import os
import winreg

import pythoncom
import win32com.client
from win32com.client import gencache

from cad_basis import Adapter, CadFehler, achsname, dot, liste, norm, runde, zusammenfassen

CM = 10.0  # mm je cm

GEO_CHAR = {
    "geradheit": "kStraightness", "ebenheit": "kFlatness", "rundheit": "kCircularity",
    "zylinderform": "kCylindricity", "linienprofil": "kProfileOfLine", "flaechenprofil": "kProfileOfSurface",
    "parallelitaet": "kParallelism", "rechtwinkligkeit": "kPerpendicularity", "neigung": "kAngularity",
    "position": "kPosition", "koaxialitaet": "kConcentricity", "symmetrie": "kSymmetry",
    "lauf": "kRunout", "gesamtlauf": "kTotalRunout",
}
VIEW_ORIENT = {"vorne": "kFrontViewOrientation", "oben": "kTopViewOrientation", "links": "kLeftViewOrientation",
               "rechts": "kRightViewOrientation", "unten": "kBottomViewOrientation", "hinten": "kBackViewOrientation",
               "iso": "kIsoTopRightViewOrientation"}


def K(name):
    """Inventor-Konstante über die Typbibliothek."""
    try:
        return getattr(win32com.client.constants, name)
    except AttributeError:
        raise CadFehler(f"Inventor-Konstante {name} nicht gefunden (Typbibliothek prüfen)") from None


class Inventor(Adapter):
    name = "inventor"
    getestet = False
    endung_teil = ".ipt"

    @classmethod
    def verfuegbar(cls):
        try:
            winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "Inventor.Application").Close()
        except OSError:
            return False, False, "nicht installiert"
        try:
            win32com.client.GetActiveObject("Inventor.Application")
            return True, True, "COM Inventor.Application"
        except Exception:
            return True, False, "COM Inventor.Application"

    def verbinden(self, sichtbar=True):
        pythoncom.CoInitialize()
        try:
            self.app = win32com.client.GetActiveObject("Inventor.Application")
        except Exception:
            self.app = gencache.EnsureDispatch("Inventor.Application")
        gencache.EnsureDispatch("Inventor.Application")  # Konstanten verfügbar machen
        self.app.Visible = sichtbar
        self.tg = self.app.TransientGeometry
        return self.app.SoftwareVersion.DisplayVersion

    def schliessen(self):
        self.app.Documents.CloseAll(False)

    def oeffnen(self, pfad):
        pfad = os.path.abspath(pfad)
        if not os.path.exists(pfad):
            raise CadFehler(f"Datei nicht gefunden: {pfad}")
        return self.app.Documents.Open(pfad, True)

    def testteil(self, pfad):
        raise CadFehler("Selbsttest-Teil für Inventor ist nicht hinterlegt – vorhandenes Teil mit 'zeichnen' testen")

    # ------------------------------------------------------------------ Analyse
    def analysieren(self, pfad):
        doc = self.oeffnen(pfad)
        if doc.DocumentType != K("kPartDocumentObject"):
            raise CadFehler("Analyse ist für Einzelteile (.ipt) ausgelegt")
        cd = doc.ComponentDefinition
        flaechen, self._faces = [], {}
        n = 0
        for bi in range(1, cd.SurfaceBodies.Count + 1):
            body = cd.SurfaceBodies.Item(bi)
            for fi in range(1, body.Faces.Count + 1):
                face = body.Faces.Item(fi)
                n += 1
                fid = f"F{n}"
                self._faces[fid] = (bi, fi)
                flaechen.append(self._flaeche(face, fid, bi - 1, fi))
        mp = cd.MassProperties
        modell = {
            "cad": "inventor", "datei": os.path.abspath(pfad), "einheit": "mm",
            "werkstoff": getattr(cd, "Material", None) and cd.Material.Name,
            "masse_kg": runde(mp.Mass, 4), "volumen_mm3": runde(mp.Volume * 1000, 1),
            "eigenschaften": {}, "features": [{"name": f.Name, "typ": f.Type} for f in cd.Features],
            "flaechen": flaechen,
        }
        modell["merkmale"] = zusammenfassen(flaechen)
        self.fl = {f["id"]: f for f in flaechen}
        return modell

    def _flaeche(self, face, fid, bi, fi):
        rb = face.Evaluator.RangeBox
        box = [rb.MinPoint.X * CM, rb.MinPoint.Y * CM, rb.MinPoint.Z * CM,
               rb.MaxPoint.X * CM, rb.MaxPoint.Y * CM, rb.MaxPoint.Z * CM]
        rec = {"id": fid, "koerper": bi, "index": fi, "flaeche_mm2": runde(face.Evaluator.Area * 100, 2),
               "kanten": face.Edges.Count, "box": runde(box, 3), "ref": f"{bi + 1}/{fi}"}
        st, g = face.SurfaceType, face.Geometry
        rev = bool(face.IsParamReversed)
        if st == K("kPlaneSurface"):
            n = norm([g.Normal.X, g.Normal.Y, g.Normal.Z])
            if rev:
                n = [-x for x in n]
            p = [g.RootPoint.X * CM, g.RootPoint.Y * CM, g.RootPoint.Z * CM]
            rec.update(typ="ebene", normale=runde(n, 6), lage=runde(dot(p, n), 4))
            ax = achsname(n)
            if ax:
                rec["normale_achse"] = ax
                rec[ax[1].lower()] = runde(p["XYZ".index(ax[1])], 4)
        elif st in (K("kCylinderSurface"), K("kConeSurface")):
            a = norm([g.AxisVector.X, g.AxisVector.Y, g.AxisVector.Z])
            i = max(range(3), key=lambda k: abs(a[k]))
            if a[i] < 0:
                a = [-x for x in a]
            o = [g.BasePoint.X * CM, g.BasePoint.Y * CM, g.BasePoint.Z * CM]
            t = dot(o, a)
            o = [o[k] - t * a[k] for k in range(3)]
            ts = [dot([x - o[0], y - o[1], z - o[2]], a) for x in (box[0], box[3]) for y in (box[1], box[4])
                  for z in (box[2], box[5])]
            rec.update(typ="zylinder" if st == K("kCylinderSurface") else "kegel",
                       art="innen" if rev else "aussen",
                       achse={"punkt": runde(o, 4), "richtung": runde(a, 6)}, bereich=runde([min(ts), max(ts)], 3))
            if st == K("kCylinderSurface"):
                rec["d"] = runde(2 * g.Radius * CM, 4)
        else:
            rec["typ"] = "sonstige"
        return rec

    def _face(self, doc, fid):
        bi, fi = self._faces[fid]
        return doc.ComponentDefinition.SurfaceBodies.Item(bi).Faces.Item(fi)

    # ------------------------------------------------------------------ Zeichnung
    def zeichnen(self, auftrag, basis="."):
        from cad_solidworks import Protokoll, _massstab, _pfad, _wert, _toleranzzelle, _bezugszelle
        prot = Protokoll()
        teil = _pfad(auftrag["teil"], basis)
        self.analysieren(teil)
        part = self.oeffnen(teil)
        b = auftrag.get("blatt", {})
        s1, s2 = _massstab(b.get("massstab", "1:1"))
        tmpl = _pfad(b["vorlage"], basis) if b.get("vorlage") else \
            self.app.FileManager.GetTemplateFile(K("kDrawingDocumentObject"))
        drw = self.app.Documents.Add(K("kDrawingDocumentObject"), tmpl, True)
        sheet = drw.ActiveSheet
        fmt = str(b.get("format", "A3")).upper().replace("H", "")
        try:
            sheet.Size = K(f"k{fmt}DrawingSheetSize")
            sheet.Orientation = K("kPortraitPageOrientation" if b.get("format", "").upper() == "A4H"
                                  else "kLandscapePageOrientation")
            prot.ok("Blatt", f"{fmt} {s1:g}:{s2:g}")
        except Exception as ex:
            prot.fehler("Blatt", str(ex))
        self.sheet, self.drw, self.part = sheet, drw, part
        self.views, self.masse = {}, {}
        for va in auftrag.get("ansichten", []):
            vid = va.get("id", va.get("richtung", "vorne"))
            try:
                x, y = va.get("pos", [200, 150])
                vs1, vs2 = _massstab(va["massstab"]) if va.get("massstab") else (s1, s2)
                v = sheet.DrawingViews.AddBaseView(part, self.tg.CreatePoint2d(x / CM, y / CM), vs1 / vs2,
                                                   K(VIEW_ORIENT[va.get("richtung", "vorne")]),
                                                   K("kHiddenLineRemovedDrawingViewStyle"))
                self.views[vid] = v
                prot.ok("Ansicht", vid)
            except Exception as ex:
                prot.fehler("Ansicht", f"{vid}: {ex}")

        def kurven(v, fid):
            return [c for c in v.DrawingCurves(self._face(part, fid))]

        def intent(c):
            return sheet.CreateGeometryIntent(c)

        for m in auftrag.get("masse", []):
            try:
                v = self.views[m.get("ansicht") or next(iter(self.views))]
                gd = sheet.DrawingDimensions.GeneralDimensions
                pos = self.tg.CreatePoint2d(*(p / CM for p in m.get("pos", self._standardpos(v, m))))
                if m.get("typ", "abstand") == "abstand":
                    ka, kb = kurven(v, m["von"]), kurven(v, m["bis"])
                    dim = gd.AddLinear(pos, intent(ka[0]), intent(kb[0]))
                else:
                    ks = kurven(v, m["flaeche"])
                    kreis = [c for c in ks if c.CurveType == K("kCircleCurve")]
                    if kreis:
                        dim = gd.AddDiameter(pos, intent(kreis[0]))
                    else:
                        linien = [c for c in ks if c.CurveType == K("kLineSegmentCurve")]
                        dim = gd.AddLinear(pos, intent(linien[0]), intent(linien[-1]))
                        if not m.get("text"):
                            dim.Text.FormattedText = "Ø<DimensionValue/>"
                if m.get("text"):
                    dim.Text.FormattedText = m["text"]
                t = m.get("tol")
                if m.get("ted"):
                    dim.Tolerance.SetToBasic()
                elif isinstance(t, str) and t.strip().startswith("±"):
                    dim.Tolerance.SetToSymmetric(_wert(t.strip()[1:]) / CM)
                elif isinstance(t, str) and "/" in t:
                    o, u = [x.strip() for x in t.split("/", 1)]
                    dim.Tolerance.SetToDeviation(_wert(o) / CM, -_wert(u) / CM)
                elif isinstance(t, str) and t:
                    if t[0].isupper():
                        dim.Tolerance.SetToFits(K("kStackedFitTolerance"), t, "")
                    else:
                        dim.Tolerance.SetToFits(K("kStackedFitTolerance"), "", t)
                if m.get("hilfsmass"):
                    dim.Tolerance.SetToReference()
                if m.get("id"):
                    self.masse[m["id"]] = (dim, v, m)
                prot.ok("Maß", m.get("id", "?"))
            except Exception as ex:
                prot.fehler("Maß", f"{m.get('id')}: {ex}")

        for g in auftrag.get("rahmen", []):
            try:
                v = self.views[g.get("ansicht") or next(iter(self.views))]
                pts = self.app.TransientObjects.CreateObjectCollection()
                x, y = g.get("pos", [100, 250])
                pts.Add(self.tg.CreatePoint2d(x / CM, y / CM))
                pts.Add(intent(kurven(v, g["flaeche"])[0]) if g.get("flaeche") else self.masse[g["an"]][0])
                fcf = sheet.FeatureControlFrames.Add(pts)
                for z in (g["zellen"] if isinstance(g["zellen"][0], list) else [g["zellen"]]):
                    dia, mc, wert = _toleranzzelle(z[1])
                    row = fcf.FeatureControlFrameRows.Add(K(GEO_CHAR[str(z[0]).lower()]),
                                                          ("Ø" if dia else "") + wert.replace("<MOD-MMC>", "Ⓜ"))
                    for i, dz in enumerate(z[2:5]):
                        setattr(row, ["DatumOne", "DatumTwo", "DatumThree"][i], _bezugszelle(dz)[0])
                prot.ok("Toleranzrahmen", "|".join(map(str, g["zellen"])))
            except Exception as ex:
                prot.fehler("Toleranzrahmen", f"{g.get('zellen')}: {ex}")

        for d in auftrag.get("bezuege", []):
            try:
                if d.get("an"):
                    dim, v, m = self.masse[d["an"]]
                    ziel = intent(kurven(v, m.get("flaeche") or m.get("von"))[0])
                else:
                    v = self.views[d.get("ansicht") or next(iter(self.views))]
                    ziel = intent(kurven(v, d["flaeche"])[0])
                pts = self.app.TransientObjects.CreateObjectCollection()
                x, y = d.get("pos", [100, 230])
                pts.Add(self.tg.CreatePoint2d(x / CM, y / CM))
                pts.Add(ziel)
                sheet.DatumIdentifierSymbols.Add(d["buchstabe"], pts)
                prot.ok("Bezug", d["buchstabe"])
            except Exception as ex:
                prot.fehler("Bezug", f"{d.get('buchstabe')}: {ex}")

        for s in auftrag.get("oberflaechen", []):
            try:
                v = self.views[s.get("ansicht") or next(iter(self.views))]
                pts = self.app.TransientObjects.CreateObjectCollection()
                x, y = s.get("pos", [100, 220])
                pts.Add(self.tg.CreatePoint2d(x / CM, y / CM))
                pts.Add(intent(kurven(v, s["flaeche"])[0]))
                art = {"abtragen": "kMaterialRemovalRequiredSurfaceType", "beliebig": "kBasicSurfaceType",
                       "ohne": "kMaterialRemovalProhibitedSurfaceType"}[s.get("art", "abtragen")]
                sheet.SurfaceTextureSymbols.Add(pts, K(art), False, False, False, s["text"])
                prot.ok("Oberfläche", s["text"])
            except Exception as ex:
                prot.fehler("Oberfläche", f"{s.get('text')}: {ex}")

        for n in auftrag.get("hinweise", []):
            try:
                x, y = n.get("pos", [25, 70])
                text = "\n".join(n["text"]) if isinstance(n["text"], list) else n["text"]
                sheet.DrawingNotes.GeneralNotes.AddFitted(self.tg.CreatePoint2d(x / CM, y / CM), text)
                prot.ok("Hinweis", text.splitlines()[0])
            except Exception as ex:
                prot.fehler("Hinweis", str(ex))

        self._eigenschaften(drw, auftrag.get("eigenschaften", {}), prot)
        aus = auftrag.get("ausgabe") or {}
        if isinstance(aus, str):
            aus = {"name": aus}
        ordner = _pfad(aus.get("ordner", os.path.dirname(teil)), basis)
        name = aus.get("name") or auftrag.get("eigenschaften", {}).get("Zeichnungsnummer") \
            or os.path.splitext(os.path.basename(teil))[0]
        ziel = os.path.join(ordner, name + ".idw")
        try:
            drw.SaveAs(ziel, False)
            prot.ok("Speichern", ziel)
            if aus.get("pdf", True):
                drw.SaveAs(os.path.splitext(ziel)[0] + ".pdf", True)
                prot.ok("PDF", os.path.splitext(ziel)[0] + ".pdf")
        except Exception as ex:
            prot.fehler("Speichern", str(ex))
        return prot.ergebnis(ziel)

    def _standardpos(self, v, m):
        c = v.Center
        return [c.X * CM, (c.Y - v.Height / 2) * CM - m.get("abstand", 12)]

    def _eigenschaften(self, drw, eig, prot):
        zuordnung = {"Benennung": ("Design Tracking Properties", "Description"),
                     "Zeichnungsnummer": ("Design Tracking Properties", "Part Number"),
                     "Gezeichnet": ("Design Tracking Properties", "Designer"),
                     "Geprueft": ("Design Tracking Properties", "Checked By"),
                     "Genehmigt": ("Design Tracking Properties", "Engineer"),
                     "Index": ("Inventor Summary Information", "Revision Number"),
                     "Eigentuemer": ("Inventor Document Summary Information", "Company")}
        for k, v in eig.items():
            try:
                if k in zuordnung:
                    ps, name = zuordnung[k]
                    drw.PropertySets.Item(ps).Item(name).Value = str(v)
                else:
                    drw.PropertySets.Item("Inventor User Defined Properties").Add(str(v), k)
            except Exception as ex:
                prot.fehler("Eigenschaft", f"{k}: {ex}")
        if eig:
            prot.ok("Eigenschaften", ", ".join(eig))

    def exportieren(self, pfad, formate=("pdf",)):
        doc = self.oeffnen(pfad)
        aus = []
        for f in formate:
            ziel = os.path.splitext(os.path.abspath(pfad))[0] + "." + f
            doc.SaveAs(ziel, True)
            aus.append(ziel)
        return aus
