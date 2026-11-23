"""Pixels of the see-through colour are drawn clear (TR116 item 1, D977)."""

from __future__ import annotations

from PySide6.QtGui import QColor, QImage
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature
from fdcad.core.units import UnitSystem
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.edit import SketchEdit, new_sketch_data


def test_white_becomes_clear(qtbot: QtBot) -> None:
    feature = Feature(
        "f5", "sketch", "Sketch 1", refs={"plane": {"feature": "f2"}}, data=new_sketch_data()
    )
    canvas = SketchCanvas(SketchEdit(feature), UnitSystem.MM)
    qtbot.addWidget(canvas)
    image = QImage(4, 2, QImage.Format.Format_RGB32)
    image.fill(QColor("#FFFFFF"))
    image.setPixelColor(0, 0, QColor("#000000"))
    out = canvas.see_through("b1", image, "#FFFFFF", 0.05)
    assert out.pixelColor(1, 1).alpha() == 0
    assert out.pixelColor(0, 0).alpha() == 255
    assert canvas.see_through("b1", image, "#FFFFFF", 0.05) is out  # cached
