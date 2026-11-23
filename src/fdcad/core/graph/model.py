"""The graph as stored in a part (FDEF_SPEC 12A): nodes, wires, groups and a seed.

Plain data only. Opening a file never runs code (CLAUDE.md rule 10): a graph is
read as JSON and every node type must be one of the built in types.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from fdcad.core.document.model import Param


@dataclass
class Node:
    """One node: its type, its settings and where it sits in the editor."""

    id: str
    type: str
    params: dict[str, Any] = field(default_factory=dict)
    x: float = 0.0
    y: float = 0.0
    #: Keys a newer FDCAD wrote on the node and in its ``ui``, kept for saving (D726).
    extra: dict[str, Any] = field(default_factory=dict)
    ui_extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Wire:
    """A connection from an output port to an input port."""

    source: str  # node id
    output: str  # port name
    target: str  # node id
    input: str  # port name

    @property
    def text(self) -> tuple[str, str]:
        """``("n1.out", "n2.radius")`` as written in the file."""
        return (f"{self.source}.{self.output}", f"{self.target}.{self.input}")


@dataclass
class Group:
    """A named frame around some nodes in the editor. Display only."""

    id: str
    name: str
    nodes: list[str] = field(default_factory=list)


@dataclass
class Graph:
    """A node graph. ``position`` is the feature after which it is evaluated (D26)."""

    id: str
    name: str
    position: str | None = None
    next_node: int = 1
    nodes: list[Node] = field(default_factory=list)
    wires: list[Wire] = field(default_factory=list)
    groups: list[Group] = field(default_factory=list)
    seed: int = 1
    extra: dict[str, Any] = field(default_factory=dict)

    def new_node_id(self) -> str:
        """The next node id. Ids are never reused."""
        nid = f"n{self.next_node}"
        self.next_node += 1
        return nid

    def new_group_id(self) -> str:
        """The next group id, from the same counter as nodes."""
        gid = f"k{self.next_node}"
        self.next_node += 1
        return gid

    def node(self, nid: str) -> Node:
        """The node with id ``nid``. Raises KeyError."""
        for n in self.nodes:
            if n.id == nid:
                return n
        raise KeyError(nid)

    def find(self, nid: str) -> Node | None:
        """The node with id ``nid``, or None."""
        return next((n for n in self.nodes if n.id == nid), None)

    def wires_into(self, nid: str) -> list[Wire]:
        """Wires that end at node ``nid``."""
        return [w for w in self.wires if w.target == nid]

    def wires_from(self, nid: str) -> list[Wire]:
        """Wires that start at node ``nid``."""
        return [w for w in self.wires if w.source == nid]

    def remove_nodes(self, ids: set[str]) -> None:
        """Remove nodes, their wires and their group memberships."""
        self.nodes = [n for n in self.nodes if n.id not in ids]
        self.wires = [w for w in self.wires if w.source not in ids and w.target not in ids]
        for g in self.groups:
            g.nodes = [n for n in g.nodes if n not in ids]

    def copy(self) -> Graph:
        """A deep copy, for editing commands."""
        return copy.deepcopy(self)


class GraphFormatError(ValueError):
    """A stored graph is damaged. The message is shown to the user."""


def _damaged(what: str) -> GraphFormatError:
    return GraphFormatError(f"The file is damaged: {what}.")


def _value_from_json(raw: Any) -> Any:
    if isinstance(raw, dict) and set(raw) == {"expr", "value"}:
        expr, value = raw["expr"], raw["value"]
        if (
            not isinstance(expr, str)
            or isinstance(value, bool)
            or not isinstance(value, int | float)
        ):
            raise _damaged("a graph node has an invalid expression or value")
        return Param(expr, float(value))
    if isinstance(raw, dict):
        return {str(k): _value_from_json(v) for k, v in raw.items()}
    if isinstance(raw, list):
        return [_value_from_json(v) for v in raw]
    if raw is None or isinstance(raw, str | bool | int | float):
        return raw
    raise _damaged("a graph node has an unsupported value")


def _value_to_json(value: Any) -> Any:
    if isinstance(value, Param):
        return {"expr": value.expr, "value": value.value}
    if isinstance(value, dict):
        return {k: _value_to_json(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_value_to_json(v) for v in value]
    return value


def _split_port(text: Any) -> tuple[str, str]:
    if not isinstance(text, str) or text.count(".") != 1:
        raise _damaged("a graph wire has an invalid end")
    node, port = text.split(".")
    if not node or not port:
        raise _damaged("a graph wire has an invalid end")
    return node, port


_NODE_KEYS = ("id", "type", "params", "ui")
_GRAPH_KEYS = ("id", "name", "position", "next_node", "nodes", "wires", "groups", "seed")


def node_to_json(node: Node) -> dict[str, Any]:
    """One node as JSON data, keys in spec order."""
    out: dict[str, Any] = {
        "id": node.id,
        "type": node.type,
        "params": _value_to_json(node.params),
        "ui": {"x": node.x, "y": node.y, **copy.deepcopy(node.ui_extra)},
    }
    for key, value in node.extra.items():
        out.setdefault(key, copy.deepcopy(value))
    return out


def node_from_json(raw: Any) -> Node:
    """Read one node. Raises GraphFormatError."""
    if not isinstance(raw, dict):
        raise _damaged("a graph node is not an object")
    nid, ntype = raw.get("id"), raw.get("type")
    if not isinstance(nid, str) or not isinstance(ntype, str):
        raise _damaged("a graph node has no valid id or type")
    params = raw.get("params", {})
    ui = raw.get("ui", {})
    if not isinstance(params, dict) or not isinstance(ui, dict):
        raise _damaged(f"graph node {nid} has invalid params")
    x, y = ui.get("x", 0), ui.get("y", 0)
    if (
        isinstance(x, bool)
        or isinstance(y, bool)
        or not isinstance(x, int | float)
        or not isinstance(y, int | float)
    ):
        raise _damaged(f"graph node {nid} has an invalid position")
    return Node(
        nid,
        ntype,
        _value_from_json(params),
        float(x),
        float(y),
        {k: copy.deepcopy(v) for k, v in raw.items() if k not in _NODE_KEYS},
        {k: copy.deepcopy(v) for k, v in ui.items() if k not in ("x", "y")},
    )


def graph_to_json(graph: Graph) -> dict[str, Any]:
    """One graph as JSON data, keys in spec order, unknown keys last."""
    out: dict[str, Any] = {
        "id": graph.id,
        "name": graph.name,
        "position": graph.position,
        "next_node": graph.next_node,
        "nodes": [node_to_json(n) for n in graph.nodes],
        "wires": [{"from": w.text[0], "to": w.text[1]} for w in graph.wires],
        "groups": [{"id": g.id, "name": g.name, "nodes": list(g.nodes)} for g in graph.groups],
        "seed": graph.seed,
    }
    for key, value in graph.extra.items():
        if key not in out:
            out[key] = copy.deepcopy(value)
    return out


def graph_from_json(raw: Any) -> Graph:
    """Read one graph. Raises GraphFormatError. Never runs code."""
    if not isinstance(raw, dict):
        raise _damaged("a graph is not an object")
    gid, name = raw.get("id"), raw.get("name")
    if not isinstance(gid, str) or not isinstance(name, str):
        raise _damaged("a graph has no valid id or name")
    position = raw.get("position")
    if position is not None and not isinstance(position, str):
        raise _damaged(f"graph {gid} has an invalid position")
    next_node, seed = raw.get("next_node", 1), raw.get("seed", 1)
    for key, value in (("next_node", next_node), ("seed", seed)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise _damaged(f"graph {gid} has an invalid '{key}'")
    nodes_raw, wires_raw, groups_raw = (
        raw.get("nodes", []),
        raw.get("wires", []),
        raw.get("groups", []),
    )
    if not all(isinstance(v, list) for v in (nodes_raw, wires_raw, groups_raw)):
        raise _damaged(f"graph {gid} has invalid lists")
    nodes = [node_from_json(n) for n in nodes_raw]
    ids = {n.id for n in nodes}
    if len(ids) != len(nodes):
        raise _damaged(f"graph {gid} has two nodes with the same id")
    wires: list[Wire] = []
    for w in wires_raw:
        if not isinstance(w, dict):
            raise _damaged(f"graph {gid} has an invalid wire")
        src, out = _split_port(w.get("from"))
        dst, inp = _split_port(w.get("to"))
        if src not in ids or dst not in ids:
            raise _damaged(f"graph {gid} has a wire to a missing node")
        wires.append(Wire(src, out, dst, inp))
    groups: list[Group] = []
    for g in groups_raw:
        if not isinstance(g, dict) or not isinstance(g.get("id"), str):
            raise _damaged(f"graph {gid} has an invalid group")
        members = g.get("nodes", [])
        if not isinstance(members, list) or not all(isinstance(m, str) for m in members):
            raise _damaged(f"graph {gid} has an invalid group")
        groups.append(Group(g["id"], str(g.get("name", "")), [m for m in members if m in ids]))
    return Graph(
        id=gid,
        name=name,
        position=position,
        next_node=next_node,
        nodes=nodes,
        wires=wires,
        groups=groups,
        seed=seed,
        extra={k: copy.deepcopy(v) for k, v in raw.items() if k not in _GRAPH_KEYS},
    )


def new_graph(gid: str = "g1", name: str = "Graph 1", position: str | None = None) -> Graph:
    """An empty graph."""
    return Graph(gid, name, position)
