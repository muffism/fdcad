"""Sketch problem list (TR38, D1301)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Line, Relation, Sketch
from fdcad.core.sketch.problems import (
    apply_way_out,
    diagnose,
    problems,
    replacement,
    set_item_entity,
    solve_around,
    state_of,
)
from fdcad.core.sketch.solver import SketchSolveError, solve


def _line(sk: Sketch, x1: float, y1: float, x2: float, y2: float) -> Line:
    line = sk.entities[sk.add_line(x1, y1, x2, y2)]
    assert isinstance(line, Line)
    return line


def test_dangling_items_are_left_out_so_the_rest_solves() -> None:
    sk = Sketch()
    line = _line(sk, 0.0, 0.0, 10.0, 1.0)
    sk.relate("horizontal", line.id)
    sk.relations.append(Relation("vertical", ["e99"]))
    sk.dimension("distance", [line.p1, "e98"], Param("5", 5.0))
    with pytest.raises(SketchSolveError):
        solve(sk)
    result, dangling = solve_around(sk)
    assert dangling == ["r1", "d1"] and result.solved
    assert sk.xy(line.p1)[1] == pytest.approx(sk.xy(line.p2)[1])  # the rest solved
    assert len(sk.relations) == 2 and not sk.relations[1].off and len(sk.dimensions) == 1
    assert state_of(result, dangling, []) == "dangling"
    rows = problems(sk, result, dangling)
    assert [p.kind for p in rows] == ["dangling", "dangling"]
    assert rows[0].missing == ["e99"] and "no longer exists" in rows[0].message


def test_invalid_geometry_and_no_solution_states() -> None:
    sk = Sketch()
    sk.add_line(1.0, 1.0, 1.0, 1.0)
    result, dangling = solve_around(sk)
    rows = problems(sk, result, dangling)
    assert [p.kind for p in rows] == ["invalid"] and "zero length" in rows[0].message
    assert state_of(result, dangling, [rows[0].entities[0]]) == "invalid"


def test_a_spline_that_crosses_itself_is_invalid() -> None:
    from fdcad.core.sketch.problems import _crosses_itself

    assert _crosses_itself([(0, 0), (10, 0), (10, 10), (5, -5)])
    assert not _crosses_itself([(0, 0), (10, 0), (10, 10), (0, 10)])
    assert not _crosses_itself([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])


def test_conflicts_are_grouped_and_diagnose_offers_the_duplicate_first() -> None:
    sk = Sketch()
    line = _line(sk, 0.0, 0.0, 10.0, 0.0)
    sk.relate("fixed", line.p1)
    sk.relate("horizontal", line.id)
    sk.dimension("distance", [line.p1, line.p2], Param("10", 10.0))
    sk.dimension("distance", [line.p1, line.p2], Param("12", 12.0))
    result, dangling = solve_around(sk)
    rows = problems(sk, result, dangling)
    conflicts = [p for p in rows if p.kind == "conflicting"]
    assert len(conflicts) == 1 and conflicts[0].group == 1
    assert set(conflicts[0].keys) >= {"d2"}
    ways = diagnose(sk, conflicts[0].keys)
    assert ways and ways[0].key == "d2" and ways[0].action == "reference"
    assert "reference dimension" in ways[0].label
    apply_way_out(sk, ways[0])
    result, _ = solve_around(sk)
    assert result.solved and not result.conflicting


def test_redundant_items_are_listed_apart_from_conflicts() -> None:
    sk = Sketch()
    line = _line(sk, 0.0, 0.0, 10.0, 0.0)
    sk.relate("horizontal", line.id)
    sk.relate("horizontal", line.id)
    result, dangling = solve_around(sk)
    kinds = [p.kind for p in problems(sk, result, dangling)]
    assert "redundant" in kinds and "conflicting" not in kinds


def test_replacement_finds_the_one_item_that_already_holds() -> None:
    sk = Sketch()
    a = _line(sk, 0.0, 0.0, 10.0, 0.0)
    _line(sk, 0.0, 5.0, 3.0, 9.0)  # slanted: Horizontal would move it
    sk.relations.append(Relation("horizontal", ["e50"]))
    assert replacement(sk, "r0") == {"e50": a.id}
    set_item_entity(sk, "r0", "e50", a.id)
    assert sk.relations[0].entities == [a.id]
    sk.relations.append(Relation("horizontal", ["e51"]))
    _line(sk, 0.0, 20.0, 10.0, 20.0)
    _line(sk, 0.0, 30.0, 10.0, 30.0)  # two free lines already hold: no clear match
    assert replacement(sk, "r1") is None
