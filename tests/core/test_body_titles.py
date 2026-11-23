"""Lasting body names (TR183 item 1, D1201)."""

from __future__ import annotations

import zipfile
from pathlib import Path

from fdcad.core import body_titles as bt
from fdcad.core.io.export import MeshSettings, export_3mf
from fdcad.core.printing import body_roles as br
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import add_extrude, add_sketch, plate, rect


def _two_bodies():  # type: ignore[no-untyped-def]
    from fdcad.core.sketch.model import Sketch

    doc, _ext = plate()
    s = Sketch()
    rect(s, 70, 0, 80, 10)
    add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 5.0)
    return doc, list(rebuild(doc).values())[-1].body


def test_names_follow_the_body_through_rebuilds() -> None:
    doc, named = _two_bodies()
    assert bt.titles_of(doc, named) == [None, None]
    assert bt.labels_of(doc, named) == ["Body 1", "Body 2"]
    doc.print_setup[bt.BODY_TITLES] = bt.with_title(doc, named, 1, "  Lid\x07 clip ")
    again = list(rebuild(doc).values())[-1].body
    assert bt.titles_of(doc, again) == [None, "Lid clip"]
    doc.print_setup[bt.BODY_TITLES] = bt.with_title(doc, again, 1, "")
    assert doc.print_setup[bt.BODY_TITLES] == {}
    doc.print_setup[bt.BODY_TITLES] = {"x": 3, 4: "a", "f9": "   "}
    assert bt.titles_of(doc, again) == [None, None]
    assert len(bt.clean("a" * 500)) == bt.TITLE_LIMIT


def test_3mf_objects_take_the_names(tmp_path: Path) -> None:
    _doc, named = _two_bodies()
    assert named is not None
    titles = [None, 'Lid & "clip"']
    for slicer in br.SLICER_FORMS:
        out = tmp_path / f"{slicer}.3mf"
        roles = [br.PART, br.MODIFIER]
        export_3mf(
            named.shape,
            out,
            name="Box",
            settings=MeshSettings(slicer=slicer),
            roles=roles,
            titles=titles,
        )
        with zipfile.ZipFile(out) as zf:
            text = "".join(
                zf.read(n).decode() for n in zf.namelist() if n.endswith((".model", ".config"))
            )
        assert "Lid &amp; &quot;clip&quot;" in text
        assert "Box body 1" in text
