"""Leaving a sketch by double click or Esc (TR120, D941)."""

from __future__ import annotations

import dataclasses

from PySide6.QtCore import QPoint, Qt
from pytestqt.qtbot import QtBot

from tests.ui.sketch_tools.p2_helpers import canvas_of


def test_switches_off_keep_the_sketch_open(qtbot: QtBot) -> None:
    canvas, _ = canvas_of(qtbot)
    asked: list[bool] = []
    canvas.exit_requested.connect(lambda: asked.append(True))
    qtbot.mouseDClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(700, 80))
    qtbot.keyClick(canvas, Qt.Key.Key_Escape)
    assert asked == []


def test_double_click_on_nothing_exits(qtbot: QtBot) -> None:
    canvas, _ = canvas_of(qtbot)
    canvas.options = dataclasses.replace(canvas.options, double_click_exit=True)
    asked: list[bool] = []
    canvas.exit_requested.connect(lambda: asked.append(True))
    qtbot.mouseDClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(700, 80))
    assert asked == [True]


def test_escape_clears_the_picks_first(qtbot: QtBot) -> None:
    canvas, _ = canvas_of(qtbot)
    canvas.options = dataclasses.replace(canvas.options, escape_exit=True)
    line = canvas.edit.sketch.add_line(0, 0, 10, 0)
    canvas.selection = [line]
    asked: list[bool] = []
    canvas.exit_requested.connect(lambda: asked.append(True))
    qtbot.keyClick(canvas, Qt.Key.Key_Escape)
    assert canvas.selection == [] and asked == []
    qtbot.keyClick(canvas, Qt.Key.Key_Escape)
    assert asked == [True]
