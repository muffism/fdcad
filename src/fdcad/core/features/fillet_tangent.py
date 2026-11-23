"""Fillet and chamfer without tangent propagation (TR131, DECISIONS D1400).

The kernel always rounds a whole smooth chain of edges. With Tangent Propagation
off, each picked edge that meets another edge smoothly is handled like a partial
edge over its whole length (``fillet_partial``): the part is split square to the
edge at each smooth join, the edge is rounded in its own piece, so the round ends
square at the join, and the pieces are fused and merged back. Picked edges with no
smooth neighbour are rounded together in one kernel call, as usual.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_EDGE, TopAbs_VERTEX
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Edge

from fdcad.core.features.base import FeatureError
from fdcad.core.features.fillet_partial import _marked, _one_edge, _unmarked
from fdcad.core.features.modify import tangent_chain
from fdcad.core.naming.names import NamedShape

#: Param name; written only when off.
PARAM = "tangent_propagation"


def propagates(params: Mapping[str, object]) -> bool:
    """True unless the feature turned Tangent Propagation off."""
    return params.get(PARAM, True) is not False


def tangent_ends(body: NamedShape, edge: TopoDS_Edge) -> tuple[bool, bool]:
    """Whether the first and the last end of ``edge`` join another edge smoothly."""
    chain = tangent_chain(body.shape, [edge])
    curve = BRepAdaptor_Curve(edge)
    ends = (curve.Value(curve.FirstParameter()), curve.Value(curve.LastParameter()))
    found = [False, False]
    for other in chain:
        if other.IsSame(edge):
            continue
        explorer = TopExp_Explorer(other, TopAbs_VERTEX)
        while explorer.More():
            p = BRep_Tool.Pnt_s(TopoDS.Vertex(explorer.Current()))
            explorer.Next()
            for k, end in enumerate(ends):
                if p.Distance(end) < 1e-6 and _touches(other, edge, end):
                    found[k] = True
    return found[0], found[1]


def _touches(other: TopoDS_Edge, edge: TopoDS_Edge, at: gp_Pnt) -> bool:
    """True when ``other`` is a direct neighbour of ``edge`` at ``at`` (not further on)."""
    explorer = TopExp_Explorer(edge, TopAbs_VERTEX)
    while explorer.More():
        vertex = explorer.Current()
        explorer.Next()
        if BRep_Tool.Pnt_s(TopoDS.Vertex(vertex)).Distance(at) < 1e-6:
            inner = TopExp_Explorer(other, TopAbs_VERTEX)
            while inner.More():
                if inner.Current().IsSame(vertex):
                    return True
                inner.Next()
    return False


def middle(edge: TopoDS_Edge) -> gp_Pnt:
    """A point in the middle of ``edge``, to find it again after other edges change."""
    curve = BRepAdaptor_Curve(edge)
    return curve.Value((curve.FirstParameter() + curve.LastParameter()) / 2)


def find_again(body: NamedShape, point: gp_Pnt) -> TopoDS_Edge | None:
    """The edge of ``body`` through ``point``, or None."""
    vertex = BRepBuilderAPI_MakeVertex(point).Vertex()
    best: tuple[float, TopoDS_Edge] | None = None
    explorer = TopExp_Explorer(body.shape, TopAbs_EDGE)
    while explorer.More():
        edge = TopoDS.Edge(explorer.Current())
        explorer.Next()
        if BRep_Tool.Degenerated_s(edge):
            continue
        dist = BRepExtrema_DistShapeShape(vertex, edge)
        if dist.IsDone() and dist.Value() < 1e-5 and (best is None or dist.Value() < best[0]):
            best = (dist.Value(), edge)
    return best[1] if best else None


def split_items(
    body: NamedShape, edges: list[tuple[str, TopoDS_Edge]]
) -> tuple[list[tuple[str, TopoDS_Edge, tuple[bool, bool]]], list[str]]:
    """Picked edges with a smooth join (and which ends), and the names of the others."""
    joined: list[tuple[str, TopoDS_Edge, tuple[bool, bool]]] = []
    plain: list[str] = []
    for name, edge in edges:
        ends = tangent_ends(body, edge)
        if any(ends):
            joined.append((name, edge, ends))
        else:
            plain.append(name)
    return joined, plain


def round_joined(
    feature_id: str,
    owner: str,
    body: NamedShape,
    joined: list[tuple[str, TopoDS_Edge, tuple[bool, bool]]],
    role: str,
    size: Callable[[str], float],
    apply: Callable[[str], Callable[[Any, TopoDS_Edge], None] | None],
    chamfer: bool = False,
) -> NamedShape:
    """Round (or bevel) each edge in ``joined`` so the round stops at its smooth joins."""
    from fdcad.core.features.solids import solids

    what = "chamfer" if chamfer else "fillet"
    if len(solids(body.shape)) != 1:
        raise FeatureError(
            f"{owner}: turning off Tangent Propagation works on a part with one body. "
            "Turn on Tangent Propagation, or split the part first."
        )
    points = [(name, middle(edge), ends) for name, edge, ends in joined]
    marks: list[str] = []
    current = NamedShape(body.shape, _marked(list(body.faces), marks))
    for name, point, ends in points:
        edge = find_again(current, point)
        step = None
        if edge is not None:
            curve = BRepAdaptor_Curve(edge)
            u0, u1 = curve.FirstParameter(), curve.LastParameter()
            span = (float(u0), float(u1), float((u0 + u1) / 2))
            try:
                step = _one_edge(
                    feature_id,
                    current,
                    edge,
                    span,
                    size(name),
                    f"{feature_id}/{role}/{name}",
                    marks,
                    chamfer,
                    split_ends=ends,
                    apply=apply(name),
                )
            except Exception:  # kernel failure: reported below
                step = None
        if step is None:
            size_word = "distance" if chamfer else "radius"
            raise FeatureError(
                f"{owner}: the {what} on edge {name} could not stop at its smooth join. "
                f"Reduce the {size_word}, or turn on Tangent Propagation."
            )
        current = step
    return NamedShape(current.shape, _unmarked(current.faces, marks))


__all__ = [
    "PARAM",
    "find_again",
    "middle",
    "propagates",
    "round_joined",
    "split_items",
    "tangent_ends",
]
