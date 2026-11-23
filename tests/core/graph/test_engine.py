"""Graph engine: order, cycle detection, lazy evaluation, errors, cancel, worker."""

from __future__ import annotations

import threading
import time

import pytest

from fdcad.core.graph.engine import (
    MAX_NODES,
    Evaluator,
    downstream,
    find_cycle,
    topological_order,
    upstream,
    wire_problem,
)
from fdcad.core.graph.model import Node, Wire
from fdcad.core.graph.nodes import NODE_TYPES, catalog
from fdcad.core.graph.types import PortType, can_connect
from fdcad.core.graph.worker import GraphWorker
from tests.core.graph.helpers import graph, p


def _chain() -> object:
    return graph(
        ("n1", "value", {"value": p(2)}),
        ("n2", "value", {"value": p(3)}),
        ("n3", "arithmetic", {"operation": "add"}),
        ("n4", "arithmetic", {"operation": "multiply", "b": p(10)}),
        wires=("n1.out>n3.a", "n2.out>n3.b", "n3.out>n4.a"),
    )


def test_evaluates_in_wire_order() -> None:
    g = _chain()
    order, looped = topological_order(g)  # type: ignore[arg-type]
    assert looped == []
    assert order.index("n3") > order.index("n1") and order.index("n4") > order.index("n3")
    result = Evaluator().evaluate(g)  # type: ignore[arg-type]
    assert result.value("n4", "out") == 50.0


def test_only_downstream_nodes_recompute_after_a_change() -> None:
    g = _chain()
    ev = Evaluator()
    first = ev.evaluate(g)  # type: ignore[arg-type]
    assert sorted(first.computed) == ["n1", "n2", "n3", "n4"]
    g.node("n2").params["value"] = p(5)  # type: ignore[attr-defined]
    second = ev.evaluate(g)  # type: ignore[arg-type]
    assert sorted(second.computed) == ["n2", "n3", "n4"]
    assert second.value("n4", "out") == 70.0
    assert ev.evaluate(g).computed == []  # type: ignore[arg-type]
    g.node("n1").x = 500  # type: ignore[attr-defined]
    assert ev.evaluate(g).computed == []  # type: ignore[arg-type]


def test_input_formulas_follow_the_variables() -> None:
    from fdcad.core.graph.nodes.base import GraphEnv
    from fdcad.core.units import Kind

    g = graph(("n1", "arithmetic", {"operation": "add", "a": p(10, "=R * 2"), "b": p(1)}))
    ev = Evaluator()
    first = ev.evaluate(g, GraphEnv(variables={"R": (Kind.NUMBER, 5.0)}))  # type: ignore[arg-type]
    assert first.value("n1", "out") == 11.0
    # The stored value is still 10: the formula is worked out again with R = 3.
    later = ev.evaluate(g, GraphEnv(variables={"R": (Kind.NUMBER, 3.0)}))  # type: ignore[arg-type]
    assert later.value("n1", "out") == 7.0
    gone = ev.evaluate(g, GraphEnv())  # type: ignore[arg-type]
    error = gone.nodes["n1"].error
    assert error is not None and "Unknown variable 'R'" in error and "Fix the value" in error


def test_targets_limit_the_work() -> None:
    g = _chain()
    g.nodes.append(Node("n5", "value", {"value": p(1)}))  # type: ignore[attr-defined]
    result = Evaluator().evaluate(g, targets=["n3"])  # type: ignore[arg-type]
    assert set(result.nodes) == {"n1", "n2", "n3"}
    assert upstream(g, ["n4"]) == {"n1", "n2", "n3", "n4"}  # type: ignore[arg-type]
    assert downstream(g, ["n2"]) == {"n2", "n3", "n4"}  # type: ignore[arg-type]


def test_cycles_are_detected_and_reported_per_node() -> None:
    g = graph(
        ("n1", "arithmetic", {}),
        ("n2", "arithmetic", {}),
        ("n3", "arithmetic", {}),
        ("n4", "value", {"value": p(1)}),
        wires=("n1.out>n2.a", "n2.out>n3.a", "n3.out>n1.a"),
    )
    assert set(find_cycle(g)) == {"n1", "n2", "n3"}
    result = Evaluator().evaluate(g)
    assert set(result.cycle) == {"n1", "n2", "n3"}
    for nid in ("n1", "n2", "n3"):
        assert "loop" in (result.nodes[nid].error or "")
    assert result.value("n4", "out") == 1.0


def test_wire_problem_blocks_loops_bad_types_and_self() -> None:
    g = _chain()
    assert wire_problem(g, Wire("n4", "out", "n1", "value")) is not None  # value has no input
    assert "loop" in (wire_problem(g, Wire("n4", "out", "n3", "a")) or "")  # type: ignore[arg-type]
    assert "itself" in (wire_problem(g, Wire("n3", "out", "n3", "b")) or "")  # type: ignore[arg-type]
    g.nodes.append(Node("n9", "sphere", {}))  # type: ignore[attr-defined]
    assert "cannot feed" in (wire_problem(g, Wire("n9", "body", "n4", "b")) or "")  # type: ignore[arg-type]
    assert wire_problem(g, Wire("n1", "out", "n4", "b")) is None  # type: ignore[arg-type]


def test_port_rules() -> None:
    assert can_connect(PortType.LENGTH, PortType.NUMBER)
    assert can_connect(PortType.POINT, PortType.VECTOR)
    assert can_connect(PortType.CURVE, PortType.BODY)
    assert can_connect(PortType.BODY, PortType.LIST)
    assert not can_connect(PortType.BODY, PortType.NUMBER)
    assert not can_connect(PortType.PLANE, PortType.POINT)


def test_errors_stay_on_their_node_and_skip_dependents() -> None:
    g = graph(
        ("n1", "value", {"value": p(0)}),
        ("n2", "arithmetic", {"operation": "divide", "a": p(1)}),
        ("n3", "arithmetic", {}),
        ("n4", "value", {"value": p(7)}),
        wires=("n1.out>n2.b", "n2.out>n3.a"),
    )
    result = Evaluator().evaluate(g)
    assert "zero" in (result.nodes["n2"].error or "")
    assert "from the Arithmetic node, which has an error" in (result.nodes["n3"].error or "")
    assert result.value("n4", "out") == 7.0


def test_kernel_exceptions_become_node_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object) -> dict[str, object]:
        raise RuntimeError("kernel")

    monkeypatch.setattr(NODE_TYPES["sphere"], "compute", boom)
    result = Evaluator().evaluate(graph(("n1", "sphere", {})))
    assert "geometry kernel" in (result.nodes["n1"].error or "")


def test_wire_to_missing_port_is_an_error() -> None:
    g = graph(("n1", "value", {}), ("n2", "arithmetic", {}), wires=("n1.out>n2.zz",))
    assert "does not have" in (Evaluator().evaluate(g).nodes["n2"].error or "")


def test_lists_run_a_node_once_per_item_and_nesting_is_limited() -> None:
    g = graph(
        ("n1", "range", {"start": p(0), "end": p(4), "count": p(5)}),
        ("n2", "arithmetic", {"operation": "multiply", "b": p(2)}),
        wires=("n1.out>n2.a",),
    )
    assert Evaluator().evaluate(g).value("n2", "out") == [0.0, 2.0, 4.0, 6.0, 8.0]
    g2 = graph(
        ("n1", "range", {"count": p(2)}),
        ("n2", "range", {"count": p(2)}),
        ("n3", "range", {"count": p(3)}),
        ("n4", "arithmetic", {}),
        wires=("n1.out>n4.a", "n2.out>n4.b"),
    )
    assert Evaluator().evaluate(g2).value("n4", "out") == [0.0, 20.0]


def test_cancel_stops_the_evaluation() -> None:
    g = _chain()
    calls = {"n": 0}

    def cancelled() -> bool:
        calls["n"] += 1
        return calls["n"] > 2

    result = Evaluator().evaluate(g, cancelled=cancelled)  # type: ignore[arg-type]
    assert result.cancelled
    assert len(result.nodes) < 4


def test_background_worker_runs_and_newer_work_cancels_older() -> None:
    worker = GraphWorker(Evaluator())
    try:
        done = threading.Event()
        seen: list[object] = []
        future = worker.submit(_chain(), done=lambda r: (seen.append(r), done.set()))  # type: ignore[arg-type]
        assert future.result(timeout=10).value("n4", "out") == 50.0
        assert done.wait(5) and seen
        big = graph(
            ("n1", "point_grid", {"count_x": p(300), "count_y": p(300)}),
            ("n2", "sphere", {"radius": p(0.1)}),
            wires=("n1.out>n2.centre",),
        )
        slow = worker.submit(big)
        fast = worker.submit(_chain())  # type: ignore[arg-type]
        assert slow.result(timeout=60).cancelled
        assert fast.result(timeout=10).value("n4", "out") == 50.0
    finally:
        worker.shutdown()


def test_unknown_node_type_is_an_error_not_a_crash() -> None:
    result = Evaluator().evaluate(graph(("n1", "teleporter", {})))
    assert "Update FDCAD" in (result.nodes["n1"].error or "")


def test_every_node_type_is_well_formed() -> None:
    names = set()
    for t in catalog():
        assert t.type_name not in names
        names.add(t.type_name)
        assert t.title and t.category
        ports = [p.name for p in t.inputs] + [p.name for p in t.outputs]
        assert len(set(p.name for p in t.inputs)) == len(t.inputs)
        assert len(set(p.name for p in t.outputs)) == len(t.outputs)
        assert all("-" not in n for n in ports)
    assert {"slider", "union", "voronoi", "lattice", "add_as_feature", "set_param"} <= names


def test_500_node_graph_evaluates_quickly() -> None:
    nodes = [("n1", "value", {"value": p(1)})]
    wires = []
    for i in range(2, MAX_NODES + 1):
        nodes.append((f"n{i}", "arithmetic", {"b": p(1)}))
        wires.append(f"n{i - 1}.out>n{i}.a")
    g = graph(*nodes, wires=tuple(wires))
    ev = Evaluator()
    t0 = time.perf_counter()
    result = ev.evaluate(g)
    assert time.perf_counter() - t0 < 2.0
    assert result.value(f"n{MAX_NODES}", "out") == float(MAX_NODES)
    g.node(f"n{MAX_NODES - 1}").params["b"] = p(2)
    t0 = time.perf_counter()
    again = ev.evaluate(g)
    assert time.perf_counter() - t0 < 0.5
    assert sorted(again.computed) == [f"n{MAX_NODES - 1}", f"n{MAX_NODES}"]


def test_fdef_spec_lists_every_node_type() -> None:
    from pathlib import Path

    spec = (Path(__file__).resolve().parents[3] / "FDEF_SPEC.md").read_text(encoding="utf-8")
    section = spec[spec.index("## 12A.") : spec.index("## 13.")]
    for t in catalog():
        assert f"- `{t.type_name}`:" in section, t.type_name


def test_a_graph_over_the_node_limit_is_refused() -> None:
    """Audit E item 10.3 (D746): only the panel kept the 500 node limit."""
    from fdcad.core.graph.engine import MAX_NODES, Evaluator

    g = graph(*[(f"n{k}", "number", {"value": p(1.0)}) for k in range(MAX_NODES + 1)])
    result = Evaluator().evaluate(g)
    assert all("more than 500" in (r.error or "") for r in result.nodes.values())
    assert len(result.nodes) == MAX_NODES + 1
