"""Replace a reference everywhere (TR277, D838)."""

from __future__ import annotations

from fdcad.core.document.model import Feature, new_document
from fdcad.core.naming.replace import replace_everywhere, users_of


def test_sketch_and_face_references_switch() -> None:
    doc = new_document()
    for fid, ftype in (("f5", "sketch"), ("f6", "sketch"), ("f7", "extrude"), ("f8", "fillet")):
        refs = {"sketch": {"feature": "f5"}} if ftype == "extrude" else {}
        if ftype == "fillet":
            refs = {
                "edges": [{"kind": "edge", "name": "f7/side/e1|f7/cap/end"}],
                "x": {"feature": "f5"},
            }
        doc.features.append(Feature(fid, ftype, fid, refs=refs))
    doc.next_id = 9
    old = {"feature": "f5"}
    assert users_of(doc, old) == ["f7", "f8"]
    edited = replace_everywhere(doc, old, {"feature": "f6"})
    assert edited["f7"].refs == {"sketch": {"feature": "f6"}}
    assert edited["f8"].refs["x"] == {"feature": "f6"}
    assert doc.feature("f7").refs == {"sketch": {"feature": "f5"}}  # copies only
    face = {"kind": "edge", "name": "f7/side/e1|f7/cap/end"}
    swapped = replace_everywhere(doc, face, {"kind": "edge", "name": "f7/side/e2|f7/cap/end"})
    assert swapped["f8"].refs["edges"][0]["name"] == "f7/side/e2|f7/cap/end"
    later = replace_everywhere(doc, old, {"feature": "f8"})  # f8 comes after f7
    assert "f7" not in later
