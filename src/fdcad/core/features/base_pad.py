"""Base pad (TUTORIAL_REVIEW_SPEC TR414 item 2, DECISIONS D1009).

Type ``base_pad``. Pick the flat face that lies on the bed (``refs.face``). A thin
removable pad, ``pad_thickness`` thick, is added under it as a body of its own: its
outline is the face's outline grown by ``pad_margin``, and an ``air_gap`` separates
it from the face so it peels off after printing. With no gap the pad touches the
face but stays a separate body. New faces are ``<fid>/pad/...``.
"""

from __future__ import annotations

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


def _value(feature: Feature, key: str, default: float) -> float:
    found = feature.params.get(key)
    return found.value if isinstance(found, Param) else default


@register
class BasePad(FeatureType):
    """A thin pad body under the bed face, with an air gap."""

    type_name = "base_pad"
    makes_solid = True
    params = (
        ParamSpec("pad_thickness", kind=Kind.LENGTH),
        ParamSpec("pad_margin", kind=Kind.LENGTH, optional=True),
        ParamSpec("air_gap", kind=Kind.LENGTH, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Add the pad body."""
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
        from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
        from OCP.GeomAbs import GeomAbs_Plane
        from OCP.gp import gp_Trsf, gp_Vec
        from OCP.TopAbs import TopAbs_REVERSED

        from fdcad.core.features.bodies import join
        from fdcad.core.features.profile_offset import offset_face
        from fdcad.core.naming.names import NamedShape, faces_of
        from fdcad.core.naming.resolve import resolve_face

        name = feature.name
        if ctx.body is None:
            raise FeatureError(f"{name}: the part is empty. Add a body first.")
        refs = feature.refs.get("face")
        ref = refs[0] if isinstance(refs, list) and refs else refs
        if not isinstance(ref, dict):
            raise FeatureError(f"{name}: pick the flat face that lies on the print bed.")
        face = resolve_face(ctx.body, ref, name)[0]
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() != GeomAbs_Plane:
            raise FeatureError(f"{name}: the picked face is not flat. Pick the bed face.")
        thickness = _value(feature, "pad_thickness", 0.6)
        margin = _value(feature, "pad_margin", 3.0)
        gap = _value(feature, "air_gap", 0.2)
        if thickness <= 0 or margin < 0 or gap < 0:
            raise FeatureError(
                f"{name}: the thickness must be above zero and the margin and gap not below "
                "zero. Enter other values."
            )
        outline = face
        if margin > 1e-9:
            try:
                outline = offset_face(face, margin)[0]
            except ValueError:
                raise FeatureError(
                    f"{name}: the face's outline could not be grown. Enter a smaller margin."
                ) from None
        normal = surface.Plane().Axis().Direction()
        if face.Orientation() == TopAbs_REVERSED:
            normal.Reverse()
        down = gp_Vec(normal)  # out of the part, toward the bed
        move = gp_Trsf()
        move.SetTranslation(down.Multiplied(gap))
        start = BRepBuilderAPI_Transform(outline, move, True).Shape()
        pad = BRepPrimAPI_MakePrism(start, down.Multiplied(thickness)).Shape()
        names = [(f"{feature.id}/pad/{j}", f) for j, f in enumerate(faces_of(pad), 1)]
        result = join([ctx.body, NamedShape(pad, names)], feature.id)
        assert result is not None
        return FeatureResult(body=result)
