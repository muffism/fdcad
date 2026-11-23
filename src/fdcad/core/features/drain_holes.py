"""Drain holes (TUTORIAL_REVIEW_SPEC TR189 item 3, DECISIONS D1006).

Type ``drain_holes``. For every closed void of the part (a hollow left by Shell with
no face removed, core/cavities.py), one round hole ``hole_diameter`` across is cut
from the void's lowest point (``toward`` "bottom") or highest point ("top") straight
down or up along Z, out through the part's wall, so liquid resin drains from where
it pools. The holes run past the part, so they always open to the outside. New
faces are ``<fid>/drain/<k>/...``.
"""

from __future__ import annotations

from typing import Any

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    register,
)
from fdcad.core.units import Kind

Vec3 = tuple[float, float, float]


def extreme_point(shell: Any, up: bool, reach: float) -> Vec3:
    """The lowest (or with ``up`` the highest) point of a void's shell along Z."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.gp import gp_Dir, gp_Pln, gp_Pnt

    box = Bnd_Box()
    BRepBndLib.Add_s(shell, box)
    lo, hi = box.CornerMin(), box.CornerMax()
    z = hi.Z() + reach if up else lo.Z() - reach
    middle = gp_Pnt((lo.X() + hi.X()) / 2, (lo.Y() + hi.Y()) / 2, z)
    size = 2 * (reach + hi.Distance(lo))
    plane = BRepBuilderAPI_MakeFace(
        gp_Pln(middle, gp_Dir(0, 0, 1)), -size, size, -size, size
    ).Face()
    nearest = BRepExtrema_DistShapeShape(shell, plane)
    if not nearest.IsDone() or nearest.NbSolution() == 0:
        c = lo if not up else hi
        return (c.X(), c.Y(), c.Z())
    p = nearest.PointOnShape1(1)
    floor = _flat_floor(shell, p.Z())
    return floor if floor is not None else (p.X(), p.Y(), p.Z())


def _flat_floor(shell: Any, z: float) -> Vec3 | None:
    """The middle of the largest level flat face at height ``z``: a flat floor (or
    ceiling) drains best from its middle, away from the walls."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepGProp import BRepGProp
    from OCP.GeomAbs import GeomAbs_Plane
    from OCP.GProp import GProp_GProps

    from fdcad.core.naming.names import faces_of

    best: tuple[float, Vec3] | None = None
    for face in faces_of(shell):
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() != GeomAbs_Plane:
            continue
        plane = surface.Plane()
        if abs(abs(plane.Axis().Direction().Z()) - 1.0) > 1e-9:
            continue
        if abs(plane.Location().Z() - z) > 1e-6:
            continue
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, props)
        c = props.CentreOfMass()
        if best is None or props.Mass() > best[0]:
            best = (props.Mass(), (c.X(), c.Y(), z))
    return None if best is None else best[1]


@register
class DrainHoles(FeatureType):
    """A hole from the lowest point of each closed void out through the wall."""

    type_name = "drain_holes"
    makes_solid = True
    params = (
        ParamSpec("hole_diameter", kind=Kind.LENGTH),
        ParamSpec("toward", choices=("bottom", "top"), optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Cut the holes."""
        from OCP.Bnd import Bnd_Box
        from OCP.BRepBndLib import BRepBndLib
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
        from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

        from fdcad.core.cavities import enclosed_voids
        from fdcad.core.features.booleans import boolean_named
        from fdcad.core.features.solids import check_result, compound
        from fdcad.core.naming.names import NamedShape, faces_of

        name = feature.name
        if ctx.body is None:
            raise FeatureError(f"{name}: the part is empty. Add a body first.")
        found = feature.params.get("hole_diameter")
        diameter = found.value if isinstance(found, Param) else 3.0
        if diameter <= 0:
            raise FeatureError(f"{name}: the hole diameter must be above zero. Enter one.")
        voids = enclosed_voids(ctx.body.shape)
        if not voids:
            raise FeatureError(
                f"{name}: the part has no closed hollow inside. Use Shell with no face removed "
                "first, or delete this feature."
            )
        up = feature.params.get("toward", "bottom") == "top"
        box = Bnd_Box()
        BRepBndLib.Add_s(ctx.body.shape, box)
        lo, hi = box.CornerMin(), box.CornerMax()
        reach = hi.Distance(lo) + 1.0
        direction = gp_Dir(0, 0, 1) if up else gp_Dir(0, 0, -1)
        holes = []
        for void in voids:
            x, y, z = extreme_point(void.shell, up, reach)
            # Start a little inside the void so the hole opens into it cleanly.
            back = diameter / 2 if not up else -diameter / 2
            start = gp_Pnt(x, y, z + back)
            length = (z + back - lo.Z() + 1.0) if not up else (hi.Z() - (z + back) + 1.0)
            holes.append(
                BRepPrimAPI_MakeCylinder(gp_Ax2(start, direction), diameter / 2, length).Shape()
            )
        names = [
            (f"{feature.id}/drain/{k + 1}/{j}", f)
            for k, hole in enumerate(holes)
            for j, f in enumerate(faces_of(hole), 1)
        ]
        tool = NamedShape(compound(holes), names)
        result = boolean_named("cut", ctx.body, tool, feature.id, name)
        return FeatureResult(
            body=result, issues=check_result(feature.id, name, ctx.body, result, None)
        )
