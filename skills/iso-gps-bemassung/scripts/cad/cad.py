"""CAD-Anbindung des ISO-GPS-Plugins.

Aufruf (Windows, Python mit pywin32):
    python -I cad.py erkennen
    python -I cad.py analysieren <teil.SLDPRT|.FCStd|.CATPart|.ipt> [-o merkmale.json] [--cad solidworks]
    python -I cad.py zeichnen <auftrag.json> [--cad solidworks]
    python -I cad.py selbsttest [--cad solidworks] [--ordner <pfad>]
    python -I cad.py export <zeichnung.SLDDRW|.FCStd|.CATDrawing|.idw> [--dxf]
    python -I cad.py schliessen

'erkennen' listet installierte und laufende CAD-Programme mit Adapterstatus.
'analysieren' liefert das neutrale Merkmalsmodell (Flächen-IDs F1…, Maße in mm).
'zeichnen' erzeugt aus einem Zeichnungsauftrag die native Zeichnung samt PDF.
Format von Merkmalsmodell und Auftrag: references/15-cad-workflow.md
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cad_basis import CadFehler, ausgabe  # noqa: E402

ADAPTER = {}


def _lade_adapter():
    if ADAPTER:
        return ADAPTER
    for modul, klasse in (("cad_solidworks", "SolidWorks"), ("cad_freecad", "FreeCAD"), ("cad_catia", "Catia"),
                          ("cad_inventor", "Inventor")):
        try:
            mod = __import__(modul)
            ADAPTER[getattr(mod, klasse).name] = getattr(mod, klasse)
        except ImportError as ex:
            ADAPTER[modul.replace("cad_", "")] = ex
    return ADAPTER


ENDUNGEN = {".fcstd": "freecad", ".sldprt": "solidworks", ".sldasm": "solidworks", ".slddrw": "solidworks",
            ".catpart": "catia", ".catproduct": "catia", ".catdrawing": "catia",
            ".ipt": "inventor", ".iam": "inventor", ".idw": "inventor", ".dwg": "inventor"}


def erkennen():
    out = []
    for name, cls in _lade_adapter().items():
        if isinstance(cls, Exception):
            out.append({"cad": name, "installiert": None, "fehler": f"Adapter nicht ladbar: {cls}"})
            continue
        try:
            inst, laeuft, info = cls.verfuegbar()
        except Exception as ex:
            inst, laeuft, info = False, False, str(ex)
        out.append({"cad": name, "installiert": inst, "laeuft": laeuft, "info": info,
                    "adapter_getestet": cls.getestet})
    return out


def waehle_adapter(cad=None, datei=None):
    adapter = _lade_adapter()
    if not cad and datei:
        cad = ENDUNGEN.get(os.path.splitext(datei)[1].lower())
    if not cad:
        verfuegbar = [e for e in erkennen() if e.get("installiert")]
        laufend = [e for e in verfuegbar if e.get("laeuft")]
        wahl = (laufend or verfuegbar)
        if not wahl:
            raise CadFehler("Kein unterstütztes CAD-Programm gefunden – neutralen Weg nutzen (zeichnung.py)")
        cad = wahl[0]["cad"]
    cls = adapter.get(cad)
    if cls is None or isinstance(cls, Exception):
        raise CadFehler(f"Kein Adapter für '{cad}' verfügbar")
    if not cls.getestet:
        print(f"Hinweis: Der {cad}-Adapter ist ungetestet. Ergebnis im CAD prüfen.", file=sys.stderr)
    a = cls()
    a.verbinden()
    return a


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="befehl", required=True)
    sub.add_parser("erkennen")
    p = sub.add_parser("analysieren")
    p.add_argument("datei")
    p.add_argument("-o", "--out")
    p.add_argument("--cad")
    p.add_argument("--mit-refs", action="store_true", help="dauerhafte CAD-Referenzen mit ausgeben")
    p = sub.add_parser("zeichnen")
    p.add_argument("auftrag")
    p.add_argument("--cad")
    p = sub.add_parser("selbsttest")
    p.add_argument("--cad")
    p.add_argument("--ordner")
    p = sub.add_parser("export", help="vorhandene CAD-Zeichnung als PDF (und optional DXF) ausgeben")
    p.add_argument("zeichnung")
    p.add_argument("--dxf", action="store_true")
    p.add_argument("--cad")
    p = sub.add_parser("schliessen", help="alle Dokumente im CAD ohne Speichern schließen")
    p.add_argument("--cad")
    args = ap.parse_args()
    try:
        if args.befehl == "erkennen":
            ausgabe(erkennen())
        elif args.befehl == "analysieren":
            a = waehle_adapter(args.cad, args.datei)
            m = a.analysieren(args.datei)
            if not args.mit_refs:
                for f in m["flaechen"]:
                    f.pop("ref", None)
            ausgabe(m, args.out)
            if args.out:
                print(f"Merkmalsmodell: {args.out} ({len(m['flaechen'])} Flächen)")
        elif args.befehl == "zeichnen":
            auftrag = json.loads(open(args.auftrag, encoding="utf-8").read())
            a = waehle_adapter(args.cad or auftrag.get("cad"), auftrag.get("teil"))
            erg = a.zeichnen(auftrag, os.path.dirname(os.path.abspath(args.auftrag)))
            ausgabe(erg)
            return 1 if erg["fehler"] else 0
        elif args.befehl == "selbsttest":
            ordner = args.ordner or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))), "beispiele", "cad-selbsttest")
            a = waehle_adapter(args.cad)
            teil = a.testteil(os.path.join(ordner, "Welle" + a.endung_teil))
            name = "selbsttest-auftrag-freecad.json" if a.name == "freecad" else "selbsttest-auftrag.json"
            auftrag_pfad = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
            auftrag = json.loads(open(auftrag_pfad, encoding="utf-8").read())
            auftrag["teil"] = teil
            auftrag["ausgabe"] = {"ordner": ordner, "name": "Welle-Selbsttest"}
            erg = a.zeichnen(auftrag, ordner)
            ausgabe(erg)
            return 1 if erg["fehler"] else 0
        elif args.befehl == "export":
            a = waehle_adapter(args.cad, args.zeichnung)
            for p in a.exportieren(args.zeichnung, ("pdf", "dxf") if args.dxf else ("pdf",)):
                print(p)
        elif args.befehl == "schliessen":
            a = waehle_adapter(args.cad)
            a.schliessen()
    except CadFehler as ex:
        print(f"Fehler: {ex}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
