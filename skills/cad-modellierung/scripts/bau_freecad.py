"""Bauskript FreeCAD: setzt einen Bauplan als PartDesign-Körper um (läuft in FreeCADCmd).

Wird von modell.py gestartet; der Auftrag (JSON) steht in der Umgebungsvariable CCW_AUFTRAG:
  {"plan": pfad, "ordner": ausgabeordner, "formate": ["step", "stl", "3mf"], "bericht": pfad,
   "vorschau_stl": pfad, "skripte": ordner dieses Skripts, "skript": optionales freies Skript,
   "parameter": {"L": 100} (optional), "name": anderer Teilename (optional)}
Jedes Feature wird einzeln gebaut und geprüft (gültig, Volumen ändert sich in die erwartete Richtung).
Nach dem Bau entsteht eine Merkmalsliste (Bohrungen, Zylinder, Radien) aus der fertigen Geometrie.
"""
import json
import math
import os
import sys
import time
import traceback

A = json.load(open(os.environ["CCW_AUFTRAG"], encoding="utf-8"))
sys.path.insert(0, A["skripte"])

import bauplan as bp  # noqa: E402
import FreeCAD as App  # noqa: E402
import Part  # noqa: E402
import Sketcher  # noqa: E402,F401

MAX_FEHLER = 3  # nach so vielen fehlgeschlagenen Features bricht der Bau ab
METHODE = {"import": "importieren"}  # 'import' ist in Python ein Schlüsselwort
SCHRIFTEN = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")


def V(p):
    return App.Vector(*(list(p) + [0] * (3 - len(p))))


def _matrix(x, y, z):
    """Drehmatrix mit den Spalten x, y, z."""
    return App.Matrix(x[0], y[0], z[0], 0, x[1], y[1], z[1], 0, x[2], y[2], z[2], 0, 0, 0, 0, 1)


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
        self.ursprung = {f.Role: f for f in self.body.Origin.OriginFeatures}
        self.xy = self.ursprung["XY_Plane"]
        self.log = []
        self.fehler = 0
        self.objekte = {}     # Feature-ID -> FreeCAD-Objekt (für Muster und Spiegeln)
        self.vorzeichen = {}  # Feature-ID -> +1 (trägt auf) / −1 (trägt ab)

    # ------------------------------------------------------------------ Hilfen
    def tip_shape(self):
        t = self.body.Tip
        return t.Shape if t is not None else Part.Shape()

    def volumen(self):
        s = self.tip_shape()
        return s.Volume if not s.isNull() else 0.0

    def skizze(self, ebene, versatz, schleifen, name):
        """Skizze in einer Planebene (Name oder geneigte Ebene als Objekt)."""
        o, u, v, _ = bp.rahmen(ebene, versatz)
        return self.skizze_rahmen(o, u, v, schleifen, name)

    def skizze_rahmen(self, o, u, v, schleifen, name):
        """Skizze mit Ursprung o und den Achsen u, v im Modell; Skizzennormale ist u × v."""
        sk = self.body.newObject("Sketcher::SketchObject", name)
        sk.AttachmentSupport = (self.xy, [""])
        sk.MapMode = "FlatFace"
        sk.AttachmentOffset = App.Placement(V(o), App.Rotation(_matrix(u, v, bp.kreuz(u, v))))
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
        if not idx:
            grund = bp.kanten_diagnose(daten, auswahl)
            raise RuntimeError(f"Kantenauswahl {json.dumps(auswahl, ensure_ascii=False)} trifft keine Kante"
                               + (f" – {grund}" if grund else ""))
        if tangential:
            idx = bp.tangential_erweitern(daten, idx)
        return [f"Edge{i + 1}" for i in idx]

    def flaechen(self, auswahl):
        daten = self.flaechen_daten(self.tip_shape())
        idx = bp.waehle_flaechen(daten, auswahl)
        if not idx:
            grund = bp.flaechen_diagnose(daten, auswahl)
            raise RuntimeError(f"Flächenauswahl {json.dumps(auswahl, ensure_ascii=False)} trifft keine Fläche"
                               + (f" – {grund}" if grund else ""))
        return [f"Face{i + 1}" for i in idx]

    @staticmethod
    def _umkehren(skizzen_normale, gewuenscht):
        return bp.dot(skizzen_normale, gewuenscht) < 0

    @staticmethod
    def _normale(ebene):
        """Skizzennormale u × v der Planebene (XZ: −Y, die Plus-Richtung des Plans ist dort +Y)."""
        _, u, v, _ = bp.rahmen(ebene)
        return bp.kreuz(u, v)

    @staticmethod
    def _richtung(f):
        plus = bp.rahmen(f["ebene"])[3]
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
            o.Reversed = self._umkehren(self._normale(f["ebene"]), self._richtung(f))
        if f.get("schraege"):  # FreeCAD: positiver Winkel weitet auf -> Vorzeichen drehen (positiv = verjüngt)
            o.TaperAngle = -f["schraege"]
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
            o.Reversed = self._umkehren(bp.mul(self._normale(f["ebene"]), -1), self._richtung(f))
        if f.get("schraege"):
            o.TaperAngle = -f["schraege"]
        return o

    def _dreh(self, f, typ):
        sk = self.skizze(f["ebene"], 0, f["_schleifen"], f["id"] + "_Skizze")
        o = self.body.newObject(typ, f["id"])
        o.Profile = sk
        u = bp.EBENEN[bp.basis(f["ebene"])][0]
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
            o.ModelThread = bool(f.get("gewinde_modelliert"))
            if f.get("gewinde_modelliert") and f.get("gewindespiel"):
                o.UseCustomThreadClearance = True
                o.CustomThreadClearance = f["gewindespiel"]
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
        if f.get("spitze"):  # 'tiefe' zählt bis zur Schulter, der Kegel kommt dazu (Zeichnungsüblich)
            o.DrillPoint = "Angled"
            o.DrillPointAngle = f["spitze"]
            o.DrillForDepth = False
        else:
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
        o.Reversed = self._umkehren(bp.mul(self._normale(f["ebene"]), -1), self._richtung(f))
        return o

    def _kantenfeature(self, f, typ):
        namen = self.kanten(f["kanten"], f.get("tangential", True))
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
        basis = self.body.Tip
        o = self.body.newObject("PartDesign::Thickness", f["id"])
        o.Base = (basis, namen)
        o.Value = f["dicke"]
        o.Join = "Intersection"
        o.Reversed = f.get("nach", "innen") == "innen"  # FreeCAD: Reversed=True heißt Wand nach innen
        return o

    # ---- Wiederholen: Muster und Spiegeln
    def _originale(self, f):
        objs = []
        for v in f["von"]:
            if v not in self.objekte:
                raise RuntimeError(f"Feature '{v}' fehlt (weiter oben fehlgeschlagen oder nicht im Plan)")
            objs.append(self.objekte[v])
        f["_vorzeichen"] = {self.vorzeichen.get(v) for v in f["von"]}
        return objs

    def _achse(self, name, durch, bezeichnung):
        """Ursprungsachse oder, bei 'durch', eine Bezugsachse durch diesen Punkt."""
        if not durch or all(abs(x) < 1e-9 for x in durch):
            return (self.ursprung[name + "_Axis"], [""])
        dl = self.body.newObject("PartDesign::Line", bezeichnung + "_Achse")
        dl.Placement = App.Placement(V(durch), App.Rotation(App.Vector(0, 0, 1), V(bp.ACHSEN[name])))
        return (dl, [""])

    def muster(self, f):
        orig = self._originale(f)
        if f.get("kreis"):
            k = f["kreis"]
            achse = self._achse(k["achse"].upper(), k.get("durch"), f["id"])
            o = self.body.newObject("PartDesign::PolarPattern", f["id"])
            o.Originals = orig
            o.Axis = achse
            if k.get("teilung"):
                o.Mode = "Spacing"
                o.Offset = abs(k["teilung"])
                o.Reversed = k["teilung"] < 0
            else:
                o.Mode = "Extent"
                o.Angle = abs(k.get("winkel", 360))
                o.Reversed = k.get("winkel", 360) < 0
            o.Occurrences = k["anzahl"]
        else:
            li = f["linear"] if isinstance(f["linear"], list) else [f["linear"]]
            o = self.body.newObject("PartDesign::LinearPattern", f["id"])
            o.Originals = orig
            for nr, m in enumerate(li):
                z = "" if nr == 0 else "2"
                name = str(m["richtung"]).upper()
                setattr(o, "Direction" + z, (self.ursprung[name.lstrip("+-") + "_Axis"], [""]))
                # Gesamtlänge statt Abstand: 'Spacing' wirkt in FreeCAD 1.1 in der zweiten Richtung nicht
                setattr(o, "Mode" + z, "Extent")
                setattr(o, "Length" + z, abs(m["abstand"]) * (m["anzahl"] - 1))
                setattr(o, "Occurrences" + z, m["anzahl"])
                setattr(o, "Reversed" + z, name.startswith("-") != (m["abstand"] < 0))
        self.body.Tip = o  # Transformationen werden nicht von selbst zur Spitze
        return o

    def spiegeln(self, f):
        orig = self._originale(f)
        if f["versatz"]:
            n = bp.EBENEN[f["ebene"]][2]
            ebene = self.body.newObject("PartDesign::Plane", f["id"] + "_Ebene")
            ebene.Placement = App.Placement(V(bp.mul(n, f["versatz"])), App.Rotation(App.Vector(0, 0, 1), V(n)))
            ref = (ebene, [""])
        else:
            ref = (self.ursprung[f["ebene"] + "_Plane"], [""])
        o = self.body.newObject("PartDesign::Mirrored", f["id"])
        o.Originals = orig
        o.MirrorPlane = ref
        self.body.Tip = o
        return o

    # ---- Ausformung und Zug
    def loft(self, f):
        sks = [self.skizze(s["ebene"], s["versatz"], s["_schleifen"], f"{f['id']}_Schnitt{k}")
               for k, s in enumerate(f["schnitte"], 1)]
        o = self.body.newObject("PartDesign::SubtractiveLoft" if f.get("abziehen") else "PartDesign::AdditiveLoft",
                                f["id"])
        o.Profile = sks[0]
        o.Sections = sks[1:]
        o.Ruled = bool(f.get("geregelt"))
        o.Closed = bool(f.get("geschlossen"))
        return o

    def zug(self, f):
        pf = f["pfad"]
        pfad = self.skizze(pf["ebene"], pf["versatz"], [f["_pfad"]], f["id"] + "_Pfad")
        o_, u, v, plus = bp.rahmen(pf["ebene"], pf["versatz"])
        p0, t2 = bp.pfad_start(f["_pfad"])
        start = bp.add(o_, bp.add(bp.mul(u, p0[0]), bp.mul(v, p0[1])))
        tang = bp.add(bp.mul(u, t2[0]), bp.mul(v, t2[1]))
        # Profil steht am Pfadanfang senkrecht zum Pfad: u = quer nach links, v = Plus-Richtung der Pfadebene
        profil = self.skizze_rahmen(start, bp.kreuz(plus, tang), plus, f["_schleifen"], f["id"] + "_Profil")
        o = self.body.newObject("PartDesign::SubtractivePipe" if f.get("abziehen") else "PartDesign::AdditivePipe",
                                f["id"])
        o.Profile = profil
        o.Spine = (pfad, [])
        o.Mode = "Frenet"
        o.Transition = "Right corner" if f["ecken"] == "scharf" else "Round corner"
        return o

    # ---- Text
    def text(self, f):
        import Draft
        schrift = f.get("schrift", "arialbd")
        if not os.path.isabs(schrift):
            schrift = os.path.join(SCHRIFTEN, schrift if schrift.lower().endswith((".ttf", ".otf")) else schrift + ".ttf")
        if not os.path.exists(schrift):
            raise RuntimeError(f"Schriftdatei {schrift} fehlt – 'schrift' z. B. arial, arialbd, consola oder voller Pfad")
        o_, u, v, plus = bp.rahmen(f["ebene"], f["versatz"])
        # Leseseite: bei Gravur dort, wo der Schnitt beginnt; bei erhabener Schrift dort, wohin sie wächst
        leser = plus if (f["art"] == "gravur") == (f["richtung"] == "-") else bp.mul(plus, -1)
        ns = bp.kreuz(u, v)
        x, y, z = (u, v, ns) if bp.dot(ns, leser) > 0 else (bp.mul(u, -1), v, bp.mul(ns, -1))
        w = math.radians(f.get("winkel", 0))
        xr = bp.add(bp.mul(x, math.cos(w)), bp.mul(y, math.sin(w)))
        yr = bp.add(bp.mul(x, -math.sin(w)), bp.mul(y, math.cos(w)))
        pos = bp.add(o_, bp.add(bp.mul(u, f["position"][0]), bp.mul(v, f["position"][1])))
        ss = Draft.make_shapestring(String=str(f["text"]), FontFile=schrift, Size=float(f["hoehe"]), Tracking=0)
        ss.Label = f["id"] + "_Text"
        ss.Justification = {"mitte": "Middle-Center", "links": "Middle-Left", "rechts": "Middle-Right"}[f["ausrichtung"]]
        ss.JustificationReference = "Cap Height"
        ss.Placement = App.Placement(V(pos), App.Rotation(_matrix(xr, yr, z)))
        self.body.addObject(ss)
        self.doc.recompute()
        o = self.body.newObject("PartDesign::Pad" if f["art"] == "erhaben" else "PartDesign::Pocket", f["id"])
        o.Profile = ss
        o.Length = f["tiefe"]
        return o

    # ---- Fremdteil als Ausgangskörper
    def importieren(self, f):
        sh = Part.Shape()
        sh.read(f["_datei"])
        if len(sh.Solids) != 1:
            raise RuntimeError(f"{os.path.basename(f['_datei'])} enthält {len(sh.Solids)} Volumenkörper – "
                               f"gebraucht wird genau einer (Baugruppen vorher trennen, Flächenmodelle schließen)")
        s = sh.Solids[0].copy()
        for achse, grad in f.get("drehen", []):
            s.rotate(App.Vector(0, 0, 0), V(bp.ACHSEN[str(achse).upper()]), grad)
        if f.get("verschieben"):
            s.translate(V(f["verschieben"]))
        if not s.isValid():
            f["_warnung"] = "importierte Geometrie ist formal ungültig – Folgefeatures können scheitern"
        roh = self.doc.addObject("Part::Feature", f["id"] + "_Datei")
        roh.Shape = s
        roh.Visibility = False
        self.body.BaseFeature = roh
        self.doc.recompute()
        return self.body.Tip

    def frei(self, f):
        code = f.get("freecad")
        if not code:
            raise RuntimeError("kein FreeCAD-Code in diesem frei-Feature")
        ns = self.namensraum()
        exec(compile(code, f["id"], "exec"), ns)
        return ns.get("ergebnis") or self.body.Tip

    def namensraum(self):
        return {"App": App, "Part": Part, "Sketcher": Sketcher, "doc": self.doc, "body": self.body,
                "bau": self, "bp": bp, "math": math, "V": V, "feature": self.feature,
                "P": dict(self.plan.get("_parameter", {}))}

    # ------------------------------------------------------------------ Ablauf
    def _erwartung(self, f):
        """+1: Feature muss Volumen aufbauen, −1: abtragen, None: offen."""
        t = f["typ"]
        if t in ("loft", "zug"):
            return -1 if f.get("abziehen") else 1
        if t == "text":
            return 1 if f["art"] == "erhaben" else -1
        if t in ("muster", "spiegeln"):
            vz = f.get("_vorzeichen", set())
            return vz.pop() if len(vz) == 1 and None not in vz else None
        return {"block": 1, "drehteil": 1, "import": 1, "tasche": -1, "drehnut": -1, "bohrung": -1,
                "schale": -1}.get(t)

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
        beginn = time.time()
        try:
            o = getattr(self, METHODE.get(f["typ"], f["typ"]))(f)
            self.doc.recompute()
            if o is not None and ("Invalid" in o.State or "Error" in o.State or not o.isValid()):
                raise RuntimeError(f"FreeCAD kann das Feature nicht bilden ({', '.join(o.State)})")
        except Exception as ex:
            self.fehler += 1
            self.log.append({"id": f["id"], "typ": f["typ"], "ok": False,
                             "fehler": str(ex) or traceback.format_exc(limit=1)})
            self._zuruecksetzen(vorher, tip0)
            return None
        v1 = self.volumen()
        e = {"id": f["id"], "typ": f["typ"], "ok": True, "volumen": round(v1, 3), "delta": round(v1 - v0, 3)}
        if f.get("_anzahl"):
            e["kanten"] = f["_anzahl"]
        if f.get("_warnung"):
            e["warnung"] = f["_warnung"]
        erwartung = self._erwartung(f)
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
            e["fehler"] = (f"Körper zerfällt in {n_solids} Teile (das Feature berührt den Körper nicht oder "
                           f"trennt ihn durch)")
            self.fehler += 1
        e["sekunden"] = round(time.time() - beginn, 1)
        gueltig = self.tip_shape().isValid()
        e["sekunden_pruefung"] = round(time.time() - beginn - e["sekunden"], 1)
        if e["ok"] and not gueltig and getattr(self, "_gueltig", True):
            e["warnung"] = ("Geometrie formal ungültig (entartete Kante/Fläche). Häufig: Außenradius ≤ Wandstärke "
                            "einer Schale (Innenradius wird 0) oder Flächen, die sich nur in einer Kante berühren")
        self._gueltig = gueltig
        self.log.append(e)
        if e["ok"]:
            self.objekte[f["id"]] = o
            self.vorzeichen[f["id"]] = 1 if v1 > v0 else -1
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
        """Baut alle Features. Nach einem Fehler geht es weiter (das fehlerhafte Feature ist entfernt),
        damit ein Lauf möglichst alle Fehler zeigt; spätere Fehler können dann Folgefehler sein."""
        for f in self.plan["features"]:
            vor = self.fehler
            self.feature(f)
            if self.fehler > vor and vor:
                self.log[-1]["folge"] = True
            if self.fehler >= MAX_FEHLER:
                rest = len(self.plan["features"]) - self.plan["features"].index(f) - 1
                if rest:
                    self.log.append({"id": "abbruch", "ok": True,
                                     "warnung": f"nach {MAX_FEHLER} Fehlern abgebrochen, {rest} Features nicht gebaut"})
                break

    def abschluss(self, auftrag):
        uhr, zeiten = [time.time()], {}

        def stopp(name):
            zeiten[name] = round(time.time() - uhr[0], 1)
            uhr[0] = time.time()
        shape = self.tip_shape()
        name = _dateiname(self.plan["name"])
        ordner = auftrag["ordner"]
        os.makedirs(ordner, exist_ok=True)
        b = {"cad": "freecad", "version": ".".join(App.Version()[:3]), "name": self.plan["name"],
             "features": self.log, "fehler": self.fehler, "dateien": [], "warnungen": []}
        b["zeiten"] = zeiten
        zeiten["features"] = round(sum(f.get("sekunden", 0) + f.get("sekunden_pruefung", 0) for f in self.log), 1)
        if self.plan.get("_parameter"):
            b["parameter"] = self.plan["_parameter"]
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
        stopp("huelle")
        try:
            b["merkmale"] = merkmale(shape)
        except Exception:
            b["warnungen"].append("Merkmalsliste nicht ermittelt: " + traceback.format_exc(limit=1).strip()[-200:])
        stopp("merkmale")
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
        if self.fehler:  # Hülle eines halb gebauten Teils sagt nichts aus
            b["warnungen"].append("Soll-Vergleich übersprungen, weil Features fehlgeschlagen sind")
        else:
            abw = bp.soll_vergleich(self.plan, huelle, shape.Volume)
            if abw:
                b["fehler"] += len(abw)
                b["soll_abweichungen"] = abw
        self.body.Tip.Visibility = True
        nativ = os.path.join(ordner, name + ".FCStd")
        self.doc.saveAs(nativ)
        b["dateien"].append(nativ)
        stopp("speichern")
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
            stopp("step")
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
            stopp("netz")
        if auftrag.get("vorschau_stl"):
            import MeshPart
            d = max(bb.DiagonalLength / 2000, 0.005)
            MeshPart.meshFromShape(Shape=shape, LinearDeflection=d, AngularDeflection=0.2,
                                   Relative=False).write(auftrag["vorschau_stl"])
            stopp("vorschaunetz")
        return b


# ---------------------------------------------------------------------------- Merkmalsliste
def _achsname(a):
    """'X', 'Y', 'Z' für achsparallele Richtungen, sonst None."""
    for n, i in (("X", 0), ("Y", 1), ("Z", 2)):
        if abs(abs(a[i]) - 1) < 1e-6:
            return n
    return None


def merkmale(shape):
    """Liest aus der fertigen Geometrie, was gebaut wurde: Bohrungen, Außenzylinder, Radien, Kegel.

    Damit lässt sich das Ergebnis mit der Vorgabe als Zahlen vergleichen (Anzahl, Ø, Lage, Tiefe),
    statt sie aus dem Vorschaubild abzulesen."""
    zyl, kegel = {}, {}
    for f in shape.Faces:
        s = f.Surface
        if s.TypeId not in ("Part::GeomCylinder", "Part::GeomCone"):
            continue
        ax = App.Vector(s.Axis)
        ax.normalize()
        gross = max(range(3), key=lambda i: abs(ax[i]))
        if ax[gross] < 0:  # Achsrichtung vereinheitlichen
            ax = ax * -1
        c = App.Vector(s.Center) if s.TypeId == "Part::GeomCylinder" else App.Vector(s.Apex)
        fuss = c - ax * c.dot(ax)  # Achspunkt, der dem Ursprung am nächsten liegt
        u0, u1, v0, v1 = f.ParameterRange
        p = f.valueAt((u0 + u1) / 2, (v0 + v1) / 2)
        n = f.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
        radial = p - (fuss + ax * (p - fuss).dot(ax))
        innen = n.dot(radial) < 0
        name = _achsname(ax)
        if name:  # achsparallel: die Hülle der Fläche ist entlang der Achse genau
            i = "XYZ".index(name)
            bb = f.BoundBox
            lo, hi = (bb.XMin, bb.YMin, bb.ZMin)[i], (bb.XMax, bb.YMax, bb.ZMax)[i]
        else:
            lagen = [v.Point.dot(ax) for v in f.Vertexes] or [p.dot(ax)]
            lo, hi = min(lagen), max(lagen)
        ort = (round(ax.x, 5), round(ax.y, 5), round(ax.z, 5), round(fuss.x, 3), round(fuss.y, 3), round(fuss.z, 3))
        if s.TypeId == "Part::GeomCylinder":
            zyl.setdefault(ort + (round(2 * s.Radius, 4), innen), []).append((lo, hi, abs(u1 - u0), 0, 0))
        else:
            rad = [(v.Point - (fuss + ax * (v.Point - fuss).dot(ax))).Length for v in f.Vertexes]
            if rad:
                kegel.setdefault(ort + (round(2 * math.degrees(abs(s.SemiAngle)), 2), innen), []).append(
                    (lo, hi, abs(u1 - u0), 2 * min(rad), 2 * max(rad)))

    def abschnitte(flaechen):
        """Fasst Teilflächen derselben Fläche zusammen, die sich entlang der Achse berühren oder überlappen.
        Gibt je Abschnitt (von, bis, mittlerer Umfangswinkel, d_klein, d_gross) zurück."""
        out = []
        for lo, hi, w, d0, d1 in sorted(flaechen):
            if out and lo <= out[-1][1] + 1e-6:
                a = out[-1]
                a[1], a[2] = max(a[1], hi), a[2] + w * (hi - lo)
                a[3], a[4] = min(a[3], d0), max(a[4], d1)
            else:
                out.append([lo, hi, w * (hi - lo), d0, d1])
        return [(a[0], a[1], a[2] / max(a[1] - a[0], 1e-9), a[3], a[4]) for a in out if a[1] - a[0] > 1e-9]

    def lage(ort):
        """Lage der Achse: bei achsparallelen Achsen die zwei Koordinaten quer dazu."""
        ax, fuss = ort[:3], ort[3:6]
        name = _achsname(ax)
        if name:
            return name, [round(fuss[i] + 0.0, 3) for i in range(3) if "XYZ"[i] != name]
        return "schräg", [round(x + 0.0, 3) for x in fuss]

    voll = 2 * math.pi - 0.02
    gruppen, radien = {}, {}
    for schluessel, flaechen in zyl.items():
        d, innen = schluessel[6], schluessel[7]
        for lo, hi, w, _, _ in abschnitte(flaechen):
            if w > math.pi + 0.02:  # Bohrung oder Zapfen; offen, wenn eine Nut oder Fläche den Umfang anschneidet
                name, wo = lage(schluessel)
                richt = tuple(schluessel[:3]) if name == "schräg" else None
                offen = None if w > voll else int(round(math.degrees(w)))
                k = (innen, d, name, round(lo + 0.0, 3), round(hi + 0.0, 3), richt, offen)
                gruppen.setdefault(k, []).append(wo)
            else:
                radien[(round(d / 2, 4), innen)] = radien.get((round(d / 2, 4), innen), 0) + 1
    out = {"bohrungen": [], "zylinder": [], "radien": [], "kegel": []}
    for (innen, d, name, lo, hi, richt, offen), orte in sorted(gruppen.items(),
                                                              key=lambda kv: (not kv[0][0], kv[0][1], kv[0][3])):
        g = {"d": d, "achse": name, "von": lo, "bis": hi, "anzahl": len(orte), "bei": sorted(orte)}
        if richt:
            g["richtung"] = list(richt)
        if offen:
            g["umfang_grad"] = offen
        out["bohrungen" if innen else "zylinder"].append(g)
    for (r, innen), n in sorted(radien.items()):
        out["radien"].append({"r": r, "innen": innen, "anzahl": n})
    kg = {}
    for schluessel, flaechen in kegel.items():
        winkel, innen = schluessel[6], schluessel[7]
        for lo, hi, w, d0, d1 in abschnitte(flaechen):
            if w > voll:
                k = (innen, winkel, round(d0, 3), round(d1, 3), lage(schluessel)[0])
                kg[k] = kg.get(k, 0) + 1
    for (innen, winkel, dmin, dmax, name), n in sorted(kg.items(), key=lambda kv: (not kv[0][0], kv[0][3])):
        out["kegel"].append({"winkel": winkel, "d_klein": dmin, "d_gross": dmax, "achse": name, "innen": innen,
                             "anzahl": n})
    return {k: v for k, v in out.items() if v}


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
        plan = bp.laden(A["plan"], skript=bool(A.get("skript")), parameter=A.get("parameter"))
        if A.get("name"):
            plan["name"] = A["name"]
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
