"""Wrap with a pull direction (TR75 item 2, D2112).

The wrapped face is swept along the pull direction, so the walls of the raised or
sunk shape run along it instead of square to the face. On a flat face the sweep goes
until it is the thickness away from the face. On a cylinder the sweep is cut to the
shell between the cylinder and the cylinder grown (emboss) or shrunk (deboss) by
the thickness. Kernel work: rebuild thread only.
"""

from __future__ import annotations

from typing import Any

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
from OCP.gp import gp_Ax2, gp_Pnt, gp_Vec

from fdcad.core.features import fastening as fx
from fdcad.core.features.base import FeatureError
from fdcad.core.features.solids import bounding_size, solids, volume_of
from fdcad.core.occ import BRepAlgoAPI_Common, BRepAlgoAPI_Cut


def _centre(face: Any) -> fx.Vec3:
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, props)
    c = props.CentreOfMass()
    return (c.X(), c.Y(), c.Z())


def pulled(
    owner: str,
    face: Any,
    kind: str,
    normal: fx.Vec3 | None,
    pull: fx.Vec3,
    thickness: float,
    outward: bool,
) -> Any:
    """The raised (``outward``) or sunk solid of ``face`` with walls along ``pull``.
    Raises FeatureError."""
    if kind == "plane":
        assert normal is not None
        along = fx.dot(pull, normal)
        if abs(along) < 0.017:
            raise FeatureError(
                f"{owner}: the pull direction lies along the face. "
                "Pick a direction that points out of the face."
            )
        sign = 1.0 if (along > 0) == outward else -1.0
        vector = fx.add((0, 0, 0), pull, sign * thickness / abs(along))
        return BRepPrimAPI_MakePrism(face, gp_Vec(*vector)).Shape()
    surface = BRepAdaptor_Surface(face)
    cylinder = surface.Cylinder()
    radius = cylinder.Radius()
    axis = cylinder.Axis()
    origin = axis.Location()
    direction = axis.Direction()
    a = (direction.X(), direction.Y(), direction.Z())
    centre = _centre(face)
    o = (origin.X(), origin.Y(), origin.Z())
    rel = fx.sub(centre, o)
    radial = fx.unit(fx.sub(rel, fx.add((0, 0, 0), a, fx.dot(rel, a))))
    along = fx.dot(pull, radial)
    if abs(along) < 0.017:
        raise FeatureError(
            f"{owner}: the pull direction runs along the cylinder at the shape. "
            "Pick a direction that points out of the face."
        )
    sign = 1.0 if (along > 0) == outward else -1.0
    size = bounding_size(face) + radius + thickness
    # Far enough to cross the shell, not so far as to reach the cylinder's far side.
    reach = min(4.0 * thickness / abs(along), 0.9 * radius + thickness)
    sweep = BRepPrimAPI_MakePrism(face, gp_Vec(*fx.add((0, 0, 0), pull, sign * reach))).Shape()
    length = 4.0 * size + 2.0 * abs(fx.dot(rel, a))
    base = gp_Pnt(*fx.add(o, a, -length / 2))
    frame = gp_Ax2(base, direction)
    outer_r, inner_r = (radius + thickness, radius) if outward else (radius, radius - thickness)
    if inner_r <= 0:
        raise FeatureError(f"{owner}: the deboss is deeper than the radius. Reduce the thickness.")
    outer = BRepPrimAPI_MakeCylinder(frame, outer_r, length).Shape()
    inner = BRepPrimAPI_MakeCylinder(frame, inner_r, length).Shape()
    shell = BRepAlgoAPI_Cut(outer, inner).Shape()
    common = BRepAlgoAPI_Common(sweep, shell)
    if not common.IsDone():
        raise FeatureError(f"{owner}: the pulled shape could not be made. Pick another direction.")
    shape = common.Shape()
    if not solids(shape) or volume_of(shape) <= 0:
        raise FeatureError(f"{owner}: the pulled shape is empty. Pick another direction.")
    return shape
