"""zeichnung.py – normgerechte technische Zeichnung (ISO GPS) aus einer JSON-Beschreibung.

Aufruf:
    python -I zeichnung.py teil.json                 # prüft und schreibt teil.svg
    python -I zeichnung.py teil.json --pdf --png     # zusätzlich PDF und PNG (über Edge/Chrome headless)
    python -I zeichnung.py teil.json --nur-pruefen   # nur Prüfung, keine Ausgabe
    python -I zeichnung.py teil.json -o ausgabe/welle.svg

Format der Beschreibung: references/14-generator.md
Exit-Code 1, wenn die Prüfung Fehler findet (Datei wird trotzdem geschrieben).
"""
import argparse
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------- Konstanten

H = 3.5                    # Schrifthöhe Maße (ISO 3098), mm
CAP = 0.716                # Versalhöhe Arial in em
FONT = "Arial, 'Liberation Sans', Helvetica, sans-serif"
W_WIDE, W_NARROW, W_FRAME = 0.5, 0.25, 0.7     # Liniengruppe 0,5
ARROW_L, ARROW_HW = 3.0, 0.55
EXT_GAP, EXT_OVER = 1.0, 2.0
TEXT_GAP = 1.0
DASH = {
    "verdeckt": "3 1",
    "mitte": "9 1.2 0.6 1.2",
    "schnitt": "9 1.2 0.6 1.2",
    "phantom": "9 1.2 0.6 1.2 0.6 1.2",
}
SHEETS = {"A4": (210, 297), "A3": (297, 420), "A2": (420, 594), "A1": (594, 841), "A0": (841, 1189)}

# Zeichenbreiten Arial (em)
CW = {c: 0.556 for c in "0123456789abdeghnopqu$"}
CW.update({",": .278, ".": .278, " ": .278, ":": .278, ";": .278, "/": .278, "|": .26, "(": .333, ")": .333,
           "[": .278, "]": .278, "-": .333, "−": .584, "+": .584, "±": .549, "×": .584, "=": .584, "°": .4,
           "′": .19, "″": .33, "'": .19, "↔": 1.0, "%": .889, "&": .667, "*": .389, "<": .584, ">": .584,
           "c": .5, "k": .5, "s": .5, "v": .5, "x": .5, "y": .5, "z": .5, "f": .278, "t": .278, "r": .333,
           "i": .222, "j": .222, "l": .222, "m": .833, "w": .722,
           "A": .667, "B": .667, "C": .722, "D": .722, "E": .667, "F": .611, "G": .778, "H": .722, "I": .278,
           "J": .5, "K": .667, "L": .556, "M": .833, "N": .722, "O": .778, "P": .667, "Q": .778, "R": .722,
           "S": .667, "T": .611, "U": .722, "V": .667, "W": .944, "X": .667, "Y": .667, "Z": .611,
           "Ä": .667, "Ö": .778, "Ü": .722, "ä": .556, "ö": .556, "ü": .556, "ß": .611, "–": .556, "—": 1.0})

UNICODE_MAP = {"⌀": "{D}", "Ø": "{D}", "ø": "{D}", "□": "{SQ}", "⌴": "{CB}", "⌵": "{CS}", "↧": "{DP}",
               "Ⓔ": "{E}", "Ⓜ": "{M}", "Ⓛ": "{L}", "Ⓟ": "{P}", "Ⓕ": "{F}", "Ⓡ": "{R}", "Ⓣ": "{T}",
               "Ⓤ": "{U}", "Ⓐ": "{A}", "Ⓒ": "{C}", "Ⓖ": "{G}", "Ⓝ": "{N}", "Ⓧ": "{X}"}
TOKEN_RE = re.compile(r"\{(D|SQ|CB|CS|DP|[A-Z])\}")
SYM_W = {"D": 1.0, "SQ": 0.95, "CB": 1.05, "CS": 1.05, "DP": 0.9}
CIRCLED_W = 1.4

CHAR_ALIASES = {
    "geradheit": "geradheit", "⏤": "geradheit",
    "ebenheit": "ebenheit", "⏥": "ebenheit",
    "rundheit": "rundheit", "○": "rundheit",
    "zylinderform": "zylinderform", "⌭": "zylinderform",
    "linienprofil": "linienprofil", "⌒": "linienprofil",
    "flaechenprofil": "flaechenprofil", "flächenprofil": "flaechenprofil", "⌓": "flaechenprofil",
    "parallelitaet": "parallelitaet", "parallelität": "parallelitaet", "∥": "parallelitaet",
    "rechtwinkligkeit": "rechtwinkligkeit", "⟂": "rechtwinkligkeit", "⊥": "rechtwinkligkeit",
    "neigung": "neigung", "∠": "neigung",
    "position": "position", "⌖": "position",
    "koaxialitaet": "koaxialitaet", "koaxialität": "koaxialitaet", "konzentrizitaet": "koaxialitaet",
    "konzentrizität": "koaxialitaet", "◎": "koaxialitaet",
    "symmetrie": "symmetrie", "⌯": "symmetrie",
    "lauf": "lauf", "rundlauf": "lauf", "planlauf": "lauf", "↗": "lauf",
    "gesamtlauf": "gesamtlauf", "⌰": "gesamtlauf",
}
FORM = {"geradheit", "ebenheit", "rundheit", "zylinderform"}
NEEDS_DATUM = {"parallelitaet", "rechtwinkligkeit", "neigung", "koaxialitaet", "symmetrie", "lauf", "gesamtlauf"}
NO_MATERIAL_MOD = {"rundheit", "zylinderform", "linienprofil", "flaechenprofil", "lauf", "gesamtlauf"}


def fnum(v):
    return f"{v:.3f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


def fmt_value(v):
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def esc(s):
    return html.escape(s, quote=True)


def unit(dx, dy):
    d = math.hypot(dx, dy)
    return (dx / d, dy / d) if d else (1.0, 0.0)


def paper_dir(deg):
    """Richtung in Blattkoordinaten (y nach unten) aus Winkel in Grad (mathematisch, 90 = oben)."""
    a = math.radians(deg)
    return math.cos(a), -math.sin(a)


# ---------------------------------------------------------------- Text mit Sonderzeichen

def parse_runs(s):
    s = str(s)
    for k, v in UNICODE_MAP.items():
        s = s.replace(k, v)
    s = re.sub(r"(?<![\w)])-(?=\d)", "−", s)
    runs, pos = [], 0
    for m in TOKEN_RE.finditer(s):
        if m.start() > pos:
            runs.append(("t", s[pos:m.start()]))
        runs.append(("s", m.group(1)))
        pos = m.end()
    if pos < len(s):
        runs.append(("t", s[pos:]))
    return runs


def text_width(s, h):
    fs = h / CAP
    return sum(CW.get(c, 0.667 if c.isupper() else 0.6) for c in s) * fs


def sym_width(name):
    return SYM_W.get(name, CIRCLED_W)


def runs_width(runs, h):
    return sum(text_width(v, h) if k == "t" else sym_width(v) * h for k, v in runs)


def svg_text(x, y, s, h, anchor="start", weight=None):
    fs = h / CAP
    w = f' font-weight="{weight}"' if weight else ""
    return (f'<text x="{x:.3f}" y="{y:.3f}" font-size="{fs:.3f}" text-anchor="{anchor}"{w} '
            f'xml:space="preserve">{esc(s)}</text>')


def draw_symbol(name, x, y, h):
    """Sonderzeichen in Textzeile; x linke Kante, y Grundlinie."""
    sw = max(0.18, h * 0.1)
    st = f'fill="none" stroke="#000" stroke-width="{sw:.3f}" stroke-linecap="round" stroke-linejoin="round"'
    if name == "D":
        cx, cy, r = x + 0.5 * h, y - 0.5 * h, 0.42 * h
        return (f'<circle cx="{cx:.3f}" cy="{cy:.3f}" r="{r:.3f}" {st}/>'
                f'<line x1="{x + 0.08 * h:.3f}" y1="{y + 0.08 * h:.3f}" x2="{x + 0.92 * h:.3f}" '
                f'y2="{y - 1.08 * h:.3f}" {st}/>')
    if name == "SQ":
        s = 0.8 * h
        return f'<rect x="{x + 0.08 * h:.3f}" y="{y - s:.3f}" width="{s:.3f}" height="{s:.3f}" {st}/>'
    if name == "CB":
        p = [(x + .12 * h, y - .85 * h), (x + .12 * h, y - .2 * h), (x + .92 * h, y - .2 * h), (x + .92 * h, y - .85 * h)]
        return poly_svg(p, st)
    if name == "CS":
        p = [(x + .08 * h, y - .9 * h), (x + .52 * h, y - .46 * h), (x + .96 * h, y - .9 * h)]
        return poly_svg(p, st)
    if name == "DP":
        return (poly_svg([(x + .42 * h, y - 1.0 * h), (x + .42 * h, y - .06 * h)], st)
                + poly_svg([(x + .17 * h, y - .36 * h), (x + .42 * h, y - .06 * h), (x + .67 * h, y - .36 * h)], st)
                + poly_svg([(x + .05 * h, y), (x + .8 * h, y)], st))
    # eingekreister Buchstabe
    cx, cy, r = x + 0.7 * h, y - 0.5 * h, 0.62 * h
    lh = 0.72 * h
    return (f'<circle cx="{cx:.3f}" cy="{cy:.3f}" r="{r:.3f}" fill="none" stroke="#000" stroke-width="{sw * .8:.3f}"/>'
            + svg_text(cx, cy + lh / 2, name, lh, "middle"))


def draw_runs(runs, x, y, h):
    out, cx = [], x
    for k, v in runs:
        if k == "t":
            out.append(svg_text(cx, y, v, h))
            cx += text_width(v, h)
        else:
            out.append(draw_symbol(v, cx, y, h))
            cx += sym_width(v) * h
    return "".join(out)


def poly_svg(pts, style):
    d = " ".join(f"{x:.3f},{y:.3f}" for x, y in pts)
    return f'<polyline points="{d}" {style}/>'


class Label:
    """Zusammengesetzte Beschriftung (Maßzahl, Abmaße, Modifikatoren) in lokalen Koordinaten.
    Ursprung links auf der Grundlinie, y nach unten."""

    def __init__(self, h=H):
        self.h, self.items, self.w, self.top, self.bottom = h, [], 0.0, -h, 0.0

    def runs(self, runs, h=None, dy=0.0):
        h = h or self.h
        self.items.append(("runs", self.w, runs, h, dy))
        x0 = self.w
        self.w += runs_width(runs, h)
        self.top, self.bottom = min(self.top, dy - h), max(self.bottom, dy)
        return x0, self.w

    def text(self, s, h=None):
        return self.runs(parse_runs(s), h)

    def space(self, k=0.35):
        if self.items:
            self.w += k * self.h

    def stack(self, up, lo):
        h2 = self.h * 0.8
        x = self.w
        self.items.append(("runs", x, parse_runs(up), h2, -1.3 * h2))
        self.items.append(("runs", x, parse_runs(lo), h2, 0.0))
        self.w += max(runs_width(parse_runs(up), h2), runs_width(parse_runs(lo), h2))
        self.top = min(self.top, -2.3 * h2)

    def box(self, x0, x1):
        p = 0.3 * self.h
        self.items.append(("box", x0 - p, x1 + p, -self.h - p, p))
        self.top = min(self.top, -self.h - p)
        self.bottom = max(self.bottom, p)

    def paren(self, x0, x1):
        self.items.append(("paren", x0, x1))

    def render(self, x, y, rot=0.0, anchor="middle"):
        dx = {"start": 0.0, "middle": -self.w / 2, "end": -self.w}[anchor]
        body = []
        for it in self.items:
            if it[0] == "runs":
                _, xo, runs, h, dy = it
                body.append(draw_runs(runs, dx + xo, dy, h))
            elif it[0] == "box":
                _, x0, x1, y0, y1 = it
                body.append(f'<rect x="{dx + x0:.3f}" y="{y0:.3f}" width="{x1 - x0:.3f}" height="{y1 - y0:.3f}" '
                            f'fill="none" stroke="#000" stroke-width="{W_NARROW}"/>')
        svg = f'<g transform="translate({x:.3f},{y:.3f}) rotate({rot:.3f})">{"".join(body)}</g>'
        pad = 0.15 * self.h
        corners = [(dx - pad, self.top - pad), (dx + self.w + pad, self.top - pad),
                   (dx + self.w + pad, self.bottom + pad), (dx - pad, self.bottom + pad)]
        c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        pts = [(x + px * c - py * s, y + px * s + py * c) for px, py in corners]
        return svg, pts


def build_dim_label(spec, value_text, h=H):
    lab = Label(h)
    main = (spec.get("vor", "") + value_text) if spec.get("text") is None else spec["text"]
    if spec.get("hilfsmass"):
        main = f"({main})"
    x0, x1 = lab.text(main)
    if spec.get("ted"):
        lab.box(x0, x1)
    tol = spec.get("tol")
    if isinstance(tol, dict):
        lab.space()
        lab.stack(tol.get("oben", "0"), tol.get("unten", "0"))
    elif isinstance(tol, str) and tol:
        t = tol.strip()
        if re.match(r"^[+\-−]?\s*\d[\d,.]*\s*/\s*[+\-−]?\s*\d", t) and not t.startswith("±"):
            up, lo = [p.strip() for p in t.split("/", 1)]
            lab.space()
            lab.stack(up, lo)
        else:
            lab.space(0.3)
            lab.text(t)
    if spec.get("nach"):
        lab.space()
        lab.text(spec["nach"])
    return lab


# ---------------------------------------------------------------- GPS-Symbole und Rahmen

def char_symbol(name, cx, cy, h):
    sw = max(0.2, h * 0.09)
    st = f'fill="none" stroke="#000" stroke-width="{sw:.3f}" stroke-linecap="round" stroke-linejoin="round"'

    def L(*pts):
        return poly_svg([(cx + a * h, cy + b * h) for a, b in pts], st)

    def C(r, ox=0.0, oy=0.0):
        return f'<circle cx="{cx + ox * h:.3f}" cy="{cy + oy * h:.3f}" r="{r * h:.3f}" {st}/>'

    if name == "geradheit":
        return L((-.7, 0), (.7, 0))
    if name == "ebenheit":
        return L((-.75, .35), (.35, .35), (.75, -.35), (-.35, -.35), (-.75, .35))
    if name == "rundheit":
        return C(.55)
    if name == "zylinderform":
        u, n, r = (0.5, -0.866), (0.866, 0.5), 0.42
        out = C(r)
        for sgn in (1, -1):
            px, py = sgn * r * n[0], sgn * r * n[1]
            out += L((px - .62 * u[0], py - .62 * u[1]), (px + .62 * u[0], py + .62 * u[1]))
        return out
    if name in ("linienprofil", "flaechenprofil"):
        r = .62 * h
        z = " Z" if name == "flaechenprofil" else ""
        return (f'<path d="M{cx - r:.3f},{cy + .3 * h:.3f} A{r:.3f},{r:.3f} 0 0 1 {cx + r:.3f},{cy + .3 * h:.3f}{z}" '
                f'{st}/>')
    if name == "parallelitaet":
        return L((-.55, .5), (-.05, -.5)) + L((.05, .5), (.55, -.5))
    if name == "rechtwinkligkeit":
        return L((0, -.6), (0, .5)) + L((-.6, .5), (.6, .5))
    if name == "neigung":
        return L((.65, .45), (-.65, .45), (.65, -.3))
    if name == "position":
        return C(.4) + L((-.72, 0), (.72, 0)) + L((0, -.72), (0, .72))
    if name == "koaxialitaet":
        return C(.3) + C(.62)
    if name == "symmetrie":
        return L((-.45, -.38), (.45, -.38)) + L((-.72, 0), (.72, 0)) + L((-.45, .38), (.45, .38))
    if name in ("lauf", "gesamtlauf"):
        def arrow(x0, y0, x1, y1):
            ux, uy = unit(x1 - x0, y1 - y0)
            tipx, tipy = cx + x1 * h, cy + y1 * h
            bx, by = tipx - ux * .45 * h, tipy - uy * .45 * h
            nx, ny = -uy * .2 * h, ux * .2 * h
            return (poly_svg([(cx + x0 * h, cy + y0 * h), (bx, by)], st)
                    + f'<polygon points="{tipx:.3f},{tipy:.3f} {bx + nx:.3f},{by + ny:.3f} {bx - nx:.3f},{by - ny:.3f}" '
                      f'fill="#000"/>')
        if name == "lauf":
            return arrow(-.45, .55, .45, -.55)
        return arrow(-.7, .55, .1, -.55) + arrow(-.1, .55, .7, -.55) + L((-.7, .55), (-.1, .55))
    raise ValueError(f"Unbekannte Eigenschaft '{name}'")


def norm_char(name):
    key = str(name).strip().lower()
    if key in CHAR_ALIASES:
        return CHAR_ALIASES[key]
    if str(name).strip() in CHAR_ALIASES:
        return CHAR_ALIASES[str(name).strip()]
    raise ValueError(f"Unbekannte Toleranzart '{name}'")


def frame_rows(cells):
    return cells if cells and isinstance(cells[0], list) else [cells]


def draw_frame(rows, ax, ay, side="links", h=H, above=None):
    """Toleranzrahmen. (ax, ay) = Mitte der linken (side=links) bzw. rechten Kante der ersten Zeile."""
    fh = 2 * h
    widths = []
    for row in rows:
        w = [fh]
        for c in row[1:]:
            w.append(max(fh, runs_width(parse_runs(c), h) + h))
        widths.append(w)
    total = [sum(w) for w in widths]
    out, boxes = [], []
    top0 = ay - fh / 2
    for i, (row, w) in enumerate(zip(rows, widths)):
        x0 = ax if side == "links" else ax - total[i]
        y0 = top0 + i * fh
        out.append(f'<rect x="{x0:.3f}" y="{y0:.3f}" width="{total[i]:.3f}" height="{fh:.3f}" fill="#fff" '
                   f'stroke="#000" stroke-width="{W_NARROW}"/>')
        cx = x0
        for j, c in enumerate(row):
            if j > 0:
                out.append(f'<line x1="{cx:.3f}" y1="{y0:.3f}" x2="{cx:.3f}" y2="{y0 + fh:.3f}" stroke="#000" '
                           f'stroke-width="{W_NARROW}"/>')
            mid = cx + w[j] / 2
            if j == 0:
                out.append(char_symbol(norm_char(c), mid, y0 + fh / 2, h))
            else:
                runs = parse_runs(c)
                out.append(draw_runs(runs, mid - runs_width(runs, h) / 2, y0 + fh / 2 + h / 2, h))
            cx += w[j]
        boxes.append((x0, y0, x0 + total[i], y0 + fh))
    if above:
        x0 = boxes[0][0]
        runs = parse_runs(above)
        out.append(draw_runs(runs, x0, top0 - 1.0, h))
        boxes.append((x0, top0 - 1.0 - h, x0 + runs_width(runs, h), top0 - 1.0))
    return "".join(out), boxes


def surface_symbol(art, texts, h=H, verfahren=None, rundum=False):
    """Oberflächensymbol lokal: Spitze bei (0,0), aufrecht (y nach unten negativ). Gibt svg, breite, Ecken."""
    H1, H2 = 1.43 * h, 3.0 * h
    s60 = math.sin(math.radians(60))
    sw = W_NARROW
    st = f'fill="none" stroke="#000" stroke-width="{sw}" stroke-linejoin="round"'
    a = (-0.5 * H1, -s60 * H1)
    b = (0.5 * H2, -s60 * H2)
    out = [poly_svg([a, (0, 0), b], st)]
    if art == "abtragen":
        out.append(poly_svg([a, (0.5 * H1, -s60 * H1)], st))
    elif art == "ohne":
        out.append(f'<circle cx="0" cy="{-H1 / math.sqrt(3):.3f}" r="{H1 / (2 * math.sqrt(3)):.3f}" {st}/>')
    tw = 0.0
    lines = [t for t in texts if t]
    for t in lines + ([verfahren] if verfahren else []):
        tw = max(tw, runs_width(parse_runs(t), h))
    right = b[0]
    if lines or verfahren:
        right = b[0] + tw + 1.5
        out.append(poly_svg([b, (right, b[1])], st))
        y = b[1] + 1.0 + h
        for t in lines:
            out.append(draw_runs(parse_runs(t), b[0] + 0.8, y, h))
            y += 1.6 * h
        if verfahren:
            out.append(draw_runs(parse_runs(verfahren), b[0] + 0.8, b[1] - 1.0, h))
    if rundum:
        out.append(f'<circle cx="{b[0]:.3f}" cy="{b[1]:.3f}" r="{0.6 * h:.3f}" {st}/>')
    top = b[1] - (h + 1.5 if verfahren else 0)
    bottom = max(0.0, b[1] + 1.0 + h + (len(lines) - 1) * 1.6 * h if lines else 0.0)
    corners = [(a[0] - 0.3, top - 0.3), (right + 0.3, top - 0.3), (right + 0.3, bottom), (a[0] - 0.3, bottom)]
    return "".join(out), right, corners


# ---------------------------------------------------------------- Zeichnung

class Drawing:
    def __init__(self, spec):
        self.spec = spec
        self.svg = []
        self.boxes = []      # (label, polygon pts, owner)
        self.segs = []       # (p, q, kind, owner)
        self.issues = []
        self.datums_def = []
        self.datums_used = set()
        self._owner = 0
        fmt = spec.get("blatt", {}).get("format", "A4").upper()
        orient = spec.get("blatt", {}).get("ausrichtung", "hoch" if fmt == "A4" else "quer")
        short, long_ = SHEETS[fmt]
        self.W, self.H = (short, long_) if orient == "hoch" else (long_, short)
        self.fmt = fmt
        self.inner = (20.0, 10.0, self.W - 10.0, self.H - 10.0)
        self.tb = (self.inner[2] - 180.0, self.inner[3] - 48.0, self.inner[2], self.inner[3])

    # ---- Grundfunktionen
    def owner(self):
        self._owner += 1
        return self._owner

    def issue(self, level, msg):
        self.issues.append((level, msg))

    def style(self, kind):
        w = W_WIDE if kind in ("kontur", "schnitt") else W_FRAME if kind == "rahmen" else W_NARROW
        st = f'fill="none" stroke="#000" stroke-width="{w}" stroke-linejoin="round"'
        if kind in DASH:
            st += f' stroke-dasharray="{DASH[kind]}" stroke-linecap="butt"'
        else:
            st += ' stroke-linecap="round"'
        return st

    def line(self, pts, kind="schmal", owner=None, record=True):
        self.svg.append(poly_svg(pts, self.style(kind)))
        if record:
            for p, q in zip(pts, pts[1:]):
                self.segs.append((p, q, kind, owner))

    def arrow(self, tip, d, owner=None):
        """Gefüllter Pfeil, Spitze bei tip, d = Richtung, in die der Pfeil zeigt."""
        ux, uy = unit(*d)
        bx, by = tip[0] - ux * ARROW_L, tip[1] - uy * ARROW_L
        nx, ny = -uy * ARROW_HW, ux * ARROW_HW
        self.svg.append(f'<polygon points="{tip[0]:.3f},{tip[1]:.3f} {bx + nx:.3f},{by + ny:.3f} '
                        f'{bx - nx:.3f},{by - ny:.3f}" fill="#000"/>')

    def dot(self, p):
        self.svg.append(f'<circle cx="{p[0]:.3f}" cy="{p[1]:.3f}" r="0.6" fill="#000"/>')

    def add_box(self, label, pts, owner):
        self.boxes.append((label, pts, owner))

    def place(self, label_obj, x, y, rot, anchor, name, owner):
        svg, pts = label_obj.render(x, y, rot, anchor)
        self.svg.append(svg)
        self.add_box(name, pts, owner)

    # ---- Blatt
    def sheet(self):
        W, Hh = self.W, self.H
        x0, y0, x1, y1 = self.inner
        self.svg.append(f'<rect x="0" y="0" width="{W}" height="{Hh}" fill="#fff"/>')
        self.line([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], "rahmen", record=False)
        mx, my = W / 2, Hh / 2
        for p, q in (((mx, 0), (mx, y0 + 5)), ((mx, Hh), (mx, y1 - 5)), ((5, my), (x0 + 5, my)),
                     ((W, my), (x1 - 5, my))):
            self.line([p, q], "rahmen", record=False)

    def title_block(self):
        tb = self.spec.get("schriftfeld", {})
        x0, y0, x1, y1 = self.tb
        st = self.style("rahmen")
        thin = self.style("schmal")
        self.svg.append(f'<rect x="{x0}" y="{y0}" width="180" height="48" fill="#fff" {st}/>')

        def cell(x, y, w, hgt, label, value, vh=3.5, bold=False):
            self.svg.append(f'<rect x="{x:.3f}" y="{y:.3f}" width="{w:.3f}" height="{hgt:.3f}" {thin}/>')
            self.svg.append(svg_text(x + 1, y + 2.6, label, 1.8))
            if value:
                lines = str(value).split("\n")
                # Schrift an Feld anpassen: Höhe unterhalb der Feldbezeichnung und Breite
                avail_h = hgt - 5.2
                vh = min(vh, avail_h / (1 + (len(lines) - 1) * 1.5))
                for ln in lines:
                    lab = Label(1.0)
                    lab.text(ln)
                    vh = min(vh, (w - 2.5) / lab.w)
                vh = max(vh, 1.8)
                yy = y + hgt - 1.4 - (len(lines) - 1) * vh * 1.5
                for ln in lines:
                    lab = Label(vh)
                    lab.text(ln)
                    svg, _ = lab.render(x + 1.5, yy, 0, "start")
                    self.svg.append(svg)
                    yy += vh * 1.5

        g = tb.get
        # Zeile 1: Werkstoff | Maßstab | Masse | Projektion
        cell(x0, y0, 100, 12, "Werkstoff / Halbzeug", g("werkstoff", ""))
        cell(x0 + 100, y0, 25, 12, "Maßstab", g("massstab", "1:1"), 5)
        cell(x0 + 125, y0, 25, 12, "Masse", g("masse", ""), 3.5)
        cell(x0 + 150, y0, 30, 12, "Projektion", "", 3.5)
        self.projection_symbol(x0 + 157, y0 + 7.4)
        # Zeile 2+3: Eigentümer, Ersteller | Titel
        cell(x0, y0 + 12, 70, 12, "Rechtlicher Eigentümer", g("eigentuemer", ""))
        cell(x0, y0 + 24, 25, 12, "Erstellt", g("erstellt", ""), 2.5)
        cell(x0 + 25, y0 + 24, 25, 12, "Genehmigt", g("genehmigt", ""), 2.5)
        cell(x0 + 50, y0 + 24, 20, 12, "Datum", g("datum", ""), 2.5)
        title = g("titel", "")
        if g("untertitel"):
            title = f"{title}\n{g('untertitel')}"
        cell(x0 + 70, y0 + 12, 110, 24, "Titel / Ergänzung", title, 5, bold=True)
        # Zeile 4
        cell(x0, y0 + 36, 30, 12, "Dokumentart", g("dokumentart", "Fertigungszeichnung"), 2.5)
        cell(x0 + 30, y0 + 36, 25, 12, "Status", g("status", "Entwurf"), 2.5)
        cell(x0 + 55, y0 + 36, 75, 12, "Zeichnungsnummer", g("zeichnungsnummer", ""), 5, bold=True)
        cell(x0 + 130, y0 + 36, 15, 12, "Index", g("index", "–"), 3.5)
        cell(x0 + 145, y0 + 36, 15, 12, "Sprache", g("sprache", "de"), 2.5)
        cell(x0 + 160, y0 + 36, 20, 12, "Blatt", g("blatt", "1/1"), 3.5)
        self.add_box("Schriftfeld", [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], -1)

    def projection_symbol(self, x, y):
        """Projektionsmethode 1 (ISO 5456-2), Mitte links bei (x, y)."""
        st = self.style("schmal")
        h = 2.6
        self.svg.append(poly_svg([(x, y - h / 2), (x + 5, y - h), (x + 5, y + h), (x, y + h / 2), (x, y - h / 2)], st))
        self.svg.append(f'<circle cx="{x + 11:.3f}" cy="{y:.3f}" r="{h:.3f}" {st}/>')
        self.svg.append(f'<circle cx="{x + 11:.3f}" cy="{y:.3f}" r="{h / 2:.3f}" {st}/>')
        cs = self.style("schmal")
        self.svg.append(poly_svg([(x - 1, y), (x + 14.5, y)], cs))
        self.svg.append(poly_svg([(x + 11, y - h - 1), (x + 11, y + h + 1)], cs))

    def notes(self):
        x0, y0 = self.tb[0] + 1.0, self.tb[1]
        notes = list(self.spec.get("hinweise", []))
        y = y0 - 3.0
        for n in reversed(notes):
            lab = Label(3.5)
            lab.text(n)
            self.place(lab, x0, y, 0, "start", f"Hinweis '{n[:20]}'", -1)
            y -= 6.0
        sammel = self.spec.get("oberflaeche_sammel")
        if sammel:
            self.collective_surface(x0, y - 2.0, sammel)

    def collective_surface(self, x, y, s):
        """Sammelangabe Oberfläche: Grundlinie y (Spitze des Symbols)."""
        owner = self.owner()
        art = s.get("art", "abtragen")
        svg, right, corners = surface_symbol(art, [s.get("wert", "")], 3.5)
        cx = x + 3
        self.svg.append(f'<g transform="translate({cx:.3f},{y:.3f})">{svg}</g>')
        pts = [(cx + a, y + b) for a, b in corners]
        xx = cx + right + 2
        klammer = s.get("klammer", [""])
        if klammer is not None:
            self.svg.append(svg_text(xx, y + 1, "(", 9))
            xx += text_width("(", 9) + 3
            for k in klammer:
                ksvg, kr, _ = surface_symbol(art, [k] if k else [], 3.5)
                self.svg.append(f'<g transform="translate({xx:.3f},{y:.3f})">{ksvg}</g>')
                xx += kr + 4
            self.svg.append(svg_text(xx - 1, y + 1, ")", 9))
            xx += text_width(")", 9)
        top = min(p[1] for p in pts) - 2
        self.add_box("Oberflächen-Sammelangabe", [(x, top), (xx, top), (xx, y + 2), (x, y + 2)], owner)

    # ---- Ansichten
    def view(self, v):
        ox, oy = v["ursprung"]
        sc = v.get("massstab", 1)
        if isinstance(sc, str):
            a, b = sc.split(":")
            sc = float(a) / float(b)
        self.s = float(sc)
        self.o = (float(ox), float(oy))
        name = v.get("name", "Ansicht")
        for el in v.get("elemente", []):
            self.element(el, name)
        for an in v.get("masse", []):
            try:
                self.annotation(an, name)
            except (KeyError, ValueError, TypeError) as e:
                self.issue("FEHLER", f"{name}: Eintrag {an.get('typ')} fehlerhaft ({e})")
        if v.get("titel"):
            pos = v.get("titel_pos")
            if pos:
                x, y = self.P(pos)
            else:
                ys = [p[1] for p, q, k, o in self.segs if o == ("geo", name)] or [self.o[1]]
                xs = [p[0] for p, q, k, o in self.segs if o == ("geo", name)] or [self.o[0]]
                x, y = (min(xs) + max(xs)) / 2, min(ys) - 18
            lab = Label(5)
            lab.text(v["titel"])
            self.place(lab, x, y, 0, "middle", f"Titel {v['titel']}", self.owner())

    def P(self, p):
        return self.o[0] + p[0] * self.s, self.o[1] - p[1] * self.s

    def element(self, el, vname):
        t = el["typ"]
        art = el.get("art", "kontur")
        own = ("geo", vname)
        if t == "linie":
            pts = [self.P(p) for p in el["p"]]
            if el.get("geschlossen"):
                pts.append(pts[0])
            self.line(pts, art, own)
        elif t == "rechteck":
            (x0, y0), (x1, y1) = el["p1"], el["p2"]
            self.line([self.P(p) for p in ((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))], art, own)
        elif t == "kreis":
            cx, cy = self.P(el["m"])
            r = el["r"] * self.s
            self.svg.append(f'<circle cx="{cx:.3f}" cy="{cy:.3f}" r="{r:.3f}" {self.style(art)}/>')
            pts = [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in [i * math.pi / 24 for i in range(49)]]
            for p, q in zip(pts, pts[1:]):
                self.segs.append((p, q, art, own))
        elif t == "bogen":
            m, r = el["m"], el["r"]
            a0, a1 = math.radians(el["von"]), math.radians(el["bis"])
            if a1 < a0:
                a1 += 2 * math.pi
            p0 = self.P((m[0] + r * math.cos(a0), m[1] + r * math.sin(a0)))
            p1 = self.P((m[0] + r * math.cos(a1), m[1] + r * math.sin(a1)))
            large = 1 if (a1 - a0) > math.pi else 0
            rs = r * self.s
            self.svg.append(f'<path d="M{p0[0]:.3f},{p0[1]:.3f} A{rs:.3f},{rs:.3f} 0 {large} 0 '
                            f'{p1[0]:.3f},{p1[1]:.3f}" {self.style(art)}/>')
            n = max(4, int((a1 - a0) / (math.pi / 24)))
            pts = [self.P((m[0] + r * math.cos(a0 + (a1 - a0) * i / n), m[1] + r * math.sin(a0 + (a1 - a0) * i / n)))
                   for i in range(n + 1)]
            for p, q in zip(pts, pts[1:]):
                self.segs.append((p, q, art, own))
        elif t == "mittellinie":
            a, b = self.P(el["p"][0]), self.P(el["p"][1])
            u = unit(b[0] - a[0], b[1] - a[1])
            o = el.get("ueberstand", 3.0)
            self.line([(a[0] - u[0] * o, a[1] - u[1] * o), (b[0] + u[0] * o, b[1] + u[1] * o)], "mitte", own)
        elif t == "mittelkreuz":
            cx, cy = self.P(el["m"])
            r = el["r"] * self.s + el.get("ueberstand", 3.0)
            kind = "mitte" if el["r"] * self.s >= 6 else "schmal"
            self.line([(cx - r, cy), (cx + r, cy)], kind, own)
            self.line([(cx, cy - r), (cx, cy + r)], kind, own)
        elif t == "teilkreis":
            cx, cy = self.P(el["m"])
            r = el["r"] * self.s
            self.svg.append(f'<circle cx="{cx:.3f}" cy="{cy:.3f}" r="{r:.3f}" {self.style("mitte")}/>')
        elif t == "gewindekreis":
            m, r = el["m"], el["r"]
            start = el.get("von", 0)
            self.element({"typ": "bogen", "m": m, "r": r, "von": start, "bis": start + 270, "art": "schmal"}, vname)
        elif t == "schraffur":
            self.hatch(el, own)
        else:
            self.issue("FEHLER", f"{vname}: unbekanntes Element '{t}'")

    def hatch(self, el, own):
        polys = [el["p"]] + el.get("loecher", [])
        ppolys = [[self.P(p) for p in poly] for poly in polys]
        cid = f"clip{self.owner()}"
        d = " ".join("M" + " L".join(f"{x:.3f},{y:.3f}" for x, y in pp) + " Z" for pp in ppolys)
        self.svg.append(f'<clipPath id="{cid}"><path d="{d}" clip-rule="evenodd"/></clipPath>')
        xs = [p[0] for p in ppolys[0]]
        ys = [p[1] for p in ppolys[0]]
        ang = math.radians(el.get("winkel", 45))
        step = el.get("abstand", 2.5)
        ux, uy = math.cos(ang), -math.sin(ang)
        nx, ny = -uy, ux
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        R = math.hypot(max(xs) - min(xs), max(ys) - min(ys)) / 2 + step
        lines = []
        k = -R
        while k <= R:
            px, py = cx + nx * k, cy + ny * k
            lines.append(f'<line x1="{px - ux * R:.3f}" y1="{py - uy * R:.3f}" x2="{px + ux * R:.3f}" '
                         f'y2="{py + uy * R:.3f}"/>')
            k += step
        self.svg.append(f'<g clip-path="url(#{cid})" stroke="#000" stroke-width="{W_NARROW}">{"".join(lines)}</g>')

    # ---- Bemaßung und Symbole
    def annotation(self, a, vname):
        t = a["typ"]
        fn = {"laenge": self.dim_linear, "durchmesser": self.dim_diameter, "radius": self.dim_radius,
              "winkel": self.dim_angle, "hinweis": self.leader_note, "rahmen": self.gps_frame,
              "bezug": self.datum, "oberflaeche": self.surface, "text": self.free_text,
              "schnittlinie": self.section_line, "einzelheit": self.detail_mark}.get(t)
        if not fn:
            raise ValueError(f"unbekannter Typ '{t}'")
        self.check_text_fields(a, vname)
        fn(a, vname)

    def check_text_fields(self, a, vname):
        for key in ("text", "tol", "vor", "nach"):
            v = a.get(key)
            vals = list(v.values()) if isinstance(v, dict) else [v] if isinstance(v, str) else []
            for s in vals:
                if re.search(r"\d\.\d", s):
                    self.issue("WARNUNG", f"{vname}: '{s}' mit Dezimalpunkt – auf deutschsprachigen Zeichnungen "
                                          f"Dezimalkomma verwenden")
        tol = a.get("tol")
        devs = None
        if isinstance(tol, dict):
            devs = [tol.get("oben", "0"), tol.get("unten", "0")]
        elif isinstance(tol, str) and re.match(r"^[+\-−]?\s*\d[\d,.]*\s*/\s*[+\-−]?\s*\d", tol.strip()):
            devs = [p.strip() for p in tol.split("/", 1)]
        if devs:
            decs = [len(re.split(r"[,.]", d)[1]) if re.search(r"[,.]", d) else 0 for d in devs
                    if re.sub(r"[+\-−\s]", "", d) not in ("0",)]
            if len(set(decs)) > 1:
                self.issue("WARNUNG", f"{vname}: Abmaße {devs[0]} / {devs[1]} mit unterschiedlicher Stellenzahl "
                                      f"(ISO 129-1: gleiche Anzahl Dezimalstellen)")
            for d in devs:
                if re.sub(r"\s", "", d) in ("+0", "−0", "-0"):
                    self.issue("WARNUNG", f"{vname}: Abmaß '{d}' – Null ohne Vorzeichen schreiben")
        if a.get("ted") and a.get("tol"):
            self.issue("FEHLER", f"{vname}: theoretisch genaues Maß mit Toleranz '{a.get('tol')}'")

    def dim_linear(self, a, vname):
        own = self.owner()
        p1, p2 = self.P(a["p1"]), self.P(a["p2"])
        mode = a.get("richtung", "h")
        off = float(a.get("abstand", 10))
        lage = a.get("lage")  # Bezugskoordinate (Teil) für die Maßlinie, z. B. Außenkontur
        if mode == "h":
            if lage is not None:
                ref = self.P((0, lage))[1]
            else:
                ref = min(p1[1], p2[1]) if off > 0 else max(p1[1], p2[1])
            yd = ref - off
            A, B = (p1[0], yd), (p2[0], yd)
            value = abs(a["p2"][0] - a["p1"][0])
        elif mode == "v":
            if lage is not None:
                ref = self.P((lage, 0))[0]
            else:
                ref = max(p1[0], p2[0]) if off > 0 else min(p1[0], p2[0])
            xd = ref + off
            A, B = (xd, p1[1]), (xd, p2[1])
            value = abs(a["p2"][1] - a["p1"][1])
        else:
            u = unit(p2[0] - p1[0], p2[1] - p1[1])
            n = (u[1], -u[0])  # links der Richtung p1->p2 (Blatt, y unten)
            A = (p1[0] + n[0] * off, p1[1] + n[1] * off)
            B = (p2[0] + n[0] * off, p2[1] + n[1] * off)
            value = math.hypot(a["p2"][0] - a["p1"][0], a["p2"][1] - a["p1"][1])
        # Maßhilfslinien
        for p, q in ((p1, A), (p2, B)):
            d = math.hypot(q[0] - p[0], q[1] - p[1])
            if d > EXT_GAP + 0.5:
                u = unit(q[0] - p[0], q[1] - p[1])
                gap = 0.0 if a.get("hilfslinie_ohne_abstand") else EXT_GAP
                self.line([(p[0] + u[0] * gap, p[1] + u[1] * gap), (q[0] + u[0] * EXT_OVER, q[1] + u[1] * EXT_OVER)],
                          "schmal", own)
        # Richtung, Textlage
        if B[0] < A[0] - 1e-9 or (abs(B[0] - A[0]) < 1e-9 and B[1] > A[1]):
            A, B = B, A  # A links bzw. unten
        u = unit(B[0] - A[0], B[1] - A[1])
        rot = math.degrees(math.atan2(u[1], u[0]))
        L = math.hypot(B[0] - A[0], B[1] - A[1])
        lab = build_dim_label(a, fmt_value(value))
        inside = L >= 2 * ARROW_L + 1.5
        ext_a = ext_b = 0.0
        if not inside:
            ext_a = ext_b = ARROW_L + 3
        shift = a.get("textpos")
        if shift is None:
            room = L - (2 * ARROW_L + 2 if inside else 0)
            shift = 0.0 if lab.w + 1.0 <= room else (L / 2 + ARROW_L + 2 + lab.w / 2 + (ext_b if not inside else 1))
        shift = float(shift)
        tx, ty = (A[0] + B[0]) / 2 + u[0] * shift, (A[1] + B[1]) / 2 + u[1] * shift
        # Maßlinie verlängern, falls Text außerhalb
        tpos = L / 2 + shift
        start = min(-ext_a, tpos - lab.w / 2 - 0.5) if tpos < 0 else -ext_a
        end = max(L + ext_b, tpos + lab.w / 2 + 0.5) if tpos > L else L + ext_b
        self.line([(A[0] + u[0] * start, A[1] + u[1] * start), (A[0] + u[0] * end, A[1] + u[1] * end)], "schmal", own)
        if inside:
            self.arrow(A, (-u[0], -u[1]))
            self.arrow(B, u)
        else:
            self.arrow(A, u)
            self.arrow(B, (-u[0], -u[1]))
        nx, ny = u[1], -u[0]  # oberhalb der Maßlinie
        gx, gy = tx + nx * TEXT_GAP, ty + ny * TEXT_GAP
        self.place(lab, gx, gy, rot, "middle", f"Maß {a.get('text') or a.get('vor', '') + fmt_value(value)}", own)

    def leader_text(self, start, label, own, name, side=None):
        """Bezugsschulter mit Text ab start (Blatt), Richtung side (+1 rechts, -1 links)."""
        side = side or 1
        end = (start[0] + side * (label.w + 1.0), start[1])
        self.line([start, end], "schmal", own)
        x = start[0] + side * 0.5
        self.place(label, x, start[1] - TEXT_GAP, 0, "start" if side > 0 else "end", name, own)

    def frame_under(self, K, side, rows, own, vname):
        """Toleranzrahmen direkt unter der Bezugsschulter einer Maß-/Hinweisangabe (gilt für das Maßelement)."""
        rows = frame_rows(rows)
        for row in rows:
            self.check_frame(row, vname)
        svg, boxes = draw_frame(rows, K[0], K[1] + H, "links" if side > 0 else "rechts", H)
        self.svg.append(svg)
        for b in boxes:
            self.add_box(f"Toleranzrahmen {'|'.join(str(c) for c in rows[0])}",
                         [(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])], own)

    def dim_diameter(self, a, vname):
        own = self.owner()
        m = self.P(a["m"])
        r = a["r"] * self.s
        ang = a.get("winkel", 45)
        d = paper_dir(ang)
        A = (m[0] + d[0] * r, m[1] + d[1] * r)
        B = (m[0] - d[0] * r, m[1] - d[1] * r)
        ext = a.get("laenge", 8)
        E = (A[0] + d[0] * ext, A[1] + d[1] * ext)
        lab = build_dim_label(a, fmt_value(2 * a["r"]))
        if not a.get("vor") and a.get("text") is None:
            lab = build_dim_label({**a, "vor": "{D}"}, fmt_value(2 * a["r"]))
        self.line([B, E], "schmal", own)
        self.arrow(A, d)
        self.arrow(B, (-d[0], -d[1]))
        side = 1 if d[0] >= -1e-9 else -1
        self.leader_text(E, lab, own, f"Durchmesser {fmt_value(2 * a['r'])}", side)
        if a.get("rahmen"):
            self.frame_under(E, side, a["rahmen"], own, vname)

    def dim_radius(self, a, vname):
        own = self.owner()
        m = self.P(a["m"])
        r = a["r"] * self.s
        d = paper_dir(a.get("winkel", 45))
        A = (m[0] + d[0] * r, m[1] + d[1] * r)
        spec = {**a}
        if spec.get("text") is None and not spec.get("vor"):
            spec["vor"] = "R"
        lab = build_dim_label(spec, fmt_value(a["r"]))
        if a.get("innen"):
            S = m if r <= 30 else (A[0] - d[0] * 30, A[1] - d[1] * 30)
            self.line([S, A], "schmal", own)
            self.arrow(A, d)
            u = d if d[0] >= 0 else (-d[0], -d[1])
            rot = math.degrees(math.atan2(u[1], u[0]))
            mid = ((S[0] + A[0]) / 2, (S[1] + A[1]) / 2)
            nx, ny = u[1], -u[0]
            self.place(lab, mid[0] + nx * TEXT_GAP, mid[1] + ny * TEXT_GAP, rot, "middle", "Radius", own)
        else:
            ext = a.get("laenge", 8)
            E = (A[0] + d[0] * ext, A[1] + d[1] * ext)
            self.line([A, E], "schmal", own)
            self.arrow(A, (-d[0], -d[1]))
            self.leader_text(E, lab, own, f"Radius {fmt_value(a['r'])}", 1 if d[0] >= -1e-9 else -1)

    def dim_angle(self, a, vname):
        own = self.owner()
        S = self.P(a["s"])
        p1, p2 = self.P(a["p1"]), self.P(a["p2"])
        R = float(a.get("radius", 20))
        a1 = math.atan2(-(p1[1] - S[1]), p1[0] - S[0])
        a2 = math.atan2(-(p2[1] - S[1]), p2[0] - S[0])
        span = (a2 - a1) % (2 * math.pi)
        if span > math.pi:
            a1, a2, p1, p2 = a2, a1, p2, p1
            span = 2 * math.pi - span
        for ang, p in ((a1, p1), (a2, p2)):
            dist = math.hypot(p[0] - S[0], p[1] - S[1])
            dx, dy = math.cos(ang), -math.sin(ang)
            if R > dist:
                self.line([(p[0] + dx * EXT_GAP, p[1] + dy * EXT_GAP), (S[0] + dx * (R + EXT_OVER), S[1] + dy * (R + EXT_OVER))],
                          "schmal", own)
        Pa = (S[0] + R * math.cos(a1), S[1] - R * math.sin(a1))
        Pb = (S[0] + R * math.cos(a2), S[1] - R * math.sin(a2))
        large = 1 if span > math.pi else 0
        self.svg.append(f'<path d="M{Pa[0]:.3f},{Pa[1]:.3f} A{R:.3f},{R:.3f} 0 {large} 0 {Pb[0]:.3f},{Pb[1]:.3f}" '
                        f'{self.style("schmal")}/>')
        n = 24
        pts = [(S[0] + R * math.cos(a1 + span * i / n), S[1] - R * math.sin(a1 + span * i / n)) for i in range(n + 1)]
        for p, q in zip(pts, pts[1:]):
            self.segs.append((p, q, "schmal", own))
        self.arrow(Pa, (math.sin(a1), math.cos(a1)))
        self.arrow(Pb, (-math.sin(a2), -math.cos(a2)))
        deg = math.degrees(span)
        txt = a.get("text") or (fmt_value(round(deg, 3)) + "°")
        lab = build_dim_label({**a, "text": txt}, txt)
        am = a1 + span / 2
        dx, dy = math.cos(am), -math.sin(am)
        off = R + 1.5 + max(lab.w / 2 * abs(dx), (lab.top * -1) / 2 * abs(dy) + 1)
        cx, cy = S[0] + dx * off, S[1] + dy * off
        self.place(lab, cx, cy - lab.top / 2, 0, "middle", f"Winkel {txt}", own)

    def leader_note(self, a, vname):
        own = self.owner()
        T = self.P(a["ziel"])
        dx, dy = a.get("versatz", [10, 10])
        K = (T[0] + dx, T[1] - dy)
        pts = [T] + [(T[0] + kx, T[1] - ky) for kx, ky in a.get("knick", [])] + [K]
        self.line(pts, "schmal", own)
        end = a.get("ende", "pfeil")
        if end == "pfeil":
            self.arrow(T, (T[0] - pts[1][0], T[1] - pts[1][1]))
        elif end == "punkt":
            self.dot(T)
        lines = a["text"] if isinstance(a["text"], list) else [a["text"]]
        side = 1 if dx >= 0 else -1
        labs = []
        for ln in lines:
            lb = Label(a.get("h", H))
            lb.text(ln)
            labs.append(lb)
        w = max(lb.w for lb in labs)
        self.line([K, (K[0] + side * (w + 1.0), K[1])], "schmal", own)
        y = K[1] - TEXT_GAP
        for lb in reversed(labs):
            self.place(lb, K[0] + side * 0.5, y, 0, "start" if side > 0 else "end", f"Hinweis {lines[0]}", own)
            y -= 1.6 * lb.h
        if a.get("rahmen"):
            self.frame_under(K, side, a["rahmen"], own, vname)

    def gps_frame(self, a, vname):
        own = self.owner()
        rows = frame_rows(a["zellen"])
        for row in rows:
            self.check_frame(row, vname)
        T = self.P(a["ziel"]) if a.get("ziel") is not None else None
        dx, dy = a.get("versatz", [10, 10])
        base = T if T else self.P(a["pos"])
        anchor = (base[0] + dx, base[1] - dy)
        side = a.get("seite") or ("links" if dx >= 0 else "rechts")
        svg, boxes = draw_frame(rows, anchor[0], anchor[1], side, H, a.get("darueber"))
        if T:
            pts = [anchor] + [(T[0] + kx, T[1] - ky) for kx, ky in reversed(a.get("knick", []))] + [T]
            self.line(pts, "schmal", own)
            if a.get("rundum"):
                k = pts[-2]
                self.svg.append(f'<circle cx="{k[0]:.3f}" cy="{k[1]:.3f}" r="1.5" {self.style("schmal")}/>')
            if a.get("ende", "pfeil") == "pfeil":
                self.arrow(T, (T[0] - pts[-2][0], T[1] - pts[-2][1]))
            else:
                self.dot(T)
        self.svg.append(svg)
        for b in boxes:
            self.add_box(f"Toleranzrahmen {'|'.join(str(c) for c in rows[0])}",
                         [(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])], own)
        surf = a.get("oberflaeche")
        if surf:
            # Oberflächensymbol auf dem Toleranzrahmen (ISO 1302 / ISO 21920-1)
            surf = {"text": surf} if isinstance(surf, str) else surf
            texts = surf["text"] if isinstance(surf["text"], list) else [surf["text"]]
            ssvg, _, corners = surface_symbol(surf.get("art", "abtragen"), texts, H, surf.get("verfahren"))
            fx, fy = boxes[0][0] + 0.5 * 1.43 * H + 1.5, boxes[0][1]
            self.svg.append(f'<g transform="translate({fx:.3f},{fy:.3f})">{ssvg}</g>')
            self.add_box(f"Oberfläche {texts[0]}", [(fx + x, fy + y) for x, y in corners], own)

    def check_frame(self, row, vname):
        try:
            ch = norm_char(row[0])
        except ValueError as e:
            self.issue("FEHLER", f"{vname}: {e}")
            return
        datums = []
        for c in row[2:]:
            s = re.sub(r"\{[A-Z]+\}|\[[A-Z]+\]|[ⓂⓁ]", "", str(c))
            datums += re.findall(r"[A-Z]{1,2}", s)
        self.datums_used.update(datums)
        tol = str(row[1]) if len(row) > 1 else ""
        label = "|".join(str(c) for c in row)
        if ch in FORM and datums:
            self.issue("FEHLER", f"{vname}: Formtoleranz {label} darf keinen Bezug haben (ISO 1101)")
        if ch in NEEDS_DATUM and not datums:
            self.issue("FEHLER", f"{vname}: {label} braucht einen Bezug (ISO 1101)")
        if ch == "position" and not datums:
            self.issue("WARNUNG", f"{vname}: Positionstoleranz {label} ohne Bezug – nur für Muster zueinander zulässig")
        if ch in NO_MATERIAL_MOD and re.search(r"\{[ML]\}|[ⓂⓁ]", tol):
            self.issue("FEHLER", f"{vname}: {label}: Ⓜ/Ⓛ ist bei dieser Eigenschaft nicht zulässig (ISO 2692)")
        if re.search(r"\d\.\d", tol):
            self.issue("WARNUNG", f"{vname}: {label}: Dezimalpunkt statt Komma")
        if ch in ("lauf", "gesamtlauf") and re.search(r"\{D\}|⌀|Ø", tol):
            self.issue("FEHLER", f"{vname}: {label}: Lauftoleranz hat keine ⌀-Zone")
        if ch in ("ebenheit", "parallelitaet") and re.search(r"\{D\}|⌀|Ø", tol) and ch == "ebenheit":
            self.issue("FEHLER", f"{vname}: {label}: Ebenheit hat keine ⌀-Zone")

    def datum(self, a, vname):
        own = self.owner()
        letter = a["buchstabe"]
        self.datums_def.append(letter)
        T = self.P(a["ziel"])
        v = paper_dir(a.get("richtung", 90))
        n = (-v[1], v[0])
        hgt, half = 3.5, 2.0
        apex = (T[0] + v[0] * hgt, T[1] + v[1] * hgt)
        tri = [(T[0] + n[0] * half, T[1] + n[1] * half), (T[0] - n[0] * half, T[1] - n[1] * half), apex]
        fill = "#000" if a.get("gefuellt", True) else "#fff"
        self.svg.append(f'<polygon points="{" ".join(f"{x:.3f},{y:.3f}" for x, y in tri)}" fill="{fill}" '
                        f'stroke="#000" stroke-width="{W_NARROW}"/>')
        L = float(a.get("laenge", 5))
        box = 2 * H
        k = (box / 2) / max(abs(v[0]), abs(v[1]))
        C = (apex[0] + v[0] * (L + k), apex[1] + v[1] * (L + k))
        edge = (apex[0] + v[0] * L, apex[1] + v[1] * L)
        self.line([apex, edge], "schmal", own)
        x0, y0 = C[0] - box / 2, C[1] - box / 2
        self.svg.append(f'<rect x="{x0:.3f}" y="{y0:.3f}" width="{box}" height="{box}" fill="#fff" stroke="#000" '
                        f'stroke-width="{W_NARROW}"/>')
        runs = parse_runs(letter)
        self.svg.append(draw_runs(runs, C[0] - runs_width(runs, H) / 2, C[1] + H / 2, H))
        self.add_box(f"Bezug {letter}", [(x0, y0), (x0 + box, y0), (x0 + box, y0 + box), (x0, y0 + box)], own)

    def surface(self, a, vname):
        own = self.owner()
        T = self.P(a["ziel"])
        texts = a["text"] if isinstance(a.get("text"), list) else [a.get("text", "")]
        art = a.get("art", "abtragen")
        if a.get("hinweis"):
            dx, dy = a["hinweis"]
            K = (T[0] + dx, T[1] - dy)
            svg, right, corners = surface_symbol(art, texts, H, a.get("verfahren"))
            side = 1 if dx >= 0 else -1
            span = right + 0.5 * 1.43 * H + 2
            ref_end = (K[0] + side * span, K[1])
            self.line([T, K, ref_end], "schmal", own)
            self.arrow(T, (T[0] - K[0], T[1] - K[1]))
            if a.get("rundum"):
                self.svg.append(f'<circle cx="{K[0]:.3f}" cy="{K[1]:.3f}" r="1.5" {self.style("schmal")}/>')
            ax = K[0] + (0.5 * 1.43 * H + 1 if side > 0 else -span + 0.5 * 1.43 * H + 1)
            self.svg.append(f'<g transform="translate({ax:.3f},{K[1]:.3f})">{svg}</g>')
            pts = [(ax + x, K[1] + y) for x, y in corners]
        else:
            ang = a.get("normale", 90)
            rot = 90 - ang
            if (ang % 360) not in (90, 180):
                self.issue("WARNUNG", f"{vname}: Oberflächensymbol {texts[0]} mit Normale {ang}° ist nicht von unten "
                                      f"oder rechts lesbar – Hinweislinie ('hinweis') verwenden")
            svg, right, corners = surface_symbol(art, texts, H, a.get("verfahren"), a.get("rundum", False))
            self.svg.append(f'<g transform="translate({T[0]:.3f},{T[1]:.3f}) rotate({rot})">{svg}</g>')
            c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
            pts = [(T[0] + x * c - y * s, T[1] + x * s + y * c) for x, y in corners]
        self.add_box(f"Oberfläche {texts[0]}", pts, own)

    def free_text(self, a, vname):
        own = self.owner()
        if a.get("blatt"):
            x, y = a["blatt"]
        else:
            x, y = self.P(a["pos"])
        lines = a["text"] if isinstance(a["text"], list) else [a["text"]]
        h = a.get("h", H)
        for i, ln in enumerate(lines):
            lb = Label(h)
            lb.text(ln)
            self.place(lb, x, y + i * 1.6 * h, a.get("drehung", 0), a.get("anker", "start"), f"Text {ln[:20]}", own)

    def section_line(self, a, vname):
        own = self.owner()
        p1, p2 = self.P(a["p"][0]), self.P(a["p"][1])
        u = unit(p2[0] - p1[0], p2[1] - p1[1])
        seg = 6.0
        self.line([p1, p2], "mitte", own)
        self.line([p1, (p1[0] + u[0] * seg, p1[1] + u[1] * seg)], "kontur", own)
        self.line([p2, (p2[0] - u[0] * seg, p2[1] - u[1] * seg)], "kontur", own)
        v = paper_dir(a.get("blick", 0))   # Blickrichtung
        name = a["name"]
        for p, inward in ((p1, u), (p2, (-u[0], -u[1]))):
            # Pfeil in Blickrichtung, Spitze am breiten Ende der Schnittlinie (ISO 128-40)
            q = (p[0] + inward[0] * 2, p[1] + inward[1] * 2)
            tail = (q[0] - v[0] * 9, q[1] - v[1] * 9)
            self.line([tail, q], "schmal", own)
            self.arrow(q, v)
            lab = Label(5)
            lab.text(name)
            lx, ly = tail[0] - v[0] * 3.5, tail[1] - v[1] * 3.5
            self.place(lab, lx, ly + 2.5, 0, "middle", f"Schnitt {name}", own)

    def detail_mark(self, a, vname):
        own = self.owner()
        c = self.P(a["m"])
        r = a["r"] * self.s
        self.svg.append(f'<circle cx="{c[0]:.3f}" cy="{c[1]:.3f}" r="{r:.3f}" {self.style("schmal")}/>')
        d = paper_dir(a.get("winkel", 45))
        lab = Label(5)
        lab.text(a["name"])
        p = (c[0] + d[0] * (r + 4), c[1] + d[1] * (r + 4) + 2.5)
        self.place(lab, p[0], p[1], 0, "middle", f"Einzelheit {a['name']}", own)

    # ---- Prüfung
    def check(self):
        sp = self.spec
        all_notes = " ".join(sp.get("hinweise", [])) + " " + " ".join(str(v) for v in sp.get("schriftfeld", {}).values())
        if "8015" not in all_notes:
            self.issue("FEHLER", "Tolerierungsgrundsatz fehlt: Hinweis 'Tolerierung ISO 8015' ergänzen")
        if not re.search(r"2768|22081|13920|8062|16742|9013", all_notes):
            self.issue("FEHLER", "Allgemeintoleranzen fehlen (ISO 22081 / ISO 2768-1 / Verfahrensnorm)")
        if "13715" not in all_notes:
            self.issue("WARNUNG", "Kantenzustand nach ISO 13715 nicht angegeben")
        if not sp.get("oberflaeche_sammel") and not any(
                an.get("typ") == "oberflaeche" for v in sp.get("ansichten", []) for an in v.get("masse", [])):
            self.issue("WARNUNG", "Keine Oberflächenangabe vorhanden")
        tb = sp.get("schriftfeld", {})
        for key, name in (("titel", "Titel"), ("zeichnungsnummer", "Zeichnungsnummer"), ("eigentuemer", "Eigentümer"),
                          ("erstellt", "Erstellt"), ("werkstoff", "Werkstoff"), ("datum", "Ausgabedatum")):
            if not tb.get(key):
                self.issue("WARNUNG", f"Schriftfeld: {name} fehlt (ISO 7200)")
        seen = set()
        for d in self.datums_def:
            if d in seen:
                self.issue("FEHLER", f"Bezugsbuchstabe {d} mehrfach vergeben")
            seen.add(d)
            if d in ("I", "O", "Q", "X"):
                self.issue("WARNUNG", f"Bezugsbuchstabe {d} ist verwechselbar – anderen Buchstaben wählen")
        for d in sorted(self.datums_used - seen):
            self.issue("FEHLER", f"Bezug {d} wird im Toleranzrahmen verwendet, ist aber nicht definiert")
        for d in sorted(seen - self.datums_used):
            self.issue("WARNUNG", f"Bezug {d} ist definiert, wird aber in keinem Toleranzrahmen verwendet")
        self.check_layout()

    def check_layout(self):
        x0, y0, x1, y1 = self.inner
        tbx0, tby0, tbx1, tby1 = self.tb
        for label, pts, own in self.boxes:
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            if min(xs) < x0 or max(xs) > x1 or min(ys) < y0 or max(ys) > y1:
                self.issue("FEHLER", f"{label} liegt außerhalb des Zeichenrahmens")
            if own != -1 and max(xs) > tbx0 and min(xs) < tbx1 and max(ys) > tby0 and min(ys) < tby1:
                self.issue("FEHLER", f"{label} überdeckt das Schriftfeld")
        polys = [(label, shrink(pts, 0.25), own) for label, pts, own in self.boxes]
        for i in range(len(polys)):
            for j in range(i + 1, len(polys)):
                (la, pa, oa), (lb, pb, ob) = polys[i], polys[j]
                if oa == ob and oa != -1:
                    continue
                if poly_overlap(pa, pb):
                    self.issue("WARNUNG", f"Überlappung: {la} ↔ {lb}")
        for label, pts, own in polys:
            if own == -1:
                continue
            hits = set()
            for p, q, kind, o in self.segs:
                if o == own:
                    continue
                if seg_hits_poly(p, q, pts):
                    hits.add(kind if isinstance(o, tuple) else "Maß-/Hinweislinie")
            if hits:
                self.issue("WARNUNG", f"{label} wird von Linien geschnitten ({', '.join(sorted(hits))}) – "
                                      f"verschieben oder Linie unterbrechen")

    # ---- Ausgabe
    def render(self):
        self.sheet()
        for v in self.spec.get("ansichten", []):
            self.view(v)
        self.notes()
        self.title_block()
        self.check()
        body = "\n".join(self.svg)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.W}mm" height="{self.H}mm" '
                f'viewBox="0 0 {self.W} {self.H}" font-family="{FONT}">\n'
                f'<g fill="#000">\n{body}\n</g>\n</svg>\n')


# ---------------------------------------------------------------- Geometrie-Hilfen

def shrink(pts, d):
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    out = []
    for x, y in pts:
        ux, uy = unit(cx - x, cy - y)
        out.append((x + ux * d, y + uy * d))
    return out


def _axes(poly):
    for i in range(len(poly)):
        p, q = poly[i], poly[(i + 1) % len(poly)]
        yield (-(q[1] - p[1]), q[0] - p[0])


def poly_overlap(a, b):
    for ax in list(_axes(a)) + list(_axes(b)):
        pa = [p[0] * ax[0] + p[1] * ax[1] for p in a]
        pb = [p[0] * ax[0] + p[1] * ax[1] for p in b]
        if max(pa) < min(pb) or max(pb) < min(pa):
            return False
    return True


def seg_hits_poly(p, q, poly):
    return poly_overlap([p, q], poly) if (p != q) else False


# ---------------------------------------------------------------- Export

def find_browser():
    cands = [os.environ.get("ZEICHNUNG_BROWSER", ""),
             r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
             r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
             r"C:\Program Files\Google\Chrome\Application\chrome.exe",
             r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
             "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
             "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
    for c in cands:
        if c and Path(c).exists():
            return c
    for n in ("msedge", "google-chrome", "chromium", "chromium-browser", "chrome"):
        p = shutil.which(n)
        if p:
            return p
    return None


def export(svg_text_, W, Hh, out_svg, pdf, png, png_scale):
    browser = find_browser()
    if not browser:
        print("Hinweis: kein Edge/Chrome gefunden – PDF/PNG übersprungen (Pfad über ZEICHNUNG_BROWSER setzen)")
        return
    with tempfile.TemporaryDirectory() as tmp:
        prof = Path(tmp) / "profil"
        common = [browser, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                  f"--user-data-dir={prof}", "--hide-scrollbars"]
        if pdf:
            page = Path(tmp) / "pdf.html"
            page.write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>@page{{size:{W}mm {Hh}mm;margin:0}}'
                            f'html,body{{margin:0;padding:0}}svg{{display:block;width:{W}mm;height:{Hh}mm}}</style>'
                            f'</head><body>{svg_text_}</body></html>', encoding="utf-8")
            out = out_svg.with_suffix(".pdf")
            subprocess.run(common + ["--no-pdf-header-footer", "--print-to-pdf-no-header",
                                     f"--print-to-pdf={out}", page.as_uri()],
                           capture_output=True, timeout=120)
            print(f"PDF: {out}" if out.exists() else "PDF-Export fehlgeschlagen")
        if png:
            wpx, hpx = int(W * png_scale), int(Hh * png_scale)
            page = Path(tmp) / "png.html"
            page.write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;padding:0;'
                            f'background:#fff}}svg{{display:block;width:{wpx}px;height:{hpx}px}}</style></head>'
                            f'<body>{svg_text_}</body></html>', encoding="utf-8")
            out = out_svg.with_suffix(".png")
            subprocess.run(common + [f"--window-size={wpx},{hpx}", f"--screenshot={out}",
                                     "--default-background-color=ffffffff", page.as_uri()],
                           capture_output=True, timeout=120)
            print(f"PNG: {out}" if out.exists() else "PNG-Export fehlgeschlagen")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("-o", "--out")
    ap.add_argument("--pdf", action="store_true")
    ap.add_argument("--png", action="store_true")
    ap.add_argument("--png-skala", type=float, default=5.0, help="Pixel je mm (Standard 5)")
    ap.add_argument("--nur-pruefen", action="store_true")
    args = ap.parse_args()
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    d = Drawing(spec)
    svg = d.render()
    errors = [m for lvl, m in d.issues if lvl == "FEHLER"]
    warns = [m for lvl, m in d.issues if lvl == "WARNUNG"]
    for m in errors:
        print(f"FEHLER:  {m}")
    for m in warns:
        print(f"WARNUNG: {m}")
    print(f"Prüfung: {len(errors)} Fehler, {len(warns)} Warnungen")
    if not args.nur_pruefen:
        out = Path(args.out) if args.out else Path(args.spec).with_suffix(".svg")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(svg, encoding="utf-8")
        print(f"SVG: {out}")
        if args.pdf or args.png:
            export(svg, d.W, d.H, out.resolve(), args.pdf, args.png, args.png_skala)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
