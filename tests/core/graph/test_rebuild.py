"""Graphs in the rebuild: graph body features, driven values and the cycle rule."""

from __future__ import annotations

from fdcad.core.document.model import Document, Feature, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.graph.drive import cycle_problems, make_env, position_index
from fdcad.core.graph.engine import Evaluator
from fdcad.core.graph.geometry import volume
from fdcad.core.graph.model import Graph
from fdcad.core.io import fdef
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.samples.builder import (
    FRONT,
    SketchBuilder,
    add_feature,
    add_sketch,
    add_variables,
    length,
)
from tests.core.graph.helpers import graph, p


def _plate(doc: Document, depth: str = "10") -> tuple[str, str]:
    sk = SketchBuilder()
    sk.rectangle(0, 0, 40, 30, "40", "30")
    sid = add_sketch(doc, sk, {"feature": FRONT}, "Sketch 1")
    fid = add_feature(
        doc, "extrude", "Extrude 1", sid, operation="boss", end_condition="blind",
        depth=length(depth, 10.0 if depth == "10" else 0.0), reverse=False,
    )  # fmt: skip
    return sid, fid


def _graph_body(doc: Document, g: Graph, output: str) -> str:
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid, "graph_body", "Graph Body 1", refs={"graph": {"graph": g.id, "output": output}}
        )
    )
    return fid


def test_graph_body_subtracts_holes_from_the_part() -> None:
    doc = new_document()
    _sid, plate = _plate(doc)
    g = graph(
        (
            "n1",
            "point_grid",
            {"count_x": p(3), "count_y": p(2), "spacing_x": p(10), "spacing_y": p(10)},
        ),
        ("n2", "cylinder", {"radius": p(2), "height": p(10)}),
        ("n3", "add_as_feature", {"operation": "subtract"}),
        wires=("n1.out>n2.base", "n2.body>n3.body"),
    )
    g.nodes[0].params["plane"] = None
    g.position = plate
    doc.graphs.append(g)
    gb = _graph_body(doc, g, "n3")
    engine = RebuildEngine()
    report = engine.rebuild(doc)
    res = report.results[gb]
    assert res.state is FeatureState.OK, res.issues
    # Grid points on the plate edges cut half holes, the corner one a quarter: 3.75 holes.
    expected = 40 * 30 * 10 - 3.75 * 3.14159265 * 4 * 10
    assert abs(volume(report.body.shape) - expected) < 0.01  # type: ignore[union-attr]
    names = [n for n, _f in report.body.faces]  # type: ignore[union-attr]
    assert any(n.startswith(f"{gb}/face/") for n in names)
    again = engine.rebuild(doc)
    assert gb in again.reused
    g.node("n2").x = 300.0  # moving a node in the editor changes nothing
    assert gb in engine.rebuild(doc).reused
    g.node("n2").params["radius"] = p(1)
    third = engine.rebuild(doc)
    assert gb in third.rebuilt
    loaded = fdef.loads(fdef.dumps(doc))
    assert RebuildEngine().rebuild(loaded).results[gb].state is FeatureState.OK


def test_new_body_and_add_operations() -> None:
    doc = new_document()
    g = graph(
        ("n1", "sphere", {"radius": p(5)}),
        ("n2", "add_as_feature", {"operation": "new"}),
        wires=("n1.body>n2.body",),
    )
    g.position = "f4"
    doc.graphs.append(g)
    gb = _graph_body(doc, g, "n2")
    report = RebuildEngine().rebuild(doc)
    assert report.results[gb].state is FeatureState.OK
    assert abs(volume(report.body.shape) - 4 / 3 * 3.14159265 * 125) < 0.1  # type: ignore[union-attr]


def test_graph_body_reports_graph_errors() -> None:
    doc = new_document()
    g = graph(
        ("n1", "sphere", {"radius": p(-1)}),
        ("n2", "add_as_feature", {}),
        wires=("n1.body>n2.body",),
    )
    g.position = "f4"
    doc.graphs.append(g)
    gb = _graph_body(doc, g, "n2")
    issue = RebuildEngine().rebuild(doc).results[gb].issues[0]
    assert "radius" in issue.message and "Graph 1" in issue.message and "n1" in issue.message
    assert "its Sphere node" in issue.message and "(sphere)" not in issue.message
    missing = new_document()
    missing.features.append(
        Feature("f5", "graph_body", "Graph Body 1", refs={"graph": {"graph": "g9"}})
    )
    assert "missing" in RebuildEngine().rebuild(missing).results["f5"].issues[0].message


def test_set_variable_drives_features_below_the_graph() -> None:
    doc = new_document()
    add_variables(doc, Depth=("10mm", 10.0))
    _sid, plate = _plate(doc, "=Depth")
    g = graph(
        ("n1", "value", {"kind": "length", "value": p(25)}),
        ("n2", "set_variable", {"variable": "Depth"}),
        wires=("n1.out>n2.value",),
    )
    g.position = "f4"  # above the sketch and the extrude
    doc.graphs.append(g)
    report = RebuildEngine().rebuild(doc)
    assert report.results[plate].state is FeatureState.OK
    assert abs(volume(report.body.shape) - 40 * 30 * 25) < 1e-6  # type: ignore[union-attr]
    assert doc.variables[0].expr == "10mm"  # the typed text is never changed
    assert "g1" in report.graphs


def test_set_param_drives_a_feature_parameter() -> None:
    doc = new_document()
    _sid, plate = _plate(doc)
    g = graph(
        ("n1", "slider", {"min": 1, "max": 50, "step": 1, "value": p(12)}),
        ("n2", "set_param", {"feature": plate, "param": "depth"}),
        wires=("n1.out>n2.value",),
    )
    g.position = "f4"
    doc.graphs.append(g)
    report = RebuildEngine().rebuild(doc)
    assert abs(volume(report.body.shape) - 40 * 30 * 12) < 1e-6  # type: ignore[union-attr]


def test_cycle_rule_feature_above_graph_cannot_use_driven_values() -> None:
    doc = new_document()
    add_variables(doc, Depth=("10mm", 10.0), Twice=("=Depth*2", 20.0))
    _sid, plate = _plate(doc, "=Twice")
    g = graph(
        ("n1", "value", {"kind": "length", "value": p(5)}),
        ("n2", "set_variable", {"variable": "Depth"}),
        wires=("n1.out>n2.value",),
    )
    g.position = plate  # the extrude is above the graph, yet uses Depth through Twice
    doc.graphs.append(g)
    problems = cycle_problems(doc)
    assert plate in problems and "above" in problems[plate] and "Twice" in problems[plate]
    report = RebuildEngine().rebuild(doc)
    assert report.results[plate].state is FeatureState.ERROR
    assert "Move Graph 1" in report.results[plate].issues[0].message


def test_cycle_rule_set_param_on_feature_above_and_graph_body_above() -> None:
    doc = new_document()
    _sid, plate = _plate(doc)
    g = graph(
        ("n1", "value", {"value": p(5)}),
        ("n2", "set_param", {"feature": plate, "param": "depth"}),
        ("n3", "sphere", {}),
        ("n4", "add_as_feature", {}),
        wires=("n1.out>n2.value", "n3.body>n4.body"),
    )
    doc.graphs.append(g)
    gb = _graph_body(doc, g, "n4")
    g.position = gb  # at the end: the extrude and the graph body are above it
    problems = cycle_problems(doc)
    assert plate in problems and gb in problems
    report = RebuildEngine().rebuild(doc)
    assert report.results[gb].state is FeatureState.ERROR
    assert report.results[plate].state is FeatureState.ERROR


def test_graph_reads_only_features_above_its_position() -> None:
    doc = new_document()
    _sid, plate = _plate(doc)
    g = Graph("g1", "Graph 1", position="f4")
    doc.graphs.append(g)
    assert position_index(doc, g) == 3
    report = RebuildEngine().rebuild(doc)
    env = make_env(doc, g, report.results, {})
    assert plate not in env.features and env.body is None
    g.position = plate
    env = make_env(doc, g, report.results, {})
    assert plate in env.features and env.body is not None
    read = graph(("n1", "read_param", {"feature": plate, "param": "depth"}))
    assert Evaluator().evaluate(read, env).value("n1", "out") == 10.0
    early = make_env(doc, Graph("g2", "G", position="f4"), report.results, {})
    assert "below" in (Evaluator().evaluate(read, early).nodes["n1"].error or "")


def test_an_added_graph_body_apart_from_the_part_warns() -> None:
    """Audit E item 9.2 (D746): a graph body added to the part never got the separate
    body check, so a lattice that came apart said nothing."""
    doc = new_document()
    sk = SketchBuilder()
    sk.rectangle(100, 100, 40, 30, "40", "30")  # well away from the sphere at the origin
    sid = add_sketch(doc, sk, {"feature": FRONT}, "Sketch 1")
    add_feature(
        doc, "extrude", "Extrude 1", sid, operation="boss", end_condition="blind",
        depth=length("10", 10.0), reverse=False,
    )  # fmt: skip
    g = graph(
        ("n1", "sphere", {"radius": p(5)}),
        ("n2", "add_as_feature", {"operation": "add"}),
        wires=("n1.body>n2.body",),
    )
    g.position = doc.features[-1].id
    doc.graphs.append(g)
    gb = _graph_body(doc, g, "n2")
    issues = RebuildEngine().rebuild(doc).results[gb].issues
    assert any(i.code == "separate_body" for i in issues), [i.message for i in issues]


def test_cycle_rule_reads_an_exponent_as_a_number() -> None:
    # D2633: the cycle rule read every word of a formula as a name, so the exponent
    # of =1e1 was taken for the driven variable e1.
    doc = new_document()
    add_variables(doc, e1=("5mm", 5.0))
    _sid, plate = _plate(doc, "=1e1")
    g = graph(
        ("n1", "value", {"kind": "length", "value": p(5)}),
        ("n2", "set_variable", {"variable": "e1"}),
        wires=("n1.out>n2.value",),
    )
    g.position = plate  # the extrude is above the graph and uses no driven value
    doc.graphs.append(g)
    assert plate not in cycle_problems(doc)
    report = RebuildEngine().rebuild(doc)
    assert report.results[plate].state is not FeatureState.ERROR
