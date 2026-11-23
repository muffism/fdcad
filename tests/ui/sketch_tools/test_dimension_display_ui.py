"""Dimension, Display (TR46, D901)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Sketch
from fdcad.core.units import UnitSystem
from fdcad.ui.sketch_tools import dimension_display_dialog as dd
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from tests.ui.sketch_tools.p2_helpers import edit_of


def test_tolerance_shows_in_the_label_and_undoes(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    s = Sketch()
    lid = s.add_line(0, 0, 10, 0)
    dim = s.dimension("distance", [lid], Param("10", 10.0))
    canvas = SketchCanvas(edit_of(s), UnitSystem.MM)
    qtbot.addWidget(canvas)

    def fill(dialog: dd.DimensionDisplayDialog) -> bool:
        dialog.tolerance.setCurrentIndex(dialog.tolerance.findData("symmetric"))
        dialog.plus.setText("0.05")
        return True

    monkeypatch.setattr(dd, "run", fill)
    assert dd.edit_display(canvas, dim.id)
    found = canvas._dimension(dim.id)
    assert found is not None and canvas._dimension_text(found) == "10.00 ±0.05"
    canvas.edit.undo()
    found = canvas._dimension(dim.id)
    assert found is not None and found.display is None


def test_hide_extension_and_dimension_lines(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    """TR111 item 3 (D1708)."""
    from fdcad.ui.sketch_tools.canvas import shown_segments

    s = Sketch()
    lid = s.add_line(0, 0, 10, 0)
    dim = s.dimension("distance", [lid], Param("10", 10.0))
    canvas = SketchCanvas(edit_of(s), UnitSystem.MM)
    qtbot.addWidget(canvas)

    def fill(dialog: dd.DimensionDisplayDialog) -> bool:
        assert dialog.hide_extension.isEnabled()
        dialog.hide_extension.setChecked(True)
        return True

    monkeypatch.setattr(dd, "run", fill)
    assert dd.edit_display(canvas, dim.id)
    found = canvas._dimension(dim.id)
    assert found is not None and found.display == {"hide_extension": True}
    _anchor, segments = canvas._dimension_geometry(found)
    assert len(segments) == 3
    assert shown_segments(found, segments) == segments[2:]
    found.display = {"hide_line": True}
    assert shown_segments(found, segments) == segments[:2]
    canvas.grab()


def test_hide_options_are_off_for_round_dimensions(qtbot: QtBot) -> None:
    s = Sketch()
    cid = s.add_circle(0, 0, 5)
    dim = s.dimension("diameter", [cid], Param("10", 10.0))
    dialog = dd.DimensionDisplayDialog(dim, UnitSystem.MM)
    qtbot.addWidget(dialog)
    assert not dialog.hide_extension.isEnabled() and not dialog.hide_line.isEnabled()
