"""3MF names are escaped (spec 2 section 20 item 11, audit D item 10, D714)."""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree

from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

from fdcad.core.io.export import export_3mf, xml_text


def test_xml_text() -> None:
    assert xml_text('R&D <"a">') == "R&amp;D &lt;&quot;a&quot;&gt;"
    assert xml_text("a\x01b") == "ab"


def test_a_name_with_an_ampersand_gives_a_valid_3mf(tmp_path: Path) -> None:
    path = tmp_path / "part.3mf"
    export_3mf(BRepPrimAPI_MakeBox(10, 10, 10).Shape(), str(path), name="R&D <test>")
    with zipfile.ZipFile(path) as archive:
        model = archive.read("3D/3dmodel.model")
    root = ElementTree.fromstring(model)  # a parse error before the fix
    names = [e.get("name") for e in root.iter() if e.tag.endswith("object")]
    assert names == ["R&D <test> body 1", "R&D <test>"]  # the body and its assembly (TR381)


def test_flat_export_counts_sketch_items_it_leaves_out() -> None:
    """Spec 2 section 20 item 21 (D715): text and failing curves were dropped silently."""
    from fdcad.core.io.flat_export import sketch_items_left_out
    from fdcad.core.sketch.model import Ellipse, Sketch
    from fdcad.core.sketch.profiles import BASIS_PLANES

    sk = Sketch()
    sk.add_line(0, 0, 10, 0)
    c, a, b = sk.add_point(0, 0), sk.add_point(2, 0), sk.add_point(0, 5)  # minor > major
    eid = sk.new_id()
    sk.entities[eid] = Ellipse(eid, c, a, b)
    edges, _plane, left = sketch_items_left_out(sk, BASIS_PLANES["xy"])
    assert len(edges) == 1 and left == 1


def test_two_step_exports_at_once_keep_their_own_schema(tmp_path: Path) -> None:
    """Audit D item 14 (D733): the schema is a process wide setting, so parallel exports
    could write each other's schema."""
    import threading

    from fdcad.core.io.export import export_step

    box = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
    jobs = [
        threading.Thread(target=export_step, args=(box, tmp_path / f"{s}-{i}.step", s))
        for i in range(3)
        for s in ("AP214", "AP242")
    ]
    for j in jobs:
        j.start()
    for j in jobs:
        j.join()
    for path in tmp_path.glob("*.step"):
        head = path.read_text(encoding="latin-1")[:2000]
        want = "AP242" if path.name.startswith("AP242") else "AUTOMOTIVE_DESIGN"
        assert want in head.upper().replace(" ", "_") or want in head, path.name
