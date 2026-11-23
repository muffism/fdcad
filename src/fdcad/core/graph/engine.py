"""Graph evaluation: cycle detection, lazy recompute and per node errors (PLAN Phase 7).

Each node result is kept under a key made from the node's type, its settings,
what it reads from the part and the keys of the nodes wired into it. After an
edit only nodes whose key changed compute again: the edited node and the nodes
downstream of it. Exceptions never escape; a failed node shows its error and
the nodes that depend on it are skipped.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

import fdcad.core.graph.nodes  # noqa: F401  (registers the node types)
from fdcad.core.document.model import Param
from fdcad.core.graph.model import Graph, Node, Wire
from fdcad.core.graph.nodes.base import (
    NODE_TYPES,
    GraphEnv,
    NeedsConfirmationError,
    NodeContext,
    NodeError,
    NodeType,
    Port,
)
from fdcad.core.graph.types import MAX_LIST_DEPTH, PortType, can_connect, list_depth
from fdcad.core.units import ExpressionError, Kind
from fdcad.core.units import evaluate as evaluate_text

#: Largest graph the editor supports (PLAN Phase 7 performance guard).
MAX_NODES = 500


@dataclass
class NodeResult:
    """What one node produced."""

    outputs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    warning: str | None = None
    #: True when the node waits for the user to confirm a slow step.
    needs_confirmation: bool = False
    #: For a node skipped because an input failed: the node where the error began.
    root: str | None = None
    key: str = ""
    seconds: float = 0.0
    computed: bool = False

    @property
    def ok(self) -> bool:
        """True when the node has outputs."""
        return self.error is None


@dataclass
class GraphResult:
    """Results of one evaluation, by node id."""

    nodes: dict[str, NodeResult] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    computed: list[str] = field(default_factory=list)
    cycle: list[str] = field(default_factory=list)
    cancelled: bool = False
    seconds: float = 0.0

    def first_error(self, nid: str) -> tuple[str, str] | None:
        """The node where the error that stops ``nid`` began, and its message."""
        res = self.nodes.get(nid)
        if res is None or res.error is None:
            return None
        if res.root is not None and res.root in self.nodes:
            root = self.nodes[res.root]
            return res.root, root.error or res.error
        return nid, res.error

    def value(self, nid: str, port: str) -> Any:
        """An output value, or None when the node failed or was skipped."""
        res = self.nodes.get(nid)
        return None if res is None or res.error else res.outputs.get(port)


# Graph structure ----------------------------------------------------------------


def topological_order(graph: Graph) -> tuple[list[str], list[str]]:
    """Node ids in an order where every node comes after its inputs, and the ids
    left over because they sit in or after a loop of wires."""
    ids = [n.id for n in graph.nodes]
    known = set(ids)
    indegree = dict.fromkeys(ids, 0)
    after: dict[str, list[str]] = {nid: [] for nid in ids}
    for w in graph.wires:
        if w.source in known and w.target in known:
            indegree[w.target] += 1
            after[w.source].append(w.target)
    ready = [nid for nid in ids if indegree[nid] == 0]
    order: list[str] = []
    while ready:
        nid = ready.pop(0)
        order.append(nid)
        for nxt in after[nid]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                ready.append(nxt)
    placed = set(order)
    return order, [nid for nid in ids if nid not in placed]


def find_cycle(graph: Graph) -> list[str]:
    """Node ids on a loop of wires, in wire order, or an empty list."""
    after: dict[str, list[str]] = {}
    for w in graph.wires:
        after.setdefault(w.source, []).append(w.target)
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(nid: str) -> list[str]:
        state[nid] = 1
        stack.append(nid)
        for nxt in after.get(nid, []):
            if state.get(nxt) == 1:
                return stack[stack.index(nxt) :]
            if nxt not in state:
                found = visit(nxt)
                if found:
                    return found
        stack.pop()
        state[nid] = 2
        return []

    for n in graph.nodes:
        if n.id not in state:
            found = visit(n.id)
            if found:
                return found
    return []


def upstream(graph: Graph, targets: Iterable[str]) -> set[str]:
    """``targets`` and every node wired into them, directly or not."""
    into: dict[str, list[str]] = {}
    for w in graph.wires:
        into.setdefault(w.target, []).append(w.source)
    seen: set[str] = set()
    todo = list(targets)
    while todo:
        nid = todo.pop()
        if nid in seen:
            continue
        seen.add(nid)
        todo.extend(into.get(nid, []))
    return seen


def downstream(graph: Graph, sources: Iterable[str]) -> set[str]:
    """``sources`` and every node they feed, directly or not."""
    out: dict[str, list[str]] = {}
    for w in graph.wires:
        out.setdefault(w.source, []).append(w.target)
    seen: set[str] = set()
    todo = list(sources)
    while todo:
        nid = todo.pop()
        if nid in seen:
            continue
        seen.add(nid)
        todo.extend(out.get(nid, []))
    return seen


def wire_problem(graph: Graph, wire: Wire) -> str | None:
    """Why ``wire`` cannot be added, or None when it can."""
    src, dst = graph.find(wire.source), graph.find(wire.target)
    if src is None or dst is None:
        return "Both ends of a wire need a node."
    if src.id == dst.id:
        return "A node cannot feed itself. Wire it to another node."
    stype, dtype = NODE_TYPES.get(src.type), NODE_TYPES.get(dst.type)
    if stype is None or dtype is None:
        return "This node type is unknown. Update FDCAD."
    out, inp = stype.output(wire.output), dtype.input(wire.input)
    if out is None or inp is None:
        return "That port does not exist."
    if not can_connect(out.type, inp.type):
        return (
            f"A {out.type.value} output cannot feed a {inp.type.value} input. "
            "Pick a matching input."
        )
    if wire.source in downstream(graph, [wire.target]):
        return "This wire would make a loop. Wire the nodes the other way."
    return None


# Evaluation ---------------------------------------------------------------------


def _jsonable(value: Any) -> Any:
    if isinstance(value, Param):
        return [value.expr, value.value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    return value


def _key(parts: Any) -> str:
    text = json.dumps(_jsonable(parts), sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_PORT_KIND = {PortType.LENGTH: Kind.LENGTH, PortType.ANGLE: Kind.ANGLE}


def _input_value(node: Node, port: Port, env: GraphEnv) -> Any:
    """A typed input value. Formulas are worked out again with the part's current
    variables, so they follow a variable change. Raises ExpressionError."""
    raw = node.params.get(port.name, port.default)
    if isinstance(raw, Param):
        if raw.expr.strip().startswith("="):
            kind = _PORT_KIND.get(port.type, Kind.NUMBER)
            return evaluate_text(raw.expr, kind, env.units, env.variables)
        return raw.value
    if port.type in (PortType.POINT, PortType.VECTOR):
        return _as_points(raw)
    return raw


def _as_points(raw: Any) -> Any:
    """Stored points are JSON lists of three numbers: make them tuples, at any depth."""
    if not isinstance(raw, list):
        return raw
    if len(raw) == 3 and all(isinstance(c, int | float) and not isinstance(c, bool) for c in raw):
        return (float(raw[0]), float(raw[1]), float(raw[2]))
    return [_as_points(v) for v in raw]


def _broadcast(
    ntype: NodeType, args: dict[str, Any], ctx: NodeContext, depth: int = 0
) -> dict[str, Any]:
    """Run ``compute``, once per item when a single value input is given a list."""
    mapped = [
        p.name
        for p in ntype.inputs
        if not p.whole_list and p.type is not PortType.LIST and isinstance(args.get(p.name), list)
    ]
    if not mapped:
        return ntype.compute(args, ctx)
    if depth >= MAX_LIST_DEPTH:
        raise NodeError("Lists can be nested at most two levels deep. Flatten the list first.")
    count = max(len(args[name]) for name in mapped)
    if any(len(args[name]) == 0 for name in mapped):
        count = 0
    outs: dict[str, list[Any]] = {p.name: [] for p in ntype.outputs}
    for i in range(count):
        if ctx.cancelled():
            raise _CancelledError
        item = dict(args)
        for name in mapped:
            values = args[name]
            item[name] = values[min(i, len(values) - 1)]
        result = _broadcast(ntype, item, ctx, depth + 1)
        for name in outs:
            outs[name].append(result.get(name))
    return dict(outs)


class _CancelledError(Exception):
    pass


class Evaluator:
    """Evaluates graphs and keeps node results for the next evaluation.

    Safe to share between threads: evaluations take turns.
    """

    def __init__(self, capacity: int = 4000) -> None:
        self.capacity = capacity
        self._cache: OrderedDict[str, NodeResult] = OrderedDict()
        self._lock = threading.Lock()

    def clear(self) -> None:
        """Forget every kept result."""
        with self._lock:
            self._cache.clear()

    def evaluate(
        self,
        graph: Graph,
        env: GraphEnv | None = None,
        cancelled: Callable[[], bool] = lambda: False,
        targets: Iterable[str] | None = None,
    ) -> GraphResult:
        """Bring the graph's results up to date.

        ``targets`` limits the work to those nodes and what feeds them.
        """
        with self._lock:
            return self._evaluate(graph, env or GraphEnv(), cancelled, targets)

    def _evaluate(
        self,
        graph: Graph,
        env: GraphEnv,
        cancelled: Callable[[], bool],
        targets: Iterable[str] | None,
    ) -> GraphResult:
        started = time.perf_counter()
        result = GraphResult()
        if len(graph.nodes) > MAX_NODES:
            # The limit was kept by the panel only; a hand edited file ran any size
            # (audit E item 10.3, D746).
            message = (
                f"The graph has {len(graph.nodes)} nodes, more than {MAX_NODES}. "
                "Delete nodes, or split the work into two graphs."
            )
            for node in graph.nodes:
                result.nodes[node.id] = NodeResult(error=message)
            result.seconds = time.perf_counter() - started
            return result
        order, looped = topological_order(graph)
        result.order = order
        if looped:
            result.cycle = find_cycle(graph) or looped
            for nid in looped:
                result.nodes[nid] = NodeResult(
                    error="This node is on a loop of wires. Remove a wire to break the loop."
                )
        wanted = upstream(graph, targets) if targets is not None else None
        into: dict[str, list[Wire]] = {}
        for w in graph.wires:
            into.setdefault(w.target, []).append(w)
        for nid in order:
            if wanted is not None and nid not in wanted:
                continue
            if cancelled():
                result.cancelled = True
                break
            node = graph.node(nid)
            try:
                res = self._node(graph, node, into.get(nid, []), result, env, cancelled)
            except _CancelledError:
                result.cancelled = True
                break
            result.nodes[nid] = res
            if res.computed:
                result.computed.append(nid)
        result.seconds = time.perf_counter() - started
        return result

    def _node(
        self,
        graph: Graph,
        node: Node,
        wires: list[Wire],
        result: GraphResult,
        env: GraphEnv,
        cancelled: Callable[[], bool],
    ) -> NodeResult:
        ntype = NODE_TYPES.get(node.type)
        if ntype is None:
            return NodeResult(
                error=f"'{node.type}' is a node type this version of FDCAD does not know. "
                "Update FDCAD."
            )
        args: dict[str, Any] = {}
        types: dict[str, PortType] = {}
        deps: list[tuple[str, str, str, str]] = []
        for port in ntype.inputs:
            feeding = [w for w in wires if w.input == port.name]
            if not feeding:
                try:
                    args[port.name] = _input_value(node, port, env)
                except ExpressionError as exc:
                    return NodeResult(error=f"Input '{port.title}': {exc} Fix the value.")
                continue
            values: list[Any] = []
            for w in feeding:
                upstream_res = result.nodes.get(w.source)
                if upstream_res is None or upstream_res.error is not None:
                    src = graph.find(w.source)
                    src_kind = NODE_TYPES.get(src.type) if src is not None else None
                    # The editor shows node titles, not type names.
                    label = (
                        src_kind.title
                        if src_kind is not None
                        else (src.type if src is not None else w.source)
                    )
                    return NodeResult(
                        error=f"Input '{port.title}' comes from the {label} node, which has an "
                        "error. Fix that node first.",
                        root=(upstream_res.root if upstream_res else None) or w.source,
                    )
                if w.output not in upstream_res.outputs:
                    return NodeResult(
                        error=f"Input '{port.title}' is wired to a missing output. Rewire it."
                    )
                values.append(upstream_res.outputs[w.output])
                deps.append((port.name, w.source, w.output, upstream_res.key))
                src_node = graph.find(w.source)
                src_type = NODE_TYPES.get(src_node.type) if src_node is not None else None
                out_port = src_type.output(w.output) if src_type is not None else None
                if out_port is not None:
                    types[port.name] = out_port.type
            if len(values) == 1:
                args[port.name] = values[0]
            else:  # several wires into one input make a list
                merged: list[Any] = []
                for v in values:
                    merged.extend(v if isinstance(v, list) else [v])
                args[port.name] = merged
        for w in wires:
            if ntype.input(w.input) is None:
                return NodeResult(
                    error=f"A wire ends at '{w.input}', which this node does not have. "
                    "Delete the wire."
                )
        formulas = any(
            isinstance(v, Param) and v.expr.strip().startswith("=") for v in node.params.values()
        )
        used = sorted((k, v[1]) for k, v in env.variables.items()) if formulas else None
        key = _key(
            [
                node.type,
                node.params,
                ntype.env_key(node, env),
                sorted(deps),
                graph.seed,
                node.id,
                used,
            ]
        )
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return NodeResult(
                outputs=cached.outputs,
                error=cached.error,
                warning=cached.warning,
                needs_confirmation=cached.needs_confirmation,
                key=key,
            )
        ctx = NodeContext(node, env, graph.seed, types, cancelled)
        t0 = time.perf_counter()
        res = NodeResult(key=key, computed=True)
        try:
            outputs = _broadcast(ntype, args, ctx)
            for value in outputs.values():
                if list_depth(value) > MAX_LIST_DEPTH:
                    raise NodeError(
                        "Lists can be nested at most two levels deep. Flatten the list first."
                    )
            res.outputs = outputs
        except _CancelledError:
            raise
        except NeedsConfirmationError as exc:
            res.error, res.needs_confirmation = str(exc), True
        except NodeError as exc:
            res.error = str(exc)
        except Exception as exc:  # kernel or unexpected failure: never crash the app
            res.error = (
                f"This node failed in the geometry kernel ({type(exc).__name__}). "
                "Change its inputs slightly."
            )
        if ctx.warnings:
            res.warning = " ".join(dict.fromkeys(ctx.warnings))
        res.seconds = time.perf_counter() - t0
        if not cancelled():
            self._cache[key] = res
            while len(self._cache) > self.capacity:
                self._cache.popitem(last=False)
        return res


#: One evaluator shared by the rebuild and the editor, so both reuse results.
SHARED = Evaluator()


def evaluate(
    graph: Graph,
    env: GraphEnv | None = None,
    cancelled: Callable[[], bool] = lambda: False,
    targets: Iterable[str] | None = None,
) -> GraphResult:
    """Evaluate with the shared evaluator."""
    return SHARED.evaluate(graph, env, cancelled, targets)
