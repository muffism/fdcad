"""The DXF options dialog starts on inches for an imperial file with no unit (audit D
item 18, D742)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.sketch.dxf_import import DxfDrawing
from fdcad.ui.sketch_tools.dxf_dialog import DxfOptions


def test_an_imperial_file_starts_on_inches(qtbot: QtBot) -> None:
    dialog = DxfOptions(DxfDrawing(units=0, measurement=0))
    qtbot.addWidget(dialog)
    assert dialog.units.currentData() == 1
    metric = DxfOptions(DxfDrawing(units=0, measurement=1))
    qtbot.addWidget(metric)
    assert metric.units.currentData() == 4
