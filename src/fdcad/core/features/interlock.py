"""Material interlock teeth (TUTORIAL_REVIEW_SPEC TR414 item 1, DECISIONS D1216).

Type ``interlock``. Pick a flat face of one body that lies against another body
(``refs.face``), where two bodies printed in different materials meet. The
boundary gets a checkerboard of square teeth, ``tooth_size`` wide and
``tooth_depth`` deep: on one colour of squares the picked body reaches into the
other, on the other colour the other body reaches back, so the two materials
lock together. The teeth stay inside the face's outline. Each body stays its own
body; new faces are ``<fid>/teeth/...``.
"""

from __future__ import annotations

from typing import Any

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.BRepGProp import BRepGProp
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.GeomAbs import GeomAbs_Plane
from OCP.gp import gp_Pnt, gp_Vec
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_IN, TopAbs_REVERSED
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    register,
)
from fdcad.core.occ import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from fdcad.core.units import Kind

#: The most teeth one feature makes.
MAX_TEETH = 2500


def _value(feature: Feature, key: str, default: float) -> float:
    found = feature.params.get(key)
    return found.value if isinstance(found, Param) else default


def _bool_op(kind: type, a: TopoDS_Shape, b: TopoDS_Shape) -> tuple[TopoDS_Shape, Any]:
    from fdcad.core.features.solids import FUZZY_TOLERANCE

    op = kind(a, b)
    op.SetFuzzyValue(FUZZY_TOLERANCE)
    op.Build()
    if not op.IsDone():
        raise ValueError("a boolean of the teeth failed")
    return op.Shape(), op.History()


@register
class Interlock(FeatureType):
    """A checkerboard of teeth where two bodies meet."""

    type_name = "interlock"
    makes_solid = True
    params = (
        ParamSpec("tooth_size", kind=Kind.LENGTH),
        ParamSpec("tooth_depth", kind=Kind.LENGTH),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Cut and add the teeth on both bodies."""
        from fdcad.core.features.bodies import solid_of_face
        from fdcad.core.features.solids import compound, polygon_face, solids
        from fdcad.core.io.flat_export import face_plane
        from fdcad.core.naming.names import NamedShape, carry, restrict
        from fdcad.core.naming.resolve import resolve_face

        name, fid = feature.name, feature.id
        if ctx.body is None:
            raise FeatureError(f"{name}: the part is empty. Add two bodies first.")
        refs = feature.refs.get("face")
        ref = refs[0] if isinstance(refs, list) and refs else refs
        if not isinstance(ref, dict):
            raise FeatureError(f"{name}: pick the flat face where the two bodies meet.")
        face = resolve_face(ctx.body, ref, name)[0]
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() != GeomAbs_Plane:
            raise FeatureError(f"{name}: the picked face is not flat. Pick a flat face.")
        size = _value(feature, "tooth_size", 3.0)
        depth = _value(feature, "tooth_depth", 1.5)
        if size <= 0 or depth <= 0:
            raise FeatureError(
                f"{name}: the tooth size and depth must be above zero. Enter other values."
            )
        normal = surface.Plane().Axis().Direction()
        if face.Orientation() == TopAbs_REVERSED:
            normal.Reverse()
        out = gp_Vec(normal)  # out of the picked body, into the other one
        parts = solids(ctx.body.shape)
        own = solid_of_face(ctx.body.shape, face)
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, props)
        centre = props.CentreOfMass()
        probe = centre.Translated(out.Multiplied(min(depth, size) * 0.25))
        other = -1
        for i, part in enumerate(parts):
            if i == own:
                continue
            test = BRepClass3d_SolidClassifier(part, probe, 1e-7)
            if test.State() == TopAbs_IN:
                other = i
                break
        if own < 0 or other < 0:
            raise FeatureError(
                f"{name}: no other body lies against the picked face. Pick a face where two "
                "bodies meet."
            )
        # The face's extent in its own plane, then the checkerboard over it.
        plane = face_plane(face)
        x_dir, y_dir, origin = plane.XDirection(), plane.YDirection(), plane.Location()
        from OCP.Bnd import Bnd_Box
        from OCP.BRepBndLib import BRepBndLib
        from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
        from OCP.gp import gp_Trsf

        to_plane = gp_Trsf()
        to_plane.SetTransformation(plane)
        box = Bnd_Box()
        BRepBndLib.Add_s(BRepBuilderAPI_Transform(face, to_plane, True).Shape(), box)
        lo, hi = box.CornerMin(), box.CornerMax()
        nx = int((hi.X() - lo.X()) / size) + 1
        ny = int((hi.Y() - lo.Y()) / size) + 1
        if nx * ny > MAX_TEETH:
            raise FeatureError(f"{name}: more than {MAX_TEETH} teeth. Enter a larger tooth size.")

        def square(i: int, j: int) -> TopoDS_Shape:
            u0, v0 = lo.X() + i * size, lo.Y() + j * size
            pts = []
            for du, dv in ((0, 0), (size, 0), (size, size), (0, size)):
                p = gp_Pnt(origin.XYZ())
                p.Translate(gp_Vec(x_dir).Multiplied(u0 + du))
                p.Translate(gp_Vec(y_dir).Multiplied(v0 + dv))
                pts.append((p.X(), p.Y(), p.Z()))
            return polygon_face(pts)

        out_cells = [square(i, j) for i in range(nx) for j in range(ny) if (i + j) % 2 == 0]
        in_cells = [square(i, j) for i in range(nx) for j in range(ny) if (i + j) % 2 == 1]
        reach = BRepPrimAPI_MakePrism(face, out.Multiplied(depth)).Shape()
        back = BRepPrimAPI_MakePrism(face, out.Reversed().Multiplied(depth)).Shape()
        try:
            forward, _h = _bool_op(
                BRepAlgoAPI_Common,
                compound(
                    [BRepPrimAPI_MakePrism(c, out.Multiplied(depth)).Shape() for c in out_cells]
                ),
                reach,
            )
            backward, _h = _bool_op(
                BRepAlgoAPI_Common,
                compound(
                    [
                        BRepPrimAPI_MakePrism(c, out.Reversed().Multiplied(depth)).Shape()
                        for c in in_cells
                    ]
                ),
                back,
            )
            a, b = parts[own], parts[other]
            names = list(ctx.body.faces)
            a, h1 = _bool_op(BRepAlgoAPI_Fuse, a, forward)
            names = carry(names, h1)
            a, h2 = _bool_op(BRepAlgoAPI_Cut, a, backward)
            names = carry(names, h2)
            b, h3 = _bool_op(BRepAlgoAPI_Cut, b, forward)
            names = carry(names, h3)
            b, h4 = _bool_op(BRepAlgoAPI_Fuse, b, backward)
            names = carry(names, h4)
        except ValueError:
            raise FeatureError(
                f"{name}: the teeth could not be made. "
                "Enter a larger tooth size or a smaller depth."
            ) from None
        kept = [p for i, p in enumerate(parts) if i not in (own, other)]
        new_a, new_b = solids(a), solids(b)
        if not new_a or not new_b:
            raise FeatureError(f"{name}: the teeth broke a body apart. Enter a smaller depth.")
        shape = compound([*new_a, *new_b, *kept])
        # New tooth faces get ``<fid>/teeth/face#k`` from restrict.
        named = restrict(names, shape, f"{fid}/teeth")
        return FeatureResult(body=NamedShape(shape, named))
