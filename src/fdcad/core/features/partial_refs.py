"""Partial edge ends set by a picked vertex, point or plane (TR64 item 5, D1401).

``partial`` "reference" with ``refs.partial_ends``: two picks, the start and the
end. A vertex or point sets the end at the nearest point of each edge; a plane
(a reference plane or a flat face) at the point where the edge crosses it. The two
positions are turned into distances along each edge, so the partial routine
(``fillet_partial``) runs as for typed distances.
"""

from __future__ import annotations

from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GCPnts import GCPnts_AbscissaPoint
from OCP.Geom import Geom_Plane
from OCP.GeomAPI import GeomAPI_IntCS, GeomAPI_ProjectPointOnCurve
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt
from OCP.TopoDS import TopoDS_Edge

from fdcad.core.document.model import Feature
from fdcad.core.features.base import BuildContext, FeatureError, Issue
from fdcad.core.features.datum import Geo, resolve_pick

KIND = "reference"
REFS = "partial_ends"


def end_picks(feature: Feature, ctx: BuildContext) -> tuple[list[Geo], list[Issue]]:
    """The start and end picks, resolved."""
    refs = feature.refs.get(REFS)
    if not isinstance(refs, list) or len(refs) != 2:
        raise FeatureError(
            f"{feature.name}: partial edges by reference need two picks, a start and an end. "
            "Pick two vertices, points or planes."
        )
    out: list[Geo] = []
    issues: list[Issue] = []
    for ref in refs:
        geo, found = resolve_pick(ref, ctx, feature.name)
        issues.extend(found)
        if geo.kind not in ("point", "plane") or (geo.kind == "plane" and not geo.direction):
            raise FeatureError(
                f"{feature.name}: a partial edge end must be a vertex, a point or a plane. "
                "Pick one of those."
            )
        out.append(geo)
    return out, issues


def _parameter(owner: str, edge: TopoDS_Edge, name: str, geo: Geo) -> float:
    first, last = 0.0, 0.0
    curve = BRep_Tool.Curve_s(edge, first, last)
    adaptor = BRepAdaptor_Curve(edge)
    u0, u1 = adaptor.FirstParameter(), adaptor.LastParameter()
    if geo.kind == "point":
        project = GeomAPI_ProjectPointOnCurve(gp_Pnt(*geo.point), curve, u0, u1)
        if project.NbPoints() == 0:
            raise FeatureError(
                f"{owner}: a partial end point is off edge {name}. Pick a point beside the edge."
            )
        return float(project.LowerDistanceParameter())
    assert geo.direction is not None
    plane = Geom_Plane(gp_Pln(gp_Pnt(*geo.point), gp_Dir(*geo.direction)))
    hit = GeomAPI_IntCS(curve, plane)
    found = [hit.Parameters(i)[2] for i in range(1, hit.NbPoints() + 1)] if hit.IsDone() else []
    inside = [u for u in found if u0 - 1e-9 <= u <= u1 + 1e-9]
    if not inside:
        raise FeatureError(
            f"{owner}: a partial end plane does not cross edge {name}. "
            "Pick a plane that crosses the edge."
        )
    return float(min(inside))


def lengths(owner: str, edge: TopoDS_Edge, name: str, ends: list[Geo]) -> tuple[float, float]:
    """Distances along ``edge`` from its first end to the start and end picks, in order."""
    adaptor = BRepAdaptor_Curve(edge)
    u0 = adaptor.FirstParameter()
    out = []
    for geo in ends:
        u = _parameter(owner, edge, name, geo)
        out.append(0.0 if u <= u0 else float(GCPnts_AbscissaPoint.Length_s(adaptor, u0, u)))
    start, end = sorted(out)
    if end - start < 1e-6:
        raise FeatureError(
            f"{owner}: the two partial ends meet at one point on edge {name}. "
            "Pick ends apart from each other."
        )
    return start, end
