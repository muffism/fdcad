"""Fully Define Sketch (TR35, D762)."""

from __future__ import annotations

import copy

import pytest

from fdcad.core.document.model import Param
from fdcad.core.sketch.fully_define import (
    FullyDefineError,
    apply,
    check_unmoved,
    origin_of,
    propose,
)
from fdcad.core.sketch.model import Line, Sketch
from fdcad.core.sketch.solver import SketchStatus, solve
from fdcad.core.units import UnitSystem

MM = UnitSystem.MM


def _base() -> Sketch:
    sk = Sketch()
    origin = sk.add_point(0.0, 0.0, construction=True)
    sk.relate("fixed", origin)
    return sk


def _rect(sk: Sketch, x0: float, y0: float, x1: float, y1: float) -> list[str]:
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    lines = [sk.add_line(*corners[i], *corners[(i + 1) % 4]) for i in range(4)]
    for a, b in zip(lines, lines[1:] + lines[:1], strict=True):
        la, lb = sk.entities[a], sk.entities[b]
        assert isinstance(la, Line) and isinstance(lb, Line)
        sk.relate("coincident", la.p2, lb.p1)
    return lines


def _check(sk: Sketch, **options: object) -> list:  # type: ignore[type-arg]
    before = copy.deepcopy(sk)
    proposals = propose(sk, MM, **options)  # type: ignore[arg-type]
    apply(sk, proposals, MM)
    result = solve(sk)
    assert result.status is SketchStatus.FULL, (result.dof, [p.text(MM) for p in proposals])
    assert check_unmoved(before, sk) < 1e-6
    return proposals


def test_a_rectangle_gets_relations_and_dimensions() -> None:
    sk = _base()
    _rect(sk, 10.0, 5.0, 40.0, 25.0)
    proposals = _check(sk)
    kinds = [(p.kind, p.type) for p in proposals]
    assert kinds.count(("relation", "horizontal")) == 2
    assert kinds.count(("relation", "vertical")) == 2
    assert ("dimension", "distance") in kinds  # a length
    texts = [p.text(MM) for p in proposals]
    assert any("30mm" in t for t in texts) and any("20mm" in t for t in texts)


def test_a_circle_gets_its_diameter_and_centre() -> None:
    sk = _base()
    sk.add_circle(12.0, 8.0, 5.0)
    proposals = _check(sk)
    assert [p.type for p in proposals] == ["diameter", "horizontal_distance", "vertical_distance"]
    assert proposals[0].value == pytest.approx(10.0)


def test_nothing_moves_and_existing_dimensions_stay() -> None:
    sk = _base()
    lines = _rect(sk, 0.0, 0.0, 30.0, 20.0)
    sk.dimension("distance", [lines[0]], Param("30", 30.0))
    proposals = _check(sk)
    lengths = [p for p in proposals if p.type == "distance"]
    assert all(p.entities != (lines[0],) for p in lengths)  # not repeated
    # The corner on the origin is tied with a relation, not a zero distance.
    assert not any(p.kind == "dimension" and p.value == 0 for p in proposals)


def test_a_fully_defined_sketch_needs_nothing() -> None:
    sk = _base()
    sk.add_circle(12.0, 8.0, 5.0)
    _check(sk)
    assert propose(sk, MM) == []


def test_a_conflict_is_refused() -> None:
    sk = _base()
    lines = _rect(sk, 0.0, 0.0, 30.0, 20.0)
    sk.dimension("distance", [lines[0]], Param("30", 30.0))
    sk.dimension("distance", [lines[0]], Param("40", 40.0))
    with pytest.raises(FullyDefineError, match="conflicting"):
        propose(sk, MM)


def test_chain_scheme() -> None:
    sk = _base()
    for x in (10.0, 25.0, 45.0):
        sk.add_circle(x, 10.0, 2.0)
    proposals = _check(sk, scheme="chain")
    horizontal = [p for p in proposals if p.type == "horizontal_distance"]
    assert sorted(round(p.value, 6) for p in horizontal) == [10.0, 15.0, 20.0]


def test_only_the_picked_entities() -> None:
    sk = _base()
    sk.add_circle(12.0, 8.0, 5.0)
    other = sk.add_circle(40.0, 8.0, 3.0)
    proposals = propose(sk, MM, entities={other})
    assert proposals and all(other in p.entities or p.kind == "dimension" for p in proposals)
    circle = sk.entities[other]
    centre = getattr(circle, "center", "")
    assert all(other in p.entities or centre in p.entities for p in proposals)


def test_relations_only_or_dimensions_only() -> None:
    sk = _base()
    _rect(sk, 10.0, 5.0, 40.0, 25.0)
    only_relations = propose(sk, MM, dimensions=False)
    assert only_relations and all(p.kind == "relation" for p in only_relations)
    only_dimensions = propose(sk, MM, relations=False)
    assert only_dimensions and all(p.kind == "dimension" for p in only_dimensions)


def test_inch_text() -> None:
    sk = _base()
    sk.add_circle(25.4, 0.0, 12.7)
    proposals = propose(sk, UnitSystem.IN)
    assert proposals[0].text(UnitSystem.IN).startswith("Diameter 1in")


def test_origin_is_found() -> None:
    sk = _base()
    assert origin_of(sk) is not None
    assert origin_of(Sketch()) is None
    with pytest.raises(FullyDefineError, match="no origin"):
        propose(Sketch(), MM)
