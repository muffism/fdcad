"""Detach linked geometry (TR340, D885)."""

from __future__ import annotations

from fdcad.core.document.model import Param
from fdcad.core.sketch.curve_convert import CurvePiece, add_piece
from fdcad.core.sketch.links import detach, linked_in
from fdcad.core.sketch.model import Line, Sketch


def test_detach_frees_converted_curves_and_keeps_dimensions() -> None:
    s = Sketch()
    lid = add_piece(s, CurvePiece("line", [(0.0, 0.0), (10.0, 0.0)]))
    line = s.entities[lid]
    assert isinstance(line, Line)
    s.point(line.p1).source = {"kind": "vertex", "name": "f1/cap/end"}
    free = s.add_line(0, 5, 10, 5)
    s.dimension("distance", [lid], Param("10", 10.0))
    assert linked_in(s, [lid, free]) == [lid]
    assert detach(s, [lid, free]) == [lid]
    assert not any(r.type == "fixed" for r in s.relations)
    assert s.point(line.p1).source is None
    assert len(s.dimensions) == 1 and linked_in(s, [lid]) == []
