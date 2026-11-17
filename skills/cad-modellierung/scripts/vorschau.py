"""Vorschaubild aus einer STL-Datei: Ansichten und Schnitte, schattiert, mit Kanten.

Nur Python-Standardbibliothek (eigener Z-Puffer, eigener PNG-Schreiber).
    python -I vorschau.py teil.stl teil-vorschau.png [--titel "Halter"] [--groesse 520]
                          [--ansichten iso,vorne,oben,rechts,unten,schnitt:X=0]
Ansichten wie im Bauplan-Koordinatensystem: Vorne = Blick auf −Y-Seite (Z oben), Oben = Blick von +Z,
Rechts = Blick von +X, Iso = von (+X, −Y, +Z). Unten zeigt X nach links (Teil um die Y-Achse gewendet).
Schnitt: das Material zwischen Betrachter und Schnittebene fällt weg, die Schnittfläche ist orange.
  schnitt:X=0  Blick von +X auf die Ebene x = 0      schnitt:Y=5  Blick von vorne (−Y) auf y = 5
  schnitt:Z=3  Blick von oben auf z = 3              Zusatz ":iso" zeigt den Schnitt in der Iso-Ansicht
"""
import argparse
import math
import struct
import sys
import zlib

BLICK = {  # Name: Blickrichtung (zur Kamera), Oben-Vektor
    "iso": ((1, -1, 1), (0, 0, 1)), "vorne": ((0, -1, 0), (0, 0, 1)), "oben": ((0, 0, 1), (0, 1, 0)),
    "rechts": ((1, 0, 0), (0, 0, 1)), "hinten": ((0, 1, 0), (0, 0, 1)), "links": ((-1, 0, 0), (0, 0, 1)),
    "unten": ((0, 0, -1), (0, 1, 0)), "iso_unten": ((1, -1, -1), (0, 0, 1)), "iso_hinten": ((-1, 1, 1), (0, 0, 1)),
}
STANDARD = ["iso", "vorne", "oben", "rechts"]
SCHNITT_BLICK = {"X": "rechts", "Y": "vorne", "Z": "oben"}
GRUND = (178, 190, 206)
KANTE = (35, 40, 48)
HINTER = (255, 255, 255)
SCHNITT = (226, 132, 58)

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
    "=": "00000 00000 11111 00000 11111 00000 00000", ":": "00000 00110 00110 00000 00110 00110 00000",
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
            knick.append((a, b, True))  # Rand: offene Kante, im Schnitt der Umriss der Schnittfläche
        elif _dot(normalen[tl[0]], normalen[tl[1]]) < cos_grenze:
            knick.append((a, b, False))
        else:
            weich.append((a, b, normalen[tl[0]], normalen[tl[1]]))
    return knick, weich


def schneiden(tris, achse, bei):
    """Schneidet das Netz an der Ebene achse = bei und behält die vom Betrachter abgewandte Hälfte
    (X und Z: Werte ≤ bei, Y: Werte ≥ bei). Die Umlaufrichtung der Dreiecke bleibt erhalten."""
    i = "XYZ".index(achse)
    s = -1.0 if achse == "Y" else 1.0
    out = []
    for t in tris:
        d = [s * (p[i] - bei) for p in t]  # > 0: fällt weg
        if max(d) <= 1e-9:
            out.append(t)
            continue
        if min(d) >= -1e-9:
            continue
        poly = []
        for k in range(3):
            a, b, da, db = t[k], t[(k + 1) % 3], d[k], d[(k + 1) % 3]
            if da <= 0:
                poly.append(a)
            if (da < 0 < db) or (db < 0 < da):
                q = da / (da - db)
                poly.append((a[0] + (b[0] - a[0]) * q, a[1] + (b[1] - a[1]) * q, a[2] + (b[2] - a[2]) * q))
        for k in range(1, len(poly) - 1):
            out.append((poly[0], poly[k], poly[k + 1]))
    return out


def ansicht_lesen(a):
    """'oben' | 'schnitt:X=0' | 'schnitt:Y=5:iso' | {"schnitt": "X", "bei": 0, "ansicht": "iso"}
    -> (Titel, Blickname, Schnittachse oder None, Schnittlage)."""
    if isinstance(a, dict):
        achse = str(a["schnitt"]).upper()
        return (f"SCHNITT {achse}={_zahl(a.get('bei', 0))}", str(a.get("ansicht", SCHNITT_BLICK[achse])).lower(),
                achse, float(a.get("bei", 0)))
    s = str(a).strip().lower()
    if s.startswith("schnitt"):
        teile = s.split(":")
        achse, _, wert = teile[1].partition("=")
        achse = achse.strip().upper()
        if achse not in SCHNITT_BLICK:
            raise ValueError(f"Schnitt '{a}': Achse X, Y oder Z, z. B. schnitt:X=0")
        bei = float(wert.replace(",", ".") or 0)
        blick = teile[2] if len(teile) > 2 else SCHNITT_BLICK[achse]
        if blick not in BLICK:
            raise ValueError(f"Ansicht '{blick}' unbekannt ({', '.join(BLICK)})")
        return f"SCHNITT {achse}={_zahl(bei)}", blick, achse, bei
    if s not in BLICK:
        raise ValueError(f"Ansicht '{a}' unbekannt ({', '.join(BLICK)}, schnitt:X=0)")
    return s.upper().replace("_", " "), s, None, 0.0


def _zahl(v):
    return f"{v:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def ueberhang(tris, normalen, grenzwinkel=45.0):
    """Flächen, die beim Druck mit Z nach oben steiler als der Grenzwinkel überhängen (ohne die Auflage).

    Gibt (Überhangfläche mm², [(z, Fläche) …] der drei größten Höhen, Auflagefläche mm²) zurück."""
    zmin = min(p[2] for t in tris for p in t)
    grenze = -math.cos(math.radians(grenzwinkel))
    summe, auflage, stufen = 0.0, 0.0, {}
    for t, n in zip(tris, normalen):
        if n[2] >= grenze:
            continue
        a, b = _sub(t[1], t[0]), _sub(t[2], t[0])
        k = _kreuz(a, b)
        flaeche = 0.5 * math.sqrt(_dot(k, k))
        z = min(t[0][2], t[1][2], t[2][2])
        if z < zmin + 0.05 and n[2] < -0.99:
            auflage += flaeche
            continue
        summe += flaeche
        stufe = round(2 * (t[0][2] + t[1][2] + t[2][2]) / 3) / 2
        stufen[stufe] = stufen.get(stufe, 0.0) + flaeche
    return summe, sorted(stufen.items(), key=lambda kv: -kv[1])[:3], auflage


def zeichne_ansicht(bild, ox, oy, bw, bh, tris, normalen, knick, weich, blick, oben, titel, mass_text,
                    schnitt=False):
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
    geschnitten = bytearray(bw * bh) if schnitt else None  # Bildpunkte, an denen die Schnittfläche zu sehen ist
    licht = _norm((r[0] * -0.4 + u[0] * 0.6 + f[0], r[1] * -0.4 + u[1] * 0.6 + f[1], r[2] * -0.4 + u[2] * 0.6 + f[2]))
    for t, n in zip(tris, normalen):
        rueck = _dot(n, f) < 0
        if rueck:
            n = (-n[0], -n[1], -n[2])
        hell = 0.35 + 0.65 * max(0.0, _dot(n, licht))
        # Im Schnitt sieht man eine Rückseite genau dort, wo die Schnittebene im Material liegt
        farbe = SCHNITT if (rueck and schnitt) else tuple(min(255, int(c * hell)) for c in GRUND)
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
                    if schnitt:
                        geschnitten[i] = rueck
                z += za
    ausdehnung = max(max(xs) - min(xs), max(ys) - min(ys))
    eps = ausdehnung * 0.004
    linien = list(knick) + [(a, b, False) for a, b, n1, n2 in weich if (_dot(n1, f) > 0) != (_dot(n2, f) > 0)]
    for a, b, rand in linien:
        (x0, y0, z0), (x1, y1, z1) = proj(a), proj(b)
        n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for k in range(n + 1):
            t = k / n
            px, py = int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t)
            if ox <= px < ox + bw and oy <= py < oy + bh:
                i = (py - oy) * bw + (px - ox)
                if schnitt and geschnitten[i] and not rand:
                    continue  # Kanten hinter der Schnittfläche liegen im Material und sind nicht zu sehen
                if z0 + (z1 - z0) * t >= zb[i] - eps:
                    bild.setze(px, py, KANTE)
    bild.text(ox + 10, oy + 8, titel)
    if mass_text:
        bild.text(ox + 10, oy + bh - 22, mass_text, (110, 110, 110))


def normalen_von(tris):
    return [_norm(_kreuz(_sub(t[1], t[0]), _sub(t[2], t[0]))) for t in tris]


def _kachel(auftrag, fertig=None):
    """Zeichnet eine Ansicht in ein eigenes Bild und gibt dessen Bildpunkte zurück (läuft auch als Unterprozess).
    fertig: schon berechnete (Normalen, Knickkanten, weiche Kanten) des ungeschnittenen Netzes."""
    tris, name, blick_name, achse, bei, bw, bh, text, tol = auftrag
    blick, oben = BLICK[blick_name]
    bild = Bild(bw, bh)
    if achse:
        tris = schneiden(tris, achse, bei)
        if not tris:
            bild.text(10, 8, name + " - LEER")
            return bytes(bild.px)
        fertig = None
    if fertig is None:
        normalen = normalen_von(tris)
        fertig = (normalen,) + _kanten(tris, normalen, tol)
    zeichne_ansicht(bild, 0, 0, bw, bh, tris, fertig[0], fertig[1], fertig[2], blick, oben, name, text,
                    schnitt=bool(achse))
    return bytes(bild.px)


def rendern(stl, png, titel="", groesse=520, modellmasse=None, ansichten=None, tris=None):
    """modellmasse: exakte Größe [dx, dy, dz] aus dem CAD für die Beschriftung (sonst aus dem Netz).
    ansichten: Liste aus Namen (BLICK) und Schnitten, siehe Modulkopf; Standard sind vier Ansichten.
    tris: schon gelesene Dreiecke (spart das zweite Lesen der STL)."""
    tris = tris or lies_stl(stl)
    if not tris:
        raise SystemExit(f"Keine Dreiecke in {stl}")
    normalen = normalen_von(tris)
    pts = [p for t in tris for p in t]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    diag = math.sqrt(sum((hi[i] - lo[i]) ** 2 for i in range(3)))
    tol = diag * 1e-6 + 1e-9
    knick, weich = _kanten(tris, normalen, tol)
    g = modellmasse or [hi[i] - lo[i] for i in range(3)]
    liste = [ansicht_lesen(a) for a in (ansichten or STANDARD)][:9]
    spalten = 1 if len(liste) == 1 else 2 if len(liste) <= 4 else 3
    zeilen = (len(liste) + spalten - 1) // spalten
    bw, bh = groesse, int(groesse * 0.8)
    kopf = 34 if titel else 0
    bild = Bild(spalten * bw, zeilen * bh + kopf)
    if titel:
        bild.text(12, 10, titel, (20, 20, 20))
    xyz = f"{_zahl(g[0])} × {_zahl(g[1])} × {_zahl(g[2])}"
    zwei = {"X": f"Y {_zahl(g[1])}  Z {_zahl(g[2])}", "Y": f"X {_zahl(g[0])}  Z {_zahl(g[2])}",
            "Z": f"X {_zahl(g[0])}  Y {_zahl(g[1])}"}
    quer = {"vorne": "Y", "hinten": "Y", "oben": "Z", "unten": "Z", "rechts": "X", "links": "X"}
    auftraege = [(tris, name, blick_name, achse, bei, bw, bh, zwei.get(quer.get(blick_name), xyz), tol)
                 for name, blick_name, achse, bei in liste]
    kacheln = None
    if len(liste) > 1 and len(tris) * len(liste) > 12000:  # lohnt erst bei größeren Netzen: Ansichten gleichzeitig
        try:
            import os
            from concurrent.futures import ProcessPoolExecutor
            with ProcessPoolExecutor(max_workers=min(len(liste), os.cpu_count() or 2, 6)) as pool:
                kacheln = list(pool.map(_kachel, auftraege))
        except Exception:
            kacheln = None  # z. B. wenn keine Unterprozesse erlaubt sind: dann nacheinander
    if kacheln is None:
        kacheln = [_kachel(a, (normalen, knick, weich)) for a in auftraege]
    for k, kachel in enumerate(kacheln):
        ox, oy = (k % spalten) * bw, kopf + (k // spalten) * bh
        for y in range(bh):
            ziel = 3 * ((oy + y) * bild.b + ox)
            bild.px[ziel:ziel + 3 * bw] = kachel[3 * y * bw:3 * (y + 1) * bw]
    for z in range(1, zeilen):
        for x in range(spalten * bw):
            bild.setze(x, kopf + z * bh, (215, 215, 215))
    for s in range(1, spalten):
        for y in range(kopf, zeilen * bh + kopf):
            bild.setze(s * bw, y, (215, 215, 215))
    bild.png(png)
    return png


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stl")
    ap.add_argument("png")
    ap.add_argument("--titel", default="")
    ap.add_argument("--groesse", type=int, default=520)
    ap.add_argument("--ansichten", default="", help="z. B. iso,vorne,oben,rechts,unten,schnitt:X=0")
    a = ap.parse_args()
    ans = [x.strip() for x in a.ansichten.split(",") if x.strip()] or None
    print(rendern(a.stl, a.png, a.titel, a.groesse, ansichten=ans))


if __name__ == "__main__":
    sys.exit(main())
