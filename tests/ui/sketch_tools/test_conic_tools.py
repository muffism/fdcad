"""Conic and Equation Curve sketch tools (TR28, D757)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.sketch.conic import conic_point
from fdcad.core.sketch.model import Sketch, Spline
from fdcad.core.units import UnitSystem
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.sketch_tools.conic_tools import ConicTool, EquationCurveTool
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.registry import EXTRA_TOOL_NAMES
from fdcad.ui.sketch_tools.tools import make_tool
from tests.ui.sketch_tools.p2_helpers import edit_of


def _snap(x: float, y: float) -> Snap:
    return Snap("free", x, y)


def _splines(sk: Sketch) -> list[Spline]:
    return [e for e in sk.entities.values() if isinstance(e, Spline)]


def test_commands_icons_and_registry() -> None:
    from fdcad.ui.icons.audit import audit

    for cid, label in (("sketch.conic", "Conic"), ("sketch.equation_curve", "Equation Curve")):
        assert BY_ID[cid].label == label and BY_ID[cid].keys == ()
        assert audit(cid) == []
    assert {"conic", "equation_curve"} <= set(EXTRA_TOOL_NAMES)
    edit = edit_of()
    assert isinstance(make_tool("conic", edit), ConicTool)
    assert isinstance(make_tool("equation_curve", edit), EquationCurveTool)


def test_conic_three_clicks() -> None:
    edit = edit_of()
    tool = ConicTool(edit)
    assert "start" in tool.prompt
    tool.rho = 0.3
    for p in ((0.0, 0.0), (40.0, 0.0)):
        assert not tool.click(_snap(*p))
    assert "top point" in tool.prompt
    tool.hover(_snap(20.0, 30.0))
    assert len(tool.preview().lines) > 10  # the chord, the tangents and the curve
    assert tool.click(_snap(20.0, 30.0))
    (spline,) = _splines(edit.sketch)
    xy = [edit.sketch.xy(p) for p in spline.points]
    assert xy[0] == (0.0, 0.0) and xy[-1] == (40.0, 0.0)
    assert xy[len(xy) // 2] == pytest.approx(conic_point((0, 0), (20, 30), (40, 0), 0.3, 0.5))
    edit.undo()
    assert _splines(edit.sketch) == []  # one undo step


def test_conic_on_the_chord_says_why() -> None:
    edit = edit_of()
    tool = ConicTool(edit)
    tool.click(_snap(0.0, 0.0))
    tool.click(_snap(40.0, 0.0))
    assert not tool.click(_snap(20.0, 0.0))
    assert "Move the top point" in tool.take_message()
    assert _splines(edit.sketch) == [] and len(tool.clicks) == 2  # pick the top again


def test_equation_curve_adds_one_spline() -> None:
    edit = edit_of()
    tool = EquationCurveTool(edit)
    tool.x_expr, tool.y_expr = "10*cos(t)", "10*sin(t)"
    tool.t_start, tool.t_end, tool.count = 0.0, math.pi / 2, 7
    assert tool.preview().lines
    assert tool.option_changed("add")
    assert "7 points" in tool.take_message()
    (spline,) = _splines(edit.sketch)
    assert len(spline.points) == 7
    assert edit.sketch.xy(spline.points[-1]) == pytest.approx((0.0, 10.0), abs=1e-9)


def test_equation_curve_error_and_units() -> None:
    edit = edit_of()
    tool = EquationCurveTool(edit)
    tool.x_expr = "t +"
    assert not tool.option_changed("add")
    assert "not added" in tool.take_message() and _splines(edit.sketch) == []
    tool.x_expr, tool.y_expr, tool.t_start, tool.t_end, tool.count = "t", "0", 0.0, 1.0, 3
    tool.units = UnitSystem.IN
    assert tool.option_changed("add")
    (spline,) = _splines(edit.sketch)
    assert edit.sketch.xy(spline.points[-1]) == pytest.approx((25.4, 0.0))
