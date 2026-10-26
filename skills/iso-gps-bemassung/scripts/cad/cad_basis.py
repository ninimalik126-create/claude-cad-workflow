"""Gemeinsame Grundlagen für alle CAD-Adapter.

Ein Adapter verbindet das Plugin mit einem CAD-Programm. Er kann
  1. ein Teil analysieren  -> neutrales Merkmalsmodell (JSON, Maße in mm)
  2. aus einem Zeichnungsauftrag (JSON) eine native Zeichnung im CAD erzeugen,
     bemaßen, tolerieren, speichern und als PDF ausgeben.

Geometriebezüge im Auftrag zeigen auf Flächen-IDs aus der Analyse ("F12").
Jeder Adapter speichert dazu eine programmeigene, dauerhafte Referenz.
"""
import base64
import json
import math
import sys
import types

MM = 1000.0


class CadFehler(RuntimeError):
    pass


def M(obj, name, *args):
    """Robuster COM-Aufruf für dynamische Dispatch-Objekte.

    Je nach Typinformation liefert win32com Methoden ohne Argumente entweder schon
    aufgerufen (als Wert) oder als gebundene Methode. M() behandelt beides gleich.
    """
    a = getattr(obj, name)
    if args or isinstance(obj, O):
        return a(*args)
    if isinstance(a, types.MethodType):
        return a()
    return a


class O:
    """Hülle für COM-Objekte mit spätem Binden über IDispatch-Namen.

    So sind alle Schnittstellen eines Objekts erreichbar (z. B. IModelDoc2 und IDrawingDoc
    am selben Dokument), unabhängig von Typbibliotheken und CAD-Version.
    Regel: JEDER Zugriff ist ein Aufruf mit Klammern – Eigenschaften und Methoden ohne
    Argumente als doc.GetTitle(), mit Argumenten als doc.SaveAs3(p, 0, 1).
    Eigenschaften setzen per Zuweisung: view.ScaleDecimal = 2.0
    """
    __slots__ = ("_o",)
    _GET = 3  # DISPATCH_METHOD | DISPATCH_PROPERTYGET

    def __init__(self, d):
        object.__setattr__(self, "_o", d._oleobj_ if hasattr(d, "_oleobj_") else d)

    def _dispid(self, name):
        import pywintypes
        try:
            return self._o.GetIDsOfNames(name)
        except pywintypes.com_error:
            raise AttributeError(f"COM-Objekt hat kein Mitglied '{name}'") from None

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        dispid = self._dispid(name)
        o = self._o

        def aufruf(*args):
            return hulle(o.Invoke(dispid, 0, O._GET, True, *[roh(x) for x in args]))
        aufruf.__name__ = name
        return aufruf

    def __setattr__(self, name, value):
        import pythoncom
        self._o.Invoke(self._dispid(name), 0, pythoncom.DISPATCH_PROPERTYPUT, False, roh(value))

    def __bool__(self):
        return True

    def __eq__(self, other):
        return isinstance(other, O) and self._o == other._o

    def __hash__(self):
        return hash(self._o)


def hulle(v):
    import pythoncom
    if isinstance(v, pythoncom.TypeIIDs[pythoncom.IID_IDispatch]):
        return O(v)
    if hasattr(v, "_oleobj_"):
        return O(v)
    if isinstance(v, tuple):
        return tuple(hulle(x) for x in v)
    return v


def roh(v):
    if isinstance(v, O):
        return v._o
    if isinstance(v, (list, tuple)) and any(isinstance(x, O) for x in v):
        return type(v)(roh(x) for x in v)
    return v


def liste(v):
    """COM-Arrays (Tupel, None) als Python-Liste."""
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return list(v)
    return [v]


def b64(data):
    if data is None:
        return None
    return base64.b64encode(bytes(data)).decode("ascii")


def unb64(s):
    return base64.b64decode(s.encode("ascii"))


def runde(v, n=4):
    if isinstance(v, (list, tuple)):
        return [runde(x, n) for x in v]
    r = round(float(v), n)
    return 0.0 if r == 0 else r


def norm(v):
    d = math.sqrt(sum(x * x for x in v))
    return [x / d for x in v] if d else list(v)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def achsname(v, tol=1e-6):
    """'+X', '-Y' … für achsparallele Richtungen, sonst None."""
    for i, n in enumerate("XYZ"):
        if abs(abs(v[i]) - 1) < tol:
            return ("+" if v[i] > 0 else "-") + n
    return None


def ausgabe(obj, pfad=None):
    txt = json.dumps(obj, ensure_ascii=False, indent=2)
    if pfad:
        with open(pfad, "w", encoding="utf-8") as f:
            f.write(txt)
    else:
        sys.stdout.write(txt + "\n")


def zusammenfassen(flaechen):
    """Leitet aus den Einzelflächen Konstruktionsmerkmale ab (Zylindergruppen, Ebenen, Rotationsteil)."""
    zyl = [f for f in flaechen if f["typ"] == "zylinder"]
    ebenen = [f for f in flaechen if f["typ"] == "ebene"]
    achsen = []
    for f in zyl + [f for f in flaechen if f["typ"] == "kegel"]:
        a = f["achse"]
        for g in achsen:
            if abs(abs(dot(g["richtung"], a["richtung"])) - 1) < 1e-6:
                d = [p - q for p, q in zip(a["punkt"], g["punkt"])]
                quer = [d[i] - dot(d, g["richtung"]) * g["richtung"][i] for i in range(3)]
                if math.sqrt(dot(quer, quer)) < 1e-3:
                    g["flaechen"].append(f["id"])
                    break
        else:
            achsen.append({"richtung": a["richtung"], "punkt": a["punkt"], "flaechen": [f["id"]]})
    rot = len(achsen) == 1 and len(zyl) >= 2
    durchmesser = sorted({(f["art"], f["d"]) for f in zyl}, key=lambda t: (t[0], t[1]))
    return {
        "rotationsteil": rot,
        "achsen": [{"richtung": runde(a["richtung"]), "punkt": runde(a["punkt"]), "flaechen": a["flaechen"]}
                   for a in achsen],
        "durchmesser": [{"art": a, "d": d} for a, d in durchmesser],
        "anzahl": {"flaechen": len(flaechen), "zylinder": len(zyl), "ebenen": len(ebenen)},
    }


class Adapter:
    """Schnittstelle, die jeder CAD-Adapter erfüllt."""
    name = "basis"
    getestet = False

    @classmethod
    def verfuegbar(cls):
        """(installiert: bool, laeuft: bool, info: str)"""
        raise NotImplementedError

    def verbinden(self, sichtbar=True):
        raise NotImplementedError

    def analysieren(self, pfad):
        """Gibt ein Merkmalsmodell zurück (dict, Maße in mm)."""
        raise NotImplementedError

    def zeichnen(self, auftrag):
        """Erzeugt eine native Zeichnung aus dem Auftrag. Gibt ein Protokoll (dict) zurück."""
        raise NotImplementedError

    def testteil(self, pfad):
        """Erzeugt das Testteil 'Welle' für den Selbsttest."""
        raise NotImplementedError

    def exportieren(self, pfad, formate=("pdf",)):
        """Vorhandene Zeichnung als PDF/DXF ausgeben; gibt die Dateipfade zurück."""
        raise NotImplementedError

    def schliessen(self):
        """Alle Dokumente ohne Speichern schließen."""
        raise NotImplementedError
