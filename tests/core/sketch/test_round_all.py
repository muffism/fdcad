"""Round All Corners (TR227, D834)."""

from __future__ import annotations

import pytest

from fdcad.core.sketch.model import Arc, Line, Sketch
from fdcad.core.sketch.ops.corner import CornerError, corners_of, round_all
from fdcad.core.sketch.solver import solve


def _rect() -> tuple[Sketch, list[str]]:
    s = Sketch()
    pts = [(0, 0), (40, 0), (40, 20), (0, 20)]
    ids = [s.add_line(*pts[i], *pts[(i + 1) % 4]) for i in range(4)]
    return s, ids


def test_four_corners_one_dimension_and_an_override() -> None:
    s, ids = _rect()
    assert len(corners_of(s, ids)) == 4
    out = round_all(s, ids, 3.0, overrides={2: 5.0})
    assert len(out.arcs) == 4 and not out.skipped
    radii = sorted(
        round(e.radius if hasattr(e, "radius") else s.radius(e.id), 6)
        for e in s.entities.values()
        if isinstance(e, Arc)
    )
    assert radii == [3.0, 3.0, 3.0, 5.0]
    dims = [d for d in s.dimensions if d.type == "radius"]
    assert len(dims) == 2  # the shared one and the override
    assert sum(1 for r in s.relations if r.type == "equal") == 2
    solve(s)
    assert all(isinstance(s.entities[i], Line) for i in ids)


def test_too_big_corners_are_skipped_or_refused() -> None:
    s, ids = _rect()
    out = round_all(s, ids, 12.0, overrides={0: 2.0})
    assert out.arcs and out.skipped
    s2, ids2 = _rect()
    with pytest.raises(CornerError, match="No corner"):
        round_all(s2, ids2, 50.0)
    with pytest.raises(CornerError, match="no corners"):
        round_all(Sketch(), [], 1.0)
