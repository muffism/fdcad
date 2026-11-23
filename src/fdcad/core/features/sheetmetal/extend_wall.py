"""Extend Wall (TR370 item 1, DECISIONS D1109): lengthen a wall to a distance, plane or face.

Type ``extend_wall``. Pick an edge face of a wall (a face through the sheet thickness,
square to the wall). The wall grows out of that face, keeping its outline, by
``distance`` (``end_condition`` "blind", the default) or up to a plane or flat face
(``end_condition`` "up_to", ``refs.limit``), measured along the face's normal at its
centre. The new material belongs to the wall, so it folds and flattens with it.

Params: ``end_condition``, ``distance``. Refs: ``face``, ``limit``, ``sheet_metal``.

Face roles: ``<fid>/extend/<role>`` and the wall's own.
"""

from __future__ import annotations

from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.gp import gp_Vec
from OCP.TopoDS import TopoDS

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.features.lookup import resolve_face
from fdcad.core.features.sheetmetal.common import require_sheet, value
from fdcad.core.features.sheetmetal.locate import face_normal, local_vector
from fdcad.core.features.sheetmetal.model import SheetModel, SheetResult, apply, inside
from fdcad.core.features.solids import transform
from fdcad.core.naming.names import NamedShape, centroid, faces_of
from fdcad.core.units import Kind

TYPE = "extend_wall"
_TOL = 1e-5


def _wall_edge_face(
    model: SheetModel, face: object, owner: str
) -> tuple[str, object, tuple[float, float, float]]:
    """The wall that ``face`` bounds through its thickness: wall, face in the wall frame and
    the outward normal there."""
    c = centroid(face)
    n = face_normal(face)
    t = model.thickness
    for wid, place in model.placements(False).items():
        if wid not in model.walls:
            continue
        inv = place.Inverted()
        ln = local_vector(inv, n)
        lc = apply(inv, c)
        if abs(ln[2]) > 1e-6 or not -_TOL <= lc[2] <= t + _TOL:
            continue
        probe = (lc[0] - ln[0] * 1e-3, lc[1] - ln[1] * 1e-3, t / 2)
        if inside(model.piece(wid).shape, probe):
            named = NamedShape(face, [("x", face)])
            local = transform(named, inv)
            return wid, local.shape, ln
    raise FeatureError(
        f"{owner}: the face is not an edge face of a wall. Pick a narrow face through the "
        "sheet at the edge of a wall."
    )


@register
class ExtendWall(FeatureType):
    """Lengthens a wall out of one of its edge faces."""

    type_name = TYPE
    makes_solid = True
    params = (
        ParamSpec("end_condition", choices=("blind", "up_to"), default="blind", optional=True),
        ParamSpec("distance", kind=Kind.LENGTH, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Grow the wall and rebuild the sheet."""
        model, issues = self.model(feature, ctx)
        return SheetResult(body=model.build(feature.id, feature.name), issues=issues, sheet=model)

    def model(self, feature: Feature, ctx: BuildContext) -> tuple[SheetModel, list[Issue]]:
        """The sheet with the wall lengthened."""
        name, fid = feature.name, feature.id
        model = require_sheet(feature, ctx)
        ref = feature.refs.get("face")
        if not isinstance(ref, dict):
            raise FeatureError(f"{name}: pick an edge face of a wall.")
        face, issues = resolve_face(ctx.body, ref, name)
        wid, local_face, n = _wall_edge_face(model, face, name)
        if feature.params.get("end_condition", "blind") == "up_to":
            distance = self._up_to(feature, ctx, model, wid, face, issues)
        else:
            distance = value(feature, "distance", 0.0)
        if distance <= _TOL:
            raise FeatureError(
                f"{name}: the wall must grow by more than zero. Enter a longer distance, or "
                "pick a plane beyond the face."
            )
        shape = BRepPrimAPI_MakePrism(
            TopoDS.Face(local_face), gp_Vec(n[0] * distance, n[1] * distance, 0.0)
        ).Shape()
        extra = NamedShape(shape, [(f"{fid}/extend/side", f) for f in faces_of(shape)])
        model.add_material(wid, [extra])
        return model, issues

    @staticmethod
    def _up_to(
        feature: Feature,
        ctx: BuildContext,
        model: SheetModel,
        wid: str,
        face: object,
        issues: list[Issue],
    ) -> float:
        """Distance along the face normal from its centre to the limit plane or face."""
        from fdcad.core.features.sketch import face_plane

        name = feature.name
        ref = feature.refs.get("limit")
        if not isinstance(ref, dict):
            raise FeatureError(
                f"{name}: Up To needs a plane or flat face. Pick one, or choose Blind."
            )
        plane = None
        fid = ref.get("feature")
        if isinstance(fid, str) and len(ref) == 1:
            datum = getattr(ctx.result(fid), "datum", None)
            if datum is not None and datum.kind == "plane":
                plane = (datum.origin, datum.direction)
        if plane is None:
            limit, found = resolve_face(ctx.body, ref, name)
            issues.extend(found)
            fp = face_plane(limit)
            if fp is None:
                raise FeatureError(
                    f"{name}: the limit face is not flat. Pick a flat face or plane."
                )
            plane = (fp.origin, fp.normal)
        c = centroid(face)
        n = face_normal(face)
        origin, normal = plane
        denom = sum(n[i] * normal[i] for i in range(3))
        if abs(denom) < 1e-9:
            raise FeatureError(
                f"{name}: the limit is parallel to the wall's growth. Pick a plane across it."
            )
        return sum((origin[i] - c[i]) * normal[i] for i in range(3)) / denom
