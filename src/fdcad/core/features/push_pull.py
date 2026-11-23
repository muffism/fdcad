"""Push Pull: move a flat face or a sketch region by a signed distance (TR267, D1413).

Params: ``distance`` (length, signed: a positive distance adds material, a
negative one cuts; no Boss or Cut choice) and, for a region, ``symmetric``
(optional boolean: the region is pushed half each way from its sketch).

Refs: ``faces`` (flat faces: each moves along its outward normal by the distance,
its neighbours stretch, as Move Face Offset) or ``sketch`` (a closed sketch on a
face: its regions are extruded out of the face or cut into it). ``to_face``
(optional): a flat face parallel to the first picked face; the distance is then
measured to it (the panel's Next Parallel Face fills it, nearest first).

Every picked face takes the same distance.
"""

from __future__ import annotations

import copy

from OCP.BRepGProp import BRepGProp
from OCP.gp import gp_Pnt, gp_Vec
from OCP.GProp import GProp_GProps
from OCP.TopoDS import TopoDS_Face

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
from fdcad.core.features.solids import check_result
from fdcad.core.naming.names import NamedShape, faces_of
from fdcad.core.plane_normal import plane_normal
from fdcad.core.units import Kind


def _centre(face: TopoDS_Face) -> gp_Pnt:
    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, props)
    return props.CentreOfMass()


def parallel_targets(body: NamedShape, face: TopoDS_Face) -> list[tuple[str, float]]:
    """Flat faces parallel to ``face``, with the signed distance to reach each, nearest first.

    The distance is along ``face``'s outward normal: positive targets lie outside it.
    """
    normal = plane_normal(face)
    if normal is None:
        return []
    n = gp_Vec(*normal)
    origin = _centre(face)
    out: list[tuple[str, float]] = []
    for other in faces_of(body.shape):
        if other.IsSame(face):
            continue
        theirs = plane_normal(other)
        if theirs is None or not gp_Vec(*theirs).IsParallel(n, 1e-9):
            continue
        d = gp_Vec(origin, _centre(other)).Dot(n)
        name = body.primary_name(other)
        if name is not None and abs(d) > 1e-9:
            out.append((name, d))
    out.sort(key=lambda item: (abs(item[1]), item[0]))
    return out


@register
class PushPull(FeatureType):
    """Moves flat faces or a sketch region by a signed distance."""

    type_name = "push_pull"
    makes_solid = True
    params = (
        ParamSpec("distance", kind=Kind.LENGTH),
        ParamSpec("symmetric", default=False, optional=True),
    )

    def _distance(self, feature: Feature, ctx: BuildContext, first: TopoDS_Face | None) -> float:
        target = feature.refs.get("to_face")
        if isinstance(target, list):  # the panel stores one pick as a list
            target = target[0] if target else None
        if target and first is not None:
            from fdcad.core.naming.resolve import resolve_face

            body = ctx.body
            if body is not None:
                face, _issues = resolve_face(body, target, feature.name)
                for name, d in parallel_targets(body, first):
                    other = body.face(name)
                    if other is not None and face.IsSame(other):
                        return d
            raise FeatureError(
                f"{feature.name}: the target face is not parallel to the picked face. "
                "Pick a parallel face, or type a distance."
            )
        value = feature.params.get("distance")
        if not isinstance(value, Param):
            raise FeatureError(f"{feature.name}: the distance is missing. Enter a distance.")
        return value.value

    def _faces(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        from fdcad.core.features.direct import offset_faces
        from fdcad.core.features.modify import require_body, resolve_faces

        body = require_body(feature, ctx)
        found, issues = resolve_faces(feature, ctx, "faces")
        for name, face in found:
            if plane_normal(face) is None:
                raise FeatureError(
                    f"{feature.name}: face {name} is not flat, and Push Pull moves flat faces. "
                    "Use Move Face for curved ones.",
                    highlight=[name],
                )
        d = self._distance(feature, ctx, found[0][1])
        if abs(d) < 1e-9:
            raise FeatureError(f"{feature.name}: the distance is zero. Enter a distance.")
        result = offset_faces(
            body, [(f, d) for _n, f in found], feature.id, feature.name, [n for n, _f in found]
        )
        return result, issues

    def _region(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        from fdcad.core.features.base import REGISTRY

        d = self._distance(feature, ctx, None)
        if abs(d) < 1e-9:
            raise FeatureError(f"{feature.name}: the distance is zero. Enter a distance.")
        params: dict[str, object] = {
            "operation": "boss" if d > 0 else "cut",
            "end_condition": "mid_plane" if feature.params.get("symmetric") is True else "blind",
            "depth": Param(f"{abs(d):g}", abs(d)),
        }
        if d < 0:
            params["reverse"] = True  # a cut goes into the face, against the sketch normal
        extrude = Feature(
            feature.id,
            "extrude",
            feature.name,
            params=params,  # type: ignore[arg-type]
            refs={"sketch": copy.deepcopy(feature.refs["sketch"])},
        )
        result = REGISTRY["extrude"].execute(extrude, ctx)
        if result.body is None:
            raise FeatureError(f"{feature.name}: the region could not be pushed. Check the sketch.")
        return result.body, list(result.issues)

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Push or pull."""
        if feature.refs.get("sketch"):
            result, issues = self._region(feature, ctx)
        elif feature.refs.get("faces"):
            result, issues = self._faces(feature, ctx)
        else:
            raise FeatureError(
                f"{feature.name}: nothing to push or pull. Pick flat faces or a sketch on a face."
            )
        issues = issues + check_result(feature.id, feature.name, ctx.body, result, None)
        return FeatureResult(body=result, issues=issues)
