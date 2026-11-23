"""Merge two sketches on the same plane (TR122 item 1, D986)."""

from __future__ import annotations

from fdcad.core.document.model import Param
from fdcad.core.sketch.merge import merge
from fdcad.core.sketch.model import Line, Sketch
from fdcad.core.sketch.solver import solve


def _with_origin() -> Sketch:
    sk = Sketch()
    sk.relate("fixed", sk.add_point(0.0, 0.0, construction=True))
    return sk


def test_everything_moves_over_with_new_ids() -> None:
    a, b = _with_origin(), _with_origin()
    a.add_line(0, 0, 10, 0)
    lid = b.add_line(0, 0, 0, 20)
    line = b.entities[lid]
    assert isinstance(line, Line)
    origin_b = next(e for e in b.entities if e not in (lid, line.p1, line.p2))
    b.relate("coincident", line.p1, origin_b)
    b.relate("vertical", lid)
    b.dimension("distance", [lid], Param("20mm", 20.0)).name = "Height"
    before = len(a.entities)
    mapped = merge(a, b)
    assert len(a.entities) == before + 3  # the line and its two points; origins are one
    new = a.entities[mapped[lid]]
    assert isinstance(new, Line)
    origin_a = mapped[origin_b]
    assert any(r.type == "coincident" and origin_a in r.entities for r in a.relations)
    assert sum(1 for r in a.relations if r.type == "fixed") == 1
    assert [d.name for d in a.dimensions] == ["Height"]
    assert solve(a).solved
