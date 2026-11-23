"""Living hinge patterns (TUTORIAL_REVIEW_SPEC_2 TR402, DECISIONS D908).

Type ``living_hinge``. A sketch on a plate face (``refs.sketch``) outlines the area
that should bend (its closed profile). Rows of slits run along the sketch's X axis
across that area and are cut through the part: each slit ``slit_length`` long and
``slit_width`` wide, ``bridge`` of material between slits in a row, rows
``row_spacing`` apart, every other row shifted by half a slit so the bridges stagger.
Slits are clipped to the outline. New faces are ``<fid>/slit/...``.
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

#: The most slits one hinge makes.
MAX_SLITS = 4000


def _value(feature: Feature, key: str, default: float) -> float:
    found = feature.params.get(key)
    return found.value if isinstance(found, Param) else default


def slit_rects(
    box: tuple[float, float, float, float],
    length: float,
    width: float,
    bridge: float,
    spacing: float,
) -> list[tuple[float, float, float, float]]:
    """Slit rectangles (x0, y0, x1, y1) over the sketch box (x0, y0, x1, y1), staggered
    row by row, before clipping to the outline."""
    x0, y0, x1, y1 = box
    pitch = length + bridge
    out: list[tuple[float, float, float, float]] = []
    row = 0
    y = y0 + spacing / 2
    while y < y1 and len(out) <= MAX_SLITS:
        shift = 0.0 if row % 2 == 0 else pitch / 2
        x = x0 - shift
        while x < x1:
            out.append((x, y - width / 2, x + length, y + width / 2))
            x += pitch
        y += spacing
        row += 1
    return out


@register
class LivingHinge(FeatureType):
    """Staggered slits through a plate so it bends."""

    type_name = "living_hinge"
    makes_solid = True
    params = (
        ParamSpec("slit_length", kind=Kind.LENGTH),
        ParamSpec("slit_width", kind=Kind.LENGTH),
        ParamSpec("bridge", kind=Kind.LENGTH),
        ParamSpec("row_spacing", kind=Kind.LENGTH),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Cut the slits."""
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
        from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
        from OCP.gp import gp_Vec

        from fdcad.core.features.sketch import sketch_input
        from fdcad.core.features.solids import bounding_size, check_result, compound, solids
        from fdcad.core.naming.names import NamedShape, carry, restrict
        from fdcad.core.occ import BRepAlgoAPI_Common, BRepAlgoAPI_Cut

        name = feature.name
        if ctx.body is None:
            raise FeatureError(f"{name}: the part is empty. Add the plate first.")
        length = _value(feature, "slit_length", 20.0)
        width = _value(feature, "slit_width", 0.3)
        bridge = _value(feature, "bridge", 3.0)
        spacing = _value(feature, "row_spacing", 2.0)
        if min(length, width, bridge, spacing) <= 0:
            raise FeatureError(f"{name}: every slit size must be above zero. Enter the sizes.")
        if width >= spacing:
            raise FeatureError(
                f"{name}: the slits are wider than the row spacing. "
                "Make the row spacing larger than the slit width."
            )
        sketch = sketch_input(feature, ctx)
        if sketch.profile is None or not sketch.profile.faces:
            raise FeatureError(f"{name}: the sketch has no closed outline. Draw the hinge area.")
        plane = sketch.plane
        us, vs = [], []
        from OCP.BRep import BRep_Tool
        from OCP.TopAbs import TopAbs_VERTEX
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopoDS import TopoDS

        for face in sketch.profile.faces:
            exp = TopExp_Explorer(face, TopAbs_VERTEX)
            while exp.More():
                p = BRep_Tool.Pnt_s(TopoDS.Vertex(exp.Current()))
                u, v, _h = plane.to_2d(p.X(), p.Y(), p.Z())
                us.append(u)
                vs.append(v)
                exp.Next()
        if not us:
            raise FeatureError(f"{name}: the outline has no corners FDCAD can read. Use lines.")
        rects = slit_rects((min(us), min(vs), max(us), max(vs)), length, width, bridge, spacing)
        if len(rects) > MAX_SLITS:
            raise FeatureError(
                f"{name}: that makes too many slits. Use longer slits or more spacing."
            )
        reach = 2 * bounding_size(ctx.body.shape) + 10.0
        n = plane.normal
        faces = []
        for x0, y0, x1, y1 in rects:
            poly = BRepBuilderAPI_MakePolygon()
            for u, v in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
                poly.Add(plane.to_3d(u, v).Translated(gp_Vec(*n).Multiplied(reach / 2)))
            poly.Close()
            faces.append(BRepBuilderAPI_MakeFace(poly.Wire(), True).Face())
        slits = BRepPrimAPI_MakePrism(compound(faces), gp_Vec(*n).Multiplied(-reach)).Shape()
        area = sketch.profile.faces
        outline = BRepPrimAPI_MakePrism(
            compound([BRepBuilderAPI_MakeFace(f).Face() for f in area]),
            gp_Vec(*n).Multiplied(-reach),
        ).Shape()
        from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
        from OCP.gp import gp_Trsf

        lift = gp_Trsf()
        lift.SetTranslation(gp_Vec(*n).Multiplied(reach / 2))
        outline = BRepBuilderAPI_Transform(outline, lift, True).Shape()
        tool = BRepAlgoAPI_Common(slits, outline).Shape()
        if not solids(tool):
            raise FeatureError(f"{name}: no slit fits in the outline. Use shorter slits.")

        def cut(body: NamedShape) -> NamedShape:
            op = BRepAlgoAPI_Cut(body.shape, tool)
            op.Build()
            if not op.IsDone() or not solids(op.Shape()):
                raise FeatureError(
                    f"{name}: the slits could not be cut. Check the outline is on the plate."
                )
            shape: Any = op.Shape()
            return NamedShape(
                shape, restrict(carry(body.faces, op.History()), shape, f"{feature.id}/slit")
            )

        # The slits go through the plate the outline was drawn on (D1077). They were cut
        # from the whole part, and went on through a body lying on the plate. A sketch
        # on a plane, not on a face, still slits every body it meets.
        from fdcad.core.features.bodies import in_body_of, sketch_face

        drawn_on = sketch_face(feature, ctx)
        if drawn_on is None:
            result = cut(ctx.body)
        else:
            result = in_body_of(ctx.body, drawn_on, feature.id, cut)
        issues = check_result(feature.id, name, ctx.body, result, None)
        return FeatureResult(body=result, issues=issues)
