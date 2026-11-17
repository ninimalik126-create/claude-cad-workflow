"""CAD-Modellbau aus einem Bauplan – Steuerung für FreeCAD und SolidWorks.

    python -I modell.py umgebung [--neu]                 CAD, Python-Pakete, Pfade und Vorgaben (zwischengespeichert)
    python -I modell.py vorgaben [--cad freecad] [--formate step,stl] [--loeschen]
                                                         Standardprogramm und -ausgaben merken (Karte entfällt)
    python -I modell.py installieren freecad|pywin32     fehlende Software installieren (winget / pip)
    python -I modell.py pruefen <plan.json>              Plan prüfen, ohne zu bauen
    python -I modell.py bauen <plan.json> [--cad freecad|solidworks] [--formate step,stl,3mf]
                 [--param L=100,B=50] [--name Halter-100] [--ansichten iso,oben,schnitt:X=0]
                 [--ordner <pfad>] [--skript frei.py] [--ohne-vorschau]
    python -I modell.py vorschau <teil.stl> <bild.png> [--ansichten …]
    python -I modell.py zusammen <a.step> <b.step> … [--step gesamt.step] [--bild bild.png]
                                                         Teile gemeinsam prüfen: Durchdringung, kleinster Abstand
    python -I modell.py netz pruefen|schnitte|vergleich|koerper|ausrichten …
                                                         Scan/STL vermessen, mit dem Modell vergleichen, in STEP wandeln
    python -I modell.py api <Methodenname>               SolidWorks-API-Signatur aus der Typbibliothek

'bauen' legt immer die native Datei (.FCStd / .SLDPRT), den Bericht (<name>-bericht.json) und das
Vorschaubild (<name>-vorschau.png) an; dazu die gewählten Austauschformate.
Ausgabe ist bewusst knapp (mit Merkmalsliste: Bohrungen, Zylinder, Radien); Einzelheiten stehen im Bericht.
Format des Bauplans: references/bauplan.md, Scan-Werkzeuge: references/scan-nachbau.md
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)

import bauplan as bp  # noqa: E402

DATEN = os.path.join(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()), "claude-cad-workflow")
CACHE = os.path.join(DATEN, "umgebung.json")
VORGABEN = os.path.join(DATEN, "vorgaben.json")
FORMATE = ("step", "stl", "3mf")


# ---------------------------------------------------------------------------- Umgebung
def _freecad_kandidaten():
    muster = [os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "FreeCAD*", "bin", "freecadcmd.exe"),
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "FreeCAD*", "bin", "freecadcmd.exe")]
    if os.environ.get("CCW_FREECAD"):
        muster.insert(0, os.environ["CCW_FREECAD"])
    gef = []
    for m in muster:
        gef += glob.glob(m)
    try:
        import winreg
        for wurzel in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for zweig in (r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                          r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"):
                try:
                    k = winreg.OpenKey(wurzel, zweig)
                except OSError:
                    continue
                for i in range(winreg.QueryInfoKey(k)[0]):
                    try:
                        sk = winreg.OpenKey(k, winreg.EnumKey(k, i))
                        name = winreg.QueryValueEx(sk, "DisplayName")[0]
                        if "freecad" in name.lower():
                            ort = winreg.QueryValueEx(sk, "InstallLocation")[0]
                            p = os.path.join(ort, "bin", "freecadcmd.exe")
                            if os.path.exists(p):
                                gef.append(p)
                    except OSError:
                        pass
    except ImportError:
        pass
    return sorted(set(os.path.normpath(p) for p in gef), key=_version_aus_pfad, reverse=True)


def _version_aus_pfad(p):
    m = re.search(r"FreeCAD[ _-]?(\d+)\.(\d+)", p, re.I)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def umgebung(neu=False):
    if not neu and os.path.exists(CACHE):
        try:
            u = json.load(open(CACHE, encoding="utf-8"))
            if (not u.get("freecad") or os.path.exists(u["freecad"]["cmd"])) and u.get("python") == sys.executable:
                return u
        except (OSError, ValueError, KeyError):
            pass
    u = {"python": sys.executable, "python_version": sys.version.split()[0], "windows": os.name == "nt"}
    fc = _freecad_kandidaten()
    if fc:
        cmd = fc[0]
        u["freecad"] = {"cmd": cmd, "gui": os.path.join(os.path.dirname(cmd), "freecad.exe"),
                        "version": ".".join(map(str, _version_aus_pfad(cmd)))}
    else:
        u["freecad"] = None
    try:
        import win32com.client  # noqa: F401
        u["pywin32"] = True
    except ImportError:
        u["pywin32"] = False
    u["solidworks"] = None
    try:
        import winreg
        winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "SldWorks.Application").Close()
        ver = None
        try:
            k = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"SldWorks.Application\CurVer")
            ver = winreg.QueryValueEx(k, "")[0]
        except OSError:
            pass
        u["solidworks"] = {"com": True, "version": ver}
    except (ImportError, OSError):
        pass
    u["winget"] = shutil.which("winget") is not None
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump(u, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return u


def umgebung_text(u):
    z = [f"Python {u['python_version']}: ok"]
    z.append(f"FreeCAD {u['freecad']['version']}: ok ({u['freecad']['cmd']})" if u.get("freecad")
             else "FreeCAD: fehlt -> python -I modell.py installieren freecad")
    if u.get("solidworks"):
        z.append(f"SolidWorks: installiert ({u['solidworks'].get('version') or 'Version unbekannt'})")
        z.append("pywin32: ok" if u["pywin32"] else "pywin32: fehlt (nötig für SolidWorks) -> python -I modell.py installieren pywin32")
    else:
        z.append("SolidWorks: nicht installiert")
    z.append(vorgaben_text(vorgaben_lesen()))
    return "\n".join(z)


# ---------------------------------------------------------------------------- Vorgaben
def vorgaben_lesen():
    try:
        return json.load(open(VORGABEN, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def vorgaben_text(v):
    if not v.get("cad"):
        return "Vorgaben: keine (Programm und Ausgaben per Karte fragen)"
    aus = " + ".join(f.upper() for f in v.get("formate", [])) or "nur native Datei"
    return f"Vorgaben: {v['cad']}, {aus} (Karte entfällt, außer der Nutzer will es anders)"


def vorgaben(args):
    if args.loeschen:
        if os.path.exists(VORGABEN):
            os.remove(VORGABEN)
    elif args.cad or args.formate is not None:
        v = vorgaben_lesen()
        if args.cad:
            v["cad"] = args.cad
        if args.formate is not None:
            v["formate"] = _formate(args.formate)
        v.setdefault("cad", "freecad")
        os.makedirs(DATEN, exist_ok=True)
        json.dump(v, open(VORGABEN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(vorgaben_text(vorgaben_lesen()))
    return 0


def _formate(text):
    out = [f.strip().lower() for f in (text or "").split(",") if f.strip()]
    for f in out:
        if f not in FORMATE:
            raise SystemExit(f"Format '{f}' unbekannt ({', '.join(FORMATE)}; die native Datei entsteht immer)")
    return out


def installieren(was):
    if was == "pywin32":
        r = subprocess.run([sys.executable, "-m", "pip", "install", "--user", "pywin32"])
    elif was == "freecad":
        if not shutil.which("winget"):
            print("winget fehlt – FreeCAD von https://www.freecad.org/downloads.php installieren.")
            return 2
        r = subprocess.run(["winget", "install", "--id", "FreeCAD.FreeCAD", "-e", "--silent",
                            "--accept-package-agreements", "--accept-source-agreements"])
    else:
        print(f"Unbekannt: {was}")
        return 2
    u = umgebung(neu=True)
    print(umgebung_text(u))
    return r.returncode


# ---------------------------------------------------------------------------- Bauen
def _kurzordner():
    d = os.path.join(tempfile.gettempdir(), "ccw")
    os.makedirs(d, exist_ok=True)
    return d


def bauen_freecad(u, auftrag):
    if not u.get("freecad"):
        raise SystemExit("FreeCAD fehlt – erst: python -I modell.py installieren freecad")
    pfad = os.path.join(_kurzordner(), "auftrag.json")
    json.dump(auftrag, open(pfad, "w", encoding="utf-8"), ensure_ascii=False)
    env = dict(os.environ, CCW_AUFTRAG=pfad)
    try:
        r = subprocess.run([u["freecad"]["cmd"], os.path.join(HIER, "bau_freecad.py")], env=env,
                           cwd=_kurzordner(), capture_output=True, text=True, errors="replace", timeout=900)
    except subprocess.TimeoutExpired:
        return {"fehler": 1, "absturz": "FreeCAD hat nach 15 min nicht geantwortet"}
    if not os.path.exists(auftrag["bericht"]):
        return {"fehler": 1, "absturz": (r.stdout[-1500:] + r.stderr[-1500:]).strip()}
    return json.load(open(auftrag["bericht"], encoding="utf-8"))


def bauen_solidworks(u, auftrag):
    if not u.get("solidworks"):
        raise SystemExit("SolidWorks ist auf diesem Rechner nicht installiert")
    if not u.get("pywin32"):
        raise SystemExit("pywin32 fehlt – erst: python -I modell.py installieren pywin32")
    import bau_solidworks
    b = bau_solidworks.bauen(auftrag)
    json.dump(b, open(auftrag["bericht"], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return b


def _zahl(v, n=1):
    s = f"{v:,.{n}f}".replace(",", " ").replace(".", ",")
    return s


def _k(v):
    """Zahl kurz und mit Komma: 6.6 -> '6,6', 10.0 -> '10'."""
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s.replace(".", ",")


def merkmale_text(m):
    """Merkmalsliste als wenige Zeilen: was tatsächlich gebaut wurde, zum Abgleich mit der Vorgabe."""
    z = []
    for titel, liste in (("Bohrungen", m.get("bohrungen", [])), ("Außenzylinder", m.get("zylinder", []))):
        for g in liste[:8]:
            a = g["achse"]
            if a == "schräg":
                wo = "schräge Achse durch " + " ".join("(" + "; ".join(_k(c) for c in p) + ")" for p in g["bei"][:4])
            else:
                quer = "".join(c for c in "XYZ" if c != a)
                wo = (f"∥{a} ({a} {_k(g['von'])}…{_k(g['bis'])}) bei {quer} "
                      + " ".join("(" + "; ".join(_k(c) for c in p) + ")" for p in g["bei"][:8])
                      + (" …" if len(g["bei"]) > 8 else ""))
            offen = f" (Umfang nur {g['umfang_grad']}°)" if g.get("umfang_grad") else ""
            z.append(f"{titel}: {g['anzahl']}× Ø{_k(g['d'])}{offen} {wo}")
        if len(liste) > 8:
            z.append(f"{titel}: … und {len(liste) - 8} weitere Gruppen (siehe Bericht)")
    if m.get("kegel"):
        z.append("Kegel/Senkungen: " + ", ".join(
            f"{g['anzahl']}× {_k(g['winkel'])}° Ø{_k(g['d_klein'])}…{_k(g['d_gross'])} ∥{g['achse']}"
            f"{' innen' if g['innen'] else ' außen'}" for g in m["kegel"][:6]))
    if m.get("radien"):
        z.append("Radien: " + ", ".join(f"{g['anzahl']}× R{_k(g['r'])} {'innen' if g['innen'] else 'außen'}"
                                        for g in m["radien"][:8]))
    return z


def zusammenfassung(b, plan_name):
    z = []
    ok = not b.get("fehler")
    kopf = f"{'OK' if ok else 'FEHLER'} – {plan_name} ({b.get('cad', '?')} {b.get('version', '')}".rstrip() + ")"
    n = len([f for f in b.get("features", []) if f.get("id") not in ("skript", "ergebnis", "abbruch")])
    z.append(f"{kopf}: {n} Features, {b.get('fehler', 0)} Fehler")
    for f in b.get("plan_befunde", []):
        z.append(f"  Plan: {f}")
    if b.get("absturz"):
        z.append("  Absturz: " + b["absturz"][-1200:])
    for f in b.get("features", []):
        if not f.get("ok"):
            z.append(f"  ✗ {f['id']}: {f.get('fehler', '')}" + ("  [evtl. Folgefehler]" if f.get("folge") else ""))
        elif f.get("warnung"):
            z.append(f"  ! {f['id']}: {f['warnung']}")
        if f.get("sekunden", 0) >= 8:
            z.append(f"  i {f['id']}: Bau dauerte {_k(f['sekunden'])} s"
                     + (" – modellierte Gewinde ans Ende des Plans stellen, sie bremsen jedes Feature danach"
                        if f.get("typ") == "bohrung" else ""))
    if b.get("parameter"):
        z.append("Parameter: " + ", ".join(f"{k}={_k(v)}" for k, v in b["parameter"].items()))
    if b.get("groesse"):
        g = b["groesse"]
        zeile = f"Größe {_zahl(g[0], 2)} × {_zahl(g[1], 2)} × {_zahl(g[2], 2)} mm | Volumen {_zahl(b['volumen_mm3'])} mm³"
        if b.get("masse_kg") is not None:
            zeile += f" | Masse {_zahl(b['masse_kg'], 3)} kg"
        z.append(zeile)
        h = [round(v, 3) + 0.0 for v in b["huelle"]]  # + 0.0 macht aus -0 eine 0
        z.append(f"Hülle (min→max): X {h[0]:g}…{h[3]:g}  Y {h[1]:g}…{h[4]:g}  Z {h[2]:g}…{h[5]:g}")
    if b.get("merkmale"):
        z.extend(merkmale_text(b["merkmale"]))
    for a in b.get("soll_abweichungen", []):
        z.append(f"  ✗ Soll: {a}")
    for w in b.get("warnungen", []):
        z.append(f"  ! {w}")
    for w in b.get("druck", []):
        z.append(f"  Druck: {w}")
    if b.get("dateien"):
        z.append("Dateien: " + ", ".join(os.path.basename(p) for p in b["dateien"]))
        z.append("Ordner: " + os.path.dirname(b["dateien"][0]))
    if b.get("vorschau"):
        z.append("Vorschau: " + b["vorschau"] + (f"  ({', '.join(b['ansichten'])})" if b.get("ansichten") else ""))
    return "\n".join(z)


def _parameter(texte):
    """['L=100,B=50', 't=3'] -> {'L': 100.0, 'B': 50.0, 't': 3.0}; Werte dürfen Ausdrücke sein."""
    out = {}
    for teil in ",".join(texte or []).split(","):
        if not teil.strip():
            continue
        k, gleich, v = teil.partition("=")
        if not gleich or not k.strip():
            raise SystemExit(f"--param erwartet Name=Wert, bekam '{teil}'")
        try:
            out[k.strip()] = float(v.replace(",", "."))
        except ValueError:
            out[k.strip()] = v.strip()
    return out


def ansichten_fuer(plan):
    """Ansichten des Vorschaubilds. Ohne Vorgabe im Plan: vier Standardansichten, dazu die Unterseite, wenn
    von unten gearbeitet wird, und ein Längsschnitt, wenn das Teil ausgehöhlt ist (sonst sieht man es nicht)."""
    if plan.get("ansichten"):
        return list(plan["ansichten"])
    a = ["iso", "vorne", "oben", "rechts"]
    feats = plan.get("features", [])
    if any(f.get("typ") in ("tasche", "bohrung", "text") and f.get("ebene", "XY") == "XY"
           and f.get("richtung") == "+" for f in feats):
        a.append("unten")
    if any(f.get("typ") == "schale" for f in feats):
        h = plan.get("soll", {}).get("huelle") or []
        mitte = (h[1] + h[4]) / 2 if len(h) == 6 else 0
        a.append(f"schnitt:Y={mitte:g}")
    return a


def druckhinweise(tris, normalen):
    """FDM-Druck in der gebauten Lage (Z nach oben): Überhänge und Auflagefläche."""
    import vorschau
    flaeche, stufen, auflage = vorschau.ueberhang(tris, normalen)
    out = []
    if flaeche > 25:
        wo = ", ".join(f"Z≈{_k(z)} ({_k(round(f))} mm²)" for z, f in stufen)
        out.append(f"Überhang steiler als 45°: {_k(round(flaeche))} mm², größte Stellen bei {wo} – Stützen einplanen, "
                   f"Kante anfasen oder Teil anders legen")
    if auflage < 100:
        out.append(f"Auflagefläche nur {_k(round(auflage))} mm² (ebene Fläche bei Z min) – Brim oder andere Lage")
    return out


def bauen(args):
    u = umgebung()
    v = vorgaben_lesen()
    cad = args.cad or v.get("cad") or "freecad"
    plan_pfad = os.path.abspath(args.plan)
    param = _parameter(args.param)
    try:
        plan = bp.laden(plan_pfad, skript=bool(args.skript), parameter=param)
    except bp.BauplanFehler as ex:
        print("FEHLER im Bauplan:\n" + "\n".join("  " + b for b in ex.befunde))
        return 1
    if args.name:
        plan["name"] = args.name
    ordner = os.path.abspath(args.ordner or os.path.dirname(plan_pfad))
    name = "".join(c if c.isalnum() or c in "-_." else "_" for c in plan["name"]).strip("_") or "Teil"
    formate = _formate(args.formate) if args.formate is not None else list(v.get("formate", []))
    try:
        ansichten = [x.strip() for x in args.ansichten.split(",") if x.strip()] if args.ansichten \
            else ansichten_fuer(plan)
        import vorschau
        for a in ansichten:
            vorschau.ansicht_lesen(a)
    except (ValueError, KeyError) as ex:
        print(f"FEHLER bei den Ansichten: {ex}")
        return 2
    vorschau_stl = os.path.join(_kurzordner(), name + "-vorschau.stl")
    if os.path.exists(vorschau_stl):
        os.remove(vorschau_stl)
    auftrag = {"plan": plan_pfad, "ordner": ordner, "formate": formate, "skripte": HIER,
               "bericht": os.path.join(ordner, name + "-bericht.json"),
               "vorschau_stl": None if args.ohne_vorschau else vorschau_stl,
               "skript": os.path.abspath(args.skript) if args.skript else None,
               "parameter": param or None, "name": args.name or None}
    os.makedirs(ordner, exist_ok=True)
    if os.path.exists(auftrag["bericht"]):
        os.remove(auftrag["bericht"])
    for h in plan.get("_hinweise", []):
        print(f"Hinweis: {h}")
    b = bauen_freecad(u, auftrag) if cad == "freecad" else bauen_solidworks(u, auftrag)
    if not args.ohne_vorschau and os.path.exists(vorschau_stl):
        tris = vorschau.lies_stl(vorschau_stl)
        png = os.path.join(ordner, name + "-vorschau.png")
        vorschau.rendern(vorschau_stl, png, plan["name"], modellmasse=b.get("groesse"), ansichten=ansichten,
                         tris=tris)
        b["vorschau"] = png
        b["ansichten"] = [a if isinstance(a, str) else f"schnitt:{a['schnitt']}={a.get('bei', 0):g}" for a in ansichten]
        if str(plan.get("fertigung", "")).lower() == "fdm" and not b.get("fehler"):
            b["druck"] = druckhinweise(tris, vorschau.normalen_von(tris))
        json.dump(b, open(auftrag["bericht"], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(zusammenfassung(b, plan["name"]))
    return 1 if b.get("fehler") else 0


def _freecad_python(u):
    """Python aus dem FreeCAD-Ordner: bringt numpy, scipy und matplotlib mit (für die Netz-Werkzeuge)."""
    if not u.get("freecad"):
        raise SystemExit("FreeCAD fehlt – erst: python -I modell.py installieren freecad")
    p = os.path.join(os.path.dirname(u["freecad"]["cmd"]), "python.exe")
    if not os.path.exists(p):
        raise SystemExit(f"{p} fehlt – FreeCAD-Installation prüfen")
    return p


def netz(rest):
    """Reicht an netz.py weiter (läuft im FreeCAD-Python)."""
    u = umgebung()
    env = dict(os.environ, PYTHONIOENCODING="utf-8", CCW_FREECAD_BIN=os.path.dirname(u["freecad"]["cmd"])
               if u.get("freecad") else "")
    return subprocess.run([_freecad_python(u), "-I", os.path.join(HIER, "netz.py")] + rest, env=env).returncode


def zusammen(args):
    """Mehrere Teile in gemeinsamer Lage prüfen: Durchdringung und kleinster Abstand je Paar."""
    u = umgebung()
    if not u.get("freecad"):
        raise SystemExit("FreeCAD fehlt – erst: python -I modell.py installieren freecad")
    teile = [os.path.abspath(p) for p in args.teile]
    fehlt = [p for p in teile if not os.path.exists(p)]
    if fehlt:
        print("Datei nicht gefunden: " + ", ".join(fehlt))
        return 2
    ergebnis = os.path.join(_kurzordner(), "zusammen.json")
    stl = os.path.join(_kurzordner(), "zusammen.stl")
    for p in (ergebnis, stl):
        if os.path.exists(p):
            os.remove(p)
    auftrag = {"teile": teile, "step": os.path.abspath(args.step) if args.step else None,
               "stl": stl if args.bild else None, "ergebnis": ergebnis}
    pfad = os.path.join(_kurzordner(), "zusammen-auftrag.json")
    json.dump(auftrag, open(pfad, "w", encoding="utf-8"), ensure_ascii=False)
    r = subprocess.run([u["freecad"]["cmd"], os.path.join(HIER, "zusammen_freecad.py")],
                       env=dict(os.environ, CCW_AUFTRAG=pfad), cwd=_kurzordner(), capture_output=True, text=True,
                       errors="replace", timeout=900)
    if not os.path.exists(ergebnis):
        print("FEHLER – FreeCAD lieferte kein Ergebnis:\n" + (r.stdout[-800:] + r.stderr[-800:]).strip())
        return 1
    e = json.load(open(ergebnis, encoding="utf-8"))
    for t in e["teile"]:
        print(f"{t['name']}: {_zahl(t['groesse'][0], 2)} × {_zahl(t['groesse'][1], 2)} × {_zahl(t['groesse'][2], 2)} mm, "
              f"Volumen {_zahl(t['volumen'])} mm³" + ("" if t["gueltig"] else "  ! Geometrie ungültig"))
    schlecht = 0
    for p in e["paare"]:
        if p["durchdringung"] > 1e-3:
            schlecht += 1
            print(f"  ✗ {p['a']} / {p['b']}: Durchdringung {_zahl(p['durchdringung'], 2)} mm³ "
                  f"um ({', '.join(_k(c) for c in p['ort'])})")
        else:
            print(f"  ✓ {p['a']} / {p['b']}: keine Durchdringung, kleinster Abstand {_zahl(p['abstand'], 3)} mm")
    for f in e.get("fehler", []):
        schlecht += 1
        print(f"  ✗ {f}")
    if e.get("step"):
        print("Gesamt-STEP: " + e["step"])
    if args.bild and os.path.exists(stl):
        import vorschau
        print("Bild: " + vorschau.rendern(stl, os.path.abspath(args.bild), "Zusammenbau"))
    print("OK – Teile passen zusammen" if not schlecht else f"FEHLER – {schlecht} Befund(e)")
    return 1 if schlecht else 0


def _sw_ordner():
    import winreg
    clsid = winreg.QueryValue(winreg.HKEY_CLASSES_ROOT, r"SldWorks.Application\CLSID")
    exe = winreg.QueryValue(winreg.HKEY_CLASSES_ROOT, rf"CLSID\{clsid}\LocalServer32").strip('"').split('"')[0]
    return os.path.dirname(exe.split(" /")[0])


def api(name):
    """Signaturen einer SolidWorks-API-Methode aus sldworks.tlb (statt raten)."""
    import pythoncom
    typen = {2: "short", 3: "long", 4: "float", 5: "double", 8: "BSTR", 9: "IDispatch", 11: "bool",
             12: "VARIANT", 13: "IUnknown", 22: "int", 24: "void", 26: "ptr", 29: "userdef", 27: "SAFEARRAY"}
    tl = pythoncom.LoadTypeLib(os.path.join(_sw_ordner(), "sldworks.tlb"))
    gef = 0
    for i in range(tl.GetTypeInfoCount()):
        ti = tl.GetTypeInfo(i)
        ta = ti.GetTypeAttr()
        for j in range(ta.cFuncs):
            fd = ti.GetFuncDesc(j)
            namen = ti.GetNames(fd.memid)
            if namen[0].lower() == name.lower():
                arg = ", ".join(f"{n}: {typen.get(t[0] if isinstance(t[0], int) else 26, t[0])}"
                                for n, t in zip(namen[1:], fd.args))
                art = {1: "", 2: " [Eigenschaft lesen]", 4: " [Eigenschaft setzen]"}.get(fd.invkind, "")
                print(f"{tl.GetDocumentation(i)[0]}.{namen[0]}({arg}){art}")
                gef += 1
    if not gef:
        print(f"'{name}' nicht in sldworks.tlb gefunden")
    return 0 if gef else 1


def pruefen(args):
    try:
        plan = bp.laden(args.plan, parameter=_parameter(args.param))
    except bp.BauplanFehler as ex:
        print("FEHLER im Bauplan:\n" + "\n".join("  " + b for b in ex.befunde))
        return 1
    print(f"OK – {plan['name']}: {len(plan['features'])} Features")
    if plan.get("_parameter"):
        print("Parameter: " + ", ".join(f"{k}={_k(v)}" for k, v in plan["_parameter"].items()))
    for h in plan.get("_hinweise", []):
        print(f"Hinweis: {h}")
    for f in plan["features"]:
        extra = ""
        if "_positionen" in f:
            extra = f" ({len(f['_positionen'])}×)"
        elif "_schleifen" in f:
            extra = f" ({len(f['_schleifen'])} Kontur{'en' if len(f['_schleifen']) != 1 else ''})"
        print(f"  {f['id']}: {f['typ']}{extra}")
    return 0


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) > 1 and sys.argv[1] == "netz":  # eigene Optionen, deshalb unverändert durchreichen
        return netz(sys.argv[2:])
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="befehl", required=True)
    p = sub.add_parser("umgebung")
    p.add_argument("--neu", action="store_true")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("vorgaben", help="Standardprogramm und -ausgaben merken")
    p.add_argument("--cad", choices=["freecad", "solidworks"])
    p.add_argument("--formate", help="z. B. step,stl (leer = nur native Datei)")
    p.add_argument("--loeschen", action="store_true")
    p = sub.add_parser("installieren")
    p.add_argument("was", choices=["freecad", "pywin32"])
    p = sub.add_parser("pruefen")
    p.add_argument("plan")
    p.add_argument("--param", action="append")
    p = sub.add_parser("bauen")
    p.add_argument("plan")
    p.add_argument("--cad", choices=["freecad", "solidworks"], help="Standard: Vorgabe, sonst freecad")
    p.add_argument("--formate", help="step,stl,3mf – Standard: Vorgabe, sonst nur die native Datei")
    p.add_argument("--param", action="append", help="Parameter für diesen Lauf überschreiben: L=100,B=50")
    p.add_argument("--name", help="anderer Teile- und Dateiname (für Varianten)")
    p.add_argument("--ansichten", help="Vorschau: iso,vorne,oben,rechts,unten,hinten,links,schnitt:X=0")
    p.add_argument("--ordner")
    p.add_argument("--skript")
    p.add_argument("--ohne-vorschau", action="store_true")
    p = sub.add_parser("vorschau")
    p.add_argument("stl")
    p.add_argument("png")
    p.add_argument("--titel", default="")
    p.add_argument("--ansichten", default="")
    p = sub.add_parser("zusammen", help="mehrere Teile gemeinsam prüfen (Durchdringung, Abstand)")
    p.add_argument("teile", nargs="+", help="STEP-, BREP- oder FCStd-Dateien in gemeinsamer Lage")
    p.add_argument("--step", help="alle Teile zusammen als eine STEP-Datei schreiben")
    p.add_argument("--bild", help="gemeinsames Vorschaubild schreiben")
    sub.add_parser("netz", help="Scan/STL-Werkzeuge, siehe: modell.py netz --help")
    p = sub.add_parser("api", help="Signatur einer SolidWorks-API-Methode anzeigen")
    p.add_argument("name")
    a = ap.parse_args()
    if a.befehl == "api":
        return api(a.name)
    if a.befehl == "umgebung":
        u = umgebung(a.neu)
        print(json.dumps(u, ensure_ascii=False, indent=1) if a.json else umgebung_text(u))
        return 0
    if a.befehl == "vorgaben":
        return vorgaben(a)
    if a.befehl == "installieren":
        return installieren(a.was)
    if a.befehl == "pruefen":
        return pruefen(a)
    if a.befehl == "bauen":
        return bauen(a)
    if a.befehl == "zusammen":
        return zusammen(a)
    if a.befehl == "vorschau":
        import vorschau
        ans = [x.strip() for x in a.ansichten.split(",") if x.strip()] or None
        print(vorschau.rendern(a.stl, a.png, a.titel, ansichten=ans))
        return 0


if __name__ == "__main__":
    sys.exit(main())
