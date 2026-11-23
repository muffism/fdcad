"""Symmetric angle about a centerline, half or full (TR111 item 2, D2200)."""

from __future__ import annotations

import math

from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Sketch, sketch_from_data, sketch_to_data
from fdcad.core.sketch.solver import measure, solve
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.edit import mirrored_middle, symmetric_order
from tests.ui.sketch_tools.p2_helpers import edit_of
from tests.ui.sketch_tools.test_dimension_panel_wp8 import (  # noqa: F401  (fixture)
    _click,
    _move,
    canvas,
)


def _sketch() -> tuple[Sketch, str, str]:
    sk = Sketch()
    axis = sk.add_line(0.0, 0.0, 0.0, 40.0, construction=True)
    line = sk.add_line(0.0, 0.0, 10.0, 30.0)
    return sk, line, axis


def test_text_across_the_centerline_gives_the_full_angle() -> None:
    sk, line, axis = _sketch()
    assert symmetric_order(sk, [axis, line], (-5.0, 20.0)) == [line, axis]
    assert symmetric_order(sk, [axis, line], (5.0, 20.0)) is None
    edit = edit_of(sk)
    sk = edit.sketch
    full = edit.add_dimension("angle", [axis, line], None, (-5.0, 20.0))
    assert full.symmetric and full.entities == [line, axis]
    half = math.atan2(10.0, 30.0)
    assert math.isclose(full.param.value, 2 * half)
    plain = edit.add_dimension("angle", [axis, line], None, (5.0, 20.0))
    assert not plain.symmetric
    assert math.isclose(plain.param.value, half)


def test_solver_holds_the_full_angle_and_it_saves() -> None:
    sk, line, axis = _sketch()
    edit = edit_of(sk)
    sk = edit.sketch
    dim = edit.add_dimension("angle", [axis, line], Param("60deg", math.radians(60)), (-5.0, 20.0))
    solve(sk)
    assert math.isclose(measure(sk, dim), math.radians(60), abs_tol=1e-6)
    again = sketch_from_data(sketch_to_data(sk))
    copy = next(d for d in again.dimensions if d.id == dim.id)
    assert copy.symmetric
    mirror = mirrored_middle(sk, dim)
    assert mirror is not None


def test_dimension_tool_places_a_symmetric_angle(
    qtbot: QtBot,
    canvas: SketchCanvas,  # noqa: F811
) -> None:
    sk = canvas.edit.sketch
    axis = sk.add_line(0.0, 0.0, 0.0, 40.0, construction=True)
    line = sk.add_line(0.0, 0.0, 10.0, 30.0)
    canvas.edit.refresh()
    canvas.set_tool("dimension")
    canvas.dim_picks = [axis, line]
    _move(qtbot, canvas, (-8.0, 20.0))
    assert canvas.dim_preview is not None and canvas.dim_preview.symmetric
    _click(qtbot, canvas, (-8.0, 20.0))
    (dim,) = sk.dimensions
    assert dim.symmetric and dim.type == "angle"
