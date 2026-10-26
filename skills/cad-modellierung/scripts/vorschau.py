"""Vorschaubild aus einer STL-Datei: vier Ansichten (Iso, Vorne, Oben, Rechts), schattiert, mit Kanten.

Nur Python-Standardbibliothek (eigener Z-Puffer, eigener PNG-Schreiber).
    python -I vorschau.py teil.stl teil-vorschau.png [--titel "Halter"] [--groesse 520]
Ansichten wie im Bauplan-Koordinatensystem: Vorne = Blick auf −Y-Seite (Z oben), Oben = Blick von +Z,
Rechts = Blick von +X, Iso = von (+X, −Y, +Z).
"""
import argparse
import math
import struct
import sys
import zlib

ANSICHTEN = [  # Titel, Blickrichtung (zur Kamera), Oben-Vektor
    ("ISO", (1, -1, 1), (0, 0, 1)),
    ("VORNE", (0, -1, 0), (0, 0, 1)),
    ("OBEN", (0, 0, 1), (0, 1, 0)),
    ("RECHTS", (1, 0, 0), (0, 0, 1)),
]
GRUND = (178, 190, 206)
KANTE = (35, 40, 48)
HINTER = (255, 255, 255)

# 5×7-Schrift für die Beschriftung (Zeilen als Bitmuster)
SCHRIFT = {
    "A": "01110 10001 10001 11111 10001 10001 10001", "B": "11110 10001 10001 11110 10001 10001 11110",
    "C": "01111 10000 10000 10000 10000 10000 01111", "D": "11110 10001 10001 10001 10001 10001 11110",
    "E": "11111 10000 10000 11110 10000 10000 11111", "F": "11111 10000 10000 11110 10000 10000 10000",
    "G": "01111 10000 10000 10011 10001 10001 01111", "H": "10001 10001 10001 11111 10001 10001 10001",
    "I": "01110 00100 00100 00100 00100 00100 01110", "J": "00111 00010 00010 00010 00010 10010 01100",
    "K": "10001 10010 10100 11000 10100 10010 10001", "L": "10000 10000 10000 10000 10000 10000 11111",
    "M": "10001 11011 10101 10101 10001 10001 10001", "N": "10001 11001 10101 10011 10001 10001 10001",
    "O": "01110 10001 10001 10001 10001 10001 01110", "P": "11110 10001 10001 11110 10000 10000 10000",
    "Q": "01110 10001 10001 10001 10101 10010 01101", "R": "11110 10001 10001 11110 10100 10010 10001",
    "S": "01111 10000 10000 01110 00001 00001 11110", "T": "11111 00100 00100 00100 00100 00100 00100",
    "U": "10001 10001 10001 10001 10001 10001 01110", "V": "10001 10001 10001 10001 10001 01010 00100",
    "W": "10001 10001 10001 10101 10101 10101 01010", "X": "10001 10001 01010 00100 01010 10001 10001",
    "Y": "10001 10001 01010 00100 00100 00100 00100", "Z": "11111 00001 00010 00100 01000 10000 11111",
    "0": "01110 10011 10101 10101 10101 11001 01110", "1": "00100 01100 00100 00100 00100 00100 01110",
    "2": "01110 10001 00001 00010 00100 01000 11111", "3": "11110 00001 00001 01110 00001 00001 11110",
    "4": "00010 00110 01010 10010 11111 00010 00010", "5": "11111 10000 11110 00001 00001 10001 01110",
    "6": "00110 01000 10000 11110 10001 10001 01110", "7": "11111 00001 00010 00100 01000 01000 01000",
    "8": "01110 10001 10001 01110 10001 10001 01110", "9": "01110 10001 10001 01111 00001 00010 01100",
    ",": "00000 00000 00000 00000 00000 00110 00100", ".": "00000 00000 00000 00000 00000 00110 00110",
    "-": "00000 00000 00000 11111 00000 00000 00000", "×": "00000 10001 01010 00100 01010 10001 00000",
    "_": "00000 00000 00000 00000 00000 00000 11111", " ": "00000 00000 00000 00000 00000 00000 00000",
    "Ä": "01010 00000 01110 10001 11111 10001 10001", "Ö": "01010 00000 01110 10001 10001 10001 01110",
    "Ü": "01010 00000 10001 10001 10001 10001 01110", "(": "00010 00100 01000 01000 01000 00100 00010",
    ")": "01000 00100 00010 00010 00010 00100 01000", "/": "00001 00010 00010 00100 01000 01000 10000",
}


def lies_stl(pfad):
    data = open(pfad, "rb").read()
    if len(data) >= 84:
        n = struct.unpack("<I", data[80:84])[0]
        if 84 + 50 * n == len(data):
            tris = []
            for i in range(n):
                v = struct.unpack("<12f", data[84 + 50 * i: 84 + 50 * i + 48])
                tris.append((v[3:6], v[6:9], v[9:12]))
            return tris
    tris, akt = [], []
    for zeile in data.decode("utf-8", "replace").splitlines():
        t = zeile.split()
        if t and t[0] == "vertex":
            akt.append(tuple(float(x) for x in t[1:4]))
            if len(akt) == 3:
                tris.append(tuple(akt))
                akt = []
    return tris


def _sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def _dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _kreuz(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    n = math.sqrt(_dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n) if n else (0.0, 0.0, 0.0)


class Bild:
    def __init__(self, b, h):
        self.b, self.h = b, h
        self.px = bytearray(HINTER * (b * h))

    def setze(self, x, y, farbe):
        if 0 <= x < self.b and 0 <= y < self.h:
            i = 3 * (y * self.b + x)
            self.px[i:i + 3] = bytes(farbe)

    def text(self, x, y, s, farbe=(60, 60, 60), skala=2):
        for ch in s.upper():
            g = SCHRIFT.get(ch, SCHRIFT[" "]).split()
            for r, zeile in enumerate(g):
                for c, bit in enumerate(zeile):
                    if bit == "1":
                        for dy in range(skala):
                            for dx in range(skala):
                                self.setze(x + c * skala + dx, y + r * skala + dy, farbe)
            x += 6 * skala

    def png(self, pfad):
        roh = b"".join(b"\x00" + bytes(self.px[3 * y * self.b: 3 * (y + 1) * self.b]) for y in range(self.h))

        def chunk(t, d):
            c = t + d
            return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        with open(pfad, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", self.b, self.h, 8, 2, 0, 0, 0))
                    + chunk(b"IDAT", zlib.compress(roh, 6)) + chunk(b"IEND", b""))


def _kanten(tris, normalen, tol):
    """Kanten mit Knick > 25° oder Rand; dazu die Nachbarnormalen für Silhouetten."""
    def key(p):
        return (round(p[0] / tol), round(p[1] / tol), round(p[2] / tol))
    karte = {}
    for ti, t in enumerate(tris):
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            ka, kb = key(a), key(b)
            if ka == kb:
                continue
            k = (ka, kb) if ka < kb else (kb, ka)
            e = karte.setdefault(k, [a, b, []])
            e[2].append(ti)
    knick, weich = [], []
    cos_grenze = math.cos(math.radians(25))
    for a, b, tl in karte.values():
        if len(tl) != 2:
            knick.append((a, b))
        elif _dot(normalen[tl[0]], normalen[tl[1]]) < cos_grenze:
            knick.append((a, b))
        else:
            weich.append((a, b, normalen[tl[0]], normalen[tl[1]]))
    return knick, weich


def zeichne_ansicht(bild, ox, oy, bw, bh, tris, normalen, knick, weich, blick, oben, titel, mass_text):
    f = _norm(blick)
    r = _norm(_kreuz(oben, f))
    u = _kreuz(f, r)
    pts = [p for t in tris for p in t]
    xs = [_dot(p, r) for p in pts]
    ys = [_dot(p, u) for p in pts]
    rand = 30
    s = min((bw - 2 * rand) / max(max(xs) - min(xs), 1e-9), (bh - 2 * rand - 20) / max(max(ys) - min(ys), 1e-9))
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    mx, my = ox + bw / 2, oy + 20 + (bh - 20) / 2

    def proj(p):
        return (mx + (_dot(p, r) - cx) * s, my - (_dot(p, u) - cy) * s, _dot(p, f))
    zb = [-1e30] * (bw * bh)
    licht = _norm((r[0] * -0.4 + u[0] * 0.6 + f[0], r[1] * -0.4 + u[1] * 0.6 + f[1], r[2] * -0.4 + u[2] * 0.6 + f[2]))
    for t, n in zip(tris, normalen):
        if _dot(n, f) < 0:
            n = (-n[0], -n[1], -n[2])
        hell = 0.35 + 0.65 * max(0.0, _dot(n, licht))
        farbe = tuple(min(255, int(c * hell)) for c in GRUND)
        P = (proj(t[0]), proj(t[1]), proj(t[2]))
        (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = P
        flaeche = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if abs(flaeche) < 1e-12:
            continue
        # Tiefe als Ebene z = a·x + b·y + c
        za = ((z1 - z0) * (y2 - y0) - (z2 - z0) * (y1 - y0)) / flaeche
        zbb = ((x1 - x0) * (z2 - z0) - (x2 - x0) * (z1 - z0)) / flaeche
        zc = z0 - za * x0 - zbb * y0
        kanten = [(P[i], P[(i + 1) % 3]) for i in range(3)]
        ya, yb = max(int(min(y0, y1, y2)), oy), min(int(max(y0, y1, y2)) + 1, oy + bh - 1)
        farbe_b = bytes(farbe)
        for py in range(ya, yb + 1):
            yc = py + 0.5
            xs_ = []
            for (ax, ay, _), (bx, by, _) in kanten:  # Zeilen-Spanne statt Rechteck: Aufwand ~ echte Fläche
                if (ay <= yc < by) or (by <= yc < ay):
                    xs_.append(ax + (yc - ay) * (bx - ax) / (by - ay))
            if len(xs_) < 2:
                continue
            xa = max(int(math.ceil(min(xs_) - 0.5)), ox)
            xb = min(int(math.floor(max(xs_) - 0.5)), ox + bw - 1)
            zeile = (py - oy) * bw - ox
            pix = 3 * (py * bild.b)
            z = za * (xa + 0.5) + zbb * yc + zc
            for px in range(xa, xb + 1):
                i = zeile + px
                if z > zb[i]:
                    zb[i] = z
                    j = pix + 3 * px
                    bild.px[j:j + 3] = farbe_b
                z += za
    ausdehnung = max(max(xs) - min(xs), max(ys) - min(ys))
    eps = ausdehnung * 0.004
    linien = list(knick) + [(a, b) for a, b, n1, n2 in weich if (_dot(n1, f) > 0) != (_dot(n2, f) > 0)]
    for a, b in linien:
        (x0, y0, z0), (x1, y1, z1) = proj(a), proj(b)
        n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for k in range(n + 1):
            t = k / n
            px, py = int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t)
            if ox <= px < ox + bw and oy <= py < oy + bh:
                if z0 + (z1 - z0) * t >= zb[(py - oy) * bw + (px - ox)] - eps:
                    bild.setze(px, py, KANTE)
    bild.text(ox + 10, oy + 8, titel)
    if mass_text:
        bild.text(ox + 10, oy + bh - 22, mass_text, (110, 110, 110))


def rendern(stl, png, titel="", groesse=520, modellmasse=None):
    """modellmasse: exakte Größe [dx, dy, dz] aus dem CAD für die Beschriftung (sonst aus dem Netz)."""
    tris = lies_stl(stl)
    if not tris:
        raise SystemExit(f"Keine Dreiecke in {stl}")
    normalen = [_norm(_kreuz(_sub(t[1], t[0]), _sub(t[2], t[0]))) for t in tris]
    pts = [p for t in tris for p in t]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    diag = math.sqrt(sum((hi[i] - lo[i]) ** 2 for i in range(3)))
    knick, weich = _kanten(tris, normalen, diag * 1e-6 + 1e-9)
    g = modellmasse or [hi[i] - lo[i] for i in range(3)]
    fmt = lambda v: f"{v:.2f}".rstrip("0").rstrip(".").replace(".", ",")  # noqa: E731
    bw, bh = groesse, int(groesse * 0.8)
    kopf = 34 if titel else 0
    bild = Bild(2 * bw, 2 * bh + kopf)
    if titel:
        bild.text(12, 10, titel, (20, 20, 20))
    masse = {"ISO": f"{fmt(g[0])} × {fmt(g[1])} × {fmt(g[2])}", "VORNE": f"X {fmt(g[0])}  Z {fmt(g[2])}",
             "OBEN": f"X {fmt(g[0])}  Y {fmt(g[1])}", "RECHTS": f"Y {fmt(g[1])}  Z {fmt(g[2])}"}
    for k, (name, blick, oben) in enumerate(ANSICHTEN):
        ox, oy = (k % 2) * bw, kopf + (k // 2) * bh
        zeichne_ansicht(bild, ox, oy, bw, bh, tris, normalen, knick, weich, blick, oben, name, masse[name])
    for x in range(2 * bw):
        bild.setze(x, kopf + bh, (215, 215, 215))
    for y in range(kopf, 2 * bh + kopf):
        bild.setze(bw, y, (215, 215, 215))
    bild.png(png)
    return png


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stl")
    ap.add_argument("png")
    ap.add_argument("--titel", default="")
    ap.add_argument("--groesse", type=int, default=520)
    a = ap.parse_args()
    print(rendern(a.stl, a.png, a.titel, a.groesse))


if __name__ == "__main__":
    sys.exit(main())
