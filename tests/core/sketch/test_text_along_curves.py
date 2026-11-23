"""Text along circles and splines, with a start offset (TR230, D976)."""

from __future__ import annotations

import pytest

from fdcad.core.sketch.model import Sketch, Spline
from fdcad.core.sketch.text import SketchText, TextError, layout, text_from_json, text_to_json
from tests.core.sketch.test_sketch_text import bounds


def test_centred_text_sits_on_top_of_a_circle() -> None:
    s = Sketch()
    cid = s.add_circle(0, 0, 30)
    faces = layout(SketchText("t1", "TOP", height=5.0, curve=cid, align="center"), s)
    x0, y0, x1, y1 = bounds(faces)
    assert y0 > 20 and y1 < 36  # on top of the ring, letters standing outward
    assert abs(x0 + x1) < 4  # centred


def test_text_along_a_spline_and_its_offset() -> None:
    s = Sketch()
    pts = [s.add_point(0, 0), s.add_point(40, 10), s.add_point(80, 0)]
    handles = [s.add_point(10, 5), s.add_point(50, 10), s.add_point(90, -5)]
    sid = s.new_id()
    s.entities[sid] = Spline(sid, pts, handles)
    plain = layout(SketchText("t1", "WAVE", height=5.0, curve=sid), s)
    moved = layout(SketchText("t1", "WAVE", height=5.0, curve=sid, offset=30.0), s)
    assert bounds(moved)[0] > bounds(plain)[0] + 20


def test_offset_round_trips_and_bad_curves_say_what_to_pick() -> None:
    t = SketchText("t1", "A", curve="e1", offset=12.5)
    assert text_to_json(t)["offset"] == 12.5
    assert text_from_json(text_to_json(t)) == t
    s = Sketch()
    pid = s.add_point(0, 0)
    with pytest.raises(TextError, match="circle or spline"):
        layout(SketchText("t1", "A", curve=pid), s)
