"""Draft, neutral plane method (PHASE2_SPEC P2.7, DECISIONS D218).

Params:

- ``angle``: angle, measured from the pull direction.
- ``reverse``: optional boolean, flips the pull direction (faces tilt the other way).
- ``propagation``: "none" (default), "tangent", "all", "inner" or "outer".
- ``draft_type``: optional, "neutral_plane" (default), "parting_line" or "step"
  (D521, built in ``draft_parting``). The parting types use ``neutral`` as the
  direction of pull and the edges in ``refs.parting_lines``, with optional
  ``other_side``, ``both_sides`` and ``angle2`` (the other side's angle), and
  ``allow_reduced`` (TR147 item 1, D1418: the largest angle that builds is used, with
  a warning, when the full angle fails).

Neutral plane options (TR323, D1419): ``neutral_split`` with ``angle2`` drafts the
faces below the neutral plane at their own angle; ``angle_mode`` "relative" adds the
angle to the lean a flat face already has ("absolute", the default, ends every face
at the angle from the pull).

Fixed Edge (TR323, D1804): ``draft_type`` "fixed_edge" with ``refs.fixed_edges``,
each face turns about its own picked edge (see ``draft_fixed_edge``).

Refs: ``neutral`` (a plane feature ``{"feature": "f2"}`` or a flat face
reference) and ``faces`` (faces to draft; may be empty for "all", "inner" and
"outer").

The pull direction is the neutral plane's normal. Drafted faces keep their names.
"""

from __future__ import annotations

import math

from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepOffsetAPI import BRepOffsetAPI_DraftAngle
from OCP.GeomAbs import GeomAbs_C0, GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Plane
from OCP.gp import gp_Dir, gp_Lin, gp_Pln, gp_Pnt
from OCP.TopAbs import TopAbs_REVERSED
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    Vec3,
    register,
)
from fdcad.core.features.modify import (
    changed_faces,
    edge_faces,
    edges_of,
    require_body,
    resolve_faces,
)
from fdcad.core.features.solids import check_result
from fdcad.core.naming.names import NamedShape, faces_of, restrict
from fdcad.core.plane_normal import plane_normal
from fdcad.core.units import Kind

PROPAGATIONS = ("none", "tangent", "all", "inner", "outer")
DRAFT_TYPES = ("neutral_plane", "parting_line", "step", "fixed_edge")  # fixed_edge: D1804
#: Draft types that tilt faces about parting line edges (D521).
PARTING_TYPES = ("parting_line", "step")
_PARALLEL_TOL = 1e-6


def plane_of(face: TopoDS_Face) -> tuple[Vec3, Vec3] | None:
    """A point and the outward unit normal of a flat face, or None for a curved face."""
    normal = plane_normal(face)
    if normal is None:
        return None
    p = BRepAdaptor_Surface(face).Plane().Location()
    return (p.X(), p.Y(), p.Z()), normal


def neutral_plane(feature: Feature, ctx: BuildContext) -> tuple[Vec3, Vec3, list[Issue]]:
    """A point and the unit pull direction of the neutral plane."""
    owner = feature.name
    ref = feature.refs.get("neutral")
    if not isinstance(ref, dict):
        if feature.params.get("draft_type") in PARTING_TYPES:
            raise FeatureError(
                f"{owner}: no direction of pull is picked. Pick a plane or a flat face."
            )
        raise FeatureError(f"{owner}: no neutral plane is picked. Pick a plane or a flat face.")
    issues: list[Issue] = []
    if "feature" in ref and "kind" not in ref:
        res = ctx.results.get(str(ref["feature"]))
        if res is None or res.plane is None:
            raise FeatureError(
                f"{owner}: the neutral plane {ref['feature']} was lost. Pick it again.",
                highlight=[str(ref["feature"])],
            )
        point, normal = res.plane.origin, res.plane.normal
    else:
        from fdcad.core.naming.resolve import resolve_face

        name = str(ref.get("name", ""))
        try:
            face, issues = resolve_face(ctx.body, ref, owner)
        except FeatureError as exc:
            raise FeatureError(
                f"{owner}: the neutral face {name} was lost. Pick it again.", highlight=[name]
            ) from exc
        flat = plane_of(face)
        if flat is None:
            raise FeatureError(
                f"{owner}: the neutral face is not flat. Pick a flat face or a plane."
            )
        point, normal = flat
    if feature.params.get("reverse") is True:
        normal = (-normal[0], -normal[1], -normal[2])
    return point, normal, issues


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def is_side_face(face: TopoDS_Face, pull: Vec3) -> bool:
    """True for a face along the pull direction: a flat face square to the plane, or a
    cylinder or cone whose axis follows the pull."""
    surface = BRepAdaptor_Surface(face)
    kind = surface.GetType()
    if kind == GeomAbs_Plane:
        d = surface.Plane().Axis().Direction()
        return abs(_dot((d.X(), d.Y(), d.Z()), pull)) < _PARALLEL_TOL
    if kind in (GeomAbs_Cylinder, GeomAbs_Cone):
        axis = (surface.Cylinder() if kind == GeomAbs_Cylinder else surface.Cone()).Axis()
        d = axis.Direction()
        return abs(abs(_dot((d.X(), d.Y(), d.Z()), pull)) - 1.0) < _PARALLEL_TOL
    return False


def _outward_normal(face: TopoDS_Face) -> tuple[gp_Pnt, Vec3] | None:
    from OCP.BRepLProp import BRepLProp_SLProps

    surface = BRepAdaptor_Surface(face)
    u = (surface.FirstUParameter() + surface.LastUParameter()) / 2
    v = (surface.FirstVParameter() + surface.LastVParameter()) / 2
    props = BRepLProp_SLProps(surface, u, v, 1, 1e-7)
    if not props.IsNormalDefined():
        return None
    n = props.Normal()
    sign = -1.0 if face.Orientation() == TopAbs_REVERSED else 1.0
    return props.Value(), (sign * n.X(), sign * n.Y(), sign * n.Z())


def is_inner(body: TopoDS_Shape, face: TopoDS_Face) -> bool:
    """True when a line leaving the face outward meets the part again (a hole or pocket)."""
    from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector

    found = _outward_normal(face)
    if found is None:
        return False
    point, n = found
    hits = IntCurvesFace_ShapeIntersector()
    hits.Load(body, 1e-7)
    hits.Perform(gp_Lin(point, gp_Dir(*n)), 1e-4, 1e9)
    return bool(hits.IsDone() and hits.NbPnt() > 0)


def _tangent_faces(body: TopoDS_Shape, faces: list[TopoDS_Face]) -> list[TopoDS_Face]:
    """``faces`` plus the faces joined to them smoothly (Along tangent)."""
    out = list(faces)
    queue = list(faces)
    while queue:
        face = queue.pop()
        for edge in edges_of(face):
            for other in edge_faces(body, edge):
                if any(other.IsSame(f) for f in out):
                    continue
                if BRep_Tool.Continuity_s(edge, face, other) != GeomAbs_C0:
                    out.append(other)
                    queue.append(other)
    return out


def faces_to_draft(
    feature: Feature, ctx: BuildContext, pull: Vec3
) -> tuple[list[tuple[str, TopoDS_Face]], list[Issue]]:
    """The picked faces with propagation applied."""
    body = require_body(feature, ctx)
    mode = str(feature.params.get("propagation", "none"))
    picked, issues = resolve_faces(feature, ctx, "faces", required=mode in ("none", "tangent"))
    faces = [f for _n, f in picked]
    if mode == "tangent":
        faces = _tangent_faces(body.shape, faces)
    elif mode in ("all", "inner", "outer"):
        sides = [f for f in faces_of(body.shape) if is_side_face(f, pull)]
        if mode == "inner":
            sides = [f for f in sides if is_inner(body.shape, f)]
        elif mode == "outer":
            sides = [f for f in sides if not is_inner(body.shape, f)]
        faces = faces + [f for f in sides if not any(f.IsSame(g) for g in faces)]
    out = [(body.primary_name(f) or "a face", f) for f in faces]
    if not out:
        raise FeatureError(f"{feature.name}: no faces to draft. Pick faces or another propagation.")
    return out, issues


def _lean(face: TopoDS_Face, pull: Vec3) -> float:
    """How far a flat face already leans from the pull, signed as the draft angle (0 for
    curved faces): Relative angles add to it (TR323, D1419)."""
    normal = plane_normal(face)
    if normal is None:
        return 0.0
    s = max(-1.0, min(1.0, sum(normal[i] * pull[i] for i in range(3))))
    return math.asin(s)


@register
class Draft(FeatureType):
    """Tilts faces by an angle from the pull direction about a neutral plane."""

    type_name = "draft"
    makes_solid = True
    params = (
        ParamSpec("angle", kind=Kind.ANGLE),
        ParamSpec("reverse", default=False, optional=True),
        ParamSpec("propagation", choices=PROPAGATIONS, optional=True),
        ParamSpec("draft_type", choices=DRAFT_TYPES, optional=True),
        ParamSpec("other_side", default=False, optional=True),
        ParamSpec("both_sides", default=False, optional=True),
        ParamSpec("angle2", kind=Kind.ANGLE, optional=True),
        ParamSpec("allow_reduced", default=False, optional=True),  # TR147 (D1418)
        ParamSpec("neutral_split", default=False, optional=True),  # TR323 (D1419)
        ParamSpec("angle_mode", choices=("absolute", "relative"), optional=True),
        ParamSpec("reapply_fillets", default=False, optional=True),  # TR259 (D1806)
    )

    def _draft(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        """The drafted part. With Reapply Fillets (TR259, D1806) on a Neutral Plane or
        Fixed Edge draft, the rounds next to the picked faces are removed first and made
        again after (as Move Face does, D1420)."""
        from fdcad.core.features import reapply_fillets as reapply

        kind = feature.params.get("draft_type", "neutral_plane")
        face_kind = kind in ("neutral_plane", "fixed_edge")
        plain = face_kind and feature.params.get("neutral_split") is not True
        by_faces = str(feature.params.get("propagation", "none")) in ("none", "tangent")
        if reapply.wanted(feature) and ctx.body is not None and plain and by_faces:
            picked, _issues = resolve_faces(feature, ctx, "faces")
            return reapply.around(
                feature, ctx, [f for _n, f in picked], lambda c: self._draft_core(feature, c)
            )
        return self._draft_core(feature, ctx)

    def _draft_core(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        body = require_body(feature, ctx)
        owner = feature.name
        value = feature.params.get("angle")
        if not isinstance(value, Param):
            raise FeatureError(f"{owner}: the draft angle is missing. Enter an angle.")
        angle = value.value
        if not 0 < angle < math.radians(89):
            raise FeatureError(
                f"{owner}: the draft angle must be between 0 and 89 degrees. "
                "Enter an angle in that range."
            )
        point, pull, issues = neutral_plane(feature, ctx)
        if feature.params.get("draft_type") == "fixed_edge":  # TR323 (D1804)
            from fdcad.core.features.draft_fixed_edge import fixed_edge_draft

            shape, more = fixed_edge_draft(feature, ctx, pull, angle)
            return shape, issues + more
        if feature.params.get("draft_type") in PARTING_TYPES:
            from fdcad.core.features.draft_parting import parting_draft

            other = feature.params.get("angle2")
            angle2 = other.value if isinstance(other, Param) else angle
            if not 0 < angle2 < math.radians(89):
                raise FeatureError(
                    f"{owner}: the other angle must be between 0 and 89 degrees. "
                    "Enter an angle in that range."
                )
            shape, more = parting_draft(feature, ctx, pull, angle, angle2)
            return shape, issues + more
        faces, more = faces_to_draft(feature, ctx, pull)
        issues = issues + more
        relative_mode = feature.params.get("angle_mode") == "relative"  # TR323 (D1419)

        def angle_of(face: TopoDS_Face) -> float:
            return angle + _lean(face, pull) if relative_mode else angle

        if feature.params.get("neutral_split") is True:  # TR323 (D1419): two angles
            from fdcad.core.features.draft_parting import split_draft

            other = feature.params.get("angle2")
            angle2 = other.value if isinstance(other, Param) else angle
            if not 0 < angle2 < math.radians(89):
                raise FeatureError(
                    f"{owner}: the other angle must be between 0 and 89 degrees. "
                    "Enter an angle in that range."
                )
            level = sum(point[i] * pull[i] for i in range(3))
            shape = split_draft(feature, body, [n for n, _f in faces], pull, level, angle, angle2)
            return shape, issues
        neutral = gp_Pln(gp_Pnt(*point), gp_Dir(*pull))
        maker = BRepOffsetAPI_DraftAngle(body.shape)
        relative = feature.params.get("angle_mode") == "relative"
        for name, face in faces:
            leaning = relative and abs(math.sin(_lean(face, pull))) < math.cos(math.radians(1))
            if not is_side_face(face, pull) and plane_of(face) is not None and not leaning:
                raise FeatureError(
                    f"{owner}: face {name} is square to the pull direction and cannot be "
                    "drafted. Remove it from the list.",
                    highlight=[name],
                )
            maker.Add(face, gp_Dir(*pull), angle_of(face), neutral, True)
            if not maker.AddDone():
                raise FeatureError(
                    f"{owner}: face {name} cannot be drafted from this neutral plane. "
                    "Remove it or pick another neutral plane.",
                    highlight=[name],
                )
        try:
            maker.Build()
        except Exception as exc:
            raise FeatureError(
                f"{owner} failed: the faces could not be tilted together. "
                "Use a smaller angle or fewer faces."
            ) from exc
        if not maker.IsDone():
            raise FeatureError(
                f"{owner} failed: the faces could not be tilted together. "
                "Use a smaller angle or fewer faces."
            )
        shape = maker.Shape()
        names = [(n, TopoDS.Face(maker.ModifiedShape(f))) for n, f in body.faces]
        return NamedShape(shape, restrict(names, shape, f"{feature.id}/face")), issues

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Tilt the faces."""
        result, issues = self._draft(feature, ctx)
        issues = issues + check_result(feature.id, feature.name, ctx.body, result, None)
        return FeatureResult(body=result, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The changed faces (or the whole result when the preview asks for it)."""
        body = require_body(feature, ctx)
        result, _issues = self._draft(feature, ctx)
        if feature.params.get("preview_whole") is True:
            return result
        return changed_faces(body.shape, result, feature.id)
