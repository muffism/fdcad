"""Keep proportions on the first dimension, through the canvas (TR119, D938)."""

from __future__ import annotations

import dataclasses

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Point
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from tests.ui.sketch_tools.p2_helpers import canvas_of


def _size(canvas: SketchCanvas) -> tuple[float, float]:
    pts = [
        e
        for e in canvas.edit.sketch.entities.values()
        if isinstance(e, Point) and not e.construction
    ]
    xs, ys = [p.x for p in pts], [p.y for p in pts]
    return max(xs) - min(xs), max(ys) - min(ys)


@pytest.mark.parametrize(("keep", "size"), [(True, (80.0, 40.0)), (False, (80.0, 20.0))])
def test_first_dimension(qtbot: QtBot, keep: bool, size: tuple[float, float]) -> None:
    canvas, _ = canvas_of(qtbot)
    canvas.options = dataclasses.replace(canvas.options, keep_proportions=keep)
    sk = canvas.edit.sketch
    corners = [(0, 0), (40, 0), (40, 20), (0, 20)]
    lines = [sk.add_line(*corners[i], *corners[(i + 1) % 4]) for i in range(4)]
    for i in range(4):
        a, b = sk.entities[lines[i]], sk.entities[lines[(i + 1) % 4]]
        canvas.edit.relate("coincident", [a.p2, b.p1])
    canvas.edit.relate("horizontal", [lines[0]])
    canvas.edit.relate("horizontal", [lines[2]])
    canvas.edit.relate("vertical", [lines[1]])
    canvas.edit.relate("vertical", [lines[3]])
    dim = canvas.edit.add_dimension("distance", [lines[0]], None)
    canvas.edit.refresh()
    assert canvas.apply_dimension_text(dim.id, "80") == ""
    width, height = _size(canvas)
    assert width == pytest.approx(size[0], abs=1e-3)
    assert height == pytest.approx(size[1], abs=1e-3)
