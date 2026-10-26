"""CAD-Modellbau aus einem Bauplan – Steuerung für FreeCAD und SolidWorks.

    python -I modell.py umgebung [--neu]                 CAD, Python-Pakete und Pfade prüfen (zwischengespeichert)
    python -I modell.py installieren freecad|pywin32     fehlende Software installieren (winget / pip)
    python -I modell.py pruefen <plan.json>              Plan prüfen, ohne zu bauen
    python -I modell.py bauen <plan.json> --cad freecad|solidworks [--formate step,stl,3mf]
                                          [--ordner <pfad>] [--skript frei.py] [--ohne-vorschau]
    python -I modell.py vorschau <teil.stl> <bild.png>
    python -I modell.py api <Methodenname>              SolidWorks-API-Signatur aus der Typbibliothek

'bauen' legt immer die native Datei (.FCStd / .SLDPRT), den Bericht (<name>-bericht.json) und das
Vorschaubild (<name>-vorschau.png) an; dazu die gewählten Austauschformate.
Ausgabe ist bewusst knapp; Einzelheiten stehen im Bericht.
Format des Bauplans: references/bauplan.md
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

CACHE = os.path.join(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()), "claude-cad-workflow", "umgebung.json")


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
    return "\n".join(z)


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


def zusammenfassung(b, plan_name):
    z = []
    ok = not b.get("fehler")
    kopf = f"{'OK' if ok else 'FEHLER'} – {plan_name} ({b.get('cad', '?')} {b.get('version', '')}".rstrip() + ")"
    n = len([f for f in b.get("features", []) if f.get("id") not in ("skript", "ergebnis")])
    z.append(f"{kopf}: {n} Features, {b.get('fehler', 0)} Fehler")
    for f in b.get("plan_befunde", []):
        z.append(f"  Plan: {f}")
    if b.get("absturz"):
        z.append("  Absturz: " + b["absturz"][-1200:])
    for f in b.get("features", []):
        if not f.get("ok"):
            z.append(f"  ✗ {f['id']}: {f.get('fehler', '')}")
        elif f.get("warnung"):
            z.append(f"  ! {f['id']}: {f['warnung']}")
    if b.get("groesse"):
        g = b["groesse"]
        zeile = f"Größe {_zahl(g[0], 2)} × {_zahl(g[1], 2)} × {_zahl(g[2], 2)} mm | Volumen {_zahl(b['volumen_mm3'])} mm³"
        if b.get("masse_kg") is not None:
            zeile += f" | Masse {_zahl(b['masse_kg'], 3)} kg"
        z.append(zeile)
        h = [round(v, 3) + 0.0 for v in b["huelle"]]  # + 0.0 macht aus -0 eine 0
        z.append(f"Hülle (min→max): X {h[0]:g}…{h[3]:g}  Y {h[1]:g}…{h[4]:g}  Z {h[2]:g}…{h[5]:g}")
    for a in b.get("soll_abweichungen", []):
        z.append(f"  ✗ Soll: {a}")
    for w in b.get("warnungen", []):
        z.append(f"  ! {w}")
    if b.get("dateien"):
        z.append("Dateien: " + ", ".join(os.path.basename(p) for p in b["dateien"]))
        z.append("Ordner: " + os.path.dirname(b["dateien"][0]))
    if b.get("vorschau"):
        z.append("Vorschau: " + b["vorschau"])
    return "\n".join(z)


def bauen(args):
    u = umgebung()
    plan_pfad = os.path.abspath(args.plan)
    try:
        plan = bp.laden(plan_pfad, skript=bool(args.skript))
    except bp.BauplanFehler as ex:
        print("FEHLER im Bauplan:\n" + "\n".join("  " + b for b in ex.befunde))
        return 1
    ordner = os.path.abspath(args.ordner or os.path.dirname(plan_pfad))
    name = "".join(c if c.isalnum() or c in "-_." else "_" for c in plan["name"]).strip("_") or "Teil"
    formate = [f.strip().lower() for f in (args.formate or "").split(",") if f.strip()]
    for f in formate:
        if f not in ("step", "stl", "3mf"):
            print(f"Format '{f}' unbekannt (step, stl, 3mf; die native Datei entsteht immer)")
            return 2
    vorschau_stl = os.path.join(_kurzordner(), name + "-vorschau.stl")
    if os.path.exists(vorschau_stl):
        os.remove(vorschau_stl)
    auftrag = {"plan": plan_pfad, "ordner": ordner, "formate": formate, "skripte": HIER,
               "bericht": os.path.join(ordner, name + "-bericht.json"),
               "vorschau_stl": None if args.ohne_vorschau else vorschau_stl,
               "skript": os.path.abspath(args.skript) if args.skript else None}
    os.makedirs(ordner, exist_ok=True)
    if os.path.exists(auftrag["bericht"]):
        os.remove(auftrag["bericht"])
    for h in plan.get("_hinweise", []):
        print(f"Hinweis: {h}")
    b = bauen_freecad(u, auftrag) if args.cad == "freecad" else bauen_solidworks(u, auftrag)
    if not args.ohne_vorschau and os.path.exists(vorschau_stl):
        import vorschau
        png = os.path.join(ordner, name + "-vorschau.png")
        vorschau.rendern(vorschau_stl, png, plan["name"], modellmasse=b.get("groesse"))
        b["vorschau"] = png
        json.dump(b, open(auftrag["bericht"], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(zusammenfassung(b, plan["name"]))
    return 1 if b.get("fehler") else 0


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
        plan = bp.laden(args.plan)
    except bp.BauplanFehler as ex:
        print("FEHLER im Bauplan:\n" + "\n".join("  " + b for b in ex.befunde))
        return 1
    print(f"OK – {plan['name']}: {len(plan['features'])} Features")
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
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="befehl", required=True)
    p = sub.add_parser("umgebung")
    p.add_argument("--neu", action="store_true")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("installieren")
    p.add_argument("was", choices=["freecad", "pywin32"])
    p = sub.add_parser("pruefen")
    p.add_argument("plan")
    p = sub.add_parser("bauen")
    p.add_argument("plan")
    p.add_argument("--cad", required=True, choices=["freecad", "solidworks"])
    p.add_argument("--formate", default="")
    p.add_argument("--ordner")
    p.add_argument("--skript")
    p.add_argument("--ohne-vorschau", action="store_true")
    p = sub.add_parser("vorschau")
    p.add_argument("stl")
    p.add_argument("png")
    p.add_argument("--titel", default="")
    p = sub.add_parser("api", help="Signatur einer SolidWorks-API-Methode anzeigen")
    p.add_argument("name")
    a = ap.parse_args()
    if a.befehl == "api":
        return api(a.name)
    if a.befehl == "umgebung":
        u = umgebung(a.neu)
        print(json.dumps(u, ensure_ascii=False, indent=1) if a.json else umgebung_text(u))
        return 0
    if a.befehl == "installieren":
        return installieren(a.was)
    if a.befehl == "pruefen":
        return pruefen(a)
    if a.befehl == "bauen":
        return bauen(a)
    if a.befehl == "vorschau":
        import vorschau
        print(vorschau.rendern(a.stl, a.png, a.titel))
        return 0


if __name__ == "__main__":
    sys.exit(main())
