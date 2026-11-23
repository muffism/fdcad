"""Part, body, feature and face colours; STEP and 3MF colours (PHASE2_SPEC P2.11, D254)."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pytest
from OCP.Quantity import Quantity_Color, Quantity_TOC_sRGB
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDocStd import TDocStd_Document
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.XCAFDoc import XCAFDoc_ColorSurf, XCAFDoc_DocumentTool

from fdcad.core.appearance import (
    PART_COLOR,
    Target,
    color_of,
    colors_in_use,
    face_colors,
    ordered,
    part_color,
    valid_color,
    with_color,
)
from fdcad.core.document.model import new_document
from fdcad.core.io import export, fdef
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from fdcad.samples.make import SAMPLE_DIR
from tests.core.features.test_features import add_extrude, add_sketch, body, rect


def _two_bodies() -> tuple[object, str, str]:
    """A plate (f6) and a separate block on top (f8)."""
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 50, 30)
    sk = add_sketch(doc, s, {"feature": "f2"})
    plate = add_extrude(doc, sk, 10.0)
    s2 = Sketch()
    rect(s2, 60, 0, 70, 10)
    sk2 = add_sketch(doc, s2, {"feature": "f2"})
    block = add_extrude(doc, sk2, 5.0, merge=False)
    return doc, plate, block


def test_colours_and_order() -> None:
    assert valid_color("#A1B2C3") and valid_color("#A1B2C3FF") and not valid_color("red")
    app = {"part_color": PART_COLOR, "faces": {}}
    app = with_color(app, Target("feature", "f8"), "#ff0000")
    app = with_color(app, Target("face", "f6/cap/end"), "#00FF00")
    app = with_color(app, Target("body", "1"), "#0000FF")
    assert list(app) == ["part_color", "faces", "features", "bodies"]
    assert color_of(app, Target("feature", "f8")) == "#FF0000"
    app = with_color(app, Target("feature", "f8"), None)
    assert "features" not in app  # empty optional maps are left out
    app = with_color(app, Target("part"), "#123456")
    assert part_color(app) == "#123456"
    assert part_color(with_color(app, Target("part"), None)) == PART_COLOR
    with pytest.raises(ValueError, match="Invalid colour"):
        with_color(app, Target("part"), "blue")
    shown = {"part_color": PART_COLOR, "faces": {}, "shown": ["f2"], "hidden": ["f5"]}
    assert list(ordered(shown)) == ["part_color", "faces", "hidden", "shown"]


def test_most_specific_colour_wins() -> None:
    doc, plate, block = _two_bodies()
    results = rebuild(doc)  # type: ignore[arg-type]
    named = body(results, block)
    app = {"part_color": PART_COLOR, "faces": {}}
    assert face_colors(named, app) == []
    app = with_color(app, Target("body", "1"), "#111111")
    app = with_color(app, Target("feature", block), "#222222")
    app = with_color(app, Target("face", f"{plate}/cap/end"), "#333333")
    colours = face_colors(named, app)
    by_colour: dict[str, int] = {}
    for _face, c in colours:
        by_colour[c] = by_colour.get(c, 0) + 1
    assert by_colour == {"#333333": 1, "#111111": 5, "#222222": 6}
    used = dict(colors_in_use(app, {block: "Extrude 2"}))
    assert used["#222222"] == ["Extrude 2"] and used[PART_COLOR] == ["Part"]


def test_step_writes_colours(tmp_path: Path) -> None:
    doc, _plate, block = _two_bodies()
    named = body(rebuild(doc), block)  # type: ignore[arg-type]
    app = with_color({"part_color": PART_COLOR, "faces": {}}, Target("feature", block), "#FF0000")
    path = tmp_path / "part.step"
    export.export_step(named.shape, path, color=part_color(app), faces=face_colors(named, app))
    reader = STEPCAFControl_Reader()
    reader.SetColorMode(True)
    reader.ReadFile(str(path))
    xde = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    assert reader.Transfer(xde)
    shapes = XCAFDoc_DocumentTool.ShapeTool_s(xde.Main())
    colors = XCAFDoc_DocumentTool.ColorTool_s(xde.Main())
    from OCP.collections import Sequence_TDF_Label

    labels = Sequence_TDF_Label()
    shapes.GetFreeShapes(labels)
    read = shapes.GetShape_s(labels.Value(1))
    red = 0
    c = Quantity_Color()
    exp = TopExp_Explorer(read, TopAbs_FACE)
    while exp.More():
        if colors.GetColor(exp.Current(), XCAFDoc_ColorSurf, c):
            r, g, b = c.Values(Quantity_TOC_sRGB)
            red += int(round(r, 2) == 1.0 and round(g, 2) == 0.0 and round(b, 2) == 0.0)
        exp.Next()
    assert red == 6
    # Without colours the plain writer is used, as before.
    export.export_step(named.shape, tmp_path / "plain.step")
    assert (tmp_path / "plain.step").stat().st_size > 0


def test_3mf_writes_a_material_per_triangle(tmp_path: Path) -> None:
    doc, plate, block = _two_bodies()
    named = body(rebuild(doc), block)  # type: ignore[arg-type]
    app = with_color(
        {"part_color": PART_COLOR, "faces": {}}, Target("face", f"{plate}/cap/end"), "#00FF00"
    )
    path = tmp_path / "part.3mf"
    export.export_3mf(named.shape, path, color=part_color(app), faces=face_colors(named, app))
    model = zipfile.ZipFile(path).read("3D/3dmodel.model").decode()
    assert 'displaycolor="#00FF00"' in model and f'displaycolor="{PART_COLOR}"' in model
    marks = re.findall(r'p1="(\d)"', model)
    assert marks.count("1") == 2  # the green top face: two triangles
    assert set(marks) == {"0", "1"}
    plain = tmp_path / "plain.3mf"
    export.export_3mf(named.shape, plain)
    assert 'p1="' not in zipfile.ZipFile(plain).read("3D/3dmodel.model").decode()


def test_files_with_colours_round_trip_and_older_files_open_unchanged() -> None:
    doc, _plate, block = _two_bodies()
    app = with_color(doc.appearance, Target("feature", block), "#FF0000")  # type: ignore[attr-defined]
    doc.appearance = with_color(app, Target("body", "2"), "#00FF00")  # type: ignore[attr-defined]
    text = fdef.dumps(doc)  # type: ignore[arg-type]
    assert '"features": {' in text and '"bodies": {' in text
    assert fdef.dumps(fdef.loads(text)) == text
    for path in sorted(SAMPLE_DIR.glob("*.fdprt")):
        raw = path.read_text(encoding="utf-8")
        assert '"features": {' not in raw
        assert fdef.dumps(fdef.loads(raw)) == raw


def test_colours_in_use_name_faces_by_their_feature() -> None:
    """Round 10c: the list showed internal face names such as "Face f6/side/e4"."""
    app = {"part_color": PART_COLOR, "faces": {}}
    app = with_color(app, Target("face", "f6/side/e4"), "#333333")
    app = with_color(app, Target("face", "f6/cap/end"), "#333333")
    app = with_color(app, Target("face", "f8/side/e1"), "#444444")
    used = dict(colors_in_use(app, {"f6": "Bracket", "f8": "Holes"}))
    assert used["#333333"] == ["2 faces of Bracket"]
    assert used["#444444"] == ["Face of Holes"]


def test_appearance_entries_one_per_item() -> None:
    """D584: each item with a colour is its own entry; a feature's faces are one entry."""
    from fdcad.core.appearance import appearance_entries

    app = {
        "part_color": "#112233",
        "bodies": {"2": "#AA0000"},
        "features": {"f6": "#00AA00"},
        "faces": {"f8/side/a": "#0000AA", "f8/side/b": "#0000AA", "f6/cap/end": "#0000AA"},
    }
    entries = appearance_entries(app, {"f6": "Bracket", "f8": "Holes"})
    labels = [(c, label, len(t)) for c, label, t in entries]
    assert labels == [
        ("#112233", "Part", 1),
        ("#AA0000", "Body 2", 1),
        ("#00AA00", "Bracket", 1),
        ("#0000AA", "2 faces of Holes", 2),
        ("#0000AA", "Face of Bracket", 1),
    ]
    assert {t.kind for _c, _l, ts in entries for t in ts} == {"part", "body", "feature", "face"}


@pytest.mark.parametrize("propagate", [True, False])
def test_propagate_colours_colours_the_copies(propagate: bool) -> None:
    """Audit B item 2, E item 7.3 (D717): the setting was stored but never read."""
    from fdcad.core.appearance import face_colors, propagating
    from tests.core.features.test_patterns import X, centred, count, length, ok_body, pattern

    doc, _plate, boss = centred()
    doc.appearance["features"] = {boss: "#FF0000"}
    params = {"spacing1": length(12), "count1": count(3), "propagate_colours": propagate}
    fid, results = pattern(
        doc, "linear_pattern", params, {"direction1": X, "features": [{"feature": boss}]}
    )
    body = ok_body(results, fid)
    red = face_colors(body, doc.appearance, propagating(doc))
    copies = {n for n, f in body.faces if "/instance" in n and any(f.IsSame(r) for r, _c in red)}
    assert bool(copies) is propagate
