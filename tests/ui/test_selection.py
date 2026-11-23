"""Selection filters and box selection (TOOL_SPEC T14.3.2, T14.3.3).

Select Other (T14.3.1) is tested with the right click menus in
``test_context_menus.py``. The 3D view needs a GPU, so its box rules are tested
through the pure rules in ``ui/input/selection_rules.py``.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Line, Point
from fdcad.ui.input import selection_rules as rules
from fdcad.ui.input.filter_cursor import filter_cursor, filter_pixmap
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from tests.ui.test_workflow import (  # noqa: F401  (fixtures)
    _folders,
    canvas_of,
    draw_rectangle,
    new_part,
    plane_id,
    window,
)

# Pure rules ---------------------------------------------------------------------------------


def test_filter_types_toggle_and_switch_off_at_once() -> None:
    f = rules.SelectionFilter()
    assert not f.is_on() and f.allows("edge") and f.view_kinds() == {"face", "edge", "vertex"}
    assert f.toggle("edge")
    assert f.is_on() and f.allows("edge") and not f.allows("face")
    assert f.view_kinds() == {"edge"}
    assert not f.toggle_enabled()  # F6: everything selects again
    assert f.allows("face") and f.active == {"edge"}
    assert f.toggle("vertex")  # a key turns the filters back on
    assert f.enabled and f.view_kinds() == {"edge", "vertex"}
    assert not f.toggle("vertex")
    f.select_all()
    assert f.active == set(rules.FILTER_KINDS)
    f.clear()
    assert not f.is_on()


def test_sketch_item_types() -> None:
    assert rules.sketch_kind("d3", ["e1"]) == "dimension"
    assert rules.sketch_kind("e1", ["e1"]) == "point"
    assert rules.sketch_kind("e2", ["e1"]) == "segment"


def test_box_direction_and_modifiers() -> None:
    assert not rules.is_crossing((10, 10), (50, 40))  # left to right: inside only
    assert rules.is_crossing((50, 10), (10, 40))  # right to left: crossing
    assert rules.scheme(False, False) == "replace"
    assert rules.scheme(True, False) == "add"
    assert rules.scheme(False, True) == "toggle"
    assert rules.apply(["a", "b"], ["b", "c"], "replace") == ["b", "c"]
    assert rules.apply(["a", "b"], ["b", "c"], "add") == ["a", "b", "c"]
    assert rules.apply(["a", "b"], ["b", "c"], "toggle") == ["a", "c"]


def test_window_and_crossing_tests() -> None:
    rect = rules.rect_of((0, 0), (10, 10))
    inside = [(2, 2), (8, 8)]
    crossing = [(5, 5), (20, 5)]
    through = [(-5, 5), (20, 5)]  # crosses with both ends outside
    away = [(20, 20), (30, 30)]
    assert rules.picked(rect, inside, crossing=False)
    assert not rules.picked(rect, crossing, crossing=False)
    assert rules.picked(rect, crossing, crossing=True)
    assert rules.picked(rect, through, crossing=True)
    assert not rules.picked(rect, away, crossing=True)
    assert not rules.polyline_inside(rect, [])


def test_filter_cursor_has_a_picture(qtbot: QtBot) -> None:
    assert not filter_pixmap(2.0).isNull()
    assert filter_cursor().hotSpot() == QPoint(1, 1)


# Window ---------------------------------------------------------------------------------------


def test_filter_keys_and_bar(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    new_part(qtbot, window)
    bar = window.filter_bar
    assert not bar.isVisible()
    assert window.commands.trigger("select.filter_bar")  # F5
    assert bar.isVisible()
    assert window.commands.trigger("select.filter_edges")  # E
    assert window._filters() == {"edge"} and bar.buttons["edge"].isChecked()
    assert "Edges" in window.status.text()
    assert window.commands.trigger("select.filter_faces")  # X
    assert window.commands.trigger("select.filter_vertices")  # V
    assert window._filters() == {"edge", "face", "vertex"}
    assert window.selection_filter.is_on()
    assert window.commands.trigger("select.filters_toggle")  # F6
    assert not window.selection_filter.is_on() and not bar.buttons["edge"].isEnabled()
    assert "off" in window.status.text()
    bar.clear_action.trigger()
    assert window.selection_filter.active == set()
    bar.all_action.trigger()
    assert window.selection_filter.active == set(rules.FILTER_KINDS)
    shortcuts = {
        cid: [k.toString() for k in window.commands.actions[cid].shortcuts()]
        for cid in (
            "select.filter_bar",
            "select.filters_toggle",
            "select.filter_edges",
            "select.filter_faces",
            "select.filter_vertices",
        )
    }
    assert shortcuts == {
        "select.filter_bar": ["F5"],
        "select.filters_toggle": ["F6"],
        "select.filter_edges": ["E"],
        "select.filter_faces": ["X"],
        "select.filter_vertices": ["V"],
    }
    assert window.commands.trigger("select.filter_bar")
    assert not bar.isVisible()


def _open_rectangle(qtbot: QtBot, win: MainWindow) -> SketchCanvas:
    tab = new_part(qtbot, win)
    assert win.sketch_mode is not None
    win.sketch_mode.start(plane_id=plane_id(tab, "Front Plane"))
    draw_rectangle(qtbot, win)  # 40 x 30 at the origin, centred in the view
    canvas = canvas_of(win)
    canvas.selection = []
    return canvas


def _drag(
    qtbot: QtBot,
    canvas: SketchCanvas,
    a: tuple[float, float],
    b: tuple[float, float],
    mods: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
) -> None:
    pa, pb = canvas.to_screen(a), canvas.to_screen(b)
    qa, qb = QPoint(round(pa.x()), round(pa.y())), QPoint(round(pb.x()), round(pb.y()))
    qtbot.mousePress(canvas, Qt.MouseButton.LeftButton, mods, qa)
    qtbot.mouseMove(canvas, QPoint((qa.x() + qb.x()) // 2, (qa.y() + qb.y()) // 2))
    qtbot.mouseMove(canvas, qb)
    qtbot.mouseRelease(canvas, Qt.MouseButton.LeftButton, mods, qb)


def test_sketch_box_window_crossing_shift_and_ctrl(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    canvas = _open_rectangle(qtbot, window)
    sk = canvas.edit.sketch
    lines = {e.id: e for e in sk.entities.values() if isinstance(e, Line)}

    def ys(eid: str) -> set[float]:
        e = lines[eid]
        return {round(sk.xy(e.p1)[1]), round(sk.xy(e.p2)[1])}

    bottom = next(i for i in lines if ys(i) == {0})
    top = next(i for i in lines if ys(i) == {30})
    # Left to right around the bottom edge only: the bottom line and its corner points.
    _drag(qtbot, canvas, (-5.0, -5.0), (45.0, 5.0))
    assert bottom in canvas.selection and top not in canvas.selection
    assert not any(i in canvas.selection for i in lines if i != bottom)
    # Right to left over the lower half: also the two sides the box crosses.
    _drag(qtbot, canvas, (45.0, -5.0), (-5.0, 10.0))
    picked_lines = {i for i in canvas.selection if i in lines}
    assert picked_lines == set(lines) - {top}
    # Shift adds what a new box finds; the rest stays.
    _drag(qtbot, canvas, (-5.0, 25.0), (45.0, 35.0), Qt.KeyboardModifier.ShiftModifier)
    assert set(lines) <= set(canvas.selection)
    # Ctrl toggles what the box finds.
    _drag(qtbot, canvas, (-5.0, 25.0), (45.0, 35.0), Qt.KeyboardModifier.ControlModifier)
    assert top not in canvas.selection and bottom in canvas.selection


def test_sketch_filter_limits_clicks_and_boxes(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    canvas = _open_rectangle(qtbot, window)
    window.filter_bar.toggle("point")
    assert canvas.select_filter is not None
    sk = canvas.edit.sketch
    _drag(qtbot, canvas, (-5.0, -5.0), (45.0, 35.0))
    assert canvas.selection and all(isinstance(sk.entities[i], Point) for i in canvas.selection)
    p = canvas.to_screen((20.0, 0.0))  # middle of the bottom line
    canvas.selection = []
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(round(p.x()), round(p.y())))
    assert canvas.selection == []
    assert canvas.cursor().shape() == Qt.CursorShape.BitmapCursor
    window.filter_bar.toggle_enabled()
    assert canvas.select_filter is None
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(round(p.x()), round(p.y())))
    assert len(canvas.selection) == 1 and isinstance(sk.entities[canvas.selection[0]], Line)


def test_body_filter_picks_through_faces_and_tree_kinds_are_greyed(qtbot: object) -> None:
    """Audit D11 item 2, E item 12.2 (D719): with only Solid Bodies or Planes on, a click
    picked nothing."""
    from fdcad.ui.main_window.filter_bar import FilterBar

    f = rules.SelectionFilter()
    f.toggle("body")
    assert f.view_kinds() == {"face"}
    bar = FilterBar(rules.SelectionFilter())
    qtbot.addWidget(bar)  # type: ignore[attr-defined]
    assert all(not bar.buttons[k].isEnabled() for k in rules.TREE_KINDS)
    assert "feature tree" in bar.buttons["plane"].toolTip()
    assert bar.buttons["body"].isEnabled()
