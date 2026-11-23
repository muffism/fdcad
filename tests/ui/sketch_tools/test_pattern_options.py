"""Sketch pattern options: model edge direction, radius and angle (TR107, D1308)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.sketch.model import Line
from fdcad.ui.sketch_tools.pattern_tools import CircularPatternTool, LinearPatternTool
from tests.ui.sketch_tools.p2_helpers import edit_of


def test_a_model_edge_sets_direction_1_and_is_held_by_a_fixed_copy() -> None:
    edit = edit_of()
    seed = edit.sketch.add_circle(0.0, 0.0, 1.0)
    tool = LinearPatternTool(edit)
    tool.tolerance = 0.5
    tool.model_lines = [[(0.0, -10.0), (10.0, 0.0)]]  # a 45 degree part edge
    tool.picks = [seed]
    tool.option_changed("pick_direction1")
    assert tool.pick_for == "direction1"
    from fdcad.ui.sketch_tools.inference import Snap

    tool.click(Snap("free", 5.0, -5.0))
    assert tool.angle1 == pytest.approx(math.pi / 4)
    assert tool.direction_model is not None
    assert tool.option_changed("make")
    copy = edit.sketch.entities[tool.direction_line or ""]
    assert isinstance(copy, Line) and copy.construction
    ends = sorted([edit.sketch.xy(copy.p1), edit.sketch.xy(copy.p2)])
    assert ends == [pytest.approx((0.0, -10.0)), pytest.approx((10.0, 0.0))]


def test_circular_radius_and_angle_move_the_centre() -> None:
    edit = edit_of()
    seed = edit.sketch.add_circle(10.0, 0.0, 1.0)
    tool = CircularPatternTool(edit)
    tool.picks = [seed]
    tool._sync_polar()
    assert tool.radius == pytest.approx(10.0) and tool.start_angle == pytest.approx(0.0)
    tool.radius = 4.0
    tool.start_angle = math.pi / 2
    tool.option_changed("radius")
    assert (tool.cx, tool.cy) == pytest.approx((10.0, -4.0))
    assert tool.centre_point is None
    tool.radius = 0.0
    tool.option_changed("radius")
    assert "greater than zero" in tool.message
    assert tool.radius == pytest.approx(4.0)
