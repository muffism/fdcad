"""Control of relations offered while drawing (TR231, D1309)."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.options import AUTO_KINDS, SWITCHES, SketchOptions
from fdcad.ui.sketch_tools.tools import LineTool
from tests.ui.sketch_tools.p2_helpers import canvas_of, edit_of


def _kinds(edit) -> list[str]:  # type: ignore[no-untyped-def]
    return [r.type for r in edit.sketch.relations if r.type != "fixed"]


def _draw_horizontal(edit) -> None:  # type: ignore[no-untyped-def]
    tool = LineTool(edit)
    tool.click(Snap("free", 0.0, 5.0))
    tool.click(Snap("free", 10.0, 5.05))


def test_every_kind_has_a_preference_switch_on_by_default() -> None:
    for kind in AUTO_KINDS:
        assert f"auto_{kind}" in SWITCHES
        assert getattr(SketchOptions(), f"auto_{kind}") is True


def test_a_kind_switched_off_is_not_added(qtbot: QtBot) -> None:
    canvas, _panel = canvas_of(qtbot)
    edit = canvas.edit
    _draw_horizontal(edit)
    assert "horizontal" in _kinds(edit)
    canvas.set_options(replace(SketchOptions(), auto_horizontal=False))
    assert edit.auto_off == {"horizontal"}
    before = len(edit.sketch.relations)
    tool = LineTool(edit)
    tool.click(Snap("free", 0.0, 20.0))
    tool.click(Snap("free", 10.0, 20.05))
    assert len(edit.sketch.relations) == before


def test_a_coincident_snap_follows_its_switch() -> None:
    edit = edit_of()
    pid = edit.sketch.add_point(3.0, 3.0)
    snap = Snap("point", 3.0, 3.0, [("coincident", [pid])], target=pid)
    edit.auto_off = {"coincident"}
    new = edit.place_point(snap)
    assert not any(new in r.entities for r in edit.sketch.relations)
    edit.auto_off = set()
    new = edit.place_point(snap)
    assert any(new in r.entities for r in edit.sketch.relations)


def test_tab_skips_the_relations_of_the_next_click(qtbot: QtBot) -> None:
    canvas, _panel = canvas_of(qtbot)
    shown: list[str] = []
    canvas.status_message.connect(shown.append)
    canvas.set_tool("line")
    qtbot.keyClick(canvas, Qt.Key.Key_Tab)
    assert canvas.edit.skip_next and "skipped" in shown[-1]
    assert not canvas.focusNextPrevChild(True)  # Tab stays in the sketch
    _draw_horizontal(canvas.edit)
    assert "horizontal" not in _kinds(canvas.edit)
    qtbot.keyClick(canvas, Qt.Key.Key_Tab)
    assert not canvas.edit.skip_next
