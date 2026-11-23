"""Mould Cavity: the negative of a part in a block (TR85 item 1, D2111).

Refs: ``main``: a face of the block body; ``part``: a face of the part body;
``coord_system``: optional, a coordinate system feature (``{"feature": id}``).

Params:
- ``uniform``: boolean (default true). ``factor``: number, for uniform shrinkage
  scaling; ``fx``, ``fy``, ``fz``: numbers along X, Y and Z otherwise.
- ``about``: "centroid" (default, the part's centre of volume), "origin" or
  "coord_system" (the origin of ``refs.coord_system``).
- ``keep_part``: boolean (default true): the part body stays; off removes it.

The part, scaled, is subtracted from the block. Faces keep their names; the block's
new faces are named from the part's faces. Bodies not picked stay as they are.
Item 2 (a tooling split with a flat parting plane) is left to Split (D233).
"""

from __future__ import annotations

from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy, BRepBuilderAPI_GTransform
from OCP.gp import gp_GTrsf, gp_Mat, gp_XYZ
from OCP.TopoDS import TopoDS

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.features.bodies import body_index, join, rest_of, sub_body
from fdcad.core.features.booleans import boolean_named
from fdcad.core.features.direct import valid_solid
from fdcad.core.features.solids import check_result
from fdcad.core.naming.names import NamedShape, restrict
from fdcad.core.units import Kind

#: Shrinkage factors outside this range are refused.
LIMITS = (0.5, 2.0)


def _factor(feature: Feature, name: str) -> float:
    value = feature.params.get(name)
    factor = value.value if isinstance(value, Param) else 1.0
    if not LIMITS[0] <= factor <= LIMITS[1]:
        raise FeatureError(
            f"{feature.name}: scale {factor:g} is out of range. "
            f"Enter a value from {LIMITS[0]:g} to {LIMITS[1]:g}, such as 1.02 for 2% shrinkage."
        )
    return factor


@register
class MouldCavity(FeatureType):
    """Subtracts a scaled part from a block body."""

    type_name = "mould_cavity"
    makes_solid = True
    params = (
        ParamSpec("uniform", default=True, optional=True),
        ParamSpec("factor", kind=Kind.NUMBER, optional=True),
        *(ParamSpec(k, kind=Kind.NUMBER, optional=True) for k in ("fx", "fy", "fz")),
        ParamSpec("about", choices=("centroid", "origin", "coord_system"), optional=True),
        ParamSpec("keep_part", default=True, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Cut the scaled part out of the block."""
        body, issues = self._build(feature, ctx)
        issues += check_result(feature.id, feature.name, ctx.body, body, None)
        return FeatureResult(body=body, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The part after the cut, for the live preview."""
        return self._build(feature, ctx)[0]

    def _build(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        name = feature.name
        if ctx.body is None:
            raise FeatureError(f"{name}: the part has no bodies. Add a block and a part first.")
        part_ref = feature.refs.get("part")
        if isinstance(part_ref, list):
            part_ref = part_ref[0] if part_ref else None
        if not feature.refs.get("main") or not isinstance(part_ref, dict):
            raise FeatureError(f"{name}: pick the block and the part to make the cavity of.")
        block_index, issues = body_index(ctx, feature.refs["main"], name)
        part_index, found = body_index(ctx, part_ref, name)
        issues += found
        if block_index == part_index:
            raise FeatureError(f"{name}: the block and the part are one body. Pick two bodies.")
        part = sub_body(ctx.body, [part_index], feature.id)
        block = sub_body(ctx.body, [block_index], feature.id)
        scaled = self._scaled(feature, ctx, part)
        cavity = boolean_named("cut", block, scaled, feature.id, name)
        keep = feature.params.get("keep_part", True) is not False
        gone = [block_index] if keep else [block_index, part_index]
        result = join([rest_of(ctx.body, gone, feature.id), cavity], feature.id)
        assert result is not None
        return result, issues

    def _centre(self, feature: Feature, ctx: BuildContext, part: NamedShape) -> tuple[float, ...]:
        about = feature.params.get("about", "centroid")
        if about == "origin":
            return (0.0, 0.0, 0.0)
        if about == "coord_system":
            ref = feature.refs.get("coord_system")
            if isinstance(ref, list):
                ref = ref[0] if ref else None
            fid = ref.get("feature") if isinstance(ref, dict) else None
            if not isinstance(fid, str):
                raise FeatureError(f"{feature.name}: pick the coordinate system to scale about.")
            datum = ctx.result(fid).datum
            if datum is None:
                raise FeatureError(
                    f"{feature.name}: the picked feature is not a coordinate system. Pick one."
                )
            return tuple(datum.origin)
        from OCP.BRepGProp import BRepGProp
        from OCP.GProp import GProp_GProps

        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(part.shape, props)
        c = props.CentreOfMass()
        return (c.X(), c.Y(), c.Z())

    def _scaled(self, feature: Feature, ctx: BuildContext, part: NamedShape) -> NamedShape:
        if feature.params.get("uniform", True) is not False:
            fx = fy = fz = _factor(feature, "factor")
        else:
            fx, fy, fz = (_factor(feature, k) for k in ("fx", "fy", "fz"))
        centre = self._centre(feature, ctx, part)
        rows = ((fx, 0.0, 0.0), (0.0, fy, 0.0), (0.0, 0.0, fz))
        gtrsf = gp_GTrsf()
        gtrsf.SetVectorialPart(gp_Mat(*rows[0], *rows[1], *rows[2]))
        gtrsf.SetTranslationPart(gp_XYZ(*(centre[i] * (1.0 - rows[i][i]) for i in range(3))))
        try:
            copier = BRepBuilderAPI_Copy(part.shape, True, False)
            maker = BRepBuilderAPI_GTransform(copier.Shape(), gtrsf, True)
            shape = maker.Shape()
            names = [
                (n, TopoDS.Face(maker.ModifiedShape(copier.Modified(f).First())))
                for n, f in part.faces
            ]
        except Exception as exc:
            raise FeatureError(
                f"{feature.name} failed in the geometry kernel. Try another scale."
            ) from exc
        if not valid_solid(shape):
            raise FeatureError(f"{feature.name} made invalid geometry. Try another scale.")
        return NamedShape(shape, restrict(names, shape, feature.id))
