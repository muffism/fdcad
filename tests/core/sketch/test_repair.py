"""Repair Sketch (TR37, D1300)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Arc, Line, Relation, Sketch
from fdcad.core.sketch.repair import find_faults, fix, fix_all
from fdcad.core.sketch.solver import solve
from fdcad.core.sketch.topology import check
from tests.core.sketch.test_feature_check import SQUARE, _poly


def _kinds(sk: Sketch, tol: float = 0.05) -> list[str]:
    return [f.kind for f in find_faults(sk, tol)]


def test_a_clean_square_has_no_faults() -> None:
    sk = Sketch()
    _poly(sk, SQUARE, closed=True)
    assert find_faults(sk) == []


def test_a_small_gap_is_found_and_joined_at_its_middle() -> None:
    sk = Sketch()
    _poly(sk, [*SQUARE, (0.0, 0.02)], closed=False)  # 0.02 mm short of the start
    (gap,) = find_faults(sk)
    assert gap.kind == "gap" and "0.02 mm" in gap.message
    assert gap.move == pytest.approx(0.01)
    assert find_faults(sk, 0.01) == []  # a smaller typed tolerance skips it
    moved = fix(sk, gap)
    assert moved == pytest.approx(0.01)
    assert find_faults(sk) == []
    assert not [i for i in check(sk) if i.kind == "open"]


def test_a_tiny_segment_is_removed_and_its_ends_joined() -> None:
    sk = Sketch()
    _poly(sk, [(0.0, 0.0), (10.0, 0.0), (10.0, 0.01), (10.0, 10.0)], closed=False)
    faults = find_faults(sk)
    assert [f.kind for f in faults] == ["tiny"]
    tiny = sk.entities[faults[0].key]
    assert isinstance(tiny, Line)
    fix(sk, faults[0])
    assert faults[0].key not in sk.entities
    lines = [e for e in sk.entities.values() if isinstance(e, Line)]
    assert len(lines) == 2 and find_faults(sk) == []
    assert not [i for i in check(sk) if i.kind == "open" and len(i.entities) > 2]


def test_zero_length_line_zero_radius_arc_and_duplicates() -> None:
    sk = Sketch()
    zero = sk.add_line(5.0, 5.0, 5.0, 5.0)
    sk.add_circle(20.0, 0.0, 0.0)
    c1 = sk.add_circle(40.0, 0.0, 3.0)
    sk.add_circle(40.0, 0.0, 3.0)
    p = sk.add_point(60.0, 0.0)
    sk.add_point(60.0, 0.0)
    kinds = _kinds(sk)
    assert kinds == ["zero_line", "zero_radius", "duplicate_curve", "duplicate_point"]
    count, largest = fix_all(sk)
    assert count == 4 and largest == 0.0
    assert zero not in sk.entities and c1 in sk.entities and p in sk.entities
    assert find_faults(sk) == []


def test_overlapping_lines_merge_into_one_without_moving() -> None:
    sk = Sketch()
    a = sk.add_line(0.0, 0.0, 10.0, 0.0)
    b = sk.add_line(6.0, 0.0, 15.0, 0.0)
    (fault,) = find_faults(sk)
    assert fault.kind == "overlap" and fault.move == 0.0
    fix(sk, fault)
    assert b not in sk.entities
    line = sk.entities[a]
    assert isinstance(line, Line)
    assert sorted([sk.xy(line.p1), sk.xy(line.p2)]) == [(0.0, 0.0), (15.0, 0.0)]
    assert len(sk.entities) == 3


def test_relations_and_dimensions_on_wrong_or_missing_items() -> None:
    sk = Sketch()
    line = sk.add_line(0.0, 0.0, 10.0, 0.0)
    circle = sk.add_circle(20.0, 0.0, 2.0)
    sk.relations.append(Relation("horizontal", [circle]))  # wrong kind
    sk.relations.append(Relation("vertical", ["e99"]))  # missing
    sk.dimension("radius", [line], Param("2", 2.0))  # a line has no radius
    sk.dimension("distance", ["e77", "e78"], Param("2", 2.0), driving=False)
    faults = find_faults(sk)
    assert [f.kind for f in faults] == [
        "bad_relation",
        "bad_relation",
        "bad_dimension",
        "bad_dimension",
    ]
    assert "no longer exists" in faults[1].message
    count, _ = fix_all(sk)
    assert count == 4 and not sk.relations and not sk.dimensions
    assert solve(sk).solved


def test_fix_all_closes_an_imported_outline() -> None:
    """Common use: a DXF outline that does not quite close (TR37 item 4)."""
    sk = Sketch()
    pts = [(0.0, 0.0), (20.0, 0.003), (20.01, 10.0), (0.0, 10.0)]
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        sk.add_line(a[0] + 0.004 * i, a[1], b[0], b[1] + 0.002)
    assert all(f.kind == "gap" for f in find_faults(sk))
    count, largest = fix_all(sk)
    assert count == 4 and 0 < largest < 0.05
    assert find_faults(sk) == []
    assert not [i for i in check(sk) if i.kind == "open"]


def test_a_tiny_arc_is_removed() -> None:
    sk = Sketch()
    arc = sk.add_arc(0.0, 0.0, 1.0, 0.0, 0.01)
    a = sk.entities[arc]
    assert isinstance(a, Arc)
    left = sk.add_line(-5.0, 0.0, 1.0, 0.0)
    right = sk.add_line(math.cos(0.01), math.sin(0.01), 5.0, 5.0)
    sk.relate("coincident", sk.entities[left].p2, a.start)  # type: ignore[union-attr]
    sk.relate("coincident", a.end, sk.entities[right].p1)  # type: ignore[union-attr]
    (fault,) = find_faults(sk)
    assert fault.kind == "tiny"
    fix(sk, fault)
    assert arc not in sk.entities and a.center not in sk.entities
    assert find_faults(sk) == []
