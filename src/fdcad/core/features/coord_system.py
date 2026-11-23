"""Coordinate system (PHASE2_SPEC P2.10 item 4, FDEF_SPEC 5.3.20, D251).

Params: ``method``: ``directions`` (axes from picks) or ``angles`` (``rx``,
``ry``, ``rz`` applied X, then Y, then Z). The origin is ``refs.first`` (a
point, vertex or round edge centre) or, without it, ``x``, ``y``, ``z``.
``directions`` reads the X direction from ``refs.second`` and the Z direction
from ``refs.third`` (a straight edge or axis: along it; a point: towards it; a
plane or flat face: its normal), each with ``reverse_x`` or ``reverse_z``.
A missing one keeps the model axis.
"""

from __future__ import annotations

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    Datum,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.features.datum import (
    Geo,
    Vec3,
    cross,
    dot,
    length_param,
    resolve_pick,
    rotate,
    scale,
    sub,
    unit,
)
from fdcad.core.units import Kind

METHODS = ("directions", "angles")


def _direction(geo: Geo, origin: Vec3, owner: str, which: str) -> Vec3:
    if geo.kind == "point":
        d = unit(sub(geo.point, origin))
        if d is None:
            raise FeatureError(f"{owner}: the {which} point is the origin. Pick another point.")
        return d
    if geo.direction is not None and geo.kind in ("line", "plane", "circle", "cylinder"):
        return geo.direction
    raise FeatureError(
        f"{owner}: the {which} direction needs a straight edge, an axis, a point or a flat face. "
        "Pick one of these."
    )


def make_frame(
    feature: Feature, origin: Vec3, x_geo: Geo | None, z_geo: Geo | None, owner: str
) -> tuple[Vec3, Vec3]:
    """The frame's X and Z axes (unit, square to each other)."""
    method = str(feature.params.get("method", "directions"))
    if method == "angles":
        x: Vec3 = (1.0, 0.0, 0.0)
        z: Vec3 = (0.0, 0.0, 1.0)
        for axis, name in (
            ((1.0, 0.0, 0.0), "rx"),
            ((0.0, 1.0, 0.0), "ry"),
            ((0.0, 0.0, 1.0), "rz"),
        ):
            angle = length_param(feature, name)
            x, z = rotate(x, axis, angle), rotate(z, axis, angle)
        return x, z
    z = _direction(z_geo, origin, owner, "Z") if z_geo is not None else (0.0, 0.0, 1.0)
    if bool(feature.params.get("reverse_z", False)):
        z = scale(z, -1.0)
    if x_geo is not None:
        x = _direction(x_geo, origin, owner, "X")
    else:
        x = (1.0, 0.0, 0.0) if abs(z[0]) < 0.999 else (0.0, 1.0, 0.0)
    if bool(feature.params.get("reverse_x", False)):
        x = scale(x, -1.0)
    square = unit(sub(x, scale(z, dot(x, z))))
    if square is None:
        raise FeatureError(f"{owner}: the X and Z directions are parallel. Pick another direction.")
    assert unit(cross(z, square)) is not None
    return square, z


@register
class CoordSystem(FeatureType):
    """A coordinate system. Passes the part through unchanged."""

    type_name = "coord_system"
    params = (
        ParamSpec("method", choices=METHODS, default="directions"),
        # Kinds let formulas and variables drive the values (D608).
        *(ParamSpec(n, kind=Kind.LENGTH, optional=True) for n in ("x", "y", "z")),
        *(ParamSpec(n, kind=Kind.ANGLE, optional=True) for n in ("rx", "ry", "rz")),
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
        """Resolve the origin and directions."""
        issues: list[Issue] = []
        geos: dict[str, Geo] = {}
        for key in ("first", "second", "third"):
            ref = feature.refs.get(key)
            if ref is not None:
                geos[key], more = resolve_pick(ref, ctx, feature.name)
                issues += more
        if "first" in geos:
            origin = geos["first"].point
        else:
            origin = (
                length_param(feature, "x"),
                length_param(feature, "y"),
                length_param(feature, "z"),
            )
        x, z = make_frame(feature, origin, geos.get("second"), geos.get("third"), feature.name)
        from fdcad.core.features.extra_placement import apply, has_extra

        if has_extra(feature):  # TR149 (D980)
            origin, z, x = apply(feature, origin, z, x)
        return FeatureResult(body=ctx.body, issues=issues, datum=Datum("frame", origin, z, x))
