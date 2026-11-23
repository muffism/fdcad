"""Snap to grid, length and angle steps, and the snap filter (TR102, D860)."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest
from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Sketch
from fdcad.core.units import UnitSystem
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.inference import Snap
from tests.ui.sketch_tools.p2_helpers import edit_of


def _canvas(qtbot: QtBot) -> SketchCanvas:
    s = Sketch()
    s.add_line(0, 0, 10, 0)
    canvas = SketchCanvas(edit_of(s), UnitSystem.MM)
    qtbot.addWidget(canvas)
    return canvas


def test_grid_snap_and_filter(qtbot: QtBot) -> None:
    canvas = _canvas(qtbot)
    canvas.grid_spacing, canvas.grid_minor = 10.0, 2
    canvas.scale = 10.0
    canvas.options = replace(canvas.options, grid_snap="always")
    got = canvas._stepped(Snap("free", 7.4, 2.4))
    assert (got.x, got.y) == pytest.approx((5.0, 5.0)) or (got.x, got.y) == pytest.approx(
        (5.0, 0.0)
    )
    canvas.snap_only = "midpoint"
    assert canvas._stepped(Snap("point", 10, 0)).kind == "free"  # not the asked kind
    assert canvas._stepped(Snap("midpoint", 5, 0)).kind == "midpoint"


def test_alt_steps_length_and_angle(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtWidgets import QApplication

    canvas = _canvas(qtbot)
    canvas.set_tool("line")
    assert canvas.tool is not None
    canvas.tool.clicks = [Snap("free", 0.0, 0.0)]
    canvas.options = replace(canvas.options, length_step=5.0, angle_step=45.0)
    monkeypatch.setattr(
        QApplication, "keyboardModifiers", staticmethod(lambda: Qt.KeyboardModifier.AltModifier)
    )
    got = canvas._stepped(Snap("free", 7.0, 6.0))
    assert math.hypot(got.x, got.y) == pytest.approx(10.0)
    assert math.degrees(math.atan2(got.y, got.x)) == pytest.approx(45.0)
