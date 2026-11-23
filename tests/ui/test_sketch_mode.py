"""Sketch mode in the main window, driven by mouse clicks on the canvas."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtWidgets import QLineEdit, QToolButton
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.sketch.model import Line, sketch_from_data
from fdcad.core.sketch.solver import SketchStatus
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.session import DocumentSession
from fdcad.ui.sketch_tools.canvas import SketchCanvas


@pytest.fixture(autouse=True)
def _folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("FDCAD_DATA_DIR", str(tmp_path / "data"))


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> Iterator[MainWindow]:
    settings = Settings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))
    win = MainWindow(settings)
    win.resize(1200, 800)
    win.show()
    win.finish_setup()
    yield win
    if win.sketch_mode is not None and win.sketch_mode.is_open:
        win.sketch_mode._close()
    while win.tabs.count():
        tab = win.tabs.widget(0)
        assert isinstance(tab, DocumentTab)
        tab.session.cancel_rebuild()
        tab.session.wait()
        tab.autosaver.discard()
        win.tabs.removeTab(0)
    win.close()
    win.deleteLater()


def _new_part(qtbot: QtBot, win: MainWindow) -> DocumentTab:
    session = DocumentSession(new_document(), None, win)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = win.add_session(session)
    return tab


def _canvas(win: MainWindow) -> SketchCanvas:
    mode = win.sketch_mode
    assert mode is not None and mode.canvas is not None
    return mode.canvas


def _click(qtbot: QtBot, canvas: SketchCanvas, x: float, y: float) -> None:
    p = canvas.to_screen((x, y))
    pos = QPoint(round(p.x()), round(p.y()))
    qtbot.mouseMove(canvas, pos)
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=pos)


def _front_sketch(qtbot: QtBot, win: MainWindow) -> SketchCanvas:
    tab = win.current
    assert tab is not None and win.sketch_mode is not None
    front = next(f for f in tab.session.document.features if f.name == "Front Plane")
    win.sketch_mode.start(plane_id=front.id)
    canvas = _canvas(win)
    qtbot.wait(50)  # let the layout give the canvas its final size
    canvas.scale, canvas.center = 5.0, (20.0, 15.0)
    return canvas


def test_draw_rectangle_ok_and_extrude(qtbot: QtBot, window: MainWindow) -> None:
    tab = _new_part(qtbot, window)
    canvas = _front_sketch(qtbot, window)
    assert tab.stack.currentWidget() is canvas
    canvas.set_tool("corner_rectangle")
    _click(qtbot, canvas, 0, 0)
    _click(qtbot, canvas, 40, 30)
    lines = [e for e in canvas.edit.sketch.entities.values() if isinstance(e, Line)]
    assert len(lines) == 4
    assert window.sketch_mode is not None
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert window.sketch_mode.accept()
    assert tab.stack.currentWidget() is tab.view_host  # the grid holding the 3D view (TR16)
    sketch = tab.session.document.features[-1]
    assert sketch.type == "sketch" and sketch.name == "Sketch 1"
    assert tab.session.report is not None
    assert tab.session.report.results[sketch.id].state is FeatureState.OK

    assert window.tree is not None
    window.tree.select(sketch.id)
    window.insert_feature("extrude", "boss")
    assert window.panel is not None and window.panel.is_editing
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        window.panel.accept()
    report = tab.session.report
    assert report is not None and report.body is not None
    assert report.results[tab.session.document.features[-1].id].state is FeatureState.OK


def test_smart_dimension_and_full_definition(qtbot: QtBot, window: MainWindow) -> None:
    _new_part(qtbot, window)
    canvas = _front_sketch(qtbot, window)
    canvas.set_tool("line")
    _click(qtbot, canvas, 0, 0)
    _click(qtbot, canvas, 30, 0)
    canvas.set_tool("dimension")
    _click(qtbot, canvas, 15, 0)  # pick the line
    _click(qtbot, canvas, 15, -8)  # place the dimension below it
    editor = canvas.findChild(QLineEdit, "dimension_editor")
    assert editor is not None
    editor.setText("45")
    qtbot.keyClick(editor, Qt.Key.Key_Return)
    canvas._update_defined()
    sk = canvas.edit.sketch
    (dim,) = sk.dimensions
    assert dim.type == "distance" and dim.param.value == 45.0  # a line gives its length
    assert canvas.edit.status().state is SketchStatus.FULL
    line = next(e for e in sk.entities.values() if isinstance(e, Line))
    assert sk.xy(line.p2)[0] == pytest.approx(45.0)


def test_tool_groups_in_toolbar(qtbot: QtBot, window: MainWindow) -> None:
    """Group buttons hold their tools and remember the last used one."""
    from fdcad.ui.main_window.sketch_mode import TOOL_ORDER

    mode = window.sketch_mode
    assert mode is not None
    buttons = [w for w in mode.toolbar.findChildren(QToolButton)]
    # The rectangle group button holds the corner and center rectangle tools.
    rect = next(
        b
        for b in buttons
        if b.menu() is not None
        and {"Corner Rectangle", "Center Rectangle"} <= {a.text() for a in b.menu().actions()}
    )
    titles = [a.text() for a in rect.menu().actions()]
    assert "Corner Rectangle" in titles
    assert "Center Rectangle" in titles

    # Triggering any tool of a group, first or last, makes it the button's default action.
    _new_part(qtbot, window)
    _front_sketch(qtbot, window)
    center = mode.tool_actions["center_rectangle"]
    corner = mode.tool_actions["corner_rectangle"]
    center.trigger()
    assert rect.defaultAction() is center
    corner.trigger()
    assert rect.defaultAction() is corner

    # Single tools are plain buttons, without a dropdown. Circle has a dropdown since
    # Perimeter Circle joined it (D512).
    point = mode.tool_actions["point"]
    assert not any(b.menu() is not None and point in b.menu().actions() for b in buttons)

    # Every tool in TOOL_ORDER is still registered as an action.
    assert set(TOOL_ORDER) == set(mode.tool_actions)


def test_undo_inside_sketch_and_cancel(qtbot: QtBot, window: MainWindow) -> None:
    tab = _new_part(qtbot, window)
    count = len(tab.session.document.features)
    canvas = _front_sketch(qtbot, window)
    canvas.set_tool("circle")
    _click(qtbot, canvas, 10, 10)
    _click(qtbot, canvas, 15, 10)
    assert len(canvas.edit.sketch.curves()) == 1
    qtbot.keyClick(canvas, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert canvas.edit.sketch.curves() == []
    qtbot.keyClick(canvas, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
    assert len(canvas.edit.sketch.curves()) == 1
    assert window.sketch_mode is not None
    window.sketch_mode._close()  # cancel without the confirmation prompt
    assert len(tab.session.document.features) == count
    assert tab.session.undo.count() == 0


def test_edit_existing_sketch_and_drag(qtbot: QtBot, window: MainWindow) -> None:
    tab = _new_part(qtbot, window)
    canvas = _front_sketch(qtbot, window)
    canvas.set_tool("line")
    _click(qtbot, canvas, 0, 0)
    _click(qtbot, canvas, 20, 0)
    canvas.set_tool(None)
    assert window.sketch_mode is not None
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        window.sketch_mode.accept()
    fid = tab.session.document.features[-1].id
    window.edit_feature(fid)
    canvas = _canvas(window)
    qtbot.wait(50)  # let the layout give the canvas its final size
    canvas.scale, canvas.center = 5.0, (10.0, 0.0)
    start = canvas.to_screen((20.0, 0.0))
    end = canvas.to_screen((30.0, 6.0))
    qtbot.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start.toPoint())
    for k in range(1, 6):
        p = start + (end - start) * (k / 5)
        qtbot.mouseMove(canvas, p.toPoint())
    qtbot.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=end.toPoint())
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        window.sketch_mode.accept()
    sk = sketch_from_data(tab.session.document.feature(fid).data)
    line = next(e for e in sk.entities.values() if isinstance(e, Line))
    x, y = sk.xy(line.p2)
    assert x == pytest.approx(30.0, abs=0.3) and y == pytest.approx(0.0, abs=1e-6)
    assert tab.session.undo.count() == 2  # add sketch, edit sketch


def test_dynamic_mirror_and_curvature_commands(qtbot: QtBot, window: MainWindow) -> None:
    """D514: the Dynamic Mirror toggle and the Curvature Combs view item."""
    mode = window.sketch_mode
    assert mode is not None
    mode.mirror_action.trigger()  # no sketch open: stays off
    assert not mode.mirror_action.isChecked()
    _new_part(qtbot, window)
    canvas = _front_sketch(qtbot, window)
    axis = canvas.edit.sketch.add_line(0, -20, 0, 20, construction=True)
    canvas.changed()
    canvas.selection = [axis]
    mode.mirror_action.trigger()
    assert canvas.edit.mirror_axis == axis and mode.mirror_action.isChecked()
    assert "Dynamic mirror on." in window.sketch_status.text()
    canvas.set_tool("line")
    _click(qtbot, canvas, 5, 5)
    _click(qtbot, canvas, 15, 5)
    lines = [e for e in canvas.edit.sketch.entities.values() if isinstance(e, Line)]
    assert len(lines) == 3  # the axis, the line and its mirror copy
    mode.mirror_action.trigger()
    assert canvas.edit.mirror_axis is None
    assert "Dynamic mirror" not in window.sketch_status.text()
    mode.mirror_action.trigger()
    assert canvas.edit.mirror_axis == axis or canvas.mirror_pick
    mode.combs_action.trigger()
    assert canvas.show_curvature
    mode._close()
    assert not mode.mirror_action.isChecked()
    assert mode.combs_action.isChecked()  # view state stays for the session
