"""Reference axis (PHASE2_SPEC P2.10 item 2, FDEF_SPEC 5.3.20, D251).

Params: ``method`` (``line``, ``two_planes``, ``two_points``, ``cylinder``,
``point_normal``), ``reverse``. Refs: ``first`` and ``second`` as the method needs.
"""

from __future__ import annotations

from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
from OCP.gp import gp_Pnt

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    Datum,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    register,
)
from fdcad.core.features.datum import (
    Geo,
    Vec3,
    add,
    cross,
    dot,
    norm,
    picks,
    scale,
    sub,
    unit,
)
from fdcad.core.units import Kind

METHODS = ("line", "two_planes", "two_points", "cylinder", "point_normal")
PICK_COUNT = {"line": 1, "two_planes": 2, "two_points": 2, "cylinder": 1, "point_normal": 2}


def guess_method(kinds: list[str]) -> str | None:
    """The method the picks suggest (P2.10 item 2)."""
    k = tuple(kinds)
    table = {
        ("line",): "line",
        ("cylinder",): "cylinder",
        ("circle",): "cylinder",
        ("plane", "plane"): "two_planes",
        ("point", "point"): "two_points",
        ("point", "plane"): "point_normal",
        ("plane", "point"): "point_normal",
        ("point", "face"): "point_normal",
        ("face", "point"): "point_normal",
        ("point", "cylinder"): "point_normal",
        ("cylinder", "point"): "point_normal",
    }
    return table.get(k)


def _normal_at(geo: Geo, point: Vec3) -> tuple[Vec3, Vec3]:
    """Foot of ``point`` on a plane or face, and the normal there."""
    if geo.kind == "plane" and geo.direction is not None:
        n = geo.direction
        foot = sub(point, scale(n, dot(sub(point, geo.point), n)))
        return foot, n
    if geo.face is None:
        raise FeatureError("Pick a plane or a face.")
    surface = BRep_Tool.Surface_s(geo.face)
    proj = GeomAPI_ProjectPointOnSurf(gp_Pnt(*point), surface)
    if proj.NbPoints() == 0:
        raise FeatureError("The point cannot be projected onto the face. Pick another point.")
    u, v = proj.LowerDistanceParameters()
    props = BRepAdaptor_Surface(geo.face)
    from OCP.BRepLProp import BRepLProp_SLProps

    slp = BRepLProp_SLProps(props, u, v, 1, 1e-6)
    if not slp.IsNormalDefined():
        raise FeatureError("The face has no normal at that point. Pick another point.")
    n = slp.Normal()
    p = proj.NearestPoint()
    return (p.X(), p.Y(), p.Z()), (n.X(), n.Y(), n.Z())


def make_axis(feature: Feature, geos: list[Geo], owner: str) -> tuple[Vec3, Vec3, float]:
    """Point, unit direction and display length of the axis."""
    method = str(feature.params.get("method", "line"))
    if method == "line":
        g = geos[0]
        if g.kind != "line" or g.direction is None:
            raise FeatureError(f"{owner}: pick a straight edge, a sketch line or an axis.")
        p, d, size = g.point, g.direction, g.length
    elif method == "two_planes":
        a, b = geos[0], geos[1]
        if a.kind != "plane" or b.kind != "plane":
            raise FeatureError(f"{owner}: pick two planes or flat faces.")
        assert a.direction is not None and b.direction is not None
        d0 = unit(cross(a.direction, b.direction))
        if d0 is None:
            raise FeatureError(f"{owner}: the two planes are parallel. Pick planes that cross.")
        # The point of the crossing line nearest the model origin.
        n1, n2 = a.direction, b.direction
        h1, h2 = dot(n1, a.point), dot(n2, b.point)
        raw = cross(n1, n2)
        p = scale(add(scale(cross(n2, raw), h1), scale(cross(raw, n1), h2)), 1.0 / dot(raw, raw))
        d, size = d0, 0.0
    elif method == "two_points":
        p1, p2 = geos[0].point, geos[1].point
        d1 = unit(sub(p2, p1))
        if d1 is None:
            raise FeatureError(f"{owner}: the two points are the same. Pick two different points.")
        p, d, size = p1, d1, norm(sub(p2, p1))
    elif method == "cylinder":
        g = geos[0]
        if g.kind not in ("cylinder", "circle") or g.direction is None:
            raise FeatureError(f"{owner}: pick a cylinder or cone face, or a round edge.")
        p, d, size = g.point, g.direction, 0.0
    elif method == "point_normal":
        points = [g for g in geos if g.kind == "point"]
        faces = [g for g in geos if g.kind in ("plane", "face", "cylinder")]
        if not points or not faces:
            raise FeatureError(f"{owner}: pick a point and a plane or face.")
        p, n = _normal_at(faces[0], points[0].point)
        d1 = unit(n)
        if d1 is None:
            raise FeatureError(f"{owner}: the face has no normal there. Pick another point.")
        d, size = d1, 0.0
    else:
        raise FeatureError(
            f"{owner}: unknown axis method '{method}'. Choose another method in the property panel."
        )
    if bool(feature.params.get("reverse", False)):
        d = scale(d, -1.0)
    return p, d, size


@register
class RefAxis(FeatureType):
    """A reference axis. Passes the part through unchanged."""

    type_name = "ref_axis"
    params = (
        ParamSpec("method", choices=METHODS, default="line"),  # TR149 (D980): the extras
        *(
            ParamSpec(n, kind=Kind.LENGTH, optional=True)
            for n in ("extra_dx", "extra_dy", "extra_dz")
        ),
        *(
            ParamSpec(n, kind=Kind.ANGLE, optional=True)
            for n in ("extra_rx", "extra_ry", "extra_rz")
        ),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Resolve the picks and place the axis."""
        method = str(feature.params.get("method", "line"))
        geos, issues = picks(feature, ctx, PICK_COUNT.get(method, 1))
        p, d, size = make_axis(feature, geos, feature.name)
        from fdcad.core.features.extra_placement import apply, has_extra

        if has_extra(feature):  # TR149 (D980)
            p, d, _x = apply(feature, p, d, None)
        return FeatureResult(body=ctx.body, issues=issues, datum=Datum("axis", p, d, None, size))
