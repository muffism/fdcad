"""Resize Face for cones: a new half angle, one end kept (TR265 item 1, DECISIONS D799).

The cone face is drafted about the circle at the end that stays, which lies in
a plane square to the cone's axis (``BRepOffsetAPI_DraftAngle`` sets the face's
angle to the axis exactly). The faces around it follow the way a draft makes
them. Kernel work: call from the rebuild (CLAUDE.md rule 2).
"""

from __future__ import annotations

import math

from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepOffsetAPI import BRepOffsetAPI_DraftAngle
from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Cone
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape

from fdcad.core.features.base import FeatureError
from fdcad.core.naming.names import NamedShape, restrict

KEEP_ENDS = ("large", "small")
_ANGLE_TOL = 1e-6


def _ends(face: TopoDS_Face) -> list[tuple[float, gp_Pnt]]:
    """The cone face's end circles as (radius, centre), largest first."""
    out: list[tuple[float, gp_Pnt]] = []
    ex = TopExp_Explorer(face, TopAbs_EDGE)
    while ex.More():
        curve = BRepAdaptor_Curve(TopoDS.Edge(ex.Current()))
        ex.Next()
        if curve.GetType() == GeomAbs_Circle:
            circle = curve.Circle()
            radius, centre = circle.Radius(), circle.Location()
            if not any(abs(r - radius) < 1e-7 and c.Distance(centre) < 1e-7 for r, c in out):
                out.append((radius, centre))
    return sorted(out, key=lambda e: -e[0])


def is_cone(face: TopoDS_Face) -> bool:
    """True for a cone face."""
    return bool(BRepAdaptor_Surface(face).GetType() == GeomAbs_Cone)


def resize_cone(
    body: NamedShape,
    face: TopoDS_Face,
    half_angle: float,
    keep: str,
    fid: str,
    name: str,
    label: str,
) -> NamedShape:
    """``body`` with the cone ``face`` at ``half_angle`` to its axis, keeping the
    ``large`` or ``small`` end circle where it is."""
    from fdcad.core.features.direct import _carry_by_history, valid_solid

    if not 0 < half_angle < math.radians(89):
        raise FeatureError(
            f"{name}: the cone angle must be between 0 and 89 degrees. Type another angle.",
            highlight=[label],
        )
    ends = _ends(face)
    if len(ends) != 2:
        raise FeatureError(
            f"{name}: {label} is a cone with {len(ends)} round ends; Resize needs a cone "
            "cut off at both ends. Use Offset.",
            highlight=[label],
        )
    (r_big, c_big), (r_small, c_small) = ends
    fixed, other = ((r_big, c_big), (r_small, c_small)) if keep != "small" else ends[::-1]
    axis = gp_Dir(
        other[1].X() - fixed[1].X(), other[1].Y() - fixed[1].Y(), other[1].Z() - fixed[1].Z()
    )
    height = fixed[1].Distance(other[1])
    narrows = other[0] < fixed[0]
    want = fixed[0] + (-1 if narrows else 1) * height * math.tan(half_angle)
    if want <= 1e-6:
        raise FeatureError(
            f"{name}: at {math.degrees(half_angle):g} degrees the cone {label} would close "
            "before its other end. Use a smaller angle or keep the other end.",
            highlight=[label],
        )
    neutral = gp_Pln(fixed[1], axis)
    last: Exception | None = None
    for sign in (1.0, -1.0):
        op = BRepOffsetAPI_DraftAngle(body.shape)
        try:
            op.Add(face, axis, sign * half_angle, neutral)
            if not op.AddDone():
                continue
            op.Build()
            if not op.IsDone():
                continue
            shape = op.Shape()
        except Exception as exc:  # kernel failure: try the other sign, then report
            last = exc
            continue
        if not valid_solid(shape):
            continue
        made = [f for f in _cones(shape) if _fits(f, fixed, narrows, half_angle)]
        if len(made) == 1:
            named = _carry_by_history(body, op, shape)
            return NamedShape(shape, restrict(named, shape, f"{fid}/cone"))
    why = f" ({type(last).__name__})" if last is not None else ""
    raise FeatureError(
        f"{name} failed: {label} cannot take that angle{why}. Try a smaller change, or keep "
        "the other end.",
        highlight=[label],
    )


def _cones(shape: TopoDS_Shape) -> list[TopoDS_Face]:
    from fdcad.core.naming.names import faces_of

    return [f for f in faces_of(shape) if is_cone(f)]


def _fits(face: TopoDS_Face, fixed: tuple[float, gp_Pnt], narrows: bool, angle: float) -> bool:
    """True when ``face`` has the angle, keeps the fixed end, and still narrows (or widens)
    away from it. Its other end may be where it now meets a neighbour (a hole wall)."""
    semi = abs(BRepAdaptor_Surface(face).Cone().SemiAngle())
    if abs(semi - angle) > _ANGLE_TOL:
        return False
    ends = _ends(face)
    has_fixed = any(abs(r - fixed[0]) < 1e-6 and c.Distance(fixed[1]) < 1e-6 for r, c in ends)
    others = [r for r, c in ends if c.Distance(fixed[1]) > 1e-6]
    if not has_fixed or not others:
        return False
    return all((r < fixed[0]) == narrows for r in others)
