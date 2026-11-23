"""Explode sketch text into curves (TR121 item 1, D1713)."""

from __future__ import annotations

import pytest

from fdcad.core.sketch.model import Arc, Line, Sketch, Spline
from fdcad.core.sketch.open_ends import open_end_points
from fdcad.core.sketch.solver import solve
from fdcad.core.sketch.text import SketchText
from fdcad.core.sketch.text_explode import apply_explode, explode_pieces


def test_explode_makes_closed_free_curves_and_drops_the_text() -> None:
    s = Sketch(texts=[SketchText("t1", "LO", height=10.0)])
    pieces = explode_pieces(s, "t1")
    assert pieces
    made = apply_explode(s, "t1", pieces)
    assert s.texts == []
    assert len(made) == len(pieces)
    kinds = {type(s.entities[c]) for c in made}
    assert Line in kinds and kinds <= {Line, Arc, Spline}
    assert not any(r.type == "fixed" and set(r.entities) & set(made) for r in s.relations)
    assert open_end_points(s) == []  # every glyph outline is closed
    xs = [s.xy(p)[0] for e in s.entities.values() if isinstance(e, Line) for p in (e.p1, e.p2)]
    assert min(xs) >= 0.0 and max(xs) < 30.0
    assert solve(s).solved


def test_unknown_text() -> None:
    with pytest.raises(ValueError, match="No text"):
        explode_pieces(Sketch(), "t9")
