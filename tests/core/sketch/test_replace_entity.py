"""Replace Entity (TR104, D846)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Arc, Dimension, Line, Sketch
from fdcad.core.sketch.ops.replace_entity import ReplaceError, replace_entity


def test_line_replaced_by_an_arc_keeps_its_id_and_fitting_links() -> None:
    s = Sketch()
    a = s.add_line(0, 0, 10, 0)
    b = s.add_line(10, 0, 10, 10)
    la, lb = s.entities[a], s.entities[b]
    assert isinstance(la, Line) and isinstance(lb, Line)
    s.relate("horizontal", a)
    s.relate("coincident", la.p2, lb.p1)
    s.dimensions.append(Dimension("d1", "distance", [la.p1, la.p2], Param("10", 10.0)))
    s.next_dimension = 2
    arc = s.add_arc(5, 0, 5.0, 3.14159265, 0.0)  # from (0, 0) over to (10, 0)
    out = replace_entity(s, a, arc)
    assert arc not in s.entities and isinstance(s.entities[a], Arc)  # the old id now an arc
    assert "horizontal relation 1" in out.dropped
    assert [r.type for r in s.relations] == ["coincident"]
    assert s.dimensions and s.dimensions[0].id == "d1"
    assert out.kept_as is None


def test_keep_old_as_construction_and_bad_picks() -> None:
    s = Sketch()
    a = s.add_line(0, 0, 10, 0)
    b = s.add_line(0, 1, 10, 1)
    out = replace_entity(s, a, b, keep_old=True)
    assert out.kept_as is not None
    kept = s.entities[out.kept_as]
    assert isinstance(kept, Line) and kept.construction
    with pytest.raises(ReplaceError):
        replace_entity(s, a, a)
