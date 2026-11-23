"""Warn when a sketch jumps to another solution; Keep This Side (TR338, D1302)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Line, Sketch
from fdcad.ui.main_window.context_menu import keys
from fdcad.ui.main_window.window import MainWindow
from tests.ui.sketch_tools.p2_helpers import canvas_of, edit_of
from tests.ui.test_main_window import _folders, window

__all__ = ["_folders", "window"]


def _arm() -> tuple[Sketch, str, str, str]:
    """A fixed base line and a second line of fixed length hinged at its end; a
    distance from the base start to the tip sets the angle up to a mirror image."""
    sk = edit_of().sketch
    a = sk.add_line(0.0, 0.0, 10.0, 0.0)
    b = sk.add_line(10.0, 0.0, 13.0, 4.0)
    la, lb = sk.entities[a], sk.entities[b]
    assert isinstance(la, Line) and isinstance(lb, Line)
    sk.relate("coincident", la.p2, lb.p1)
    sk.relate("fixed", la.p1)
    sk.relate("fixed", la.p2)
    sk.dimension("distance", [lb.p1, lb.p2], Param("5", 5.0))
    return sk, a, b, lb.p2


def _flip_tip(canvas, tip: str) -> None:  # type: ignore[no-untyped-def]
    """Add a vertical distance whose stored side puts the tip below the base line:
    the solver moves the tip across, to the mirror image of the corner."""

    def change() -> None:
        sk = canvas.edit.sketch
        base = next(e for e in sk.entities.values() if isinstance(e, Line))
        dim = sk.dimension("vertical_distance", [base.p1, tip], Param("4", 4.0))
        dim.side = -1

    canvas.run(change)


def test_a_jump_warns_and_keep_this_side_locks_it(qtbot: QtBot) -> None:
    sk, a, b, tip = _arm()
    canvas, _panel = canvas_of(qtbot, sk)
    shown: list[str] = []
    canvas.status_message.connect(shown.append)
    _flip_tip(canvas, tip)
    key = f"corner:{a}:{b}"
    assert key in canvas.edit.jump_sides
    assert any("jumped to another solution" in s for s in shown)
    before = canvas.edit.jump_sides[key]
    assert canvas.edit.keep_this_side()
    assert canvas.edit.sketch.keep_sides == {key: before}
    assert canvas.edit.sketch.point(tip).y > 0  # the jump was undone
    shown.clear()
    _flip_tip(canvas, tip)  # a locked item may not flip: the change is undone
    assert canvas.edit.sketch.point(tip).y > 0
    assert canvas.edit.sketch.dimensions[-1].type != "vertical_distance"
    assert any("Keep This Side holds" in s for s in shown)
    assert canvas.edit.remove_side_locks()
    _flip_tip(canvas, tip)
    assert canvas.edit.sketch.point(tip).y < 0


def test_menu_offers_keep_side_after_a_jump(qtbot: QtBot, window: MainWindow) -> None:
    sk, _a, _b, tip = _arm()
    canvas, _panel = canvas_of(qtbot, sk)
    menu = window.context_menus.build_sketch_menu(canvas)
    assert "keep_side" not in keys(menu)
    _flip_tip(canvas, tip)
    menu = window.context_menus.build_sketch_menu(canvas)
    assert "keep_side" in keys(menu)
    next(a for a in menu.actions() if a.data() == "keep_side").trigger()
    assert canvas.edit.sketch.keep_sides
    menu = window.context_menus.build_sketch_menu(canvas)
    assert "remove_side_locks" in keys(menu)
