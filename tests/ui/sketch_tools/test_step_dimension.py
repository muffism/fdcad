"""Step a dimension through a range (TR236, D922)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Line
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.sketch_tools import step_dimension as sd
from tests.ui.test_context_menus import _sketch, canvas_of, draw_rectangle
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_values() -> None:
    assert sd.values(10.0, 20.0, 3) == [10.0, 15.0, 20.0]
    assert sd.values(5.0, 1.0, 1) == [5.0]


def test_steps_then_puts_the_sketch_back(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _sketch(qtbot, window)
    canvas = canvas_of(window)
    draw_rectangle(qtbot, window)
    line = next(e.id for e in canvas.edit.sketch.entities.values() if isinstance(e, Line))
    canvas.run(lambda: canvas.edit.add_dimension("distance", [line], None))
    dim = canvas.edit.sketch.dimensions[-1]
    did, typed = dim.id, dim.param.value
    depth = canvas.edit.undo_depth
    monkeypatch.setattr(sd, "run", lambda dialog: True)
    monkeypatch.setattr(sd, "STEP_MS", 1)
    stepper = sd.step_dimension(canvas, did)
    assert stepper is not None and len(stepper.steps) == 10
    # The first step is half the value as the box shows it: four figures (D2708).
    assert canvas._dimension(did).param.value == pytest.approx(float(f"{typed * 0.5:.4g}"))
    stepper.timer.stop()
    while stepper.step():
        pass
    assert canvas._dimension(did).param.value == pytest.approx(typed)
    assert canvas.edit.undo_depth == depth
    assert stepper.failed == []
