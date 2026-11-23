"""Temporary guide lines (TR232, D1714)."""

from __future__ import annotations

from PySide6.QtCore import QPointF
from pytestqt.qtbot import QtBot

from fdcad.ui.sketch_tools.guides import Guides
from tests.ui.sketch_tools.p2_helpers import canvas_of


def test_guide_points() -> None:
    g = Guides()
    assert g.rest_on((0.0, 0.0)) == "started"
    assert g.rest_on((0.0, 0.0)) == ""
    assert g.rest_on((12.0, 0.0)) == "made"
    assert (6.0, 0.0) in g.points() and (4.0, 0.0) in g.points() and (3.0, 0.0) in g.points()
    assert g.snap((4.1, 0.1), 0.5) == (4.0, 0.0)
    assert g.snap((5.0, 3.0), 0.5) is None
    g.clear()
    assert g.lines == [] and g.anchor is None


def test_resting_on_two_points_gives_snaps_until_the_tool_ends(qtbot: QtBot) -> None:
    canvas, _panel = canvas_of(qtbot)
    sk = canvas.edit.sketch
    a = sk.add_point(0.0, 0.0)
    b = sk.add_point(30.0, 0.0)
    canvas.edit.refresh()
    canvas.set_tool("line")
    notes: list[str] = []
    canvas.status_message.connect(notes.append)
    assert canvas.rest_on_point(a) == "started"
    assert canvas.rest_on_point(b) == "made"
    assert "Guide added" in notes[-1]
    snap = canvas._snap_at(canvas.to_screen((10.05, 0.4)))
    assert snap.kind == "guide" and abs(snap.x - 10.0) < 1e-9 and snap.relations == []
    canvas.grab()  # draws the guide
    canvas.set_tool("circle")
    assert canvas.guides.lines == []
    assert canvas._snap_at(canvas.to_screen((10.05, 0.4))).kind != "guide"


def test_the_rest_timer_makes_the_guide(qtbot: QtBot) -> None:
    canvas, _panel = canvas_of(qtbot)
    pid = canvas.edit.sketch.add_point(5.0, 5.0)
    canvas.edit.refresh()
    canvas.set_tool("line")
    snap = canvas._snap_at(QPointF(canvas.to_screen((5.0, 5.0))))
    assert snap.kind == "point" and snap.target == pid
    canvas._watch_rest(snap)
    qtbot.waitUntil(lambda: canvas.guides.anchor is not None, timeout=3000)
