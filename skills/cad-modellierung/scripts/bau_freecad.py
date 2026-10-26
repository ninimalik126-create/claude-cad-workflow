"""Bauskript FreeCAD: setzt einen Bauplan als PartDesign-Körper um (läuft in FreeCADCmd).

Wird von modell.py gestartet; der Auftrag (JSON) steht in der Umgebungsvariable CCW_AUFTRAG:
  {"plan": pfad, "ordner": ausgabeordner, "formate": ["step", "stl", "3mf"], "bericht": pfad,
   "vorschau_stl": pfad, "skripte": ordner dieses Skripts, "skript": optionales freies Skript}
Jedes Feature wird einzeln gebaut und geprüft (gültig, Volumen ändert sich in die erwartete Richtung).
"""
import json
import math
import os
import sys
import traceback

A = json.load(open(os.environ["CCW_AUFTRAG"], encoding="utf-8"))
sys.path.insert(0, A["skripte"])

import bauplan as bp  # noqa: E402
import FreeCAD as App  # noqa: E402
import Part  # noqa: E402
import Sketcher  # noqa: E402,F401

# Lokales Skizzensystem je Planebene: Spalten (u, v, Normale) als echte Drehung.
# XZ: u=X, v=Z -> Skizzennormale −Y (Plus-Richtung des Plans ist +Y, das regelt 'Reversed').
DREHUNG = {"XY": ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
           "XZ": ((1, 0, 0), (0, 0, 1), (0, -1, 0)),
           "YZ": ((0, 1, 0), (0, 0, 1), (1, 0, 0))}


def V(p):
    return App.Vector(*(list(p) + [0] * (3 - len(p))))


class Bau:
    def __init__(self, plan):
        self.plan = plan
        self.doc = App.newDocument(_dokname(plan["name"]))
        self.body = self.doc.addObject("PartDesign::Body", "Body")
        self.body.Label = plan["name"]
        # Werkstoff und Dichte im Modell ablegen (liest die Zeichnungsanbindung für Masse und Schriftfeld)
        self.body.addProperty("App::PropertyString", "Werkstoff", "Teil")
        self.body.addProperty("App::PropertyFloat", "Dichte", "Teil", "g/cm³")
        self.body.Werkstoff = str(plan.get("werkstoff", ""))
        self.body.Dichte = bp.dichte(plan) or 0.0
        self.xy = [f for f in self.body.Origin.OriginFeatures if f.Role == "XY_Plane"][0]
        self.log = []
        self.fehler = 0

    # ------------------------------------------------------------------ Hilfen
    def tip_shape(self):
        t = self.body.Tip
        return t.Shape if t is not None else Part.Shape()

    def volumen(self):
        s = self.tip_shape()
        return s.Volume if not s.isNull() else 0.0

    def skizze(self, ebene, versatz, schleifen, name):
        u, v, n = DREHUNG[ebene]
        m = App.Matrix(u[0], v[0], n[0], 0, u[1], v[1], n[1], 0, u[2], v[2], n[2], 0, 0, 0, 0, 1)
        sk = self.body.newObject("Sketcher::SketchObject", name)
        sk.AttachmentSupport = (self.xy, [""])
        sk.MapMode = "FlatFace"
        sk.AttachmentOffset = App.Placement(V(bp.modellpunkt(ebene, versatz, (0, 0))), App.Rotation(m))
        for sch in schleifen:
            ids = []
            for s in sch:
                if s[0] == "linie":
                    ids.append(sk.addGeometry(Part.LineSegment(V(s[1]), V(s[2]))))
                elif s[0] == "bogen":
                    ids.append(sk.addGeometry(Part.ArcOfCircle(V(s[1]), V(s[2]), V(s[3]))))
                else:
                    sk.addGeometry(Part.Circle(V(s[1]), App.Vector(0, 0, 1), s[2]))
            self._verbinden(sk, ids)
        return sk

    @staticmethod
    def _verbinden(sk, ids):
        """Koinzidenzen zwischen aufeinanderfolgenden Segmenten, damit die Skizze editierbar bleibt."""
        if len(ids) < 2:
            return
        for a, b in zip(ids, ids[1:] + ids[:1]):
            best = None
            for pa in (1, 2):
                for pb in (1, 2):
                    d = (sk.getPoint(a, pa) - sk.getPoint(b, pb)).Length
                    if best is None or d < best[0]:
                        best = (d, pa, pb)
            if best and best[0] < 1e-6:
                try:
                    sk.addConstraint(Sketcher.Constraint("Coincident", a, best[1], b, best[2]))
                except Exception:
                    pass

    @staticmethod
    def kanten_daten(shape):
        out = []
        for i, e in enumerate(shape.Edges):
            if e.Length < 1e-9:  # entartete Kante (z. B. Kegelspitze, Nahtpunkt)
                continue
            c = e.Curve
            try:
                punkte = [tuple(p) for p in e.discretize(7)]
            except Exception:
                punkte = [tuple(v.Point) for v in e.Vertexes] + [tuple(e.CenterOfMass)]
            k = {"i": i, "typ": "andere", "punkte": punkte}
            if not e.isClosed():
                a, b = e.ParameterRange
                k["enden"] = [(tuple(e.valueAt(a)), tuple(e.tangentAt(a))), (tuple(e.valueAt(b)), tuple(e.tangentAt(b)))]
            if c.TypeId == "Part::GeomLine":
                k["typ"] = "linie"
                k["richtung"] = tuple((e.Vertexes[-1].Point - e.Vertexes[0].Point).normalize())
            elif c.TypeId == "Part::GeomCircle":
                k.update(typ="kreis", mitte=tuple(c.Center), d=2 * c.Radius, achse=tuple(c.Axis))
            out.append(k)
        return out

    @staticmethod
    def flaechen_daten(shape):
        out = []
        for i, f in enumerate(shape.Faces):
            s = f.Surface
            d = {"i": i, "typ": "andere", "punkt": tuple(f.CenterOfMass)}
            if s.TypeId == "Part::GeomPlane":
                u0, u1, v0, v1 = f.ParameterRange
                n = f.normalAt((u0 + u1) / 2, (v0 + v1) / 2)  # Surface.Axis + Orientation ist unzuverlässig
                d.update(typ="ebene", normale=tuple(round(x, 9) for x in n))
            elif s.TypeId == "Part::GeomCylinder":
                d.update(typ="zylinder", d=2 * s.Radius, achse=tuple(s.Axis))
            out.append(d)
        return out

    def kanten(self, auswahl, tangential=True):
        daten = self.kanten_daten(self.tip_shape())
        idx = bp.waehle_kanten(daten, auswahl)
        if tangential:
            idx = bp.tangential_erweitern(daten, idx)
        return [f"Edge{i + 1}" for i in idx]

    def flaechen(self, auswahl):
        idx = bp.waehle_flaechen(self.flaechen_daten(self.tip_shape()), auswahl)
        return [f"Face{i + 1}" for i in idx]

    @staticmethod
    def _umkehren(skizzen_normale, gewuenscht):
        return bp.dot(skizzen_normale, gewuenscht) < 0

    @staticmethod
    def _richtung(f):
        plus = bp.EBENEN[f["ebene"]][2]
        return plus if f["richtung"] == "+" else bp.mul(plus, -1)

    # ------------------------------------------------------------------ Features
    def block(self, f):
        sk = self.skizze(f["ebene"], f["versatz"], f["_schleifen"], f["id"] + "_Skizze")
        o = self.body.newObject("PartDesign::Pad", f["id"])
        o.Profile = sk
        o.Length = f["hoehe"]
        if f["richtung"] == "beide":
            _symmetrisch(o)
        else:
            o.Reversed = self._umkehren(DREHUNG[f["ebene"]][2], self._richtung(f))
        return o

    def tasche(self, f):
        sk = self.skizze(f["ebene"], f["versatz"], f["_schleifen"], f["id"] + "_Skizze")
        o = self.body.newObject("PartDesign::Pocket", f["id"])
        o.Profile = sk
        if f.get("durch"):
            o.Type = "ThroughAll"
        else:
            o.Length = f["tiefe"]
        if f["richtung"] == "beide":
            _symmetrisch(o)
        else:  # Tasche schneidet entgegen der Skizzennormale
            o.Reversed = self._umkehren(bp.mul(DREHUNG[f["ebene"]][2], -1), self._richtung(f))
        return o

    def _dreh(self, f, typ):
        sk = self.skizze(f["ebene"], 0, f["_schleifen"], f["id"] + "_Skizze")
        o = self.body.newObject(typ, f["id"])
        o.Profile = sk
        u = bp.EBENEN[f["ebene"]][0]
        o.ReferenceAxis = (sk, ["H_Axis" if bp.ACHSEN[f["achse"]] == u else "V_Axis"])
        o.Angle = f["winkel"]
        return o

    def drehteil(self, f):
        return self._dreh(f, "PartDesign::Revolution")

    def drehnut(self, f):
        return self._dreh(f, "PartDesign::Groove")

    def bohrung(self, f):
        r = f["d"] / 2
        sk = self.skizze(f["ebene"], f["versatz"], [[("kreis", p, r)] for p in f["_positionen"]],
                         f["id"] + "_Skizze")
        o = self.body.newObject("PartDesign::Hole", f["id"])
        o.Profile = sk
        g = f.get("_gewinde")
        if g:
            o.Threaded = True
            o.ThreadType = "ISOMetricProfile" if g["p"] == bp.REGELGEWINDE.get(g["d"]) else "ISOMetricFineProfile"
            groessen = o.getEnumerationsOfProperty("ThreadSize")
            name = next((s for s in groessen if s.replace(",", ".").startswith(f"M{g['d']:g}x{g['p']:g}")), None)
            name = name or next((s for s in groessen if s.startswith(f"M{g['d']:g}x")), None)
            if name is None:
                raise RuntimeError(f"FreeCAD kennt {g['name']} nicht")
            o.ThreadSize = name
            o.ModelThread = False
            if f.get("gewindetiefe"):
                o.ThreadDepthType = "Dimension"
                o.ThreadDepth = f["gewindetiefe"]
        else:
            o.Threaded = False
        o.Diameter = f["d"]
        if f.get("durch"):
            o.DepthType = "ThroughAll"
        else:
            o.DepthType = "Dimension"
            o.Depth = f["tiefe"]
        o.DrillPoint = "Flat"  # flacher Grund wie in SolidWorks (gleiches Volumen in beiden Programmen)
        if f.get("flachsenkung"):
            o.HoleCutType = "Counterbore"
            o.HoleCutDiameter = f["flachsenkung"]["d"]
            o.HoleCutDepth = f["flachsenkung"]["tiefe"]
        elif f.get("senkung"):
            o.HoleCutType = "Countersink"
            o.HoleCutDiameter = f["senkung"]["d"]
            o.HoleCutCountersinkAngle = f["senkung"]["winkel"]
        # Bohrung geht entgegen der Skizzennormale
        o.Reversed = self._umkehren(bp.mul(DREHUNG[f["ebene"]][2], -1), self._richtung(f))
        return o

    def _kantenfeature(self, f, typ):
        namen = self.kanten(f["kanten"], f.get("tangential", True))
        if not namen:
            raise RuntimeError(f"Kantenauswahl {json.dumps(f['kanten'])} trifft keine Kante")
        basis = self.body.Tip  # vor newObject merken – danach ist das neue Feature die Spitze
        o = self.body.newObject(typ, f["id"])
        o.Base = (basis, namen)
        f["_anzahl"] = len(namen)
        return o

    def fase(self, f):
        o = self._kantenfeature(f, "PartDesign::Chamfer")
        o.Size = f["laenge"]
        return o

    def verrundung(self, f):
        o = self._kantenfeature(f, "PartDesign::Fillet")
        o.Radius = f["r"]
        return o

    def schale(self, f):
        namen = self.flaechen(f["flaechen"])
        if not namen:
            raise RuntimeError(f"Flächenauswahl {json.dumps(f['flaechen'])} trifft keine Fläche")
        basis = self.body.Tip
        o = self.body.newObject("PartDesign::Thickness", f["id"])
        o.Base = (basis, namen)
        o.Value = f["dicke"]
        o.Join = "Intersection"
        o.Reversed = f.get("nach", "innen") == "innen"  # FreeCAD: Reversed=True heißt Wand nach innen
        return o

    def frei(self, f):
        code = f.get("freecad")
        if not code:
            raise RuntimeError("kein FreeCAD-Code in diesem frei-Feature")
        ns = self.namensraum()
        exec(compile(code, f["id"], "exec"), ns)
        return ns.get("ergebnis") or self.body.Tip

    def namensraum(self):
        return {"App": App, "Part": Part, "Sketcher": Sketcher, "doc": self.doc, "body": self.body,
                "bau": self, "bp": bp, "math": math, "V": V, "feature": self.feature}

    # ------------------------------------------------------------------ Ablauf
    def feature(self, f):
        """Baut ein Feature (dict wie im Plan, schon geprüft) und protokolliert die Wirkung."""
        try:
            bp.einzeln(f)
        except bp.BauplanFehler as ex:
            self.fehler += 1
            self.log.append({"id": f.get("id", "?"), "ok": False, "fehler": "; ".join(ex.befunde)})
            return None
        v0 = self.volumen()
        huelle0 = self.tip_shape().BoundBox if v0 else None
        vorher = {o.Name for o in self.doc.Objects}
        tip0 = self.body.Tip
        try:
            o = getattr(self, f["typ"])(f)
            self.doc.recompute()
            if o is not None and ("Invalid" in o.State or "Error" in o.State or not o.isValid()):
                raise RuntimeError(f"FreeCAD kann das Feature nicht bilden ({', '.join(o.State)})")
        except Exception as ex:
            self.fehler += 1
            self.log.append({"id": f["id"], "ok": False, "fehler": str(ex) or traceback.format_exc(limit=1)})
            self._zuruecksetzen(vorher, tip0)
            return None
        v1 = self.volumen()
        e = {"id": f["id"], "typ": f["typ"], "ok": True, "volumen": round(v1, 3), "delta": round(v1 - v0, 3)}
        if f.get("_anzahl"):
            e["kanten"] = f["_anzahl"]
        erwartung = {"block": 1, "drehteil": 1, "tasche": -1, "drehnut": -1, "bohrung": -1, "schale": -1}.get(f["typ"])
        if erwartung and (v1 - v0) * erwartung <= 1e-6:
            e["ok"] = False
            e["fehler"] = ("Feature ändert das Volumen nicht in die erwartete Richtung "
                           "(Richtung, Versatz oder Lage prüfen)")
            self.fehler += 1
        if f["typ"] == "schale" and huelle0 is not None:
            bb = self.tip_shape().BoundBox
            if f.get("nach", "innen") == "innen" and bb.DiagonalLength > huelle0.DiagonalLength + 1e-6:
                e["ok"] = False
                e["fehler"] = "Schale wächst nach außen – 'nach' prüfen"
                self.fehler += 1
        n_solids = len(self.tip_shape().Solids)
        if n_solids > 1:
            e["ok"] = False
            e["fehler"] = f"Körper zerfällt in {n_solids} Teile"
            self.fehler += 1
        gueltig = self.tip_shape().isValid()
        if e["ok"] and not gueltig and getattr(self, "_gueltig", True):
            e["warnung"] = ("Geometrie formal ungültig (entartete Kante/Fläche). Häufig: Außenradius ≤ Wandstärke "
                            "einer Schale (Innenradius wird 0) oder Flächen, die sich nur in einer Kante berühren")
        self._gueltig = gueltig
        self.log.append(e)
        return o

    def _zuruecksetzen(self, vorher, tip0):
        """Entfernt ein fehlgeschlagenes Feature, damit Datei und Vorschau den letzten gültigen Stand zeigen."""
        neu = [o for o in self.doc.Objects if o.Name not in vorher]
        for o in reversed(neu):
            try:
                if o in self.body.Group:
                    self.body.removeObject(o)
                self.doc.removeObject(o.Name)
            except Exception:
                pass
        if tip0 is not None:
            self.body.Tip = tip0
        self.doc.recompute()

    def bauen(self):
        for f in self.plan["features"]:
            self.feature(f)
            if self.fehler:
                break

    def abschluss(self, auftrag):
        shape = self.tip_shape()
        name = _dateiname(self.plan["name"])
        ordner = auftrag["ordner"]
        os.makedirs(ordner, exist_ok=True)
        b = {"cad": "freecad", "version": ".".join(App.Version()[:3]), "name": self.plan["name"],
             "features": self.log, "fehler": self.fehler, "dateien": [], "warnungen": []}
        if shape.isNull() or not shape.Solids:
            b["fehler"] += 1
            b["features"].append({"id": "ergebnis", "ok": False, "fehler": "kein Volumenkörper entstanden"})
            return b
        try:  # BoundBox ist bei Freiformflächen zu weit (Kontrollpunkte) -> exakte Hülle
            bb = shape.optimalBoundingBox(False, False)
        except Exception:
            bb = shape.BoundBox
        huelle = [bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax]
        b["gueltig"] = shape.isValid()
        b["koerper"] = len(shape.Solids)
        b["huelle"] = [round(x, 4) for x in huelle]
        b["groesse"] = [round(bb.XLength, 4), round(bb.YLength, 4), round(bb.ZLength, 4)]
        b["volumen_mm3"] = round(shape.Volume, 3)
        b["oberflaeche_mm2"] = round(shape.Area, 3)
        rho = bp.dichte(self.plan)
        if rho:
            b["masse_kg"] = round(shape.Volume * rho / 1e6, 4)
        if not b["gueltig"]:
            repariert = shape.copy()
            repariert.fix(1e-7, 1e-7, 1e-7)
            if repariert.isValid() and abs(repariert.Volume - shape.Volume) < 1e-6 * max(shape.Volume, 1):
                shape = repariert
                b["gueltig"] = "repariert"
                b["warnungen"].append("Geometrie war formal ungültig; für den Export repariert (Volumen unverändert). "
                                      "Ursache steht beim Feature.")
            else:
                b["fehler"] += 1
                b["warnungen"].append("Geometrie ist ungültig und nicht reparierbar (Part.isValid)")
        abw = bp.soll_vergleich(self.plan, huelle, shape.Volume)
        if abw:
            b["fehler"] += len(abw)
            b["soll_abweichungen"] = abw
        self.body.Tip.Visibility = True
        nativ = os.path.join(ordner, name + ".FCStd")
        self.doc.saveAs(nativ)
        b["dateien"].append(nativ)
        formate = [x.lower() for x in auftrag.get("formate", [])]
        if b["fehler"]:  # fehlerhafte Teile nicht als Austauschdatei weitergeben
            b["warnungen"].append("Austauschformate wegen Fehlern nicht erzeugt")
            formate = []
        if "step" in formate:
            p = os.path.join(ordner, name + ".step")
            if b["gueltig"] is True:
                Part.export([self.body], p)
            else:
                shape.exportStep(p)
            b["dateien"].append(p)
        if "stl" in formate or "3mf" in formate:
            import MeshPart
            m = MeshPart.meshFromShape(Shape=shape, LinearDeflection=auftrag.get("stl_toleranz", 0.01),
                                       AngularDeflection=math.radians(auftrag.get("stl_winkel", 5)), Relative=False)
            for fmt in ("stl", "3mf"):
                if fmt in formate:
                    p = os.path.join(ordner, f"{name}.{fmt}")
                    m.write(p)
                    b["dateien"].append(p)
            b["dreiecke"] = m.CountFacets
        if auftrag.get("vorschau_stl"):
            import MeshPart
            d = max(bb.DiagonalLength / 2000, 0.005)
            MeshPart.meshFromShape(Shape=shape, LinearDeflection=d, AngularDeflection=0.2,
                                   Relative=False).write(auftrag["vorschau_stl"])
        return b


def _symmetrisch(o):
    """Beidseitig symmetrisch; ab FreeCAD 1.1 über SideType (Midplane ist veraltet und geht beim Laden verloren)."""
    if "SideType" in o.PropertiesList:
        o.SideType = "Symmetric"
    else:
        o.Midplane = True


def _dokname(s):
    return "".join(c if c.isalnum() else "_" for c in s)[:40] or "Teil"


def _dateiname(s):
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in s).strip("_") or "Teil"


def main():
    bericht = {"cad": "freecad", "fehler": 1, "features": []}
    try:
        plan = bp.laden(A["plan"], skript=bool(A.get("skript")))
        bau = Bau(plan)
        bau.bauen()
        if A.get("skript") and not bau.fehler:
            ns = bau.namensraum()
            code = open(A["skript"], encoding="utf-8").read()
            try:
                exec(compile(code, A["skript"], "exec"), ns)
                bau.doc.recompute()
                bau.log.append({"id": "skript", "ok": True, "volumen": round(bau.volumen(), 3)})
            except Exception:
                bau.fehler += 1
                bau.log.append({"id": "skript", "ok": False, "fehler": traceback.format_exc(limit=3)})
        bericht = bau.abschluss(A)
    except bp.BauplanFehler as ex:
        bericht = {"cad": "freecad", "fehler": len(ex.befunde), "plan_befunde": ex.befunde, "features": []}
    except Exception:
        bericht["absturz"] = traceback.format_exc()
    with open(A["bericht"], "w", encoding="utf-8") as fh:
        json.dump(bericht, fh, ensure_ascii=False, indent=1)


main()
