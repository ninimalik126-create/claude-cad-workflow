"""Netz-Werkzeuge für Scans und STL-Dateien: prüfen, vermessen, mit dem Modell vergleichen, in STEP wandeln.

Läuft im Python aus dem FreeCAD-Ordner (bringt numpy, scipy, matplotlib mit). Aufruf über modell.py:

    python -I modell.py netz pruefen <netz> [--bild bild.png]
        Größe, Dreiecke, dicht?, Einzelteile, Auflösung, Wandstärke, Ausrichtung – und ein Vorschaubild.
    python -I modell.py netz schnitte <netz> --achse X|Y|Z (--bei 0,5,10 | --anzahl 5) [--bild b.png] [--json s.json]
        Querschnitte als Maße in Textform: Kreise mit Ø und Mitte, Rechtecke, sonst vereinfachte Konturen.
        Die Punkte im JSON passen direkt als 'kontur' in den Bauplan (Schnitt X -> Ebene YZ, Y -> XZ, Z -> XY).
    python -I modell.py netz vergleich <vorlage> <modell> [--bild b.png] [--grenze 1.0]
        Vorlage (Scan) und Modell aus denselben Blickwinkeln nebeneinander, dazu Abweichung in beide Richtungen.
    python -I modell.py netz koerper <netz> <aus.step> [--facetten 20000] [--stl aus.stl]
        Netz reparieren, vereinfachen und als Volumenkörper (STEP) schreiben – der schnelle Weg „Scan zu STEP“.
    python -I modell.py netz ausrichten <netz> <aus.stl> [--pca | --flaeche-unten]
        Scan an den Hauptachsen ausrichten oder die größte ebene Fläche nach unten legen, Z min = 0.

Netz: STL (binär/ASCII), OBJ, PLY, 3MF. Alle Maße in mm.
"""
import argparse
import json
import math
import os
import struct
import sys

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
STL = np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
ANSICHTEN = [("Iso", (1, -1, 1), (0, 0, 1)), ("Vorne", (0, -1, 0), (0, 0, 1)),
             ("Oben", (0, 0, 1), (0, 1, 0)), ("Rechts", (1, 0, 0), (0, 0, 1))]
QUER = {"X": (1, 2, "Y", "Z"), "Y": (0, 2, "X", "Z"), "Z": (0, 1, "X", "Y")}
TEILER = 2  # Abstandsmessung: Felder des Suchrasters je Zelle und Richtung


def k(v, n=2):
    """Zahl mit Komma, ohne überflüssige Nullen."""
    s = f"{v:.{n}f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s.replace(".", ",")


def t(v):
    """Ganze Zahl mit schmalem Tausendertrenner."""
    return f"{int(round(v)):,}".replace(",", " ")


# ---------------------------------------------------------------------------- Laden und Schreiben
def freecad():
    """FreeCAD-Module laden (nur wo nötig – der Start kostet etwa eine Sekunde)."""
    b = os.environ.get("CCW_FREECAD_BIN") or os.path.dirname(sys.executable)
    for p in (b, os.path.join(os.path.dirname(b), "lib")):
        if os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)
    if hasattr(os, "add_dll_directory") and os.path.isdir(b):
        os.add_dll_directory(b)
    import FreeCAD  # noqa: F401
    import Mesh
    import Part
    return FreeCAD, Mesh, Part


def lade(pfad):
    """Netz als Feld (n, 3, 3) der Dreiecksecken."""
    if not os.path.exists(pfad):
        raise SystemExit(f"Datei nicht gefunden: {pfad}")
    if pfad.lower().endswith(".stl"):
        with open(pfad, "rb") as f:
            kopf = f.read(84)
        if len(kopf) == 84:
            n = struct.unpack("<I", kopf[80:84])[0]
            if os.path.getsize(pfad) == 84 + 50 * n:
                return np.fromfile(pfad, dtype=STL, offset=84, count=n)["v"].astype(np.float64)
    _, Mesh, _ = freecad()
    m = Mesh.Mesh(pfad)
    punkte, flaechen = m.Topology
    if not flaechen:
        raise SystemExit(f"Keine Dreiecke in {pfad}")
    return np.array([(p.x, p.y, p.z) for p in punkte])[np.array(flaechen)]


def schreibe_stl(tri, pfad):
    d = np.zeros(len(tri), dtype=STL)
    d["v"] = tri
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    d["n"] = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-30)
    with open(pfad, "wb") as f:
        f.write(b"claude-cad-workflow".ljust(80, b" ") + struct.pack("<I", len(tri)))
        d.tofile(f)


# ---------------------------------------------------------------------------- Kennwerte
def flaechen_normalen(tri):
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    laenge = np.linalg.norm(n, axis=1)
    return 0.5 * laenge, n / np.maximum(laenge, 1e-30)[:, None]


def topologie(tri):
    """Verschweißt gleiche Ecken und zählt offene und mehrfach belegte Kanten sowie Einzelteile."""
    v = tri.reshape(-1, 3)
    diag = float(np.linalg.norm(v.max(0) - v.min(0)))
    q = np.round(v / max(diag * 1e-6, 1e-5)).astype(np.int64)
    _, inv = np.unique(np.ascontiguousarray(q).view([("", np.int64)] * 3), return_inverse=True)
    f = inv.reshape(-1, 3)
    f = f[(f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 2] != f[:, 0])]
    nv = int(inv.max()) + 1
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    lo, hi = e.min(1), e.max(1)
    _, anz = np.unique(lo * nv + hi, return_counts=True)
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    nk, marke = connected_components(coo_matrix((np.ones(len(lo), dtype=np.int8), (lo, hi)), shape=(nv, nv)),
                                     directed=False)
    teile = np.sort(np.bincount(marke[f[:, 0]], minlength=nk))[::-1]
    return {"ecken": nv, "entartet": len(inv) // 3 - len(f), "offen": int((anz == 1).sum()),
            "mehrfach": int((anz > 2).sum()), "teile": [int(x) for x in teile if x > 0]}


def hauptrichtung(flaeche, normale):
    """Normale der größten ebenen Fläche (flächengewichtet) und ihr Anteil an der Gesamtfläche."""
    kachel = np.round(normale * 40).astype(np.int64)
    schl = (kachel[:, 0] + 50) * 10000 + (kachel[:, 1] + 50) * 100 + (kachel[:, 2] + 50)
    einmal, inv = np.unique(schl, return_inverse=True)
    summe = np.bincount(inv, weights=flaeche)
    beste = int(summe.argmax())
    m = inv == beste
    n = (normale[m] * flaeche[m, None]).sum(0)
    n /= np.linalg.norm(n)
    nah = (normale @ n) > math.cos(math.radians(2.0))
    return n, float(flaeche[nah].sum() / flaeche.sum())


def kennwerte(tri):
    flaeche, normale = flaechen_normalen(tri)
    v = tri.reshape(-1, 3)
    lo, hi = v.min(0), v.max(0)
    vol = float(np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum() / 6)
    kanten = np.linalg.norm(tri[::max(1, len(tri) // 200000), 1] - tri[::max(1, len(tri) // 200000), 0], axis=1)
    return {"dreiecke": len(tri), "lo": lo, "hi": hi, "groesse": hi - lo, "flaeche": float(flaeche.sum()),
            "volumen": vol, "kante": float(np.median(kanten)), "_fl": flaeche, "_n": normale}


# ---------------------------------------------------------------------------- Bilder
def streue(tri, n, saat=1):
    """n zufällige Punkte gleichmäßig auf der Oberfläche; gibt Punkte und Dreiecksnummern zurück."""
    flaeche, _ = flaechen_normalen(tri)
    rng = np.random.default_rng(saat)
    idx = rng.choice(len(tri), size=n, p=flaeche / flaeche.sum())
    a, b = rng.random(n), rng.random(n)
    m = a + b > 1
    a[m], b[m] = 1 - a[m], 1 - b[m]
    d = tri[idx]
    return d[:, 0] + a[:, None] * (d[:, 1] - d[:, 0]) + b[:, None] * (d[:, 2] - d[:, 0]), idx


def bild_ansicht(pts, nrm, blick, oben, huelle, breite, hoehe, wert=None, wmax=1.0, klecks=2):
    """Punktwolke als schattiertes Bild (vorderster Punkt je Bildpunkt). wert färbt nach Abweichung.
    huelle = (kleinste Ecke, größte Ecke): das Bild wird so eingestellt, dass diese Hülle die Kachel füllt."""
    f = np.array(blick, float) / np.linalg.norm(blick)
    r = np.cross(oben, f)
    r /= np.linalg.norm(r)
    u = np.cross(f, r)
    lo, hi = huelle
    ecken = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    ex, ey = ecken @ r, ecken @ u
    skala = 0.94 * min(breite / max(np.ptp(ex), 1e-9), hoehe / max(np.ptp(ey), 1e-9))
    px = ((pts @ r - (ex.min() + ex.max()) / 2) * skala + breite / 2).astype(np.int64)
    py = (hoehe / 2 - (pts @ u - (ey.min() + ey.max()) / 2) * skala).astype(np.int64)
    p = pts
    ok = np.flatnonzero((px >= 0) & (px < breite) & (py >= 0) & (py < hoehe))
    # Von hinten nach vorn eintragen: bei mehrfach belegten Bildpunkten bleibt der zuletzt geschriebene stehen
    vorn = ok[np.argsort((p @ f)[ok], kind="stable")]
    licht = -0.4 * r + 0.6 * u + f
    licht /= np.linalg.norm(licht)
    hell = 0.35 + 0.65 * np.abs(nrm[vorn] @ licht)
    img = np.ones((hoehe * breite, 3))
    if wert is None:
        farbe = np.array([0.70, 0.745, 0.81]) * hell[:, None]
    else:
        import matplotlib
        farbe = matplotlib.colormaps["RdYlGn_r"](np.clip(wert[vorn] / wmax, 0, 1))[:, :3] * (0.6 + 0.4 * hell[:, None])
    # Jeder Punkt färbt ein kleines Feld, damit auch dünn besetzte Seitenflächen geschlossen erscheinen
    x, y = px[vorn], py[vorn]
    for dx in range(klecks):
        for dy in range(klecks):
            img[np.minimum(y + dy, hoehe - 1) * breite + np.minimum(x + dx, breite - 1)] = farbe
    return img.reshape(hoehe, breite, 3)


def rahmen_fuer(*felder):
    """Gemeinsame Hülle (kleinste Ecke, größte Ecke) und Diagonale mehrerer Netze."""
    lo = np.min([f.reshape(-1, 3).min(0) for f in felder], axis=0)
    hi = np.max([f.reshape(-1, 3).max(0) for f in felder], axis=0)
    return (lo, hi), float(np.linalg.norm(hi - lo))


def plt_laden():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def bild_netz(tri, pfad, titel=""):
    plt = plt_laden()
    pts, idx = streue(tri, 900000)
    _, normale = flaechen_normalen(tri)
    huelle, _ = rahmen_fuer(tri)
    b, h = 440, 350
    fig, achsen = plt.subplots(2, 2, figsize=(2 * b / 100, 2 * h / 100 + 0.3), dpi=100)
    for ax, (name, blick, oben) in zip(achsen.ravel(), ANSICHTEN):
        ax.imshow(bild_ansicht(pts, normale[idx], blick, oben, huelle, b, h))
        ax.set_title(name, fontsize=9, loc="left", pad=2)
        ax.axis("off")
    if titel:
        fig.suptitle(titel, fontsize=10, x=0.01, ha="left")
    fig.subplots_adjust(left=0, right=1, bottom=0, top=0.93, wspace=0.01, hspace=0.08)
    fig.savefig(pfad)
    plt.close(fig)
    return pfad


# ---------------------------------------------------------------------------- pruefen
def pruefen(a):
    tri = lade(a.netz)
    w = kennwerte(tri)
    topo = topologie(tri)
    g = w["groesse"]
    dicht = topo["offen"] == 0 and topo["mehrfach"] == 0
    z = [f"{os.path.basename(a.netz)}: {t(w['dreiecke'])} Dreiecke, {t(topo['ecken'])} Ecken",
         f"Größe {k(g[0])} × {k(g[1])} × {k(g[2])} mm | Hülle X {k(w['lo'][0])}…{k(w['hi'][0])}  "
         f"Y {k(w['lo'][1])}…{k(w['hi'][1])}  Z {k(w['lo'][2])}…{k(w['hi'][2])}",
         f"Oberfläche {t(w['flaeche'])} mm² | Auflösung (mittlere Kantenlänge) {k(w['kante'])} mm"]
    if dicht:
        z.append(f"Netz ist dicht: Volumen {t(abs(w['volumen']))} mm³"
                 + (" (Normalen zeigen nach innen)" if w["volumen"] < 0 else ""))
        z.append(f"Mittlere Wandstärke, falls Schale (2·V/A): {k(2 * abs(w['volumen']) / w['flaeche'])} mm")
    else:
        z.append(f"Netz ist NICHT dicht: {t(topo['offen'])} offene Kanten, {t(topo['mehrfach'])} mehrfach belegte "
                 f"Kanten, {t(topo['entartet'])} entartete Dreiecke – Volumen unsicher "
                 f"(≈ {t(abs(w['volumen']))} mm³); 'netz koerper' repariert vor dem Umwandeln")
    teile = topo["teile"]
    if len(teile) > 1:
        klein = [x for x in teile[1:] if x < 0.01 * teile[0]]
        z.append(f"{len(teile)} getrennte Teile: größtes {t(teile[0])} Dreiecke"
                 + (f", {len(klein)} Splitter unter 1 % (werden von 'netz koerper' entfernt)" if klein else "")
                 + (f", weitere große: {', '.join(t(x) for x in teile[1:4] if x >= 0.01 * teile[0])}"
                    if len(klein) < len(teile) - 1 else ""))
    n, anteil = hauptrichtung(w["_fl"], w["_n"])
    achse = int(np.abs(n).argmax())
    winkel = math.degrees(math.acos(min(1.0, abs(n[achse]))))
    if anteil > 0.03:
        z.append(f"Größte ebene Fläche: {k(100 * anteil, 0)} % der Oberfläche, Normale ({k(n[0])}; {k(n[1])}; {k(n[2])})"
                 + (f" – liegt parallel zu {'−' if n[achse] < 0 else '+'}{'XYZ'[achse]}" if winkel < 1
                    else f" – {k(winkel, 1)}° schief zu {'XYZ'[achse]}; 'netz ausrichten --flaeche-unten' legt sie auf Z = 0"))
    else:
        z.append("Keine größere ebene Fläche (Freiform) – Ausrichten höchstens über 'netz ausrichten --pca'")
    print("\n".join(z))
    if a.bild:
        print("Bild: " + bild_netz(tri, os.path.abspath(a.bild), os.path.basename(a.netz)))
    return 0


# ---------------------------------------------------------------------------- schnitte
def schnitt_segmente(tri, achse, wert):
    """Schnittlinien des Netzes mit der Ebene achse = wert als Feld (m, 2, 2) in den beiden Querkoordinaten."""
    i = "XYZ".index(achse)
    d = tri[:, :, i] - wert
    d[d == 0] = 1e-9
    m = ~((d[:, 0] > 0) == (d[:, 1] > 0)) | ~((d[:, 1] > 0) == (d[:, 2] > 0))
    tr, d = tri[m], d[m]
    pts = np.zeros((len(tr), 2, 3))
    voll = np.zeros(len(tr), dtype=np.int64)
    for p, q in ((0, 1), (1, 2), (2, 0)):
        z = np.flatnonzero((d[:, p] > 0) != (d[:, q] > 0))
        anteil = d[z, p] / (d[z, p] - d[z, q])
        pts[z, voll[z]] = tr[z, p] + (tr[z, q] - tr[z, p]) * anteil[:, None]
        voll[z] += 1
    u, v = QUER[achse][:2]
    return pts[voll == 2][:, :, [u, v]]


def ketten(seg, tol):
    """Fügt Strecken zu Linienzügen zusammen. Gibt eine Liste (Punkte, geschlossen) zurück."""
    if not len(seg):
        return []
    q = np.round(seg / tol).astype(np.int64)
    ecke = {}
    for i in range(len(seg)):
        for e in (0, 1):
            ecke.setdefault((q[i, e, 0], q[i, e, 1]), []).append((i, e))
    frei = np.ones(len(seg), dtype=bool)
    out = []
    for start in range(len(seg)):
        if not frei[start]:
            continue
        frei[start] = False
        kette = [seg[start, 0], seg[start, 1]]
        for richtung in (1, 0):  # erst vorwärts vom Ende, dann rückwärts vom Anfang
            ende = (q[start, richtung, 0], q[start, richtung, 1])
            while True:
                weiter = [(i, e) for i, e in ecke.get(ende, []) if frei[i]]
                if not weiter:
                    break
                i, e = weiter[0]
                frei[i] = False
                ende = (q[i, 1 - e, 0], q[i, 1 - e, 1])
                if richtung:
                    kette.append(seg[i, 1 - e])
                else:
                    kette.insert(0, seg[i, 1 - e])
        p = np.array(kette)
        zu = len(p) > 3 and np.linalg.norm(p[0] - p[-1]) < 3 * tol
        out.append((p[:-1] if zu else p, bool(zu)))
    return out


def vereinfachen(p, eps, zu):
    """Douglas-Peucker; bei geschlossenen Zügen vom entferntesten Punktepaar aus."""
    def dp(a):
        if len(a) < 3:
            return a
        halten = np.zeros(len(a), dtype=bool)
        halten[[0, -1]] = True
        stapel = [(0, len(a) - 1)]
        while stapel:
            i, j = stapel.pop()
            if j <= i + 1:
                continue
            ab = a[j] - a[i]
            l = np.linalg.norm(ab)
            rel = a[i + 1:j] - a[i]
            d = np.abs(ab[0] * rel[:, 1] - ab[1] * rel[:, 0]) / l if l > 1e-12 else np.linalg.norm(rel, axis=1)
            m = int(d.argmax())
            if d[m] > eps:
                halten[i + 1 + m] = True
                stapel += [(i, i + 1 + m), (i + 1 + m, j)]
        return a[halten]
    if not zu:
        return dp(p)
    weit = int(np.linalg.norm(p - p[0], axis=1).argmax())
    return np.vstack([dp(p[:weit + 1])[:-1], dp(np.vstack([p[weit:], p[:1]]))[:-1]])


def kreis_einpassen(p):
    """Ausgleichskreis: Mitte, Radius, größte Abweichung."""
    A = np.column_stack([2 * p, np.ones(len(p))])
    (cx, cy, c), *_ = np.linalg.lstsq(A, (p ** 2).sum(1), rcond=None)
    r = math.sqrt(max(c + cx * cx + cy * cy, 0))
    return (float(cx), float(cy)), r, float(np.abs(np.linalg.norm(p - (cx, cy), axis=1) - r).max())


def kontur_beschreiben(p, zu, eps):
    """Erkennt Kreis und Rechteck, sonst vereinfachte Kontur. Gibt ein dict für Text und JSON zurück."""
    lo, hi = p.min(0), p.max(0)
    umfang = float(np.linalg.norm(np.diff(np.vstack([p, p[:1]]) if zu else p, axis=0), axis=1).sum())
    e = {"geschlossen": zu, "umfang": round(umfang, 2), "huelle": [round(float(x), 3) for x in (*lo, *hi)]}
    if zu and len(p) >= 8:
        x, y = p[:, 0], p[:, 1]
        e["flaeche"] = round(abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))) / 2, 2)
        mitte, r, abw = kreis_einpassen(p)
        if abw < max(eps, 0.02 * r) and abs(2 * math.pi * r - umfang) < 0.03 * umfang:
            e.update(art="kreis", d=round(2 * r, 3), mitte=[round(mitte[0], 3), round(mitte[1], 3)],
                     rundheit=round(abw, 3))
            return e
    ecken = vereinfachen(p, eps, zu)
    e["punkte"] = [[round(float(a), 2), round(float(b), 2)] for a, b in ecken]
    if zu and "flaeche" in e:
        # Achsparalleles Rechteck, auch mit Eckenradius: Fläche und Umfang müssen beide zum selben Radius passen
        b, h = (float(x) for x in hi - lo)
        r = math.sqrt(max(b * h - e["flaeche"], 0) / (4 - math.pi))
        if r <= min(b, h) / 2 * 1.02 and abs(2 * (b + h) - (8 - 2 * math.pi) * r - umfang) < 0.01 * umfang:
            mitte = [round(float(lo[0] + b / 2), 3), round(float(lo[1] + h / 2), 3)]
            if r < max(eps, 0.01 * min(b, h)):
                e.update(art="rechteck", masse=[round(b, 3), round(h, 3)], mitte=mitte)
            elif r > 0.49 * min(b, h):
                e.update(art="langloch", masse=[round(max(b, h), 3), round(min(b, h), 3)], mitte=mitte,
                         winkel=0 if b >= h else 90)
            else:
                e.update(art="rechteck", masse=[round(b, 3), round(h, 3)], mitte=mitte, r=round(r, 2))
            return e
    e["art"] = "kontur" if zu else "offen"
    return e


def schnitte(a):
    tri = lade(a.netz)
    achse = a.achse.upper()
    i = "XYZ".index(achse)
    v = tri.reshape(-1, 3)
    lo, hi = float(v[:, i].min()), float(v[:, i].max())
    if a.bei:
        werte = [float(x.replace(",", ".")) for x in a.bei.replace(";", ",").split(",") if x.strip()]
    else:
        n = a.anzahl or 5
        werte = [lo + (hi - lo) * (j + 0.5) / n for j in range(n)]
    diag = float(np.linalg.norm(v.max(0) - v.min(0)))
    tol = max(diag * 2e-6, 2e-5)
    na, nb = QUER[achse][2:]
    alle = []
    print(f"{os.path.basename(a.netz)}: Schnitte quer zu {achse} (Netz reicht von {achse} = {k(lo)} bis {k(hi)}), "
          f"Koordinaten ({na}; {nb}) – im Bauplan Ebene {na}{nb}")
    for w in werte:
        zuege = [(p, zu) for p, zu in ketten(schnitt_segmente(tri, achse, w), tol) if len(p) >= 3]
        laengen = [float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum()) for p, _ in zuege]
        grenze = max(laengen, default=0) * a.klein
        besch = [kontur_beschreiben(p, zu, a.genau) for (p, zu), l in zip(zuege, laengen) if l >= grenze]
        besch.sort(key=lambda e: -e.get("flaeche", 0))
        weg = len(zuege) - len(besch)
        print(f"{achse} = {k(w)}: {len(besch)} Konturen" + (f" ({weg} Splitter weggelassen)" if weg else "")
              + ("" if besch else " – Ebene trifft das Netz nicht"))
        for nr, e in enumerate(besch[:a.max], 1):
            h = e["huelle"]
            innen = any(o is not e and o.get("flaeche", 0) > e.get("flaeche", 0) and o["huelle"][0] <= h[0]
                        and o["huelle"][1] <= h[1] and o["huelle"][2] >= h[2] and o["huelle"][3] >= h[3] for o in besch)
            lage = "innen" if innen else ("außen" if e["geschlossen"] else "offen")
            e["lage"] = lage
            if e["art"] == "kreis":
                print(f"  {nr} {lage}: Kreis Ø{k(e['d'])} bei ({k(e['mitte'][0])}; {k(e['mitte'][1])}), "
                      f"Rundheit {k(e['rundheit'])}")
            elif e["art"] in ("rechteck", "langloch"):
                print(f"  {nr} {lage}: {e['art'].capitalize()} {k(e['masse'][0])} × {k(e['masse'][1])}"
                      + (f" mit Eckenradius R{k(e['r'])}" if e.get("r") else "")
                      + (" (senkrecht)" if e.get("winkel") else "")
                      + f", Mitte ({k(e['mitte'][0])}; {k(e['mitte'][1])})")
            else:
                print(f"  {nr} {lage}: Kontur mit {len(e['punkte'])} Punkten, {na} {k(h[0])}…{k(h[2])}, "
                      f"{nb} {k(h[1])}…{k(h[3])}, Umfang {k(e['umfang'], 1)}"
                      + (f", Fläche {k(e['flaeche'], 1)}" if "flaeche" in e else " (nicht geschlossen)"))
        if len(besch) > a.max:
            print(f"  … {len(besch) - a.max} weitere im JSON")
        alle.append({"achse": achse, "bei": round(w, 4), "ebene": na + nb, "konturen": besch, "_zuege": zuege})
    if a.bild:
        plt = plt_laden()
        n = len(alle)
        sp = min(n, 4)
        ze = (n + sp - 1) // sp
        fig, achsen = plt.subplots(ze, sp, figsize=(4.2 * sp, 3.6 * ze), dpi=90, squeeze=False)
        for ax in achsen.ravel()[n:]:
            ax.axis("off")
        for ax, s in zip(achsen.ravel(), alle):
            for p, zu in s["_zuege"]:
                q = np.vstack([p, p[:1]]) if zu else p
                ax.plot(q[:, 0], q[:, 1], "-", lw=0.9, color="#1f2a38")
            for e in s["konturen"]:
                if e["art"] == "kreis":
                    ax.annotate(f"Ø{k(e['d'])}", e["mitte"], fontsize=7, color="#b3541e", ha="center", va="center")
            ax.set_aspect("equal", adjustable="datalim")
            ax.grid(True, lw=0.3)
            ax.minorticks_on()
            ax.grid(True, which="minor", lw=0.12)
            ax.tick_params(labelsize=7)
            ax.set_title(f"{achse} = {k(s['bei'])}   ({na} waagrecht, {nb} senkrecht)", fontsize=8, loc="left")
        fig.tight_layout()
        fig.savefig(os.path.abspath(a.bild))
        plt.close(fig)
        print("Bild: " + os.path.abspath(a.bild))
    if a.json:
        for s in alle:
            del s["_zuege"]
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(alle, f, ensure_ascii=False, indent=1)
        print("JSON: " + os.path.abspath(a.json))
    return 0


# ---------------------------------------------------------------------------- vergleich
def punkt_dreieck(p, a, b, c):
    """Abstand Punkt–Dreieck für viele Paare zugleich (nach Ericson, Real-Time Collision Detection)."""
    def mal(x, y):  # zeilenweises Skalarprodukt; Summen über die kurze Achse wären deutlich langsamer
        return np.einsum("ij,ij->i", x, y)
    ab, ac, ap = b - a, c - a, p - a
    d1, d2 = mal(ab, ap), mal(ac, ap)
    bp = p - b
    d3, d4 = mal(ab, bp), mal(ac, bp)
    cp = p - c
    d5, d6 = mal(ab, cp), mal(ac, cp)
    va, vb, vc = d3 * d6 - d5 * d4, d5 * d2 - d1 * d6, d1 * d4 - d3 * d2

    def teil(z, n):
        return z / np.where(n == 0, 1, n)
    summe = va + vb + vc
    q = a + ab * teil(vb, summe)[:, None] + ac * teil(vc, summe)[:, None]
    m = (va <= 0) & (d4 - d3 >= 0) & (d5 - d6 >= 0)
    q[m] = (b + (c - b) * teil(d4 - d3, (d4 - d3) + (d5 - d6))[:, None])[m]
    m = (vb <= 0) & (d2 >= 0) & (d6 <= 0)
    q[m] = (a + ac * teil(d2, d2 - d6)[:, None])[m]
    m = (d6 >= 0) & (d5 <= d6)
    q[m] = c[m]
    m = (vc <= 0) & (d1 >= 0) & (d3 <= 0)
    q[m] = (a + ab * teil(d1, d1 - d3)[:, None])[m]
    m = (d3 >= 0) & (d4 <= d3)
    q[m] = b[m]
    m = (d1 <= 0) & (d2 <= 0)
    q[m] = a[m]
    q -= p
    return np.sqrt(mal(q, q))


def unterteilen(tri, lmax, hoechstens=4000000):
    """Halbiert Dreiecke an ihrer längsten Kante, bis keine Kante länger als lmax ist (Umlaufsinn bleibt)."""
    while len(tri) < hoechstens:
        kanten = np.stack([np.linalg.norm(tri[:, 1] - tri[:, 0], axis=1), np.linalg.norm(tri[:, 2] - tri[:, 1], axis=1),
                           np.linalg.norm(tri[:, 0] - tri[:, 2], axis=1)], axis=1)
        lang = kanten.max(1) > lmax
        if not lang.any():
            break
        d, i = tri[lang], kanten[lang].argmax(1)
        z = np.arange(len(d))
        a, b, c = d[z, i], d[z, (i + 1) % 3], d[z, (i + 2) % 3]
        m = (a + b) / 2
        tri = np.concatenate([tri[~lang], np.stack([a, m, c], axis=1), np.stack([m, b, c], axis=1)])
    return tri


def abstaende(pts, tri):
    """Kürzester Abstand jedes Punkts zur Oberfläche tri.

    Große Dreiecke werden zuerst unterteilt. Die nächsten Dreiecksschwerpunkte liefern je Punkt eine obere
    Schranke b. Das wirklich nächste Dreieck muss den Würfel p ± b schneiden; ein Zellenraster liefert alle
    Dreiecke, deren Hülle dort liegt. Vor dem genauen Messen fallen die Paare weg, deren Hüllenabstand schon
    über der Schranke liegt.
    Genau gemessen wird so bis zu einem Abstand von zwei Zellen (Zelle ≈ dreifache Kantenlänge des Netzes,
    höchstens 1/60 der Diagonale). Bei gröberen Abweichungen genügt die Näherung über die 32 nächsten
    Dreiecke – ihr Fehler liegt unter einer Dreiecksgröße und spielt bei mehreren Millimetern keine Rolle."""
    from scipy.spatial import cKDTree
    v = tri.reshape(-1, 3)
    diag = float(np.linalg.norm(v.max(0) - v.min(0)))
    stichprobe = tri[::max(1, len(tri) // 100000)]
    kante = float(np.median(np.linalg.norm(stichprobe[:, 1] - stichprobe[:, 0], axis=1)))
    zelle = min(max(3 * kante, diag / 400), diag / 60)
    tri = unterteilen(tri, zelle)  # danach ist keine Dreieckshülle größer als eine Zelle
    lo, hi = tri.min(1), tri.max(1)
    ursprung = lo.min(0) - 1e-6
    best = np.full(len(pts), np.inf)

    def messen(punkt, dreieck):
        for s in range(0, len(punkt), 3000000):
            p, d = punkt[s:s + 3000000], dreieck[s:s + 3000000]
            q = pts[p]
            luecke = np.maximum(np.maximum(lo[d] - q, q - hi[d]), 0)
            nah = np.einsum("ij,ij->i", luecke, luecke) <= best[p] ** 2
            p, d = p[nah], tri[d[nah]]
            if len(p):
                np.minimum.at(best, p, punkt_dreieck(pts[p], d[:, 0], d[:, 1], d[:, 2]))

    baum = cKDTree(tri.mean(1))
    _, nah = baum.query(pts, k=4, workers=-1)
    for j in range(nah.shape[1]):
        messen(np.arange(len(pts)), nah[:, j])
    fern = np.flatnonzero(best > zelle / 2)
    if len(fern):  # Schranke der entfernteren Punkte verbessern, bevor das Raster sie übernimmt
        _, nah = baum.query(pts[fern], k=32, workers=-1)
        for j in range(nah.shape[1]):
            messen(fern, nah[:, j])
    # Felder kleiner als die Zelle: weniger Dreiecke je Feld, dafür reicht eine Hülle über bis zu TEILER + 1 Felder
    ecken = [(x, y, z) for x in range(TEILER + 1) for y in range(TEILER + 1) for z in range(TEILER + 1)]
    offen = np.arange(len(pts))
    for stufe in range(2):
        jetzt = offen[best[offen] <= zelle / 2]  # ihr Suchwürfel ist höchstens eine Zelle breit
        feld = zelle / TEILER
        offen = offen[best[offen] > zelle / 2]
        if len(jetzt):
            c0 = np.floor((lo - ursprung) / feld).astype(np.int64)
            c1 = np.floor((hi - ursprung) / feld).astype(np.int64)
            n = c1.max(0) + 2

            def schluessel(c):
                return (c[:, 0] * n[1] + c[:, 1]) * n[2] + c[:, 2]
            eintrag, nummer = [], []
            for e in ecken:
                c = c0 + e
                ok = np.flatnonzero((c[:, 0] <= c1[:, 0]) & (c[:, 1] <= c1[:, 1]) & (c[:, 2] <= c1[:, 2]))
                eintrag.append(schluessel(c[ok]))
                nummer.append(ok)
            eintrag, nummer = np.concatenate(eintrag), np.concatenate(nummer)
            ordnung = np.argsort(eintrag, kind="stable")
            eintrag, nummer = eintrag[ordnung], nummer[ordnung]
            zellen, anfang, menge = np.unique(eintrag, return_index=True, return_counts=True)
            q0 = np.floor((pts[jetzt] - best[jetzt, None] - ursprung) / feld).astype(np.int64)
            q1 = np.floor((pts[jetzt] + best[jetzt, None] - ursprung) / feld).astype(np.int64)
            for e in ecken:
                c = q0 + e
                ok = (c[:, 0] <= q1[:, 0]) & (c[:, 1] <= q1[:, 1]) & (c[:, 2] <= q1[:, 2])
                for i in range(3):
                    ok &= (c[:, i] >= 0) & (c[:, i] < n[i])
                ok = np.flatnonzero(ok)
                if not len(ok):
                    continue
                s = schluessel(c[ok])
                ort = np.minimum(np.searchsorted(zellen, s), len(zellen) - 1)
                da = zellen[ort] == s
                p, a, m = jetzt[ok[da]], anfang[ort[da]], menge[ort[da]]
                gesamt = int(m.sum())
                if not gesamt or (stufe and gesamt > 3000000):  # grobes Raster, sehr viele Kandidaten: Näherung
                    continue
                wdh = np.repeat(np.arange(len(p)), m)
                messen(p[wdh], nummer[a[wdh] + np.arange(gesamt) - np.repeat(np.cumsum(m) - m, m)])
        if not len(offen):
            break
        zelle *= 4
    return best


def haeufung(pts, abw, grenze, diag):
    """Die drei Stellen mit den meisten Punkten über der Grenze (grobes Raster)."""
    m = abw > grenze
    if not m.any():
        return []
    zelle = max(diag / 16, 1e-6)
    q = np.floor(pts[m] / zelle).astype(np.int64)
    einmal, inv, anz = np.unique(q, axis=0, return_inverse=True, return_counts=True)
    out = []
    for j in np.argsort(-anz)[:3]:
        sel = inv.ravel() == j
        out.append((pts[m][sel].mean(0), float(abw[m][sel].mean()), float(abw[m][sel].max()),
                    100.0 * anz[j] / len(pts)))
    return out


def vergleich(a):
    A, B = lade(a.vorlage), lade(a.modell)
    huelle, diag = rahmen_fuer(A, B)
    gA, gB = A.reshape(-1, 3), B.reshape(-1, 3)
    na, nb = os.path.basename(a.vorlage), os.path.basename(a.modell)
    print(f"Vorlage {na}: {k(np.ptp(gA[:, 0]))} × {k(np.ptp(gA[:, 1]))} × {k(np.ptp(gA[:, 2]))} mm | "
          f"Modell {nb}: {k(np.ptp(gB[:, 0]))} × {k(np.ptp(gB[:, 1]))} × {k(np.ptp(gB[:, 2]))} mm")
    versatz = (gB.min(0) + gB.max(0)) / 2 - (gA.min(0) + gA.max(0)) / 2
    if np.linalg.norm(versatz) > 0.05 * diag:
        print(f"  ! Die Hüllen liegen um ({k(versatz[0])}; {k(versatz[1])}; {k(versatz[2])}) mm auseinander – "
              f"beide Netze müssen im selben Koordinatensystem liegen")
    n = 100000
    pA, iA = streue(A, n, saat=3)
    pB, iB = streue(B, n, saat=4)
    dA, dB = abstaende(pA, B), abstaende(pB, A)
    g = a.grenze
    for titel, pts, d, sinn in (("Vorlage → Modell", pA, dA, "fehlt im Modell oder sitzt falsch"),
                                ("Modell → Vorlage", pB, dB, "im Modell zu viel oder sitzt falsch")):
        print(f"{titel}: Median {k(np.median(d))} mm, 95 % unter {k(np.percentile(d, 95))} mm, "
              f"größte {k(d.max())} mm, {k(100 * (d > g).mean(), 1)} % über {k(g)} mm")
        for ort, mittel, groesste, anteil in haeufung(pts, d, g, diag):
            print(f"  Abweichung um ({k(ort[0], 1)}; {k(ort[1], 1)}; {k(ort[2], 1)}): im Mittel {k(mittel)} mm, "
                  f"bis {k(groesste)} mm ({k(anteil, 1)} % der Fläche) – {sinn}")
    print("Die Zahlen sind nur die Zusatzprüfung: Freigabe erst nach dem Blick auf das Vergleichsbild "
          "(Form, Proportionen, fehlende Details).")
    if a.bild:
        plt = plt_laden()
        b, h = 380, 300
        rA, jA = streue(A, 700000, saat=5)
        rB, jB = streue(B, 700000, saat=6)
        nA, nB = flaechen_normalen(A)[1], flaechen_normalen(B)[1]
        fig, achsen = plt.subplots(3, 4, figsize=(4 * b / 100, 3 * h / 100 + 0.5), dpi=100)
        for sp, (name, blick, oben) in enumerate(ANSICHTEN):
            achsen[0, sp].imshow(bild_ansicht(rA, nA[jA], blick, oben, huelle, b, h))
            achsen[0, sp].set_title(f"Vorlage – {name}", fontsize=8, loc="left", pad=2)
            achsen[1, sp].imshow(bild_ansicht(rB, nB[jB], blick, oben, huelle, b, h))
            achsen[1, sp].set_title(f"Modell – {name}", fontsize=8, loc="left", pad=2)
        for sp, (name, blick, oben) in enumerate(ANSICHTEN[:1] + ANSICHTEN[2:3]):
            achsen[2, sp].imshow(bild_ansicht(pA, nA[iA], blick, oben, huelle, b, h, wert=dA, wmax=2 * g, klecks=3))
            achsen[2, sp].set_title(f"Abweichung Vorlage → Modell – {name}", fontsize=8, loc="left", pad=2)
            achsen[2, sp + 2].imshow(bild_ansicht(pB, nB[iB], blick, oben, huelle, b, h, wert=dB, wmax=2 * g, klecks=3))
            achsen[2, sp + 2].set_title(f"Abweichung Modell → Vorlage – {name}", fontsize=8, loc="left", pad=2)
        for ax in achsen.ravel():
            ax.axis("off")
        fig.suptitle(f"Farbe: grün = 0 mm, gelb = {k(g)} mm, rot ≥ {k(2 * g)} mm", fontsize=8, x=0.01, y=0.012,
                     ha="left", va="bottom")
        fig.subplots_adjust(left=0, right=1, bottom=0.03, top=0.97, wspace=0.01, hspace=0.1)
        fig.savefig(os.path.abspath(a.bild))
        plt.close(fig)
        print("Bild: " + os.path.abspath(a.bild))
    return 0


# ---------------------------------------------------------------------------- koerper
def verschweissen(tri):
    """Gleiche Ecken zusammenlegen: Eckpunkte P und Dreiecke F als Nummern, ohne entartete Dreiecke."""
    v = tri.reshape(-1, 3)
    diag = float(np.linalg.norm(v.max(0) - v.min(0)))
    q = np.round(v / max(diag * 1e-6, 1e-5)).astype(np.int64)
    _, erst, inv = np.unique(np.ascontiguousarray(q).view([("", np.int64)] * 3), return_index=True,
                             return_inverse=True)
    f = inv.reshape(-1, 3)
    return v[erst], f[(f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 2] != f[:, 0])]


def kanten_zaehlen(f, nv):
    """Je Dreieckskante: wie viele Dreiecke teilen sie (1 = offener Rand, > 2 = mehrfach belegt)."""
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    schl = e.min(1) * nv + e.max(1)
    _, inv, anz = np.unique(schl, return_inverse=True, return_counts=True)
    return e, anz[inv.ravel()]


def netz_schliessen(tri, runden=6):
    """Macht ein fast dichtes Netz dicht: Dreiecke an mehrfach belegten Kanten entfernen und jede Randschleife
    mit einem Fächer zum Schwerpunkt schließen. Für die wenigen Restlöcher, die FreeCAD nicht füllt.
    Gibt (Dreiecke, geschlossene Löcher, offene Kanten am Ende) zurück."""
    geschlossen = 0
    for _ in range(runden):
        P, f = verschweissen(tri)
        e, anz = kanten_zaehlen(f, len(P))
        if (anz > 2).any():
            schlecht = (anz > 2).reshape(3, -1).any(0)
            f = f[~schlecht]
            e, anz = kanten_zaehlen(f, len(P))
        rand = e[anz == 1]
        if not len(rand):
            return P[f], geschlossen, 0
        nach = {}
        for a, b in rand:  # das Füllstück braucht die Kante in Gegenrichtung
            nach.setdefault(int(b), []).append(int(a))
        punkte, neu = [P], []
        naechste = len(P)
        while nach:
            start = next(iter(nach))
            schleife, jetzt = [start], start
            while jetzt in nach:
                ziel = nach[jetzt].pop()
                if not nach[jetzt]:
                    del nach[jetzt]
                if ziel == start:
                    break
                schleife.append(ziel)
                jetzt = ziel
            else:
                continue  # offene Kette ohne Rückweg: bleibt für die nächste Runde
            if len(schleife) < 3:
                continue
            geschlossen += 1
            if len(schleife) == 3:
                neu.append(schleife)
            else:
                punkte.append(P[schleife].mean(0, keepdims=True))
                neu += [[naechste, schleife[i], schleife[(i + 1) % len(schleife)]] for i in range(len(schleife))]
                naechste += 1
        if not neu:
            break
        tri = np.vstack(punkte)[np.vstack([f, np.array(neu, dtype=np.int64)])]
    P, f = verschweissen(tri)
    _, anz = kanten_zaehlen(f, len(P))
    return P[f], geschlossen, int((anz != 2).sum())


def koerper(a):
    _, Mesh, Part = freecad()
    m = Mesh.Mesh(a.netz)
    n0 = m.CountFacets
    print(f"{os.path.basename(a.netz)}: {t(n0)} Dreiecke, dicht: {'ja' if m.isSolid() else 'nein'}")
    schritte = []
    if not a.ohne_reparatur:
        m.removeDuplicatedPoints()
        m.removeDuplicatedFacets()
        m.fixIndices()
        m.fixDegenerations(0.0)
        teile = m.getSeparateComponents()
        if len(teile) > 1:
            teile.sort(key=lambda x: -x.CountFacets)
            behalten = [x for x in teile if x.CountFacets >= 0.01 * teile[0].CountFacets]
            if len(behalten) < len(teile):
                m = Mesh.Mesh()
                for x in behalten:
                    m.addMesh(x)
                schritte.append(f"{len(teile) - len(behalten)} Splitter entfernt")
            if len(behalten) > 1:
                schritte.append(f"{len(behalten)} getrennte Teile bleiben (jedes wird ein eigener Körper)")
        m.removeNonManifolds()
        m.removeNonManifoldPoints()
        if m.hasSelfIntersections():
            m.fixSelfIntersections()
            schritte.append("Selbstdurchdringungen entfernt")
        m.harmonizeNormals()
        m.fillupHoles(a.loch, 1)
        m.removeDuplicatedPoints()
        m.fixIndices()
    if a.facetten and m.CountFacets > a.facetten:
        vor = m.CountFacets
        m.decimate(a.abweichung, 1.0 - a.facetten / vor)
        schritte.append(f"vereinfacht von {t(vor)} auf {t(m.CountFacets)} Dreiecke (Abweichung ≤ {k(a.abweichung)} mm)")
        if not a.ohne_reparatur:
            m.removeNonManifolds()
            m.harmonizeNormals()
            m.fillupHoles(a.loch, 1)
    def schliessen(netz):
        """Restlöcher füllen, die FreeCAD offen lässt (z. B. Ränder, die sich in einer Ecke berühren)."""
        punkte, flaechen = netz.Topology
        tri, loecher, offen = netz_schliessen(np.array([(p.x, p.y, p.z) for p in punkte])[np.array(flaechen)])
        if not loecher:
            return netz, 0
        neu = Mesh.Mesh(tri.tolist())
        neu.harmonizeNormals()
        return neu, loecher

    if not a.ohne_reparatur:
        gefuellt = 0
        if not m.isSolid():
            m, gefuellt = schliessen(m)
        for _ in range(3):  # Durchdringungen: betroffene Dreiecke entfernen und die Lücken neu füllen
            if not (m.isSolid() and m.hasSelfIntersections()):
                break
            versuch = m.copy()
            versuch.fixSelfIntersections()
            versuch.removeNonManifolds()
            versuch.fillupHoles(a.loch, 1)
            versuch, n = schliessen(versuch)
            if not versuch.isSolid() or len(versuch.getSelfIntersections()) >= len(m.getSelfIntersections()):
                break
            m, gefuellt = versuch, gefuellt + n
        if gefuellt:
            schritte.append(f"{gefuellt} Restlöcher mit Füllstücken geschlossen")
    for s in schritte:
        print("  " + s)
    dicht = m.isSolid()
    if dicht and m.hasSelfIntersections():
        print(f"  ! {len(m.getSelfIntersections())} Dreieckspaare durchdringen sich noch – der Körper ist "
              f"geschlossen, Schnitte genau an diesen Stellen können im CAD scheitern")
    print(f"Nach der Aufbereitung: {t(m.CountFacets)} Dreiecke, dicht: {'ja' if dicht else 'NEIN'}, "
          f"Volumen {t(abs(m.Volume))} mm³, Oberfläche {t(m.Area)} mm²")
    if a.stl:
        m.write(os.path.abspath(a.stl))
        print("Netz: " + os.path.abspath(a.stl))
    if not dicht:
        print("FEHLER – das Netz lässt sich nicht automatisch schließen. Es entsteht kein Volumenkörper. Auswege: "
              "größeres --loch (Kanten je Loch), Netz im Scanprogramm oder in MeshLab schließen, "
              "oder das Teil aus Grundformen nachbauen (references/scan-nachbau.md).")
        return 1
    if m.Volume < 0:
        m.flipNormals()
    koerper_liste = []
    for teil in (m.getSeparateComponents() if m.countComponents() > 1 else [m]):
        sh = Part.Shape()
        sh.makeShapeFromMesh(teil.Topology, 0.05)
        koerper_liste.append(Part.makeSolid(sh))
    solid = koerper_liste[0] if len(koerper_liste) == 1 else Part.makeCompound(koerper_liste)
    gueltig = solid.isValid()
    solid.exportStep(os.path.abspath(a.step))
    bb = solid.BoundBox
    print(f"{'OK' if gueltig else 'FEHLER'} – STEP-Volumenkörper: {k(bb.XLength)} × {k(bb.YLength)} × {k(bb.ZLength)} mm, "
          f"Volumen {t(solid.Volume)} mm³, {t(len(solid.Faces))} Flächen, "
          f"{os.path.getsize(os.path.abspath(a.step)) / 1e6:.1f} MB, gültig: {'ja' if gueltig else 'NEIN'}")
    print("Datei: " + os.path.abspath(a.step))
    print("Hinweis: Das ist das Netz als Körper aus Dreiecksflächen (1:1 zum Scan, ohne Konstruktionsverlauf). "
          "Bohren, Schneiden und Anbauen geht im CAD, einzelne Maße ändern nicht.")
    return 0 if gueltig else 1


# ---------------------------------------------------------------------------- ausrichten
def ausrichten(a):
    tri = lade(a.netz)
    v = tri.reshape(-1, 3)
    flaeche, normale = flaechen_normalen(tri)
    if a.flaeche_unten:
        n, anteil = hauptrichtung(flaeche, normale)
        z = -n  # die Fläche zeigt nach unten
        hilf = np.array([1.0, 0, 0]) if abs(z[0]) < 0.9 else np.array([0, 1.0, 0])
        x = np.cross(hilf, z)
        x /= np.linalg.norm(x)
        R = np.vstack([x, np.cross(z, x), z])
        print(f"Größte ebene Fläche ({k(100 * anteil, 0)} % der Oberfläche) liegt jetzt unten")
    else:
        mitte = np.average(tri.mean(1), axis=0, weights=flaeche)
        c = np.cov((tri.mean(1) - mitte).T, aweights=flaeche)
        _, vek = np.linalg.eigh(c)
        R = vek[:, ::-1].T  # größte Ausdehnung -> X, kleinste -> Z
        if np.linalg.det(R) < 0:
            R[2] *= -1
        print("An den Hauptachsen ausgerichtet (längste Richtung = X, kürzeste = Z)")
    neu = (v @ R.T).reshape(-1, 3, 3)
    p = neu.reshape(-1, 3)
    verschiebung = np.array([-(p[:, 0].min() + p[:, 0].max()) / 2, -(p[:, 1].min() + p[:, 1].max()) / 2, -p[:, 2].min()])
    neu = neu + verschiebung
    schreibe_stl(neu, os.path.abspath(a.aus))
    g = neu.reshape(-1, 3)
    print(f"Größe {k(np.ptp(g[:, 0]))} × {k(np.ptp(g[:, 1]))} × {k(np.ptp(g[:, 2]))} mm, Mitte in X/Y auf 0, Z min = 0")
    print("Datei: " + os.path.abspath(a.aus))
    return 0


def main():
    ap = argparse.ArgumentParser(prog="modell.py netz", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="befehl", required=True)
    p = sub.add_parser("pruefen")
    p.add_argument("netz")
    p.add_argument("--bild")
    p = sub.add_parser("schnitte")
    p.add_argument("netz")
    p.add_argument("--achse", required=True, choices=["X", "Y", "Z", "x", "y", "z"])
    p.add_argument("--bei", help="Lagen, z. B. 0,5,12.5")
    p.add_argument("--anzahl", type=int, help="statt --bei: so viele Schnitte gleichmäßig verteilt")
    p.add_argument("--genau", type=float, default=0.1, help="Vereinfachung der Konturen in mm (Standard 0,1)")
    p.add_argument("--klein", type=float, default=0.02, help="Konturen kürzer als dieser Anteil der längsten weglassen")
    p.add_argument("--max", type=int, default=12, help="höchstens so viele Konturen je Schnitt ausgeben")
    p.add_argument("--bild")
    p.add_argument("--json")
    p = sub.add_parser("vergleich")
    p.add_argument("vorlage")
    p.add_argument("modell")
    p.add_argument("--grenze", type=float, default=1.0, help="ab dieser Abweichung in mm zählt eine Stelle als auffällig")
    p.add_argument("--bild")
    p = sub.add_parser("koerper")
    p.add_argument("netz")
    p.add_argument("step")
    p.add_argument("--facetten", type=int, default=20000, help="Zielzahl der Dreiecke (0 = nicht vereinfachen)")
    p.add_argument("--abweichung", type=float, default=0.05, help="erlaubte Abweichung beim Vereinfachen in mm")
    p.add_argument("--loch", type=int, default=2000, help="Löcher bis zu so vielen Randkanten schließen")
    p.add_argument("--stl", help="das aufbereitete Netz zusätzlich als STL schreiben")
    p.add_argument("--ohne-reparatur", action="store_true")
    p = sub.add_parser("ausrichten")
    p.add_argument("netz")
    p.add_argument("aus")
    p.add_argument("--pca", action="store_true")
    p.add_argument("--flaeche-unten", action="store_true")
    arg = sys.argv[1:]
    for i in range(len(arg) - 1):  # '--bei -60,0,60' sonst als Option missverstanden
        if arg[i] == "--bei":
            arg[i:i + 2] = [f"--bei={arg[i + 1]}"]
            break
    a = ap.parse_args(arg)
    return {"pruefen": pruefen, "schnitte": schnitte, "vergleich": vergleich, "koerper": koerper,
            "ausrichten": ausrichten}[a.befehl](a)


if __name__ == "__main__":
    sys.exit(main())
