"""Several connectors per loft profile (TR136 item 1, D2403).

``connect_<k>`` (D220) says where profile ``k`` starts. ``match_<k>`` adds more
connectors: text such as "3, 6", vertex numbers of profile ``k`` counted like
``connect_<k>`` (vertex ``n`` is where edge ``n`` starts, from 0). Every profile
with a wire must list the same number of them. The loft then joins the first
connector of each profile to the first of the others, the second to the second
and so on, in the order they come along each profile: the edges between two
connectors are split, the longest first, until every profile has as many edges in
that stretch as the others, so the kernel pairs them one to one and the loft does
not twist there. No Qt; runs with the rebuild.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from itertools import pairwise

from OCP.BRep import BRep_Tool
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
from OCP.BRepGProp import BRepGProp
from OCP.BRepTools import BRepTools_WireExplorer
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_REVERSED
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Wire

from fdcad.core.document.model import Feature
from fdcad.core.features.base import FeatureError

Vec3 = tuple[float, float, float]
#: At most this many edges a stretch is split into.
MAX_SPLITS = 64


def match_numbers(feature: Feature, k: int) -> list[int]:
    """The extra connector vertex numbers of profile ``k`` (1 based), or []."""
    text = str(feature.params.get(f"match_{k}", "") or "").strip()
    if not text:
        return []
    parts = [p.strip() for p in re.split(r"[,;\s]+", text) if p.strip()]
    if not all(p.isdigit() for p in parts):
        raise FeatureError(
            f"{feature.name}: the connectors of profile {k} must be vertex numbers such as "
            f"3, 6. Fix '{text}'."
        )
    return [int(p) for p in parts]


def edges_of(wire: TopoDS_Wire) -> list[TopoDS_Edge]:
    """The wire's edges in order along it."""
    out: list[TopoDS_Edge] = []
    explorer = BRepTools_WireExplorer(wire)
    while explorer.More():
        out.append(explorer.Current())
        explorer.Next()
    return out


def _start(edge: TopoDS_Edge) -> Vec3:
    """Where ``edge`` starts along its wire (its orientation counted)."""
    vertex = TopExp.FirstVertex_s(edge, True)
    p = BRep_Tool.Pnt_s(vertex)
    return p.X(), p.Y(), p.Z()


def vertex_points(wire: TopoDS_Wire, numbers: Sequence[int]) -> list[Vec3]:
    """The points of vertex ``numbers`` of ``wire`` (vertex n starts edge n)."""
    edges = edges_of(wire)
    if not edges:
        return []
    return [_start(edges[n % len(edges)]) for n in numbers]


def _length(edge: TopoDS_Edge) -> float:
    props = GProp_GProps()
    BRepGProp.LinearProperties_s(edge, props)
    return float(props.Mass())


def _halves(edge: TopoDS_Edge) -> list[TopoDS_Edge]:
    """``edge`` split at its middle parameter, in the order the wire runs."""
    curve = BRep_Tool.Curve_s(edge, 0.0, 0.0)
    first, last = BRep_Tool.Range_s(edge)
    mid = (first + last) / 2
    loc = edge.Location()
    one = TopoDS.Edge(BRepBuilderAPI_MakeEdge(curve, first, mid).Edge().Moved(loc))
    two = TopoDS.Edge(BRepBuilderAPI_MakeEdge(curve, mid, last).Edge().Moved(loc))
    if edge.Orientation() == TopAbs_REVERSED:
        return [TopoDS.Edge(two.Reversed()), TopoDS.Edge(one.Reversed())]
    return [one, two]


def _nearest(edges: list[TopoDS_Edge], point: Vec3) -> int:
    def gap(e: TopoDS_Edge) -> float:
        s = _start(e)
        return sum((a - b) ** 2 for a, b in zip(s, point, strict=True))

    return min(range(len(edges)), key=lambda i: gap(edges[i]))


def _stretches(edges: list[TopoDS_Edge], points: list[Vec3]) -> list[list[TopoDS_Edge]]:
    """The edges between the connectors (the wire's start counts as one), in order."""
    cuts = sorted({_nearest(edges, p) for p in points} - {0})
    bounds = [0, *cuts, len(edges)]
    return [edges[a:b] for a, b in pairwise(bounds)]


def _filled(stretch: list[TopoDS_Edge], count: int) -> list[TopoDS_Edge]:
    out = list(stretch)
    while len(out) < count:
        i = max(range(len(out)), key=lambda j: _length(out[j]))
        out[i : i + 1] = _halves(out[i])
    return out


def matched_wires(
    owner: str, wires: list[TopoDS_Wire], points: list[list[Vec3]]
) -> list[TopoDS_Wire]:
    """``wires`` with the edges between connectors split so each stretch has the same
    number of edges on every wire. ``points`` holds each wire's connector points.
    Raises FeatureError when the counts differ or a stretch cannot be matched."""
    counts = {len(p) for p in points}
    if len(counts) != 1:
        raise FeatureError(
            f"{owner}: every profile needs the same number of connectors. Add or remove "
            "connectors so the counts match."
        )
    split = [_stretches(edges_of(w), p) for w, p in zip(wires, points, strict=True)]
    if len({len(s) for s in split}) != 1:
        raise FeatureError(
            f"{owner}: two connectors of one profile sit on the same point. Pick other vertices."
        )
    out: list[TopoDS_Wire] = []
    targets = [max(len(s[i]) for s in split) for i in range(len(split[0]))]
    if any(t > MAX_SPLITS for t in targets):
        raise FeatureError(f"{owner}: the profiles have too many edges to match. Use fewer.")
    for stretches in split:
        maker = BRepBuilderAPI_MakeWire()
        for stretch, target in zip(stretches, targets, strict=True):
            for edge in _filled(stretch, target):
                maker.Add(edge)
        if not maker.IsDone():
            raise FeatureError(f"{owner}: the connectors could not be matched. Pick others.")
        out.append(maker.Wire())
    return out
