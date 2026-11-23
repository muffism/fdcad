"""Save and autosave while a sketch is open keep the sketch (bug hunt round 10a, D590)."""

from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from fdcad.core.io import fdef
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from tests.ui.test_workflow import (  # noqa: F401  (fixtures)
    _folders,
    click,
    new_part,
    plane_id,
    ready_canvas,
    window,
)


def _sketch_with_a_rectangle(qtbot: QtBot, win: MainWindow) -> DocumentTab:
    tab = new_part(qtbot, win)
    assert win.tree is not None
    win.tree.select(plane_id(tab, "Top Plane"))
    win.commands.trigger("sketch.sketch")
    canvas = ready_canvas(qtbot, win, (10.0, 10.0))
    canvas.set_tool("corner_rectangle")
    click(qtbot, canvas, 0, 0)
    click(qtbot, canvas, 20, 15)
    canvas.set_tool(None)
    return tab


def _sketches(path: Path) -> list[str]:
    return [f.name for f in fdef.load(path).features if f.type == "sketch"]


def test_save_with_a_new_sketch_open_keeps_the_sketch(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
) -> None:
    tab = _sketch_with_a_rectangle(qtbot, window)
    target = tmp_path / "part.fdprt"
    tab.session.path = target
    assert window.save()
    assert window.sketch_mode is not None and not window.sketch_mode.is_open
    assert _sketches(target) == ["Sketch 1"]
    assert not tab.session.is_dirty


def test_autosave_with_a_sketch_open_keeps_its_edits(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = _sketch_with_a_rectangle(qtbot, window)
    window.autosave()
    mode = window.sketch_mode
    assert mode is not None and mode.is_open  # autosave never closes the sketch
    assert _sketches(tab.autosaver.fdef_path) == ["Sketch 1"]
    assert all(f.type != "sketch" for f in tab.session.document.features)
