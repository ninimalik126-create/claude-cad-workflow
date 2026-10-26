"""ISO 286-1/-2: Grenzabmaße und Passungen für Nennmaße bis 500 mm.

Aufruf:
    python -I passung.py 25 H7/g6     Passung mit Spiel/Übermaß
    python -I passung.py 40 k6        einzelnes Toleranzfeld
    python -I passung.py 25 H7 --json

Unterstützte Grundabmaße:
    Wellen:   d e f g h js k m n p
    Bohrungen D E F G H JS K M N P
Toleranzgrade IT3 bis IT14.

Werte in µm, ausgegeben in mm. Für Grundabmaße außerhalb dieser Liste
(a, b, c, r, s, t, u, …) ISO 286-2 heranziehen.
"""
import json
import re
import sys

# Obergrenzen der Nennmaßbereiche ("über ... bis"), erster Bereich: bis 3
RANGES = [3, 6, 10, 18, 30, 50, 80, 120, 180, 250, 315, 400, 500]

IT = {  # µm
    3:  [2, 2.5, 2.5, 3, 4, 4, 5, 6, 8, 10, 12, 13, 15],
    4:  [3, 4, 4, 5, 6, 7, 8, 10, 12, 14, 16, 18, 20],
    5:  [4, 5, 6, 8, 9, 11, 13, 15, 18, 20, 23, 25, 27],
    6:  [6, 8, 9, 11, 13, 16, 19, 22, 25, 29, 32, 36, 40],
    7:  [10, 12, 15, 18, 21, 25, 30, 35, 40, 46, 52, 57, 63],
    8:  [14, 18, 22, 27, 33, 39, 46, 54, 63, 72, 81, 89, 97],
    9:  [25, 30, 36, 43, 52, 62, 74, 87, 100, 115, 130, 140, 155],
    10: [40, 48, 58, 70, 84, 100, 120, 140, 160, 185, 210, 230, 250],
    11: [60, 75, 90, 110, 130, 160, 190, 220, 250, 290, 320, 360, 400],
    12: [100, 120, 150, 180, 210, 250, 300, 350, 400, 460, 520, 570, 630],
    13: [140, 180, 220, 270, 330, 390, 460, 540, 630, 720, 810, 890, 970],
    14: [250, 300, 360, 430, 520, 620, 740, 870, 1000, 1150, 1300, 1400, 1550],
}

# Oberes Abmaß es der Wellen d..h (µm)
ES_SHAFT = {
    "d": [-20, -30, -40, -50, -65, -80, -100, -120, -145, -170, -190, -210, -230],
    "e": [-14, -20, -25, -32, -40, -50, -60, -72, -85, -100, -110, -125, -135],
    "f": [-6, -10, -13, -16, -20, -25, -30, -36, -43, -50, -56, -62, -68],
    "g": [-2, -4, -5, -6, -7, -9, -10, -12, -14, -15, -17, -18, -20],
    "h": [0] * 13,
}

# Unteres Abmaß ei der Wellen k..p (µm); k gilt für IT4..IT7, sonst 0
EI_SHAFT = {
    "k": [0, 1, 1, 1, 2, 2, 2, 3, 3, 4, 4, 4, 5],
    "m": [2, 4, 6, 7, 8, 9, 11, 13, 15, 17, 20, 21, 23],
    "n": [4, 8, 10, 12, 15, 17, 20, 23, 27, 31, 34, 37, 40],
    "p": [6, 12, 15, 18, 22, 26, 32, 37, 43, 50, 56, 62, 68],
}


def range_index(size):
    if size <= 0 or size > 500:
        raise ValueError("Nennmaß muss > 0 und <= 500 mm sein")
    for i, upper in enumerate(RANGES):
        if size <= upper:
            return i
    raise ValueError(size)


def it_value(grade, i):
    if grade not in IT:
        raise ValueError(f"IT{grade} nicht hinterlegt (IT3..IT14)")
    return IT[grade][i]


def shaft(letter, grade, i):
    """(es, ei) in µm."""
    t = it_value(grade, i)
    if letter in ES_SHAFT:
        es = ES_SHAFT[letter][i]
        return es, es - t
    if letter == "js":
        half = t / 2
        return half, -half
    if letter in EI_SHAFT:
        ei = EI_SHAFT[letter][i]
        if letter == "k" and not (4 <= grade <= 7):
            ei = 0
        return ei + t, ei
    raise ValueError(f"Grundabmaß '{letter}' nicht hinterlegt")


def hole(letter, grade, i):
    """(ES, EI) in µm."""
    t = it_value(grade, i)
    low = letter.lower()
    if low in ES_SHAFT:  # D..H: EI = -es
        ei = -ES_SHAFT[low][i]
        return ei + t, ei
    if low == "js":
        half = t / 2
        return half, -half
    if low in EI_SHAFT:
        ei_shaft = EI_SHAFT[low][i]
        if low == "k" and not (4 <= grade <= 7):
            ei_shaft = 0
        # Sonderregel (ISO 286-1): K, M, N bis IT8 und P bis IT7 über 3 mm: ES = -ei + Δ
        special = (low in ("k", "m", "n") and grade <= 8) or (low == "p" and grade <= 7)
        if i > 0 and special:
            delta = it_value(grade, i) - it_value(grade - 1, i)
            es = -ei_shaft + delta
        elif low == "n" and grade > 8 and i > 0:
            es = 0
        else:
            es = -ei_shaft
        if low == "m" and grade == 6 and i == 10:
            es = -9  # Ausnahme ISO 286-2: M6 über 250 bis 315
        if (low in ("k", "m", "n") and grade > 8) or (low == "p" and grade > 7):
            print(f"Warnung: {letter}{grade} außerhalb der üblichen Grade – Wert mit ISO 286-2 abgleichen",
                  file=sys.stderr)
        return es, es - t
    raise ValueError(f"Grundabmaß '{letter}' nicht hinterlegt")


FIELD_RE = re.compile(r"^(js|JS|[a-zA-Z])(\d{1,2})$")


def parse_field(s):
    m = FIELD_RE.match(s.strip())
    if not m:
        raise ValueError(f"Toleranzfeld '{s}' nicht erkannt (z. B. H7, g6, js6)")
    letter, grade = m.group(1), int(m.group(2))
    is_hole = letter[0].isupper()
    return letter, grade, is_hole


def field(size, spec):
    letter, grade, is_hole = parse_field(spec)
    i = range_index(size)
    upper, lower = (hole if is_hole else shaft)(letter, grade, i)
    return {
        "feld": spec,
        "art": "Bohrung" if is_hole else "Welle",
        "nennmass": size,
        "bereich": f"über {([0] + RANGES)[i]} bis {RANGES[i]}",
        "IT": it_value(grade, i),
        "oberes_abmass_um": upper,
        "unteres_abmass_um": lower,
        "hoechstmass": round(size + upper / 1000, 4),
        "mindestmass": round(size + lower / 1000, 4),
    }


def _decimals(*um_values):
    # ISO 129-1: beide Abmaße mit gleicher Anzahl Dezimalstellen; 3 Stellen, 4 bei halben µm
    return 4 if any(abs(v * 2) % 2 == 1 for v in um_values) else 3


def fmt_dev(um, dec=3):
    if um == 0:
        return "0"
    return f"{um / 1000:+.{dec}f}".replace(".", ",").replace("-", "−")


def fmt_mm(v, dec=None):
    if dec is None:
        return f"{v:.4f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{v:.{dec}f}".replace(".", ",")


def describe(f):
    up, lo = f["oberes_abmass_um"], f["unteres_abmass_um"]
    d = _decimals(up, lo)
    devs = f"{fmt_dev(up, d)}/{fmt_dev(lo, d)}"
    return (f"{fmt_mm(f['nennmass'])} {f['feld']}  ({f['art']}, {f['bereich']} mm, IT = {f['IT']} µm)\n"
            f"  Abmaße:     {fmt_dev(up, d)} / {fmt_dev(lo, d)}\n"
            f"  Grenzmaße:  {fmt_mm(f['hoechstmass'], d)} … {fmt_mm(f['mindestmass'], d)}\n"
            f"  Zeichnung:  ⌀{fmt_mm(f['nennmass'])} {f['feld']} ({devs})")


def fit(size, spec):
    a, b = spec.split("/")
    fa, fb = field(size, a), field(size, b)
    if fa["art"] == fb["art"]:
        raise ValueError("Passung braucht ein Bohrungs- und ein Wellenfeld")
    h, s = (fa, fb) if fa["art"] == "Bohrung" else (fb, fa)
    max_clear = h["oberes_abmass_um"] - s["unteres_abmass_um"]
    min_clear = h["unteres_abmass_um"] - s["oberes_abmass_um"]
    if min_clear >= 0:
        kind = "Spielpassung"
    elif max_clear <= 0:
        kind = "Übermaßpassung"
    else:
        kind = "Übergangspassung"
    return {"bohrung": h, "welle": s, "art": kind,
            "hoechstspiel_um": max_clear, "mindestspiel_um": min_clear}


def main(argv):
    as_json = "--json" in argv
    args = [a for a in argv if a != "--json"]
    if len(args) != 2:
        print(__doc__)
        return 2
    size = float(args[0].replace(",", "."))
    spec = args[1]
    try:
        if "/" in spec:
            r = fit(size, spec)
            if as_json:
                print(json.dumps(r, ensure_ascii=False, indent=2))
            else:
                print(describe(r["bohrung"]))
                print(describe(r["welle"]))
                mx, mn = r["hoechstspiel_um"], r["mindestspiel_um"]
                d = _decimals(mx, mn)
                v = lambda um: fmt_mm(abs(um) / 1000, d)
                if r["art"] == "Spielpassung":
                    txt = f"Höchstspiel {v(mx)}  /  Mindestspiel {v(mn)}"
                elif r["art"] == "Übermaßpassung":
                    txt = f"Mindestübermaß {v(mx)}  /  Höchstübermaß {v(mn)}"
                else:
                    txt = f"Höchstspiel {v(mx)}  /  Höchstübermaß {v(mn)}"
                print(f"\n{r['art']}: {txt} mm")
        else:
            r = field(size, spec)
            print(json.dumps(r, ensure_ascii=False, indent=2) if as_json else describe(r))
    except ValueError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
