"""Repair Sketch tool (TR37, D1300)."""

from __future__ import annotations

from fdcad.ui.input.commands import BY_ID
from fdcad.ui.sketch_tools.registry import EXTRA_TOOL_NAMES
from fdcad.ui.sketch_tools.repair_tool import RepairSketchTool
from tests.core.sketch.test_feature_check import SQUARE, _poly
from tests.ui.sketch_tools.p2_helpers import edit_of


def test_command_icon_and_registry() -> None:
    from fdcad.ui.icons.audit import audit

    assert BY_ID["sketch.repair_sketch"].keys == ()
    assert audit("sketch.repair_sketch") == []
    assert "repair_sketch" in EXTRA_TOOL_NAMES


def test_find_zoom_fix_and_undo_in_one_step() -> None:
    edit = edit_of()
    _poly(edit.sketch, [*SQUARE, (0.0, 0.02)], closed=False)
    edit.sketch.add_line(30.0, 0.0, 30.0, 0.0)
    before = len(edit.sketch.entities)
    tool = RepairSketchTool(edit)
    assert "press Find" in tool.prompt
    tool.option_changed("find")
    assert tool.faults is not None and len(tool.faults) == 2
    assert "2 faults" in tool.prompt
    tool.option_changed("next")
    focus = tool.take_focus()
    assert focus is not None and focus[1]
    assert "Fault 1 of 2" in tool.take_message()
    assert tool.option_changed("fix")
    assert "moving points by up to" in tool.take_message()
    assert tool.faults is not None and len(tool.faults) == 1
    edit.undo()
    assert len(edit.sketch.entities) == before
    assert tool.option_changed("fix_all")
    assert "Fixed 2 faults" in tool.take_message()
    assert tool.prompt == "No faults found."
    edit.undo()  # Fix All is one undo step
    assert len(edit.sketch.entities) == before


def test_tolerance_change_and_nothing_to_fix() -> None:
    edit = edit_of()
    _poly(edit.sketch, [*SQUARE, (0.0, 0.02)], closed=False)
    tool = RepairSketchTool(edit)
    tool.gap = 0.01
    tool.option_changed("gap")
    assert not tool.option_changed("fix_all")
    assert tool.take_message() == "No faults found."
    tool.option_changed("next")
    assert "Press Find first" in tool.take_message()
