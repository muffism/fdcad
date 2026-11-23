"""Fully Define Sketch tool (TR35, D762)."""

from __future__ import annotations

from fdcad.core.sketch.solver import SketchStatus, solve
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.sketch_tools.fully_define_tool import FullyDefineTool
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.registry import EXTRA_TOOL_NAMES
from tests.ui.sketch_tools.p2_helpers import edit_of


def test_command_and_icon() -> None:
    from fdcad.ui.icons.audit import audit

    assert BY_ID["sketch.fully_define"].label == "Fully Define Sketch"
    assert BY_ID["sketch.fully_define"].keys == ()
    assert audit("sketch.fully_define") == []
    assert "fully_define" in EXTRA_TOOL_NAMES


def test_calculate_then_apply_is_one_undo_step() -> None:
    edit = edit_of()
    edit.sketch.add_circle(12.0, 8.0, 5.0)
    tool = FullyDefineTool(edit)
    assert "Press Calculate" in tool.prompt
    assert not tool.option_changed("calculate")
    assert "Would add 3" in tool.prompt and "Diameter 10mm" in tool.prompt
    assert tool.option_changed("apply")
    assert "Added 3" in tool.take_message()
    assert solve(edit.sketch).status is SketchStatus.FULL
    edit.undo()
    assert edit.sketch.dimensions == []


def test_a_clicked_point_becomes_the_datum() -> None:
    edit = edit_of()
    cid = edit.sketch.add_circle(12.0, 8.0, 5.0)
    other = edit.sketch.add_circle(40.0, 8.0, 3.0)
    centre = edit.sketch.entities[cid].center  # type: ignore[union-attr]
    tool = FullyDefineTool(edit)
    tool.click(Snap("point", 12.0, 8.0, target=centre))
    assert tool.datum == centre and "clicked point" in tool.take_message()
    tool.option_changed("calculate")
    other_centre = edit.sketch.entities[other].center  # type: ignore[union-attr]
    assert tool.proposals is not None
    assert any(p.entities == (centre, other_centre) for p in tool.proposals)


def test_selected_scope_without_a_selection_says_so() -> None:
    edit = edit_of()
    edit.sketch.add_circle(12.0, 8.0, 5.0)
    tool = FullyDefineTool(edit)
    tool.scope = "selected"
    tool.option_changed("calculate")
    assert "Nothing is selected" in tool.take_message()
    tool.take_selection([])
    assert tool.scope == "selected"
    cid = next(iter(e for e in edit.sketch.entities if e.startswith("e")), "")
    tool.take_selection([cid])
    assert tool.selected == [cid]


def test_a_fully_defined_sketch_has_nothing_to_add() -> None:
    edit = edit_of()
    tool = FullyDefineTool(edit)
    tool.option_changed("calculate")
    assert "Nothing to add" in tool.prompt
    assert not tool.option_changed("apply")
