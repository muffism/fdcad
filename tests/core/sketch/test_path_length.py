"""Path Length dimension (TR45, D1307)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Sketch, sketch_from_data, sketch_to_data
from fdcad.core.sketch.solver import measure, path_length, solve
from tests.core.sketch.test_feature_check import _poly


def test_a_path_length_drives_the_total_length_of_a_chain() -> None:
    sk = Sketch()
    lines = _poly(sk, [(0.0, 0.0), (10.0, 0.0), (10.0, 5.0)], closed=False)
    arc = sk.add_arc(20.0, 5.0, 10.0, math.pi / 2, math.pi)
    assert path_length(sk, [*lines, arc]) == pytest.approx(15 + 5 * math.pi)
    sk.relate("horizontal", lines[0])
    sk.relate("vertical", lines[1])
    dim = sk.dimension("path_length", lines, Param("20", 20.0))
    result = solve(sk)
    assert result.solved and not result.conflicting
    assert path_length(sk, lines) == pytest.approx(20.0, abs=1e-6)
    assert measure(sk, dim) == pytest.approx(20.0, abs=1e-6)
    again = sketch_from_data(sketch_to_data(sk))
    assert again.dimensions[0].type == "path_length"


def test_a_path_length_with_an_arc() -> None:
    sk = Sketch()
    line = sk.add_line(0.0, 0.0, 10.0, 0.0)
    arc = sk.add_arc(10.0, 5.0, 5.0, -math.pi / 2, 0.0)
    sk.dimension("path_length", [line, arc], Param("30", 30.0))
    assert solve(sk).solved
    assert path_length(sk, [line, arc]) == pytest.approx(30.0, abs=1e-6)


def test_a_path_length_refuses_other_curves() -> None:
    from fdcad.core.sketch.solver import SketchSolveError

    sk = Sketch()
    circle = sk.add_circle(0.0, 0.0, 3.0)
    sk.dimension("path_length", [circle], Param("5", 5.0))
    with pytest.raises(SketchSolveError, match="lines, arcs or splines"):
        solve(sk)
