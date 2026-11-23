"""Check Sketch for Feature (TR36, D763)."""

from __future__ import annotations

import pytest

from fdcad.core.sketch.feature_check import KINDS, check_for
from fdcad.core.sketch.model import Line, Sketch


def _poly(sk: Sketch, pts: list[tuple[float, float]], closed: bool) -> list[str]:
    pairs = list(zip(pts, pts[1:] + (pts[:1] if closed else []), strict=False))
    lines = [sk.add_line(*a, *b) for a, b in pairs]
    for a, b in zip(lines, lines[1:] + (lines[:1] if closed else []), strict=False):
        la, lb = sk.entities[a], sk.entities[b]
        assert isinstance(la, Line) and isinstance(lb, Line)
        sk.relate("coincident", la.p2, lb.p1)
    return lines


SQUARE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]


def test_a_closed_square_suits_closed_kinds_only() -> None:
    sk = Sketch()
    _poly(sk, SQUARE, closed=True)
    for kind in ("boss", "cut", "revolve", "sweep_profile", "loft_profile", "wrap", "flange"):
        assert check_for(sk, kind) == [], kind
    (problem,) = check_for(sk, "sweep_path")
    assert problem.kind == "count" and "one open contour" in problem.message


def test_an_open_contour_reports_its_gap() -> None:
    sk = Sketch()
    _poly(sk, [*SQUARE, (0.0, 2.0)], closed=False)  # stops 2 mm short of the start
    problems = check_for(sk, "boss")
    opens = [p for p in problems if p.kind == "open"]
    assert len(opens) == 2 and all("2 mm from the nearest open end" in p.message for p in opens)
    assert all(p.at is not None for p in opens)
    assert check_for(sk, "rib") == []  # one open contour is what a rib takes


def test_a_near_miss() -> None:
    sk = Sketch()
    _poly(sk, [*SQUARE, (0.0, 0.01)], closed=False)
    problems = check_for(sk, "boss")
    near = [p for p in problems if p.kind == "near_miss"]
    assert len(near) == 1 and "0.01 mm apart" in near[0].message


def test_three_curves_at_one_point() -> None:
    sk = Sketch()
    lines = _poly(sk, SQUARE, closed=True)
    extra = sk.add_line(10.0, 10.0, 20.0, 20.0)
    end = sk.entities[lines[1]]
    assert isinstance(end, Line)
    sk.relate("coincident", end.p2, sk.entities[extra].p1)  # type: ignore[union-attr]
    kinds = {p.kind for p in check_for(sk, "boss")}
    assert "branch" in kinds


def test_duplicates_and_two_profiles() -> None:
    sk = Sketch()
    _poly(sk, SQUARE, closed=True)
    sk.add_line(0.0, 0.0, 10.0, 0.0)  # on top of the bottom edge
    assert any(p.kind == "duplicate" for p in check_for(sk, "boss"))
    two = Sketch()
    _poly(two, SQUARE, closed=True)
    _poly(two, [(20.0, 0.0), (30.0, 0.0), (30.0, 10.0)], closed=True)
    assert check_for(two, "boss") == []
    (problem,) = check_for(two, "loft_profile")
    assert "one closed contour" in problem.message and "2 closed" in problem.message


def test_construction_and_crossings_are_ignored() -> None:
    sk = Sketch()
    _poly(sk, SQUARE, closed=True)
    sk.add_line(-5.0, 5.0, 15.0, 5.0, construction=True)
    assert check_for(sk, "sweep_profile") == []
    crossing = Sketch()
    _poly(crossing, SQUARE, closed=True)
    _poly(crossing, [(5.0, -5.0), (15.0, -5.0), (15.0, 5.0), (5.0, 5.0)], closed=True)
    assert check_for(crossing, "boss") == []


def test_empty_and_unknown() -> None:
    assert check_for(Sketch(), "boss")[0].kind == "empty"
    with pytest.raises(ValueError):
        check_for(Sketch(), "nothing")
    assert set(KINDS) >= {"boss", "cut", "revolve", "sweep_path", "rib", "flange"}
