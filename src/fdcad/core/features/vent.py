"""Vent (PHASE4_SPEC P4.4 item 5, DECISIONS D319).

An opening through a flat wall made from a sketch, with ribs and spars across
it and an optional fill in area left solid. The open area is reported live.

Params (FDEF_SPEC 5.3.28), all lengths:

- ``rib_width``, ``rib_depth``, ``rib_offset`` (from the face down to the rib top).
- ``spar_width``, ``spar_depth``, ``spar_offset``.
- ``fill_depth``, ``fill_offset``.

Refs: ``sketch`` (``{"feature": <sketch id>}``), ``face`` (the flat face, one
reference), and the sketch curves by role, each a list of
``{"feature": <sketch id>, "sketch_entity": <id>}``: ``boundary`` (closed),
``ribs`` (lines), ``spars`` (lines, need at least one rib) and ``fill`` (closed,
crossed by at least one rib).

Face roles: ``opening/<k>``, ``rib/<k>/<j>``, ``spar/<k>/<j>``, ``fill/<j>``.
"""

from __future__ import annotations

from typing import Any

from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.gp import gp_Vec
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape

from fdcad.core.document.model import Feature, Param
from fdcad.core.features import fastening as fx
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    SketchOutput,
    register,
)
from fdcad.core.features.hole import line_hits
from fdcad.core.features.modify import require_body
from fdcad.core.features.sketch import face_plane
from fdcad.core.features.solids import check_result, combine, compound, face_area, polygon_face
from fdcad.core.naming.names import NamedShape, centroid, restrict
from fdcad.core.occ import BRepAlgoAPI_Common, BRepAlgoAPI_Fuse
from fdcad.core.sketch.model import Line
from fdcad.core.units import Kind

_LENGTHS = (
    "rib_width",
    "rib_depth",
    "rib_offset",
    "spar_width",
    "spar_depth",
    "spar_offset",
    "fill_depth",
    "fill_offset",
    "rib_fillet",  # TR146 item 3 (D2406)
    "spar_fillet",
    "fill_fillet",
)
#: Draft angle per element group (TR146 item 3, D2406).
_ANGLES = ("rib_draft", "spar_draft", "fill_draft")


def _value(feature: Feature, name: str, default: float = 0.0) -> float:
    v = feature.params.get(name)
    return v.value if isinstance(v, Param) else default


def role_ids(feature: Feature, role: str) -> list[str]:
    """The sketch entity ids picked for ``role``."""
    refs = feature.refs.get(role)
    if not isinstance(refs, list):
        return []
    return [str(r["sketch_entity"]) for r in refs if isinstance(r, dict) and "sketch_entity" in r]


def _sketch(feature: Feature, ctx: BuildContext) -> SketchOutput:
    ref = feature.refs.get("sketch")
    if not isinstance(ref, dict) or "feature" not in ref:
        raise FeatureError(f"{feature.name} has no sketch. Choose the vent sketch.")
    out = ctx.result(str(ref["feature"])).sketch
    if out is None:
        raise FeatureError(f"{feature.name}: the chosen feature is not a sketch. Pick a sketch.")
    return out


def closed_faces(
    feature: Feature, sketch: SketchOutput, ids: list[str], what: str
) -> list[TopoDS_Face]:
    """Flat faces bounded by the picked curves, made from a copy of the sketch that
    holds only those curves (so nesting and holes work as in any profile)."""
    from fdcad.core.sketch.model import Arc, Circle
    from fdcad.core.sketch.model import Sketch as SketchModel
    from fdcad.core.sketch.profiles import ProfileError, build_profile

    part = SketchModel()
    for eid in ids:
        entity = sketch.model.entities.get(eid)
        if entity is None:
            raise FeatureError(f"{feature.name}: the {what} curve {eid} is gone. Pick it again.")
        points: list[str] = []
        if isinstance(entity, Line):
            points = [entity.p1, entity.p2]
        elif isinstance(entity, Arc):
            points = [entity.center, entity.start, entity.end]
        elif isinstance(entity, Circle):
            points = [entity.center]
        part.entities[eid] = entity
        for pid in points:
            part.entities[pid] = sketch.model.entities[pid]
    try:
        profile = build_profile(part, sketch.plane)
    except ProfileError as exc:
        raise FeatureError(
            f"{feature.name}: the {what} is not closed. Pick curves that form a closed loop."
        ) from exc
    return list(profile.faces)


def bar_faces(
    sketch: SketchOutput, ids: list[str], width: float, feature: Feature, what: str
) -> list[TopoDS_Face]:
    """A flat strip of ``width`` along each picked line."""
    out = []
    plane = sketch.plane
    for eid in ids:
        line = sketch.model.entities.get(eid)
        if not isinstance(line, Line):
            raise FeatureError(f"{feature.name}: {what} {eid} is not a line. Pick sketch lines.")
        a, b = sketch.model.entities[line.p1], sketch.model.entities[line.p2]
        ax, ay = getattr(a, "x", 0.0), getattr(a, "y", 0.0)
        bx, by = getattr(b, "x", 0.0), getattr(b, "y", 0.0)
        dx, dy = bx - ax, by - ay
        length = (dx * dx + dy * dy) ** 0.5
        if length < 1e-9:
            continue
        nx, ny = -dy / length * width / 2, dx / length * width / 2
        corners = [(ax + nx, ay + ny), (bx + nx, by + ny), (bx - nx, by - ny), (ax - nx, ay - ny)]
        pts = []
        for u, v in corners:
            p = plane.to_3d(u, v)
            pts.append((p.X(), p.Y(), p.Z()))
        out.append(polygon_face(pts))
    return out


def _clip(faces: list[TopoDS_Face], region: list[TopoDS_Face]) -> TopoDS_Shape:
    """The parts of ``faces`` inside ``region``."""
    op = BRepAlgoAPI_Common(compound(faces), compound(region))
    op.Build()
    return op.Shape()


def _union_area(shapes: list[TopoDS_Shape]) -> float:
    """Area covered by flat shapes that may overlap (each shape a separate operand)."""
    from fdcad.core.occ import ShapeList

    shapes = [s for s in shapes if face_area([s]) > 0]
    if len(shapes) <= 1:
        return face_area(shapes) if shapes else 0.0
    op = BRepAlgoAPI_Fuse()
    args, tools = ShapeList(), ShapeList()
    args.Append(shapes[0])
    for s in shapes[1:]:
        tools.Append(s)
    op.SetArguments(args)
    op.SetTools(tools)
    op.Build()
    return face_area([op.Shape()])


def _slab(prefix: str, shape: TopoDS_Shape, up: fx.Vec3, top: float, depth: float) -> NamedShape:
    """``shape`` (flat faces) pushed from ``top`` below the face down by ``depth``."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Trsf

    move = gp_Trsf()
    move.SetTranslation(gp_Vec(*fx.add((0, 0, 0), up, -top)))
    moved = BRepBuilderAPI_Transform(shape, move, True).Shape()
    maker = BRepPrimAPI_MakePrism(moved, gp_Vec(*fx.add((0, 0, 0), up, -depth)))
    maker.Build()
    solid = maker.Shape()
    return NamedShape(solid, restrict([], solid, prefix))


@register
class Vent(FeatureType):
    """An opening with ribs, spars and a fill in area."""

    type_name = "vent"
    makes_solid = True
    params = (ParamSpec("rib_width", kind=Kind.LENGTH, optional=True),)

    def kind_of(self, name: str) -> Kind | None:
        """Lengths, and the draft angles of the element groups."""
        if name in _LENGTHS:
            return Kind.LENGTH
        if name in _ANGLES:
            return Kind.ANGLE
        return super().kind_of(name)

    def _layout(self, feature: Feature, ctx: BuildContext) -> dict[str, Any]:
        """Opening, ribs, spars and fill as flat shapes, plus the wall frame."""
        require_body(feature, ctx)
        sketch = _sketch(feature, ctx)
        face, issues = fx.face_of(feature, ctx)
        plane = face_plane(face)
        if plane is None:
            raise FeatureError(
                f"{feature.name}: vents are made on flat faces. Pick a flat face (D319)."
            )
        if abs(fx.dot(plane.normal, fx.unit(sketch.plane.normal))) < 1 - 1e-6:
            raise FeatureError(
                f"{feature.name}: the sketch must be parallel to the vent face. "
                "Pick a sketch on a parallel plane."
            )
        boundary = role_ids(feature, "boundary")
        if not boundary:
            raise FeatureError(f"{feature.name}: pick the closed boundary curves of the vent.")
        opening = closed_faces(feature, sketch, boundary, "boundary")
        ribs = role_ids(feature, "ribs")
        spars = role_ids(feature, "spars")
        if spars and not ribs:
            raise FeatureError(f"{feature.name}: spars need at least one rib. Pick a rib first.")
        rib_w, spar_w = _value(feature, "rib_width"), _value(feature, "spar_width")
        if (ribs and rib_w <= 0) or (spars and spar_w <= 0):
            raise FeatureError(
                f"{feature.name}: rib and spar widths must be greater than zero. "
                "Enter larger widths."
            )
        rib = _clip(bar_faces(sketch, ribs, rib_w, feature, "rib"), opening) if ribs else None
        spar = _clip(bar_faces(sketch, spars, spar_w, feature, "spar"), opening) if spars else None
        fill = None
        fill_ids = role_ids(feature, "fill")
        if fill_ids:
            fill_faces = closed_faces(feature, sketch, fill_ids, "fill in boundary")
            if (
                rib is None
                or face_area([_clip(fill_faces, [TopoDS.Face(f) for f in _faces(rib)])]) <= 0
            ):
                raise FeatureError(
                    f"{feature.name}: the fill in boundary must be crossed by at least one rib. "
                    "Draw a rib across it."
                )
            fill = _clip(fill_faces, opening)
        # Lift everything onto the face's plane (the sketch may sit above or below it).
        lift = fx.dot(fx.sub(plane.origin, sketch.plane.origin), plane.normal)
        return {
            "face": face,
            "up": plane.normal,
            "lift": lift,
            "opening": opening,
            "rib": rib,
            "spar": spar,
            "fill": fill,
            "issues": issues,
        }

    def areas(self, feature: Feature, ctx: BuildContext) -> tuple[float, float]:
        """Total area of the opening and the open area left by ribs, spars and fill."""
        lay = self._layout(feature, ctx)
        total = face_area(lay["opening"])
        blocked = _union_area([s for s in (lay["rib"], lay["spar"], lay["fill"]) if s is not None])
        return total, max(total - blocked, 0.0)

    def preview_info(self, feature: Feature, ctx: BuildContext) -> dict[str, float]:
        """The live area values for the panel."""
        total, open_area = self.areas(feature, ctx)
        return {"total_area": total, "open_area": open_area}

    def _solids(
        self, feature: Feature, ctx: BuildContext
    ) -> tuple[NamedShape, list[NamedShape], list[Issue], TopoDS_Face]:
        from fdcad.core.features.solids import solids

        body = require_body(feature, ctx)
        lay = self._layout(feature, ctx)
        up, lift = lay["up"], lay["lift"]
        fid = feature.id
        # The wall is measured in the body of the vent face only (D2641): a body lying
        # under the wall made the opening go on into it.
        own = fx.solid_with_face(body.shape, lay["face"]) if len(solids(body.shape)) > 1 else None
        wall = self._wall(body.shape if own is None else own, lay["opening"], up, lift)
        cut = _slab(f"{fid}/opening", compound(lay["opening"]), up, -lift - 0.01, wall + 0.02)
        adds: list[NamedShape] = []
        for role in ("rib", "spar", "fill"):
            shape = lay[role]
            if shape is None:
                continue
            offset = _value(feature, f"{role}_offset")
            depth = _value(feature, f"{role}_depth")
            if depth <= 0 or offset < 0:
                raise FeatureError(
                    f"{feature.name}: the {role} depth must be above zero and its offset not "
                    "negative. Enter other values."
                )
            depth = min(depth, wall - offset)
            if depth <= 0:
                raise FeatureError(
                    f"{feature.name}: the {role} offset is deeper than the wall. Reduce the offset."
                )
            slab = _slab(f"{fid}/{role}", shape, up, offset - lift, depth)
            draft = _value(feature, f"{role}_draft")
            fillet = _value(feature, f"{role}_fillet")
            if draft or fillet:  # TR146 item 3 (D2406)
                from fdcad.core.features.vent_shape import shaped

                where = fx.add(centroid(lay["opening"][0]), up, lift - offset)
                slab = shaped(feature.name, role, slab, up, where, draft, fillet, lay["opening"])
            adds.append(slab)
        return cut, adds, lay["issues"], lay["face"]

    @staticmethod
    def _wall(body: TopoDS_Shape, opening: list[TopoDS_Face], up: fx.Vec3, lift: float) -> float:
        """Wall thickness under the opening: where a line down from it leaves the part."""
        deepest = 0.0
        for face in opening:
            start = fx.add(centroid(face), up, lift + 1e-3)
            hits = [h for h in line_hits(body, start, fx.neg(up)) if h[0] > 2e-3]
            if hits:
                deepest = max(deepest, hits[0][0] - 1e-3)
        if deepest <= 0:
            raise FeatureError("The vent is not over the part. Move the sketch onto the face.")
        return deepest

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Cut the opening, then add the ribs, spars and fill back."""
        from fdcad.core.features.bodies import in_body_of

        body = require_body(feature, ctx)
        cut, adds, issues, face = self._solids(feature, ctx)

        def run(wall: NamedShape) -> NamedShape:
            result = combine(feature.id, feature.name, wall, cut, "cut")
            for part in adds:
                result = combine(feature.id, feature.name, result, part, "boss")
            return result

        # Only the body of the vent face is cut and gets the ribs back (IDEAS 52, D2641).
        # The opening also cut into a body lying under the wall, and the ribs were fused
        # with the whole part, which can join to the wall a body that touches them.
        result = in_body_of(body, face, feature.id, run)
        issues = issues + check_result(feature.id, feature.name, ctx.body, result, None)
        return FeatureResult(body=result, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The opening, for the preview."""
        cut, _adds, _issues, _face = self._solids(feature, ctx)
        return cut


def _faces(shape: TopoDS_Shape) -> list[TopoDS_Shape]:
    from fdcad.core.naming.names import faces_of

    return list(faces_of(shape))
