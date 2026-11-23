"""Owner notes 2026-10-30 (D434): steadier snaps, the grid off by default, light theme."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QPointF, QSettings
from pytestqt.qtbot import QtBot

from fdcad.ui.preferences.settings import Settings, Theme
from fdcad.ui.sketch_tools.canvas import PICK_PX, STICKY, SketchCanvas
from fdcad.ui.sketch_tools.options import SketchOptions
from fdcad.ui.themes.theme import LIGHT
from tests.ui.test_sketch_preferences import _click, _move
from tests.ui.test_sketch_preferences import canvas as canvas_fixture
from tests.ui.test_workflow import _folders  # noqa: F401  (fixture)

canvas = canvas_fixture


def test_point_snap_holds_while_the_cursor_drifts(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.edit.sketch.add_point(10, 10)
    canvas.set_tool("point")
    tol = PICK_PX / canvas.scale
    _move(canvas, 10.2, 10)
    assert canvas.snap is not None and canvas.snap.kind == "point"
    # Just outside the pick distance but inside the hold distance: still on the point.
    _move(canvas, 10 + tol * 1.3, 10)
    assert canvas.snap is not None and canvas.snap.kind == "point"
    assert canvas.snap.xy == (10.0, 10.0)
    # Well away: the hold lets go.
    _move(canvas, 10 + tol * (STICKY + 0.5), 10)
    assert canvas.snap is not None and canvas.snap.kind != "point"


def test_no_hold_from_a_fresh_approach(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.edit.sketch.add_point(10, 10)
    canvas.set_tool("point")
    tol = PICK_PX / canvas.scale
    _move(canvas, 10 + tol * 1.3, 10)  # never came within the pick distance
    assert canvas.snap is not None and canvas.snap.kind != "point"


def test_ctrl_and_snapping_off_drop_the_hold(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.edit.sketch.add_point(10, 10)
    canvas.set_tool("point")
    _move(canvas, 10.2, 10)
    _move(canvas, 10.2, 10, ctrl=True)
    assert canvas.snap is not None and canvas.snap.kind == "free"
    _move(canvas, 10.2, 10)
    canvas.set_options(replace(SketchOptions(), snapping=False))
    _move(canvas, 10.3, 10)
    assert canvas.snap is not None and canvas.snap.kind == "free"


def test_pick_prefers_an_end_point_over_its_line(qtbot: QtBot, canvas: SketchCanvas) -> None:
    sk = canvas.edit.sketch
    lid = sk.add_line(0, 0, 40, 0)
    line = sk.entities[lid]
    tol = PICK_PX / canvas.scale
    # On the line, most of a pick distance from its end: the end point is picked.
    at = canvas.to_screen((40 - tol * 0.8, 0))
    assert canvas.pick(QPointF(at)) == line.p2  # type: ignore[attr-defined]
    # Far from both ends: the line.
    assert canvas.pick(QPointF(canvas.to_screen((20, 0)))) == lid


def test_grid_is_off_by_default(qtbot: QtBot, canvas: SketchCanvas) -> None:
    assert not SketchOptions().show_grid
    calls: list[int] = []
    canvas._paint_grid = lambda painter: calls.append(1)  # type: ignore[method-assign]
    canvas.repaint()
    assert calls == []
    canvas.set_options(replace(SketchOptions(), show_grid=True))
    canvas.repaint()
    assert calls


def test_light_grey_view_and_light_theme_by_default(tmp_path: Path) -> None:
    settings = Settings(QSettings(str(tmp_path / "p.ini"), QSettings.Format.IniFormat))
    assert settings.theme is Theme.LIGHT
    for colour in (LIGHT.viewport_top, LIGHT.viewport_bottom):
        r, g, b = (int(colour[i : i + 2], 16) for i in (1, 3, 5))
        assert max(r, g, b) - min(r, g, b) <= 12  # grey, not tinted
    assert LIGHT.viewport_top > LIGHT.viewport_bottom  # lighter at the top


def test_a_click_drops_the_hold(qtbot: QtBot, canvas: SketchCanvas) -> None:
    """The next point of a tool is not pulled back onto the point just placed."""
    canvas.edit.sketch.add_point(10, 10)
    canvas.set_tool("circle")
    tol = PICK_PX / canvas.scale
    _click(qtbot, canvas, 10.2, 10)  # centre on the point
    _move(canvas, 10 + tol * 1.3, 10)
    assert canvas.snap is not None and canvas.snap.xy != (10.0, 10.0)


def test_left_tabs_are_icons_with_names_as_tooltips(qtbot: QtBot) -> None:
    from PySide6.QtWidgets import QLabel

    from fdcad.ui import strings
    from fdcad.ui.main_window.left_tabs import LeftTabs

    tabs = LeftTabs()
    qtbot.addWidget(tabs)
    errors = QLabel()
    for widget, name in ((QLabel(), strings.TAB_TREE), (errors, strings.TAB_ERRORS)):
        tabs.addTab(widget, name)
    assert [tabs.tabText(i) for i in range(2)] == ["", ""]
    assert [tabs.name(i) for i in range(2)] == [strings.TAB_TREE, strings.TAB_ERRORS]
    assert not tabs.tabIcon(0).isNull()
    tabs.set_count(errors, strings.TAB_ERRORS, 3)
    assert tabs.tabText(1) == "3" and tabs.tabToolTip(1) == "Errors (3)"
    tabs.set_count(errors, strings.TAB_ERRORS, 0)
    assert tabs.tabText(1) == "" and tabs.tabToolTip(1) == strings.TAB_ERRORS
