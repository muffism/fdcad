"""Replace Face: swap faces for a plane, extending or trimming the body (TR130, D1412).

Refs: ``faces`` (the faces to replace) and ``target`` (a reference plane or a
flat face; one reference, or a list holding one). The body under the picked
faces is extended up to the target plane where the faces lie short of it, and
trimmed back to it where they stick out past it. Common use: flatten a bumpy
imported face onto a plane.

Only flat targets are built (the owner decision in the spec: a curved target is
surface work). For each picked face, with ``n`` the plane normal pointing the way
the face looks:

- added: the face swept along ``n``, the part of that sweep short of the plane;
- removed: the face swept against ``n``, the part of that sweep past the plane.

Both are cut to the picked faces' own column, so the rest of the body is left
alone. Kept faces keep their names; the new flat face is ``replaced``.
"""

from __future__ import annotations

from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt, gp_Vec
from OCP.TopoDS import TopoDS_Face, TopoDS_Shape

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    register,
)
from fdcad.core.features.solids import check_result, compound, reach_from, solids
from fdcad.core.naming.names import NamedFace, NamedShape, faces_of
from fdcad.core.occ import BRepAlgoAPI_Common


def _target(feature: Feature, ctx: BuildContext) -> tuple[gp_Pln, list[Issue]]:
    from fdcad.core.features.datum import resolve_pick

    ref = feature.refs.get("target")
    if isinstance(ref, list):  # the panel stores one pick as a list
        ref = ref[0] if ref else None
    if not isinstance(ref, dict):
        raise FeatureError(
            f"{feature.name}: no target is picked. Pick a plane or a flat face as the target."
        )
    geo, issues = resolve_pick(ref, ctx, feature.name)
    if geo.kind != "plane" or geo.direction is None:
        raise FeatureError(
            f"{feature.name}: the target must be a plane or a flat face. A curved target is not "
            "supported. Pick a plane or a flat face."
        )
    return gp_Pln(gp_Pnt(*geo.point), gp_Dir(*geo.direction)), issues


def _slab(plane: gp_Pln, size: float, beyond: bool) -> TopoDS_Shape:
    """A big slab on one side of ``plane``: past it along its normal, or short of it."""
    face = BRepBuilderAPI_MakeFace(plane, -size, size, -size, size).Face()
    n = gp_Vec(plane.Axis().Direction()).Scaled(size if beyond else -size)
    return BRepPrimAPI_MakePrism(face, n).Shape()


def _sweep(face: TopoDS_Face, vector: gp_Vec) -> TopoDS_Shape:
    return BRepPrimAPI_MakePrism(face, vector).Shape()


def _common(a: TopoDS_Shape, b: TopoDS_Shape) -> TopoDS_Shape:
    op = BRepAlgoAPI_Common(a, b)
    op.Build()
    if not op.IsDone():
        raise FeatureError("Replace Face failed: the kernel could not cut a sweep to the plane.")
    return op.Shape()


def _looks(face: TopoDS_Face) -> gp_Vec:
    """The way a face looks: its outward normal at the middle of its parameter range."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepTools import BRepTools
    from OCP.TopAbs import TopAbs_REVERSED

    surface = BRep_Tool.Surface_s(face)
    u0, u1, v0, v1 = BRepTools.UVBounds_s(face)
    point, du, dv = gp_Pnt(), gp_Vec(), gp_Vec()
    surface.D1((u0 + u1) / 2, (v0 + v1) / 2, point, du, dv)
    n = du.Crossed(dv)
    if face.Orientation() == TopAbs_REVERSED:
        n.Reverse()
    return n


@register
class ReplaceFace(FeatureType):
    """Replaces picked faces with a target plane, extending or trimming the body."""

    type_name = "replace_face"
    makes_solid = True
    params = ()

    def _build(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        from fdcad.core.features.modify import require_body, resolve_faces
        from fdcad.core.features.solids import combine

        body = require_body(feature, ctx)
        picked, issues = resolve_faces(feature, ctx, "faces")
        plane, more = _target(feature, ctx)
        issues += more
        at = plane.Location()
        # The slab is centred on the plane's origin, which may be far from the part (D1087).
        size = reach_from((at.X(), at.Y(), at.Z()), body.shape)
        added: list[TopoDS_Shape] = []
        removed: list[TopoDS_Shape] = []
        for _name, face in picked:
            n = gp_Vec(plane.Axis().Direction())
            if _looks(face).Dot(n) < 0:
                n.Reverse()
            facing = gp_Pln(plane.Location(), gp_Dir(n))
            up = _common(_sweep(face, n.Scaled(size)), _slab(facing, size, beyond=False))
            down = _common(_sweep(face, n.Scaled(-size)), _slab(facing, size, beyond=True))
            added += solids(up)
            removed += solids(down)
        if not added and not removed:
            raise FeatureError(
                f"{feature.name}: the picked faces already lie on the target. "
                "Pick other faces or another target."
            )
        role = f"{feature.id}/replaced"
        current = body
        if added:
            tool = compound(added)
            current = combine(
                feature.id, feature.name, current, _on_plane(tool, plane, role), "boss"
            )
        if removed:
            tool = compound(removed)
            current = combine(
                feature.id, feature.name, current, _on_plane(tool, plane, role), "cut"
            )
        return current, issues

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Replace the faces."""
        result, issues = self._build(feature, ctx)
        issues = issues + check_result(feature.id, feature.name, ctx.body, result, None)
        return FeatureResult(body=result, issues=issues)


def _on_plane(tool: TopoDS_Shape, plane: gp_Pln, role: str) -> NamedShape:
    """The tool with its faces on ``plane`` named ``role``."""
    from fdcad.core.plane_normal import plane_normal

    named: list[NamedFace] = []
    for face in faces_of(tool):
        normal = plane_normal(face)
        if normal is None:
            continue
        from OCP.BRepGProp import BRepGProp
        from OCP.GProp import GProp_GProps

        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, props)
        if plane.Distance(props.CentreOfMass()) < 1e-6 and gp_Vec(*normal).IsParallel(
            gp_Vec(plane.Axis().Direction()), 1e-6
        ):
            named.append((role, face))
    return NamedShape(tool, named)
