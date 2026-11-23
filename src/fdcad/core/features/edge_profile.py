"""Edge Profile: router shapes swept along edges (TR243, DECISIONS D2011).

Type ``edge_profile``. Refs: ``loop_face`` (a flat face: the profile runs round its
outer loop) or ``edges`` (a chain of joined edges). Params:

- ``router_profile``: ``round_over`` (default), ``cove``, ``rabbet``, ``chamfer_flat`` or
  ``ogee``.
- ``profile_size``: length, the profile's width across the face.
- ``profile_depth``: optional length, the depth down the side (``rabbet`` and
  ``chamfer_flat``; the size when left out).

The cut's cross section sits in the corner between the face (the first face of
the first edge, for picked edges) and the side face, and is swept along the loop
with round joins at corners, keeping its turn to the face's normal. Faces of the
cut are ``<fid>/profile#k``.
"""

from __future__ import annotations

import math

from OCP.BRep import BRep_Tool
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeWire,
    BRepBuilderAPI_RoundCorner,
)
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell
from OCP.BRepTools import BRepTools, BRepTools_WireExplorer
from OCP.GC import GC_MakeArcOfCircle
from OCP.gp import gp_Dir, gp_Pnt, gp_Vec
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Face, TopoDS_Shape, TopoDS_Wire

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
from fdcad.core.features.solids import FUZZY_TOLERANCE, compound, solids
from fdcad.core.naming.names import NamedShape, carry, faces_of, restrict
from fdcad.core.occ import BRepAlgoAPI_Cut, ShapeListMap, ShapeMap
from fdcad.core.plane_normal import plane_normal
from fdcad.core.units import Kind

PROFILES = ("round_over", "cove", "rabbet", "chamfer_flat", "ogee")
#: How far the cut's section reaches past the faces, so the cut is clean (mm).
_PAST = 0.05


def section(kind: str, size: float, depth: float) -> list[tuple[str, list[tuple[float, float]]]]:
    """The cut's closed outline in the corner's (u, v) plane: u across the face, v down
    the side, both into the material. Pieces are ("line", [a, b]) or ("arc", [a, m, b])."""
    e = _PAST
    if kind == "rabbet":
        pts = [(-e, -e), (size, -e), (size, depth), (-e, depth)]
        return [("line", [pts[i], pts[(i + 1) % 4]]) for i in range(4)]
    if kind == "chamfer_flat":  # a 45 degree chamfer, then a flat step at its foot
        step = size / 3
        pts = [(-e, -e), (size, -e), (size, step), (size - step, depth), (-e, depth)]
        return [("line", [pts[i], pts[(i + 1) % len(pts)]]) for i in range(len(pts))]
    s45 = math.sqrt(0.5)
    half = size / 2
    q = half * (1 - s45)
    if kind == "cove":  # a quarter circle hollow centred on the edge
        arcs = [("arc", [(size, 0.0), (size * s45, size * s45), (0.0, size)])]
    elif kind == "round_over":  # the corner rounded: the square less a quarter circle
        arcs = [("arc", [(size, 0.0), (size * (1 - s45), size * (1 - s45)), (0.0, size)])]
    else:  # ogee: a hollow then a round, an S from the face down the side
        arcs = [
            ("arc", [(size, 0.0), (half + q, half - q), (half, half)]),
            ("arc", [(half, half), (q, half + q), (0.0, size)]),
        ]
    return [
        ("line", [(-e, -e), (size, -e)]),
        ("line", [(size, -e), (size, 0.0)]),
        *arcs,
        ("line", [(0.0, size), (-e, size)]),
        ("line", [(-e, size), (-e, -e)]),
    ]


def _section_wire(
    pieces: list[tuple[str, list[tuple[float, float]]]], at: gp_Pnt, u: gp_Vec, v: gp_Vec
) -> TopoDS_Wire:
    def point(p: tuple[float, float]) -> gp_Pnt:
        return at.Translated(u.Multiplied(p[0])).Translated(v.Multiplied(p[1]))

    maker = BRepBuilderAPI_MakeWire()
    for kind, pts in pieces:
        if kind == "line":
            maker.Add(BRepBuilderAPI_MakeEdge(point(pts[0]), point(pts[1])).Edge())
        else:
            arc = GC_MakeArcOfCircle(point(pts[0]), point(pts[1]), point(pts[2])).Value()
            maker.Add(BRepBuilderAPI_MakeEdge(arc).Edge())
    if not maker.IsDone():
        raise ValueError("the profile outline could not be made")
    return maker.Wire()


def _faces_of_edge(shape: TopoDS_Shape, edge: TopoDS_Edge) -> list[TopoDS_Face]:
    found = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(shape, TopAbs_EDGE, TopAbs_FACE, found)
    index = found.FindIndex(edge)
    if index == 0:
        return []
    return [TopoDS.Face(f) for f in found.FindFromIndex(index)]


@register
class EdgeProfile(FeatureType):
    """A router shape cut along a face's outer loop or a chain of edges."""

    type_name = "edge_profile"
    makes_solid = True
    params = (
        ParamSpec("router_profile", choices=PROFILES, default="round_over"),
        ParamSpec("profile_size", kind=Kind.LENGTH),
        ParamSpec("profile_depth", kind=Kind.LENGTH, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Sweep the section and cut it."""
        from fdcad.core.features.lookup import resolve_face
        from fdcad.core.features.modify import resolve_edges

        owner, fid = feature.name, feature.id
        body = ctx.body
        if body is None:
            raise FeatureError(f"{owner}: the part is empty. Add a body first.")
        size_value = feature.params.get("profile_size")
        size = size_value.value if isinstance(size_value, Param) else 0.0
        depth_value = feature.params.get("profile_depth")
        depth = depth_value.value if isinstance(depth_value, Param) else size
        if size <= 0 or depth <= 0:
            raise FeatureError(f"{owner}: enter a size and a depth greater than zero.")
        issues: list[Issue] = []
        face_ref = feature.refs.get("loop_face")
        if isinstance(face_ref, list):
            face_ref = face_ref[0] if face_ref else None
        if isinstance(face_ref, dict):
            top, issues = resolve_face(body, face_ref, owner)
            path = BRepTools.OuterWire_s(top)
        else:
            picked, issues = resolve_edges(feature, ctx, "edges")
            if not picked:
                raise FeatureError(f"{owner}: pick a flat face or the edges to profile.")
            maker = BRepBuilderAPI_MakeWire()
            for _n, e in picked:
                maker.Add(e)
            if not maker.IsDone():
                raise FeatureError(f"{owner}: the edges do not join end to end. Pick a chain.")
            path = maker.Wire()
            top = _faces_of_edge(body.shape, picked[0][1])[0]
        normal = plane_normal(top)
        walk = BRepTools_WireExplorer(path)
        first = walk.Current()
        start = BRep_Tool.Pnt_s(walk.CurrentVertex())
        sides = [f for f in _faces_of_edge(body.shape, first) if not f.IsSame(top)]
        if not sides:
            raise FeatureError(f"{owner}: the edge has no side face. Pick an edge of a solid.")
        side_normal = plane_normal(sides[0])
        if normal is None or side_normal is None:
            raise FeatureError(
                f"{owner}: the face and the side must be flat where the profile starts. "
                "Start on a straight edge between flat faces."
            )
        at = start
        u = gp_Vec(*side_normal).Reversed()
        v = gp_Vec(*normal).Reversed()
        kind = str(feature.params.get("router_profile", "round_over"))
        try:
            outline = _section_wire(section(kind, size, depth), at, u, v)
            pipe = BRepOffsetAPI_MakePipeShell(path)
            pipe.SetMode(gp_Dir(*normal))
            pipe.SetTransitionMode(BRepBuilderAPI_RoundCorner)
            pipe.Add(outline, False, False)
            pipe.Build()
            if not pipe.IsDone():
                raise ValueError("the profile could not be swept along the edges")
            pipe.MakeSolid()
            tool = pipe.Shape()
        except (ValueError, RuntimeError) as exc:
            raise FeatureError(
                f"{owner} failed: {exc}. Use a smaller size or pick fewer edges."
            ) from exc
        # The profile is cut from the body of the picked face (D2622). It was cut from
        # the whole part, and its section, which reaches a little past the faces, cut a
        # sliver from a body standing against the side.
        from fdcad.core.features.bodies import in_body_of

        def run(part: NamedShape) -> NamedShape:
            cut = BRepAlgoAPI_Cut(part.shape, tool)
            cut.SetFuzzyValue(FUZZY_TOLERANCE)
            cut.Build()
            if not cut.IsDone() or not solids(cut.Shape()):
                raise FeatureError(
                    f"{owner} failed: the profile could not be cut. Use a smaller size."
                )
            shape = compound(solids(cut.Shape()))
            names = carry(part.faces, cut.History())
            named = ShapeMap()
            for _n, f in names:
                named.Add(f)
            k = 0
            for f in faces_of(shape):
                if not named.Contains(f):
                    k += 1
                    names.append((f"{fid}/profile#{k}", f))
            return NamedShape(shape, restrict(names, shape, fid))

        return FeatureResult(body=in_body_of(body, top, fid, run), issues=issues)
