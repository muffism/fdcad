"""Lasting face relations on bodies with no history (TR266, DECISIONS D2418).

Type ``face_relation``: a relation between faces of a body, often an imported one,
kept in the feature tree. It does not change the part; it checks that the relation
holds now (a warning when not) and later Move Face features keep it:

- ``coplanar``: two flat faces on one plane. A move of one moves the other with it.
- ``offset``: two parallel flat faces keep their distance: an offset of one moves the
  other the same way.
- ``concentric``: two round faces on one axis. A translate or rotate of one takes the
  other along.
- ``parallel`` and ``perpendicular``: two flat faces keep their angle. A rotate of one
  turns the other with it.
- ``equal_radius``: two round faces keep one radius. An offset or resize of one does
  the same to the other.
- ``fixed``: one or more faces that a Move Face may not move.

Refs: ``faces`` (two faces; one or more for ``fixed``). Param: ``relation``. No Qt.
"""

from __future__ import annotations

import math
from typing import Any

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Sphere
from OCP.TopoDS import TopoDS_Face

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureState,
    FeatureType,
    Issue,
    ParamSpec,
    register,
)

RELATIONS = ("coplanar", "offset", "concentric", "parallel", "perpendicular", "equal_radius",
             "fixed")  # fmt: skip
TYPE = "face_relation"
#: Which Move Face modes take a relation's partner face along.
TAKES_PARTNER = {
    "coplanar": ("offset", "translate", "rotate"),
    "offset": ("offset", "translate", "rotate"),
    "concentric": ("translate", "rotate"),
    "parallel": ("rotate",),
    "perpendicular": ("rotate",),
    "equal_radius": ("offset", "resize"),
}
_TOL = 1e-6


def _normal(face: TopoDS_Face) -> tuple[float, float, float] | None:
    from fdcad.core.features.face_picks import outward_normal

    return outward_normal(face)


def _round(face: TopoDS_Face) -> tuple[Any, float] | None:
    """The axis (gp_Ax1, or a sphere's centre as an axis) and radius of a round face."""
    surface = BRepAdaptor_Surface(face)
    if surface.GetType() == GeomAbs_Cylinder:
        cyl = surface.Cylinder()
        return cyl.Axis(), cyl.Radius()
    if surface.GetType() == GeomAbs_Sphere:
        sphere = surface.Sphere()
        return sphere.Position().Axis(), sphere.Radius()
    return None


def holds(kind: str, a: TopoDS_Face, b: TopoDS_Face | None) -> bool | None:
    """True when relation ``kind`` holds between ``a`` and ``b``, None when the faces
    are of the wrong kind for it."""
    from fdcad.core.features.geometry_refs import dot
    from fdcad.core.features.sketch import face_plane

    if kind == "fixed" or b is None:
        return True
    if kind in ("coplanar", "offset", "parallel", "perpendicular"):
        na, nb = _normal(a), _normal(b)
        if na is None or nb is None:
            return None
        d = dot(na, nb)
        if kind == "perpendicular":
            return abs(d) < _TOL
        if kind in ("parallel", "offset"):
            return abs(abs(d) - 1) < _TOL
        pa, pb = face_plane(a), face_plane(b)
        assert pa is not None and pb is not None
        gap = sum((p - q) * n for p, q, n in zip(pb.origin, pa.origin, na, strict=True))
        return d > 1 - _TOL and abs(gap) < 1e-4
    ra, rb = _round(a), _round(b)
    if ra is None or rb is None:
        return None
    if kind == "equal_radius":
        return abs(ra[1] - rb[1]) < 1e-4
    axis_a, axis_b = ra[0], rb[0]  # concentric: one line
    if not axis_a.IsParallel(axis_b, 1e-6):
        return False
    from OCP.gp import gp_Lin

    return bool(gp_Lin(axis_a).Distance(axis_b.Location()) < 1e-4)


@register
class FaceRelation(FeatureType):
    """A kept relation between faces; checks it and leaves the part as it is."""

    type_name = TYPE
    makes_solid = False
    params = (ParamSpec("relation", choices=RELATIONS, default="coplanar"),)

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Check the relation holds now."""
        from fdcad.core.features.direct import resolve_faces, short_name

        name = feature.name
        kind = str(feature.params.get("relation", "coplanar"))
        faces, labels, issues = resolve_faces(ctx, feature.refs.get("faces"), name)
        if kind != "fixed" and len(faces) != 2:
            raise FeatureError(
                f"{name}: a {kind.replace('_', ' ')} relation needs two faces. Pick two faces."
            )
        ok = holds(kind, faces[0], faces[1] if len(faces) > 1 else None)
        if ok is None:
            raise FeatureError(
                f"{name}: {kind.replace('_', ' ')} needs "
                f"{'round' if kind in ('concentric', 'equal_radius') else 'flat'} faces. "
                "Pick other faces."
            )
        if not ok:
            pair = " and ".join(short_name(n) for n in labels)
            issues.append(
                Issue(
                    FeatureState.WARNING,
                    f"{name}: {pair} are not {kind.replace('_', ' ')} now. Move one of them, "
                    "or delete the relation.",
                    code="relation_off",
                    highlight=list(labels),
                )
            )
        return FeatureResult(body=ctx.body, issues=issues)


def kept(ctx: BuildContext, before: str) -> list[Feature]:
    """The relations above feature ``before`` in the tree that are not suppressed."""
    order = [f.id for f in ctx.document.features]
    mine = order.index(before) if before in order else len(order)
    return [f for f in ctx.document.features[:mine] if f.type == TYPE and not f.suppressed]


def partners(
    feature: Feature, ctx: BuildContext, faces: list[TopoDS_Face]
) -> list[tuple[TopoDS_Face, str, float]]:
    """The faces kept relations add to a Move Face (with its label and Offset factor),
    after checking no picked face is fixed. Raises FeatureError for a fixed face."""
    from fdcad.core.features.direct import short_name
    from fdcad.core.features.geometry_refs import dot

    if ctx.body is None:
        return []
    mode = str(feature.params.get("mode", "offset"))
    picked = {ctx.body.primary_name(f) for f in faces}
    out: list[tuple[TopoDS_Face, str, float]] = []
    for rel in kept(ctx, feature.id):
        names = [r.get("name") for r in rel.refs.get("faces") or [] if isinstance(r, dict)]
        kind = str(rel.params.get("relation", "coplanar"))
        if kind == "fixed":
            hit = [n for n in names if n in picked]
            if hit:
                raise FeatureError(
                    f"{feature.name}: {short_name(str(hit[0]))} is fixed by {rel.name}. Pick "
                    "another face, or suppress the relation.",
                    highlight=[str(h) for h in hit],
                )
            continue
        if len(names) != 2 or mode not in TAKES_PARTNER.get(kind, ()):
            continue
        for here, there in (names, names[::-1]):
            if here not in picked or there in picked or not isinstance(there, str):
                continue
            a, b = ctx.body.face(str(here)), ctx.body.face(there)
            if a is None or b is None or any(b.IsSame(f) for f, _l, _k in out):
                continue
            factor = 1.0
            na, nb = _normal(a), _normal(b)
            if na is not None and nb is not None and kind in ("coplanar", "offset"):
                factor = dot(na, nb)  # opposite faces of a slab move the same way
            out.append((b, short_name(there), factor if not math.isnan(factor) else 1.0))
    return out
