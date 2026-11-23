"""Sketch, Airfoil (TR257, D839)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.airfoil import code_points
from fdcad.core.sketch.model import Line, Spline
from fdcad.core.units import UnitSystem
from fdcad.ui.sketch_tools import airfoil_dialog as ad
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from tests.ui.sketch_tools.p2_helpers import edit_of


def _canvas(qtbot: QtBot) -> SketchCanvas:
    canvas = SketchCanvas(edit_of(), UnitSystem.MM)
    qtbot.addWidget(canvas)
    return canvas


def test_code_with_a_thick_closed_edge(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    canvas = _canvas(qtbot)

    def accept(dialog: ad.AirfoilDialog) -> bool:
        dialog.code.setText("4412")
        dialog.chord.setText("80")
        dialog.edge.setText("0.5")
        return True

    monkeypatch.setattr(ad, "run", accept)
    made = ad.insert_airfoil(canvas)
    sketch = canvas.edit.sketch
    assert [type(sketch.entities[i]) for i in made] == [Spline, Line]
    spline = sketch.entities[made[0]]
    assert isinstance(spline, Spline) and len(spline.points) == 17
    canvas.edit.undo()
    assert not any(isinstance(e, Spline) for e in canvas.edit.sketch.entities.values())


def test_point_file_and_a_bad_code(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    canvas = _canvas(qtbot)
    path = tmp_path / "foil.dat"
    path.write_text("".join(f"{x} {y}\n" for x, y in code_points("0012", 40)), encoding="utf-8")

    def accept(dialog: ad.AirfoilDialog) -> bool:
        assert dialog.load_file(str(path))
        return True

    monkeypatch.setattr(ad, "run", accept)
    assert len(ad.insert_airfoil(canvas)) == 1  # a sharp edge: Coincident, no line
    dialog = ad.AirfoilDialog(UnitSystem.MM)
    qtbot.addWidget(dialog)
    dialog.code.setText("99")
    assert dialog.points() is None and "four or five digit" in dialog.message.text()
