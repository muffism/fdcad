"""WP14 model geometry snapping in the sketch editor (TOOL_SPEC T1.2.2, T3.1 note 3, D250)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtCore import QPoint, Qt
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature
from fdcad.core.sketch.links import (
    LinkUpdate,
    ModelCircle,
    ModelGeometry,
    ModelLine,
    ModelPoint,
)
from fdcad.core.sketch.model import Circle, Line, Point, Sketch
from fdcad.core.units import UnitSystem
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.edit import SketchEdit, new_sketch_data
from fdcad.ui.sketch_tools.inference import find_snap
from fdcad.ui.sketch_tools.link_bar import LinkBar
from fdcad.ui.sketch_tools.model_snap import ModelSnapIndex

Vec = tuple[float, float]
CORNER = ("vertex", "vertex(a|b|c)")
BOTTOM = ("edge", "edge(a|b)")
HOLE = ("edge", "edge(c|d)")


def _geometry() -> ModelGeometry:
    """A 60 by 40 plate seen face on, corner at (10, 5), with a radius 6 hole at (40, 25)."""
    g = ModelGeometry()
    g.points = [
        ModelPoint((0.0, 0.0), ("origin", "")),
        ModelPoint((10.0, 5.0), CORNER),
        ModelPoint((40.0, 25.0), HOLE),
    ]
    g.lines = [ModelLine((10.0, 5.0), (70.0, 5.0), BOTTOM)]
    g.circles = [ModelCircle((40.0, 25.0), 6.0, HOLE)]
    g.polylines = [[(10.0, 5.0), (70.0, 5.0)]]
    return g


@pytest.fixture
def canvas(qtbot: QtBot) -> Iterator[SketchCanvas]:
    feature = Feature(
        "f5", "sketch", "Sketch 1", refs={"plane": {"feature": "f2"}}, data=new_sketch_data()
    )
    canvas = SketchCanvas(SketchEdit(feature), UnitSystem.MM)
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    canvas.show()
    canvas.scale, canvas.center = 4.0, (40.0, 20.0)
    canvas.set_model(_geometry())
    yield canvas


def _pos(canvas: SketchCanvas, at: Vec) -> QPoint:
    p = canvas.to_screen(at)
    return QPoint(round(p.x()), round(p.y()))


def _move(qtbot: QtBot, canvas: SketchCanvas, at: Vec) -> None:
    qtbot.mouseMove(canvas, _pos(canvas, at))


def _click(qtbot: QtBot, canvas: SketchCanvas, at: Vec) -> None:
    _move(qtbot, canvas, at)
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=_pos(canvas, at))


def _has(sk: Sketch, rtype: str, *ids: str) -> bool:
    return any(r.type == rtype and set(ids) <= set(r.entities) for r in sk.relations)


def _copies(sk: Sketch) -> list[Point | Line | Circle]:
    return [e for e in sk.entities.values() if getattr(e, "source", None) is not None]  # type: ignore[misc]


def _placed(sk: Sketch) -> Point:
    return next(e for e in sk.entities.values() if isinstance(e, Point) and not e.construction)


# The index ------------------------------------------------------------------------------


def test_index_finds_the_nearest_items_with_arrays() -> None:
    index = ModelSnapIndex(_geometry())
    kinds = {h.kind: h for h in index.query((10.3, 5.2), 1.0)}
    assert kinds["point"].point is not None and kinds["point"].point.source == CORNER
    on = index.query((30.0, 5.4), 1.0)
    assert [h.kind for h in on] == ["on_curve"] and on[0].xy == pytest.approx((30.0, 5.0))
    mid = {h.kind for h in index.query((40.0, 5.2), 1.0)}
    assert mid == {"midpoint", "on_curve"}
    ring = index.query((46.3, 25.0), 1.0)
    assert ring[0].kind == "on_curve" and isinstance(ring[0].curve, ModelCircle)
    assert index.query((25.0, 30.0), 1.0) == []
    # Centres are revealed by hover, not snapped at once (W3.2).
    assert all(p.source != HOLE for p in index.points)
    assert index.centre_at((40.0, 25.0)) is not None


def test_index_respects_arc_ranges() -> None:
    g = ModelGeometry(circles=[ModelCircle((0.0, 0.0), 10.0, HOLE, 0.0, (0.0, 1.5))])
    index = ModelSnapIndex(g)
    assert index.query((7.07, 7.07), 0.5)
    assert index.query((-10.0, 0.0), 0.5) == []


def test_sketch_points_win_a_tie_and_vertices_beat_edges() -> None:
    sk = Sketch()
    sk.add_point(10.0, 5.0)
    index = ModelSnapIndex(_geometry())
    snap = find_snap(sk, (10.2, 5.1), 1.0, model=index)
    assert snap.kind == "point" and snap.model is None and snap.target is not None
    snap = find_snap(Sketch(), (10.2, 5.3), 1.0, model=index)
    assert snap.kind == "point" and snap.model_source == CORNER


# Drawing tools --------------------------------------------------------------------------


def test_vertex_snap_ties_to_a_linked_copy(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.set_tool("point")
    _click(qtbot, canvas, (10.3, 5.2))
    sk = canvas.edit.sketch
    (copy,) = _copies(sk)
    assert isinstance(copy, Point) and copy.construction and (copy.x, copy.y) == (10.0, 5.0)
    assert copy.source == {"kind": "vertex", "name": "vertex(a|b|c)"}
    assert _has(sk, "fixed", copy.id) and _has(sk, "coincident", _placed(sk).id, copy.id)


def test_edge_snap_puts_the_point_on_a_linked_line_copy(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.set_tool("point")
    _click(qtbot, canvas, (25.0, 5.4))
    sk = canvas.edit.sketch
    (copy,) = _copies(sk)
    assert isinstance(copy, Line) and copy.source == {"kind": "edge", "name": "edge(a|b)"}
    p = _placed(sk)
    assert (p.x, p.y) == pytest.approx((25.0, 5.0))
    assert _has(sk, "coincident", p.id, copy.id)


def test_edge_midpoint_snap_adds_midpoint(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.set_tool("point")
    _click(qtbot, canvas, (40.2, 5.3))
    sk = canvas.edit.sketch
    (copy,) = _copies(sk)
    assert _has(sk, "midpoint", _placed(sk).id, copy.id)


def test_round_edge_and_revealed_centre(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.set_tool("point")
    _click(qtbot, canvas, (40.0, 31.2))  # on the hole's edge: also reveals its centre
    assert (40.0, 25.0) in canvas.revealed
    sk = canvas.edit.sketch
    (circle,) = _copies(sk)
    assert isinstance(circle, Circle) and circle.radius == 6.0 and _has(sk, "fixed", circle.id)
    assert circle.source == {"kind": "edge", "name": "edge(c|d)"}
    # The copy's own centre is now the nearest centre snap.
    _click(qtbot, canvas, (40.3, 25.2))
    second = [e for e in canvas.edit.sketch.entities.values() if isinstance(e, Point)][-1]
    assert _has(canvas.edit.sketch, "coincident", second.id, circle.center)


def test_revealed_centre_alone_gets_a_linked_point_copy(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.set_tool("point")
    _move(qtbot, canvas, (40.0, 31.0))  # hover the edge: reveals the centre
    _click(qtbot, canvas, (40.3, 25.2))
    sk = canvas.edit.sketch
    (centre,) = _copies(sk)
    assert isinstance(centre, Point) and centre.source == {"kind": "edge", "name": "edge(c|d)"}


def test_copies_are_reused(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.set_tool("point")
    _click(qtbot, canvas, (20.0, 5.3))
    _click(qtbot, canvas, (30.0, 5.3))
    assert len(_copies(canvas.edit.sketch)) == 1


def test_ctrl_and_model_snaps_off_give_free_points(qtbot: QtBot, canvas: SketchCanvas) -> None:
    from dataclasses import replace

    canvas.set_options(replace(canvas.options, model_snaps=False))
    canvas.set_tool("point")
    _click(qtbot, canvas, (10.3, 5.2))
    assert _copies(canvas.edit.sketch) == []


def test_undo_removes_the_copy_with_the_point(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.set_tool("point")
    _click(qtbot, canvas, (10.3, 5.2))
    canvas.undo()
    assert _copies(canvas.edit.sketch) == []


# Smart Dimension and drags ----------------------------------------------------------------


def test_smart_dimension_picks_linked_copies(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.set_tool("dimension")
    _click(qtbot, canvas, (10.3, 5.2))  # a vertex
    _click(qtbot, canvas, (55.0, 5.3))  # the edge
    sk = canvas.edit.sketch
    assert len(canvas.dim_picks) == 2
    kinds = {type(sk.entities[i]).__name__ for i in canvas.dim_picks}
    assert kinds == {"Point", "Line"}
    assert all(sk.entities[i] in _copies(sk) for i in canvas.dim_picks)


def test_drag_onto_a_vertex_ties_the_point(qtbot: QtBot, canvas: SketchCanvas) -> None:
    sk = canvas.edit.sketch
    p = sk.add_point(25.0, 15.0)
    canvas.changed()
    qtbot.mousePress(canvas, Qt.MouseButton.LeftButton, pos=_pos(canvas, (25.0, 15.0)))
    for t in (0.2, 0.5, 0.8, 1.0):
        _move(qtbot, canvas, (25.0 - 14.8 * t, 15.0 - 9.8 * t))
    qtbot.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=_pos(canvas, (10.2, 5.2)))
    sk = canvas.edit.sketch
    (copy,) = _copies(sk)
    assert _has(sk, "coincident", p, copy.id)
    assert sk.xy(p) == pytest.approx((10.0, 5.0), abs=1e-6)


# Update -----------------------------------------------------------------------------------


def test_update_moves_copies_as_one_undo_step(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.set_tool("point")
    _click(qtbot, canvas, (10.3, 5.2))
    sk = canvas.edit.sketch
    (copy,) = _copies(sk)
    placed = _placed(sk).id
    assert canvas.edit.link_updates([LinkUpdate(copy.id, (12.0, 6.0))]) == 1
    sk = canvas.edit.sketch
    assert sk.xy(copy.id) == (12.0, 6.0)
    assert sk.xy(placed) == pytest.approx((12.0, 6.0))  # tied geometry follows
    canvas.undo()
    assert canvas.edit.sketch.xy(copy.id) == (10.0, 5.0)
    assert canvas.edit.link_updates([LinkUpdate(copy.id, None)]) == 0  # lost: nothing moves


def test_link_bar_text_and_button(qtbot: QtBot) -> None:
    bar = LinkBar()
    qtbot.addWidget(bar)
    bar.set_updates([])
    assert bar.isHidden()
    bar.set_updates([LinkUpdate("e3", (1.0, 2.0)), LinkUpdate("e4", None)])
    assert not bar.isHidden() and not bar.button.isHidden()
    assert "1 part copy no longer matches" in bar.label.text()
    assert "lost" in bar.label.text()
    bar.set_updates([LinkUpdate("e4", None)])
    assert bar.button.isHidden()
    with qtbot.waitSignal(bar.update_requested):
        bar.set_updates([LinkUpdate("e3", (1.0, 2.0))])
        bar.button.click()
