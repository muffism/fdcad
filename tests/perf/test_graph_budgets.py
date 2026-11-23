"""Node editor budgets (PLAN Phase 7 performance guard, section 11)."""

from __future__ import annotations

import time

import pytest

from fdcad.core.graph.drive import make_env
from fdcad.core.graph.engine import MAX_NODES, Evaluator
from fdcad.core.graph.model import Graph, Node, Wire
from fdcad.core.io import fdef
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.samples.graphs import GRAPH_SAMPLES, SAMPLE_DIR

MARGIN = 1.5


@pytest.mark.parametrize("name", sorted(GRAPH_SAMPLES))
def test_sample_preview_under_one_second(name: str) -> None:
    """A full preview of each sample graph from scratch takes under 1 s."""
    doc = fdef.load(SAMPLE_DIR / f"{name}.fdprt")
    report = RebuildEngine().rebuild(doc)
    graph = doc.graphs[0]
    env = make_env(doc, graph, report.results, {})
    start = time.perf_counter()
    result = Evaluator().evaluate(graph, env)
    elapsed = time.perf_counter() - start
    assert all(r.error is None for r in result.nodes.values())
    assert elapsed < 1.0 * MARGIN, elapsed


def _big_graph() -> Graph:
    g = Graph("g1", "Graph 1")
    g.nodes.append(Node("n1", "value", {}))
    for i in range(2, MAX_NODES + 1):
        g.nodes.append(Node(f"n{i}", "arithmetic", {}, x=(i % 25) * 200.0, y=(i // 25) * 120.0))
        g.wires.append(Wire(f"n{i - 1}", "out", f"n{i}", "a"))
    g.next_node = MAX_NODES + 1
    return g


def test_500_node_graph_evaluates_and_draws(qtbot: object) -> None:
    """Graphs up to 500 nodes stay responsive: evaluate and draw each in under 1 s."""
    from fdcad.ui.node_editor.scene import NodeScene

    graph = _big_graph()
    start = time.perf_counter()
    result = Evaluator().evaluate(graph)
    assert time.perf_counter() - start < 1.0 * MARGIN
    scene = NodeScene()
    start = time.perf_counter()
    scene.show_graph(graph, result)
    assert time.perf_counter() - start < 1.0 * MARGIN
    assert len(scene.items_by_id) == MAX_NODES
