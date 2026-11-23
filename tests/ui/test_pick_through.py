"""Pick through see through bodies and the before and after slider (TR224, D1610)."""

from __future__ import annotations

import sys
from collections.abc import Iterator

import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from fdcad.ui.viewport.blend import BlendSlider


@pytest.fixture
def viewport(qapp: QApplication) -> Iterator[object]:
    if sys.platform.startswith("linux"):
        pytest.skip("the 3D viewer needs a display on Linux")
    from fdcad.ui.viewport.widget import ViewportWidget

    view = ViewportWidget()
    yield view
    view.deleteLater()


def test_see_through_subshapes_and_shift(viewport: object) -> None:
    box = BRepPrimAPI_MakeBox(1, 1, 1).Shape()
    face = TopExp_Explorer(box, TopAbs_FACE).Current()
    other = TopExp_Explorer(BRepPrimAPI_MakeBox(2, 2, 2).Shape(), TopAbs_FACE).Current()
    v = viewport
    assert v._through_pick(Qt.KeyboardModifier.NoModifier) is None  # type: ignore[attr-defined]
    v.set_see_through([box])  # type: ignore[attr-defined]
    found = v._see_through_subshapes()  # type: ignore[attr-defined]
    assert found.Contains(face) and not found.Contains(other)
    assert v._through_pick(Qt.KeyboardModifier.ShiftModifier) is None  # type: ignore[attr-defined]
    v.transparent = True  # type: ignore[attr-defined]
    assert v._through_pick(Qt.KeyboardModifier.NoModifier) is None  # type: ignore[attr-defined]


def test_blend_does_nothing_without_a_preview(viewport: object) -> None:
    viewport.set_preview_blend(0.5)  # type: ignore[attr-defined]


def test_slider_reports_fractions(qtbot: QtBot) -> None:
    from PySide6.QtWidgets import QWidget

    view = QWidget()
    qtbot.addWidget(view)
    seen: list[float] = []
    slider = BlendSlider(view, seen.append)
    slider.slider.setValue(40)
    assert seen == [0.4]
    slider.slider.setValue(70)
    slider.open()
    assert slider.slider.value() == 0 and seen == [0.4, 0.7]  # open resets silently
