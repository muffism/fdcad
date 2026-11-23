"""Cuts and joins on large bodies that work only where the tool is (D2601, IDEAS 66).

The kernel's boolean works on every face of both shapes. On the machine bed (one body
of 5400 faces) each cut took about 2 s, even for a 3 mm hole, and booleans were 58
percent of its 16 minute rebuild. Most of that time went to faces far from the tool,
and to the bed's top face, whose 955 holes the kernel rebuilt for every new one.

Here only the faces whose boxes meet the tool's box go to the kernel's splitter. A big
flat face whose outline is away from the tool is stood in for by a small patch of its
plane, which takes along the holes of the face that lie in the patch; the new outline
the cut makes then goes back into the big face as one more loop. The split pieces are
sorted:

* a piece of the tool is inside the body when a ray from it crosses the body's faces
  an odd number of times (the faces a ray can reach are found from boxes in numpy);
* a piece of the body is inside the tool by the kernel's point classifier on the
  small tool;
* a piece that lies on a face of the other shape is kept by the directions of the two
  faces: for a cut when they face apart, for a join when they face the same way.

The kept pieces are put into a copy of the body's shell, with every other face as it
was, and the result is checked before it is used: each new or changed face is valid,
every edge of them is used twice with opposite directions, and the shell is still one
connected piece. Anything unusual, or any doubt, returns None, and the caller uses the
kernel's own boolean. ``FDCAD_LOCAL_BOOLEAN=0`` turns this off; with
``FDCAD_LOCAL_BOOLEAN_CHECK=1`` every local result is compared with the kernel's
(tests on the large parts).

Kernel work: rebuild thread only. Nothing here imports Qt.
"""

from __future__ import annotations

import os
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from OCP.Bnd import Bnd_Box
from OCP.BOPAlgo import BOPAlgo_Builder
from OCP.BOPTools import BOPTools_AlgoTools3D
from OCP.BRep import BRep_Builder, BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepClass import BRepClass_FaceClassifier
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.BRepTools import BRepTools, BRepTools_History
from OCP.Geom import Geom_Plane
from OCP.GeomAbs import GeomAbs_Plane
from OCP.gp import gp_Dir, gp_Lin, gp_Pnt, gp_Pnt2d, gp_Vec
from OCP.IntCurvesFace import IntCurvesFace_Intersector
from OCP.IntCurveSurface import IntCurveSurface_Tangent
from OCP.IntTools import IntTools_Context
from OCP.Message import Message_ProgressRange
from OCP.ShapeAnalysis import ShapeAnalysis_Surface
from OCP.TopAbs import (
    TopAbs_EDGE,
    TopAbs_FACE,
    TopAbs_FORWARD,
    TopAbs_IN,
    TopAbs_ON,
    TopAbs_OUT,
    TopAbs_REVERSED,
    TopAbs_SHELL,
    TopAbs_SOLID,
    TopAbs_WIRE,
)
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Compound, TopoDS_Face, TopoDS_Iterator, TopoDS_Shape

#: Bodies with fewer faces go to the kernel: it is quick enough on them.
MIN_FACES = 1000
#: Bodies from this many faces up to ``MIN_FACES`` are made here only when every face
#: near the tool is a big flat face stood in for by a patch (D2664): the kernel rebuilds
#: every hole of such a face in each cut, so a plate's holes grew dearer one by one.
PATCH_MIN_FACES = 100
#: Flat faces with at least this many edges may be stood in for by a patch.
BIG_FACE_EDGES = 40
#: More faces near the tool than this share of the body: the kernel is as quick.
MAX_NEAR_SHARE = 0.3
DISABLE_ENV = "FDCAD_LOCAL_BOOLEAN"
CHECK_ENV = "FDCAD_LOCAL_BOOLEAN_CHECK"

_BUILDER = BRep_Builder()
_RAYS = [
    gp_Dir(0, 0, 1),
    gp_Dir(0, 0, -1),
    gp_Dir(1, 0, 0),
    gp_Dir(-1, 0, 0),
    gp_Dir(0, 1, 0),
    gp_Dir(0, -1, 0),
    gp_Dir(0.31, 0.47, 0.83),
    gp_Dir(-0.53, 0.29, -0.79),
]


def enabled() -> bool:
    """False when turned off with ``FDCAD_LOCAL_BOOLEAN=0``."""
    return os.environ.get(DISABLE_ENV, "1") != "0"


def checking() -> bool:
    """True when every local result is compared with the kernel's (``CHECK_ENV``)."""
    return os.environ.get(CHECK_ENV) == "1"


#: What the local booleans did, for tests and measurements.
STATS: dict[str, int] = {}


def _count(what: str) -> None:
    STATS[what] = STATS.get(what, 0) + 1


@dataclass
class Result:
    """A local boolean's shape (a compound of one solid, as the kernel gives) and the
    history of every face of both shapes."""

    shape: TopoDS_Shape
    history: BRepTools_History


# The face index of a body ---------------------------------------------------------


def _box(shape: TopoDS_Shape) -> Bnd_Box:
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box, False)
    return box


def _corners(box: Bnd_Box) -> tuple[float, float, float, float, float, float]:
    low, high = box.CornerMin(), box.CornerMax()
    return (low.X(), low.Y(), low.Z(), high.X(), high.Y(), high.Z())


def _faces(shape: TopoDS_Shape) -> list[TopoDS_Face]:
    found: list[TopoDS_Face] = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        found.append(TopoDS.Face(explorer.Current()))
        explorer.Next()
    return found


@dataclass(eq=False)
class _Index:
    """A solid's faces with their boxes, kept from one feature to the next."""

    solid: TopoDS_Shape
    faces: list[TopoDS_Face]
    boxes: np.ndarray[Any, Any]
    hits: dict[int, IntCurvesFace_Intersector] = field(default_factory=dict)

    @classmethod
    def of(cls, solid: TopoDS_Shape) -> _Index:
        faces = _faces(solid)
        boxes = np.array([_corners(_box(f)) for f in faces], dtype=float).reshape(-1, 6)
        return cls(solid, faces, boxes)

    def near(self, box: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
        """Indices of the faces whose boxes meet ``box``."""
        b = self.boxes
        meets = np.all(b[:, :3] <= box[3:], axis=1) & np.all(b[:, 3:] >= box[:3], axis=1)
        return np.nonzero(meets)[0]

    def reachable(self, p: gp_Pnt, d: gp_Dir) -> np.ndarray[Any, Any]:
        """Indices of the faces whose boxes a ray from ``p`` along ``d`` meets."""
        origin = np.array([p.X(), p.Y(), p.Z()])
        way = np.array([d.X(), d.Y(), d.Z()])
        low, high = self.boxes[:, :3] - 1e-4, self.boxes[:, 3:] + 1e-4
        t_in = np.full(len(low), -np.inf)
        t_out = np.full(len(low), np.inf)
        for a in range(3):
            if way[a] == 0:
                inside = (low[:, a] <= origin[a]) & (origin[a] <= high[:, a])
                t_in = np.where(inside, t_in, np.inf)
            else:
                t1 = (low[:, a] - origin[a]) / way[a]
                t2 = (high[:, a] - origin[a]) / way[a]
                t_in = np.maximum(t_in, np.minimum(t1, t2))
                t_out = np.minimum(t_out, np.maximum(t1, t2))
        return np.nonzero((t_out >= t_in) & (t_out >= 0))[0]

    def inside(self, p: gp_Pnt) -> bool | None:
        """True when ``p`` is inside the solid, by counting ray crossings; None when no
        ray gives a clean count (it grazes an edge or a face)."""
        rays = sorted(_RAYS, key=lambda d: len(self.reachable(p, d)))
        for way in rays:
            line = gp_Lin(p, way)
            count, clean = 0, True
            for i in self.reachable(p, way):
                hit = self.hits.get(int(i))
                if hit is None:
                    hit = self.hits[int(i)] = IntCurvesFace_Intersector(self.faces[i], 1e-7)
                hit.Perform(line, -1e-7, 1e100)
                for k in range(1, hit.NbPnt() + 1):
                    w = hit.WParameter(k)
                    if (
                        abs(w) < 1e-6
                        or hit.State(k) == TopAbs_ON
                        or hit.Transition(k) == IntCurveSurface_Tangent
                    ):
                        clean = False
                        break
                    if w > 0:
                        count += 1
                if not clean:
                    break
            if clean:
                return count % 2 == 1
        return None

    def after(self, solid: TopoDS_Shape, gone: set[int], added: list[TopoDS_Face]) -> _Index:
        """The index of the result: these faces gone, those added. The kept faces keep
        their boxes and ray tests."""
        keep = [i for i in range(len(self.faces)) if i not in gone]
        faces = [self.faces[i] for i in keep] + added
        new_boxes = np.array([_corners(_box(f)) for f in added], dtype=float).reshape(-1, 6)
        boxes = np.concatenate([self.boxes[keep], new_boxes])
        renumber = {old: new for new, old in enumerate(keep)}
        hits = {renumber[i]: h for i, h in self.hits.items() if i in renumber}
        return _Index(solid, faces, boxes, hits)


_INDEXES: OrderedDict[int, _Index] = OrderedDict()
_KEEP = 6


def _index_of(solid: TopoDS_Shape) -> _Index:
    key = hash(solid)
    found = _INDEXES.get(key)
    if found is not None and found.solid.IsSame(solid):
        _INDEXES.move_to_end(key)
        return found
    made = _Index.of(solid)
    _remember(made)
    return made


def _remember(index: _Index) -> None:
    _INDEXES[hash(index.solid)] = index
    _INDEXES.move_to_end(hash(index.solid))
    while len(_INDEXES) > _KEEP:
        _INDEXES.popitem(last=False)


def forget() -> None:
    """Drop every kept face index (tests, freeing memory)."""
    _INDEXES.clear()


# Pieces and points ----------------------------------------------------------------


_CONTEXT = IntTools_Context()


def _point_in(face: TopoDS_Shape) -> gp_Pnt | None:
    p, uv = gp_Pnt(), gp_Pnt2d()
    if BOPTools_AlgoTools3D.PointInFace_s(TopoDS.Face(face), p, uv, _CONTEXT) != 0:
        return None
    return p


def _normal(face: TopoDS_Shape, p: gp_Pnt) -> gp_Vec | None:
    f = TopoDS.Face(face)
    u, v = ShapeAnalysis_Surface(BRep_Tool.Surface_s(f)).ValueOfUV(p, 1e-6).Coord()
    q, du, dv = gp_Pnt(), gp_Vec(), gp_Vec()
    BRepAdaptor_Surface(f).D1(u, v, q, du, dv)
    n = du.Crossed(dv)
    if n.Magnitude() < 1e-12:
        return None
    if face.Orientation() == TopAbs_REVERSED:
        n.Reverse()
    return n.Normalized()


def _wires(face: TopoDS_Shape) -> list[TopoDS_Shape]:
    found = []
    it = TopoDS_Iterator(face.Oriented(TopAbs_FORWARD))
    while it.More():
        if it.Value().ShapeType() == TopAbs_WIRE:
            found.append(it.Value())
        it.Next()
    return found


def _edge_count(shape: TopoDS_Shape) -> int:
    from fdcad.core.occ import ShapeMap

    edges = ShapeMap()
    TopExp.MapShapes_s(shape, TopAbs_EDGE, edges)
    return int(edges.Extent())


def _patch(face: TopoDS_Face, tool_box: Bnd_Box) -> tuple[TopoDS_Face, list[Any]] | None:
    """A small patch of a big flat face's plane around the tool, carrying the face's
    holes that lie in it; None when the face is not one to stand in for."""
    from fdcad.core.occ import ShapeMap

    if _edge_count(face) < BIG_FACE_EDGES:
        return None
    if BRepAdaptor_Surface(face).GetType() != GeomAbs_Plane:
        return None
    grown = Bnd_Box()
    grown.Add(tool_box)
    grown.Enlarge(1.0)
    outer = BRepTools.OuterWire_s(face)
    outline = ShapeMap()
    TopExp.MapShapes_s(outer, TopAbs_EDGE, outline)
    for i in range(1, outline.Extent() + 1):
        if not _box(outline.FindKey(i)).IsOut(grown):
            return None  # the tool is near the face's own outline
    holes = [(w, _box(w)) for w in _wires(face) if not w.IsSame(outer)]
    carried: list[Any] = []
    for _round in range(4):
        carried, crossing = [], False
        for wire, box in holes:
            if box.IsOut(grown):
                continue
            if not grown.IsOut(box.CornerMin()) and not grown.IsOut(box.CornerMax()):
                carried.append(wire)
            else:
                grown.Add(box)
                grown.Enlarge(0.5)
                crossing = True
        if not crossing:
            break
    else:
        return None
    plane = BRepAdaptor_Surface(face).Plane()
    surface = ShapeAnalysis_Surface(Geom_Plane(plane))
    low, high = grown.CornerMin(), grown.CornerMax()
    us, vs = [], []
    for x in (low.X(), high.X()):
        for y in (low.Y(), high.Y()):
            for z in (low.Z(), high.Z()):
                u, v = surface.ValueOfUV(gp_Pnt(x, y, z), 1e-6).Coord()
                us.append(u)
                vs.append(v)
    rect = BRepBuilderAPI_MakeFace(plane, min(us), max(us), min(vs), max(vs)).Face()
    centre = surface.Value((min(us) + max(us)) / 2, (min(vs) + max(vs)) / 2)
    if not carried and BRepClass_FaceClassifier(face, centre, 1e-7).State() != TopAbs_IN:
        return None
    wire = BRepTools.OuterWire_s(rect)
    for loop in (wire, wire.Reversed()):
        probe = TopoDS.Face(face.Oriented(TopAbs_FORWARD).EmptyCopied())
        _BUILDER.Add(probe, loop)
        if BRepClass_FaceClassifier(probe, centre, 1e-7).State() != TopAbs_IN:
            continue
        patch = TopoDS.Face(face.Oriented(TopAbs_FORWARD).EmptyCopied())
        _BUILDER.Add(patch, loop)
        for hole in carried:
            _BUILDER.Add(patch, hole)
        return TopoDS.Face(patch.Oriented(face.Orientation())), carried
    return None


# The boolean ----------------------------------------------------------------------


def _one_solid(shape: TopoDS_Shape) -> TopoDS_Shape | None:
    """The only solid of ``shape``, when it holds exactly one and nothing else."""
    solids = []
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        solids.append(explorer.Current())
        explorer.Next()
    if len(solids) != 1:
        return None
    from fdcad.core.occ import ShapeMap

    all_faces, solid_faces = ShapeMap(), ShapeMap()
    TopExp.MapShapes_s(shape, TopAbs_FACE, all_faces)
    TopExp.MapShapes_s(solids[0], TopAbs_FACE, solid_faces)
    if all_faces.Extent() != solid_faces.Extent():
        return None  # loose faces beside the solid
    return solids[0]


def run(kind: str, body: TopoDS_Shape, tool: TopoDS_Shape, fuzzy: float) -> Result | None:
    """Cut (``kind`` "cut") or join ("fuse") ``tool`` with ``body`` locally; None when
    the kernel's own boolean should do it."""
    if kind not in ("cut", "fuse") or not enabled():
        return None
    from fdcad.core.occ import ShapeMap

    count = ShapeMap()
    TopExp.MapShapes_s(body, TopAbs_FACE, count)
    if count.Extent() < min(MIN_FACES, PATCH_MIN_FACES):
        return None
    patch_only = count.Extent() < MIN_FACES
    solid = _one_solid(body)
    if solid is None:
        _count("body not one solid")
        return None
    cutter = _one_solid(tool)
    if cutter is None:
        _count("tool not one solid")
        return None
    try:
        made = _local(kind, solid, cutter, fuzzy, patch_only)
    except Exception:  # the kernel raises its own types: use its boolean instead
        _count("failed")
        return None
    if made is None:
        return None
    _count(kind)
    return made


def _local(
    kind: str, solid: TopoDS_Shape, tool: TopoDS_Shape, fuzzy: float, patch_only: bool = False
) -> Result | None:
    from fdcad.core.occ import ShapeMap, shape_list

    index = _index_of(solid)
    tool_box = _box(tool)
    tool_box.Enlarge(max(1e-4, 10 * fuzzy))
    near_ids = index.near(np.array(_corners(tool_box)))
    if len(near_ids) == 0:
        _count("none near")
        return None
    if len(near_ids) > MAX_NEAR_SHARE * len(index.faces):
        _count("too many near")
        return None
    near = [index.faces[i] for i in near_ids]
    stand_in: dict[int, tuple[TopoDS_Face, list[Any]]] = {}
    pieces_in = TopoDS_Compound()
    _BUILDER.MakeCompound(pieces_in)
    for k, face in enumerate(near):
        got = _patch(face, tool_box)
        if got is not None:
            stand_in[k] = got
            _BUILDER.Add(pieces_in, got[0])
        else:
            _BUILDER.Add(pieces_in, face)
    if patch_only and len(stand_in) < len(near):
        # A mid size body (D2664): only a tool that meets nothing but the inside of big
        # flat faces is made here, as on a perforated plate. Where it meets other faces
        # too, the kernel may split them in ways the local pieces do not.
        _count("not only big faces near")
        return None
    splitter = BOPAlgo_Builder()
    splitter.AddArgument(pieces_in)
    splitter.AddArgument(tool)
    splitter.SetNonDestructive(True)
    splitter.SetRunParallel(True)
    if fuzzy > 0:
        splitter.SetFuzzyValue(fuzzy)
    splitter.Perform(Message_ProgressRange())
    if splitter.HasErrors():
        _count("split failed")
        return None

    def images(face: TopoDS_Shape) -> list[TopoDS_Shape]:
        found = shape_list(splitter.Modified(face))
        if found:
            return found
        return [] if splitter.IsDeleted(face) else [face]

    body_side = ShapeMap()
    split: dict[int, list[TopoDS_Shape]] = {}  # every near face's pieces, split or not
    for k, face in enumerate(near):
        source = stand_in[k][0] if k in stand_in else face
        pieces = images(source)
        for piece in pieces:
            body_side.Add(piece)
        split[k] = pieces
    tool_faces = _faces(tool)
    tool_images = {j: images(tf) for j, tf in enumerate(tool_faces)}
    kept_tool: dict[int, list[TopoDS_Face]] = {}
    for j, pieces in tool_images.items():
        kept: list[TopoDS_Face] = []
        for piece in pieces:
            if body_side.Contains(piece):
                continue  # on a body face: that face's piece decides
            p = _point_in(piece)
            if p is None:
                _count("no point")
                return None
            state = index.inside(p)
            if state is None:
                _count("ray unclear")
                return None
            if kind == "cut" and state:
                kept.append(TopoDS.Face(piece.Reversed()))
            elif kind == "fuse" and not state:
                kept.append(TopoDS.Face(piece))
        kept_tool[j] = kept
    if not any(kept_tool.values()):
        _count("no tool face kept")
        return None  # nothing of the tool stays: the kernel decides (removed lumps)

    new_faces: dict[int, list[TopoDS_Face]] = {}  # only the faces that change
    valid: list[TopoDS_Face] = [f for kept in kept_tool.values() for f in kept]
    edge_from: list[TopoDS_Shape] = list(valid)  # shapes whose edges must close up
    for k, pieces in split.items():
        face = near[k]
        keep: list[TopoDS_Shape] = []
        for piece in pieces:
            p = _point_in(piece)
            if p is None:
                _count("no point")
                return None
            state = BRepClass3d_SolidClassifier(tool, p, 1e-6).State()
            if state == TopAbs_OUT:
                keep.append(piece)
            elif state == TopAbs_ON:
                on = next(
                    (
                        tool_faces[j]
                        for j, ims in tool_images.items()
                        if any(x.IsSame(piece) for x in ims)
                    ),
                    None,
                )
                if on is None:
                    _count("on, no tool face")
                    return None
                mine, theirs = _normal(face, p), _normal(on, p)
                if mine is None or theirs is None:
                    _count("no normal")
                    return None
                same = mine.Dot(theirs) > 0
                if (kind == "cut" and not same) or (kind == "fuse" and same):
                    keep.append(piece)
            elif state != TopAbs_IN:
                _count("unclear piece")
                return None
        if k in stand_in:
            if len(keep) != 1:
                _count("patch split")
                return None
            carried = stand_in[k][1]
            image = TopoDS.Face(keep[0].Oriented(TopAbs_FORWARD))
            outline = BRepTools.OuterWire_s(image)
            big = TopoDS.Face(face.Oriented(TopAbs_FORWARD).EmptyCopied())
            for wire in _wires(face):
                if not any(wire.IsSame(c) for c in carried):
                    _BUILDER.Add(big, wire)
            for wire in _wires(image):
                if not wire.IsSame(outline):
                    _BUILDER.Add(big, wire)
                    edge_from.append(wire)  # the big face's new and carried loops
            valid.append(image)  # the patch with them: the big face's other loops are
            keep = [big.Oriented(face.Orientation())]  # far, and as they were
        elif len(keep) == 1 and keep[0].IsSame(face):
            continue  # untouched and outside the tool
        else:
            valid.extend(TopoDS.Face(s) for s in keep)
            edge_from.extend(keep)
            edge_from.append(face)  # its edges that stay must still close the shell
        new_faces[k] = [TopoDS.Face(s) for s in keep]

    # Into a copy of the shell that holds the changed faces.
    gone = ShapeMap()
    for k in new_faces:
        gone.Add(near[k])
    shells = []
    explorer = TopExp_Explorer(solid, TopAbs_SHELL)
    while explorer.More():
        shells.append(explorer.Current())
        explorer.Next()
    touched = [s for s in shells if any(gone.Contains(f) for f in _faces_once(s, gone))]
    if not new_faces:
        _count("no body face changes")
        return None  # a hollow inside, or a lump beside: the kernel makes its shell
    if len(touched) != 1:
        _count("several shells")
        return None
    shell = touched[0]
    by_face = {k: near[k] for k in new_faces}
    replacement = ShapeMap()
    for face in by_face.values():
        replacement.Add(face)
    added_tool = [f for kept in kept_tool.values() for f in kept]
    added = added_tool + [f for k in new_faces for f in new_faces[k]]
    new_shell = shell.EmptyCopied()
    it = TopoDS_Iterator(shell)
    while it.More():
        face = it.Value()
        k = replacement.FindIndex(face)
        if k:
            for piece in new_faces[list(by_face)[k - 1]]:
                _BUILDER.Add(new_shell, piece)
        else:
            _BUILDER.Add(new_shell, face)
        it.Next()
    for face in added_tool:
        _BUILDER.Add(new_shell, face)
    new_shell.Closed(True)
    new_solid = solid.EmptyCopied()
    for s in shells:
        _BUILDER.Add(new_solid, new_shell if s.IsSame(shell) else s)
    if not _sound(new_shell, valid, edge_from):
        return None
    result = TopoDS_Compound()
    _BUILDER.MakeCompound(result)
    _BUILDER.Add(result, new_solid)

    history = BRepTools_History()
    for k, face in by_face.items():
        kept_pieces = new_faces[k]
        if not kept_pieces:
            history.Remove(face)
        for piece in kept_pieces:
            if not piece.IsSame(face):
                history.AddModified(face, piece)
    for j, face in enumerate(tool_faces):
        kept_pieces = kept_tool[j]
        if not kept_pieces:
            history.Remove(face)
        for piece in kept_pieces:
            if not piece.IsSame(face):
                history.AddModified(face, piece)
    gone_ids = {int(near_ids[k]) for k in new_faces}
    _remember(index.after(new_solid, gone_ids, added))
    return Result(result, history)


def _faces_once(shell: TopoDS_Shape, _gone: Any) -> list[TopoDS_Shape]:
    found = []
    it = TopoDS_Iterator(shell)
    while it.More():
        found.append(it.Value())
        it.Next()
    return found


def _sound(shell: TopoDS_Shape, valid: list[TopoDS_Face], edge_from: list[TopoDS_Shape]) -> bool:
    """True when the new faces (``valid``) are valid, every edge of ``edge_from`` that
    is still in the shell is used there twice with opposite directions, and the shell is
    one connected piece."""
    from fdcad.core.occ import ShapeListMap, ShapeMap, shape_list

    for face in valid:
        if not BRepCheck_Analyzer(face, True).IsValid():
            _count("face not valid")
            return False
    ancestors = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(shell, TopAbs_EDGE, TopAbs_FACE, ancestors)
    checked = ShapeMap()
    for shape in edge_from:
        explorer = TopExp_Explorer(shape, TopAbs_EDGE)
        while explorer.More():
            edge = explorer.Current()
            if ancestors.Contains(edge) and not BRep_Tool.Degenerated_s(TopoDS.Edge(edge)):
                checked.Add(edge)  # an edge of a removed face that is gone needs nothing
            explorer.Next()
    uses: dict[int, list[int]] = {}
    seen_faces = ShapeMap()
    for i in range(1, checked.Extent() + 1):
        k = ancestors.FindIndex(checked.FindKey(i))
        for face in shape_list(ancestors.FindFromIndex(k)):
            seen_faces.Add(face)
    # Directions: every checked edge, over all the faces that hold it.
    for j in range(1, seen_faces.Extent() + 1):
        face = seen_faces.FindKey(j)
        explorer = TopExp_Explorer(face, TopAbs_EDGE)
        while explorer.More():
            edge = explorer.Current()
            i = checked.FindIndex(edge)
            if i:
                uses.setdefault(i, []).append(int(edge.Orientation()))
            explorer.Next()
    for i in range(1, checked.Extent() + 1):
        found = uses.get(i, [])
        if sorted(found) != [int(TopAbs_FORWARD), int(TopAbs_REVERSED)]:
            _count("open or doubled edge")
            return False
    if not _connected(seen_faces, ancestors):
        _count("split in two")
        return False
    return True


def _connected(around: Any, ancestors: Any) -> bool:
    """True when the faces ``around`` the change are all in one connected piece.

    That is enough for the whole shell: it was one piece before, so every part of it
    that the change could cut off holds a face next to the change. The search stops as
    soon as it has reached them all, which is near the change unless the only way
    between them is far round the part.
    """
    from fdcad.core.occ import ShapeMap, shape_list

    targets = around.Extent()
    if targets == 0:
        return True
    reached = ShapeMap()
    reached.Add(around.FindKey(1))
    found = 1
    stack = [around.FindKey(1)]
    while stack and found < targets:
        face = stack.pop()
        explorer = TopExp_Explorer(face, TopAbs_EDGE)
        while explorer.More():
            k = ancestors.FindIndex(explorer.Current())
            if k:
                for other in shape_list(ancestors.FindFromIndex(k)):
                    if not reached.Contains(other):
                        reached.Add(other)
                        stack.append(other)
                        if around.Contains(other):
                            found += 1
            explorer.Next()
    return bool(found >= targets)


__all__ = [
    "CHECK_ENV",
    "DISABLE_ENV",
    "MIN_FACES",
    "PATCH_MIN_FACES",
    "STATS",
    "Result",
    "checking",
    "forget",
    "run",
]
