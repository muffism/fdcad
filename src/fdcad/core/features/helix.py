"""Helix and spiral curves (PHASE3_SPEC P3.6 item 1, DECISIONS D291).

Params:

- ``definition``: ``"pitch_turns"``, ``"height_turns"``, ``"height_pitch"`` or
  ``"spiral"`` (flat, pitch and turns).
- ``pitch_type``: ``"constant"`` (default) or ``"variable"`` (helix only). Variable
  pitch uses rows ``vp_turns_<k>``, ``vp_pitch_<k>``, ``vp_diameter_<k>`` for
  ``k`` from 1 to ``vp_rows``: at turn ``vp_turns_<k>`` the pitch and diameter are
  the row's; between rows they change evenly. Row 1 is at turn 0.
- ``pitch``, ``height`` (lengths) and ``turns`` (a number), as the definition needs.
- ``reverse``: the helix grows the other way from the sketch plane; a spiral
  winds inward. ``clockwise``: winds clockwise seen from the side the helix grows
  toward (counterclockwise by default). ``start_angle``: where the curve starts,
  measured from the sketch X direction.
- ``taper_angle`` with ``taper_outward`` (default true): a conical helix, constant
  pitch only.
- ``ends`` (TR162, D1923): optional, ``open`` (default) or ``closed``: spring end coils,
  the pitch ``end_pitch`` at each end growing to the pitch over the first and last turn.

Refs: ``sketch``: a sketch with one circle; its centre, plane and diameter
place the curve.
"""

from __future__ import annotations

import itertools
import math

import numpy as np
from numpy.typing import NDArray
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
from OCP.BRepLib import BRepLib
from OCP.collections import HArray1_gp_Pnt
from OCP.GeomAbs import GeomAbs_C2
from OCP.GeomAPI import GeomAPI_Interpolate
from OCP.gp import gp_Ax3, gp_Dir, gp_Dir2d, gp_Pnt, gp_Pnt2d
from OCP.TopoDS import TopoDS_Wire

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureState,
    FeatureType,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.features.curves import curve_result
from fdcad.core.sketch.model import Circle
from fdcad.core.units import Kind

DEFINITIONS = ("pitch_turns", "height_turns", "height_pitch", "spiral")
#: Points per turn for curves made through points (variable pitch, spiral).
POINTS_PER_TURN = 64
#: At most this many points, so very long curves stay quick (D291 item 3).
MAX_POINTS = 4000
_MAX_TURNS = 1000.0


def _value(feature: Feature, name: str, label: str) -> float:
    value = feature.params.get(name)
    if not isinstance(value, Param):
        raise FeatureError(f"{feature.name}: the {label} is missing. Enter a value.")
    return value.value


def _positive(feature: Feature, name: str, label: str) -> float:
    v = _value(feature, name, label)
    if not v > 0:
        raise FeatureError(
            f"{feature.name}: the {label} must be greater than zero. Enter a larger value."
        )
    return v


class Placement:
    """Where the curve sits: the circle's centre, axis, start direction and radius."""

    def __init__(self, feature: Feature, ctx: BuildContext) -> None:
        owner = feature.name
        ref = feature.refs.get("sketch")
        if not isinstance(ref, dict) or "feature" not in ref:
            raise FeatureError(f"{owner} has no sketch. Choose a sketch with one circle.")
        out = ctx.result(str(ref["feature"])).sketch
        if out is None:
            raise FeatureError(f"{owner}: the sketch is not a sketch. Choose a sketch.")
        circles = [
            e for e in out.model.entities.values() if isinstance(e, Circle) and not e.construction
        ]
        if len(circles) != 1:
            raise FeatureError(
                f"{owner}: the sketch must hold exactly one circle (it has {len(circles)}). "
                "Draw one circle for the helix diameter."
            )
        circle = circles[0]
        cx, cy = out.model.xy(circle.center)
        c = out.plane.to_3d(cx, cy)
        self.centre = (c.X(), c.Y(), c.Z())
        self.radius = circle.radius
        self.normal = out.plane.normal
        self.x_dir = out.plane.x_dir


def _frame(place: Placement, reverse: bool, clockwise: bool, start: float) -> gp_Ax3:
    """Axis along the growth direction, X toward the start point.

    The start angle is measured on the sketch plane from the sketch X direction
    toward its Y direction. Counterclockwise is seen from the side the helix grows
    toward, so the frame is right handed for counterclockwise and left handed for
    clockwise.
    """
    n, x = place.normal, place.x_dir
    y = (n[1] * x[2] - n[2] * x[1], n[2] * x[0] - n[0] * x[2], n[0] * x[1] - n[1] * x[0])
    c, s = math.cos(start), math.sin(start)
    turned = gp_Dir(*(x[i] * c + y[i] * s for i in range(3)))
    axis = gp_Dir(-n[0], -n[1], -n[2]) if reverse else gp_Dir(*n)
    frame = gp_Ax3(gp_Pnt(*place.centre), axis, turned)
    if clockwise:
        frame.YReverse()
    return frame


def _exact_helix(
    frame: gp_Ax3, radius: float, pitch: float, turns: float, taper: float
) -> TopoDS_Wire:
    """A constant pitch helix as a straight line on a cylinder or cone (exact)."""
    from OCP.Geom import Geom_ConicalSurface, Geom_CylindricalSurface
    from OCP.Geom2d import Geom2d_Line

    if abs(taper) < 1e-12:
        surface = Geom_CylindricalSurface(frame, radius)
        rise = pitch
    else:
        surface = Geom_ConicalSurface(frame, taper, radius)
        rise = pitch / math.cos(taper)
    direction = gp_Dir2d(2 * math.pi, rise)
    line = Geom2d_Line(gp_Pnt2d(0.0, 0.0), direction)
    length = turns * math.hypot(2 * math.pi, rise)
    edge = BRepBuilderAPI_MakeEdge(line, surface, 0.0, length).Edge()
    BRepLib.BuildCurves3d_s(edge, 1e-6, GeomAbs_C2, 14, max(20, int(turns * 4)))
    return BRepBuilderAPI_MakeWire(edge).Wire()


def _through_points(frame: gp_Ax3, local: NDArray[np.float64]) -> TopoDS_Wire:
    """A smooth curve through points given in ``frame`` (columns x, y, z)."""
    o, x, y, z = frame.Location(), frame.XDirection(), frame.YDirection(), frame.Direction()
    basis = np.array(
        [[x.X(), x.Y(), x.Z()], [y.X(), y.Y(), y.Z()], [z.X(), z.Y(), z.Z()]], dtype=np.float64
    )
    world = local @ basis + np.array([o.X(), o.Y(), o.Z()])
    points = HArray1_gp_Pnt(1, len(world))
    # A bounded number of points (MAX_POINTS), not a mesh or a large point set.
    for i, (px, py, pz) in enumerate(world.tolist(), start=1):
        points.SetValue(i, gp_Pnt(px, py, pz))
    interpolate = GeomAPI_Interpolate(points, False, 1e-9)
    interpolate.Perform()
    if not interpolate.IsDone():
        raise FeatureError(
            "The curve could not be made through its points. Change the pitch or diameter slightly."
        )
    edge = BRepBuilderAPI_MakeEdge(interpolate.Curve()).Edge()
    return BRepBuilderAPI_MakeWire(edge).Wire()


def _samples(turns: float) -> NDArray[np.float64]:
    count = int(min(MAX_POINTS, max(16, math.ceil(turns * POINTS_PER_TURN)))) + 1
    return np.linspace(0.0, turns, count)


def spiral_points(radius: float, pitch: float, turns: float, inward: bool) -> NDArray[np.float64]:
    """Points of a flat spiral whose radius changes by ``pitch`` every turn."""
    t = _samples(turns)
    r = radius + (-1.0 if inward else 1.0) * pitch * t
    angle = 2 * math.pi * t
    return np.column_stack([r * np.cos(angle), r * np.sin(angle), np.zeros_like(t)])


def variable_points(
    rows: list[tuple[float, float, float]],
) -> NDArray[np.float64]:
    """Points of a helix whose pitch and diameter change between rows.

    ``rows`` are (turn, pitch, diameter), the first at turn 0, turns increasing.
    Pitch changes evenly between rows, so the height is its running integral.
    """
    turns_at = np.array([r[0] for r in rows])
    t = _samples(float(turns_at[-1]))
    pitch = np.interp(t, turns_at, np.array([r[1] for r in rows]))
    radius = np.interp(t, turns_at, np.array([r[2] for r in rows])) / 2
    z = np.concatenate([[0.0], np.cumsum((pitch[1:] + pitch[:-1]) / 2 * np.diff(t))])
    angle = 2 * math.pi * t
    return np.column_stack([radius * np.cos(angle), radius * np.sin(angle), z])


def closed_rows(
    feature: Feature, radius: float, pitch: float, turns: float
) -> list[tuple[float, float, float]]:
    """Variable pitch rows for closed spring ends (TR162 item 2, D1923): the pitch is
    ``end_pitch`` (about the wire's diameter, so the end coil touches the next) at
    each end and grows to ``pitch`` over the first and last turn."""
    end = _positive(feature, "end_pitch", "end pitch")
    if end >= pitch:
        raise FeatureError(
            f"{feature.name}: the end pitch must be smaller than the pitch, about the wire's "
            "diameter. Enter a smaller end pitch."
        )
    if turns < 2.5:
        raise FeatureError(
            f"{feature.name}: closed ends need at least 2.5 turns: one at each end and some "
            "between. Enter more turns."
        )
    d = 2 * radius
    return [(0.0, end, d), (1.0, pitch, d), (turns - 1.0, pitch, d), (turns, end, d)]


def row_heights(rows: list[tuple[float, float, float]]) -> list[float]:
    """Height of each variable pitch row above the start (shown in the table)."""
    out = [0.0]
    for (t0, p0, _d0), (t1, p1, _d1) in itertools.pairwise(rows):
        out.append(out[-1] + (t1 - t0) * (p0 + p1) / 2)
    return out


@register
class Helix(FeatureType):
    """A helix or flat spiral from a sketch circle."""

    type_name = "helix"
    params = (
        ParamSpec("definition", choices=DEFINITIONS, default="pitch_turns"),
        ParamSpec("pitch_type", choices=("constant", "variable"), optional=True),
        ParamSpec("pitch", kind=Kind.LENGTH, optional=True),
        ParamSpec("turns", kind=Kind.NUMBER, optional=True),
        ParamSpec("height", kind=Kind.LENGTH, optional=True),
        ParamSpec("reverse", default=False, optional=True),
        ParamSpec("clockwise", default=False, optional=True),
        ParamSpec("start_angle", kind=Kind.ANGLE, optional=True),
        ParamSpec("taper_angle", kind=Kind.ANGLE, optional=True),
        ParamSpec("taper_outward", default=True, optional=True),
        ParamSpec("ends", choices=("open", "closed"), optional=True),  # TR162 (D1923)
        ParamSpec("end_pitch", kind=Kind.LENGTH, optional=True),
    )

    def kind_of(self, name: str) -> Kind | None:
        """Kinds of the numbered variable pitch values."""
        if name.startswith("vp_turns_"):
            return Kind.NUMBER
        if name.startswith(("vp_pitch_", "vp_diameter_")):
            return Kind.LENGTH
        return super().kind_of(name)

    def sizes(self, feature: Feature) -> tuple[float, float]:
        """Pitch and turns for a constant pitch curve, from its definition."""
        definition = str(feature.params.get("definition", "pitch_turns"))
        if definition in ("pitch_turns", "spiral"):
            pitch = _positive(feature, "pitch", "pitch")
            turns = _positive(feature, "turns", "number of turns")
        elif definition == "height_turns":
            turns = _positive(feature, "turns", "number of turns")
            pitch = _positive(feature, "height", "height") / turns
        else:
            pitch = _positive(feature, "pitch", "pitch")
            turns = _positive(feature, "height", "height") / pitch
        if turns > _MAX_TURNS:
            raise FeatureError(
                f"{feature.name}: {turns:g} turns is too many. Use at most {_MAX_TURNS:g}."
            )
        return pitch, turns

    def rows(self, feature: Feature) -> list[tuple[float, float, float]]:
        """The variable pitch rows: (turn, pitch, diameter)."""
        count = feature.params.get("vp_rows", 0)
        if not isinstance(count, int) or count < 2:
            raise FeatureError(
                f"{feature.name}: variable pitch needs at least two rows. Add a row."
            )
        rows: list[tuple[float, float, float]] = []
        for k in range(1, count + 1):
            turn = 0.0 if k == 1 else _value(feature, f"vp_turns_{k}", f"turn of row {k}")
            pitch = _positive(feature, f"vp_pitch_{k}", f"pitch of row {k}")
            diameter = _positive(feature, f"vp_diameter_{k}", f"diameter of row {k}")
            if rows and turn <= rows[-1][0]:
                raise FeatureError(
                    f"{feature.name}: row {k} must be at a later turn than row {k - 1}. "
                    "Enter a larger turn."
                )
            rows.append((turn, pitch, diameter))
        if rows[-1][0] > _MAX_TURNS:
            raise FeatureError(f"{feature.name}: use at most {_MAX_TURNS:g} turns.")
        return rows

    def curve(self, feature: Feature, ctx: BuildContext) -> TopoDS_Wire:
        """Build the curve."""
        owner = feature.name
        place = Placement(feature, ctx)
        definition = str(feature.params.get("definition", "pitch_turns"))
        reverse = feature.params.get("reverse") is True
        clockwise = feature.params.get("clockwise") is True
        start = feature.params.get("start_angle")
        start_angle = start.value if isinstance(start, Param) else 0.0
        variable = feature.params.get("pitch_type") == "variable"
        taper = feature.params.get("taper_angle")
        taper_angle = taper.value if isinstance(taper, Param) else 0.0
        if abs(taper_angle) > 1e-12 and (variable or definition == "spiral"):
            raise FeatureError(
                f"{owner}: taper works with a constant pitch helix only. Set the taper to 0."
            )
        if not abs(taper_angle) < math.radians(89):
            raise FeatureError(
                f"{owner}: the taper angle must be less than 89 degrees. Enter a smaller angle."
            )
        if definition == "spiral":
            if variable:
                raise FeatureError(
                    f"{owner}: variable pitch is for helices. Choose Constant pitch for a spiral."
                )
            pitch, turns = self.sizes(feature)
            if reverse and place.radius - pitch * turns <= 1e-6:
                raise FeatureError(
                    f"{owner}: the spiral reaches its centre. Use fewer turns or a smaller pitch."
                )
            # A spiral stays on the sketch plane: Reverse winds it inward.
            frame = _frame(place, False, clockwise, start_angle)
            return _through_points(frame, spiral_points(place.radius, pitch, turns, reverse))
        frame = _frame(place, reverse, clockwise, start_angle)
        if variable:
            return _through_points(frame, variable_points(self.rows(feature)))
        pitch, turns = self.sizes(feature)
        if feature.params.get("ends") == "closed":  # TR162 (D1923): spring end coils
            if abs(taper_angle) > 1e-12:
                raise FeatureError(
                    f"{owner}: closed ends work with a straight helix. Set the taper to 0."
                )
            return _through_points(
                frame, variable_points(closed_rows(feature, place.radius, pitch, turns))
            )
        outward = feature.params.get("taper_outward", True) is not False
        signed = taper_angle if outward else -taper_angle
        if signed < 0:
            end_radius = place.radius + pitch * turns * math.tan(signed)
            if end_radius <= 1e-6:
                raise FeatureError(
                    f"{owner}: the taper closes the helix before its end. "
                    "Use a smaller taper angle or fewer turns."
                )
        return _exact_helix(frame, place.radius, pitch, turns, signed)

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Make the curve; the part is unchanged."""
        result = curve_result(ctx, self.curve(feature, ctx))
        turns = self._sampled_turns(feature)
        if turns * POINTS_PER_TURN > MAX_POINTS:
            # Sampled curves thin out past this many turns (audit A item 10, D738).
            result.issues.append(
                Issue(
                    FeatureState.WARNING,
                    f"{feature.name} has {turns:g} turns, more than "
                    f"{MAX_POINTS // POINTS_PER_TURN} for a spiral or variable pitch curve, "
                    "so it is less exact. Use fewer turns, or split it into two curves.",
                    code="few_points",
                )
            )
        return result

    def _sampled_turns(self, feature: Feature) -> float:
        """Turns of a curve built through sample points (spiral or variable pitch); 0 for
        an exact helix."""
        if feature.params.get("pitch_type") == "variable":
            return max((r[0] for r in self.rows(feature)), default=0.0)
        if feature.params.get("definition") == "spiral":
            return self.sizes(feature)[1]
        return 0.0
