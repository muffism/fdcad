"""Graphs inside the rebuild: their position in the tree, the cycle rule and the
output nodes that drive variables and feature parameters (PLAN Phase 7, D26).

A graph is evaluated during the rebuild right after the feature at its
position. It reads only features at or above that position. Its set variable
and set feature parameter outputs then change values for the features below
it, the same way a changed variable does before a rebuild (``refresh_values``).
The typed text in the part is never changed. A feature at or above the
position that uses a driven value is an error, so the graph and the model can
never feed each other in a loop.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.graph.engine import SHARED, GraphResult
from fdcad.core.graph.model import Graph
from fdcad.core.graph.nodes.base import GraphEnv
from fdcad.core.units import Kind, VariableDef, evaluate_variables
from fdcad.core.units.expressions import references


def position_index(doc: Document, graph: Graph) -> int:
    """Index in the tree of the feature the graph sits after; the end of the tree
    when the position is not set or the feature is gone."""
    if graph.position is not None:
        for i, f in enumerate(doc.features):
            if f.id == graph.position:
                return i
    return len(doc.features) - 1


def graph_of(doc: Document, gid: str) -> Graph | None:
    """The graph with id ``gid``."""
    return next((g for g in doc.graphs if g.id == gid), None)


def make_env(
    doc: Document,
    graph: Graph,
    results: dict[str, Any],
    variables: dict[str, tuple[Kind, float]],
) -> GraphEnv:
    """What the graph may read: features at or above its position only (D26)."""
    last = position_index(doc, graph)
    above = doc.features[: last + 1]
    env = GraphEnv(units=doc.units, variables=dict(variables))
    from fdcad.core.named_items import items as named_items

    env.named = {i["name"].casefold(): i["ref"] for i in named_items(doc)}  # TR152
    for f in above:
        env.features[f.id] = (f.type, f.name, dict(f.params))
        if f.id in results:
            env.results[f.id] = results[f.id]
    for f in reversed(above):
        res = results.get(f.id)
        if res is not None:
            env.body = res.body
            env.body_key = res.key
            break
    return env


@dataclass
class Drive:
    """One output node that drives a value."""

    node: str
    variable: str | None = None
    feature: str | None = None
    param: str | None = None


def drives(graph: Graph) -> list[Drive]:
    """The graph's set variable and set feature parameter nodes."""
    out = []
    for n in graph.nodes:
        if n.type == "set_variable" and n.params.get("variable"):
            out.append(Drive(n.id, variable=str(n.params["variable"])))
        elif n.type == "set_param" and n.params.get("feature") and n.params.get("param"):
            out.append(Drive(n.id, feature=str(n.params["feature"]), param=str(n.params["param"])))
    return out


def _names_in(text: str) -> set[str]:
    # The formula's own tokens: the exponent of =1e1 is not a name e1 (D2633).
    return references(text)


def _expressions(feature: Feature) -> list[str]:
    texts = [v.expr for v in feature.params.values() if isinstance(v, Param)]
    for dim in feature.data.get("dimensions", []) or []:
        param = dim.get("param") if isinstance(dim, dict) else None
        if isinstance(param, Param):
            texts.append(param.expr)
        elif isinstance(param, dict) and isinstance(param.get("expr"), str):
            texts.append(param["expr"])
    return texts


def _dependents(doc: Document, names: set[str]) -> set[str]:
    """``names`` and every variable that uses one of them, directly or not."""
    found = set(names)
    changed = True
    while changed:
        changed = False
        for v in doc.variables:
            if v.name not in found and _names_in(v.expr) & found:
                found.add(v.name)
                changed = True
    return found


def cycle_problems(doc: Document) -> dict[str, str]:
    """Features that break the cycle rule, with the message to show (PLAN Phase 7).

    A feature at or above a graph's position must not use a value the graph
    drives, and a graph body feature must come below its graph.
    """
    problems: dict[str, str] = {}
    for graph in doc.graphs:
        last = position_index(doc, graph)
        ds = drives(graph)
        variables = _dependents(doc, {d.variable for d in ds if d.variable})
        params = {(d.feature, d.param) for d in ds if d.feature}
        for f in doc.features[: last + 1]:
            used = sorted(set().union(*(_names_in(t) for t in _expressions(f))) & variables)
            if used:
                problems[f.id] = (
                    f"{f.name} uses {used[0]}, which {graph.name} sets, but {f.name} is above "
                    f"{graph.name} in the tree. Move {graph.name} above {f.name} or stop using "
                    f"{used[0]} there."
                )
            hit = sorted(str(p) for fid, p in params if fid == f.id)
            if hit:
                problems[f.id] = (
                    f"{graph.name} sets {f.name} {hit[0]}, but {f.name} is above "
                    f"{graph.name} in the tree. Move {graph.name} above {f.name}."
                )
            ref = f.refs.get("graph") if f.type == "graph_body" else None
            if isinstance(ref, dict) and ref.get("graph") == graph.id:
                problems[f.id] = (
                    f"{f.name} uses {graph.name}, so it must be below the graph in the tree. "
                    f"Move {graph.name} above {f.name}."
                )
    return problems


def _override_text(kind: Kind, value: float) -> str:
    unit = {Kind.LENGTH: "mm", Kind.ANGLE: "rad", Kind.NUMBER: ""}[kind]
    return f"{value!r}{unit}"


@dataclass
class GraphDriver:
    """Runs a part's graphs at their positions during one rebuild."""

    doc: Document
    cancelled: Callable[[], bool] = lambda: False
    done: set[str] = field(default_factory=set)
    results: dict[str, GraphResult] = field(default_factory=dict)
    #: Driven parameters: (feature id, parameter) to value.
    params: dict[tuple[str, str], float] = field(default_factory=dict)
    #: Driven variables: name to value.
    variables: dict[str, float] = field(default_factory=dict)
    problems: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.problems = cycle_problems(self.doc)
        self._index = {f.id: i for i, f in enumerate(self.doc.features)}

    def due(self, feature: Feature) -> list[Graph]:
        """Graphs to run before ``feature`` builds: those positioned above it."""
        index = self._index.get(feature.id, len(self.doc.features))
        due = [
            g
            for g in self.doc.graphs
            if g.id not in self.done and position_index(self.doc, g) < index and drives(g)
        ]
        return due

    def run(
        self,
        graph: Graph,
        results: dict[str, Any],
        variables: dict[str, tuple[Kind, float]],
    ) -> dict[str, tuple[Kind, float]] | None:
        """Evaluate ``graph`` and return the new variables, or None when nothing changed."""
        self.done.add(graph.id)
        env = make_env(self.doc, graph, results, variables)
        ds = drives(graph)
        outcome = SHARED.evaluate(graph, env, self.cancelled, targets=[d.node for d in ds])
        self.results[graph.id] = outcome
        blocked = set(self.problems)
        changed = False
        overrides: dict[str, float] = {}
        for d in ds:
            value = outcome.value(d.node, "out")
            if not isinstance(value, float):
                continue
            if d.variable is not None:
                if any(v.name == d.variable for v in self.doc.variables):
                    overrides[d.variable] = value
            elif d.feature is not None and d.param is not None and d.feature not in blocked:
                self.params[(d.feature, d.param)] = value
                changed = True
        if not overrides and not changed:
            return None
        self.variables.update(overrides)
        defs = []
        for v in self.doc.variables:
            if v.name in self.variables:
                defs.append(
                    VariableDef(v.name, v.kind, _override_text(v.kind, self.variables[v.name]))
                )
            else:
                defs.append(VariableDef(v.name, v.kind, v.expr))
        try:
            values = evaluate_variables(defs, self.doc.units)
        except Exception:
            return None
        return {v.name: (v.kind, values[v.name]) for v in self.doc.variables}

    def apply_params(self) -> None:
        """Put driven parameter values into the features below the graphs."""
        for (fid, name), value in self.params.items():
            try:
                feature = self.doc.feature(fid)
            except KeyError:
                continue
            current = feature.params.get(name)
            if isinstance(current, Param):
                current.value = value
