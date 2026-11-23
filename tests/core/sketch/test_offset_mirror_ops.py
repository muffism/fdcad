"""Offset and Mirror on small sketches of our own (PHASE2_SPEC P2.8 items 1 and 4)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param
from fdcad.core.io import fdef
from fdcad.core.sketch.model import Arc, Circle, Line, Sketch, sketch_from_data, sketch_to_data
from fdcad.core.sketch.ops.geom import geo
from fdcad.core.sketch.ops.mirror import mirror
from fdcad.core.sketch.ops.offset import OffsetError, chain_from, offset
from fdcad.core.sketch.solver import SketchStatus, drag, solve
from fdcad.samples.make import SAMPLE_DIR


def _corner() -> tuple[Sketch, str, str]:
    """An L: (0,0) to (20,0) to (20,10), joined at the corner."""
    sk = Sketch()
    a = sk.add_line(0, 0, 20, 0)
    b = sk.add_line(20, 0, 20, 10)
    la, lb = sk.entities[a], sk.entities[b]
    assert isinstance(la, Line) and isinstance(lb, Line)
    sk.relate("coincident", la.p2, lb.p1)
    return sk, a, b


def _ends(sk: Sketch, lid: str) -> tuple[tuple[float, float], tuple[float, float]]:
    line = sk.entities[lid]
    assert isinstance(line, Line)
    return sk.xy(line.p1), sk.xy(line.p2)


def test_offset_chain_inside_meets_at_the_corner() -> None:
    sk, a, b = _corner()
    dof = solve(sk).dof
    result = offset(sk, [a, b], 2.0, (10, 5))
    ca, cb = result.copies
    assert _ends(sk, ca) == (pytest.approx((0, 2)), pytest.approx((18, 2)))
    assert _ends(sk, cb) == (pytest.approx((18, 2)), pytest.approx((18, 10)))
    res = solve(sk)
    assert res.solved and res.status is not SketchStatus.OVER
    assert res.dof == dof  # the copies add no freedom
    rel = next(r for r in sk.relations if r.type == "offset")
    assert rel.entities == [a, ca, b, cb] and rel.value == 2.0


def test_offset_follows_the_source() -> None:
    sk, a, b = _corner()
    sk.relate("fixed", a)
    result = offset(sk, [a, b], 2.0, (10, 5))
    line = sk.entities[b]
    assert isinstance(line, Line)
    drag(sk, {line.p2: (20, 20)})
    copy_b = result.copies[1]
    assert _ends(sk, copy_b)[1] == pytest.approx((18, 20), abs=1e-6)


def test_offset_with_dimension_drives_the_distance() -> None:
    sk, a, b = _corner()
    sk.relate("fixed", a, b)
    result = offset(sk, [a, b], 2.0, (10, 5), add_dimension=True)
    assert result.dimension is not None
    rel = next(r for r in sk.relations if r.type == "offset")
    assert rel.value is None
    dim = next(d for d in sk.dimensions if d.id == result.dimension)
    dim.param = Param("3", 3.0)
    assert solve(sk).solved
    assert _ends(sk, result.copies[1])[0][0] == pytest.approx(17)


def test_offset_circle_and_arc() -> None:
    sk = Sketch()
    c = sk.add_circle(0, 0, 5)
    out = offset(sk, [c], 2.0, (10, 0)).copies[0]
    circle = sk.entities[out]
    assert isinstance(circle, Circle) and circle.radius == pytest.approx(7)
    arc = sk.add_arc(30, 0, 5, 0, math.pi)
    copy = offset(sk, [arc], 1.0, (30, 1)).copies[0]
    assert geo(sk, copy).r == pytest.approx(4)
    assert solve(sk).status is not SketchStatus.OVER


def test_offset_that_inverts_an_arc_is_refused() -> None:
    sk = Sketch()
    arc = sk.add_arc(0, 0, 2, 0, math.pi)
    with pytest.raises(OffsetError, match="inside out"):
        offset(sk, [arc], 3.0, (0, 1))


def test_offset_both_directions_with_line_caps() -> None:
    sk = Sketch()
    lid = sk.add_line(0, 0, 20, 0)
    result = offset(sk, [lid], 1.0, (5, 3), both=True, cap="lines")
    assert len(result.copies) == 2 and len(result.caps) == 2
    ys = sorted(_ends(sk, c)[0][1] for c in result.copies)
    assert ys == pytest.approx([-1, 1])
    res = solve(sk)
    assert res.solved and res.status is not SketchStatus.OVER and res.dof == 4


def test_offset_caps_arcs_one_side() -> None:
    sk = Sketch()
    lid = sk.add_line(0, 0, 20, 0)
    result = offset(sk, [lid], 2.0, (5, 3), cap="arcs")
    assert len(result.caps) == 2
    for cap in result.caps:
        assert isinstance(sk.entities[cap], Arc)
        assert geo(sk, cap).r == pytest.approx(1)
    assert solve(sk).status is not SketchStatus.OVER


def test_offset_construction_options() -> None:
    sk, a, b = _corner()
    result = offset(sk, [a, b], 1.0, (10, 5), base_construction=True, offset_construction=True)
    assert all(sk.entities[i].construction for i in (a, b, *result.copies))


def test_chain_from_follows_connected_curves() -> None:
    sk, a, b = _corner()
    sk.add_line(50, 50, 60, 50)
    assert sorted(chain_from(sk, a)) == sorted([a, b])


def test_relation_value_round_trips_and_older_relations_save_unchanged() -> None:
    sk, a, b = _corner()
    plain = sketch_to_data(sk)
    assert all("value" not in r for r in plain["relations"])
    offset(sk, [a, b], 2.0, (10, 5))
    data = sketch_to_data(sk)
    rel = next(r for r in data["relations"] if r["type"] == "offset")
    assert rel["value"] == 2.0
    assert sketch_to_data(sketch_from_data(data)) == data


def test_samples_still_save_byte_for_byte() -> None:
    for path in SAMPLE_DIR.glob("*.fdprt"):
        text = path.read_text(encoding="utf-8")
        assert fdef.dumps(fdef.loads(text)) == text


def test_mirror_copies_with_symmetric_relations() -> None:
    sk = Sketch()
    axis = sk.add_line(0, -10, 0, 10, construction=True)
    lid = sk.add_line(2, 0, 8, 3)
    cid = sk.add_circle(5, 5, 2)
    aid = sk.add_arc(5, -5, 2, 0, 1)
    report = mirror(sk, [lid, cid, aid], axis)
    assert report is not None and len(report.entities) == 3
    ml, mc, ma = report.entities
    assert _ends(sk, ml) == (pytest.approx((-2, 0)), pytest.approx((-8, 3)))
    circle = sk.entities[mc]
    assert isinstance(circle, Circle) and sk.xy(circle.center) == pytest.approx((-5, 5))
    arc = sk.entities[ma]
    assert isinstance(arc, Arc) and not arc.ccw
    sym = [r for r in sk.relations if r.type == "symmetric"]
    assert all(r.entities[-1] == axis for r in sym)
    assert len(sym) == 2 + 1 + 2  # line ends, the circle, the arc ends
    assert any(r.type == "equal" and r.entities == [aid, ma] for r in sk.relations)
    sk.relate("fixed", axis)
    res = solve(sk)
    assert res.solved and res.status is not SketchStatus.OVER and not res.redundant
    # The copy follows the original.
    line = sk.entities[lid]
    assert isinstance(line, Line)
    drag(sk, {line.p2: (9, 4)})
    x, y = sk.xy(line.p2)
    assert (x, y) != pytest.approx((8, 3))
    assert _ends(sk, ml)[1] == pytest.approx((-x, y), abs=1e-6)


def test_mirror_without_copy_replaces_the_originals() -> None:
    sk = Sketch()
    axis = sk.add_line(0, -10, 0, 10, construction=True)
    lid = sk.add_line(2, 0, 8, 3)
    sk.relate("fixed", lid)
    report = mirror(sk, [lid], axis, copy=False)
    assert report is not None
    assert lid not in sk.entities and [r.type for r in report.relations] == ["fixed"]
    assert _ends(sk, report.entities[0])[0] == pytest.approx((-2, 0))


def test_point_on_the_mirror_line_is_shared() -> None:
    sk = Sketch()
    axis = sk.add_line(0, -10, 0, 10, construction=True)
    lid = sk.add_line(0, 0, 8, 3)
    report = mirror(sk, [lid], axis)
    assert report is not None
    a, b = sk.entities[lid], sk.entities[report.entities[0]]
    assert isinstance(a, Line) and isinstance(b, Line)
    assert a.p1 == b.p1


def _line(sk: Sketch, lid: str) -> Line:
    line = sk.entities[lid]
    assert isinstance(line, Line)
    return line


def test_mirror_without_copy_keeps_the_joins_of_the_replaced_shape() -> None:
    # Round 10: the replaced rectangle lost its corner joins and came apart on a drag.
    sk = Sketch()
    corners = [(5, 5), (25, 5), (25, 20), (5, 20)]
    lines = [sk.add_line(*corners[i], *corners[(i + 1) % 4]) for i in range(4)]
    for i in range(4):
        a, b = _line(sk, lines[i]), _line(sk, lines[(i + 1) % 4])
        sk.relate("coincident", a.p2, b.p1)
    sk.relate("parallel", lines[0], lines[2])
    sk.relate("fixed", lines[0])
    axis = sk.add_line(0, -10, 0, 30, construction=True)
    report = mirror(sk, lines, axis, copy=False)
    assert report is not None
    copies = report.entities
    # The joins and Parallel move onto the copies; only the Fix is removed.
    assert [r.type for r in report.relations] == ["fixed"]
    for i in range(4):
        a, b = _line(sk, copies[i]), _line(sk, copies[(i + 1) % 4])
        assert ["coincident", a.p2, b.p1] in [[r.type, *r.entities] for r in sk.relations]
    assert ["parallel", copies[0], copies[2]] in [[r.type, *r.entities] for r in sk.relations]
    assert all(set(r.entities) <= set(sk.entities) for r in sk.relations)
    assert solve(sk).solved
    # Dragging a corner keeps the shape closed.
    corner = _line(sk, copies[1]).p2
    assert drag(sk, {corner: (-30.0, 25.0)})
    assert sk.xy(_line(sk, copies[1]).p2) == pytest.approx(sk.xy(_line(sk, copies[2]).p1))
