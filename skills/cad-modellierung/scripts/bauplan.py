"""Bauplan: neutrale Beschreibung eines Bauteils, gemeinsam für alle Bauskripte.

Nur Python-Standardbibliothek, damit es im normalen Python UND im FreeCAD-Python läuft.
Format: references/bauplan.md

laden(pfad)       -> geprüfter, normalisierter Plan (dict) oder BauplanFehler mit allen Befunden
schleifen(feat)   -> geschlossene Konturen in (u, v): [("linie", p, q) | ("bogen", p, m, q) | ("kreis", c, r)]
rahmen(ebene, versatz) -> Ursprung, u, v, Plus-Richtung einer Skizzenebene (auch geneigt)
ausdruck(text, werte)  -> rechnet "L/2-rand" mit den Parametern des Plans
waehle_kanten / waehle_flaechen -> neutrale Auswahl auf Geometriedaten der Bauskripte
"""
import ast
import json
import math
import operator
import os

EBENEN = {
    # u-Achse, v-Achse, Plus-Richtung (Normale des Plans). Versatz liegt auf der Plus-Achse.
    "XY": ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    "XZ": ((1, 0, 0), (0, 0, 1), (0, 1, 0)),
    "YZ": ((0, 1, 0), (0, 0, 1), (1, 0, 0)),
}
ACHSEN = {"X": (1, 0, 0), "Y": (0, 1, 0), "Z": (0, 0, 1)}
TYPEN_PLUS = {"block", "drehteil"}
TYPEN_MINUS = {"tasche", "drehnut", "bohrung"}
# Diese Typen baut bisher nur FreeCAD (SolidWorks meldet sie als nicht unterstützt)
NUR_FREECAD = {"muster", "spiegeln", "loft", "zug", "text", "import"}
TYPEN = TYPEN_PLUS | TYPEN_MINUS | {"fase", "verrundung", "schale", "frei"} | NUR_FREECAD
# Features mit eigener Skizze: nur sie lassen sich als Muster wiederholen oder spiegeln
SKIZZENTYPEN = {"block", "tasche", "bohrung", "drehteil", "drehnut", "loft", "zug", "text"}
FERTIGUNG = {"fdm", "sla", "fraesen", "drehen"}

# ISO 261 Regelgewinde: Nenndurchmesser -> Steigung
REGELGEWINDE = {1.6: 0.35, 2: 0.4, 2.5: 0.45, 3: 0.5, 3.5: 0.6, 4: 0.7, 5: 0.8, 6: 1.0, 8: 1.25, 10: 1.5,
                12: 1.75, 14: 2.0, 16: 2.0, 18: 2.5, 20: 2.5, 22: 2.5, 24: 3.0, 27: 3.0, 30: 3.5, 33: 3.5,
                36: 4.0, 39: 4.0, 42: 4.5, 45: 4.5, 48: 5.0, 52: 5.0, 56: 5.5, 60: 5.5, 64: 6.0}
# ISO 273 Durchgangsbohrung, Reihe mittel
DURCHGANG = {1.6: 1.8, 2: 2.4, 2.5: 2.9, 3: 3.4, 4: 4.5, 5: 5.5, 6: 6.6, 8: 9.0, 10: 11.0, 12: 13.5, 14: 15.5,
             16: 17.5, 18: 20.0, 20: 22.0, 22: 24.0, 24: 26.0, 27: 30.0, 30: 33.0, 33: 36.0, 36: 39.0}
# ISO 4032 Sechskantmutter: Nenndurchmesser -> (Schlüsselweite, Höhe max).
# DIN 934 weicht ab bei M10 (17), M12 (19), M14 (22).
MUTTER = {2: (4.0, 1.6), 2.5: (5.0, 2.0), 3: (5.5, 2.4), 4: (7.0, 3.2), 5: (8.0, 4.7), 6: (10.0, 5.2),
          8: (13.0, 6.8), 10: (16.0, 8.4), 12: (18.0, 10.8), 14: (21.0, 12.8), 16: (24.0, 14.8), 20: (30.0, 18.0)}
# Dichte g/cm³ für die Massenangabe (Richtwerte)
DICHTE = {"stahl": 7.85, "s235": 7.85, "s355": 7.85, "c45": 7.85, "42crmo4": 7.85, "edelstahl": 7.9,
          "1.4301": 7.9, "1.4305": 7.9, "1.4404": 8.0, "aluminium": 2.7, "alu": 2.7, "en aw-6082": 2.71,
          "en aw-7075": 2.81, "en aw-5083": 2.66, "messing": 8.5, "cuzn39pb3": 8.47, "kupfer": 8.94,
          "grauguss": 7.2, "en-gjl-250": 7.2, "titan": 4.43, "pla": 1.24, "petg": 1.27, "abs": 1.04,
          "asa": 1.07, "pa6": 1.14, "pa12": 1.01, "pom": 1.41, "pe": 0.95, "pp": 0.91, "pc": 1.2,
          "tpu": 1.21, "holz": 0.7}


class BauplanFehler(ValueError):
    def __init__(self, befunde):
        self.befunde = befunde if isinstance(befunde, list) else [befunde]
        super().__init__("\n".join(self.befunde))


# ---------------------------------------------------------------------------- Vektoren
def add(a, b): return tuple(x + y for x, y in zip(a, b))
def sub(a, b): return tuple(x - y for x, y in zip(a, b))
def mul(a, s): return tuple(x * s for x in a)
def dot(a, b): return sum(x * y for x, y in zip(a, b))
def laenge(a): return math.sqrt(dot(a, a))


def kreuz(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def einheit(a):
    n = laenge(a)
    return mul(a, 1 / n) if n else a


def drehe(a, achse, grad):
    """Dreht den Vektor a um die globale Achse X, Y oder Z (Rechte-Hand-Regel)."""
    c, s = math.cos(math.radians(grad)), math.sin(math.radians(grad))
    x, y, z = a
    if achse == "X":
        r = (x, c * y - s * z, s * y + c * z)
    elif achse == "Y":
        r = (c * x + s * z, y, -s * x + c * z)
    else:
        r = (c * x - s * y, s * x + c * y, z)
    return tuple(0.0 if abs(k) < 1e-12 else k for k in r)


def basis(ebene):
    """Name der Grundebene: 'XZ' bleibt 'XZ', {"basis": "XZ", …} -> 'XZ'."""
    return ebene if isinstance(ebene, str) else ebene.get("basis", "XY")


def geneigt(ebene):
    return not isinstance(ebene, str)


def rahmen(ebene, versatz=0):
    """Skizzenebene -> (Ursprung, u, v, Plus-Richtung) im Modell.

    ebene: "XY" | "XZ" | "YZ" oder {"basis": "XY", "ursprung": [x, y, z], "drehen": [["X", 30], …]}.
    Gedreht wird nacheinander um globale Achsenrichtungen durch den Ursprung der Ebene."""
    u, v, n = EBENEN[basis(ebene)]
    o = (0.0, 0.0, 0.0)
    if geneigt(ebene):
        for achse, grad in ebene.get("drehen", []):
            a = str(achse).upper()
            u, v, n = drehe(u, a, grad), drehe(v, a, grad), drehe(n, a, grad)
        o = tuple(float(x) for x in ebene.get("ursprung", o))
    return add(o, mul(n, versatz)), u, v, n


def modellpunkt(ebene, versatz, uv):
    """(u, v) in der Planebene -> 3D-Punkt im Modell (mm)."""
    o, u, v, _ = rahmen(ebene, versatz)
    return add(o, add(mul(u, uv[0]), mul(v, uv[1])))


def _ebene_pruefen(e):
    """Leere Zeichenkette, wenn die Ebenenangabe gültig ist, sonst der Befund."""
    if isinstance(e, str):
        return "" if e in EBENEN else f"ebene '{e}' unbekannt (XY, XZ, YZ)"
    if not isinstance(e, dict):
        return "ebene muss 'XY', 'XZ', 'YZ' oder ein Objekt mit 'basis' sein"
    if e.get("basis", "XY") not in EBENEN:
        return f"ebene.basis '{e.get('basis')}' unbekannt (XY, XZ, YZ)"
    if len(e.get("ursprung", [0, 0, 0])) != 3:
        return "ebene.ursprung braucht [x, y, z]"
    for d in e.get("drehen", []):
        if not (isinstance(d, (list, tuple)) and len(d) == 2 and str(d[0]).upper() in ACHSEN):
            return 'ebene.drehen erwartet eine Liste wie [["X", 30], ["Z", 45]]'
    return ""


# ---------------------------------------------------------------------------- Parameter und Ausdrücke
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv,
        ast.USub: operator.neg, ast.UAdd: operator.pos,
        ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
        ast.Eq: operator.eq, ast.NotEq: operator.ne}
# Winkelfunktionen rechnen in Grad (wie im CAD üblich)
_FUNKT = {"sin": lambda g: math.sin(math.radians(g)), "cos": lambda g: math.cos(math.radians(g)),
          "tan": lambda g: math.tan(math.radians(g)), "asin": lambda x: math.degrees(math.asin(x)),
          "acos": lambda x: math.degrees(math.acos(x)), "atan": lambda x: math.degrees(math.atan(x)),
          "atan2": lambda y, x: math.degrees(math.atan2(y, x)), "sqrt": math.sqrt, "abs": abs, "min": min,
          "max": max, "round": round, "floor": math.floor, "ceil": math.ceil}
_KONST = {"pi": math.pi}


def ausdruck(text, werte):
    """Rechnet 'L/2 - rand' oder 'd*cos(30)' mit den Parametern in werte.

    Erlaubt: Zahlen, Parameter, + - * / ** % //, Vergleiche, 'a if b else c' und die Funktionen in _FUNKT."""
    def ev(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            return n.value
        if isinstance(n, ast.Name):
            if n.id in werte:
                return werte[n.id]
            if n.id in _KONST:
                return _KONST[n.id]
            raise ValueError(f"'{n.id}' ist kein Parameter")
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.operand))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FUNKT and not n.keywords:
            return _FUNKT[n.func.id](*[ev(a) for a in n.args])
        if isinstance(n, ast.Compare) and len(n.ops) == 1 and type(n.ops[0]) in _OPS:
            return _OPS[type(n.ops[0])](ev(n.left), ev(n.comparators[0]))
        if isinstance(n, ast.IfExp):
            return ev(n.body) if ev(n.test) else ev(n.orelse)
        raise ValueError("nicht erlaubter Ausdruck")
    try:
        w = ev(ast.parse(str(text).strip(), mode="eval").body)
    except SyntaxError:
        raise ValueError("Schreibfehler im Ausdruck")
    except ZeroDivisionError:
        raise ValueError("Division durch 0")
    except (TypeError, OverflowError) as ex:
        raise ValueError(str(ex))
    if isinstance(w, bool):
        return w
    w = float(w)
    return int(w) if w.is_integer() and abs(w) < 1e15 else w


def parameter_aufloesen(plan, ueberschreiben=None):
    """Ersetzt im ganzen Plan Zeichenketten der Form "=Ausdruck" durch Zahlen.

    plan["parameter"]: {"L": 80, "t": "=L/8"} – spätere dürfen frühere verwenden.
    ueberschreiben: {"L": 100} ändert Parameter nur für diesen Lauf (Varianten ohne Planänderung).
    Gibt die Befunde zurück; die aufgelösten Werte stehen danach in plan["_parameter"]."""
    bef, werte = [], {}
    roh = dict(plan.get("parameter") or {})
    for k, v in (ueberschreiben or {}).items():
        if k not in roh:
            bef.append(f"Parameter '{k}' gibt es im Plan nicht (vorhanden: {', '.join(roh) or 'keine'})")
        roh[k] = v
    for k, v in roh.items():
        try:
            if isinstance(v, str):
                v = ausdruck(v.lstrip("="), werte)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ValueError("muss eine Zahl sein")
            werte[k] = v
        except ValueError as ex:
            bef.append(f"Parameter '{k}': {ex}")

    def geh(x, wo):
        if isinstance(x, dict):
            for k in list(x):
                if k not in ("freecad", "solidworks", "parameter"):
                    x[k] = geh(x[k], f"{wo}.{k}" if wo else k)
            return x
        if isinstance(x, list):
            return [geh(e, f"{wo}[{i}]") for i, e in enumerate(x)]
        if isinstance(x, str) and x.startswith("="):
            try:
                return ausdruck(x[1:], werte)
            except ValueError as ex:
                bef.append(f"{wo}: '{x}' – {ex}")
        return x
    geh(plan, "")
    plan["_parameter"] = werte
    return bef


# ---------------------------------------------------------------------------- Gewinde
def gewinde(spec):
    """'M6' -> (6.0, 1.0, 'M6');  'M10x1' -> (10.0, 1.0, 'M10x1')"""
    s = str(spec).strip().upper().replace(",", ".").replace("×", "X")
    if not s.startswith("M"):
        raise ValueError(f"Gewinde '{spec}' nicht erkannt (Form: M6 oder M10x1)")
    teile = s[1:].split("X")
    d = float(teile[0])
    if len(teile) > 1:
        p = float(teile[1])
    else:
        p = REGELGEWINDE.get(d)
        if p is None:
            raise ValueError(f"Regelgewinde M{d:g} nicht in der Tabelle – Steigung angeben (z. B. M{d:g}x1.5)")
    return d, p, (f"M{d:g}" if len(teile) == 1 else f"M{d:g}x{p:g}")


def kernloch(d, p):
    """Kernlochbohrung für metrisches Gewinde (d − P, Werkstattregel)."""
    return round(d - p, 2)


# ---------------------------------------------------------------------------- Profile
def _bogen_r(p, q, r, gross=False):
    """Bogen von p nach q mit Radius r (>0 wölbt nach links in Laufrichtung) -> Bogenmitte."""
    c = sub(q, p)
    L = laenge(c)
    if L > 2 * abs(r) + 1e-9:
        raise ValueError(f"Bogenradius {abs(r)} zu klein für Sehne {L:.3f}")
    w = math.sqrt(max(r * r - (L / 2) ** 2, 0))
    h = abs(r) + w if gross else abs(r) - w
    m = mul(add(p, q), 0.5)
    nl = (-c[1] / L, c[0] / L)
    s = 1 if r > 0 else -1
    return (m[0] + s * nl[0] * h, m[1] + s * nl[1] * h)


def _rechteck(b, h, mitte=None, ecke=None, r=0, winkel=0):
    if ecke is not None:
        mitte = (ecke[0] + b / 2, ecke[1] + h / 2)
    cx, cy = mitte
    rot = _dreher(mitte, winkel)
    if not r:
        pts = [(cx - b / 2, cy - h / 2), (cx + b / 2, cy - h / 2), (cx + b / 2, cy + h / 2), (cx - b / 2, cy + h / 2)]
        pts = [rot(p) for p in pts]
        return [("linie", pts[i], pts[(i + 1) % 4]) for i in range(4)]
    if 2 * r > min(b, h) + 1e-9:
        raise ValueError(f"Eckenradius {r} zu groß für Rechteck {b}×{h}")
    x0, x1, y0, y1 = cx - b / 2, cx + b / 2, cy - h / 2, cy + h / 2
    k = r * (1 - 1 / math.sqrt(2))
    segs = []
    ecken = [((x1 - r, y0), (x1, y0 + r), (x1 - k, y0 + k)), ((x1, y1 - r), (x1 - r, y1), (x1 - k, y1 - k)),
             ((x0 + r, y1), (x0, y1 - r), (x0 + k, y1 - k)), ((x0, y0 + r), (x0 + r, y0), (x0 + k, y0 + k))]
    for i, (a, e, m) in enumerate(ecken):
        segs.append(("bogen", rot(a), rot(m), rot(e)))
        n = ecken[(i + 1) % 4][0]
        if laenge(sub(e, n)) > 1e-9:
            segs.append(("linie", rot(e), rot(n)))
    return segs


def _dreher(mitte, winkel):
    if not winkel:
        return lambda p: (p[0], p[1])
    c, s = math.cos(math.radians(winkel)), math.sin(math.radians(winkel))
    mx, my = mitte

    def rot(p):
        dx, dy = p[0] - mx, p[1] - my
        return (mx + c * dx - s * dy, my + s * dx + c * dy)
    return rot


def _langloch(l, b, mitte, winkel=0):
    if l <= b:
        raise ValueError(f"Langloch: Länge {l} muss größer als Breite {b} sein")
    rot = _dreher(mitte, winkel)
    cx, cy = mitte
    a = (l - b) / 2
    r = b / 2
    p1, p2 = (cx - a, cy - r), (cx + a, cy - r)
    p3, p4 = (cx + a, cy + r), (cx - a, cy + r)
    return [("linie", rot(p1), rot(p2)), ("bogen", rot(p2), rot((cx + a + r, cy)), rot(p3)),
            ("linie", rot(p3), rot(p4)), ("bogen", rot(p4), rot((cx - a - r, cy)), rot(p1))]


def _vieleck(n, mitte, sw=None, d=None, winkel=0):
    if sw:
        R = sw / (2 * math.cos(math.pi / n))
    elif d:
        R = d / 2
    else:
        raise ValueError("Vieleck braucht 'sw' (Schlüsselweite) oder 'd' (Umkreis)")
    pts = [(mitte[0] + R * math.cos(math.radians(winkel) + 2 * math.pi * i / n),
            mitte[1] + R * math.sin(math.radians(winkel) + 2 * math.pi * i / n)) for i in range(n)]
    return [("linie", pts[i], pts[(i + 1) % n]) for i in range(n)]


def _kontur(elemente):
    if len(elemente) < 2:
        raise ValueError("Kontur braucht mindestens 2 Elemente")
    start = tuple(elemente[0])
    segs, p = [], start
    for el in elemente[1:] + [start]:
        if isinstance(el, dict):
            q = tuple(el["bis"])
            if "durch" in el:
                m = tuple(el["durch"])
            elif "r" in el:
                m = _bogen_r(p, q, float(el["r"]), el.get("gross", False))
            else:
                raise ValueError(f"Bogen {el} braucht 'durch' oder 'r'")
            segs.append(("bogen", p, m, q))
        else:
            q = tuple(el)
            if laenge(sub(q, p)) < 1e-9:
                continue
            segs.append(("linie", p, q))
        p = q
    if laenge(sub(p, start)) > 1e-6:
        raise ValueError("Kontur ist nicht geschlossen")
    return segs


def linienzug(elemente, geschlossen=False):
    """Pfad aus Punkten und Bögen (Schreibweise wie 'kontur'), bleibt offen, außer geschlossen=True."""
    if not isinstance(elemente, list) or len(elemente) < 2:
        raise ValueError("Pfad braucht mindestens 2 Punkte")
    if isinstance(elemente[0], dict):
        raise ValueError("Pfad muss mit einem Punkt [u, v] beginnen")
    start = tuple(elemente[0])
    segs, p = [], start
    for el in list(elemente[1:]) + ([list(start)] if geschlossen else []):
        if isinstance(el, dict):
            q = tuple(el["bis"])
            if "durch" in el:
                m = tuple(el["durch"])
            elif "r" in el:
                m = _bogen_r(p, q, float(el["r"]), el.get("gross", False))
            else:
                raise ValueError(f"Bogen {el} braucht 'durch' oder 'r'")
            segs.append(("bogen", p, m, q))
        else:
            q = tuple(el)
            if laenge(sub(q, p)) < 1e-9:
                continue
            segs.append(("linie", p, q))
        p = q
    if not segs:
        raise ValueError("Pfad hat keine Länge")
    return segs


def pfad_start(segs):
    """Startpunkt und Starttangente (Einheitsvektor) eines Linienzugs in (u, v)."""
    s = segs[0]
    if s[0] == "linie":
        return s[1], einheit(sub(s[2], s[1]))
    p, m, q = s[1], s[2], s[3]  # Bogen durch drei Punkte: Tangente steht senkrecht auf dem Radius im Startpunkt
    a, b = sub(m, p), sub(q, p)
    d = 2 * (a[0] * b[1] - a[1] * b[0])
    if abs(d) < 1e-12:
        return p, einheit(b)
    cx = (b[1] * dot(a, a) - a[1] * dot(b, b)) / d
    cy = (a[0] * dot(b, b) - b[0] * dot(a, a)) / d
    t = einheit((-cy, cx))
    return p, (t if dot(t, a) > 0 else mul(t, -1))


def positionen(spec):
    """'mitte' als Punkt, Punktliste oder Muster -> Liste von (u, v)."""
    m = spec.get("muster")
    if m:
        if "raster" in m:
            r = m["raster"]
            (sx, sy), (nx, ny), (dx, dy) = r["start"], r["anzahl"], r["abstand"]
            return [(sx + i * dx, sy + j * dy) for j in range(ny) for i in range(nx)]
        if "kreis" in m:
            k = m["kreis"]
            (cx, cy), n = k["mitte"], k["anzahl"]
            r = k["r"] if "r" in k else k["d"] / 2
            w0 = math.radians(k.get("start_winkel", 0))
            teil = math.radians(k.get("teilung", 360 / n))
            return [(cx + r * math.cos(w0 + i * teil), cy + r * math.sin(w0 + i * teil)) for i in range(n)]
        raise ValueError(f"Muster {m} unbekannt (raster oder kreis)")
    mitte = spec.get("mitte", spec.get("positionen", [0, 0]))
    if mitte and isinstance(mitte[0], (list, tuple)):
        return [tuple(p) for p in mitte]
    return [tuple(mitte)]


def form_zu_schleifen(f):
    """Ein Profilelement -> Liste geschlossener Schleifen."""
    w = f.get("winkel", 0)
    if "rechteck" in f:
        b, h = f["rechteck"]
        if "ecke" in f:
            return [_rechteck(b, h, ecke=f["ecke"], r=f.get("r", 0), winkel=w)]
        return [_rechteck(b, h, mitte=p, r=f.get("r", 0), winkel=w) for p in positionen(f)]
    if "kreis" in f:
        return [[("kreis", p, f["kreis"] / 2)] for p in positionen(f)]
    if "langloch" in f:
        l, b = f["langloch"]
        return [_langloch(l, b, p, w) for p in positionen(f)]
    if "vieleck" in f:
        return [_vieleck(int(f["vieleck"]), p, f.get("sw"), f.get("d"), w) for p in positionen(f)]
    if "mutter" in f:  # Sechskant für eine Mutter ISO 4032; 'spiel' wird auf die Schlüsselweite addiert
        d, _, _ = gewinde(f["mutter"])
        if d not in MUTTER:
            raise ValueError(f"keine Mutter M{d:g} hinterlegt – 'vieleck': 6 mit 'sw' angeben")
        return [_vieleck(6, p, MUTTER[d][0] + f.get("spiel", 0), None, w) for p in positionen(f)]
    if "kontur" in f:
        return [_kontur(f["kontur"])]
    raise ValueError(f"Profilelement {json.dumps(f, ensure_ascii=False)} unbekannt")


def schleifen(feat):
    out = []
    for f in feat.get("profil", []):
        out.extend(form_zu_schleifen(f))
    return out


def _bbox2(sch):
    pts = []
    for s in sch:
        if s[0] == "kreis":
            (cx, cy), r = s[1], s[2]
            pts += [(cx - r, cy - r), (cx + r, cy + r)]
        else:
            pts += list(s[1:])
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


# ---------------------------------------------------------------------------- Prüfen
def pruefen(plan, skript=False):
    """Prüft und normalisiert den Plan an Ort und Stelle. Gibt Liste der Befunde zurück (leer = gut).
    skript=True: Plan begleitet ein freies Skript, Features sind dann optional."""
    bef = []
    if not plan.get("name"):
        bef.append("Plan: 'name' fehlt")
    feats = plan.setdefault("features", [])
    if not feats and not skript:
        bef.append("Plan: 'features' fehlt oder leer")
        return bef
    einzeln_modus = bool(plan.get("_einzeln"))
    if feats and not skript:
        f0 = feats[0]
        baut_auf = (f0.get("typ") in TYPEN_PLUS | {"frei", "import"}
                    or (f0.get("typ") in ("loft", "zug") and not f0.get("abziehen")))
        if not baut_auf:
            bef.append("Feature 1: Das erste Feature muss Material aufbauen "
                       "(block, drehteil, loft, zug, import oder frei)")
    if plan.get("fertigung") and str(plan["fertigung"]).lower() not in FERTIGUNG:
        bef.append(f"fertigung '{plan['fertigung']}' unbekannt ({', '.join(sorted(FERTIGUNG))})")
    ids, typ_von = set(), {}
    for i, f in enumerate(feats, 1):
        t = f.get("typ")
        wo = f"Feature {i} ({f.get('id') or t})"
        f["_geprueft"] = True
        f.setdefault("id", f"{t}{i}")
        if f["id"] in ids:
            bef.append(f"{wo}: id '{f['id']}' doppelt")
        ids.add(f["id"])
        typ_von[f["id"]] = t
        if t not in TYPEN:
            bef.append(f"{wo}: Typ '{t}' unbekannt – erlaubt: {', '.join(sorted(TYPEN))}")
            continue
        if t in ("block", "tasche", "bohrung", "drehteil", "drehnut", "text"):
            e = f.setdefault("ebene", "XY")
            b = _ebene_pruefen(e)
            if b:
                bef.append(f"{wo}: {b}")
                continue
            f.setdefault("versatz", 0)
        if t in ("block", "tasche"):
            f.setdefault("richtung", "+" if t == "block" else "-")
            if f["richtung"] not in ("+", "-", "beide"):
                bef.append(f"{wo}: richtung muss '+', '-' oder 'beide' sein")
            if t == "block" and not f.get("hoehe"):
                bef.append(f"{wo}: 'hoehe' fehlt")
            if t == "tasche" and not (f.get("tiefe") or f.get("durch")):
                bef.append(f"{wo}: 'tiefe' oder 'durch': true fehlt")
            if f.get("schraege") and not -60 < f["schraege"] < 60:
                bef.append(f"{wo}: 'schraege' in Grad zwischen −60 und 60")
            if f.get("schraege") and f["richtung"] == "beide":
                bef.append(f"{wo}: 'schraege' geht nicht zusammen mit richtung 'beide'")
            try:
                sch = schleifen(f)
                if not sch:
                    bef.append(f"{wo}: 'profil' fehlt")
                f["_schleifen"] = sch
            except (ValueError, KeyError, TypeError) as ex:
                bef.append(f"{wo}: Profil – {ex}")
        elif t in ("drehteil", "drehnut"):
            a = f.get("achse")
            u, v, _ = EBENEN[basis(f["ebene"])]
            if a not in ACHSEN or ACHSEN[a] not in (u, v):
                bef.append(f"{wo}: achse '{a}' muss in der Ebene {basis(f['ebene'])} liegen")
            if f["versatz"]:
                bef.append(f"{wo}: Drehteile werden in der Grundebene skizziert (versatz 0)")
            f.setdefault("winkel", 360)
            try:
                f["_schleifen"] = schleifen(f)
                ax = 0 if ACHSEN.get(a) == u else 1
                for s in f["_schleifen"]:
                    x0, y0, x1, y1 = _bbox2(s)
                    lo, hi = (y0, y1) if ax == 0 else (x0, x1)
                    if lo < -1e-6 and hi > 1e-6:
                        bef.append(f"{wo}: Profil kreuzt die Drehachse – nur eine Hälfte skizzieren")
            except (ValueError, KeyError, TypeError) as ex:
                bef.append(f"{wo}: Profil – {ex}")
        elif t == "bohrung":
            f.setdefault("richtung", "-")
            try:
                f["_positionen"] = positionen(f)
            except (ValueError, KeyError, TypeError) as ex:
                bef.append(f"{wo}: Positionen – {ex}")
            if f.get("gewinde"):
                try:
                    d, p, name = gewinde(f["gewinde"])
                    f["_gewinde"] = {"d": d, "p": p, "name": name, "kern": kernloch(d, p)}
                    f.setdefault("d", kernloch(d, p))
                except ValueError as ex:
                    bef.append(f"{wo}: {ex}")
            elif f.get("durchgang"):
                try:
                    d, _, _ = gewinde(f["durchgang"])
                    if d not in DURCHGANG:
                        raise ValueError(f"keine ISO-273-Durchgangsbohrung für M{d:g} hinterlegt – 'd' angeben")
                    f.setdefault("d", DURCHGANG[d])
                except ValueError as ex:
                    bef.append(f"{wo}: {ex}")
            if not f.get("d"):
                bef.append(f"{wo}: 'd', 'gewinde' oder 'durchgang' fehlt")
            if not (f.get("tiefe") or f.get("durch")):
                bef.append(f"{wo}: 'tiefe' oder 'durch': true fehlt")
            if f.get("senkung") and f.get("flachsenkung"):
                bef.append(f"{wo}: nur 'senkung' ODER 'flachsenkung'")
            s = f.get("senkung")
            if s:
                s.setdefault("winkel", 90)
                if s.get("d", 0) <= f.get("d", 0):
                    bef.append(f"{wo}: Senkungsdurchmesser muss größer als die Bohrung sein")
            s = f.get("flachsenkung")
            if s and (s.get("d", 0) <= f.get("d", 0) or not s.get("tiefe")):
                bef.append(f"{wo}: flachsenkung braucht 'd' (> Bohrung) und 'tiefe'")
            if f.get("spitze") is True:
                f["spitze"] = 118
            if f.get("spitze") and (f.get("durch") or not 60 <= f["spitze"] < 180):
                bef.append(f"{wo}: 'spitze' (Spitzenwinkel 60…179°, üblich 118) nur bei Sacklöchern mit 'tiefe'")
            if f.get("gewinde_modelliert") and not f.get("gewinde"):
                bef.append(f"{wo}: 'gewinde_modelliert' braucht 'gewinde'")
        elif t in ("muster", "spiegeln"):
            von = f.get("von")
            if von is None:
                von = [feats[i - 2]["id"]] if i > 1 else []
            f["von"] = von = [von] if isinstance(von, str) else list(von)
            if not von and not einzeln_modus:
                bef.append(f"{wo}: 'von' fehlt (IDs der Features, die wiederholt werden)")
            for v in von:
                if einzeln_modus:
                    continue
                if v == f["id"] or v not in typ_von:
                    bef.append(f"{wo}: 'von' nennt '{v}' – dieses Feature steht nicht weiter oben im Plan")
                elif typ_von[v] not in SKIZZENTYPEN:
                    bef.append(f"{wo}: '{v}' ist ein {typ_von[v]}-Feature und lässt sich nicht wiederholen "
                               f"(möglich: {', '.join(sorted(SKIZZENTYPEN))})")
            if t == "spiegeln":
                if f.setdefault("ebene", "YZ") not in EBENEN:
                    bef.append(f"{wo}: ebene muss XY, XZ oder YZ sein (Lage über 'versatz')")
                f.setdefault("versatz", 0)
            else:
                li, kr = f.get("linear"), f.get("kreis")
                if bool(li) == bool(kr):
                    bef.append(f"{wo}: genau eines von 'linear' oder 'kreis' angeben")
                for m in ([li] if isinstance(li, dict) else li or []):
                    if str(m.get("richtung", "")).lstrip("+-").upper() not in ACHSEN:
                        bef.append(f"{wo}: linear.richtung muss X, Y, Z (oder −X …) sein")
                    if not isinstance(m.get("anzahl"), int) or m["anzahl"] < 2 or not m.get("abstand"):
                        bef.append(f"{wo}: linear braucht 'anzahl' (≥ 2, einschließlich Original) und 'abstand'")
                if isinstance(li, list) and len(li) > 2:
                    bef.append(f"{wo}: linear nimmt höchstens zwei Richtungen")
                if kr:
                    if str(kr.get("achse", "")).upper() not in ACHSEN:
                        bef.append(f"{wo}: kreis.achse muss X, Y oder Z sein")
                    if not isinstance(kr.get("anzahl"), int) or kr["anzahl"] < 2:
                        bef.append(f"{wo}: kreis braucht 'anzahl' (≥ 2, einschließlich Original)")
                    if len(kr.get("durch", [0, 0, 0])) != 3:
                        bef.append(f"{wo}: kreis.durch braucht [x, y, z] (Punkt auf der Drehachse)")
        elif t == "loft":
            sn = f.get("schnitte")
            if not isinstance(sn, list) or len(sn) < 2:
                bef.append(f"{wo}: 'schnitte' braucht mindestens zwei Querschnitte")
                continue
            for k, s in enumerate(sn, 1):
                b = _ebene_pruefen(s.setdefault("ebene", "XY"))
                s.setdefault("versatz", 0)
                try:
                    s["_schleifen"] = schleifen(s)
                    if len(s["_schleifen"]) != 1:
                        b = b or "jeder Schnitt braucht genau eine geschlossene Kontur"
                except (ValueError, KeyError, TypeError) as ex:
                    b = b or f"Profil – {ex}"
                if b:
                    bef.append(f"{wo}, Schnitt {k}: {b}")
        elif t == "zug":
            try:
                f["_schleifen"] = schleifen(f)
                if not f["_schleifen"]:
                    bef.append(f"{wo}: 'profil' fehlt")
            except (ValueError, KeyError, TypeError) as ex:
                bef.append(f"{wo}: Profil – {ex}")
            pf = f.get("pfad")
            if not isinstance(pf, dict) or not pf.get("linie"):
                bef.append(f"{wo}: 'pfad' braucht 'linie' (Punkte und Bögen wie bei 'kontur')")
            else:
                b = _ebene_pruefen(pf.setdefault("ebene", "XY"))
                pf.setdefault("versatz", 0)
                if b:
                    bef.append(f"{wo}: pfad.{b}")
                try:
                    f["_pfad"] = linienzug(pf["linie"], bool(pf.get("geschlossen")))
                except (ValueError, KeyError, TypeError) as ex:
                    bef.append(f"{wo}: Pfad – {ex}")
            if f.setdefault("ecken", "scharf") not in ("scharf", "rund"):
                bef.append(f"{wo}: ecken muss 'scharf' oder 'rund' sein")
        elif t == "text":
            if not str(f.get("text", "")).strip():
                bef.append(f"{wo}: 'text' fehlt")
            if not f.get("hoehe") or not f.get("tiefe"):
                bef.append(f"{wo}: 'hoehe' (Schrifthöhe) und 'tiefe' (Gravurtiefe oder Erhebung) fehlen")
            if f.setdefault("art", "gravur") not in ("gravur", "erhaben"):
                bef.append(f"{wo}: art muss 'gravur' oder 'erhaben' sein")
            f.setdefault("richtung", "-" if f["art"] == "gravur" else "+")
            if f["richtung"] not in ("+", "-"):
                bef.append(f"{wo}: richtung muss '+' oder '-' sein")
            if f.setdefault("ausrichtung", "mitte") not in ("mitte", "links", "rechts"):
                bef.append(f"{wo}: ausrichtung muss 'mitte', 'links' oder 'rechts' sein")
            if len(f.setdefault("position", [0, 0])) != 2:
                bef.append(f"{wo}: position braucht [u, v]")
        elif t == "import":
            if i != 1:
                bef.append(f"{wo}: 'import' muss das erste Feature sein")
            d = str(f.get("datei", ""))
            pfad = d if os.path.isabs(d) else os.path.join(plan.get("_ordner", ""), d)
            if not d:
                bef.append(f"{wo}: 'datei' fehlt (STEP, BREP oder IGES)")
            elif os.path.splitext(d)[1].lower() not in (".step", ".stp", ".brep", ".brp", ".igs", ".iges"):
                bef.append(f"{wo}: nur STEP, BREP oder IGES – ein Netz (STL/OBJ/3MF) erst mit "
                           f"'modell.py netz koerper' in einen Volumenkörper wandeln")
            elif not os.path.exists(pfad):
                bef.append(f"{wo}: Datei '{pfad}' nicht gefunden")
            else:
                f["_datei"] = os.path.abspath(pfad)
        elif t in ("fase", "verrundung"):
            if not f.get("kanten"):
                bef.append(f"{wo}: 'kanten' (Auswahl) fehlt")
            if t == "fase" and not f.get("laenge"):
                bef.append(f"{wo}: 'laenge' fehlt")
            if t == "verrundung" and not f.get("r"):
                bef.append(f"{wo}: 'r' fehlt")
        elif t == "schale":
            if not f.get("dicke"):
                bef.append(f"{wo}: 'dicke' fehlt")
            if not f.get("flaechen"):
                bef.append(f"{wo}: 'flaechen' (zu öffnende Flächen) fehlt")
        elif t == "frei":
            if not (f.get("freecad") or f.get("solidworks")):
                bef.append(f"{wo}: Code für 'freecad' und/oder 'solidworks' fehlt")
            if not f.get("beschreibung"):
                bef.append(f"{wo}: 'beschreibung' fehlt (was macht der Code?)")
    # Konstruktionshinweise (blockieren nicht)
    hinweise = plan.setdefault("_hinweise", [])
    radien = []
    for f in feats:
        if f.get("typ") == "verrundung" and f.get("r"):
            radien.append((f["id"], f["r"]))
        if f.get("typ") == "schale" and f.get("dicke") and f.get("nach", "innen") == "innen":
            for fid, r in radien:
                if r <= f["dicke"] + 1e-9:
                    hinweise.append(f"{fid}: Radius {r:g} ≤ Wandstärke {f['dicke']:g} der Schale {f['id']} – innen "
                                    f"entsteht eine scharfe/entartete Kante; Radius > Wandstärke wählen "
                                    f"(innen bleibt r − Wandstärke)")
    if not skript and not plan.get("soll", {}).get("huelle"):
        hinweise.append("soll.huelle fehlt – ohne Soll-Hülle werden Lage- und Richtungsfehler nicht erkannt")
    if not bef:
        hinweise.extend(fertigungshinweise(plan))
    soll = plan.get("soll", {})
    h = soll.get("huelle")
    if h is not None and len(h) not in (3, 6):
        bef.append("soll.huelle: [dx, dy, dz] oder [xmin, ymin, zmin, xmax, ymax, zmax]")
    return bef


def fertigungshinweise(plan):
    """Konstruktionshinweise aus dem Plan je nach 'fertigung' (blockieren nicht, sparen aber Fehldrucke)."""
    art = str(plan.get("fertigung", "")).lower()
    out = []
    for f in plan.get("features", []):
        t, fid = f.get("typ"), f.get("id")
        if art == "fdm":
            g = f.get("_gewinde")
            if g and g["d"] < 6 and not f.get("gewinde_modelliert"):
                out.append(f"{fid}: {g['name']} lässt sich im FDM-Druck kaum schneiden – besser 'durchgang' mit "
                           f"Muttertasche ('mutter') oder Gewindeeinsatz")
            if g and f.get("gewinde_modelliert") and g["d"] < 6:
                out.append(f"{fid}: modelliertes Gewinde {g['name']} ist für FDM zu fein (ab M6 brauchbar)")
            if t == "bohrung" and not g and f.get("d", 9) < 2:
                out.append(f"{fid}: Bohrung Ø{f['d']:g} läuft im FDM-Druck meist zu – ab Ø2 planen")
            if t == "schale" and f.get("dicke", 9) < 1.2:
                out.append(f"{fid}: Wandstärke {f['dicke']:g} mm ist für FDM dünn (Richtwert ≥ 1,2 mm)")
            if t == "text" and (f.get("hoehe", 9) < 4 or f.get("tiefe", 9) < 0.4):
                out.append(f"{fid}: Schrift unter 4 mm Höhe oder 0,4 mm Tiefe wird im FDM-Druck unleserlich")
        if art == "fraesen" and t == "tasche" and not f.get("durch"):
            eckig = [p for p in f.get("profil", []) if ("rechteck" in p and not p.get("r")) or "vieleck" in p
                     or "mutter" in p]
            if eckig:
                out.append(f"{fid}: Tasche mit scharfen Innenecken – fräsbar nur mit Eckenradius "
                           f"(z. B. 'r' ≥ Fräserradius) oder wenn die Ecken frei auslaufen")
    return out


def nur_freecad(f):
    """Grund (Text), warum ein Feature nur in FreeCAD gebaut werden kann – sonst None."""
    t = f.get("typ")
    if t in NUR_FREECAD:
        return f"Feature-Typ '{t}' gibt es bisher nur in FreeCAD"
    if geneigt(f.get("ebene", "XY")):
        return "geneigte Ebenen (ebene als Objekt) gibt es bisher nur in FreeCAD"
    for k in ("schraege", "gewinde_modelliert"):
        if f.get(k):
            return f"'{k}' gibt es bisher nur in FreeCAD"
    return None


def einzeln(f):
    """Prüft ein einzelnes Feature (für feature() in freien Skripten); wirft BauplanFehler."""
    if not f.get("_geprueft"):
        bef = [b for b in pruefen({"name": "x", "features": [f], "_einzeln": True}, skript=True)]
        if bef:
            raise BauplanFehler(bef)
    return f


def laden(pfad, skript=False, parameter=None):
    """Liest, rechnet Parameter aus ("=…") und prüft. parameter: {"L": 100} überschreibt für diesen Lauf."""
    with open(pfad, encoding="utf-8") as fh:
        plan = json.load(fh)
    plan["_ordner"] = os.path.dirname(os.path.abspath(pfad))
    bef = parameter_aufloesen(plan, parameter)
    if not bef:
        bef = pruefen(plan, skript)
    if bef:
        raise BauplanFehler(bef)
    return plan


def dichte(plan):
    if plan.get("dichte"):
        return float(plan["dichte"])
    w = str(plan.get("werkstoff", "")).lower()
    for k in sorted(DICHTE, key=len, reverse=True):
        if k in w:
            return DICHTE[k]
    return None


# ---------------------------------------------------------------------------- Auswahl
# Kantendaten der Bauskripte: {"i": Index, "typ": "linie"|"kreis"|"andere", "punkte": [(x,y,z)…],
#   "richtung": (…) bei Linien, "mitte": (…) und "d" bei Kreisen, "achse": (…) bei Kreisen}
# Flächendaten: {"i", "typ": "ebene"|"zylinder"|"andere", "normale": (…) bei Ebenen (aus dem Material),
#   "punkt": (…) Schwerpunkt, "d" bei Zylindern, "achse"}

def _achse(name):
    s = name.strip().upper()
    sign = -1 if s.startswith("-") else 1
    return mul(ACHSEN[s.lstrip("+-")], sign)


def _kante_passt(k, sel, tol):
    if sel.get("alle"):
        return True
    if "parallel" in sel:
        if k["typ"] != "linie" or abs(abs(dot(k["richtung"], ACHSEN[sel["parallel"].upper()])) - 1) > 1e-6:
            return False
    if "in_ebene" in sel:
        for ax, wert in sel["in_ebene"].items():
            i = "XYZ".index(ax.upper())
            if any(abs(p[i] - wert) > tol for p in k["punkte"]):
                return False
    if "kreis" in sel and sel["kreis"] and k["typ"] != "kreis":
        return False
    if "d" in sel and (k["typ"] != "kreis" or abs(k["d"] - sel["d"]) > tol):
        return False
    if "box" in sel:
        b = sel["box"]
        m = k["punkte"][len(k["punkte"]) // 2]
        if not all(b[i] - tol <= m[i] <= b[i + 3] + tol for i in range(3)):
            return False
    return True


def _abstand_kante(k, p):
    return min(laenge(sub(q, p)) for q in k["punkte"])


def waehle_kanten(kanten, auswahl, tol=1e-3):
    """auswahl: dict oder Liste von dicts (Vereinigung). Gibt Indizes zurück."""
    if isinstance(auswahl, str):
        auswahl = {"alle": True} if auswahl == "alle" else None
    sels = auswahl if isinstance(auswahl, list) else [auswahl]
    treffer = []
    for sel in sels:
        kand = [k for k in kanten if _kante_passt(k, {x: y for x, y in sel.items() if x != "nahe"}, tol)]
        if "nahe" in sel:
            for p in sel["nahe"]:
                if kand:
                    treffer.append(min(kand, key=lambda k: _abstand_kante(k, tuple(p)))["i"])
        else:
            treffer.extend(k["i"] for k in kand)
    return sorted(set(treffer))


def tangential_erweitern(kanten, idx, tol=1e-4):
    """Erweitert die Auswahl um tangential anschließende Kanten (wie 'Tangentenfortsetzung' im CAD).
    Benötigt in den Kantendaten 'enden': [(punkt, tangente), (punkt, tangente)]."""
    nach_i = {k["i"]: k for k in kanten}
    gewaehlt = set(idx)
    offen = list(idx)
    while offen:
        k = nach_i[offen.pop()]
        for p, t in k.get("enden", []):
            for n in kanten:
                if n["i"] in gewaehlt:
                    continue
                for q, s in n.get("enden", []):
                    if laenge(sub(p, q)) < tol and abs(abs(dot(einheit(t), einheit(s))) - 1) < 1e-4:
                        gewaehlt.add(n["i"])
                        offen.append(n["i"])
                        break
    return sorted(gewaehlt)


def _werte_kurz(werte, n=8):
    w = sorted({round(x, 3) + 0.0 for x in werte})
    return ", ".join(f"{x:g}" for x in w[:n]) + (" …" if len(w) > n else "")


def kanten_diagnose(kanten, auswahl, tol=1e-3):
    """Sagt in einem Satz, warum eine Kantenauswahl nichts trifft und was es stattdessen gibt."""
    sels = auswahl if isinstance(auswahl, list) else [auswahl]
    teile = []
    for sel in sels:
        if not isinstance(sel, dict):
            continue
        rest = {k: v for k, v in sel.items() if k != "nahe"}
        if any(_kante_passt(k, rest, tol) for k in kanten):
            continue
        allein_leer = False
        for key, wert in rest.items():
            if any(_kante_passt(k, {key: wert}, tol) for k in kanten):
                continue
            allein_leer = True
            if key == "in_ebene":
                for ax in wert:
                    i = "XYZ".index(ax.upper())
                    da = [k["punkte"][0][i] for k in kanten
                          if max(p[i] for p in k["punkte"]) - min(p[i] for p in k["punkte"]) < tol]
                    teile.append(f"keine Kante liegt in {ax.upper()} = {wert[ax]:g}; Kanten gibt es bei "
                                 f"{ax.upper()} = {_werte_kurz(da)}")
            elif key == "d":
                teile.append(f"kein Kreis mit Ø{wert:g}; vorhandene Kreis-Ø: "
                             f"{_werte_kurz(k['d'] for k in kanten if k['typ'] == 'kreis') or 'keine'}")
            elif key == "parallel":
                teile.append(f"keine gerade Kante parallel zu {wert}")
            elif key == "box":
                teile.append("keine Kantenmitte liegt in der Box")
            elif key == "kreis":
                teile.append("es gibt keine Kreiskanten")
        if not allein_leer:
            teile.append("jede Bedingung trifft für sich Kanten, aber keine Kante erfüllt alle zugleich")
    return "; ".join(teile)


def flaechen_diagnose(flaechen, auswahl):
    """Sagt, welche ebenen Flächen und Zylinder es gibt, wenn eine Flächenauswahl nichts trifft."""
    sels = auswahl if isinstance(auswahl, list) else [auswahl]
    teile = []
    for sel in sels:
        if not isinstance(sel, dict):
            continue
        if "normale" in sel:
            n = _achse(sel["normale"])
            i = [abs(x) for x in n].index(1)
            da = [f["punkt"][i] for f in flaechen if f["typ"] == "ebene" and dot(f["normale"], n) > 1 - 1e-6]
            teile.append(f"ebene Flächen mit Normale {sel['normale']} liegen bei {_werte_kurz(da) or '– (keine)'}")
        if "zylinder" in sel:
            teile.append("vorhandene Zylinder-Ø: "
                         f"{_werte_kurz(f['d'] for f in flaechen if f['typ'] == 'zylinder') or 'keine'}")
    return "; ".join(teile)


def waehle_flaechen(flaechen, auswahl, tol=1e-3):
    sels = auswahl if isinstance(auswahl, list) else [auswahl]
    treffer = []
    for sel in sels:
        kand = list(flaechen)
        if "normale" in sel:
            n = _achse(sel["normale"])
            kand = [f for f in kand if f["typ"] == "ebene" and dot(f["normale"], n) > 1 - 1e-6]
            if "lage" in sel:
                i = [abs(x) for x in n].index(1)
                werte = [f["punkt"][i] for f in kand]
                if sel["lage"] in ("max", "min") and werte:
                    ziel = max(werte) if sel["lage"] == "max" else min(werte)
                else:
                    ziel = float(sel["lage"])
                kand = [f for f in kand if abs(f["punkt"][i] - ziel) < tol]
        if "zylinder" in sel:
            kand = [f for f in kand if f["typ"] == "zylinder" and abs(f["d"] - sel["zylinder"]) < tol]
        if "box" in sel:
            b = sel["box"]
            kand = [f for f in kand if all(b[i] - tol <= f["punkt"][i] <= b[i + 3] + tol for i in range(3))]
        if "nahe" in sel:
            for p in sel["nahe"]:
                if kand:
                    treffer.append(min(kand, key=lambda f: laenge(sub(f["punkt"], tuple(p))))["i"])
        else:
            treffer.extend(f["i"] for f in kand)
    return sorted(set(treffer))


# ---------------------------------------------------------------------------- Soll/Ist
def soll_vergleich(plan, huelle, volumen):
    """huelle = [xmin, ymin, zmin, xmax, ymax, zmax] in mm. Gibt Liste der Abweichungen zurück."""
    abw = []
    soll = plan.get("soll", {})
    h = soll.get("huelle")
    tol = soll.get("toleranz_mm", 0.01)
    if h:
        if len(h) == 3:
            ist = [huelle[3] - huelle[0], huelle[4] - huelle[1], huelle[5] - huelle[2]]
            for ax, s, i in zip("XYZ", h, ist):
                if abs(s - i) > tol:
                    abw.append(f"Hülle {ax}: soll {s:g}, ist {i:.3f}")
        else:
            for k, s, i in zip(("xmin", "ymin", "zmin", "xmax", "ymax", "zmax"), h, huelle):
                if abs(s - i) > tol:
                    abw.append(f"Hülle {k}: soll {s:g}, ist {i:.3f}")
    v = soll.get("volumen")
    if v:
        p = soll.get("toleranz_volumen_prozent", 0.5)
        if abs(volumen - v) > v * p / 100:
            abw.append(f"Volumen: soll {v:g} mm³ (±{p:g} %), ist {volumen:.1f} mm³")
    return abw
