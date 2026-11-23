"""Explode Text from the sketch menu (TR121 item 1, D1713)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Line
from fdcad.core.sketch.text import SketchText
from fdcad.ui.sketch_tools.text_explode_job import explode_texts
from tests.ui.sketch_tools.p2_helpers import canvas_of


def test_explode_runs_off_the_ui_thread_and_is_one_undo_step(qtbot: QtBot) -> None:
    canvas, _panel = canvas_of(qtbot)
    canvas.edit.sketch.texts = [SketchText("t1", "L", height=10.0)]
    notes: list[str] = []
    canvas.status_message.connect(notes.append)
    job = explode_texts(canvas)
    assert job is not None
    qtbot.waitUntil(lambda: not canvas.edit.sketch.texts, timeout=10000)
    assert any(isinstance(e, Line) for e in canvas.edit.sketch.entities.values())
    assert "Turned 1 text items into curves" in notes[-1]
    canvas.edit.undo()
    assert len(canvas.edit.sketch.texts) == 1


def test_nothing_to_explode(qtbot: QtBot) -> None:
    canvas, _panel = canvas_of(qtbot)
    assert explode_texts(canvas) is None
