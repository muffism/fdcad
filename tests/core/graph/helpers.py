"""Small builders for graph tests."""

from __future__ import annotations

from typing import Any

from fdcad.core.document.model import Param
from fdcad.core.graph.model import Graph, Node, Wire


def p(value: float, expr: str | None = None) -> Param:
    """A parameter object."""
    return Param(expr if expr is not None else f"{value:g}", float(value))


def graph(*nodes: tuple[str, str, dict[str, Any]], wires: tuple[str, ...] = ()) -> Graph:
    """A graph from ``(id, type, params)`` tuples and ``"n1.out>n2.a"`` wires."""
    g = Graph("g1", "Graph 1")
    for nid, ntype, params in nodes:
        g.nodes.append(Node(nid, ntype, dict(params)))
    for text in wires:
        a, b = text.split(">")
        s, o = a.split(".")
        t, i = b.split(".")
        g.wires.append(Wire(s, o, t, i))
    g.next_node = len(nodes) + 1
    return g
