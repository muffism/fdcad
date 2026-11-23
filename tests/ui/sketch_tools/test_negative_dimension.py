"""A negative horizontal or vertical distance flips the side (TR111 item 4, D1312)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from tests.ui.sketch_tools.p2_helpers import canvas_of, edit_of
from tests.ui.test_main_window import _folders, window

__all__ = ["_folders", "window"]


def test_negative_value_puts_the_point_on_the_other_side(qtbot: QtBot) -> None:
    sk = edit_of().sketch
    origin = next(iter(sk.entities))
    pid = sk.add_point(10.0, 4.0)
    dim = sk.dimension("horizontal_distance", [origin, pid], Param("10", 10.0))
    canvas, _panel = canvas_of(qtbot, sk)
    assert canvas.apply_dimension_text(dim.id, "-6") == ""
    target = canvas.edit.sketch.dimensions[0]
    assert target.param.expr == "6" and target.param.value == pytest.approx(6.0)
    assert canvas.edit.sketch.xy(pid)[0] == pytest.approx(-6.0, abs=1e-6)
    assert canvas.apply_dimension_text(dim.id, "0") == ""
    assert canvas.edit.sketch.xy(pid)[0] == pytest.approx(0.0, abs=1e-6)


def test_other_dimensions_still_refuse_zero_or_less(qtbot: QtBot) -> None:
    sk = edit_of().sketch
    lid = sk.add_line(0.0, 0.0, 10.0, 0.0)
    dim = sk.dimension("distance", [lid], Param("10", 10.0))
    canvas, _panel = canvas_of(qtbot, sk)
    assert canvas.apply_dimension_text(dim.id, "-3") != ""


def test_angle_to_horizontal_through_a_line_end(qtbot: QtBot, window) -> None:  # type: ignore[no-untyped-def]
    import math

    from fdcad.ui.main_window.context_menu import keys

    sk = edit_of().sketch
    lid = sk.add_line(0.0, 0.0, 10.0, 10.0)
    canvas, _panel = canvas_of(qtbot, sk)
    canvas.selection = [lid]
    menu = window.context_menus.build_sketch_menu(canvas)
    assert {"angle_horizontal", "angle_vertical"} <= set(keys(menu))
    next(a for a in menu.actions() if a.data() == "angle_horizontal").trigger()
    (dim,) = canvas.edit.sketch.dimensions
    assert dim.type == "angle"
    assert math.degrees(dim.param.value) in (pytest.approx(45.0), pytest.approx(135.0))
    assert canvas.edit.result is not None and canvas.edit.result.solved
