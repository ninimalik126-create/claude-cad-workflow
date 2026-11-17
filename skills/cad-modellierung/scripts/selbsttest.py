"""Selbsttest: baut alle Beispielpläne in FreeCAD und vergleicht das Ergebnis mit festen Sollwerten.

    python -I selbsttest.py [--ordner <pfad>] [--behalten]

Nach jeder Änderung an den Bauskripten laufen lassen. Geprüft werden je Beispiel: 0 Fehler, Volumen auf
0,05 %, Zahl der Bohrungen laut Merkmalsliste, Vorschaubild vorhanden. Dazu Planprüfung, Parameter,
Zusammenbau-Prüfung und die Netz-Werkzeuge an einem gebauten Teil. Dauer drei bis vier Minuten.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
BEISPIELE = os.path.join(os.path.dirname(HIER), "beispiele")
# Beispiel: (Volumen mm³, Zahl der Bohrungen in der Merkmalsliste)
SOLL = {"halter": (27779.1, 5), "welle": (64901.8, 1), "gehaeuse": (13876.7, 4), "kabelclip": (5869.4, 5),
        "adapter": (17070.2, 5), "buegel": (8381.0, 0), "pruefblock": (42804.2, 9)}


def lauf(*arg):
    r = subprocess.run([sys.executable, "-I", os.path.join(HIER, "modell.py"), *arg], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout + r.stderr


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ordner", help="Arbeitsordner (Standard: temporär)")
    ap.add_argument("--behalten", action="store_true", help="Arbeitsordner nicht löschen")
    a = ap.parse_args()
    ordner = os.path.abspath(a.ordner) if a.ordner else tempfile.mkdtemp(prefix="ccw-test-")
    os.makedirs(ordner, exist_ok=True)
    schlecht = []

    def pruefe(name, ok, text=""):
        print(f"  {'✓' if ok else '✗'} {name}" + (f": {text}" if text else ""))
        if not ok:
            schlecht.append(name)

    print("Beispielpläne (FreeCAD)")
    for name, (volumen, bohrungen) in SOLL.items():
        code, aus = lauf("bauen", os.path.join(BEISPIELE, name + ".json"), "--cad", "freecad", "--ordner", ordner,
                         "--formate", "step,stl")
        try:
            plan = json.load(open(os.path.join(BEISPIELE, name + ".json"), encoding="utf-8"))
            b = json.load(open(os.path.join(ordner, plan["name"] + "-bericht.json"), encoding="utf-8"))
        except (OSError, ValueError):
            pruefe(name, False, "kein Bericht – " + aus.strip()[-300:])
            continue
        v = b.get("volumen_mm3", 0)
        n = sum(g["anzahl"] for g in b.get("merkmale", {}).get("bohrungen", []))
        ok = (code == 0 and not b.get("fehler") and abs(v - volumen) <= 5e-4 * volumen and n == bohrungen
              and os.path.exists(b.get("vorschau", "")))
        pruefe(name, ok, f"Volumen {v:.1f} (soll {volumen:.1f}), {n} Bohrungen (soll {bohrungen}), "
                         f"{b.get('fehler', '?')} Fehler")

    print("Parameter und Planprüfung")
    code, aus = lauf("bauen", os.path.join(BEISPIELE, "kabelclip.json"), "--cad", "freecad", "--ordner", ordner,
                     "--param", "L=80,dk=10", "--name", "Kabelclip-80", "--ohne-vorschau")
    pruefe("Variante über --param", code == 0 and "80,00 × 24,00 × 16,40" in aus, aus.strip().splitlines()[0])
    falsch = os.path.join(ordner, "falsch.json")
    json.dump({"name": "Falsch", "features": [
        {"id": "A", "typ": "block", "profil": [{"rechteck": [20, 20], "mitte": [0, 0]}], "hoehe": "=h"},
        {"id": "B", "typ": "fase", "kanten": {"in_ebene": {"Z": 99}}, "laenge": 1}]}, open(falsch, "w"))
    code, aus = lauf("pruefen", falsch)
    pruefe("unbekannter Parameter wird gemeldet", code != 0 and "kein Parameter" in aus)
    json.dump({"name": "Falsch", "features": [
        {"id": "A", "typ": "block", "profil": [{"rechteck": [20, 20], "mitte": [0, 0]}], "hoehe": 5},
        {"id": "B", "typ": "fase", "kanten": {"in_ebene": {"Z": 99}}, "laenge": 1}]}, open(falsch, "w"))
    code, aus = lauf("bauen", falsch, "--cad", "freecad", "--ordner", ordner, "--ohne-vorschau")
    pruefe("falsche Kantenauswahl nennt die vorhandenen Lagen", code != 0 and "Kanten gibt es bei Z = 0, 5" in aus)

    print("Zusammenbau")
    deckel = os.path.join(ordner, "deckel.json")
    json.dump({"name": "Deckel", "parameter": {"spiel": 0.2}, "features": [
        {"id": "Platte", "typ": "block", "versatz": 25, "profil": [{"rechteck": [60, 40], "mitte": [0, 0], "r": 4}],
         "hoehe": 2},
        {"id": "Falz", "typ": "block", "versatz": 25, "richtung": "-", "hoehe": 3,
         "profil": [{"rechteck": ["=56-2*spiel", "=36-2*spiel"], "mitte": [0, 0], "r": 2}]}],
        "soll": {"huelle": [-30, -20, 22, 30, 20, 27]}}, open(deckel, "w"))
    lauf("bauen", deckel, "--cad", "freecad", "--formate", "step", "--ohne-vorschau")
    lauf("bauen", deckel, "--cad", "freecad", "--formate", "step", "--ohne-vorschau", "--param", "spiel=-0.3",
         "--name", "Deckel-eng")
    geh = os.path.join(ordner, "Gehaeuse.step")
    code, aus = lauf("zusammen", geh, os.path.join(ordner, "Deckel.step"))
    pruefe("passender Deckel", code == 0 and "keine Durchdringung" in aus)
    code, aus = lauf("zusammen", geh, os.path.join(ordner, "Deckel-eng.step"))
    pruefe("zu enger Deckel wird gemeldet", code != 0 and "Durchdringung" in aus)

    print("Netz-Werkzeuge")
    stl = os.path.join(ordner, "Halter.stl")
    code, aus = lauf("netz", "pruefen", stl, "--bild", os.path.join(ordner, "netz.png"))
    pruefe("pruefen", code == 0 and "Netz ist dicht: Volumen 27 779" in aus)
    code, aus = lauf("netz", "schnitte", stl, "--achse", "Z", "--bei", "2")
    pruefe("schnitte", code == 0 and "Rechteck 80 × 40 mit Eckenradius R5" in aus and "Langloch 30 × 8" in aus
           and aus.count("Kreis Ø6,6") == 2)
    code, aus = lauf("netz", "vergleich", stl, stl, "--bild", os.path.join(ordner, "vergleich.png"))
    pruefe("vergleich", code == 0 and "größte 0 mm" in aus)
    code, aus = lauf("netz", "koerper", stl, os.path.join(ordner, "Halter-netz.step"), "--facetten", "0")
    pruefe("koerper", code == 0 and "gültig: ja" in aus)

    print(f"\n{'OK – alles bestanden' if not schlecht else 'FEHLER – ' + ', '.join(schlecht)}")
    if a.behalten or a.ordner or schlecht:
        print("Ordner: " + ordner)
    else:
        shutil.rmtree(ordner, ignore_errors=True)
    return 1 if schlecht else 0


if __name__ == "__main__":
    sys.exit(main())
