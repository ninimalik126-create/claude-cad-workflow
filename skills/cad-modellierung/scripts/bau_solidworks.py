"""Bauskript SolidWorks: setzt einen Bauplan als Feature-Baum um (COM, Python + pywin32).

Wird von modell.py aufgerufen: bauen(auftrag) -> Bericht (dict), gleiches Format wie bau_freecad.py.
Getestet mit SolidWorks 2026 (deutsch). Alle Längen der SolidWorks-API sind in Metern.

SolidWorks-Eigenheiten, auf denen das beruht (aus Tests mit der Typbibliothek sldworks.tlb):
- Standardebenen in Baumreihenfolge: vorne = XY (Normale +Z), oben = XZ (+Y), rechts = YZ (+X).
- Skizzenkoordinaten sind Skizzenraum (oben: Skizzen-y = −Z) -> Umrechnung über ModelToSketchTransform.
- Extrusion läuft standardmäßig in Normalenrichtung, Schnitt entgegen. Versatz über den Start-Offset (T0 = 3).
- Eine aktive Auswahl beim STL-Export schreibt nur Teilflächen -> vor jedem Export Auswahl leeren.
- COM-Objekte nie doppelt in O() hüllen.
"""
import math
import os
import sys
import traceback

HIER = os.path.dirname(os.path.abspath(__file__))
CAD = os.path.join(os.path.dirname(os.path.dirname(HIER)), "iso-gps-bemassung", "scripts", "cad")
sys.path.insert(0, HIER)
sys.path.insert(0, CAD)

import pythoncom  # noqa: E402
from win32com.client import VARIANT  # noqa: E402

import bauplan as bp  # noqa: E402
from cad_basis import MM, M, liste  # noqa: E402
from cad_solidworks import SolidWorks, byref_int  # noqa: E402

END_BLIND, END_DURCH, END_MITTE = 0, 1, 6
START_OFFSET = 3
# Benutzereinstellungen für den STL/3MF-Export (werden nach dem Export zurückgesetzt)
STL_EINHEIT, STL_QUALITAET = 211, 78       # swExportStlUnits (0 = mm), swSTLQuality (3 = benutzerdefiniert)
STL_ABWEICHUNG, STL_WINKEL = 2, 3          # swSTLDeviation (m), swSTLAngleTolerance (rad)
PLAN_ANSICHTEN = {  # Blickrichtung (zum Betrachter), Bildschirm-x – gleich wie fc_arbeiter.RICHTUNGEN
    "vorne": ((0, -1, 0), (1, 0, 0)), "hinten": ((0, 1, 0), (-1, 0, 0)),
    "oben": ((0, 0, 1), (1, 0, 0)), "unten": ((0, 0, -1), (1, 0, 0)),
    "rechts": ((1, 0, 0), (0, 1, 0)), "links": ((-1, 0, 0), (0, -1, 0)),
    "iso": ((1, -1, 1), (1, 1, 0)),
}


def m(v):
    return v / MM


class Bau:
    def __init__(self, plan, auftrag):
        self.plan, self.auftrag = plan, auftrag
        self.a = SolidWorks()
        self.version = self.a.verbinden()
        self.sw = self.a.sw
        self.nativ = os.path.join(auftrag["ordner"], _dateiname(plan["name"]) + ".SLDPRT")
        self._freigeben(self.nativ)
        self.part = self.sw.NewDocument(self.sw.GetUserPreferenceStringValue(8), 0, 0, 0)
        if self.part is None:
            raise RuntimeError("SolidWorks konnte kein neues Teil anlegen (Teilevorlage prüfen)")
        ebenen, f = [], M(self.part, "FirstFeature")
        while f is not None and len(ebenen) < 3:
            if M(f, "GetTypeName2") == "RefPlane":
                ebenen.append(f)
            f = M(f, "GetNextFeature")
        self.ebenen = dict(zip(("XY", "XZ", "YZ"), ebenen))
        self.fm = M(self.part, "FeatureManager")
        self.sm = M(self.part, "SketchManager")
        self.ext = M(self.part, "Extension")
        self.sel = M(self.part, "SelectionManager")
        self.log = []
        self.fehler = 0

    def _freigeben(self, pfad):
        """Schließt das alte Teil und Dokumente, die es verwenden (z. B. eine offene Zeichnung), damit es
        überschrieben werden kann – aber nur ohne ungespeicherte Änderungen."""
        ziel = os.path.normcase(os.path.abspath(pfad))
        for doc in liste(self.sw.GetDocuments()):
            name = os.path.normcase(M(doc, "GetPathName") or "")
            abh = [os.path.normcase(str(x)) for x in liste(doc.GetDependencies2(True, True, False))]
            if name != ziel and ziel not in abh:
                continue
            if M(doc, "GetSaveFlag"):
                raise RuntimeError(f"{M(doc, 'GetTitle')} ist in SolidWorks mit ungespeicherten Änderungen offen "
                                   f"und verwendet das Teil – bitte speichern oder schließen")
            self.sw.CloseDoc(M(doc, "GetTitle"))

    # ------------------------------------------------------------------ Hilfen
    def SD(self):
        return self.sel.CreateSelectData()

    def koerper(self):
        return liste(self.part.GetBodies2(0, True))

    def volumen(self):
        if not self.koerper():
            return 0.0
        return M(self.ext, "CreateMassProperty").Volume() * 1e9

    def _letztes(self):
        f = self.part.FeatureByPositionReverse(0)
        return M(f, "Name") if f is not None else None

    def _zuruecksetzen(self, bis):
        """Löscht alle Features nach 'bis' (fehlgeschlagenes Feature samt Skizze)."""
        for _ in range(10):
            f = self.part.FeatureByPositionReverse(0)
            if f is None or M(f, "Name") == bis:
                break
            self.part.ClearSelection2(True)
            f.Select2(False, 0)
            self.part.EditDelete()
        self.part.ClearSelection2(True)

    def skizze(self, ebene, schleifen, achse=None):
        self.part.ClearSelection2(True)
        self.ebenen[ebene].Select2(False, 0)
        self.sm.InsertSketch(True)
        self.sm.AddToDB = True
        sk = self.part.GetActiveSketch2()
        d = liste(M(M(sk, "ModelToSketchTransform"), "ArrayData"))
        R, t, s = d[0:9], d[9:12], d[12] or 1.0

        def S(uv):
            p = [m(c) for c in bp.modellpunkt(ebene, 0, uv)]
            x = (p[0] * R[0] + p[1] * R[3] + p[2] * R[6]) * s + t[0]
            y = (p[0] * R[1] + p[1] * R[4] + p[2] * R[7]) * s + t[1]
            return x, y
        for sch in schleifen:
            for seg in sch:
                if seg[0] == "linie":
                    (x1, y1), (x2, y2) = S(seg[1]), S(seg[2])
                    self.sm.CreateLine(x1, y1, 0, x2, y2, 0)
                elif seg[0] == "bogen":
                    (x1, y1), (xm, ym), (x2, y2) = S(seg[1]), S(seg[2]), S(seg[3])
                    self.sm.Create3PointArc(x1, y1, 0, x2, y2, 0, xm, ym, 0)
                else:
                    (xc, yc) = S(seg[1])
                    self.sm.CreateCircleByRadius(xc, yc, 0, m(seg[2]))
        if achse:
            u = bp.EBENEN[ebene][0]
            ende = (1000, 0) if bp.ACHSEN[achse] == u else (0, 1000)
            (x1, y1), (x2, y2) = S((-ende[0], -ende[1])), S(ende)
            self.sm.CreateCenterLine(x1, y1, 0, x2, y2, 0)
        self.sm.AddToDB = False
        self.sm.InsertSketch(True)

    @staticmethod
    def _start(f):
        v = f.get("versatz", 0)
        return (START_OFFSET if v else 0), m(abs(v)), v < 0

    def _extrusion(self, f, hoehe, ende=END_BLIND, umkehren=False, entformung=None):
        t0, so, flip = self._start(f)
        beide = f.get("richtung") == "beide"
        dchk, dang = (True, math.radians(entformung)) if entformung else (False, 0.0)
        return self.fm.FeatureExtrusion3(True, False, umkehren, END_MITTE if beide else ende, 0, m(hoehe), 0,
                                         dchk, False, False, False, dang, 0, False, False, False, False,
                                         True, True, True, t0, so, flip)

    def _schnitt(self, f, tiefe, durch=False, umkehren=False, entformung=None, nach_innen=True):
        t0, so, flip = self._start(f)
        beide = f.get("richtung") == "beide"
        dchk, dang = (True, math.radians(entformung)) if entformung else (False, 0.0)
        if durch and beide:
            return self.fm.FeatureCut4(False, False, False, END_DURCH, END_DURCH, 0, 0, False, False, False, False,
                                       0, 0, False, False, False, False, False, True, True, True, True, False,
                                       t0, so, flip, False)
        ende = END_DURCH if durch else (END_MITTE if beide else END_BLIND)
        # Ddir1 = True heißt Formschräge nach außen (gemessen: Senkung wuchs sonst nach außen)
        return self.fm.FeatureCut4(True, False, umkehren, ende, 0, m(tiefe or 0.001), 0, dchk, False,
                                   not nach_innen, False, dang, 0, False, False, False, False, False, True, True,
                                   True, True, False, t0, so, flip, False)

    # ------------------------------------------------------------------ Geometriedaten
    def kanten_daten(self):
        out = []
        for i, e in enumerate(e for b in self.koerper() for e in liste(M(b, "GetEdges"))):
            cu = M(e, "GetCurve")
            cp = M(e, "GetCurveParams3")
            s, t = M(cp, "UMinValue"), M(cp, "UMaxValue")
            pts = [tuple(c * MM for c in liste(cu.Evaluate2(s + (t - s) * k / 6, 1))[:3]) for k in range(7)]
            k = {"i": i, "typ": "andere", "punkte": pts, "_e": e}
            if M(cu, "IsLine"):
                k["typ"] = "linie"
                k["richtung"] = bp.einheit(bp.sub(pts[-1], pts[0]))
            elif M(cu, "IsCircle"):
                c = liste(M(cu, "CircleParams"))
                k.update(typ="kreis", mitte=tuple(x * MM for x in c[0:3]), d=2 * c[6] * MM, achse=tuple(c[3:6]))
            if bp.laenge(bp.sub(pts[0], pts[-1])) > 1e-6:
                enden = []
                for par in (s, t):
                    ev = liste(cu.Evaluate2(par, 1))
                    tan = tuple(ev[3:6]) if len(ev) >= 6 and any(ev[3:6]) else None
                    if tan is None:
                        q = liste(cu.Evaluate2(par + (t - s) * (1e-4 if par == s else -1e-4), 0))[:3]
                        tan = bp.sub(tuple(x * MM for x in q), tuple(x * MM for x in ev[:3]))
                    enden.append((tuple(x * MM for x in ev[:3]), tan))
                k["enden"] = enden
            out.append(k)
        return out

    def flaechen_daten(self):
        out = []
        for i, fc in enumerate(fc for b in self.koerper() for fc in liste(M(b, "GetFaces"))):
            box = [v * MM for v in liste(M(fc, "GetBox"))]
            d = {"i": i, "typ": "andere", "punkt": tuple((box[k] + box[k + 3]) / 2 for k in range(3)), "_f": fc}
            s = M(fc, "GetSurface")
            if M(s, "IsPlane"):
                d.update(typ="ebene", normale=tuple(round(x, 9) for x in bp.einheit(liste(M(fc, "Normal")))))
            elif M(s, "IsCylinder"):
                c = liste(M(s, "CylinderParams"))
                d.update(typ="zylinder", d=2 * c[6] * MM, achse=tuple(c[3:6]))
            out.append(d)
        return out

    def waehle_kanten(self, auswahl, tangential=True):
        daten = self.kanten_daten()
        idx = bp.waehle_kanten(daten, auswahl)
        if tangential:
            idx = bp.tangential_erweitern(daten, idx)
        self.part.ClearSelection2(True)
        for i in idx:
            daten[i]["_e"].Select4(True, self.SD())
        return len(idx)

    def waehle_flaechen(self, auswahl):
        daten = self.flaechen_daten()
        idx = bp.waehle_flaechen(daten, auswahl)
        self.part.ClearSelection2(True)
        for i in idx:
            daten[i]["_f"].Select4(True, self.SD())
        return len(idx)

    # ------------------------------------------------------------------ Features
    def block(self, f):
        self.skizze(f["ebene"], f["_schleifen"])
        return self._extrusion(f, f["hoehe"], umkehren=f["richtung"] == "-")

    def tasche(self, f):
        self.skizze(f["ebene"], f["_schleifen"])
        return self._schnitt(f, f.get("tiefe"), bool(f.get("durch")), umkehren=f["richtung"] == "+")

    def _dreh(self, f, schnitt):
        self.skizze(f["ebene"], f["_schleifen"], achse=f["achse"])
        return self.fm.FeatureRevolve2(True, True, False, schnitt, False, False, 0, 0, math.radians(f["winkel"]),
                                       0, False, False, 0, 0, 0, 0, 0, True, True, True)

    def drehteil(self, f):
        return self._dreh(f, False)

    def drehnut(self, f):
        return self._dreh(f, True)

    def bohrung(self, f):
        pos = f["_positionen"]
        umk = f["richtung"] == "+"
        self.skizze(f["ebene"], [[("kreis", p, f["d"] / 2)] for p in pos])
        feat = self._schnitt(f, f.get("tiefe"), bool(f.get("durch")), umkehren=umk)
        if feat is None:
            return None
        feat.Name = f["id"]
        fs = f.get("flachsenkung")
        if fs:
            self.skizze(f["ebene"], [[("kreis", p, fs["d"] / 2)] for p in pos])
            s = self._schnitt(f, fs["tiefe"], umkehren=umk)
            if s is None:
                raise RuntimeError("Flachsenkung konnte nicht geschnitten werden")
            s.Name = f["id"] + "_Flachsenkung"
        sk = f.get("senkung")
        if sk:
            halb = sk["winkel"] / 2
            tiefe = (sk["d"] - f["d"]) / 2 / math.tan(math.radians(halb))
            self.skizze(f["ebene"], [[("kreis", p, sk["d"] / 2)] for p in pos])
            s = self._schnitt(f, tiefe, umkehren=umk, entformung=halb, nach_innen=True)
            if s is None:
                raise RuntimeError("Senkung konnte nicht geschnitten werden")
            s.Name = f["id"] + "_Senkung"
        g = f.get("_gewinde")
        if g:
            self._gewinde(f, g, pos)
        return feat

    def _gewinde(self, f, g, pos):
        """Kosmetisches Gewinde an jeder Bohrungskante in der Startebene."""
        ebene = f["ebene"]
        achse = "XYZ"[[abs(c) for c in bp.EBENEN[ebene][2]].index(1)]
        lage = f.get("versatz", 0)
        if f.get("flachsenkung"):
            lage += f["flachsenkung"]["tiefe"] * (1 if f["richtung"] == "+" else -1)
        tiefe = f.get("gewindetiefe") or f.get("tiefe")
        ende = 0 if tiefe else 1
        for p in pos:
            ziel = bp.modellpunkt(ebene, lage, p)
            n = self.waehle_kanten({"d": f["d"], "in_ebene": {achse: lage}, "nahe": [ziel]}, tangential=False)
            if not n:
                raise RuntimeError(f"Bohrungskante für Gewinde bei {p} nicht gefunden")
            th = self.fm.InsertCosmeticThread3(0, "", "", m(g["d"]), ende, m(tiefe or 0), g["name"])
            if th is None:
                raise RuntimeError(f"Kosmetisches Gewinde {g['name']} nicht angelegt")

    def fase(self, f):
        n = self.waehle_kanten(f["kanten"], f.get("tangential", True))
        if not n:
            raise RuntimeError("Kantenauswahl trifft keine Kante")
        f["_anzahl"] = n
        return self.fm.InsertFeatureChamfer(4, 1, m(f["laenge"]), math.radians(f.get("winkel", 45)), 0, 0, 0, 0)

    def verrundung(self, f):
        n = self.waehle_kanten(f["kanten"], f.get("tangential", True))
        if not n:
            raise RuntimeError("Kantenauswahl trifft keine Kante")
        f["_anzahl"] = n
        return self.fm.FeatureFillet3(195, m(f["r"]), 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

    def schale(self, f):
        if not self.waehle_flaechen(f["flaechen"]):
            raise RuntimeError("Flächenauswahl trifft keine Fläche")
        self.part.InsertFeatureShell(m(f["dicke"]), f.get("nach", "innen") != "innen")
        return self.part.FeatureByPositionReverse(0)

    def frei(self, f):
        code = f.get("solidworks")
        if not code:
            raise RuntimeError("kein SolidWorks-Code in diesem frei-Feature")
        ns = self.namensraum()
        exec(compile(code, f["id"], "exec"), ns)
        return ns.get("ergebnis") or self.part.FeatureByPositionReverse(0)

    def namensraum(self):
        return {"sw": self.sw, "part": self.part, "fm": self.fm, "sm": self.sm, "bau": self, "bp": bp,
                "math": math, "M": M, "liste": liste, "m": m, "feature": self.feature}

    # ------------------------------------------------------------------ Ablauf
    def feature(self, f):
        try:
            bp.einzeln(f)
        except bp.BauplanFehler as ex:
            self.fehler += 1
            self.log.append({"id": f.get("id", "?"), "ok": False, "fehler": "; ".join(ex.befunde)})
            return None
        v0 = self.volumen()
        letztes = self._letztes()
        try:
            o = getattr(self, f["typ"])(f)
            if o is None:
                raise RuntimeError("SolidWorks konnte das Feature nicht bilden")
            if f["typ"] != "bohrung":
                o.Name = f["id"]
        except Exception as ex:
            self.fehler += 1
            msg = str(ex) if isinstance(ex, RuntimeError) else traceback.format_exc(limit=2)
            self.log.append({"id": f["id"], "ok": False, "fehler": msg})
            self._zuruecksetzen(letztes)
            return None
        self.part.ClearSelection2(True)
        v1 = self.volumen()
        e = {"id": f["id"], "typ": f["typ"], "ok": True, "volumen": round(v1, 3), "delta": round(v1 - v0, 3)}
        if f.get("_anzahl"):
            e["kanten"] = f["_anzahl"]
        erwartung = {"block": 1, "drehteil": 1, "tasche": -1, "drehnut": -1, "bohrung": -1, "schale": -1}.get(f["typ"])
        if erwartung and (v1 - v0) * erwartung <= 1e-6:
            e.update(ok=False, fehler="Feature ändert das Volumen nicht in die erwartete Richtung "
                                      "(Richtung, Versatz oder Lage prüfen)")
            self.fehler += 1
        n = len(self.koerper())
        if n > 1:
            e.update(ok=False, fehler=f"Körper zerfällt in {n} Teile")
            self.fehler += 1
        self.log.append(e)
        return o

    def bauen(self):
        for f in self.plan["features"]:
            self.feature(f)
            if self.fehler:
                break

    def _plan_ansichten(self):
        """Benannte Ansichten 'Plan vorne' … im Bauplan-Sinn (Z oben), wie in FreeCAD und der Vorschau.
        SolidWorks' eigene Normansichten gehen von Y oben aus; die Zeichnungsanbindung nimmt diese hier zuerst.
        Orientierung: Zeilen = Bildschirm-(x, y, zum Betrachter)-Anteile der Modellachsen X, Y, Z."""
        for name, (D, X) in PLAN_ANSICHTEN.items():
            D, X = bp.einheit(D), bp.einheit(X)
            Y = bp.kreuz(D, X)
            rot = [X[0], Y[0], D[0], X[1], Y[1], D[1], X[2], Y[2], D[2]]
            mv = self.part.ActiveView()
            daten = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(x) for x in rot] + [0, 0, 0, 1.0, 0, 0, 0])
            mv.Orientation3 = self.a.mu.CreateTransform(daten)  # ohne Double-Array: stillschweigend Einheitsmatrix
            self.part.NameView("Plan " + name)
        self.part.ShowNamedView2("Plan iso", -1)
        self.part.ViewZoomtofit2()

    def _speichern(self, pfad, kopie=True, netz=None):
        """netz = (Abweichung mm, Winkel °) für STL/3MF; Benutzereinstellungen werden danach zurückgesetzt."""
        if os.path.exists(pfad):
            os.remove(pfad)
        self.part.ClearSelection2(True)
        alt = None
        if netz:
            sw = self.sw
            alt = (sw.GetUserPreferenceIntegerValue(STL_EINHEIT), sw.GetUserPreferenceIntegerValue(STL_QUALITAET),
                   sw.GetUserPreferenceDoubleValue(STL_ABWEICHUNG), sw.GetUserPreferenceDoubleValue(STL_WINKEL))
            sw.SetUserPreferenceIntegerValue(STL_EINHEIT, 0)
            sw.SetUserPreferenceIntegerValue(STL_QUALITAET, 3)
            sw.SetUserPreferenceDoubleValue(STL_ABWEICHUNG, m(netz[0]))
            sw.SetUserPreferenceDoubleValue(STL_WINKEL, math.radians(netz[1]))
        try:
            err = self.part.SaveAs3(pfad, 0, 1 | (2 if kopie else 0))
        finally:
            if alt:
                self.sw.SetUserPreferenceIntegerValue(STL_EINHEIT, alt[0])
                self.sw.SetUserPreferenceIntegerValue(STL_QUALITAET, alt[1])
                self.sw.SetUserPreferenceDoubleValue(STL_ABWEICHUNG, alt[2])
                self.sw.SetUserPreferenceDoubleValue(STL_WINKEL, alt[3])
        if err or not os.path.exists(pfad):
            raise RuntimeError(f"Speichern als {os.path.basename(pfad)} fehlgeschlagen (Code {err})")
        return pfad

    def abschluss(self):
        a = self.auftrag
        name = _dateiname(self.plan["name"])
        ordner = a["ordner"]
        os.makedirs(ordner, exist_ok=True)
        b = {"cad": "solidworks", "version": self.version, "name": self.plan["name"], "features": self.log,
             "fehler": self.fehler, "dateien": [], "warnungen": []}
        if not self.koerper():
            b["fehler"] += 1
            b["features"].append({"id": "ergebnis", "ok": False, "fehler": "kein Volumenkörper entstanden"})
            return b
        huelle = [v * MM for v in liste(self.part.GetPartBox(True))]
        mp = M(self.ext, "CreateMassProperty")
        b["koerper"] = len(self.koerper())
        b["huelle"] = [round(x, 4) for x in huelle]
        b["groesse"] = [round(huelle[k + 3] - huelle[k], 4) for k in range(3)]
        b["volumen_mm3"] = round(mp.Volume() * 1e9, 3)
        b["oberflaeche_mm2"] = round(mp.SurfaceArea() * 1e6, 3)
        rho = bp.dichte(self.plan)
        if rho:
            b["masse_kg"] = round(b["volumen_mm3"] * rho / 1e6, 4)
        abw = bp.soll_vergleich(self.plan, huelle, b["volumen_mm3"])
        if abw:
            b["fehler"] += len(abw)
            b["soll_abweichungen"] = abw
        cpm = self.ext.CustomPropertyManager("")
        for k, v in (("Benennung", self.plan["name"]), ("Werkstoff", self.plan.get("werkstoff"))):
            if v:
                cpm.Add3(k, 30, str(v), 2)
        try:
            self._plan_ansichten()
        except Exception as ex:
            b["warnungen"].append(f"Benannte Plan-Ansichten nicht angelegt: {ex}")
        self._speichern(self.nativ, kopie=False)
        b["dateien"].append(self.nativ)
        formate = [x.lower() for x in a.get("formate", [])]
        if b["fehler"]:
            b["warnungen"].append("Austauschformate wegen Fehlern nicht erzeugt")
            formate = []
        netz = (a.get("stl_toleranz", 0.01), a.get("stl_winkel", 5))
        for fmt, endung in (("step", ".step"), ("stl", ".stl"), ("3mf", ".3mf")):
            if fmt in formate:
                p = self._speichern(os.path.join(ordner, name + endung), netz=netz if fmt != "step" else None)
                b["dateien"].append(p)
                if fmt == "stl":
                    b["warnungen"] += _stl_pruefen(p, huelle)
        if a.get("vorschau_stl"):
            diag = math.dist(huelle[:3], huelle[3:])
            self._speichern(a["vorschau_stl"], netz=(max(diag / 2000, 0.005), 11.5))
            b["warnungen"] += _stl_pruefen(a["vorschau_stl"], huelle)
        return b


def _stl_pruefen(pfad, huelle):
    """Vergleicht die Hülle der exportierten STL mit dem Modell (Einheiten, Teilexport)."""
    import vorschau
    pts = [p for t in vorschau.lies_stl(pfad) for p in t]
    if not pts:
        return ["STL-Export ist leer"]
    for k in range(3):
        soll = huelle[k + 3] - huelle[k]
        ist = max(p[k] for p in pts) - min(p[k] for p in pts)
        if soll > 0.1 and abs(ist - soll) > max(0.05, soll * 0.01):
            return [f"STL-Hülle weicht vom Modell ab ({'XYZ'[k]}: {ist:.3f} statt {soll:.3f} mm) – Exporteinheit prüfen"]
    return []


def _dateiname(s):
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in s).strip("_") or "Teil"


def bauen(auftrag):
    bericht = {"cad": "solidworks", "fehler": 1, "features": []}
    bau = None
    try:
        plan = bp.laden(auftrag["plan"], skript=bool(auftrag.get("skript")))
        bau = Bau(plan, auftrag)
        bau.bauen()
        if auftrag.get("skript") and not bau.fehler:
            ns = bau.namensraum()
            try:
                exec(compile(open(auftrag["skript"], encoding="utf-8").read(), auftrag["skript"], "exec"), ns)
                bau.log.append({"id": "skript", "ok": True, "volumen": round(bau.volumen(), 3)})
            except Exception:
                bau.fehler += 1
                bau.log.append({"id": "skript", "ok": False, "fehler": traceback.format_exc(limit=3)})
        bericht = bau.abschluss()
    except bp.BauplanFehler as ex:
        bericht = {"cad": "solidworks", "fehler": len(ex.befunde), "plan_befunde": ex.befunde, "features": []}
    except RuntimeError as ex:
        bericht["features"] = [{"id": "start", "ok": False, "fehler": str(ex)}]
    except Exception:
        bericht["absturz"] = traceback.format_exc()
    if bau is not None and bericht.get("absturz") and not M(bau.part, "GetPathName"):
        try:  # eigenes, nie gespeichertes Teil nach Absturz nicht offen liegen lassen
            bau.sw.CloseDoc(M(bau.part, "GetTitle"))
        except Exception:
            pass
    return bericht
