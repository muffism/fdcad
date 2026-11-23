"""Sketch blocks from the sketch right click menu (TR34, D1717)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Circle
from fdcad.ui.main_window.context_menu import block_command, keys
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_context_menus import _sketch
from tests.ui.test_workflow import _folders, canvas_of, window  # noqa: F401  (fixtures)


def test_make_insert_update_and_explode(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    _sketch(qtbot, window)
    canvas = canvas_of(window)
    sk = canvas.edit.sketch
    bar = sk.add_line(0.0, 0.0, 20.0, 0.0)
    hole = sk.add_circle(20.0, 0.0, 2.0)
    canvas.edit.refresh()
    canvas.selection = [bar, hole]
    menus = window.context_menus
    assert "make_block" in keys(menus.build_sketch_menu(canvas))
    assert block_command(canvas, "make", [bar, hole])
    canvas.selection = [bar]
    found = keys(menus.build_sketch_menu(canvas))
    assert {"insert_block", "select_block", "update_block", "explode_block"} <= set(found)
    assert "make_block" not in found
    assert block_command(canvas, "insert", [bar])
    copy2 = list(sk.blocks[0]["copies"][1]["map"].values())
    assert set(canvas.selection) <= set(copy2) and canvas.selection
    c = sk.entities[hole]
    assert isinstance(c, Circle)
    c.radius = 4.0
    assert block_command(canvas, "update", [bar])
    holes = [
        sk.entities[e]
        for e in sk.blocks[0]["copies"][1]["map"].values()
        if isinstance(sk.entities.get(e), Circle)
    ]
    assert holes and all(h.radius == 4.0 for h in holes)  # type: ignore[union-attr]
    assert block_command(canvas, "select", [bar])
    assert set(canvas.selection) == {e for e in sk.blocks[0]["copies"][0]["map"].values()}
    assert block_command(canvas, "explode", [bar])
    assert len(sk.blocks[0]["copies"]) == 1
    canvas.edit.undo()
    assert len(canvas.edit.sketch.blocks[0]["copies"]) == 2
