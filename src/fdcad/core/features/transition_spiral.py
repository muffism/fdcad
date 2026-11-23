"""Transition spiral: an easement curve from a straight to an arc (TR408 item 1, D2010).

Type ``transition_spiral``. Refs: ``sketch``: a sketch with one line; the spiral
starts at the line's end, along it, in the sketch plane. Params: ``spiral_length``
(length of the spiral) and ``end_radius`` (the radius it ends at), and ``hand``
(``left``, default, or ``right``: the way it turns, seen on the sketch).

The curve is a clothoid: its curvature grows evenly from 0 at the start to
1 / radius at the end, so a train or car on it turns in smoothly. It is found by
summing the clothoid's direction along many short steps (numpy) and fitted with a
spline through points along it. The curve is kept in ``extras["curve"]`` for
Sweep and the other curve users.
"""

from __future__ import annotations

import math

import numpy as np
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
from OCP.collections import Array1_gp_Pnt
from OCP.GeomAbs import GeomAbs_C2
from OCP.GeomAPI import GeomAPI_PointsToBSpline
from OCP.gp import gp_Pnt

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    register,
)
from fdcad.core.features.curves import curve_result
from fdcad.core.units import Kind

#: Steps used to sum the clothoid, and the points the spline goes through.
STEPS, POINTS = 4000, 41


def clothoid(length: float, radius: float, left: bool = True) -> np.ndarray:
    """(POINTS, 2) points of a clothoid from (0, 0) heading +X, ``length`` long, ending
    at curvature 1 / ``radius``. Raises ValueError for values that cannot work."""
    if length <= 0 or radius <= 0:
        raise ValueError("the length and the radius must be greater than zero")
    if length > 4 * radius:
        raise ValueError("the spiral would turn more than two right angles")
    s = np.linspace(0.0, length, STEPS + 1)
    theta = s * s / (2.0 * radius * length)
    if not left:
        theta = -theta
    ds = length / STEPS
    mid = 0.5 * (theta[1:] + theta[:-1])
    x = np.concatenate([[0.0], np.cumsum(np.cos(mid) * ds)])
    y = np.concatenate([[0.0], np.cumsum(np.sin(mid) * ds)])
    pick = np.linspace(0, STEPS, POINTS).round().astype(int)
    return np.stack([x[pick], y[pick]], axis=1)


@register
class TransitionSpiral(FeatureType):
    """A clothoid easement curve that starts along a sketch line."""

    type_name = "transition_spiral"
    params = (
        ParamSpec("spiral_length", kind=Kind.LENGTH),
        ParamSpec("end_radius", kind=Kind.LENGTH),
        ParamSpec("hand", choices=("left", "right"), default="left"),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Build the curve."""
        from fdcad.core.sketch.model import Line

        owner = feature.name
        ref = feature.refs.get("sketch")
        fid = ref.get("feature") if isinstance(ref, dict) else None
        out = ctx.result(fid).sketch if isinstance(fid, str) and fid in ctx.results else None
        if out is None:
            raise FeatureError(f"{owner}: pick a sketch with the straight to start from.")
        lines = [
            e
            for e in out.model.entities.values()
            if isinstance(e, Line) and not getattr(e, "construction", False)
        ]
        if len(lines) != 1:
            raise FeatureError(f"{owner}: the sketch must have exactly one line. Draw one line.")
        a, b = out.model.xy(lines[0].p1), out.model.xy(lines[0].p2)
        heading = math.atan2(b[1] - a[1], b[0] - a[0])
        values = {}
        for name in ("spiral_length", "end_radius"):
            value = feature.params.get(name)
            values[name] = value.value if isinstance(value, Param) else 0.0
        try:
            local = clothoid(
                values["spiral_length"], values["end_radius"], feature.params.get("hand") != "right"
            )
        except ValueError as exc:
            raise FeatureError(
                f"{owner}: {exc}. Enter a longer radius or a shorter spiral."
            ) from exc
        c, s = math.cos(heading), math.sin(heading)
        uv = np.stack(
            [b[0] + local[:, 0] * c - local[:, 1] * s, b[1] + local[:, 0] * s + local[:, 1] * c],
            axis=1,
        )
        plane = out.plane
        o, n, x = (np.array(v, dtype=float) for v in (plane.origin, plane.normal, plane.x_dir))
        y = np.cross(n, x)
        world = o + uv[:, :1] * x + uv[:, 1:] * y
        array = Array1_gp_Pnt(1, len(world))
        for k, p in enumerate(world.tolist(), start=1):  # 41 fit points, not a mesh
            array.SetValue(k, gp_Pnt(*p))
        fit = GeomAPI_PointsToBSpline(array, 3, 8, GeomAbs_C2, 1e-6)
        if not fit.IsDone():
            raise FeatureError(f"{owner}: the spiral could not be made. Change the length.")
        edge = BRepBuilderAPI_MakeEdge(fit.Curve()).Edge()
        return curve_result(ctx, edge)
