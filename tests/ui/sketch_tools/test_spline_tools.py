"""Insert Spline Point, Fit Spline and Simplify Spline tools (TR42, D1306)."""

from __future__ import annotations

import math

from fdcad.core.sketch.model import Line, Spline
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.registry import EXTRA_TOOL_NAMES
from fdcad.ui.sketch_tools.spline_tools import (
    FitSplineTool,
    InsertSplinePointTool,
    SimplifySplineTool,
)
from tests.core.sketch.test_feature_check import _poly
from tests.core.sketch.test_spline_edit import _wave
from tests.ui.sketch_tools.p2_helpers import edit_of


def test_commands_icons_and_registry() -> None:
    from fdcad.ui.icons.audit import audit

    for name in ("insert_spline_point", "fit_spline", "simplify_spline"):
        assert name in EXTRA_TOOL_NAMES
        assert BY_ID[f"sketch.{name}"].keys == ()
        assert audit(f"sketch.{name}") == []


def test_insert_spline_point_by_click() -> None:
    edit = edit_of()
    sp = _wave(edit.sketch, 3)
    tool = InsertSplinePointTool(edit)
    tool.tolerance = 0.5
    assert not tool.click(Snap("free", 50.0, 50.0))
    assert "Click on a spline" in tool.take_message()
    x = 2.5
    y = math.sin(x / 10 * math.pi) * 3
    assert tool.click(Snap("free", x, y))
    spline = edit.sketch.entities[sp.id]
    assert isinstance(spline, Spline) and len(spline.points) == 4
    edit.undo()
    assert len(edit.sketch.entities[sp.id].points) == 3  # type: ignore[union-attr]


def test_fit_spline_from_the_selection() -> None:
    edit = edit_of()
    lines = _poly(edit.sketch, [(0.0, 0.0), (5.0, 2.0), (10.0, 0.0)], closed=False)
    tool = FitSplineTool(edit)
    assert not tool.option_changed("fit")
    assert "Nothing is picked" in tool.take_message()
    tool.take_selection(lines)
    assert "2 curves picked" in tool.prompt
    tool.keep = True
    assert tool.option_changed("fit")
    assert "Made a spline" in tool.take_message()
    assert all(edit.sketch.entities[i].construction for i in lines)  # type: ignore[union-attr]
    assert len([e for e in edit.sketch.entities.values() if isinstance(e, Spline)]) == 1
    edit.undo()
    assert not [e for e in edit.sketch.entities.values() if isinstance(e, Spline)]
    assert all(isinstance(edit.sketch.entities[i], Line) for i in lines)


def test_simplify_spline_previews_then_applies() -> None:
    edit = edit_of()
    sp = _wave(edit.sketch, 15)
    tool = SimplifySplineTool(edit)
    assert not tool.option_changed("calculate")
    tool.take_selection([sp.id])
    tool.option_changed("calculate")
    assert "of 15 points left" in tool.prompt and tool.result is not None
    assert tool.preview().lines
    assert tool.option_changed("apply")
    assert "Removed" in tool.take_message()
    assert len(edit.sketch.entities[sp.id].points) < 15  # type: ignore[union-attr]
