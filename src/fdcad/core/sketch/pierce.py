"""Pierce: a sketch point kept where a curve crosses the sketch plane (TR101, D843).

``refs.pierce`` of a sketch feature lists ``{"point": <point id>, "curve": <ref>}``;
the curve is a curve feature or another sketch (``{"feature": id}``) or an edge of
the part. On every rebuild the point is moved to the crossing nearest to where it
is, before the sketch is solved, and it carries a Fixed relation so the solver
keeps it there. No Qt.
"""

from __future__ import annotations

from typing import Any

from fdcad.core.features.base import BuildContext, FeatureError, FeatureState, Issue
from fdcad.core.sketch.model import Point, Sketch
from fdcad.core.sketch.profiles import SketchPlane


def crossings(edges: list[Any], plane: SketchPlane) -> list[tuple[float, float]]:
    """Where the edges cross the sketch plane, in sketch coordinates."""
    from OCP.BRep import BRep_Tool
    from OCP.Geom import Geom_Plane
    from OCP.GeomAPI import GeomAPI_IntCS
    from OCP.gp import gp_Pln

    surface = Geom_Plane(gp_Pln(plane.ax3()))
    out: list[tuple[float, float]] = []
    for edge in edges:
        from OCP.BRepAdaptor import BRepAdaptor_Curve

        span = BRepAdaptor_Curve(edge)
        first, last = span.FirstParameter(), span.LastParameter()
        curve = BRep_Tool.Curve_s(edge, 0.0, 0.0)  # OCP returns the curve only
        if curve is None:
            continue
        hit = GeomAPI_IntCS(curve, surface)
        if not hit.IsDone():
            continue
        for i in range(1, hit.NbPoints() + 1):
            _u, _v, w = hit.Parameters(i)
            if min(first, last) - 1e-9 <= w <= max(first, last) + 1e-9:
                p = hit.Point(i)
                x, y, _h = plane.to_2d(p.X(), p.Y(), p.Z())
                out.append((x, y))
    return out


def _edges(ctx: BuildContext, ref: Any, owner: str) -> list[Any]:
    from fdcad.core.features.curves import feature_edges
    from fdcad.core.naming.resolve import resolve_edge

    if isinstance(ref, dict) and ref.get("kind") == "edge":
        return [resolve_edge(ctx.body, ref, owner)[0]]
    return feature_edges(ctx, ref, owner)


def place_pierced(
    sketch: Sketch, plane: SketchPlane, refs: Any, ctx: BuildContext, owner: str
) -> list[Issue]:
    """Move each pierced point to its curve's crossing and hold it there. A point whose
    curve no longer crosses the plane stays where it is, with a warning."""
    issues: list[Issue] = []
    if not isinstance(refs, list):
        return issues
    for item in refs:
        if not isinstance(item, dict):
            continue
        pid = str(item.get("point", ""))
        point = sketch.entities.get(pid)
        if not isinstance(point, Point):
            continue  # the point was deleted: the pierce goes with it
        try:
            found = crossings(_edges(ctx, item.get("curve"), owner), plane)
        except FeatureError as exc:
            issues.append(Issue(FeatureState.WARNING, str(exc), code="pierce_lost"))
            continue
        if not found:
            issues.append(
                Issue(
                    FeatureState.WARNING,
                    f"{owner}: the curve of a pierced point no longer crosses the sketch "
                    "plane. Move the curve or the plane, or delete the point's Fixed relation.",
                    code="pierce_lost",
                )
            )
            continue
        here = (point.x, point.y)
        best = min(found, key=lambda q: (q[0] - here[0]) ** 2 + (q[1] - here[1]) ** 2)
        point.x, point.y = best
        if not any(r.type == "fixed" and r.entities == [pid] for r in sketch.relations):
            sketch.relate("fixed", pid)
    return issues
