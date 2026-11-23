"""Drag without solving, dimensions from a drag, detach on drag in the canvas (TR112, D1716)."""

from __future__ import annotations

from dataclasses import replace

import pytest
from PySide6.QtCore import QPoint, Qt
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Line
from fdcad.ui.sketch_tools import canvas as canvas_module
from fdcad.ui.sketch_tools.options import SketchOptions
from tests.ui.sketch_tools.p2_helpers import canvas_of


def _drag(qtbot: QtBot, canvas: object, a: tuple[float, float], b: tuple[float, float]) -> None:
    pa = canvas.to_screen(a)  # type: ignore[attr-defined]
    pb = canvas.to_screen(b)  # type: ignore[attr-defined]
    qa, qb = QPoint(round(pa.x()), round(pa.y())), QPoint(round(pb.x()), round(pb.y()))
    qtbot.mouseMove(canvas, qa)  # type: ignore[arg-type]
    qtbot.mousePress(canvas, Qt.MouseButton.LeftButton, pos=qa)  # type: ignore[arg-type]
    for k in range(1, 6):
        q = qa + (qb - qa) * (k / 5)
        qtbot.mouseMove(canvas, q)  # type: ignore[arg-type]
    qtbot.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=qb)  # type: ignore[arg-type]


def _corner(canvas: object) -> tuple[str, str]:
    sk = canvas.edit.sketch  # type: ignore[attr-defined]
    a = sk.add_line(0.0, 0.0, 20.0, 0.0)
    b = sk.add_line(20.0, 0.0, 20.0, 20.0)
    sk.relate("coincident", sk.entities[a].p2, sk.entities[b].p1)
    sk.relate("vertical", b)
    canvas.edit.refresh()  # type: ignore[attr-defined]
    return a, b


def test_free_drag_asks_then_deletes_what_broke(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    canvas, _panel = canvas_of(qtbot)
    _a, b = _corner(canvas)
    asked: list[int] = []
    monkeypatch.setattr(canvas_module, "ask_delete_unmet", lambda _p, n: asked.append(n) or True)
    canvas.edit.free_drag = True
    top = canvas.edit.sketch.entities[b]
    assert isinstance(top, Line)
    _drag(qtbot, canvas, (20.0, 20.0), (28.0, 20.0))
    assert canvas.edit.sketch.xy(top.p2) == pytest.approx((28.0, 20.0), abs=0.3)
    assert asked == [1]
    assert all(r.type != "vertical" for r in canvas.edit.sketch.relations)


def test_drag_changes_dimensions_preference(qtbot: QtBot) -> None:
    canvas, _panel = canvas_of(qtbot)
    sk = canvas.edit.sketch
    lid = sk.add_line(0.0, 0.0, 20.0, 0.0)
    sk.relate("horizontal", lid)
    dim = sk.dimension("distance", [lid], Param("20mm", 20.0))
    canvas.edit.refresh()
    canvas.set_options(replace(SketchOptions(), drag_changes_dimensions=True))
    line = sk.entities[lid]
    assert isinstance(line, Line)
    canvas.edit.drag_to({line.p2: (26.0, 0.0)})
    assert dim.driving
    assert canvas.edit.sketch.dimensions[0].param.value == pytest.approx(26.0, abs=1e-6)


def test_detach_on_drag_breaks_the_corner(qtbot: QtBot) -> None:
    canvas, _panel = canvas_of(qtbot)
    sk = canvas.edit.sketch
    a = sk.add_line(0.0, 0.0, 20.0, 0.0)
    b = sk.add_line(20.0, 0.0, 20.0, 20.0)
    la, lb = sk.entities[a], sk.entities[b]
    assert isinstance(la, Line) and isinstance(lb, Line)
    lb.p1 = la.p2  # one shared corner point
    canvas.edit.refresh()
    canvas.detach_drag = True
    canvas.selection = [a]
    _drag(qtbot, canvas, (20.0, 0.0), (30.0, -6.0))
    la, lb = canvas.edit.sketch.entities[a], canvas.edit.sketch.entities[b]
    assert isinstance(la, Line) and isinstance(lb, Line)
    assert la.p2 != lb.p1
    assert canvas.edit.sketch.xy(lb.p1) == pytest.approx((20.0, 0.0), abs=1e-6)
