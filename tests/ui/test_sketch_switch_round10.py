"""Edit Sketch on another sketch while the open one cannot close (bug hunt round 10)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import sketch_from_data
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_workflow import (  # noqa: F401  (fixtures)
    _folders,
    canvas_of,
    click,
    new_part,
    rectangle_sketch,
    window,
)


def test_edit_another_sketch_keeps_the_open_one_when_its_value_is_wrong(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = new_part(qtbot, window)
    first = rectangle_sketch(qtbot, window, tab)
    second = rectangle_sketch(qtbot, window, tab)
    mode = window.sketch_mode
    assert mode is not None
    mode.edit(first)
    canvas = canvas_of(window)
    canvas.scale, canvas.center = 4.0, (20.0, 15.0)
    canvas.set_tool("line")
    click(qtbot, canvas, 50, 50)
    click(qtbot, canvas, 60, 50)
    canvas.set_tool("dimension")
    click(qtbot, canvas, 20, 0)
    click(qtbot, canvas, 20, -8)
    assert canvas.value_box is not None
    canvas.value_box.edit.setText("abc")
    # The open sketch cannot be written back, so it stays open with its changes.
    mode.edit(second)
    assert canvas_of(window) is canvas
    assert canvas.edit.feature.id == first
    assert canvas.value_box is not None
    canvas.value_box.edit.setText("40")
    mode.edit(second)
    assert canvas_of(window).edit.feature.id == second
    lines = sketch_from_data(tab.session.document.feature(first).data).curves()
    assert len(lines) == 5  # the rectangle and the new line were kept


def test_switching_parts_keeps_a_sketch_whose_value_is_wrong(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    # Round 10a (D592): the tab changed and left the sketch open under the other part.
    first = new_part(qtbot, window)
    sid = rectangle_sketch(qtbot, window, first)
    second = new_part(qtbot, window)
    window.tabs.setCurrentWidget(first)
    mode = window.sketch_mode
    assert mode is not None
    mode.edit(sid)
    canvas = canvas_of(window)
    canvas.scale, canvas.center = 4.0, (20.0, 15.0)
    canvas.set_tool("dimension")
    click(qtbot, canvas, 20, 0)
    click(qtbot, canvas, 20, -8)
    assert canvas.value_box is not None
    canvas.value_box.edit.setText("abc")
    window.tabs.setCurrentWidget(second)
    assert window.tabs.currentWidget() is first
    assert mode.is_open and mode.tab is first
