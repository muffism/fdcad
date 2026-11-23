"""Scale bodies (PHASE3_SPEC P3.8 item 1, PLAN Phase 3, DECISIONS D235).

Params:
- ``uniform``: boolean (default true). ``factor``: number, for uniform scaling;
  ``fx``, ``fy``, ``fz``: numbers along X, Y and Z otherwise.
- ``about``: "centroid" (default, the centre of the picked bodies), "origin" or
  "point" (``ox``, ``oy``, ``oz`` lengths).

Shear (TR371 item 3, D1000): ``shear_angle`` (angle, optional) slides the bodies
along ``shear_along`` ("x", "y" or "z") by the distance from the centre along
``shear_from`` (another axis) times the tangent of the angle. It is applied after
the scale factors.

Refs: ``bodies``: optional face references to faces of the bodies; without
any, every body is scaled.

Faces keep their names. A per axis scale turns circles into ellipses, so
those faces become general surfaces.
"""

from __future__ import annotations

from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_Copy,
    BRepBuilderAPI_GTransform,
    BRepBuilderAPI_Transform,
)
from OCP.gp import gp_GTrsf, gp_Mat, gp_Pnt, gp_Trsf, gp_XYZ
from OCP.TopoDS import TopoDS

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureState,
    FeatureType,
    Issue,
    ParamSpec,
    PreviewHandle,
    register,
    value_label,
)
from fdcad.core.features.bodies import body_indices, join, rest_of, sub_body
from fdcad.core.features.direct import valid_solid
from fdcad.core.features.solids import bounding_size, solids
from fdcad.core.naming.names import NamedShape, centroid, restrict
from fdcad.core.units import Kind

_LIMIT = (1e-3, 1e3)
_AXES = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
_AXIS_NAMES = ("x", "y", "z")
#: The steepest shear, in degrees (TR371).
SHEAR_LIMIT = 80.0


def shear_of(feature: Feature) -> tuple[int, int, float] | None:
    """(along, from, tangent) of the shear, or None when there is none (TR371)."""
    import math

    angle = feature.params.get("shear_angle")
    if not isinstance(angle, Param) or abs(angle.value) < 1e-12:
        return None
    if abs(math.degrees(angle.value)) >= SHEAR_LIMIT:
        raise FeatureError(
            f"{feature.name}: the shear angle must be less than {SHEAR_LIMIT:g} degrees. "
            "Enter a smaller angle."
        )
    along = _AXIS_NAMES.index(str(feature.params.get("shear_along", "x")))
    source = _AXIS_NAMES.index(str(feature.params.get("shear_from", "z")))
    if along == source:
        raise FeatureError(
            f"{feature.name}: the shear slides along and measures from the same axis. "
            "Pick two different axes."
        )
    return along, source, math.tan(angle.value)


#: Ruler ticks of a scale handle, as a factor (D411).
FACTOR_STEP = 0.1


def _factor(feature: Feature, name: str) -> float:
    value = feature.params.get(name)
    if not isinstance(value, Param):
        raise FeatureError(
            f"{feature.name}: the {value_label(name)} value is missing. Enter a scale factor."
        )
    if not _LIMIT[0] <= value.value <= _LIMIT[1]:
        raise FeatureError(
            f"{feature.name}: the scale factor must be between {_LIMIT[0]:g} and {_LIMIT[1]:g}. "
            "Enter a factor in that range."
        )
    return value.value


@register
class Scale(FeatureType):
    """Scales bodies uniformly or along each axis."""

    type_name = "scale"
    makes_solid = True
    params = (
        ParamSpec("uniform", default=True, optional=True),
        ParamSpec("factor", kind=Kind.NUMBER, optional=True),
        *(ParamSpec(k, kind=Kind.NUMBER, optional=True) for k in ("fx", "fy", "fz")),
        ParamSpec("about", choices=("centroid", "origin", "point"), optional=True),
        *(ParamSpec(k, kind=Kind.LENGTH, optional=True) for k in ("ox", "oy", "oz")),
        ParamSpec("shear_angle", kind=Kind.ANGLE, optional=True),  # TR371 (D1000)
        ParamSpec("shear_along", choices=_AXIS_NAMES, optional=True),
        ParamSpec("shear_from", choices=_AXIS_NAMES, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Scale the bodies."""
        body, issues = self._build(feature, ctx)
        meshes = [
            f.name
            for f in ctx.document.features
            if f.type == "import_mesh"
            and f.id in ctx.results
            and ctx.results[f.id].extras.get("reference") is not None
            and f.params.get("convert") is not True
        ]
        if meshes:
            # Spec 2 section 20 item 20 (D715): reference meshes are not solids, so Scale
            # leaves them as they are; say so instead of leaving them behind silently.
            issues = [
                *issues,
                Issue(
                    FeatureState.WARNING,
                    f"{feature.name} scales solid bodies only, so {', '.join(meshes)} keeps "
                    "its size. Tick Convert to Solid on the mesh to scale it too.",
                    code="mesh_not_scaled",
                ),
            ]
        return FeatureResult(body=body, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The scaled part, for the live preview."""
        return self._build(feature, ctx)[0]

    def _build(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        name = feature.name
        if ctx.body is None:
            raise FeatureError(f"{name}: the part has no bodies to scale. Add a body first.")
        if feature.refs.get("bodies"):
            indices, issues = body_indices(ctx, feature.refs["bodies"], name)
        else:
            indices, issues = list(range(len(solids(ctx.body.shape)))), []
        picked = sub_body(ctx.body, indices, feature.id)
        centre = self._centre(feature, picked)
        uniform = feature.params.get("uniform", True) is not False
        shear = shear_of(feature)
        try:
            if uniform and shear is None:
                trsf = gp_Trsf()
                trsf.SetScale(gp_Pnt(*centre), _factor(feature, "factor"))
                maker = BRepBuilderAPI_Transform(picked.shape, trsf, True)
                uniform = True
            else:
                if uniform:
                    fx = fy = fz = _factor(feature, "factor")
                else:
                    fx, fy, fz = (_factor(feature, k) for k in ("fx", "fy", "fz"))
                rows = [[fx, 0.0, 0.0], [0.0, fy, 0.0], [0.0, 0.0, fz]]
                if shear is not None:  # TR371 (D1000): slide after scaling
                    along, source, tangent = shear
                    rows[along] = [rows[along][k] + tangent * rows[source][k] for k in range(3)]
                gtrsf = gp_GTrsf()
                gtrsf.SetVectorialPart(gp_Mat(*rows[0], *rows[1], *rows[2]))
                shift = gp_XYZ(
                    *(centre[i] - sum(rows[i][k] * centre[k] for k in range(3)) for i in range(3))
                )
                gtrsf.SetTranslationPart(shift)
                uniform = False
                # Transform a copy without the display mesh: a meshed part (the one
                # the view shows, which the live preview reads) made invalid geometry.
                copier = BRepBuilderAPI_Copy(picked.shape, True, False)
                maker = BRepBuilderAPI_GTransform(copier.Shape(), gtrsf, True)
                faces = [(n, copier.Modified(f).First()) for n, f in picked.faces]
            shape = maker.Shape()
            if uniform:
                faces = list(picked.faces)
            names = [(n, TopoDS.Face(maker.ModifiedShape(f))) for n, f in faces]
        except FeatureError:
            raise
        except Exception as exc:
            raise FeatureError(f"{name} failed in the geometry kernel. Try other factors.") from exc
        if not valid_solid(shape):
            raise FeatureError(f"{name} made invalid geometry. Try other factors.")
        scaled = NamedShape(shape, restrict(names, shape, feature.id))
        result = join([rest_of(ctx.body, indices, feature.id), scaled], feature.id)
        assert result is not None
        return result, issues

    def _centre(self, feature: Feature, picked: NamedShape) -> tuple[float, float, float]:
        about = feature.params.get("about", "centroid")
        if about == "origin":
            return (0.0, 0.0, 0.0)
        if about == "point":
            return tuple(  # type: ignore[return-value]
                v.value if isinstance(v := feature.params.get(k), Param) else 0.0
                for k in ("ox", "oy", "oz")
            )
        from OCP.BRepGProp import BRepGProp
        from OCP.GProp import GProp_GProps

        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(picked.shape, props)
        c = props.CentreOfMass()
        return (c.X(), c.Y(), c.Z())

    def preview_handles(self, feature: Feature, ctx: BuildContext) -> list[PreviewHandle]:
        """Scale handles at the centre of the picked bodies (PLAN Phase 3, D411).

        One box along X for a uniform factor, or one box along each axis. The box
        sits half the bodies' size times the factor from the centre, so dragging
        it out to twice as far doubles the factor. The ruler ticks every 0.1.
        """
        if ctx.body is None:
            return []
        try:
            if feature.refs.get("bodies"):
                indices, _ = body_indices(ctx, feature.refs["bodies"], feature.name)
            else:
                indices = list(range(len(solids(ctx.body.shape))))
        except FeatureError:
            return []
        picked = sub_body(ctx.body, indices, feature.id)
        half = bounding_size(picked.shape) * 0.5
        if half <= 0:
            return []
        base = centroid(picked.shape)
        uniform = feature.params.get("uniform", True) is not False
        names = ("factor",) if uniform else ("fx", "fy", "fz")
        out = []
        for name, direction in zip(names, _AXES, strict=False):
            found = feature.params.get(name)
            factor = found.value if isinstance(found, Param) else 1.0
            out.append(
                PreviewHandle(
                    name,
                    base,
                    direction,
                    factor,
                    scale=1.0 / half,
                    step=half * FACTOR_STEP,
                    style="box",
                )
            )
        return out
