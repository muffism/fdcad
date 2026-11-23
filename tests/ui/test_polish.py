"""Polish items of the tool audit (gap report WP3): T1.4.1, T1.4.3, T1.5.2, T2.4.1, T10."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QTreeWidgetItem
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature
from fdcad.core.sketch.model import Circle, Line
from fdcad.core.units import UnitSystem
from fdcad.ui.input.gesture_guide import GestureGuide, GestureTracker
from fdcad.ui.main_window.shortcut_bar import ShortcutBar
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.edit import SketchEdit, new_sketch_data
from fdcad.ui.themes.theme import DARK, LIGHT
from fdcad.ui.tree.feature_tree import UNDER_PREFIX, strip_prefix
from tests.ui.test_workflow import (  # noqa: F401  (fixtures)
    _folders,
    canvas_of,
    new_part,
    plane_id,
    rectangle_sketch,
    window,
)


@pytest.fixture
def canvas(qtbot: QtBot) -> Iterator[SketchCanvas]:
    feature = Feature(
        "f5", "sketch", "Sketch 1", refs={"plane": {"feature": "f2"}}, data=new_sketch_data()
    )
    canvas = SketchCanvas(SketchEdit(feature), UnitSystem.MM)
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    canvas.show()
    canvas.scale, canvas.center = 4.0, (0.0, 0.0)
    yield canvas


# T1.4.3: tree prefix ----------------------------------------------------------------------


def _row(win: MainWindow, fid: str) -> QTreeWidgetItem:
    assert win.tree is not None
    item = win.tree.item_for(fid)
    assert item is not None
    return item


def test_tree_marks_an_under_defined_sketch(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = new_part(qtbot, window)
    sid = rectangle_sketch(qtbot, window, tab)  # no dimensions: under defined
    item = _row(window, sid)
    assert item.text(0) == UNDER_PREFIX + tab.session.document.feature(sid).name
    assert item.text(0).startswith("(-) ")
    # Renaming keeps the prefix out of the stored name.
    assert window.tree is not None
    item.setText(0, "(-) Outline")
    assert tab.session.document.feature(sid).name == "Outline"
    assert _row(window, sid).text(0) == "(-) Outline"
    # Planes and solid features never get a prefix.
    front = plane_id(tab, "Front Plane")
    assert _row(window, front).text(0) == "Front Plane"


def test_strip_prefix() -> None:
    assert strip_prefix("(-) Sketch 1") == "Sketch 1"
    assert strip_prefix("(+) Sketch 1") == "Sketch 1"
    assert strip_prefix("Sketch 1") == "Sketch 1"


# T1.5.2: discard restores the view ----------------------------------------------------------


def test_discard_restores_the_view_and_keep_does_not(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = new_part(qtbot, window)
    restored: list[object] = []
    view = tab.viewport
    view.camera_pose = lambda: "pose before"  # type: ignore[attr-defined]
    view.restore_pose = restored.append  # type: ignore[attr-defined]
    assert window.sketch_mode is not None
    window.sketch_mode.start(plane_id=plane_id(tab, "Front Plane"))
    assert window.sketch_mode.cancel()  # nothing changed: no question
    assert restored == ["pose before"]
    window.sketch_mode.start(plane_id=plane_id(tab, "Front Plane"))
    canvas_of(window)
    window.sketch_mode.accept()
    assert restored == ["pose before"]  # exit and keep leaves the view as it is


# T10.1: shortcut bar search -----------------------------------------------------------------


def test_shortcut_bar_search(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    new_part(qtbot, window)
    menu = window.commands.shortcut_bar("part", QPoint(10, 10))
    assert isinstance(menu, ShortcutBar)
    menu.show()
    context = [a.text() for a in menu.listed]
    assert "Extruded Boss" in context
    menu.search.setText("normal")
    assert [a.text() for a in menu.listed] == ["Normal To"]
    menu.search.setText("cut")
    names = [a.text() for a in menu.listed]
    assert "Extruded Cut" in names and "Revolved Cut" in names
    assert all("cut" in n.lower() for n in names)
    menu.search.setText("")
    assert [a.text() for a in menu.listed] == context
    # Arrows move, Enter runs.
    menu.search.setText("sketch")
    first = menu.activeAction()
    assert first is menu.listed[0]
    qtbot.keyClick(menu.search, Qt.Key.Key_Down)
    assert menu.activeAction() is menu.listed[1 % len(menu.listed)]
    ran: list[str] = []
    menu.activeAction().triggered.connect(lambda: ran.append("yes"))
    qtbot.keyClick(menu.search, Qt.Key.Key_Return)
    assert ran == ["yes"] and not menu.isVisible()


def test_shortcut_bar_escape_closes(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    menu = window.commands.shortcut_bar("sketch", QPoint(10, 10))
    assert isinstance(menu, ShortcutBar)
    menu.show()
    qtbot.keyClick(menu.search, Qt.Key.Key_Escape)
    assert not menu.isVisible()
    menu.search.setText("zzzz")
    assert menu.listed == [] and not menu.run_current()


# T10.2: gesture guide -----------------------------------------------------------------------


def test_gesture_guide_shows_after_a_short_drag(qtbot: QtBot, canvas: SketchCanvas) -> None:
    tracker = canvas.gesture_tracker
    assert isinstance(tracker, GestureTracker)
    tracker.source = lambda: ({"up": "Smart Dimension", "left": "Line"}, 4)
    start = QPoint(400, 300)
    qtbot.mousePress(canvas, Qt.MouseButton.RightButton, pos=start)
    qtbot.mouseMove(canvas, start + QPoint(0, -5))
    assert tracker.guide is None  # a plain right click shows nothing
    qtbot.mouseMove(canvas, start + QPoint(0, -20))
    guide = tracker.guide
    assert isinstance(guide, GestureGuide) and guide.isVisible()
    assert guide.active is None  # still inside the inner circle: releasing cancels
    qtbot.mouseMove(canvas, start + QPoint(0, -80))
    assert guide.active == "up"
    guide.repaint()
    gestures: list[tuple[float, float]] = []
    canvas.gesture.connect(lambda dx, dy: gestures.append((dx, dy)))
    qtbot.mouseRelease(canvas, Qt.MouseButton.RightButton, pos=start + QPoint(0, -80))
    assert tracker.guide is None
    assert gestures == [(0.0, -80.0)]


def test_release_inside_the_guide_runs_nothing(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = new_part(qtbot, window)
    assert window.sketch_mode is not None
    window.sketch_mode.start(plane_id=plane_id(tab, "Front Plane"))
    canvas = canvas_of(window)
    qtbot.wait(30)
    start = QPoint(canvas.width() // 2, canvas.height() // 2)
    qtbot.mousePress(canvas, Qt.MouseButton.RightButton, pos=start)
    qtbot.mouseMove(canvas, start + QPoint(-25, 0))
    guide = canvas.gesture_tracker.guide
    assert guide is not None and guide.labels["left"] == "Line"
    qtbot.mouseRelease(canvas, Qt.MouseButton.RightButton, pos=start + QPoint(-25, 0))
    assert canvas.tool_name == ""  # released inside: cancelled
    qtbot.mousePress(canvas, Qt.MouseButton.RightButton, pos=start)
    qtbot.mouseMove(canvas, start + QPoint(-90, 0))
    qtbot.mouseRelease(canvas, Qt.MouseButton.RightButton, pos=start + QPoint(-90, 0))
    assert canvas.tool_name == "line"


def test_gesture_labels_follow_the_settings(window: MainWindow) -> None:  # noqa: F811
    labels, sectors = window.commands.gesture_labels("part")
    assert sectors == 4 and labels["up"] == "Top"


# T1.4.1 and T2.4.1: colours and centre marks ------------------------------------------------


def test_selected_uses_the_theme_accent(canvas: SketchCanvas) -> None:
    lid = canvas.edit.sketch.add_line(0, 0, 10, 0)
    canvas.selection = [lid]
    assert canvas._color(lid, set()).name().upper() == LIGHT.accent
    canvas.palette_colors = DARK
    assert canvas._color(lid, set()).name().upper() == DARK.accent
    canvas.selection = []
    canvas.hover = lid
    assert canvas._color(lid, set()) == canvas.hover_color()
    canvas.repaint()


def test_circle_centres_are_plus_marks(canvas: SketchCanvas) -> None:
    sk = canvas.edit.sketch
    circle = sk.entities[sk.add_circle(10, 10, 5)]
    line = sk.entities[sk.add_line(0, 0, 20, 0)]
    assert isinstance(circle, Circle) and isinstance(line, Line)
    marks = canvas.point_marks()
    assert marks[circle.center] == "plus"
    assert marks[line.p1] == "dot" and marks[line.p2] == "dot"
    canvas.selection = [circle.id]
    canvas.repaint()  # paints the selected circle and its plus mark without error
