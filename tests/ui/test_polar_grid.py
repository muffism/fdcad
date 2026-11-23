"""Polar sketch grid (TR238, D1014)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.options import SketchOptions
from fdcad.ui.sketch_tools.polar_grid import polar_snap, rings_and_spokes
from tests.ui.test_workflow import _folders, window

__all__ = ["_folders", "window"]


def test_snap_to_ring_and_spoke() -> None:
    x, y = polar_snap(9.6, 3.0, 5.0, 15.0)
    assert math.hypot(x, y) == pytest.approx(10.0)
    assert math.degrees(math.atan2(y, x)) == pytest.approx(15.0)
    assert polar_snap(0.4, 0.3, 5.0, 15.0) == (0.0, 0.0)


def test_rings_cover_the_view_and_spokes_go_round() -> None:
    rings, spokes, far = rings_and_spokes([(-20, -20), (20, -20), (-20, 20), (20, 20)], 5.0, 30)
    assert rings[0] == 5.0 and rings[-1] <= far and far == pytest.approx(math.hypot(20, 20))
    assert len(spokes) == 12
    rings, _s, _f = rings_and_spokes([(100, 100), (120, 100), (100, 120), (120, 120)], 5.0, 30)
    assert rings[0] >= 140.0 - 5.0  # a view away from the origin skips the inner rings


def test_the_choice_is_kept(tmp_path: Path) -> None:
    settings = Settings(QSettings(str(tmp_path / "p.ini"), QSettings.Format.IniFormat))
    assert settings.sketch_options.grid_kind == "square"
    settings.sketch_options = SketchOptions(grid_kind="polar", polar_angle=30.0)
    again = settings.sketch_options
    assert again.grid_kind == "polar" and again.polar_angle == 30.0


def test_an_open_sketch_draws_and_snaps_to_the_polar_grid(qtbot: QtBot, window: MainWindow) -> None:
    import dataclasses

    from tests.ui.test_context_menus import _sketch
    from tests.ui.test_workflow import canvas_of

    _sketch(qtbot, window)
    canvas = canvas_of(window)
    canvas.options = dataclasses.replace(
        canvas.options, show_grid=True, grid_snap="always", grid_kind="polar", polar_angle=45.0
    )
    canvas.repaint()
    step = canvas._grid_step()
    found = canvas._stepped(Snap("free", step * 2.1, step * 1.9))
    assert math.hypot(found.x, found.y) == pytest.approx(3 * step)
    assert math.degrees(math.atan2(found.y, found.x)) == pytest.approx(45.0)
