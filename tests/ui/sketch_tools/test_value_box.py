"""Value box of Smart Dimension: position, stepping and Escape (T4.2.2 to T4.2.4, note 2)."""

from __future__ import annotations

import math
from collections.abc import Iterator

import pytest
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature
from fdcad.core.units import Kind, UnitSystem
from fdcad.ui.sketch_tools.canvas import SketchCanvas, beside
from fdcad.ui.sketch_tools.edit import SketchEdit, new_sketch_data
from fdcad.ui.sketch_tools.value_box import ValueBox, default_step, stepped_text


@pytest.fixture
def canvas(qtbot: QtBot) -> Iterator[SketchCanvas]:
    feature = Feature(
        "f5", "sketch", "Sketch 1", refs={"plane": {"feature": "f2"}}, data=new_sketch_data()
    )
    canvas = SketchCanvas(SketchEdit(feature), UnitSystem.MM)
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    canvas.show()
    canvas.scale, canvas.center = 4.0, (0.0, 0.0)
    yield canvas


def _click(qtbot: QtBot, canvas: SketchCanvas, x: float, y: float) -> None:
    p = canvas.to_screen((x, y))
    pos = QPoint(round(p.x()), round(p.y()))
    qtbot.mouseMove(canvas, pos)
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=pos)


def _dimension_far_line(qtbot: QtBot, canvas: SketchCanvas) -> None:
    """Draw a line well away from the canvas centre and dimension it."""
    canvas.set_tool("line")
    _click(qtbot, canvas, 40, 50)
    _click(qtbot, canvas, 70, 50)
    canvas.set_tool("dimension")
    _click(qtbot, canvas, 55, 50)
    _click(qtbot, canvas, 55, 44)


def _wheel(box: ValueBox, steps: int, mods: Qt.KeyboardModifier) -> None:
    pos = QPointF(5, 5)
    event = QWheelEvent(
        pos,
        box.mapToGlobal(pos),
        QPoint(0, 0),
        QPoint(0, 120 * steps),
        Qt.MouseButton.NoButton,
        mods,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(box, event)


def test_new_dimension_box_opens_beside_its_label(qtbot: QtBot, canvas: SketchCanvas) -> None:
    """Owner note 2: the box of a just placed dimension sits next to its text."""
    _dimension_far_line(qtbot, canvas)
    box = canvas.value_box
    assert box is not None and box.isVisible()
    (dim,) = canvas.edit.sketch.dimensions
    canvas.repaint()
    label = canvas._labels[dim.id]
    geo = QRectF(box.geometry())
    # Right beside the label, at the same height, not at the canvas centre.
    assert abs(geo.left() - label.right()) <= 8 or abs(geo.right() - label.left()) <= 8
    assert geo.top() <= label.center().y() <= geo.bottom()
    assert not geo.contains(QPointF(canvas.width() / 2, canvas.height() / 2))


def test_beside_flips_left_at_the_right_edge() -> None:
    assert beside(QRectF(100, 100, 40, 20), 60, 30, 800, 600) == (146, 95)
    x, _y = beside(QRectF(750, 100, 40, 20), 60, 30, 800, 600)
    assert x == 750 - 6 - 60


def test_escape_removes_a_new_dimension(qtbot: QtBot, canvas: SketchCanvas) -> None:
    _dimension_far_line(qtbot, canvas)
    assert canvas.value_box is not None and len(canvas.edit.sketch.dimensions) == 1
    qtbot.keyClick(canvas.value_box.edit, Qt.Key.Key_Escape)
    assert canvas.value_box is None
    assert canvas.edit.sketch.dimensions == []
    assert len(canvas.edit.sketch.entities) > 1  # the line stays


def test_escape_keeps_an_existing_dimension(qtbot: QtBot, canvas: SketchCanvas) -> None:
    _dimension_far_line(qtbot, canvas)
    box = canvas.value_box
    assert box is not None
    box.edit.setText("25")
    box.ok.click()
    (dim,) = canvas.edit.sketch.dimensions
    canvas.set_tool(None)
    canvas.repaint()
    qtbot.mouseDClick(
        canvas, Qt.MouseButton.LeftButton, pos=canvas._labels[dim.id].center().toPoint()
    )
    assert canvas.value_box is not None and canvas.value_box.text() == "25"
    canvas.value_box.edit.setText("40")
    qtbot.keyClick(canvas.value_box.edit, Qt.Key.Key_Escape)
    (dim,) = canvas.edit.sketch.dimensions
    assert dim.param.value == pytest.approx(25.0)


def test_cross_button_removes_a_new_dimension(qtbot: QtBot, canvas: SketchCanvas) -> None:
    _dimension_far_line(qtbot, canvas)
    assert canvas.value_box is not None
    canvas.value_box.cancel.click()
    assert canvas.edit.sketch.dimensions == []


def test_applied_new_dimension_survives_escape(qtbot: QtBot, canvas: SketchCanvas) -> None:
    _dimension_far_line(qtbot, canvas)
    box = canvas.value_box
    assert box is not None
    box.edit.setText("20")
    box.rebuild.click()
    qtbot.keyClick(box.edit, Qt.Key.Key_Escape)
    (dim,) = canvas.edit.sketch.dimensions
    assert dim.param.value == pytest.approx(20.0)


def test_stepped_text() -> None:
    assert stepped_text("10", 1, Kind.LENGTH, UnitSystem.MM) == "11"
    assert stepped_text("1in", 1, Kind.LENGTH, UnitSystem.MM) == "1.03937in"  # keeps its unit
    assert stepped_text("2", 0.1, Kind.LENGTH, UnitSystem.IN) == "2.1"
    assert stepped_text("45", -1, Kind.ANGLE, UnitSystem.MM) == "44"
    assert stepped_text("0.5", -1, Kind.LENGTH, UnitSystem.MM) is None  # never zero or less
    assert stepped_text("=width", 1, Kind.LENGTH, UnitSystem.MM) is None  # formulas stay
    assert stepped_text("2 *", 1, Kind.LENGTH, UnitSystem.MM) is None  # not a value
    assert default_step(Kind.LENGTH, UnitSystem.MM) == 1.0
    assert default_step(Kind.LENGTH, UnitSystem.IN) == 0.1
    assert default_step(Kind.ANGLE, UnitSystem.IN) == 1.0


def test_wheel_and_arrows_step_with_ctrl_and_alt(qtbot: QtBot) -> None:
    box = ValueBox("10", kind=Kind.LENGTH, units=UnitSystem.MM)
    qtbot.addWidget(box)
    box.show()
    assert box.step.isVisible() and box.step.value() == 1.0
    _wheel(box, 1, Qt.KeyboardModifier.NoModifier)
    assert box.text() == "11"
    _wheel(box, -1, Qt.KeyboardModifier.ControlModifier)
    assert box.text() == "1"
    _wheel(box, 2, Qt.KeyboardModifier.AltModifier)
    assert box.text() == "1.2"
    qtbot.keyClick(box.edit, Qt.Key.Key_Up)
    assert box.text() == "2.2"
    qtbot.keyClick(box.edit, Qt.Key.Key_Down, Qt.KeyboardModifier.ControlModifier)
    assert box.text() == "2.2"  # would go below zero: unchanged
    qtbot.keyClick(box.edit, Qt.Key.Key_Down, Qt.KeyboardModifier.AltModifier)
    assert box.text() == "2.1"
    box.step.setValue(5)
    qtbot.keyClick(box.edit, Qt.Key.Key_Up)
    assert box.text() == "7.1"


def test_angle_dimension_steps_in_degrees(qtbot: QtBot, canvas: SketchCanvas) -> None:
    sk = canvas.edit.sketch
    a = sk.add_line(0, 0, 30, 0)
    b = sk.add_line(0, 0, 20, 20)
    dim = canvas.edit.add_dimension("angle", [a, b], None)
    canvas.edit_dimension(dim.id)
    box = canvas.value_box
    assert box is not None and box.kind is Kind.ANGLE
    before = math.degrees(dim.param.value)
    qtbot.keyClick(box.edit, Qt.Key.Key_Up)
    assert float(box.text()) == pytest.approx(round(before + 1, 6))
    box.ok.click()
    (dim,) = canvas.edit.sketch.dimensions
    assert math.degrees(dim.param.value) == pytest.approx(before + 1)


def test_plain_box_does_not_step(qtbot: QtBot) -> None:
    box = ValueBox("10")
    qtbot.addWidget(box)
    box.show()
    assert not box.step.isVisible()
    qtbot.keyClick(box.edit, Qt.Key.Key_Up)
    assert box.text() == "10"


def test_stepping_keeps_a_typed_unit_and_says_why_it_cannot_step(qtbot: QtBot) -> None:
    """Audit D2 item 5 (D734): "5mm" stepped back as a bare number, and formulas or a
    step to zero did nothing silently."""
    from fdcad.core.units import Kind, UnitSystem
    from fdcad.ui.sketch_tools.value_box import (
        STEP_FORMULA,
        STEP_ZERO,
        step_refusal,
        stepped_text,
    )

    assert stepped_text("5mm", 1.0, Kind.LENGTH, UnitSystem.MM) == "6mm"
    assert stepped_text("5mm", 0.1, Kind.LENGTH, UnitSystem.IN) == "7.54mm"
    assert stepped_text("2.5 in", -0.5, Kind.LENGTH, UnitSystem.IN) == "2in"
    assert stepped_text("=W*2", 1.0, Kind.LENGTH, UnitSystem.MM) is None
    assert step_refusal("=W*2", Kind.LENGTH) == STEP_FORMULA
    assert stepped_text("1", -1.0, Kind.LENGTH, UnitSystem.MM) is None
    assert step_refusal("1", Kind.LENGTH) == STEP_ZERO
