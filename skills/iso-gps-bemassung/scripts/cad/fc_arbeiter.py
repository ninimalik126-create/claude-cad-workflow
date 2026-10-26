"""Arbeitsskript im FreeCAD-Python für cad_freecad.py (Analyse, TechDraw-Zeichnung, Export).

Auftrag als JSON in der Umgebungsvariable CCW_FC: {"modus": "analysieren"|"zeichnen"|"export", ...,
"ergebnis": pfad}. 'zeichnen' und 'export' brauchen die FreeCAD-Oberfläche (unsichtbar gestartet mit
QT_QPA_PLATFORM=offscreen), weil TechDraw PDFs nur über die Oberfläche ausgibt.

TechDraw-Konventionen (gemessen, FreeCAD 1.1):
- projectPoint(P) liefert die unskalierte Projektion (x = P·XDirection, y = P·(Direction × XDirection)).
- Sichtbare Ecken/Kanten liegen skaliert, um getGeometricCenter() zentriert und mit gespiegeltem y vor.
- Blattpunkt = (X, Y) der Ansicht + (Projektion − Projektion des Mittelpunkts) × Maßstab, y nach oben.
- Maß-X/Y = Lage der Maßzahl relativ zum Ansichtsmittelpunkt in Blatt-mm.
- Rahmen und Schriftfeld erscheinen im PDF erst, wenn die Blattansicht geöffnet wurde.
- Kleine Toleranzen formatiert FreeCAD in µm -> Toleranztexte werden selbst gesetzt (ArbitraryTolerances).
"""
import json
import math
import os
import sys
import time
import traceback

A = json.load(open(os.environ["CCW_FC"], encoding="utf-8"))
sys.path.insert(0, A["skripte"])
sys.path.insert(0, os.path.dirname(A["skripte"]))

import FreeCAD as App  # noqa: E402

from cad_basis import achsname, dot, norm, runde, zusammenfassen  # noqa: E402

SHEETS = {"A4": (210, 297, "A4_Portrait"), "A4H": (210, 297, "A4_Portrait"), "A3": (420, 297, "A3_Landscape"),
          "A2": (594, 420, "A2_Landscape"), "A1": (841, 594, "A1_Landscape"), "A0": (1189, 841, "A0_Landscape")}
RICHTUNGEN = {  # Blickrichtung (zum Betrachter), x-Richtung auf dem Blatt; wie Bauplan/Vorschau (Z oben)
    "vorne": ((0, -1, 0), (1, 0, 0)), "hinten": ((0, 1, 0), (-1, 0, 0)),
    "oben": ((0, 0, 1), (1, 0, 0)), "unten": ((0, 0, -1), (1, 0, 0)),
    "rechts": ((1, 0, 0), (0, 1, 0)), "links": ((-1, 0, 0), (0, -1, 0)),
    "iso": ((1, -1, 1), (1, 1, 0)),
}
FELDER = {  # Auftragsschlüssel -> Feld im deutschen ISO-7200-Schriftfeld von FreeCAD
    "Benennung": "drawing_title", "Zeichnungsnummer": "Sachnummer", "Gezeichnet": "author_name",
    "Genehmigt": "Genehmiger", "Eigentuemer": "owner_1", "Datum": "fc-date", "Projekt": "projekt",
    "Dokumentenart": "document_type",
}
H = 3.5


def T(s):
    """Text für TechDraw: osifont hat kein Minuszeichen U+2212 (erscheint als Kästchen)."""
    return str(s).replace("−", "-")


def V(p):
    return App.Vector(*p)


def kreuz(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def zahl(v, n=None):
    n = nachkomma(v) if n is None else n
    return f"{v:.{n}f}".replace(".", ",")


def nachkomma(v):
    for n in range(4):
        if abs(round(v, n) - v) < 1e-6:
            return n
    return 4


def koerper(doc):
    for o in doc.Objects:
        if o.TypeId == "PartDesign::Body" and not o.Shape.isNull() and o.Shape.Solids:
            return o
    kand = [o for o in doc.Objects if hasattr(o, "Shape") and not o.Shape.isNull() and o.Shape.Solids
            and not o.InList]
    if not kand:
        raise RuntimeError("Kein Volumenkörper im Dokument")
    return max(kand, key=lambda o: o.Shape.Volume)


# ---------------------------------------------------------------------------- Analyse
def _achse(a_raw, o_raw):
    a = norm(list(a_raw))
    i = max(range(3), key=lambda k: abs(a[k]))
    if a[i] < 0:
        a = [-x for x in a]
    o = list(o_raw)
    t = dot(o, a)
    return a, [o[k] - t * a[k] for k in range(3)]


def _bereich(face, o, a):
    pts = []
    for e in face.Edges:
        try:
            pts += e.discretize(9)
        except Exception:
            pts += [v.Point for v in e.Vertexes]
    ts = [dot([p.x - o[0], p.y - o[1], p.z - o[2]], a) for p in pts]
    return runde([min(ts), max(ts)], 3) if ts else [0.0, 0.0]


def _art(face, o, a):
    u0, u1, v0, v1 = face.ParameterRange
    u, v = (u0 + u1) / 2, (v0 + v1) / 2
    p = face.valueAt(u, v)
    n = face.normalAt(u, v)  # berücksichtigt die Flächenorientierung (zeigt aus dem Material)
    q = [p.x - o[0], p.y - o[1], p.z - o[2]]
    t = dot(q, a)
    radial = [q[k] - t * a[k] for k in range(3)]
    return "aussen" if dot(radial, [n.x, n.y, n.z]) > 0 else "innen"


def flaeche(face, fid):
    s = face.Surface
    bb = face.BoundBox
    box = [bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax]
    rec = {"id": fid, "flaeche_mm2": runde(face.Area, 2), "kanten": len(face.Edges), "box": runde(box, 3)}
    t = s.TypeId
    if t == "Part::GeomPlane":
        u0, u1, v0, v1 = face.ParameterRange
        n = face.normalAt((u0 + u1) / 2, (v0 + v1) / 2)  # Surface.Axis + Orientation ist unzuverlässig
        nrm = norm([n.x, n.y, n.z])
        pt = face.CenterOfMass
        pt = [pt.x, pt.y, pt.z]
        rec.update(typ="ebene", normale=runde(nrm, 6), lage=runde(dot(pt, nrm), 4))
        ax = achsname(nrm)
        if ax:
            rec["normale_achse"] = ax
            rec[ax[1].lower()] = runde(pt["XYZ".index(ax[1])], 4)
    elif t == "Part::GeomCylinder":
        a, o = _achse(s.Axis, s.Center)
        u0, u1 = face.ParameterRange[0:2]
        rec.update(typ="zylinder", art=_art(face, o, a), d=runde(2 * s.Radius, 4),
                   achse={"punkt": runde(o, 4), "richtung": runde(a, 6)}, bereich=_bereich(face, o, a),
                   winkel=runde(math.degrees(u1 - u0), 1))
        ax = achsname(a)
        if ax:
            rec["achse"]["name"] = ax[1]
    elif t == "Part::GeomCone":
        a, o = _achse(s.Axis, s.Apex)
        rec.update(typ="kegel", art=_art(face, o, a), halber_winkel_grad=runde(math.degrees(s.SemiAngle), 4),
                   achse={"punkt": runde(o, 4), "richtung": runde(a, 6)}, bereich=_bereich(face, o, a))
    elif t == "Part::GeomSphere":
        c = s.Center
        rec.update(typ="kugel", mitte=runde([c.x, c.y, c.z], 4), d=runde(2 * s.Radius, 4))
    elif t == "Part::GeomToroid":
        c, ax = s.Center, s.Axis
        rec.update(typ="torus", mitte=runde([c.x, c.y, c.z], 4), achse=runde(norm([ax.x, ax.y, ax.z]), 6),
                   r_gross=runde(s.MajorRadius, 4), r_klein=runde(s.MinorRadius, 4))
    else:
        rec["typ"] = "freiform"
    return rec


def analysieren(pfad, doc=None):
    doc = doc or App.openDocument(pfad)
    obj = koerper(doc)
    sh = obj.Shape
    flaechen = [flaeche(f, f"F{i}") for i, f in enumerate(sh.Faces, 1)]
    bb = sh.optimalBoundingBox(False, False) if hasattr(sh, "optimalBoundingBox") else sh.BoundBox
    werkstoff = getattr(obj, "Werkstoff", None)
    dichte = getattr(obj, "Dichte", 0) or None
    feats = [{"name": o.Label, "typ": o.TypeId.split("::")[-1]} for o in getattr(obj, "Group", [])
             if o.TypeId.startswith("PartDesign::") and "Sketch" not in o.TypeId]
    modell = {"cad": "freecad", "datei": os.path.abspath(pfad), "einheit": "mm", "werkstoff": werkstoff,
              "masse_kg": runde(sh.Volume * dichte / 1e6, 4) if dichte else None,
              "volumen_mm3": runde(sh.Volume, 1),
              "huelle_mm": runde([bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax], 3),
              "eigenschaften": {}, "features": feats, "flaechen": flaechen}
    modell["merkmale"] = zusammenfassen(flaechen)
    return modell


# ---------------------------------------------------------------------------- Zeichnung
class Protokoll:
    def __init__(self):
        self.eintraege = []

    def eintrag(self, art, ok, info):
        self.eintraege.append({"art": art, "ok": bool(ok), "info": info})

    def ok(self, art, info):
        self.eintrag(art, True, info)

    def fehler(self, art, info):
        self.eintrag(art, False, info)

    def ergebnis(self, ziel, **extra):
        return dict({"zeichnung": ziel, "fehler": sum(1 for e in self.eintraege if not e["ok"]),
                     "schritte": self.eintraege}, **extra)


def warten(bedingung, sek=30):
    from PySide import QtWidgets
    t0 = time.time()
    while not bedingung() and time.time() - t0 < sek:
        QtWidgets.QApplication.processEvents()
        time.sleep(0.05)
    return bedingung()


def massstab(s):
    a, b = str(s).replace("/", ":").split(":")
    return float(a.replace(",", ".")), float(b.replace(",", "."))


class Ansicht:
    def __init__(self, v, D, X):
        self.v = v
        self.D = norm(list(D))
        self.X = norm(list(X))
        self.Y = kreuz(self.D, self.X)
        self.s = v.Scale
        c = v.getGeometricCenter()
        self.c = (dot([c.x, c.y, c.z], self.X), dot([c.x, c.y, c.z], self.Y))

    def proj(self, P):
        return dot(P, self.X), dot(P, self.Y)

    def blatt(self, P):
        px, py = self.proj(P)
        return [self.v.X.Value + (px - self.c[0]) * self.s, self.v.Y.Value + (py - self.c[1]) * self.s]

    def lokal(self, P):
        px, py = self.proj(P)
        return (px - self.c[0]) * self.s, -(py - self.c[1]) * self.s

    def blatt_aus_lokal(self, lx, ly):
        return [self.v.X.Value + lx, self.v.Y.Value - ly]

    def richtung(self, d):
        x, y = dot(d, self.X), dot(d, self.Y)
        n = math.hypot(x, y) or 1.0
        return [x / n, y / n]

    def ecken(self):
        return [(i, (q.x, q.y)) for i, q in enumerate(self.v.getVisibleVertexes())]

    def ecke_bei(self, lx, ly, tol=0.05):
        ecken = self.ecken()
        i, p = min(ecken, key=lambda t: (t[1][0] - lx) ** 2 + (t[1][1] - ly) ** 2)
        if math.hypot(p[0] - lx, p[1] - ly) > tol * max(self.s, 1) + 0.5:
            raise RuntimeError(f"keine sichtbare Ecke bei {lx / self.s:.2f}/{-ly / self.s:.2f} (Ansichtsmaß)")
        return i, p

    def umriss(self):
        """Blatt-Hülle der sichtbaren Geometrie [xmin, ymin, xmax, ymax]."""
        xs, ys = [], []
        for e in self.v.getVisibleEdges():
            bb = e.BoundBox
            xs += [bb.XMin, bb.XMax]
            ys += [bb.YMin, bb.YMax]
        x0, y0 = self.blatt_aus_lokal(min(xs), max(ys))
        x1, y1 = self.blatt_aus_lokal(max(xs), min(ys))
        return [x0, y0, x1, y1]

    def zylinderpunkte(self, f, bei=None):
        """3D-Punkte: (oben, unten, seitlich). Blick entlang der Achse: (Randpunkt, Mitte, False)."""
        a, o = f["achse"]["richtung"], f["achse"]["punkt"]
        r = f.get("d", 0) / 2
        t = bei if bei is not None else sum(f["bereich"]) / 2
        c = [o[k] + t * a[k] for k in range(3)]
        if abs(dot(a, self.D)) > 0.9:
            return [c[k] + r * self.X[k] for k in range(3)], c, False
        u = norm(kreuz(self.D, a))
        if dot(u, self.Y) < -1e-9 or (abs(dot(u, self.Y)) < 1e-9 and dot(u, self.X) < 0):
            u = [-x for x in u]
        return [c[k] + r * u[k] for k in range(3)], [c[k] - r * u[k] for k in range(3)], True


class Zeichner:
    def __init__(self, auftrag, basis):
        import TechDraw  # noqa: F401
        self.auftrag, self.basis = auftrag, basis
        self.prot = Protokoll()
        teil = self._pfad(auftrag["teil"])
        self.teil = teil
        self.doc = App.openDocument(teil)
        self.modell = analysieren(teil, self.doc)
        self.fl = {f["id"]: f for f in self.modell["flaechen"]}
        self.obj = koerper(self.doc)
        self.ansichten, self.masse = {}, {}

    def _pfad(self, p):
        return os.path.abspath(p if os.path.isabs(p) else os.path.join(self.basis, p))

    def _f(self, fid):
        if fid not in self.fl:
            raise RuntimeError(f"Fläche {fid} nicht in der Analyse")
        return self.fl[fid]

    # ---- Blatt
    def blatt(self):
        b = self.auftrag.get("blatt", {})
        fmt = str(b.get("format", "A3")).upper()
        if fmt not in SHEETS:
            raise RuntimeError(f"Blattformat {fmt} unbekannt ({', '.join(SHEETS)})")
        self.W, self.Hh, stamm = SHEETS[fmt]
        self.s1, self.s2 = massstab(b.get("massstab", "1:1"))
        page = self.doc.addObject("TechDraw::DrawPage", "Zeichnung")
        tpl = self.doc.addObject("TechDraw::DrawSVGTemplate", "Schriftfeld")
        if b.get("vorlage"):
            datei = self._pfad(b["vorlage"])
        else:
            tdir = os.path.join(App.getResourceDir(), "Mod", "TechDraw", "Templates", "ISO")
            datei = os.path.join(tdir, "localized", "de", f"{stamm}_ISO7200_DE.svg")
            if not os.path.exists(datei):
                datei = os.path.join(tdir, f"{stamm}_ISO5457_minimal.svg")
        tpl.Template = datei
        page.Template = tpl
        self.page, self.tpl = page, tpl
        self.prot.ok("Blatt", f"{fmt}, {zahl(self.s1)}:{zahl(self.s2)}, Vorlage {os.path.basename(datei)}")

    # ---- Ansichten
    def ansichten_anlegen(self):
        for va in self.auftrag.get("ansichten", []):
            vid = va.get("id", va.get("richtung", "vorne"))
            r = va.get("richtung", "vorne")
            if isinstance(r, dict):
                D, X = r["blick"], r["x"]
            elif r in RICHTUNGEN:
                D, X = RICHTUNGEN[r]
            else:
                self.prot.fehler("Ansicht", f"{vid}: Richtung '{r}' unbekannt ({', '.join(RICHTUNGEN)})")
                continue
            v = self.doc.addObject("TechDraw::DrawViewPart", "Ansicht_" + vid)
            self.page.addView(v)
            v.Source = [self.obj]
            v.Direction = V(D)
            v.XDirection = V(X)
            v.ScaleType = "Custom"
            s1, s2 = massstab(va["massstab"]) if va.get("massstab") else (self.s1, self.s2)
            v.Scale = s1 / s2
            x, y = va.get("pos", [self.W / 2, self.Hh / 2])
            v.X, v.Y = x, y
            self.ansichten[vid] = (v, D, X, r)
        self.doc.recompute()
        for vid, (v, D, X, r) in list(self.ansichten.items()):
            if not warten(lambda: bool(v.getVisibleEdges())):
                self.prot.fehler("Ansicht", f"{vid}: keine Geometrie berechnet")
                del self.ansichten[vid]
                continue
            self.ansichten[vid] = Ansicht(v, D, X)
            self.prot.ok("Ansicht", f"{vid}: {r if isinstance(r, str) else 'frei'} bei "
                                    f"{v.X.Value:.0f}/{v.Y.Value:.0f} mm, Maßstab {zahl(v.Scale)}")

    def _ansicht(self, spec):
        vid = spec.get("ansicht") or next(iter(self.ansichten))
        if vid not in self.ansichten:
            raise RuntimeError(f"Ansicht '{vid}' existiert nicht")
        return self.ansichten[vid]

    # ---- Mittellinien
    @staticmethod
    def _sichtbar(a, P, tol=0.3):
        """Liegt der Modellpunkt P auf einer sichtbaren Kante der Ansicht?"""
        import Part
        lx, ly = a.lokal(P)
        pt = Part.Vertex(V((lx, ly, 0)))
        return any(e.distToShape(pt)[0] < tol for e in a.v.getVisibleEdges())

    @staticmethod
    def _randpunkte(a, f):
        """Prüfpunkte auf dem Zylinderrand in vier Richtungen (Halbzylinder liegen nur auf einer Seite)."""
        o, d = f["achse"]["punkt"], f["achse"]["richtung"]
        t = sum(f["bereich"]) / 2
        c = [o[k] + t * d[k] for k in range(3)]
        r = f["d"] / 2
        if abs(dot(d, a.D)) > 0.9:
            return [[c[k] + s * r * e[k] for k in range(3)] for e in (a.X, a.Y) for s in (1, -1)]
        oben, unten, _ = a.zylinderpunkte(f)
        return [oben, unten]

    def mittellinien(self):
        """Mittellinien nur für Bohrungen, Wellen und Bögen ab 180° (keine Eckenradien) und nur sichtbare."""
        for vid, a in self.ansichten.items():
            n = 0
            for achse in self.modell["merkmale"]["achsen"]:
                fl = [self.fl[i] for i in achse["flaechen"] if self.fl[i]["typ"] == "zylinder"
                      and self.fl[i].get("winkel", 360) >= 179]
                if not fl:
                    continue
                rmax = max(f.get("d", 0) for f in fl) / 2
                d = achse["richtung"]
                c0 = achse["punkt"]
                sicht = [f for f in fl if any(self._sichtbar(a, p) for p in self._randpunkte(a, f))]
                if not sicht:
                    continue
                if abs(dot(d, a.D)) > 0.9:  # Blick entlang der Achse: Mittelkreuz
                    t = sum(fl[0]["bereich"]) / 2
                    c = [c0[k] + t * d[k] for k in range(3)]
                    ue = rmax + 2 / a.s
                    for e in (a.X, a.Y):
                        a.v.makeCosmeticLine3D(V([c[k] - ue * e[k] for k in range(3)]),
                                               V([c[k] + ue * e[k] for k in range(3)]), 4, 0.25)
                else:
                    t0 = min(f["bereich"][0] for f in fl) - 3 / a.s
                    t1 = max(f["bereich"][1] for f in fl) + 3 / a.s
                    a.v.makeCosmeticLine3D(V([c0[k] + t0 * d[k] for k in range(3)]),
                                           V([c0[k] + t1 * d[k] for k in range(3)]), 4, 0.25)
                n += 1
            if n:
                self.prot.ok("Mittellinie", f"{vid}: {n} Achse(n)")

    # ---- Maße
    def _ebene_ecke(self, a, f, seite):
        """Sichtbare Ecke auf der Kantenlinie einer Ebene; bevorzugt zur Maßseite hin."""
        n = f["normale"]
        if abs(dot(n, a.D)) > 0.1:
            raise RuntimeError(f"Fläche {f['id']} steht nicht auf Kante in dieser Ansicht")
        nd = a.richtung(n)
        pt = [(f["box"][k] + f["box"][k + 3]) / 2 for k in range(3)]
        lx, ly = a.lokal(pt)
        nl = (nd[0], -nd[1])  # Normale in lokalen Koordinaten (y gespiegelt)
        lage = lx * nl[0] + ly * nl[1]
        kand = [(i, p) for i, p in a.ecken() if abs(p[0] * nl[0] + p[1] * nl[1] - lage) < 0.02 * max(a.s, 1)]
        if not kand:
            raise RuntimeError(f"keine sichtbare Ecke auf Fläche {f['id']}")
        sx, sy = {"unten": (0, 1), "oben": (0, -1), "links": (-1, 0), "rechts": (1, 0)}[seite]
        return max(kand, key=lambda t: t[1][0] * sx + t[1][1] * sy)

    def _platz(self, a, dim, blattpos):
        dim.X = blattpos[0] - a.v.X.Value
        dim.Y = blattpos[1] - a.v.Y.Value

    def _neues_mass(self, typ, refs, a):
        d = self.doc.addObject("TechDraw::DrawViewDimension", "Mass")
        d.Type = typ
        d.References2D = refs
        self.page.addView(d)
        return d

    def mass(self, m):
        a = self._ansicht(m)
        typ = m.get("typ", "abstand")
        vor = ""
        if typ == "abstand":
            seite = m.get("lage", "unten")
            if "von" in m:
                fa, fb = self._f(m["von"]), self._f(m["bis"])
                ia, pa = self._ebene_ecke(a, fa, seite)
                ib, pb = self._ebene_ecke(a, fb, seite)
                nd = a.richtung(fa["normale"])
                dtyp = "DistanceX" if abs(nd[0]) > abs(nd[1]) else "DistanceY"
            else:
                ia, pa = a.ecke_bei(*a.lokal(m["punkt_a"]))
                ib, pb = a.ecke_bei(*a.lokal(m["punkt_b"]))
                dtyp = "Distance"
            d = self._neues_mass(dtyp, [(a.v, f"Vertex{ia}"), (a.v, f"Vertex{ib}")], a)
            if m.get("pos"):
                self._platz(a, d, m["pos"])
            else:
                ol = a.umriss()
                ab = m.get("abstand", 12)
                mxl, myl = (pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2
                mx, my = a.blatt_aus_lokal(mxl, myl)
                pos = {"unten": [mx, ol[1] - ab], "oben": [mx, ol[3] + ab],
                       "links": [ol[0] - ab, my], "rechts": [ol[2] + ab, my]}[seite]
                self._platz(a, d, pos)
        elif typ == "durchmesser":
            f = self._f(m["flaeche"])
            oben, unten, seitlich = a.zylinderpunkte(f, m.get("bei"))
            vor = "⌀"
            if seitlich:
                lo, lu = a.lokal(oben), a.lokal(unten)
                ax = a.richtung(f["achse"]["richtung"])
                quer_lokal = (lo[0] - lu[0], lo[1] - lu[1])
                laenge = math.hypot(*quer_lokal)
                q = (quer_lokal[0] / laenge, quer_lokal[1] / laenge)
                axl = (ax[0], -ax[1])

                def auf_linie(p, ziel):
                    return abs((p[0] - ziel[0]) * q[0] + (p[1] - ziel[1]) * q[1]) < 0.02 * max(a.s, 1)
                bei_l = lo[0] * axl[0] + lo[1] * axl[1]
                ko = [(i, p) for i, p in a.ecken() if auf_linie(p, lo)]
                ku = [(i, p) for i, p in a.ecken() if auf_linie(p, lu)]
                if not ko or not ku:
                    raise RuntimeError(f"Mantellinien von {f['id']} nicht sichtbar")
                ia, _ = min(ko, key=lambda t: abs(t[1][0] * axl[0] + t[1][1] * axl[1] - bei_l))
                ib, _ = min(ku, key=lambda t: abs(t[1][0] * axl[0] + t[1][1] * axl[1] - bei_l))
                dtyp = "DistanceY" if abs(ax[0]) > abs(ax[1]) else "DistanceX"
                d = self._neues_mass(dtyp, [(a.v, f"Vertex{ia}"), (a.v, f"Vertex{ib}")], a)
                if m.get("pos"):
                    self._platz(a, d, m["pos"])
                else:
                    po, pu = a.blatt(oben), a.blatt(unten)
                    mitte = [(po[0] + pu[0]) / 2, (po[1] + pu[1]) / 2]
                    v = m.get("textpos", f["d"] * 0.3) * a.s
                    qb = [(po[0] - pu[0]) / (laenge or 1), (po[1] - pu[1]) / (laenge or 1)]
                    self._platz(a, d, [mitte[0] + qb[0] * v, mitte[1] + qb[1] * v])
            else:
                cl = a.lokal(unten)
                r = f["d"] / 2 * a.s
                kreise = [(i, e) for i, e in enumerate(a.v.getVisibleEdges()) if e.Curve.TypeId == "Part::GeomCircle"
                          and abs(e.Curve.Radius - r) < 0.01 * max(a.s, 1)
                          and math.hypot(e.Curve.Center.x - cl[0], e.Curve.Center.y - cl[1]) < 0.05 * max(a.s, 1)]
                if not kreise:
                    raise RuntimeError(f"Kreis ⌀{zahl(f['d'])} von {f['id']} in der Ansicht nicht sichtbar")
                d = self._neues_mass("Diameter", [(a.v, f"Edge{kreise[0][0]}")], a)
                _hinweislinienstil(d)
                po = a.blatt(oben)
                dx, dy = m.get("versatz", [12, 12])
                self._platz(a, d, m.get("pos") or [po[0] + dx, po[1] + dy])
        elif typ == "punkte":
            ia, _ = a.ecke_bei(*a.lokal(m["a"]))
            ib, _ = a.ecke_bei(*a.lokal(m["b"]))
            d = self._neues_mass("Distance", [(a.v, f"Vertex{ia}"), (a.v, f"Vertex{ib}")], a)
            self._platz(a, d, m["pos"])
        elif typ in ("radius", "kante"):
            lx, ly = a.lokal(m["punkt"])
            kreise = [(i, e) for i, e in enumerate(a.v.getVisibleEdges())
                      if e.Curve.TypeId in ("Part::GeomCircle", "Part::GeomArcOfCircle")]
            if not kreise:
                raise RuntimeError("kein Kreis/Bogen in der Ansicht")
            i, e = min(kreise, key=lambda t: t[1].distToShape(__import__("Part").Vertex(V((lx, ly, 0))))[0])
            voll = e.isClosed()
            dtyp = "Diameter" if (typ == "kante" and voll) else "Radius"
            vor = "⌀" if dtyp == "Diameter" else "R"
            d = self._neues_mass(dtyp, [(a.v, f"Edge{i}")], a)
            _hinweislinienstil(d)
            self._platz(a, d, m["pos"])
        else:
            raise RuntimeError(f"Maßtyp '{typ}' unbekannt")
        self.doc.recompute()
        wert = d.getRawValue()
        self._toleranz(d, m, wert, vor)
        if m.get("id"):
            self.masse[m["id"]] = (d, a, m)
        return f"{m.get('id', typ)} = {zahl(wert)} mm"

    def _toleranz(self, d, m, wert, vor):
        import re
        nks = nachkomma(wert)
        kern = f"%.{nks}f"
        t = m.get("tol")
        vor = m.get("vor", vor)
        nach = m.get("nach", "")
        if m.get("text"):
            d.Arbitrary = True
            d.FormatSpec = T(m["text"])
            return
        if m.get("ted"):
            d.TheoreticalExact = True
        if isinstance(t, dict) or (isinstance(t, str) and "/" in t and re.match(r"^\s*[+\-−]", t)):
            o, u = (t["oben"], t["unten"]) if isinstance(t, dict) else [x.strip() for x in t.split("/", 1)]
            d.EqualTolerance = False
            d.ArbitraryTolerances = True
            d.FormatSpecOverTolerance = T(_vz(o))
            d.FormatSpecUnderTolerance = T(_vz(u))
        elif isinstance(t, str) and t.strip().startswith(("±", "+-")):
            d.EqualTolerance = True
            d.ArbitraryTolerances = True
            d.FormatSpecOverTolerance = t.strip().lstrip("±+-").strip()
        elif isinstance(t, str) and re.match(r"^[A-Za-z]{1,2}\d{1,2}$", t.strip()):
            import passung
            feld = t.strip()
            fd = passung.field(round(wert, 3), feld)
            kern += f" {feld}"
            if m.get("abmasse", True):
                o, u = fd["oberes_abmass_um"], fd["unteres_abmass_um"]
                dez = passung._decimals(o, u)
                d.EqualTolerance = False
                d.ArbitraryTolerances = True
                d.FormatSpecOverTolerance = T(passung.fmt_dev(o, dez))
                d.FormatSpecUnderTolerance = T(passung.fmt_dev(u, dez))
        elif t:
            raise RuntimeError(f"Toleranzangabe '{t}' nicht erkannt")
        spec = f"{vor}{kern}{(' ' + nach) if nach else ''}"
        if m.get("hilfsmass"):
            spec = f"({spec})"
        d.FormatSpec = T(spec)

    # ---- Symbole (Toleranzrahmen, Bezüge, Oberflächen) als SVG mit Hinweislinie
    def _anker(self, spec):
        """(Ansicht, Ankerpunkt Blatt, Richtung der Hinweislinie oder None, Maßtyp)."""
        if spec.get("an"):
            if spec["an"] not in self.masse:
                raise RuntimeError(f"Maß '{spec['an']}' nicht vorhanden")
            d, a, m = self.masse[spec["an"]]
            if m.get("typ") == "durchmesser":
                f = self._f(m["flaeche"])
                oben, unten, seitlich = a.zylinderpunkte(f, m.get("bei"))
                p = a.blatt(unten if spec.get("seite") == "unten" else oben)
                if seitlich:
                    q = a.blatt(unten if spec.get("seite") != "unten" else oben)
                    r = [p[0] - q[0], p[1] - q[1]]
                    n = math.hypot(*r) or 1
                    return a, p, [r[0] / n, r[1] / n]
                return a, p, None
            return a, [a.v.X.Value + d.X.Value, a.v.Y.Value + d.Y.Value], None
        a = self._ansicht(spec)
        if spec.get("punkt"):
            return a, a.blatt(spec["punkt"]), None
        f = self._f(spec["flaeche"])
        if f["typ"] in ("zylinder", "kegel"):
            oben, unten, seitlich = a.zylinderpunkte(f, spec.get("bei"))
            return a, a.blatt(unten if spec.get("seite") == "unten" else oben), None
        if f["typ"] == "ebene":
            if abs(dot(f["normale"], a.D)) > 0.9:
                return a, a.blatt([(f["box"][k] + f["box"][k + 3]) / 2 for k in range(3)]), None
            nd = a.richtung(f["normale"])
            entlang = [-nd[1], nd[0]]
            if entlang[1] < 0 or (abs(entlang[1]) < 1e-9 and entlang[0] < 0):
                entlang = [-entlang[0], -entlang[1]]
            bx = f["box"]
            pts = [a.blatt([x, y, z]) for x in (bx[0], bx[3]) for y in (bx[1], bx[4]) for z in (bx[2], bx[5])]
            ts = [p[0] * entlang[0] + p[1] * entlang[1] for p in pts]
            p0, p1 = pts[ts.index(min(ts))], pts[ts.index(max(ts))]
            anteil = spec.get("anteil", 0.8)
            return a, [p0[0] + (p1[0] - p0[0]) * anteil, p0[1] + (p1[1] - p0[1]) * anteil], None
        return a, a.blatt([(f["box"][k] + f["box"][k + 3]) / 2 for k in range(3)]), None

    def _symbol(self, name, teile, punkte):
        """teile: SVG in Blattkoordinaten mit y nach unten (y = −Blatt-y); punkte: Hüllpunkte (svg)."""
        xs, ys = [p[0] for p in punkte], [p[1] for p in punkte]
        x0, y0, x1, y1 = min(xs) - 1, min(ys) - 1, max(xs) + 1, max(ys) + 1
        w, h = x1 - x0, y1 - y0
        sym = self.doc.addObject("TechDraw::DrawViewSymbol", name)
        sym.Symbol = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.3f}mm" height="{h:.3f}mm" '
                      f'viewBox="{x0:.3f} {y0:.3f} {w:.3f} {h:.3f}" font-family="osifont">{T("".join(teile))}</svg>')
        self.page.addView(sym)
        sym.X, sym.Y = (x0 + x1) / 2, -(y0 + y1) / 2
        return sym

    @staticmethod
    def _pfeil(spitze, von, gefuellt=True, laenge=3.0, breite=0.55):
        ux, uy = spitze[0] - von[0], spitze[1] - von[1]
        n = math.hypot(ux, uy) or 1
        ux, uy = ux / n, uy / n
        bx, by = spitze[0] - ux * laenge, spitze[1] - uy * laenge
        nx, ny = -uy * breite, ux * breite
        return (f'<polygon points="{spitze[0]:.3f},{spitze[1]:.3f} {bx + nx:.3f},{by + ny:.3f} '
                f'{bx - nx:.3f},{by - ny:.3f}" fill="#000"/>')

    @staticmethod
    def _linie(pts, w=0.25):
        d = " ".join(f"{x:.3f},{y:.3f}" for x, y in pts)
        return f'<polyline points="{d}" fill="none" stroke="#000" stroke-width="{w}"/>'

    def rahmen(self, g):
        import zeichnung as zg
        a, anker, quer = self._anker(g)
        rows = zg.frame_rows(g["zellen"])
        dx, dy = g.get("versatz", [12, 14])
        ziel = g["pos"] if g.get("pos") else [anker[0] + dx, anker[1] + dy]
        seite = "rechts" if ziel[0] < anker[0] - 1 else "links"
        ax, ay = ziel[0], -ziel[1]
        svg, boxen = zg.draw_frame(rows, ax, ay, seite, H, g.get("darueber"))
        sp = (anker[0], -anker[1])
        if quer:  # Achse: Hinweislinie in Verlängerung der Maßlinie, Pfeil auf dem Maßlinienende
            knick = (sp[0], ay)
            weg = [(ax, ay), knick, sp]
            spitze_von = knick
        else:
            weg = [(ax, ay), sp]
            spitze_von = (ax, ay)
        teile = [svg, self._linie(weg), self._pfeil(sp, spitze_von)]
        punkte = [p for b in boxen for p in ((b[0], b[1]), (b[2], b[3]))] + list(weg)
        self._symbol("Toleranzrahmen", teile, punkte)
        return "|".join(str(x) for x in rows[0])

    def bezug(self, d):
        a, anker, quer = self._anker(d)
        dx, dy = d.get("versatz", [0, -12] if d.get("seite") == "unten" else [0, 12])
        sp = (anker[0], -anker[1])
        if quer:
            dx = 0
        kasten = (sp[0] + dx, sp[1] - dy)
        rich = (kasten[0] - sp[0], kasten[1] - sp[1])
        n = math.hypot(*rich) or 1
        ux, uy = rich[0] / n, rich[1] / n
        hb = 2.0  # halbe Dreiecksbreite, Höhe ~ 1,73 × hb
        basis = [(sp[0] - uy * hb, sp[1] + ux * hb), (sp[0] + uy * hb, sp[1] - ux * hb)]
        spitze = (sp[0] + ux * hb * 1.73, sp[1] + uy * hb * 1.73)
        k = 2 * H  # Kastenseite
        kx0, ky0 = kasten[0] - k / 2, kasten[1] - (k if uy <= 0 else 0)
        teile = [f'<polygon points="{basis[0][0]:.3f},{basis[0][1]:.3f} {basis[1][0]:.3f},{basis[1][1]:.3f} '
                 f'{spitze[0]:.3f},{spitze[1]:.3f}" fill="#000"/>',
                 self._linie([spitze, (kasten[0], ky0 + (k if uy <= 0 else 0))]),
                 f'<rect x="{kx0:.3f}" y="{ky0:.3f}" width="{k:.3f}" height="{k:.3f}" fill="#fff" stroke="#000" '
                 f'stroke-width="0.25"/>',
                 f'<text x="{kasten[0]:.3f}" y="{ky0 + k / 2 + H / 2:.3f}" font-size="{H / 0.716:.3f}" '
                 f'text-anchor="middle">{d["buchstabe"]}</text>']
        self._symbol("Bezug_" + d["buchstabe"], teile, basis + [spitze, (kx0, ky0), (kx0 + k, ky0 + k)])
        return f"{d['buchstabe']} an {d.get('an') or d.get('flaeche') or d.get('punkt')}"

    def oberflaeche(self, s):
        import zeichnung as zg
        a, anker, _ = self._anker(s)
        dx, dy = s.get("versatz", [10, 12])
        sp = (anker[0], -anker[1])
        fuss = (sp[0] + dx, sp[1] - dy)
        svg, rechts, ecken = zg.surface_symbol(s.get("art", "abtragen"), [s["text"]], H, s.get("verfahren"))
        teile = [f'<g transform="translate({fuss[0]:.3f},{fuss[1]:.3f})">{svg}</g>',
                 self._linie([fuss, sp]), self._pfeil(sp, fuss)]
        punkte = [(fuss[0] + x, fuss[1] + y) for x, y in ecken] + [sp, fuss]
        self._symbol("Oberflaeche", teile, punkte)
        return s["text"]

    def hinweis(self, n):
        zeilen = n["text"] if isinstance(n.get("text"), list) else [n["text"]]
        x, y = n.get("pos", [20, 60])
        an = self.doc.addObject("TechDraw::DrawViewAnnotation", "Hinweis")
        an.Text = [T(z) for z in zeilen]
        an.TextSize = H
        self.page.addView(an)
        breite = max(len(z) for z in zeilen) * H * 0.62
        hoehe = len(zeilen) * H * 1.55
        an.X, an.Y = x + breite / 2, y - hoehe / 2
        return zeilen[0]

    def eigenschaften(self):
        eig = dict(self.auftrag.get("eigenschaften", {}))
        if eig.get("Masse") == "auto":
            eig["Masse"] = (f"{self.modell['masse_kg']:.3f} kg".replace(".", ",")
                            if self.modell.get("masse_kg") else "")
        texte = dict(self.tpl.EditableTexts)
        neu = {k: "" for k in texte}  # Platzhalter der Vorlage leeren
        neu["fc-sc"] = f"{zahl(self.s1)}:{zahl(self.s2)}"
        neu["page_number"] = "1 / 1"
        neu["document_type"] = "Teilzeichnung"
        neu["fc-date"] = time.strftime("%Y-%m-%d")
        neu["drawing_title"] = self.obj.Label
        for k, v in eig.items():
            if k in FELDER and FELDER[k] in neu:
                neu[FELDER[k]] = T(v)
        self.tpl.EditableTexts = neu
        zusatz = [f"{k}: {eig[k]}" for k in ("Werkstoff", "Masse", "Index", "Geprueft") if eig.get(k)]
        if not eig.get("Werkstoff") and self.modell.get("werkstoff"):
            zusatz.insert(0, f"Werkstoff: {self.modell['werkstoff']}")
        if zusatz:
            an = self.doc.addObject("TechDraw::DrawViewAnnotation", "Schriftfeld_Zusatz")
            an.Text = [T("   ".join(zusatz).replace("Geprueft", "Geprüft"))]
            an.TextSize = 2.5
            self.page.addView(an)
            breite = len(an.Text[0]) * 2.5 * 0.62
            an.X, an.Y = self.W - 189 + breite / 2, 52.5
        self.prot.ok("Eigenschaften", ", ".join(k for k in eig) or "Standard")

    def _schritt(self, art, spec, fn):
        try:
            self.prot.ok(art, fn(spec))
        except Exception as ex:
            self.prot.fehler(art, f"{spec.get('id') or spec.get('zellen') or spec.get('text') or spec}: {ex}")

    def zeichnen(self):
        self.blatt()
        self.ansichten_anlegen()
        if self.auftrag.get("mittellinien", "auto") == "auto":
            try:
                self.mittellinien()
            except Exception as ex:
                self.prot.fehler("Mittellinie", str(ex))
        for m in self.auftrag.get("masse", []):
            self._schritt("Maß", m, self.mass)
        for d in self.auftrag.get("bezuege", []):
            self._schritt("Bezug", d, self.bezug)
        for g in self.auftrag.get("rahmen", []):
            self._schritt("Toleranzrahmen", g, self.rahmen)
        for s in self.auftrag.get("oberflaechen", []):
            self._schritt("Oberfläche", s, self.oberflaeche)
        for n in self.auftrag.get("hinweise", []):
            self._schritt("Hinweis", n, self.hinweis)
        self.eigenschaften()
        self.doc.recompute()
        aus = self.auftrag.get("ausgabe") or {}
        if isinstance(aus, str):
            aus = {"name": aus}
        ordner = self._pfad(aus.get("ordner", os.path.dirname(self.teil)))
        name = aus.get("name") or self.auftrag.get("eigenschaften", {}).get("Zeichnungsnummer") \
            or os.path.splitext(os.path.basename(self.teil))[0] + "-Zeichnung"
        os.makedirs(ordner, exist_ok=True)
        ziel = os.path.join(ordner, name + ".FCStd")
        if os.path.normcase(os.path.abspath(ziel)) == os.path.normcase(self.teil):
            ziel = os.path.join(ordner, name + "-Zeichnung.FCStd")
        self.doc.saveAs(ziel)
        self.prot.ok("Speichern", ziel)
        dateien = ausgeben(self.page, ziel, aus.get("pdf", True), aus.get("dxf", False), self.prot)
        return self.prot.ergebnis(ziel, dateien=dateien)


def ausgeben(page, ziel, pdf=True, dxf=False, prot=None):
    import TechDraw
    import TechDrawGui
    out = []
    try:
        page.ViewObject.doubleClicked()  # ohne geöffnete Blattansicht fehlen Rahmen und Schriftfeld im PDF
    except Exception:
        pass
    warten(lambda: False, 1.5)
    if pdf:
        p = os.path.splitext(ziel)[0] + ".pdf"
        TechDrawGui.exportPageAsPdf(page, p)
        ok = os.path.exists(p) and os.path.getsize(p) > 1000
        if prot:
            prot.eintrag("PDF", ok, p)
        out.append(p)
    if dxf:
        p = os.path.splitext(ziel)[0] + ".dxf"
        TechDraw.writeDXFPage(page, p)
        if prot:
            prot.eintrag("DXF", os.path.exists(p), p)
        out.append(p)
    return out


def _hinweislinienstil(d):
    """Kreis- und Radiusmaße mit waagrechtem Text auf Hinweislinie (ISO 129-1, Bezugslinien-Stil)."""
    try:
        vo = d.ViewObject
        stile = vo.getEnumerationsOfProperty("StandardAndStyle")
        stil = next((x for x in stile if "ISO" in x and "Referenc" in x), None)
        if stil:
            vo.StandardAndStyle = stil
    except Exception:
        pass


def _vz(s):
    s = str(s).strip().replace("-", "−")
    if s in ("0", "+0", "−0"):
        return "0"
    return s if s.startswith(("+", "−")) else "+" + s


# ---------------------------------------------------------------------------- Ablauf
def ausfuehren():
    modus = A["modus"]
    try:
        if modus == "analysieren":
            erg = analysieren(A["teil"])
        elif modus == "zeichnen":
            erg = Zeichner(A["auftrag"], A["basis"]).zeichnen()
        elif modus == "export":
            doc = App.openDocument(A["zeichnung"])
            pages = [o for o in doc.Objects if o.TypeId == "TechDraw::DrawPage"]
            if not pages:
                raise RuntimeError("Dokument enthält kein Zeichnungsblatt")
            erg = {"dateien": ausgeben(pages[0], A["zeichnung"], "pdf" in A["formate"], "dxf" in A["formate"])}
        else:
            raise RuntimeError(f"Modus {modus} unbekannt")
    except Exception:
        erg = {"absturz": traceback.format_exc()}
    with open(A["ergebnis"], "w", encoding="utf-8") as fh:
        json.dump(erg, fh, ensure_ascii=False, indent=1)


if App.GuiUp:
    from PySide import QtCore

    def _gui():
        ausfuehren()
        os._exit(0)
    QtCore.QTimer.singleShot(300, _gui)
else:
    ausfuehren()
