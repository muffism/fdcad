"""Unit tests for every node type (PLAN section 10 item 10)."""

from __future__ import annotations

import math
from typing import Any

import pytest

from fdcad.core.document.model import Param
from fdcad.core.graph import geometry as geo
from fdcad.core.graph.engine import Evaluator, _input_value
from fdcad.core.graph.model import Node
from fdcad.core.graph.nodes import NODE_TYPES
from fdcad.core.graph.nodes.base import GraphEnv, NeedsConfirmationError, NodeContext, NodeError
from fdcad.core.graph.types import XY_PLANE, Plane, PortType, make_plane
from fdcad.core.units import Kind
from tests.core.graph.helpers import graph, p

SQUARE = [(0.0, 0.0, 0.0), (40.0, 0.0, 0.0), (40.0, 30.0, 0.0), (0.0, 30.0, 0.0)]


def run(
    ntype: str,
    args: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    env: GraphEnv | None = None,
    types: dict[str, PortType] | None = None,
) -> dict[str, Any]:
    """Compute one node, unwired inputs taken from ``params`` or their defaults."""
    t = NODE_TYPES[ntype]
    node = Node("n1", ntype, dict(params or {}))
    full = {port.name: _input_value(node, port, env or GraphEnv()) for port in t.inputs}
    full.update(args or {})
    ctx = NodeContext(node, env or GraphEnv(), 1, types or {})
    return t.compute(full, ctx)


def square() -> Any:
    return geo.polyline(SQUARE, True)


# Input ------------------------------------------------------------------------------


def test_slider_clamps_and_snaps() -> None:
    assert run("slider", params={"min": 2, "max": 10, "step": 0.5, "value": p(4.3)})["out"] == 4.5
    assert run("slider", params={"min": 2, "max": 10, "step": 0.5, "value": p(99)})["out"] == 10
    assert run("slider", params={"min": 2, "max": 10, "step": 0, "value": p(1)})["out"] == 2
    with pytest.raises(NodeError, match="maximum"):
        run("slider", params={"min": 5, "max": 1, "value": p(3)})


def test_value_takes_the_full_expression_syntax_and_variables() -> None:
    env = GraphEnv(variables={"Width": (Kind.LENGTH, 50.0)})
    assert (
        run("value", params={"kind": "length", "value": Param("=Width/2", 0)}, env=env)["out"] == 25
    )
    assert run("value", params={"kind": "length", "value": Param("1in", 25.4)})["out"] == 25.4
    with pytest.raises(NodeError, match="formula"):
        run("value", params={"kind": "length", "value": Param("=Nope", 0)}, env=env)


def test_toggle_and_point_and_vector() -> None:
    assert run("toggle", params={"value": True})["out"] is True
    assert run("point", params={"x": p(1), "y": p(2)})["out"] == (1.0, 2.0, 0.0)
    assert run("vector")["out"] == (0.0, 0.0, 1.0)


def test_read_variable() -> None:
    env = GraphEnv(variables={"Width": (Kind.LENGTH, 50.0)})
    assert run("read_variable", params={"variable": "Width"}, env=env)["out"] == 50.0
    with pytest.raises(NodeError, match="no variable"):
        run("read_variable", params={"variable": "X"}, env=env)
    with pytest.raises(NodeError, match="Choose"):
        run("read_variable", env=env)


def test_read_param() -> None:
    env = GraphEnv(features={"f6": ("extrude", "Extrude 1", {"depth": Param("10", 10.0)})})
    assert run("read_param", params={"feature": "f6", "param": "depth"}, env=env)["out"] == 10
    with pytest.raises(NodeError, match="no value"):
        run("read_param", params={"feature": "f6", "param": "radius"}, env=env)
    with pytest.raises(NodeError, match="below"):
        run("read_param", params={"feature": "f9", "param": "depth"}, env=env)


def test_model_reference_face_edge_body_and_curve() -> None:
    from fdcad.core.features.base import FeatureResult
    from fdcad.core.naming.names import NamedShape, faces_of
    from fdcad.core.naming.resolve import face_snapshot

    box = geo.box(XY_PLANE, 10, 20, 30)
    faces = faces_of(box)
    named = NamedShape(box, [(f"f5/face/{i}", f) for i, f in enumerate(faces, 1)])
    env = GraphEnv(body=named, body_key="k")
    top = next(f for f in faces if abs(geo.bounds(f)[0][2] - 30) < 1e-9)
    name = named.primary_name(top)
    ref = {"kind": "face", "name": name, "snapshot": face_snapshot(top)}
    out = run("model_ref", params={"kind": "face", "ref": ref}, env=env)
    assert abs(geo.curve_length(out["curve"]) - 60) < 1e-6
    assert out["plane"].normal == pytest.approx((0, 0, 1))
    body = run("model_ref", params={"kind": "body", "ref": ref}, env=env)["body"]
    assert abs(geo.volume(body) - 6000) < 1e-6
    lost = {"kind": "face", "name": "f5/face/99", "snapshot": face_snapshot(top)}
    graph_out = (
        Evaluator()
        .evaluate(graph(("n1", "model_ref", {"kind": "face", "ref": lost})), env)
        .nodes["n1"]
    )
    assert graph_out.ok and graph_out.warning  # found by its position: a warning
    res = FeatureResult(body=None, extras={"curve": square()})
    curve_env = GraphEnv(results={"f7": res})
    curve = run("model_ref", params={"kind": "curve", "ref": {"feature": "f7"}}, env=curve_env)[
        "curve"
    ]
    assert abs(geo.curve_length(geo.wire_of(curve)) - 140) < 1e-6
    with pytest.raises(NodeError, match="Pick"):
        run("model_ref", params={"kind": "face"}, env=env)
    with pytest.raises(NodeError, match="no body"):
        run("model_ref", params={"kind": "face", "ref": ref}, env=GraphEnv())


# Math -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("op", "a", "b", "out"),
    [
        ("add", 2, 3, 5),
        ("subtract", 2, 3, -1),
        ("multiply", 2, 3, 6),
        ("divide", 3, 2, 1.5),
        ("power", 2, 3, 8),
        ("modulo", 7, 3, 1),
        ("minimum", 2, 3, 2),
        ("maximum", 2, 3, 3),
    ],
)
def test_arithmetic(op: str, a: float, b: float, out: float) -> None:
    assert run("arithmetic", {"a": a, "b": b}, {"operation": op})["out"] == out


def test_arithmetic_errors() -> None:
    with pytest.raises(NodeError, match="zero"):
        run("arithmetic", {"a": 1, "b": 0}, {"operation": "divide"})
    with pytest.raises(NodeError, match="real number"):
        run("arithmetic", {"a": -1, "b": 0.5}, {"operation": "power"})


def test_trigonometry() -> None:
    assert run("trig", {"x": math.pi / 2}, {"function": "sin"})["out"] == pytest.approx(1)
    assert run("trig", {"x": 1.0}, {"function": "acos"})["out"] == pytest.approx(0)
    with pytest.raises(NodeError, match="-1 to 1"):
        run("trig", {"x": 2.0}, {"function": "asin"})


def test_range_series_remap() -> None:
    assert run("range", {"start": 0, "end": 1, "count": 3})["out"] == [0, 0.5, 1]
    assert run("series", {"start": 1, "step": 2, "count": 3})["out"] == [1, 3, 5]
    assert (
        run(
            "remap",
            {"value": 5, "source_min": 0, "source_max": 10, "target_min": 0, "target_max": 1},
        )["out"]
        == 0.5
    )
    assert run("remap", {"value": 50}, {"clamp": True})["out"] == 10
    assert run("remap", {"value": 2}, {"clamp": False})["out"] == 20
    with pytest.raises(NodeError, match="empty"):
        run("remap", {"source_min": 1, "source_max": 1})


def test_random_is_seeded_and_repeatable() -> None:
    a = run("random", {"count": 5, "min": 0, "max": 1}, {"seed": 3})["out"]
    b = run("random", {"count": 5, "min": 0, "max": 1}, {"seed": 3})["out"]
    c = run("random", {"count": 5, "min": 0, "max": 1}, {"seed": 4})["out"]
    assert a == b and a != c and all(0 <= v <= 1 for v in a)


def test_expression_uses_the_safe_parser_with_units() -> None:
    out = run(
        "expression",
        {"a": 10.0, "b": 2.0},
        {"formula": "a * b + 1mm", "kind": "length"},
        types={"a": PortType.LENGTH},
    )
    assert out["out"] == 21.0
    env = GraphEnv(variables={"Width": (Kind.LENGTH, 40.0)})
    assert (
        run("expression", {"a": 2.0}, {"formula": "=Width / a", "kind": "length"}, env=env)["out"]
        == 20
    )
    with pytest.raises(NodeError, match="formula"):
        run("expression", {}, {"formula": "__import__('os')"})
    with pytest.raises(NodeError, match="Enter a formula"):
        run("expression", {}, {"formula": " "})


# Lists ------------------------------------------------------------------------------


def test_list_nodes() -> None:
    items = [3.0, 1.0, 2.0]
    assert run("list_item", {"list": items, "index": 4})["out"] == 1.0
    with pytest.raises(NodeError, match="outside"):
        run("list_item", {"list": items, "index": 4}, {"wrap": False})
    assert run("list_length", {"list": items})["out"] == 3
    assert run("list_reverse", {"list": items})["out"] == [2.0, 1.0, 3.0]
    sort = run("list_sort", {"list": ["a", "b", "c"], "keys": items})
    assert sort["out"] == ["b", "c", "a"] and sort["indices"] == [1, 2, 0]
    assert run("list_sort", {"list": items})["out"] == [1.0, 2.0, 3.0]
    assert run("list_shift", {"list": items, "offset": 1})["out"] == [1.0, 2.0, 3.0]
    assert run("list_shift", {"list": items, "offset": 1}, {"wrap": False})["out"] == [1.0, 2.0]
    assert run("list_cull", {"list": [1, 2, 3, 4, 5]})["out"] == [1, 3, 5]
    assert run("list_flatten", {"list": [[1, [2]], 3]})["out"] == [1, 2, 3]


def test_nested_lists_up_to_two_levels() -> None:
    g = graph(
        ("n1", "range", {"count": p(2)}),
        ("n2", "range", {"start": p(0), "count": p(2)}),
        ("n3", "series", {}),
        wires=("n1.out>n3.start", "n2.out>n3.count"),
    )
    nested = Evaluator().evaluate(g).value("n3", "out")
    assert len(nested) == 2 and isinstance(nested[0], list)  # two levels
    g3 = graph(
        ("n1", "range", {"count": p(2)}),
        ("n2", "series", {"count": p(2)}),
        ("n3", "range", {"count": p(2)}),
        wires=("n1.out>n2.start", "n2.out>n3.start"),
    )
    res = Evaluator().evaluate(g3).nodes["n3"]
    assert "two levels" in (res.error or "")


# Point and vector -------------------------------------------------------------------


def test_deconstruct_plane_distance_closest() -> None:
    assert run("deconstruct", {"point": (1.0, 2.0, 3.0)}) == {"x": 1, "y": 2, "z": 3}
    plane = run("plane", {"origin": (0.0, 0.0, 5.0), "normal": (0.0, 0.0, 2.0)})["out"]
    assert plane.origin == (0, 0, 5) and plane.normal == (0, 0, 1)
    with pytest.raises(NodeError, match="zero length"):
        run("plane", {"normal": (0.0, 0.0, 0.0)})
    assert run("distance", {"a": (0.0, 0.0, 0.0), "b": (3.0, 4.0, 0.0)})["out"] == 5
    out = run(
        "closest_point", {"point": (9.0, 0.0, 0.0), "points": [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)]}
    )
    assert out["out"] == (10, 0, 0) and out["index"] == 1 and out["distance"] == 1
    with pytest.raises(NodeError, match="empty"):
        run("closest_point", {"points": []})


def test_point_grid_divide_curve_populate() -> None:
    grid = run("point_grid", {"count_x": 3, "count_y": 2, "spacing_x": 5, "spacing_y": 7})["out"]
    assert grid == [(0, 0, 0), (5, 0, 0), (10, 0, 0), (0, 7, 0), (5, 7, 0), (10, 7, 0)]
    tilted = run(
        "point_grid", {"plane": make_plane((0, 0, 1), (1, 0, 0)), "count_x": 2, "count_y": 1}
    )["out"]
    assert tilted[0] == (0, 0, 1) and tilted[1][0] == pytest.approx(0)
    div = run("divide_curve", {"curve": geo.line((0, 0, 0), (10, 0, 0)), "count": 3})
    assert [pt[0] for pt in div["points"]] == pytest.approx([0, 5, 10])
    assert div["tangents"][0] == pytest.approx((1, 0, 0))
    closed = run("divide_curve", {"curve": square(), "count": 14})["points"]
    assert len(closed) == 14  # a closed curve does not repeat its start
    pts = run("populate_region", {"boundary": square(), "count": 30}, {"seed": 1})["out"]
    again = run("populate_region", {"boundary": square(), "count": 30}, {"seed": 1})["out"]
    assert pts == again and len(pts) == 30
    assert all(0 <= x <= 40 and 0 <= y <= 30 and z == 0 for x, y, z in pts)
    with pytest.raises(NodeError, match="open"):
        run("populate_region", {"boundary": geo.line((0, 0, 0), (1, 0, 0)), "count": 3})


# Curves -----------------------------------------------------------------------------


def test_curve_nodes() -> None:
    line = run("line", {"start": (0.0, 0.0, 0.0), "end": (3.0, 4.0, 0.0)})["out"]
    assert geo.curve_length(line) == pytest.approx(5)
    poly = run("polyline", {"points": SQUARE}, {"closed": True})["out"]
    assert geo.curve_length(poly) == pytest.approx(140) and geo.is_closed(poly)
    arc = run(
        "arc", {"start": (-1.0, 0.0, 0.0), "middle": (0.0, 1.0, 0.0), "end": (1.0, 0.0, 0.0)}
    )["out"]
    assert geo.curve_length(arc) == pytest.approx(math.pi)
    circle = run("circle", {"centre": (5.0, 5.0, 0.0), "radius": 2.0})["out"]
    assert geo.curve_length(circle) == pytest.approx(4 * math.pi)
    assert geo.bounds(circle)[0][0] == pytest.approx(3)
    smooth = run("interpolate", {"points": [(0.0, 0.0, 0.0), (5.0, 3.0, 0.0), (10.0, 0.0, 0.0)]})[
        "out"
    ]
    assert geo.curve_length(smooth) > 10
    grown = run("offset_curve", {"curve": poly, "distance": 1.0})["out"]
    assert geo.curve_length(grown) == pytest.approx(140 + 2 * math.pi, rel=1e-6)
    with pytest.raises(NodeError, match="same point"):
        run("line", {"start": (0.0, 0.0, 0.0), "end": (0.0, 0.0, 0.0)})
    with pytest.raises(NodeError, match="on a line"):
        run("arc", {"start": (0.0, 0.0, 0.0), "middle": (1.0, 0.0, 0.0), "end": (2.0, 0.0, 0.0)})
    with pytest.raises(NodeError, match="radius"):
        run("circle", {"radius": 0.0})


# Solids -----------------------------------------------------------------------------


def test_primitive_solids() -> None:
    assert geo.volume(
        run("box", {"size_x": 1.0, "size_y": 2.0, "size_z": 3.0})["body"]
    ) == pytest.approx(6)
    cyl = run("cylinder", {"radius": 1.0, "height": 2.0, "axis": (1.0, 0.0, 0.0)})["body"]
    assert geo.volume(cyl) == pytest.approx(2 * math.pi)
    assert geo.bounds(cyl)[1][0] == pytest.approx(2)
    assert geo.volume(run("sphere", {"radius": 1.0})["body"]) == pytest.approx(4 / 3 * math.pi)
    with pytest.raises(NodeError):
        run("box", {"size_x": 0.0})


def test_extrude_and_pipe() -> None:
    body = run("extrude", {"curve": square(), "distance": 5.0})["body"]
    assert geo.volume(body) == pytest.approx(6000)
    slanted = run("extrude", {"curve": square(), "distance": 5.0, "direction": (0.0, 0.0, -1.0)})[
        "body"
    ]
    assert geo.bounds(slanted)[0][2] == pytest.approx(-5)
    tube = run("pipe", {"curve": geo.line((0, 0, 0), (0, 0, 10)), "radius": 1.0})["body"]
    assert geo.volume(tube) == pytest.approx(10 * math.pi, rel=1e-6)
    with pytest.raises(NodeError, match="open"):
        run("extrude", {"curve": geo.line((0, 0, 0), (1, 0, 0))})


def test_booleans() -> None:
    a = geo.box(XY_PLANE, 10, 10, 10)
    b = geo.box(Plane((5.0, 0.0, 0.0)), 10, 10, 10)
    assert geo.volume(run("union", {"bodies": [a, b]})["body"]) == pytest.approx(1500)
    assert geo.volume(run("difference", {"body": a, "tools": [b]})["body"]) == pytest.approx(500)
    assert geo.volume(run("intersection", {"body": a, "others": [b]})["body"]) == pytest.approx(500)
    far = geo.box(Plane((50.0, 0.0, 0.0)), 1, 1, 1)
    with pytest.raises(NodeError, match="do not overlap"):
        run("intersection", {"body": a, "others": [far]})


def test_boolean_guard_asks_before_more_than_200_bodies() -> None:
    many = [geo.sphere((i * 3.0, 0.0, 0.0), 1.0) for i in range(201)]
    with pytest.raises(NeedsConfirmationError, match="201 bodies"):
        run("union", {"bodies": many})
    ok = run("union", {"bodies": many[:200]})["body"]
    assert len(geo.solids_of(ok)) == 200
    res = (
        Evaluator()
        .evaluate(
            graph(
                ("n1", "lattice", {"cell": p(1), "radius": p(0.1)}),
                ("n2", "box", {}),
                wires=("n2.body>n1.body",),
            )
        )
        .nodes["n1"]
    )
    assert res.needs_confirmation and "Run Anyway" in (res.error or "")


def test_transforms_take_curves_and_bodies() -> None:
    box = geo.box(XY_PLANE, 1, 1, 1)
    moved = run("move", {"geometry": box, "vector": (5.0, 0.0, 0.0)})["out"]
    assert geo.bounds(moved)[0][0] == pytest.approx(5)
    turned = run("rotate", {"geometry": box, "angle": math.pi / 2})["out"]
    assert geo.bounds(turned)[0][0] == pytest.approx(-1)
    big = run("scale", {"geometry": box, "factor": 2.0})["out"]
    assert geo.volume(big) == pytest.approx(8)
    flipped = run("mirror", {"geometry": box, "plane": make_plane((0, 0, 0), (1, 0, 0))})["out"]
    assert geo.bounds(flipped)[0][0] == pytest.approx(-1)
    copies = run("array", {"geometry": box, "step": (2.0, 0.0, 0.0), "count": 3})["out"]
    assert len(copies) == 3 and geo.bounds(copies[2])[0][0] == pytest.approx(4)
    curve = run("move", {"geometry": square(), "vector": (0.0, 0.0, 1.0)})["out"]
    assert geo.curve_length(geo.wire_of(curve)) == pytest.approx(140)
    with pytest.raises(NodeError, match="factor"):
        run("scale", {"geometry": box, "factor": 0.0})


# Outputs ----------------------------------------------------------------------------


def test_output_nodes_pass_their_value_through() -> None:
    assert run("set_variable", {"value": 3.0}, {"variable": "W"})["out"] == 3
    with pytest.raises(NodeError, match="Choose"):
        run("set_variable", {"value": 3.0})
    assert run("set_param", {"value": 3.0}, {"feature": "f6", "param": "depth"})["out"] == 3
    with pytest.raises(NodeError, match="Choose"):
        run("set_param", {"value": 3.0}, {"feature": "f6"})
    body = geo.sphere((0, 0, 0), 1)
    assert run("add_as_feature", {"body": body})["out"].IsSame(body)
    two = run("add_as_feature", {"body": [body, geo.sphere((5, 0, 0), 1)]})["out"]
    assert len(geo.solids_of(two)) == 2
    with pytest.raises(NodeError, match="Connect"):
        run("add_as_feature", {"body": []})
    assert run("comment", {}, {"text": "note"}) == {}
