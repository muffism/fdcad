"""Sketch, Shapes (TR228, D927)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Arc, Line
from fdcad.core.units import UnitSystem
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.sketch_tools import shape_dialog as sd
from tests.ui.test_context_menus import _sketch, canvas_of
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_dialog_fields_follow_the_shape(qtbot: QtBot) -> None:
    dialog = sd.ShapeDialog(UnitSystem.MM)
    qtbot.addWidget(dialog)
    dialog.kind.setCurrentIndex(dialog.kind.findData("reuleaux"))
    assert not dialog.form.isRowVisible(dialog.boxes[1])
    assert dialog.pieces() is not None
    dialog.kind.setCurrentIndex(dialog.kind.findData("triangle_sss"))
    dialog.boxes[2].setText("100")
    assert dialog.pieces() is None and "cannot close" in dialog.message.text()


def test_insert_adds_one_undo_step(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _sketch(qtbot, window)
    canvas = canvas_of(window)
    monkeypatch.setattr(
        sd,
        "run",
        lambda dialog: (dialog.kind.setCurrentIndex(dialog.kind.findData("keyhole")), True)[1],
    )
    depth = canvas.edit.undo_depth
    made = sd.insert_shape(canvas)
    kinds = sorted(type(canvas.edit.sketch.entities[m]).__name__ for m in made)
    assert kinds == ["Arc", "Line", "Line", "Line"]
    assert canvas.edit.undo_depth == depth + 1
    assert any(isinstance(canvas.edit.sketch.entities[m], Arc) for m in made)
    assert any(isinstance(canvas.edit.sketch.entities[m], Line) for m in made)


def test_a_tube_adds_two_outlines(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TR367 (D991): a rectangular tube is its outside and inside outlines."""
    _sketch(qtbot, window)
    canvas = canvas_of(window)
    monkeypatch.setattr(
        sd,
        "run",
        lambda dialog: (dialog.kind.setCurrentIndex(dialog.kind.findData("rect_tube")), True)[1],
    )
    made = sd.insert_shape(canvas)
    assert len(made) == 8 and all(isinstance(canvas.edit.sketch.entities[m], Line) for m in made)


def test_i_beam_uses_four_values(qtbot: QtBot) -> None:
    dialog = sd.ShapeDialog(UnitSystem.MM)
    qtbot.addWidget(dialog)
    dialog.kind.setCurrentIndex(dialog.kind.findData("i_beam"))
    assert dialog.form.isRowVisible(dialog.boxes[3])
    loops = dialog.loops()
    assert loops is not None and len(loops) == 1 and len(loops[0]) == 12
