"""Sketch text (PHASE4_SPEC P4.8): data round trip, layout options, the profile and
extrude, cut and wrap of text."""

import math
from typing import Any

import pytest

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import face_area
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Arc, Line, Sketch, sketch_from_data, sketch_to_data
from fdcad.core.sketch.profiles import BASIS_PLANES, ProfileError, build_profile
from fdcad.core.sketch.text import SketchText, TextError, layout, text_from_json, text_to_json
from tests.core.features.test_features import (
    add_extrude,
    add_sketch,
    body,
    messages,
    plate,
    rect,
    volume,
)
from tests.core.features.test_hole import face_ref

XY = BASIS_PLANES["xy"]


def bounds(faces: list[Any]) -> tuple[float, float, float, float]:
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    for f in faces:
        BRepBndLib.Add_s(f, box)
    lo, hi = box.CornerMin(), box.CornerMax()
    return lo.X(), lo.Y(), hi.X(), hi.Y()


def test_round_trip_keeps_defaults_out() -> None:
    t = SketchText("t1", "FDCAD", x=1.0, y=2.0, bold=True)
    raw = text_to_json(t)
    assert raw == {"id": "t1", "text": "FDCAD", "x": 1.0, "y": 2.0, "bold": True}
    assert text_from_json(raw) == t
    s = Sketch(texts=[t])
    assert sketch_from_data(sketch_to_data(s)).texts == [t]
    assert "texts" not in sketch_to_data(Sketch())


def test_layout_options() -> None:
    s = Sketch()
    plain = layout(SketchText("t1", "HHHH", height=10.0), s)
    x0, _y0, x1, _y1 = bounds(plain)
    assert x0 >= -0.5 and x1 > 20
    wide = layout(SketchText("t1", "HHHH", height=10.0, spacing=200.0), s)
    assert bounds(wide)[2] > x1 + 15
    narrow = layout(SketchText("t1", "HHHH", height=10.0, width=50.0), s)
    assert bounds(narrow)[2] < x1
    right = layout(SketchText("t1", "HHHH", height=10.0, align="right", box=100.0), s)
    assert bounds(right)[2] == pytest.approx(100.0, abs=2.0)
    turned = layout(SketchText("t1", "HHHH", height=10.0, angle=math.pi / 2), s)
    assert bounds(turned)[3] > 20
    flipped = layout(SketchText("t1", "HHHH", height=10.0, flip_h=True), s)
    assert bounds(flipped)[0] < -20
    bold = layout(SketchText("t1", "HHHH", height=10.0, bold=True), s)
    assert face_area(bold) > face_area(plain)


def test_text_along_a_line_and_an_arc() -> None:
    s = Sketch()
    a, b = s.add_point(0, 0), s.add_point(0, 60)
    lid = s.new_id()
    s.entities[lid] = Line(lid, a, b)
    up = layout(SketchText("t1", "ABC", height=8.0, curve=lid, align="full"), s)
    x0, _y0, x1, y1 = bounds(up)
    assert y1 > 50 and x1 - x0 < 12
    c, p, q = s.add_point(0, 0), s.add_point(30, 0), s.add_point(-30, 0)
    aid = s.new_id()
    s.entities[aid] = Arc(aid, c, p, q, ccw=True)
    curved = layout(SketchText("t2", "ARC TEXT", height=5.0, curve=aid), s)
    # The text runs along the arc's direction with its top to the left (inside).
    assert 15 < bounds(curved)[3] < 30.5


def test_errors() -> None:
    with pytest.raises(TextError, match="empty"):
        layout(SketchText("t1", "  "), Sketch())
    with pytest.raises(TextError, match="height"):
        layout(SketchText("t1", "A", height=0.0), Sketch())
    with pytest.raises(ProfileError):
        s = Sketch(texts=[SketchText("t1", "")])
        build_profile(s, XY)


def _text_sketch(doc: Any, plane: dict[str, Any], **kw: Any) -> str:
    s = Sketch(texts=[SketchText("t1", "FD", x=5.0, y=20.0, height=10.0, **kw)])
    return add_sketch(doc, s, plane)


def test_extrude_and_cut_text() -> None:
    doc, ext = plate()
    top = face_ref(doc, ext, "cap/end")
    sk = _text_sketch(doc, top)
    cut = add_extrude(doc, sk, 1.0, operation="cut", reverse=True)
    results = rebuild(doc)
    removed = 25000 - volume(body(results, cut).shape)
    letters = build_profile(results[sk].sketch.model, results[sk].sketch.plane)  # type: ignore[union-attr]
    assert removed == pytest.approx(face_area(letters.faces), rel=1e-6)
    boss = add_extrude(doc, sk, 2.0)
    assert rebuild(doc)[boss].state is not FeatureState.ERROR


def test_text_with_curves_and_wrap() -> None:
    from tests.core.features.test_wrap import SHAFT, side_shaft

    doc, ext, eid = side_shaft()
    s = Sketch(texts=[SketchText("t1", "A", x=-3.0, y=-25.0, height=8.0)])
    sk = add_sketch(doc, s, {"feature": "f3"})
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "wrap",
            "Wrap 1",
            params={"wrap_type": "emboss", "thickness": Param("0.5", 0.5)},
            refs={"sketch": {"feature": sk}, "face": [face_ref(doc, ext, f"side/{eid}")]},
        )
    )
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert volume(body({fid: res}, fid).shape) > SHAFT
    both = Sketch(texts=[SketchText("t1", "A", x=20.0, y=20.0, height=5.0)])
    rect(both, 0, 0, 10, 10)
    assert len(build_profile(both, XY).faces) == 2


def test_stencil_bridges_free_every_island() -> None:
    """An O cut through a sheet keeps its middle joined (TR297 item 3, D802)."""
    from OCP.BRepTools import BRepTools
    from OCP.TopAbs import TopAbs_WIRE
    from OCP.TopExp import TopExp_Explorer

    from fdcad.core.sketch.model import Sketch
    from fdcad.core.sketch.text import SketchText, layout, text_from_json, text_to_json

    def holes(face: object) -> int:
        count = 0
        ex = TopExp_Explorer(face, TopAbs_WIRE)
        while ex.More():
            count += 0 if ex.Current().IsSame(BRepTools.OuterWire_s(face)) else 1
            ex.Next()
        return count

    plain = layout(SketchText("t1", "O", height=10.0), Sketch())
    assert sum(holes(f) for f in plain) == 1
    stencil = SketchText("t1", "O", height=10.0, stencil=True, bridge=1.5)
    cut = layout(stencil, Sketch())
    assert sum(holes(f) for f in cut) == 0 and len(cut) == 2
    back = text_from_json(text_to_json(stencil))
    assert back.stencil and back.bridge == 1.5
    assert "stencil" not in text_to_json(SketchText("t1", "O"))
