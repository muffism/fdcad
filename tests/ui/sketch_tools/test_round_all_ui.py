"""Round All Corners from the sketch (TR227, D834)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Arc, Sketch, sketch_to_data
from fdcad.core.units import UnitSystem
from fdcad.ui.sketch_tools import round_all as ra
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from tests.ui.sketch_tools.p2_helpers import edit_of


def test_round_all_with_one_override(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    s = Sketch()
    pts = [(0, 0), (40, 0), (40, 20), (0, 20)]
    ids = [s.add_line(*pts[i], *pts[(i + 1) % 4]) for i in range(4)]
    canvas = SketchCanvas(edit_of(s), UnitSystem.MM)
    qtbot.addWidget(canvas)
    canvas.selection = list(ids)
    assert sketch_to_data(s)

    def accept(dialog: ra.RoundAllDialog) -> bool:
        dialog.radius.setText("3")
        item = dialog.table.item(1, 1)
        assert item is not None
        item.setText("5mm")
        return True

    monkeypatch.setattr(ra, "run", accept)
    status = QLabel()
    made = ra.round_all_corners(canvas, status)
    assert len(made) == 4 and "4 corners rounded" in status.text()
    arcs = [e for e in canvas.edit.sketch.entities.values() if isinstance(e, Arc)]
    assert len(arcs) == 4
    canvas.edit.undo()
    assert not any(isinstance(e, Arc) for e in canvas.edit.sketch.entities.values())
