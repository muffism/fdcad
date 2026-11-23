"""Remaining Phase 1 spec gaps: animated turn to a sketch (W1.3), model cursor
coordinates (L6, W8), remembered dropdown tools (C6) and saved show and hide state."""

from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot

from fdcad.core.io import fdef
from fdcad.ui.command_tabs.tabs import SKETCH_GROUPS, build_panel, remember_groups
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.preferences.dialog import PreferencesDialog
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.session import DocumentSession
from fdcad.ui.viewport.views import TURN_MS, CameraPose, blend_pose, ease
from tests.ui.test_workflow import (  # noqa: F401  (fixtures)
    _folders,
    canvas_of,
    new_part,
    plane_id,
    rectangle_sketch,
    window,
)


def _settings(tmp_path: Path) -> Settings:
    return Settings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))


# W1.3: animated turn ----------------------------------------------------------------------


def test_animation_preference(qtbot: QtBot, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    assert settings.animations  # on by default
    dialog = PreferencesDialog(settings)
    qtbot.addWidget(dialog)
    # Shown as Reduce motion (U4.5, D664): unticked while animations are on.
    box = dialog.reduce_motion_box
    assert not box.isChecked() and box.toolTip()
    box.setChecked(True)
    dialog.accept()
    assert not settings.animations
    assert not _settings(tmp_path).animations  # stored


def test_ease_and_camera_blend() -> None:
    assert ease(0) == 0 and ease(1) == 1 and ease(0.5) == pytest.approx(0.5)
    assert ease(-1) == 0 and ease(2) == 1
    start = CameraPose((0, 0, 0), (0, 0, -1), (0, 1, 0), 100.0, 50.0)
    end = CameraPose((10, 0, 0), (0, -1, 0), (0, 0, -1), 200.0, 200.0)
    assert blend_pose(start, end, 0) == pytest.approx(start)  # type: ignore[arg-type]
    final = blend_pose(start, end, 1)
    assert final.direction == pytest.approx(end.direction, abs=1e-9)
    assert final.up == pytest.approx(end.up, abs=1e-9)
    half = blend_pose(start, end, 0.5)
    assert half.center == pytest.approx((5, 0, 0))
    assert half.distance == pytest.approx(150.0) and half.scale == pytest.approx(100.0)
    d = half.direction
    assert math.hypot(*d) == pytest.approx(1.0)
    assert d == pytest.approx((0, -math.sqrt(0.5), -math.sqrt(0.5)))
    assert sum(a * b for a, b in zip(half.up, d, strict=True)) == pytest.approx(0, abs=1e-9)
    # Opposite directions still turn smoothly (round the start's up vector).
    back = CameraPose((0, 0, 0), (0, 0, 1), (0, 1, 0), 100.0, 50.0)
    mid = blend_pose(start, back, 0.5)
    assert math.hypot(*mid.direction) == pytest.approx(1.0)
    assert abs(mid.direction[2]) < 1e-9


class _FakeTurn:
    """Records the animated turn the sketch asks the 3D view for."""

    def __init__(self) -> None:
        self.calls: list[tuple[tuple[float, float, float], int]] = []
        self.done: Callable[[], None] | None = None

    def __call__(
        self, normal: tuple[float, float, float], ms: int, done: Callable[[], None]
    ) -> None:
        self.calls.append((normal, ms))
        self.done = done


@pytest.mark.parametrize("animations", [True, False])
def test_sketch_opens_after_the_view_turns(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    animations: bool,
) -> None:
    tab = new_part(qtbot, window)
    window.settings.animations = animations
    turn = _FakeTurn()
    tab.viewport.animate_normal_to = turn  # type: ignore[attr-defined]
    mode = window.sketch_mode
    assert mode is not None
    mode.start(plane_id=plane_id(tab, "Top Plane"))
    assert mode.is_open
    [(normal, ms)] = turn.calls
    assert normal == pytest.approx((0, 1, 0))
    assert ms == (TURN_MS if animations else 0)
    canvas = canvas_of(window)
    assert tab.sketch_canvas is None  # the 3D view stays until the turn ends
    assert turn.done is not None
    turn.done()
    assert tab.sketch_canvas is canvas
    mode._close()


def test_turn_that_ends_after_the_sketch_closed_does_nothing(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = new_part(qtbot, window)
    turn = _FakeTurn()
    tab.viewport.animate_normal_to = turn  # type: ignore[attr-defined]
    mode = window.sketch_mode
    assert mode is not None
    mode.start(plane_id=plane_id(tab, "Front Plane"))
    mode._close()
    assert turn.done is not None
    turn.done()
    assert tab.sketch_canvas is None


# L6: cursor coordinates outside sketch mode ------------------------------------------------


def test_model_cursor_in_the_status_bar(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = new_part(qtbot, window)
    window.model_cursor(tab, (1.0, -2.5, 30.0))
    assert window.coords.text() == "X 1.00  Y -2.50  Z 30.00"
    window.model_cursor(tab, None)
    assert window.coords.text() == ""
    mode = window.sketch_mode
    assert mode is not None
    mode.start(plane_id=plane_id(tab, "Front Plane"))
    window.coords.setText("sketch")
    window.model_cursor(tab, (1.0, 2.0, 3.0))  # the sketch owns the label meanwhile
    assert window.coords.text() == "sketch"
    mode._close()


# C6: grouped tools across restarts --------------------------------------------------------


def test_dropdowns_remember_their_tool_across_restarts(qtbot: QtBot, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    owners: list[QWidget] = []  # keep the actions' owners alive

    def panel_with_actions() -> tuple[dict[str, QAction], object]:
        owner = QWidget()
        owners.append(owner)
        qtbot.addWidget(owner)
        ids = ["sketch.line", "sketch.centerline", "sketch.corner_rectangle"]
        ids += ["sketch.center_rectangle", "sketch.circle"]
        actions = {cid: QAction(cid, owner) for cid in ids}
        panel = build_panel("sketch", SKETCH_GROUPS, actions)
        qtbot.addWidget(panel)
        remember_groups(panel, actions, settings)
        return actions, panel

    actions, panel = panel_with_actions()
    actions["sketch.center_rectangle"].trigger()
    assert settings.tool_groups == {"sketch.corner_rectangle": "sketch.center_rectangle"}
    actions["sketch.circle"].trigger()  # not in a group: nothing stored
    assert list(settings.tool_groups) == ["sketch.corner_rectangle"]

    # A new start: the rectangle button shows the center rectangle again.
    actions, panel = panel_with_actions()
    rect = next(
        b
        for b in panel.buttons()  # type: ignore[attr-defined]
        if actions["sketch.corner_rectangle"] in b.group_actions
    )
    assert rect.defaultAction() is actions["sketch.center_rectangle"]
    line = next(
        b
        for b in panel.buttons()  # type: ignore[attr-defined]
        if actions["sketch.line"] in b.group_actions
    )
    assert line.defaultAction() is actions["sketch.line"]


def test_window_restores_the_sketch_tab_dropdowns(qtbot: QtBot, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.remember_tool("sketch.center_arc", "sketch.three_point_arc")
    win = MainWindow(settings)
    qtbot.addWidget(win)
    win.finish_setup()
    arc = win.commands.actions["sketch.three_point_arc"]
    panel = win.sketch_mode.toolbar  # type: ignore[union-attr]
    button = next(b for b in panel.buttons() if arc in b.group_actions)
    assert button.defaultAction() is arc


# Saved show and hide state (D114) ---------------------------------------------------------


def test_show_and_hide_are_undoable_and_saved(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
) -> None:
    tab: DocumentTab = new_part(qtbot, window)
    sid = rectangle_sketch(qtbot, window, tab)
    tree = window.tree
    assert tree is not None
    session = tab.session
    top = plane_id(tab, "Top Plane")

    # A plane: hidden by default, Show from the tree menu.
    menu = tree._context_menu(session, tree.item_for(top))  # type: ignore[arg-type]
    assert menu is not None
    show = next(a for a in menu.actions() if a.text() == "Show")
    count = session.undo.count()
    with qtbot.waitSignal(session.display_changed, timeout=2000):
        show.trigger()
    assert tab.visible_plane_ids() == [top]
    assert session.undo.count() == count + 1 and session.is_dirty

    # A finished sketch: shown by default; Hide it.
    with qtbot.waitSignal(session.display_changed, timeout=2000):
        tree.set_visible(sid, False)
    assert tab.visible_sketch_ids() == []
    assert session.document.appearance["hidden"] == [sid]
    assert session.document.appearance["shown"] == [top]

    # Undo brings the sketch back; redo hides it again.
    session.undo.undo()
    assert tab.visible_sketch_ids() == [sid]
    session.undo.redo()
    assert tab.visible_sketch_ids() == []

    # Saved in the file and back after opening it.
    path = tmp_path / "shown.fdef"
    session.save(path)
    again = fdef.load(path)
    assert again.appearance["hidden"] == [sid] and again.appearance["shown"] == [top]
    reopened = DocumentSession.open(path, window)
    with qtbot.waitSignal(reopened.rebuilt, timeout=20000):
        tab2 = window.add_session(reopened)
    assert tab2.visible_sketch_ids() == [] and tab2.visible_plane_ids() == [top]
