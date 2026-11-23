"""Sketch, Gear (TR161, D866)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Spline
from fdcad.core.units import UnitSystem
from fdcad.ui.sketch_tools import gear_dialog as gd
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from tests.ui.sketch_tools.p2_helpers import edit_of


def test_spur_gear_and_sprocket(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    canvas = SketchCanvas(edit_of(), UnitSystem.MM)
    qtbot.addWidget(canvas)

    def spur(dialog: gd.GearDialog) -> bool:
        dialog.size_box.setValue(2.0)
        dialog.teeth.setValue(12)
        return True

    monkeypatch.setattr(gd, "run", spur)
    made = gd.insert_gear(canvas)
    assert len(made) == 12 * 6
    assert any(isinstance(canvas.edit.sketch.entities[e], Spline) for e in made)
    canvas.edit.undo()
    assert not canvas.edit.sketch.entities or not any(
        isinstance(e, Spline) for e in canvas.edit.sketch.entities.values()
    )

    def sprocket(dialog: gd.GearDialog) -> bool:
        dialog.kind.setCurrentIndex(dialog.kind.findData("sprocket"))
        dialog.teeth.setValue(10)
        return True

    monkeypatch.setattr(gd, "run", sprocket)
    assert len(gd.insert_gear(canvas)) == 10 * 3


def test_timing_pulley_and_root_fillet(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    """TR348 (D2007)."""
    canvas = SketchCanvas(edit_of(), UnitSystem.MM)
    qtbot.addWidget(canvas)

    def pulley(dialog: gd.GearDialog) -> bool:
        dialog.kind.setCurrentIndex(dialog.kind.findData("pulley"))
        assert dialog.belt.isEnabled() and not dialog.size_box.isEnabled()
        dialog.belt.setCurrentIndex(dialog.belt.findData("GT2 (2 mm)"))
        dialog.teeth.setValue(20)
        return True

    monkeypatch.setattr(gd, "run", pulley)
    assert len(gd.insert_gear(canvas)) == 20 * 2

    def filleted(dialog: gd.GearDialog) -> bool:
        dialog.size_box.setValue(2.0)
        dialog.teeth.setValue(12)
        dialog.fillet_radius.setValue(0.5)
        return True

    monkeypatch.setattr(gd, "run", filleted)
    made = gd.insert_gear(canvas)
    assert len(made) > 12 * 6  # roots are a line, two fillet arcs and the root arc
