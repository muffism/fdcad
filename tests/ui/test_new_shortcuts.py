"""Phase 1 keys that TOOL_SPEC T12.4 and T12.5 listed as missing (gap report WP4).

Body commands (I, H for bodies, Shift+Tab, Ctrl+Shift+Tab) came with Phase 3 (D116 item 4, D410).
"""

from __future__ import annotations

import sys

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from fdcad.ui.input.commands import BY_ID, COMMANDS, ShortcutMap, normalize
from fdcad.ui.main_window.snap_popup import SnapOptions
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.preferences.dialog import PreferencesDialog
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.tree.feature_tree import FID_ROLE
from fdcad.ui.viewport.view_selector import ViewSelector, direction_at, project, view_of
from fdcad.ui.viewport.views import STANDARD_VIEWS
from tests.ui.test_input import (  # noqa: F401  (fixtures)
    _folders,
    _keys,
    _open_plate,
    settings,
    window,
)

NEW = {
    "view.selector": ["Ctrl+Space"],
    "view.hide_show": ["H"],
    "view.hide_reference": ["Ctrl+H"],
    "sketch.snap_options": ["F3"],
    "tree.flat": ["Ctrl+T"],
    "sketch.line_arc": [],
}


def test_new_commands_and_their_keys(window: MainWindow) -> None:  # noqa: F811
    m, mac = ShortcutMap(), ShortcutMap(mac=True)
    for cid, keys in NEW.items():
        assert m.keys(cid) == keys, cid
        assert cid in window.commands.actions, cid
        # The window uses the Mac keys on a Mac (SHORTCUTS.md 1.2).
        expected = mac.keys(cid) if sys.platform == "darwin" else keys
        assert _keys(window, cid) == expected, cid
    # Mac keeps the Control key where Cmd is a system shortcut (SHORTCUTS.md 1.2).
    assert mac.keys("view.selector") == ["Meta+Space"]
    assert mac.keys("view.hide_reference") == ["Meta+H"]


def test_body_commands_arrive_with_phase_3() -> None:
    keys = {normalize(k) for c in COMMANDS for k in c.keys}
    assert {"i", "shift+tab", "ctrl+shift+tab"} <= keys  # D116 item 4, D410


def test_new_commands_are_in_the_shortcut_editor(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    settings: Settings,  # noqa: F811
) -> None:
    dialog = PreferencesDialog(settings, window)
    qtbot.addWidget(dialog)
    editor = dialog.shortcuts
    for cid in NEW:
        editor.select(cid)
    # The line to arc switch has no key but can be given one.
    editor.select("sketch.line_arc")
    assert editor.assign_current("Alt+A") == {}
    dialog.accept()
    window.commands.reload()
    assert _keys(window, "sketch.line_arc") == ["Alt+A"]
    assert BY_ID["sketch.line_arc"].group == "Sketch"


# Ctrl+Space: view selector ------------------------------------------------------------------


def test_view_selector_cube_cells() -> None:
    assert direction_at(*project((0.0, 0.0, 1.0))) == (0.0, 0.0, 1.0)  # front face
    assert direction_at(*project((1.0, 0.0, 0.0))) == (1.0, 0.0, 0.0)  # right face
    assert direction_at(*project((0.0, 1.0, 0.0))) == (0.0, 1.0, 0.0)  # top face
    assert direction_at(*project((0.0, 0.8, 1.0))) == (0.0, 1.0, 1.0)  # front top edge
    assert direction_at(*project((0.9, 0.9, 1.0))) == (1.0, 1.0, 1.0)  # corner
    assert direction_at(*project((-0.9, -0.9, 1.0))) == (-1.0, -1.0, 1.0)
    assert direction_at(3.0, 3.0) is None
    assert view_of((0.0, 0.0, 1.0)) == STANDARD_VIEWS["front"]
    assert view_of((1.0, 1.0, 1.0)) == STANDARD_VIEWS["iso"]
    eye, up = view_of((0.0, 1.0, 1.0))
    assert eye == pytest.approx((0.0, 0.7071, 0.7071), abs=1e-3)
    assert abs(sum(a * b for a, b in zip(eye, up, strict=True))) < 1e-9


def test_view_selector_turns_the_view(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open_plate(qtbot, window, hole=False)
    looks: list[tuple[object, object]] = []
    tab.viewport.look = lambda eye, up: looks.append((eye, up))  # type: ignore[attr-defined]
    assert window.commands.trigger("view.selector")
    selector = window.view_selector
    assert isinstance(selector, ViewSelector) and selector.isVisible()
    cube = selector.cube
    pos = cube.to_widget((0.0, 0.0, 1.0)).toPoint()
    move = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(pos),
        cube.mapToGlobal(QPointF(pos)),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(cube, move)
    assert cube.hover == (0.0, 0.0, 1.0)
    cube.repaint()
    qtbot.mouseClick(cube, Qt.MouseButton.LeftButton, pos=pos)
    assert looks == [STANDARD_VIEWS["front"]]
    assert not selector.isVisible()
    window.show_view_selector().buttons["back"].click()  # type: ignore[attr-defined]
    assert looks[-1] == STANDARD_VIEWS["back"]


# H and Ctrl+H -------------------------------------------------------------------------------


def test_h_hides_and_shows_the_selected_sketch_or_plane(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = _open_plate(qtbot, window, hole=False)
    assert window.tree is not None
    doc = tab.session.document
    sketch = next(f.id for f in doc.features if f.type == "sketch")
    plane = next(f.id for f in doc.features if f.name == "Front Plane")
    assert not window.hide_or_show()  # nothing selected
    window.tree.select(sketch)
    assert sketch not in tab.visible_sketch_ids()  # used by the extrude: hidden
    count = tab.session.undo.count()
    assert window.commands.trigger("view.hide_show")
    assert sketch in tab.visible_sketch_ids()
    assert tab.session.undo.count() == count + 1  # one undoable command
    window.commands.trigger("view.hide_show")
    assert sketch not in tab.visible_sketch_ids()
    window.tree.select(plane)
    window.commands.trigger("view.hide_show")
    assert plane in tab.visible_plane_ids()
    # Ctrl+H hides every reference plane, and shows them again.
    assert window.commands.trigger("view.hide_reference")
    assert tab.visible_plane_ids() == []
    assert "hidden" in window.status.text()
    window.commands.trigger("view.hide_reference")
    assert plane in tab.visible_plane_ids()


# F3: snap options -----------------------------------------------------------------------------


def test_f3_snap_options_reach_the_open_sketch(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open_plate(qtbot, window, hole=False)
    front = next(f.id for f in tab.session.document.features if f.name == "Front Plane")
    assert window.sketch_mode is not None
    window.sketch_mode.start(plane_id=front)
    canvas = window.sketch_mode.canvas
    assert canvas is not None
    assert window.commands.trigger("sketch.snap_options")
    popup = window.snap_popup
    assert isinstance(popup, SnapOptions) and list(popup.boxes) == [
        "snapping",
        "model_snaps",
        "auto_relations",
    ]
    popup.boxes["snapping"].setChecked(False)
    assert not window.settings.sketch_options.snapping
    assert not canvas.options.snapping
    popup.boxes["auto_relations"].setChecked(False)
    assert not canvas.edit.auto_relations


# Ctrl+T: flat tree --------------------------------------------------------------------------


def test_ctrl_t_flat_tree(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open_plate(qtbot, window, hole=False)
    tree = window.tree
    assert tree is not None
    sketch = next(f.id for f in tab.session.document.features if f.type == "sketch")
    item = tree.item_for(sketch)
    assert item is not None and item.parent() is not None  # nested under its extrude
    assert window.commands.trigger("tree.flat")
    item = tree.item_for(sketch)
    assert item is not None and item.parent() is None
    assert not tree.rootIsDecorated()
    rows = [tree.topLevelItem(i).data(0, FID_ROLE) for i in range(tree.topLevelItemCount())]
    assert sketch in rows
    window.commands.trigger("tree.flat")
    item = tree.item_for(sketch)
    assert item is not None and item.parent() is not None


# T12.5: line to arc command -----------------------------------------------------------------


def test_line_arc_command_is_registered(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open_plate(qtbot, window, hole=False)
    front = next(f.id for f in tab.session.document.features if f.name == "Front Plane")
    assert window.sketch_mode is not None
    window.sketch_mode.start(plane_id=front)
    window.commands.trigger("sketch.line")
    assert window.commands.trigger("sketch.line_arc")
    assert "Draw a line or arc first" in window.status.text()  # no segment yet (T2.1.3)
    canvas = window.sketch_mode.canvas
    assert canvas is not None and canvas.tool_name == "line"


def test_snap_popup_only_sets_the_three_switches() -> None:
    """Regression (D483): the popup once wrote ``**{key: on}`` into the sketch options,
    which would give the over define choice a bool for a wrong key."""
    from fdcad.ui.main_window.snap_popup import SNAP_KEYS, with_snap
    from fdcad.ui.sketch_tools.options import OverDefine, SketchOptions

    start = SketchOptions()
    for key in SNAP_KEYS:
        changed = with_snap(start, key, False)
        assert getattr(changed, key) is False
        assert changed.over_define is OverDefine.ASK
        assert all(getattr(changed, k) for k in SNAP_KEYS if k != key)
    with pytest.raises(ValueError):
        with_snap(start, "over_define", True)


def test_sketch_mode_keeps_outline_and_model_jobs(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression (D484): the job list was typed for outline jobs only, but the model
    snap job is kept in it too. Both kinds stay alive until they report back."""
    from PySide6.QtCore import QRunnable

    from fdcad.ui.main_window import sketch_mode

    monkeypatch.setattr(sketch_mode, "_MODEL_CACHE", {})
    tab = _open_plate(qtbot, window, hole=False)
    front = next(f.id for f in tab.session.document.features if f.name == "Front Plane")
    mode = window.sketch_mode
    assert mode is not None
    mode.start(plane_id=front)
    kinds = {type(job).__name__ for job in mode._jobs}
    assert {"_OutlineJob", "_ModelJob"} <= kinds
    assert all(isinstance(job, QRunnable) for job in mode._jobs)
