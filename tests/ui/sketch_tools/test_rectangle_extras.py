"""Rectangle extras: construction lines, rounded corners, inner frame (TR114, D1313)."""

from __future__ import annotations

from fdcad.core.sketch.model import Arc, Line
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.tools import CenterRectangleTool, CornerRectangleTool
from tests.ui.sketch_tools.p2_helpers import edit_of


def _draw(tool) -> None:  # type: ignore[no-untyped-def]
    tool.click(Snap("free", 0.0, 0.0))
    tool.click(Snap("free", 20.0, 10.0))
    tool.edit.refresh()


def _lines(edit, construction: bool) -> list[Line]:  # type: ignore[no-untyped-def]
    return [
        e
        for e in edit.sketch.entities.values()
        if isinstance(e, Line) and e.construction == construction
    ]


def test_plain_rectangle_is_unchanged() -> None:
    edit = edit_of()
    _draw(CornerRectangleTool(edit))
    assert len(_lines(edit, False)) == 4 and not _lines(edit, True)


def test_midlines_round_corners_and_frame_in_one_step() -> None:
    edit = edit_of()
    tool = CornerRectangleTool(edit)
    tool.lines, tool.round, tool.frame = "midlines", 2.0, 1.5
    _draw(tool)
    assert len(_lines(edit, True)) == 2
    arcs = [e for e in edit.sketch.entities.values() if isinstance(e, Arc)]
    assert len(arcs) == 4  # the outer corners only
    assert len(_lines(edit, False)) == 8  # outer sides and the inner frame
    assert edit.result is not None and edit.result.solved and not edit.result.conflicting
    edit.undo()
    assert not [e for e in edit.sketch.entities.values() if isinstance(e, Line)]


def test_diagonals_on_a_corner_rectangle_and_too_big_a_radius() -> None:
    edit = edit_of()
    tool = CornerRectangleTool(edit)
    tool.lines = "diagonals"
    _draw(tool)
    assert len(_lines(edit, True)) == 2
    edit2 = edit_of()
    tool = CornerRectangleTool(edit2)
    tool.round = 50.0
    tool.click(Snap("free", 0.0, 0.0))
    assert not tool.click(Snap("free", 20.0, 10.0))
    assert not [e for e in edit2.sketch.entities.values() if isinstance(e, Line)]


def test_centre_rectangle_keeps_its_own_diagonals() -> None:
    edit = edit_of()
    tool = CenterRectangleTool(edit)
    tool.lines = "diagonals"
    _draw(tool)
    assert len(_lines(edit, True)) == 2
