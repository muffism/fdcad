"""Right click locks the dimension type while placing (TR111 item 1, D1707)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.edit import locked_type
from tests.ui.sketch_tools.test_dimension_panel_wp8 import (  # noqa: F401  (fixture)
    _click,
    _move,
    _pos,
    canvas,
)


def test_locked_type_only_swaps_point_to_point_types() -> None:
    assert locked_type("distance", "horizontal_distance") == "horizontal_distance"
    assert locked_type("radius", "horizontal_distance") == "radius"
    assert locked_type("vertical_distance", None) == "vertical_distance"


def test_right_click_locks_horizontal_then_unlocks(
    qtbot: QtBot,
    canvas: SketchCanvas,  # noqa: F811
) -> None:
    sk = canvas.edit.sketch
    a = sk.add_point(0.0, 0.0)
    b = sk.add_point(30.0, 20.0)
    canvas.edit.refresh()
    canvas.set_tool("dimension")
    canvas.dim_picks = [a, b]
    _move(qtbot, canvas, (15.0, 30.0))  # above both: horizontal
    assert canvas.dim_preview is not None
    assert canvas.dim_preview.type == "horizontal_distance"
    notes: list[str] = []
    canvas.status_message.connect(notes.append)
    qtbot.mouseClick(canvas, Qt.MouseButton.RightButton, pos=_pos(canvas, (15.0, 30.0)))
    assert canvas.dim_lock == "horizontal_distance"
    assert "locked to horizontal" in notes[-1]
    _move(qtbot, canvas, (40.0, 10.0))  # beside both: would be vertical
    assert canvas.dim_preview is not None
    assert canvas.dim_preview.type == "horizontal_distance"
    _click(qtbot, canvas, (40.0, 10.0))
    (dim,) = sk.dimensions
    assert dim.type == "horizontal_distance"
    assert canvas.dim_lock is None


def test_right_click_with_nothing_to_place_is_not_a_lock(
    canvas: SketchCanvas,  # noqa: F811
) -> None:
    canvas.set_tool("dimension")
    assert not canvas.toggle_dimension_lock()
