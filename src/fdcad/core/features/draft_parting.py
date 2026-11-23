"""Parting line draft and step draft (PHASE2_SPEC P2.7 item 4, DECISIONS D521).

Faces next to the picked parting edges are tilted about the edges, so the
edges stay where they are. The kernel's draft always carries a tilt on to
faces joined smoothly (a face split by a split line would drag its other half
along), so the part is cut by the parting plane into the piece on each side,
each piece is drafted about the plane, and the pieces are joined again. Only
the faces the cut divided are merged back.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_Transform
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepOffsetAPI import BRepOffsetAPI_DraftAngle
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt, gp_Trsf, gp_Vec
from OCP.ShapeFix import ShapeFix_Shape
from OCP.TopAbs import TopAbs_EDGE, TopAbs_VERTEX
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Face, TopoDS_Shape

from fdcad.core.document.model import Feature
from fdcad.core.features.base import BuildContext, FeatureError, FeatureState, Issue, Vec3
from fdcad.core.features.modify import edge_faces, require_body, resolve_edges
from fdcad.core.features.solids import FUZZY_TOLERANCE, bounding_size, common, solids
from fdcad.core.naming.names import NamedShape, carry, centroid, restrict
from fdcad.core.occ import BRepAlgoAPI_Fuse, ShapeList

#: Parting edges must lie within this distance of one plane square to the pull (mm).
LEVEL_TOLERANCE = 1e-3
_SAMPLES = 9
_PIECE = re.compile(r"^(.*)#\d+$")


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _edge_level(edge: TopoDS_Edge, pull: Vec3) -> tuple[float, float]:
    """Lowest and highest height of the edge along the pull."""
    curve = BRepAdaptor_Curve(edge)
    first, last = curve.FirstParameter(), curve.LastParameter()
    heights = []
    for k in range(_SAMPLES):
        p = curve.Value(first + (last - first) * k / (_SAMPLES - 1))
        heights.append(_dot((p.X(), p.Y(), p.Z()), pull))
    return min(heights), max(heights)


def _sides(feature: Feature) -> tuple[bool, bool]:
    """Whether the pull side and the other side are drafted."""
    both = feature.params.get("both_sides") is True
    other = feature.params.get("other_side") is True
    return (both or not other, both or other)


def faces_by_level(
    feature: Feature, body: NamedShape, edges: Sequence[tuple[str, TopoDS_Edge]], pull: Vec3
) -> dict[float, dict[str, bool]]:
    """For each parting level (height along the pull), the names of the faces to draft and
    whether each is on the pull side (True) or the other side (False)."""
    owner = feature.name
    up, down = _sides(feature)
    levels: dict[float, dict[str, bool]] = {}
    face_level: dict[str, float] = {}
    for name, edge in edges:
        low, high = _edge_level(edge, pull)
        if high - low > LEVEL_TOLERANCE:
            raise FeatureError(
                f"{owner}: parting line {name} does not lie square to the direction of pull. "
                "Pick edges that lie in a plane square to the pull.",
                highlight=[name],
            )
        level = (low + high) / 2
        known = next((k for k in levels if abs(k - level) <= LEVEL_TOLERANCE), None)
        level = known if known is not None else level
        for face in edge_faces(body.shape, edge):
            height = _dot(centroid(face), pull)
            if height > level + LEVEL_TOLERANCE:
                on_pull_side = True
            elif height < level - LEVEL_TOLERANCE:
                on_pull_side = False
            else:
                continue  # a face in the parting plane
            if not (up if on_pull_side else down):
                continue
            face_name = body.primary_name(face) or ""
            if not face_name:
                continue
            seen = face_level.get(face_name)
            if seen is not None and abs(seen - level) > LEVEL_TOLERANCE:
                raise FeatureError(
                    f"{owner}: face {face_name} touches parting lines at two heights. "
                    "Remove one of its parting lines.",
                    highlight=[face_name],
                )
            face_level[face_name] = level
            levels.setdefault(level, {})[face_name] = on_pull_side
    if not levels:
        raise FeatureError(
            f"{owner}: no face next to the parting lines can be drafted on this side. "
            "Tick Other side or pick other edges."
        )
    return levels


def _half_box(body: NamedShape, level: float, pull: Vec3, upward: bool) -> NamedShape:
    """A box far larger than the part, on one side of the parting plane."""
    size = 4 * max(bounding_size(body.shape), 1.0)
    d = gp_Dir(*pull)
    origin = gp_Pnt(d.X() * level, d.Y() * level, d.Z() * level)
    plane = gp_Pln(origin, d)
    face = BRepBuilderAPI_MakeFace(plane, -size, size, -size, size).Face()
    centre = centroid(body.shape)
    shift = gp_Vec(*centre) - gp_Vec(d).Multiplied(_dot(centre, pull))
    move = gp_Trsf()
    move.SetTranslation(shift)
    face = TopoDS.Face(BRepBuilderAPI_Transform(face, move, True).Shape())
    vector = gp_Vec(d).Multiplied(size if upward else -size)
    return NamedShape(BRepPrimAPI_MakePrism(face, vector).Shape(), [])


def _find(half: NamedShape, name: str) -> list[TopoDS_Face]:
    """The face called ``name`` in a piece, or its parts when the cut split it."""
    return [f for n, f in half.faces if n == name or (_PIECE.match(n) or [None, ""])[1] == name]


def _draft_half(
    feature: Feature,
    half: NamedShape,
    names: list[str],
    pull: Vec3,
    level: float,
    angle: float,
) -> NamedShape:
    if not names:
        return half
    owner = feature.name
    d = gp_Dir(*pull)
    plane = gp_Pln(gp_Pnt(d.X() * level, d.Y() * level, d.Z() * level), d)
    maker = BRepOffsetAPI_DraftAngle(half.shape)
    for name in names:
        for face in _find(half, name):
            maker.Add(face, d, angle, plane, True)
            if not maker.AddDone():
                raise FeatureError(
                    f"{owner}: face {name} cannot be drafted about its parting line. "
                    "Remove its parting line or use the neutral plane method.",
                    highlight=[name],
                )
    try:
        maker.Build()
    except Exception as exc:
        raise FeatureError(_FAILED.format(owner=owner)) from exc
    if not maker.IsDone():
        raise FeatureError(_FAILED.format(owner=owner))
    shape = maker.Shape()
    faces = [(n, TopoDS.Face(maker.ModifiedShape(f))) for n, f in half.faces]
    if not BRepCheck_Analyzer(shape).IsValid():
        # Faces split by a split line can come back slightly out of tolerance where
        # their neighbours were tilted; the shape fixer mends the edges.
        fixer = ShapeFix_Shape(shape)
        fixer.Perform()
        reshape = fixer.Context()
        shape = fixer.Shape()
        faces = [(n, TopoDS.Face(reshape.Apply(f))) for n, f in faces]
    return NamedShape(shape, restrict(faces, shape, f"{feature.id}/face"))


_FAILED = (
    "{owner} failed: the faces could not be tilted about the parting lines. "
    "Use a smaller angle or fewer parting lines."
)


def _on_plane(shape: TopoDS_Shape, level: float, pull: Vec3) -> bool:
    if shape.ShapeType() == TopAbs_VERTEX:
        p = BRep_Tool.Pnt_s(TopoDS.Vertex(shape))
        return abs(_dot((p.X(), p.Y(), p.Z()), pull) - level) <= LEVEL_TOLERANCE
    low, high = _edge_level(TopoDS.Edge(shape), pull)
    return abs(low - level) <= LEVEL_TOLERANCE and abs(high - level) <= LEVEL_TOLERANCE


def _join(
    feature: Feature, upper: NamedShape, lower: NamedShape, level: float, pull: Vec3
) -> NamedShape:
    """Fuse the two pieces and merge back the faces the cut divided."""
    op = BRepAlgoAPI_Fuse()
    args, tools = ShapeList(), ShapeList()
    args.Append(upper.shape)
    tools.Append(lower.shape)
    op.SetArguments(args)
    op.SetTools(tools)
    op.SetFuzzyValue(FUZZY_TOLERANCE)
    op.SetToFillHistory(True)
    op.Build()
    if not op.IsDone():
        raise FeatureError(_FAILED.format(owner=feature.name))
    shape = op.Shape()
    fused = NamedShape(
        shape, restrict(carry(upper.faces + lower.faces, op.History()), shape, feature.id)
    )
    from fdcad.core.unify import unify_faces

    keep: list[TopoDS_Shape] = []
    for kind in (TopAbs_EDGE, TopAbs_VERTEX):
        explorer = TopExp_Explorer(shape, kind)
        while explorer.More():
            item = explorer.Current()
            if not _on_plane(item, level, pull) or (
                kind == TopAbs_EDGE and not _same_face_pieces(fused, item)
            ):
                keep.append(item)
            explorer.Next()
    out, history = unify_faces(shape, keep)
    names = carry(fused.faces, history) if history is not None else list(fused.faces)
    return NamedShape(out, restrict(names, out, feature.id))


def _base(name: str) -> str:
    match = _PIECE.match(name)
    return match.group(1) if match else name


def _same_face_pieces(fused: NamedShape, edge: TopoDS_Shape) -> bool:
    """True when the faces on both sides of ``edge`` are pieces of one face the cut divided."""
    faces = edge_faces(fused.shape, TopoDS.Edge(edge))
    if len(faces) != 2:
        return False
    a, b = (fused.primary_name(f) or "" for f in faces)
    return bool(a) and _base(a) == _base(b)


def parting_draft(
    feature: Feature, ctx: BuildContext, pull: Vec3, angle: float, angle2: float
) -> tuple[NamedShape, list[Issue]]:
    """Draft the faces next to the parting lines, one parting level after the other."""
    body = require_body(feature, ctx)
    owner = feature.name
    refs = feature.refs.get("parting_lines")
    if not isinstance(refs, list) or not refs:
        raise FeatureError(f"{owner}: no parting lines are picked. Pick edges in the view.")
    edges, issues = resolve_edges(feature, ctx, "parting_lines")
    levels = faces_by_level(feature, body, edges, pull)
    if feature.params.get("draft_type") == "parting_line" and len(levels) > 1:
        raise FeatureError(
            f"{owner}: the parting lines lie at {len(levels)} heights. "
            "Pick edges at one height, or use Step Draft."
        )

    def build(a1: float, a2: float) -> NamedShape:
        return _levels(feature, body, levels, pull, a1, a2)

    try:
        return build(angle, angle2), issues
    except FeatureError as exc:
        if feature.params.get("allow_reduced") is not True or str(exc) != _FAILED.format(
            owner=owner
        ):
            raise
    # TR147 item 1 (D1418): the largest share of the angles that builds.
    low, high, best = 0.0, 1.0, None
    for _ in range(_REDUCE_STEPS):
        middle = (low + high) / 2
        try:
            best, low = (build(angle * middle, angle2 * middle), middle), middle
        except FeatureError:
            high = middle
    if best is None:
        raise FeatureError(_FAILED.format(owner=owner))
    result, share = best
    import math

    issues.append(
        Issue(
            FeatureState.WARNING,
            f"{owner}: the full angle fails, so the faces are drafted at "
            f"{math.degrees(angle * share):.3g} degrees. Use a smaller angle, or turn off "
            "Allow reduced angle to see the failure.",
            code="reduced_angle",
        )
    )
    return result, issues


#: Halving steps when looking for the largest angle that builds (TR147, D1418).
_REDUCE_STEPS = 7


def _levels(
    feature: Feature,
    body: NamedShape,
    levels: dict[float, dict[str, bool]],
    pull: Vec3,
    angle: float,
    angle2: float,
) -> NamedShape:
    """Draft every parting level, lowest first."""
    owner = feature.name
    down = (-pull[0], -pull[1], -pull[2])
    current = body
    for level in sorted(levels):
        faces = levels[level]
        upper = common(feature.id, owner, current, _half_box(current, level, pull, True))
        lower = common(feature.id, owner, current, _half_box(current, level, pull, False))
        upper = _draft_half(
            feature, upper, [n for n, up in faces.items() if up], pull, level, angle
        )
        lower = _draft_half(
            feature, lower, [n for n, up in faces.items() if not up], down, -level, angle2
        )
        if not solids(upper.shape):
            current = lower  # the parting plane is the top of the part
        elif not solids(lower.shape):
            current = upper  # the parting plane is the bottom of the part
        else:
            current = _join(feature, upper, lower, level, pull)
    return current


def split_draft(
    feature: Feature,
    body: NamedShape,
    names: list[str],
    pull: Vec3,
    level: float,
    angle: float,
    angle2: float,
) -> NamedShape:
    """Neutral plane draft with a second angle below the plane (TR323, D1419).

    The part is cut at the neutral plane; the faces above tilt by ``angle`` and the
    faces below by ``angle2``, both about the plane with the same pull, so with equal
    angles the result is the one plane draft; the pieces are joined again."""
    owner = feature.name
    upper = common(feature.id, owner, body, _half_box(body, level, pull, True))
    lower = common(feature.id, owner, body, _half_box(body, level, pull, False))
    upper = _draft_half(feature, upper, names, pull, level, angle)
    lower = _draft_half(feature, lower, names, pull, level, angle2)
    if not solids(upper.shape):
        return lower
    if not solids(lower.shape):
        return upper
    return _join(feature, upper, lower, level, pull)
