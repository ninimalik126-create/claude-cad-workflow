"""Prüft mehrere Teile in gemeinsamer Lage (läuft in FreeCADCmd, gestartet von 'modell.py zusammen').

Auftrag (JSON in CCW_AUFTRAG): {"teile": [pfade], "step": pfad oder null, "stl": pfad oder null, "ergebnis": pfad}
Je Paar: Volumen der Durchdringung (muss 0 sein) und kleinster Abstand (= Spiel bzw. Berührung).
"""
import json
import os

import FreeCAD as App
import Part

A = json.load(open(os.environ["CCW_AUFTRAG"], encoding="utf-8"))


def lade(pfad):
    if pfad.lower().endswith(".fcstd"):
        doc = App.openDocument(pfad)
        koerper = [o for o in doc.Objects if o.TypeId == "PartDesign::Body"]
        formen = [o.Shape.copy() for o in (koerper or doc.Objects) if hasattr(o, "Shape") and o.Shape.Solids]
        if not formen:
            raise RuntimeError("kein Volumenkörper in der Datei")
        return formen[0] if len(formen) == 1 else Part.makeCompound(formen)
    s = Part.Shape()
    s.read(pfad)
    if not s.Solids:
        raise RuntimeError("kein Volumenkörper in der Datei")
    return s


e = {"teile": [], "paare": [], "fehler": []}
formen = []
for p in A["teile"]:
    name = os.path.splitext(os.path.basename(p))[0]
    try:
        s = lade(p)
    except Exception as ex:
        e["fehler"].append(f"{name}: {ex}")
        continue
    bb = s.BoundBox
    e["teile"].append({"name": name, "groesse": [bb.XLength, bb.YLength, bb.ZLength], "volumen": s.Volume,
                       "gueltig": s.isValid()})
    formen.append((name, s))
for i in range(len(formen)):
    for j in range(i + 1, len(formen)):
        (na, a), (nb, b) = formen[i], formen[j]
        try:
            gemeinsam = a.common(b)
            v = 0.0 if gemeinsam.isNull() else gemeinsam.Volume
            paar = {"a": na, "b": nb, "durchdringung": v}
            if v > 1e-3:
                paar["ort"] = [round(x, 2) for x in gemeinsam.BoundBox.Center]
            else:
                paar["abstand"] = a.distToShape(b)[0]
            e["paare"].append(paar)
        except Exception as ex:
            e["fehler"].append(f"{na} / {nb}: {ex}")
if formen and A.get("step"):
    Part.makeCompound([s for _, s in formen]).exportStep(A["step"])
    e["step"] = A["step"]
if formen and A.get("stl"):
    import MeshPart
    MeshPart.meshFromShape(Shape=Part.makeCompound([s for _, s in formen]), LinearDeflection=0.05,
                           AngularDeflection=0.2, Relative=False).write(A["stl"])
with open(A["ergebnis"], "w", encoding="utf-8") as fh:
    json.dump(e, fh, ensure_ascii=False)
