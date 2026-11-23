"""Weak automatic relations (TR362, D1310)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Relation, Sketch, sketch_from_data, sketch_to_data
from fdcad.ui.main_window.context_menu import keys
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.tools import LineTool
from tests.ui.sketch_tools.p2_helpers import canvas_of
from tests.ui.test_main_window import _folders, window

__all__ = ["_folders", "window"]


def _line(canvas) -> str:  # type: ignore[no-untyped-def]
    tool = LineTool(canvas.edit)
    tool.click(Snap("free", 0.0, 5.0))
    tool.click(Snap("free", 10.0, 5.05))
    canvas.changed()
    return tool.drawn[0]


def _rise(canvas, lid: str) -> None:  # type: ignore[no-untyped-def]
    """A vertical distance of 3 mm between the line's ends: Horizontal cannot hold."""
    from fdcad.core.document.model import Param

    line = canvas.edit.sketch.entities[lid]
    canvas.edit.sketch.dimension("vertical_distance", [line.p1, line.p2], Param("3", 3.0))


def test_automatic_relations_are_weak_and_saved() -> None:
    sk = Sketch()
    sk.relations.append(Relation("horizontal", ["e1"], weak=True))
    again = sketch_from_data(sketch_to_data(sk))
    assert again.relations[0].weak
    assert "weak" not in sketch_to_data(Sketch())["relations"]


def test_a_conflicting_relation_replaces_the_weak_one(qtbot: QtBot) -> None:
    canvas, _panel = canvas_of(qtbot)
    shown: list[str] = []
    canvas.status_message.connect(shown.append)
    lid = _line(canvas)
    (auto,) = [r for r in canvas.edit.sketch.relations if r.type == "horizontal"]
    assert auto.weak
    canvas.run(lambda: _rise(canvas, lid))
    types = [r.type for r in canvas.edit.sketch.relations]
    assert "horizontal" not in types
    assert canvas.edit.result is not None and not canvas.edit.result.conflicting
    assert any("Replaced the automatic relation" in s for s in shown)
    canvas.edit.undo()
    assert [r.type for r in canvas.edit.sketch.relations if r.type == "horizontal"]


def test_keep_relation_makes_it_strong(qtbot: QtBot, window: MainWindow) -> None:
    canvas, _panel = canvas_of(qtbot)
    lid = _line(canvas)
    index = next(i for i, r in enumerate(canvas.edit.sketch.relations) if r.type == "horizontal")
    canvas.selection = [f"r{index}"]
    menu = window.context_menus.build_sketch_menu(canvas)
    assert "keep_relation" in keys(menu)
    next(a for a in menu.actions() if a.data() == "keep_relation").trigger()
    assert not canvas.edit.sketch.relations[index].weak
    canvas.run(lambda: _rise(canvas, lid))
    assert canvas.edit.result is not None and canvas.edit.result.conflicting  # stays
