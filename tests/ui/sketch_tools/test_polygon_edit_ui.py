"""Edit Polygon from the sketch right click menu, and the Triangle preset (TR114, D1709)."""

from __future__ import annotations

import math

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Line, Sketch
from fdcad.core.sketch.ops.shapes import polygon
from fdcad.core.units import UnitSystem
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.sketch_tools import polygon_dialog as pd
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.tools import make_tool
from tests.ui.sketch_tools.p2_helpers import edit_of
from tests.ui.test_workflow import _folders, window  # noqa: F401  (fixtures)


def test_edit_polygon_is_one_undo_step(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    s = Sketch()
    made = polygon(s, (0.0, 0.0), (10.0, 0.0), 6)
    canvas = SketchCanvas(edit_of(s), UnitSystem.MM)
    qtbot.addWidget(canvas)

    def fill(dialog: pd.PolygonDialog) -> bool:
        assert dialog.sides.value() == 6 and dialog.inscribed.isChecked()
        assert dialog.size_box.text() == "20"
        dialog.sides.setValue(5)
        dialog.size_box.setText("30")
        dialog.angle.setText("90deg")
        return True

    monkeypatch.setattr(pd, "run", fill)
    assert pd.edit_polygon_values(canvas, made.curves[0])
    lines = [e for e in canvas.edit.sketch.entities.values() if isinstance(e, Line)]
    assert len(lines) == 5
    info = pd.polygon_of(canvas, lines[0].id)
    assert info is not None and info.radius == pytest.approx(15.0)
    assert info.angle == pytest.approx(math.pi / 2)
    canvas.edit.undo()
    lines = [e for e in canvas.edit.sketch.entities.values() if isinstance(e, Line)]
    assert len(lines) == 6


def test_menu_offers_edit_polygon_on_a_side(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    from fdcad.ui.main_window.context_menu import keys
    from tests.ui.test_context_menus import _sketch
    from tests.ui.test_workflow import canvas_of

    _sketch(qtbot, window)
    canvas = canvas_of(window)
    made = polygon(canvas.edit.sketch, (0.0, 0.0), (10.0, 0.0), 4)
    canvas.edit.refresh()
    canvas.selection = [made.curves[0]]
    menus = window.context_menus
    assert "edit_polygon" in keys(menus.build_sketch_menu(canvas))
    other = canvas.edit.sketch.add_line(50, 50, 60, 60)
    canvas.selection = [other]
    assert "edit_polygon" not in keys(menus.build_sketch_menu(canvas))


def test_triangle_preset_sets_three_sides() -> None:
    tool = make_tool("polygon", edit_of())
    tool.option_changed("triangle")  # type: ignore[attr-defined]
    assert tool.sides == 3  # type: ignore[attr-defined]
