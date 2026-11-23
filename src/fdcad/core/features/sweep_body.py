"""Sweep a solid tool body along a path (TR138 item 3, D2405).

For a milling cutter path: the tool body (one body of the part, placed at the start
of the path) moves along the path without turning, and the space it passes through
is the sweep's solid. The kernel has no sweep of a solid, so the path is followed as
straight moves (curves split within a small chord error) and each move's swept space
is built exactly: the tool is cut in two square to the move through its middle (where
the outline of a round tool lies), every face of each half is pushed along the move
(a prism), and the tool is added at the far end. All pieces go into one boolean. A
tool whose half still has a face curving both ways along a move is refused. No Qt.
"""

from __future__ import annotations

from itertools import pairwise
from typing import Any

from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.BRepTools import BRepTools_WireExplorer
from OCP.collections import List_TopoDS_Shape as TopTools_ListOfShape
from OCP.GCPnts import GCPnts_TangentialDeflection
from OCP.GeomAbs import GeomAbs_Line
from OCP.gp import gp_Pnt, gp_Trsf, gp_Vec
from OCP.TopAbs import TopAbs_REVERSED
from OCP.TopoDS import TopoDS_Shape, TopoDS_Wire

from fdcad.core.document.model import Feature
from fdcad.core.features.base import BuildContext, FeatureError
from fdcad.core.features.solids import solids, volume_of
from fdcad.core.occ import BRepAlgoAPI_Fuse

#: Chord error (mm) and turn (radians) a curved path piece is followed within.
CHORD = 0.05
TURN = 0.2
#: More straight moves than this is refused, so a rebuild stays quick.
MAX_MOVES = 200


def path_points(path: TopoDS_Wire) -> list[gp_Pnt]:
    """Points along ``path`` in order: the ends of straight pieces, and points on
    curved pieces close enough that the straight moves between them stay on it."""
    out: list[gp_Pnt] = []
    explorer = BRepTools_WireExplorer(path)
    while explorer.More():
        edge = explorer.Current()
        explorer.Next()
        curve = BRepAdaptor_Curve(edge)
        if curve.GetType() == GeomAbs_Line:
            ts = [curve.FirstParameter(), curve.LastParameter()]
        else:
            sample = GCPnts_TangentialDeflection(curve, TURN, CHORD)
            ts = [sample.Parameter(i) for i in range(1, sample.NbPoints() + 1)]
        points = [curve.Value(t) for t in ts]
        if edge.Orientation() == TopAbs_REVERSED:  # the wire runs this edge back to front
            points.reverse()
        for p in points:
            if not out or out[-1].Distance(p) > 1e-7:
                out.append(p)
    return out


def tool_solid(feature: Feature, ctx: BuildContext) -> TopoDS_Shape:
    """The body picked as the tool (``refs.tool_body``, any face of it)."""
    from fdcad.core.features.bodies import body_indices

    owner = feature.name
    ref = feature.refs.get("tool_body")
    if ctx.body is None or not isinstance(ref, dict):
        raise FeatureError(f"{owner}: pick the tool body to move along the path.")
    indices, _issues = body_indices(ctx, [ref], owner)
    every = solids(ctx.body.shape)
    if not indices or not 0 <= indices[0] < len(every):
        raise FeatureError(f"{owner}: the tool body was lost. Pick it again.")
    return every[indices[0]]


def _moved(shape: TopoDS_Shape, v: gp_Vec) -> TopoDS_Shape:
    trsf = gp_Trsf()
    trsf.SetTranslation(v)
    return BRepBuilderAPI_Transform(shape, trsf, True).Shape()


def _halves(tool: TopoDS_Shape, v: gp_Vec) -> list[TopoDS_Shape]:
    """``tool`` cut in two by the plane through its middle square to ``v``."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.gp import gp_Dir, gp_Pln

    from fdcad.core.features.preview_anchor import box_centre
    from fdcad.core.occ import BRepAlgoAPI_Splitter

    centre = box_centre(tool)
    if centre is None:
        return [tool]
    face = BRepBuilderAPI_MakeFace(gp_Pln(gp_Pnt(*centre), gp_Dir(v)), -1e4, 1e4, -1e4, 1e4)
    args, tools = TopTools_ListOfShape(), TopTools_ListOfShape()
    args.Append(tool)
    tools.Append(face.Face())
    splitter = BRepAlgoAPI_Splitter()
    splitter.SetArguments(args)
    splitter.SetTools(tools)
    splitter.Build()
    if not splitter.IsDone():
        return [tool]
    return solids(splitter.Shape()) or [tool]


def _one_sided(face: TopoDS_Shape, v: gp_Vec) -> bool:
    """True when every normal of ``face`` points the same side of ``v`` (or along it)."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepLProp import BRepLProp_SLProps
    from OCP.TopAbs import TopAbs_REVERSED as REV
    from OCP.TopoDS import TopoDS

    f = TopoDS.Face(face)
    surface = BRepAdaptor_Surface(f)
    u0, u1 = surface.FirstUParameter(), surface.LastUParameter()
    w0, w1 = surface.FirstVParameter(), surface.LastVParameter()
    signs = set()
    for i in range(7):
        for j in range(7):
            props = BRepLProp_SLProps(
                surface, u0 + (u1 - u0) * (i + 0.5) / 7, w0 + (w1 - w0) * (j + 0.5) / 7, 1, 1e-7
            )
            if not props.IsNormalDefined():
                continue
            n = props.Normal()
            d = n.X() * v.X() + n.Y() * v.Y() + n.Z() * v.Z()
            d = -d if f.Orientation() == REV else d
            if abs(d) > 1e-6 * v.Magnitude():
                signs.add(d > 0)
    return len(signs) <= 1


def _move_pieces(tool: TopoDS_Shape, v: gp_Vec) -> list[TopoDS_Shape] | None:
    """The space ``tool`` sweeps moving straight by ``v``, as pieces to fuse: the tool's
    two halves (cut square to ``v`` through its middle, where a round tool's outline
    lies) each with their faces pushed along ``v``, and the tool at the far end. None
    when a face of a half curves both ways along ``v`` (not a round tool)."""
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer

    out: list[TopoDS_Shape] = [_moved(tool, v)]
    for half in _halves(tool, v):
        explorer = TopExp_Explorer(half, TopAbs_FACE)
        while explorer.More():
            face = explorer.Current()
            explorer.Next()
            if not _one_sided(face, v):
                return None
            prism = BRepPrimAPI_MakePrism(face, v, True).Shape()
            if abs(volume_of(prism)) > 1e-9:  # a face along the move sweeps nothing
                out.append(prism)
    return out


def swept_body(owner: str, tool: TopoDS_Shape, path: TopoDS_Wire) -> TopoDS_Shape:
    """The space ``tool`` passes through moving along ``path`` from the end nearer to it
    (the tool moves by the path point less that end), exact for each straight move of a
    round or flat sided tool."""
    points = path_points(path)
    if len(points) < 2:
        raise FeatureError(f"{owner}: the path has no length. Pick a longer path.")
    if len(points) - 1 > MAX_MOVES:
        raise FeatureError(
            f"{owner}: the path needs more than {MAX_MOVES} moves. Use a shorter or less "
            "curved path."
        )
    from fdcad.core.features.preview_anchor import box_centre

    centre = gp_Pnt(*(box_centre(tool) or (0.0, 0.0, 0.0)))
    if centre.Distance(points[-1]) < centre.Distance(points[0]):
        points.reverse()  # the tool stands at the end the path is drawn to
    start = points[0]
    pieces: list[TopoDS_Shape] = [tool]
    for a, b in pairwise(points):
        at = _moved(tool, gp_Vec(start, a)) if a.Distance(start) > 1e-9 else tool
        made = _move_pieces(at, gp_Vec(a, b))
        if made is None:
            raise FeatureError(
                f"{owner}: the tool body must be round about an axis or flat sided, so its "
                "outline is the same all along a move. Use a simpler tool body."
            )
        pieces += made
    args, tools = TopTools_ListOfShape(), TopTools_ListOfShape()
    args.Append(pieces[0])
    for piece in pieces[1:]:
        tools.Append(piece)
    fuse = BRepAlgoAPI_Fuse()
    fuse.SetArguments(args)
    fuse.SetTools(tools)
    fuse.SetRunParallel(True)
    fuse.Build()
    if not fuse.IsDone():
        raise FeatureError(
            f"{owner}: the tool's path could not be built. Use a simpler path or tool body."
        )
    from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain

    unify = ShapeUpgrade_UnifySameDomain(fuse.Shape(), True, True, False)
    unify.Build()
    return unify.Shape()


def body_sweep(feature: Feature, ctx: BuildContext, path: TopoDS_Wire) -> Any:
    """The named solid of a tool body sweep: faces ``tool/face<k>`` in explorer order."""
    from fdcad.core.naming.names import NamedShape, faces_of

    if feature.params.get("operation", "boss") != "cut":
        raise FeatureError(
            f"{feature.name}: a tool body sweep removes material. Use Swept Cut, or pick a "
            "sketch profile for a boss."
        )
    shape = swept_body(feature.name, tool_solid(feature, ctx), path)
    names = [(f"{feature.id}/tool/face{k}", f) for k, f in enumerate(faces_of(shape), start=1)]
    return NamedShape(shape, names)
