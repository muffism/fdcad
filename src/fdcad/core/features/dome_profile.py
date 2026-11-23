"""Dome constraint sketch (TR147 item 3, DECISIONS D2301).

A Dome's optional ``refs.profile_sketch`` names a sketch with a closed outline that
sets the dome's shape. The outline is read in the sketch's own coordinates, as the
flange profile is (D1101): X is the distance out from the middle of the face, Y the
height above it. The outline is turned a full turn about the sketch's Y axis, the
solid is set on the face with the Y axis through the face's middle along its normal,
and it is trimmed to the face's outline, so a round face gets a dome of exactly the
drawn section and other faces get the drawn section cut by their edges.
"""

from __future__ import annotations

import math

from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Vec
from OCP.TopoDS import TopoDS_Face, TopoDS_Shape

from fdcad.core.document.model import Feature
from fdcad.core.features import fastening as fx
from fdcad.core.features.base import BuildContext, FeatureError
from fdcad.core.features.solids import revolve, transform
from fdcad.core.naming.names import NamedShape

_TOL = 1e-6


def has_profile(feature: Feature) -> bool:
    """True when the dome has a profile sketch."""
    return isinstance(feature.refs.get("profile_sketch"), dict)


def _range(shape: TopoDS_Shape) -> tuple[float, float, float, float]:
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    lo, hi = box.CornerMin(), box.CornerMax()
    return lo.X(), hi.X(), lo.Y(), hi.Y()


def profile_dome(
    feature: Feature, ctx: BuildContext, face: TopoDS_Face, centre: fx.Vec3, up: fx.Vec3
) -> TopoDS_Shape:
    """The dome over ``face`` shaped by the profile sketch, growing out of it."""
    from fdcad.core.features.dome import _common
    from fdcad.core.features.sheetmetal.model import frame

    name = feature.name
    ref = feature.refs.get("profile_sketch")
    assert isinstance(ref, dict)
    out = ctx.result(str(ref.get("feature"))).sketch
    if out is None or out.profile is None:
        raise FeatureError(
            f"{name}: the dome profile must be a sketch with a closed outline. "
            "Close the profile sketch."
        )
    plane = out.plane
    to_local = frame(plane.origin, plane.x_dir, plane.normal).Inverted()
    from fdcad.core.features.solids import compound

    flat = NamedShape(compound(list(out.profile.faces)), [])
    local = transform(flat, to_local).shape
    x0, _x1, y0, y1 = _range(local)
    if x0 < -_TOL:
        raise FeatureError(
            f"{name}: the dome profile crosses its sketch's Y axis. "
            "Draw the profile at X = 0 or more, with X = 0 at the middle of the dome."
        )
    if y0 < -_TOL or y1 <= _TOL:
        raise FeatureError(
            f"{name}: the dome profile must lie above Y = 0 of its sketch. "
            "Move the profile up to Y = 0 or more."
        )
    y_axis = gp_Ax1(gp_Pnt(*plane.origin), gp_Dir(*fx.cross(plane.normal, plane.x_dir)))
    solid = revolve(f"{feature.id}/profile", out.profile, y_axis, 2 * math.pi, True).shape
    f = fx.frame(centre, up)
    side = fx.cross(f.x, up)
    placed = transform(NamedShape(solid, []), frame(centre, f.x, side).Multiplied(to_local))
    reach = gp_Vec(*fx.add((0.0, 0.0, 0.0), up, y1 * 1.01 + 1.0))
    column = BRepPrimAPI_MakePrism(face, reach).Shape()
    return _common(column, placed.shape)
