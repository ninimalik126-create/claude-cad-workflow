# Freies Skript (FreeCAD): Knopf als Loft von Kreis zu Achteck, dann Gewindebohrung über feature()
import Part
basis = feature({"id": "Fuss", "typ": "block", "ebene": "XY", "profil": [{"kreis": 30, "mitte": [0, 0]}], "hoehe": 4})
sk1 = bau.skizze("XY", 4, [[("kreis", (0, 0), 15)]], "Loft_unten")
sk2 = bau.skizze("XY", 32, bp.form_zu_schleifen({"vieleck": 8, "d": 20, "mitte": [0, 0], "winkel": 22.5}), "Loft_oben")
loft = body.newObject("PartDesign::AdditiveLoft", "Knopf")
loft.Profile = sk1
loft.Sections = [sk2]
loft.Ruled = True
doc.recompute()
feature({"id": "Gewinde", "typ": "bohrung", "ebene": "XY", "versatz": 0, "richtung": "+", "mitte": [0, 0], "gewinde": "M6", "tiefe": 12})
