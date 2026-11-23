"""Sketch tools and the edit model, ending in a real extrude."""

from __future__ import annotations

import math

import pytest
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import Arc, Circle, Line, Point
from fdcad.core.sketch.solver import SketchStatus
from fdcad.core.sketch.topology import check
from fdcad.ui.sketch_tools.edit import (
    SketchEdit,
    new_sketch_data,
    relations_for,
    smart_dimension,
)
from fdcad.ui.sketch_tools.inference import Snap, find_snap
from fdcad.ui.sketch_tools.tools import Tool, make_tool


def _edit() -> SketchEdit:
    feature = Feature(
        "f5", "sketch", "Sketch 1", refs={"plane": {"feature": "f2"}}, data=new_sketch_data()
    )
    return SketchEdit(feature)


def _click(edit: SketchEdit, tool: Tool, x: float, y: float) -> bool:
    changed = tool.click(find_snap(edit.sketch, (x, y), 0.5))
    edit.refresh()
    return changed


def _count(edit: SketchEdit, kind: type) -> int:
    return sum(isinstance(e, kind) for e in edit.sketch.entities.values())


def test_new_sketch_has_fixed_origin() -> None:
    edit = _edit()
    (origin,) = edit.sketch.entities.values()
    assert isinstance(origin, Point) and origin.construction
    assert edit.defined == {origin.id}


def test_line_chain_with_auto_relations() -> None:
    edit = _edit()
    tool = make_tool("line", edit)
    _click(edit, tool, 0.1, 0.1)  # snaps to the origin
    _click(edit, tool, 20, 0.4)  # horizontal
    _click(edit, tool, 20.2, 15)  # vertical
    assert _count(edit, Line) == 2
    types = [r.type for r in edit.sketch.relations]
    assert types.count("horizontal") == 1 and types.count("vertical") == 1
    assert types.count("coincident") == 2  # origin, and the chain joint
    assert tool.busy  # the chain continues
    assert not tool.cancel() and tool.cancel()


def test_corner_rectangle_closes_and_extrudes() -> None:
    edit = _edit()
    tool = make_tool("corner_rectangle", edit)
    _click(edit, tool, 0, 0)
    _click(edit, tool, 40, 30)
    assert _count(edit, Line) == 4 and check(edit.sketch) == []
    lines = [e.id for e in edit.sketch.curves()]
    edit.checkpoint()
    edit.add_dimension("distance", [lines[0]], Param("40", 40.0))
    edit.add_dimension("distance", [lines[1]], Param("30", 30.0))
    edit.refresh()
    assert edit.status().state is SketchStatus.FULL
    assert edit.defined >= set(edit.sketch.entities)

    doc = new_document()
    sketch = edit.to_feature()
    doc.features.append(sketch)
    doc.next_id = max(doc.next_id, int(sketch.id[1:]) + 1)  # ids are unique (fdef)
    fid = doc.new_feature_id()
    params = {
        "operation": "boss",
        "end_condition": "blind",
        "depth": Param("10", 10.0),
        "reverse": False,
    }
    doc.features.append(
        Feature(fid, "extrude", "Extrude", params=params, refs={"sketch": {"feature": sketch.id}})
    )
    report = RebuildEngine().rebuild(doc)
    assert report.body is not None
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(report.body.shape, props)
    assert math.isclose(props.Mass(), 40 * 30 * 10, rel_tol=1e-6)


def test_center_rectangle_is_symmetric() -> None:
    edit = _edit()
    tool = make_tool("center_rectangle", edit)
    _click(edit, tool, 0, 0)
    _click(edit, tool, 10, 5)
    assert check(edit.sketch) == []
    assert edit.result is not None and edit.result.solved
    corners = sorted(
        (round(p.x, 6), round(p.y, 6))
        for p in edit.sketch.entities.values()
        if isinstance(p, Point) and not p.construction
    )
    assert corners[0] == (-10.0, -5.0) and corners[-1] == (10.0, 5.0)


def test_circle_and_arcs() -> None:
    edit = _edit()
    circle = make_tool("circle", edit)
    _click(edit, circle, 50, 0)
    _click(edit, circle, 55, 0)
    assert _count(edit, Circle) == 1

    arc = make_tool("center_arc", edit)
    _click(edit, arc, 0, 50)
    _click(edit, arc, 10, 50)
    for k in range(1, 10):  # turn counter clockwise a quarter
        a = k * math.pi / 18
        arc.hover(Snap("free", 10 * math.cos(a), 50 + 10 * math.sin(a)))
    _click(edit, arc, 0, 60)
    arcs = [e for e in edit.sketch.entities.values() if isinstance(e, Arc)]
    assert len(arcs) == 1 and arcs[0].ccw
    assert math.isclose(edit.sketch.radius(arcs[0].id), 10.0, rel_tol=1e-6)

    three = make_tool("three_point_arc", edit)
    _click(edit, three, 100, 0)
    _click(edit, three, 120, 0)
    _click(edit, three, 110, 10)
    arcs = [e for e in edit.sketch.entities.values() if isinstance(e, Arc)]
    assert len(arcs) == 2
    assert math.isclose(edit.sketch.radius(arcs[1].id), 10.0, rel_tol=1e-6)


def test_tangent_arc_continues_a_line() -> None:
    edit = _edit()
    line = make_tool("line", edit)
    _click(edit, line, 10, 10)
    _click(edit, line, 30, 10)
    line.cancel()
    tangent = make_tool("tangent_arc", edit)
    assert not _click(edit, tangent, 25, 25)  # not on an end point
    _click(edit, tangent, 30, 10)
    _click(edit, tangent, 30, 30)
    arcs = [e for e in edit.sketch.entities.values() if isinstance(e, Arc)]
    assert len(arcs) == 1
    assert math.isclose(edit.sketch.radius(arcs[0].id), 10.0, rel_tol=1e-6)
    assert any(r.type == "tangent" for r in edit.sketch.relations)
    assert edit.result is not None and edit.result.solved


def test_undo_redo_delete_and_construction() -> None:
    edit = _edit()
    tool = make_tool("circle", edit)
    _click(edit, tool, 5, 5)
    _click(edit, tool, 8, 5)
    (cid,) = [e.id for e in edit.sketch.curves()]
    edit.checkpoint()
    edit.toggle_construction({cid})
    assert edit.sketch.entities[cid].construction
    edit.checkpoint()
    edit.delete({cid})
    assert _count(edit, Circle) == 0 and _count(edit, Point) == 1  # origin stays
    edit.undo()
    assert _count(edit, Circle) == 1
    edit.undo()
    assert not edit.sketch.entities[cid].construction
    edit.redo()
    assert edit.sketch.entities[cid].construction


def test_selection_rules() -> None:
    edit = _edit()
    sk = edit.sketch
    l1 = sk.add_line(0, 0, 10, 0)
    l2 = sk.add_line(0, 5, 10, 6)
    c = sk.add_circle(0, 20, 3)
    p = sk.add_point(3, 3)
    assert "parallel" in relations_for(sk, [l1, l2])
    assert "tangent" in relations_for(sk, [l1, c])
    assert "midpoint" in relations_for(sk, [p, l1])
    assert relations_for(sk, [c]) == ["fixed"]
    assert smart_dimension(sk, [c]) == "diameter"
    assert smart_dimension(sk, [l1, l2]) == "angle"
    # A single line gives its length wherever the text goes (T4.1).
    assert smart_dimension(sk, [l1], (5, 4)) == "distance"
    assert smart_dimension(sk, [l1], (15, 0)) == "distance"


def test_drag_keeps_relations() -> None:
    edit = _edit()
    tool = make_tool("line", edit)
    _click(edit, tool, 0, 0)
    _click(edit, tool, 20, 0)
    line = next(e for e in edit.sketch.curves() if isinstance(e, Line))
    assert edit.drag_to({line.p2: (30.0, 8.0)})
    assert edit.sketch.xy(line.p1) == pytest.approx((0.0, 0.0), abs=1e-9)
    assert edit.sketch.xy(line.p2)[1] == pytest.approx(0.0, abs=1e-6)


def test_a_flat_rectangle_says_why_nothing_was_drawn() -> None:
    """Audit D2 item 7 (D743): a rectangle with no height was dropped without a word."""
    from fdcad.ui.sketch_tools.tool_text import FLAT_RECTANGLE

    edit = _edit()
    tool = make_tool("corner_rectangle", edit)
    _click(edit, tool, 0, 0)
    assert not _click(edit, tool, 20, 0)
    assert edit.take_note() == FLAT_RECTANGLE
    assert _count(edit, Line) == 0


def test_a_typed_size_that_cannot_be_a_dimension_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit D2 item 13 (D743): a typed size whose dimension failed was skipped silently."""
    from types import SimpleNamespace

    from fdcad.ui.sketch_tools import typed_size
    from fdcad.ui.sketch_tools.tool_text import TYPED_NOT_DIMENSIONED

    edit = _edit()
    bad = [("distance", ["no_such_point", "other"], Param("5", 5.0))]
    monkeypatch.setattr(typed_size, "dimensions", lambda _tool: bad)
    assert typed_size.add_dimensions(SimpleNamespace(edit=edit)) == []  # type: ignore[arg-type]
    assert edit.take_note() == TYPED_NOT_DIMENSIONED.format(n=1)
