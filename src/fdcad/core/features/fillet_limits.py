"""Fillet limits: edges to keep and a limiting plane (TR271 items 2 and 3, D1407).

Edges to keep (``refs.keep_edges``): after rounding, every kept edge must still be
in the part (found again by its middle point). When a round swallows one, the
fillet fails, names the edges and offers the largest radius that keeps them.

Limiting plane (``refs.limit_plane``, one reference plane or flat face, and
``limit_flip``): the rounds stop at the plane. Each edge keeps the part behind the
plane (against its normal; the front with ``limit_flip``): an edge that crosses the
plane is rounded up to it, with a square end, as a partial edge (``fillet_partial``);
an edge wholly in front is not rounded.
"""

from __future__ import annotations

from collections.abc import Callable

from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GCPnts import GCPnts_AbscissaPoint
from OCP.Geom import Geom_Plane
from OCP.GeomAPI import GeomAPI_IntCS
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt, gp_Vec
from OCP.TopoDS import TopoDS_Edge

from fdcad.core.document.model import Feature
from fdcad.core.features.base import BuildContext, FeatureError, Fix, Issue
from fdcad.core.naming.names import NamedShape

KEEP = "keep_edges"
LIMIT = "limit_plane"


def kept_points(
    feature: Feature, ctx: BuildContext
) -> tuple[list[tuple[str, gp_Pnt]], list[Issue]]:
    """The middle point of every edge to keep, by name."""
    from fdcad.core.features.fillet_tangent import middle
    from fdcad.core.features.modify import resolve_edges

    if not feature.refs.get(KEEP):
        return [], []
    found, issues = resolve_edges(feature, ctx, KEEP)
    return [(name, middle(edge)) for name, edge in found], issues


def swallowed(result: NamedShape, points: list[tuple[str, gp_Pnt]]) -> list[str]:
    """Names of the kept edges that are no longer in ``result``."""
    from fdcad.core.features.fillet_tangent import find_again

    return [name for name, p in points if find_again(result, p) is None]


def keep_error(
    feature: Feature,
    lost: list[str],
    largest: float | None,
) -> FeatureError:
    """The error naming swallowed kept edges, with the radius fix when one was found."""
    fixes: list[Fix] = []
    if largest is not None:
        from fdcad.core.features.fillet import _round_down

        value = _round_down(largest)
        fixes.append(
            Fix(
                f"Reduce the radius to {value:g} mm",
                "set_param",
                {"feature": feature.id, "param": "radius", "value": value},
            )
        )
    count = len(lost)
    return FeatureError(
        f"{feature.name}: the round swallows {count} edge{'s' if count != 1 else ''} to keep "
        f"({', '.join(lost)}). Reduce the radius, or remove the edge from Edges to Keep.",
        fixes=fixes,
        highlight=lost,
    )


def largest_keeping(
    build: Callable[[float], NamedShape | None],
    points: list[tuple[str, gp_Pnt]],
    wanted: float,
    steps: int = 8,
) -> float | None:
    """The largest radius below ``wanted`` whose round keeps every kept edge."""
    low, high, best = 0.0, wanted, None
    for _ in range(steps):
        middle = (low + high) / 2
        result = build(middle)
        if result is not None and not swallowed(result, points):
            best, low = middle, middle
        else:
            high = middle
    return best


def limit_plane(feature: Feature, ctx: BuildContext) -> tuple[gp_Pln | None, list[Issue]]:
    """The limiting plane, or None when the fillet has none."""
    from fdcad.core.features.datum import resolve_pick

    ref = feature.refs.get(LIMIT)
    if not ref:
        return None, []
    geo, issues = resolve_pick(ref, ctx, feature.name)
    if geo.kind != "plane" or geo.direction is None:
        raise FeatureError(
            f"{feature.name}: the limiting item must be a plane or a flat face. Pick one of those."
        )
    normal = gp_Dir(*geo.direction)
    if feature.params.get("limit_flip") is True:
        normal.Reverse()
    return gp_Pln(gp_Pnt(*geo.point), normal), issues


def _side(plane: gp_Pln, point: gp_Pnt) -> float:
    origin = plane.Location()
    return float(gp_Vec(origin, point).Dot(gp_Vec(plane.Axis().Direction())))


def kept_range(plane: gp_Pln, edge: TopoDS_Edge) -> tuple[float, float] | None:
    """The part of ``edge`` behind ``plane``, in mm along it, or None when none is."""
    adaptor = BRepAdaptor_Curve(edge)
    u0, u1 = adaptor.FirstParameter(), adaptor.LastParameter()
    total = float(GCPnts_AbscissaPoint.Length_s(adaptor))
    curve = BRep_Tool.Curve_s(edge, 0.0, 0.0)
    hit = GeomAPI_IntCS(curve, Geom_Plane(plane))
    found = [hit.Parameters(i)[2] for i in range(1, hit.NbPoints() + 1)] if hit.IsDone() else []
    inside = sorted(u for u in found if u0 + 1e-9 < u < u1 - 1e-9)
    start_behind = _side(plane, adaptor.Value(u0)) <= 0
    if not inside:
        middle = adaptor.Value((u0 + u1) / 2)
        return (0.0, total) if _side(plane, middle) <= 0 else None
    at = float(GCPnts_AbscissaPoint.Length_s(adaptor, u0, inside[0]))
    return (0.0, at) if start_behind else (at, total)
