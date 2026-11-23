"""Kernel helpers shared by solid features: named prisms and revolves, robust booleans,
and the checks of PLAN section 5A (tolerant booleans, zero thickness, unexpected bodies).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar

from OCP.Bnd import Bnd_Box
from OCP.BRep import BRep_Builder
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism, BRepPrimAPI_MakeRevol
from OCP.gp import gp_Ax1, gp_Trsf, gp_Vec
from OCP.GProp import GProp_GProps
from OCP.TopAbs import (
    TopAbs_EDGE,
    TopAbs_FACE,
    TopAbs_ShapeEnum,
    TopAbs_SOLID,
    TopAbs_VERTEX,
    TopAbs_WIRE,
)
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Compound, TopoDS_Face, TopoDS_Shape

from fdcad.core.document.model import Feature
from fdcad.core.features.base import BuildContext, FeatureError, FeatureState, Fix, Issue, Vec3
from fdcad.core.naming.names import (
    NamedFace,
    NamedShape,
    carry,
    order_by_position,
    restrict,
)
from fdcad.core.occ import (
    BRepAlgoAPI_BooleanOperation,
    BRepAlgoAPI_Cut,
    BRepAlgoAPI_Fuse,
    ShapeList,
    ShapeListMap,
    ShapeMap,
    ShapeSet,
    shape_list,
)
from fdcad.core.sketch.profiles import Profile
from fdcad.core.tool_check import tools_kept

#: Default boolean fuzzy tolerance in mm (DECISIONS D47).
FUZZY_TOLERANCE = 1e-5


def compound(shapes: Sequence[TopoDS_Shape]) -> TopoDS_Compound:
    """Group shapes into one compound."""
    comp = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(comp)
    for s in shapes:
        builder.Add(comp, s)
    return comp


def solids(shape: TopoDS_Shape) -> list[TopoDS_Shape]:
    """The solids in ``shape``."""
    out = []
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        out.append(explorer.Current())
        explorer.Next()
    return out


def bounding_size(*shapes: TopoDS_Shape) -> float:
    """Diagonal of the box around all shapes, in mm."""
    box = Bnd_Box()
    for s in shapes:
        BRepBndLib.Add_s(s, box)
    if box.IsVoid():
        return 0.0
    return float(box.CornerMin().Distance(box.CornerMax()))


def reach_from(origin: tuple[float, float, float], *shapes: TopoDS_Shape) -> float:
    """How far a big box centred on ``origin`` must reach to hold all of ``shapes``: the
    distance to the far corner of the box round them, doubled, plus 10 mm (D1087).

    A size from the shapes alone (their diagonal) is not enough when the box is not
    centred on them: a finger joint centred its cutting slabs on the model origin, and
    on two small plates 340 mm from it every finger came out empty.
    """
    box = Bnd_Box()
    for s in shapes:
        BRepBndLib.Add_s(s, box)
    if box.IsVoid():
        return 10.0
    lo, hi = box.CornerMin(), box.CornerMax()
    far = max(
        math.dist(origin, (x, y, z))
        for x in (lo.X(), hi.X())
        for y in (lo.Y(), hi.Y())
        for z in (lo.Z(), hi.Z())
    )
    return 2.0 * far + 10.0


def _cap_names(prefix: str, faces: list[TopoDS_Face], role: str) -> list[NamedFace]:
    if len(faces) == 1:
        return [(f"{prefix}/{role}", faces[0])]
    return [(f"{prefix}/{role}#{k}", f) for k, f in enumerate(order_by_position(faces), start=1)]


def _swept(
    fid: str,
    profile: Profile,
    make: type[BRepPrimAPI_MakePrism] | type[BRepPrimAPI_MakeRevol],
    *args: object,
    caps: bool = True,
) -> NamedShape:
    """Sweep every profile face and name caps and sides (``fid/cap/start``, ``fid/side/e3``)."""
    shapes: list[TopoDS_Shape] = []
    starts: list[TopoDS_Face] = []
    ends: list[TopoDS_Face] = []
    sides: list[NamedFace] = []
    for face in profile.faces:
        maker = make(face, *args)
        maker.Build()
        if not maker.IsDone():
            raise FeatureError("The profile could not be swept. Check the sketch and the values.")
        shapes.append(maker.Shape())
        if caps:
            starts.append(TopoDS.Face(maker.FirstShape()))
            ends.append(TopoDS.Face(maker.LastShape()))
        explorer = TopExp_Explorer(face, TopAbs_EDGE)
        done: set[str] = set()
        while explorer.More():
            edge = explorer.Current()
            entity = profile.entity_of(TopoDS.Edge(edge))
            explorer.Next()
            if entity is None or entity in done:
                continue
            done.add(entity)
            for k, side in enumerate(shape_list(maker.Generated(edge)), start=1):
                suffix = "" if k == 1 else f"#{k}"
                if side.ShapeType() == TopAbs_FACE:
                    sides.append((f"{fid}/side/{entity}{suffix}", TopoDS.Face(side)))
    shape = shapes[0] if len(shapes) == 1 else compound(shapes)
    names = _cap_names(fid, starts, "cap/start") + _cap_names(fid, ends, "cap/end") + sides
    return NamedShape(shape, restrict(names, shape, fid))


def prism(fid: str, profile: Profile, vector: gp_Vec) -> NamedShape:
    """Extrude every profile face along ``vector``."""
    return _swept(fid, profile, BRepPrimAPI_MakePrism, vector)


def revolve(
    fid: str, profile: Profile, axis: gp_Ax1, angle: float, full: bool, copy: bool = False
) -> NamedShape:
    """Revolve every profile face by ``angle`` radians. A full turn has no caps.

    ``copy`` revolves a copy of the profile: only then does the kernel report the
    faces a full turn makes from edges square to the axis (thin walls, D523).
    """
    if copy:
        return _swept(fid, profile, BRepPrimAPI_MakeRevol, axis, angle, True, caps=not full)
    return _swept(fid, profile, BRepPrimAPI_MakeRevol, axis, angle, caps=not full)


def transform(named: NamedShape, trsf: gp_Trsf) -> NamedShape:
    """Move a named shape, keeping its names."""
    maker = BRepBuilderAPI_Transform(named.shape, trsf, True)
    shape = maker.Shape()
    names = [(n, TopoDS.Face(maker.ModifiedShape(f))) for n, f in named.faces]
    return NamedShape(shape, restrict(names, shape, "moved"))


# Checks ----------------------------------------------------------------------------


def _distinct(shapes: ShapeList) -> int:
    """Number of distinct shapes in a list (same shape in two orientations counts once)."""
    seen = ShapeMap()
    for shape in shape_list(shapes):
        seen.Add(shape)
    return int(seen.Extent())


def zero_thickness(
    shape: TopoDS_Shape, limit: int = 20, only: ShapeMap | None = None
) -> list[TopoDS_Shape]:
    """Edges and vertices where separate bodies touch, or edges shared by more than two
    faces (PLAN 5A item 2). At most ``limit`` are returned.

    With ``only``, a map of bodies of ``shape``, just the touches that one of those
    bodies has a part in (D1070).
    """
    found: list[TopoDS_Shape] = []

    def wanted(users: ShapeList) -> bool:
        return only is None or any(only.Contains(u) for u in shape_list(users))

    several = len(solids(shape)) > 1
    contact = _FaceContact(shape) if several else None
    edge_solids = ShapeListMap()
    if several:
        TopExp.MapShapesAndAncestors_s(shape, TopAbs_EDGE, TopAbs_SOLID, edge_solids)

    def on_contact(key: TopoDS_Shape, users: ShapeList) -> bool:
        return (
            contact is not None
            and users.Size() > 1
            and _distinct(users) > 1
            and contact.covers(key, shape_list(users))
        )

    edge_faces = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(shape, TopAbs_EDGE, TopAbs_FACE, edge_faces)
    for i in range(1, edge_faces.Extent() + 1):
        faces = edge_faces.FindFromIndex(i)
        # Size() is a cheap C++ call; only the rare edge with more than two face
        # uses needs the slower distinct count (a seam lists its face twice).
        if faces.Size() > 2 and _distinct(faces) > 2:
            key = edge_faces.FindKey(i)
            if several and not wanted(edge_solids.FindFromKey(key)):
                continue
            if not (several and on_contact(key, edge_solids.FindFromKey(key))):
                found.append(key)
    if several:
        for kind in (TopAbs_EDGE, TopAbs_VERTEX):
            owners = edge_solids if kind == TopAbs_EDGE else ShapeListMap()
            if kind == TopAbs_VERTEX:
                TopExp.MapShapesAndAncestors_s(shape, kind, TopAbs_SOLID, owners)
            for i in range(1, owners.Extent() + 1):
                users = owners.FindFromIndex(i)
                if users.Size() > 1 and _distinct(users) > 1 and wanted(users):
                    key = owners.FindKey(i)
                    if not on_contact(key, users) and not any(key.IsSame(f) for f in found):
                        found.append(key)
    return found[:limit]


class _FaceContact:
    """Where bodies meet face to face (D620).

    Split and Split for Print leave pieces that share their cut face. Edges and
    corners on such a contact are not a zero thickness touch.
    """

    def __init__(self, shape: TopoDS_Shape) -> None:
        self.index = ShapeMap()
        TopExp.MapShapes_s(shape, TopAbs_SOLID, self.index)
        self.cache: dict[tuple[int, int], TopoDS_Shape | None] = {}

    def covers(self, key: TopoDS_Shape, users: list[TopoDS_Shape]) -> bool:
        """True when ``key`` lies on a face contact of every pair of ``users``."""
        from OCP.BRepExtrema import BRepExtrema_DistShapeShape

        ids = sorted({self.index.FindIndex(u) for u in users})
        for n, a in enumerate(ids):
            for b in ids[n + 1 :]:
                region = self._region(a, b)
                if region is None:
                    return False
                dist = BRepExtrema_DistShapeShape(key, region)
                if not dist.IsDone() or dist.Value() > 1e-6:
                    return False
        return True

    def _region(self, a: int, b: int) -> TopoDS_Shape | None:
        if (a, b) not in self.cache:
            self.cache[(a, b)] = _contact_faces(self.index.FindKey(a), self.index.FindKey(b))
        return self.cache[(a, b)]


def _contact_faces(one: TopoDS_Shape, two: TopoDS_Shape) -> TopoDS_Shape | None:
    """The area where two solids meet face to face, or None when they do not."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane

    from fdcad.core.occ import BRepAlgoAPI_Common

    def faces(solid: TopoDS_Shape) -> list[tuple[TopoDS_Face, Bnd_Box, bool]]:
        out = []
        explorer = TopExp_Explorer(solid, TopAbs_FACE)
        while explorer.More():
            face = TopoDS.Face(explorer.Current())
            plain = BRepAdaptor_Surface(face).GetType() in (GeomAbs_Plane, GeomAbs_Cylinder)
            box = Bnd_Box()
            BRepBndLib.Add_s(face, box)
            box.Enlarge(1e-6)
            out.append((face, box, plain))
            explorer.Next()
        return out

    found: list[TopoDS_Shape] = []
    second = faces(two)
    for fa, ba, plain_a in faces(one):
        for fb, bb, plain_b in second:
            if ba.IsOut(bb):
                continue
            if fa.IsSame(fb):
                found.append(fa)
                continue
            if not (plain_a and plain_b):
                # Any other surface (the walls of a letter, a swept or lofted face):
                # the faces meet when one lies on the other (D1057). An inlay of text
                # with round letters was called a touch along an edge.
                if plain_a == plain_b:
                    if _lies_on(fa, fb):
                        found.append(fa)
                    elif _lies_on(fb, fa):
                        found.append(fb)
                continue
            if not _same_surface(fa, fb):
                continue
            op = BRepAlgoAPI_Common(fa, fb)
            op.SetFuzzyValue(FUZZY_TOLERANCE)
            op.Build()
            if op.IsDone():
                explorer = TopExp_Explorer(op.Shape(), TopAbs_FACE)
                while explorer.More():
                    if face_area([explorer.Current()]) > 1e-9:
                        found.append(explorer.Current())
                    explorer.Next()
    return compound(found) if found else None


def _lies_on(inner: TopoDS_Face, outer: TopoDS_Face) -> bool:
    """True when ``inner`` lies on ``outer``: its corners and the middle of each of its
    edges are on ``outer`` (within 1e-6 mm)."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape

    points = []
    explorer = TopExp_Explorer(inner, TopAbs_EDGE)
    while explorer.More():
        edge = TopoDS.Edge(explorer.Current())
        explorer.Next()
        if BRep_Tool.Degenerated_s(edge):
            continue
        curve = BRepAdaptor_Curve(edge)
        a, b = curve.FirstParameter(), curve.LastParameter()
        points += [curve.Value(a), curve.Value((a + b) / 2)]
    if not points:
        return False
    for point in points:
        dist = BRepExtrema_DistShapeShape(BRepBuilderAPI_MakeVertex(point).Vertex(), outer)
        if not dist.IsDone() or dist.Value() > 1e-6:
            return False
    return True


#: The sub shapes the last pair of shapes did not share: ``(before, after, new shapes)``.
_LAST_NEW: list[tuple[TopoDS_Shape, TopoDS_Shape, list[TopoDS_Shape]]] = []


def _new_of(before: NamedShape, after: NamedShape, kind: TopAbs_ShapeEnum) -> list[TopoDS_Shape]:
    """The sub shapes of ``kind`` in ``after`` that ``before`` does not have, each once.

    Both shapes are mapped and subtracted in the kernel, and the few shapes left are
    sorted by kind in Python (D2662). The old way walked every face or edge of the part
    in Python, three times per feature (the merge check and the validity check of
    each boolean), which grew with the part: 4 ms an edge pass at 200 faces. The
    last pair is kept, so the checks of one feature map the part once.
    """
    made = next(
        (
            shapes
            for old_shape, new_shape, shapes in _LAST_NEW
            if old_shape.IsEqual(before.shape) and new_shape.IsEqual(after.shape)
        ),
        None,
    )
    if made is None:
        old, new = ShapeSet(), ShapeSet()
        if before.shape.IsNull() or after.shape.IsNull():  # nothing to map, nothing kept
            return _new_by_walk(before, after, kind)
        TopExp.MapShapes_s(before.shape, old)
        TopExp.MapShapes_s(after.shape, new)
        new.Subtract(old)
        made = list(new)
        kept = [s.Oriented(s.Orientation()) for s in (before.shape, after.shape)]  # copies
        _LAST_NEW[:] = [(kept[0], kept[1], made)]
    return [s for s in made if s.ShapeType() == kind]


def _new_by_walk(
    before: NamedShape, after: NamedShape, kind: TopAbs_ShapeEnum
) -> list[TopoDS_Shape]:
    """``_new_of`` by walking ``after`` (an empty shape on either side)."""
    old = ShapeMap()
    TopExp.MapShapes_s(before.shape, kind, old)
    out: list[TopoDS_Shape] = []
    explorer = TopExp_Explorer(after.shape, kind)
    while explorer.More():
        if not old.Contains(explorer.Current()):
            out.append(explorer.Current())
        explorer.Next()
    return out


#: Changed faces with more edge loops than this are checked through their new edges only.
_FULL_FACE_CHECK_WIRES = 8


def _wire_count(face: TopoDS_Shape) -> int:
    count = 0
    explorer = TopExp_Explorer(face, TopAbs_WIRE)
    while explorer.More():
        count += 1
        explorer.Next()
    return count


def is_valid(before: NamedShape | None, after: NamedShape) -> bool:
    """Kernel validity of a feature's result (PLAN 5A, DECISIONS D77).

    Faces and edges the feature did not touch were checked when they were made.
    New edges are always checked, and so are new or changed faces with few edge
    loops. A face with many holes is checked through its new edges, because a
    full face check compares every pair of loops and slows long trees (PLAN 11.2).
    The first solid of a part is checked whole.
    """
    if before is None:
        return bool(BRepCheck_Analyzer(after.shape, True, True).IsValid())
    faces = [
        f for f in _new_of(before, after, TopAbs_FACE) if _wire_count(f) <= _FULL_FACE_CHECK_WIRES
    ]
    parts = faces + _new_of(before, after, TopAbs_EDGE)
    if not parts:
        return True
    return bool(BRepCheck_Analyzer(compound(parts), True, True).IsValid())


def breaks_solid(before: NamedShape, after: NamedShape) -> bool:
    """True when ``after`` fails a whole shape check that ``before`` passed.

    Rounds and chamfers on nearby edges can each be valid on their own and still
    run into each other, so the solid crosses itself. :func:`is_valid` checks only
    the new faces and edges and cannot see that. The whole check is a few
    milliseconds even at 200 faces. A part that was already invalid is not
    blamed on the new feature.
    """
    if BRepCheck_Analyzer(after.shape, True, True).IsValid():
        return False
    return bool(BRepCheck_Analyzer(before.shape, True, True).IsValid())


def _same_surface(a: TopoDS_Face, b: TopoDS_Face) -> bool:
    """True when two faces could be merged: same plane, or same cylinder, or unknown."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
    from OCP.gp import gp_Lin

    # Without the face's bounds (False): only the surface is compared, and working out
    # the bounds of a face with many holes took about 7 ms each (D2662).
    sa, sb = BRepAdaptor_Surface(a, False), BRepAdaptor_Surface(b, False)
    ta, tb = sa.GetType(), sb.GetType()
    if ta != tb:
        return False
    tol = 1e-6
    if ta == GeomAbs_Plane:
        pa, pb = sa.Plane(), sb.Plane()
        return bool(pa.Axis().IsParallel(pb.Axis(), tol) and pa.Distance(pb.Location()) < tol)
    if ta == GeomAbs_Cylinder:
        ca, cb = sa.Cylinder(), sb.Cylinder()
        return bool(
            abs(ca.Radius() - cb.Radius()) < tol
            and ca.Axis().IsParallel(cb.Axis(), tol)
            and gp_Lin(ca.Axis()).Distance(cb.Location()) < tol
        )
    return True  # other surfaces: let the merge step decide


def needs_merge(before: NamedShape | None, after: NamedShape) -> bool:
    """True when merging faces and edges could change ``after`` (DECISIONS D77).

    A boolean makes new edges wherever it changes the part, so only new edges
    can border a merge: one whose two faces lie on the same surface, or one
    that continues another edge between the same two faces.
    """
    if before is None:
        return True
    new_edges = _new_of(before, after, TopAbs_EDGE)
    if not new_edges:
        return False
    edge_faces = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(after.shape, TopAbs_EDGE, TopAbs_FACE, edge_faces)
    vertex_edges = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(after.shape, TopAbs_VERTEX, TopAbs_EDGE, vertex_edges)

    def faces_of_edge(edge: TopoDS_Shape) -> list[TopoDS_Shape]:
        index = edge_faces.FindIndex(edge)
        return shape_list(edge_faces.FindFromIndex(index)) if index else []

    face_index = ShapeMap()
    TopExp.MapShapes_s(after.shape, TopAbs_FACE, face_index)

    def face_key(edge: TopoDS_Shape) -> set[int]:
        # Face identity by map index: hashing OCP handles does not identify shapes.
        return {face_index.FindIndex(f) for f in faces_of_edge(edge)}

    for edge in new_edges:
        faces = faces_of_edge(edge)
        distinct = [f for i, f in enumerate(faces) if not any(f.IsSame(g) for g in faces[:i])]
        if len(distinct) == 2 and _same_surface(TopoDS.Face(distinct[0]), TopoDS.Face(distinct[1])):
            return True
        key = face_key(edge)
        explorer = TopExp_Explorer(edge, TopAbs_VERTEX)
        while explorer.More():
            index = vertex_edges.FindIndex(explorer.Current())
            neighbours = shape_list(vertex_edges.FindFromIndex(index)) if index else []
            for other in neighbours:
                if not other.IsSame(edge) and face_key(other) == key:
                    return True
            explorer.Next()
    return False


#: How many touches the last checked result had, so the next feature, which starts
#: from that body, does not look for them again: ``(shape, count)``.
def new_touches(before: NamedShape | None, after: NamedShape) -> list[TopoDS_Shape]:
    """The zero thickness touches a feature made: those of ``after`` when there are
    more of them than ``before`` had, else none.

    Only the feature that makes a touch says so (D1057). And only the bodies the
    feature made or changed are looked at (D1070): the touches between bodies it left
    alone are the same before and after. Looking at the whole part after every feature
    cost 6 s a feature on a part with two blocks locked by teeth, whose hundreds of
    shared edges were checked again each time though nothing had touched them.
    """
    if before is None or (len(solids(before.shape)) < 2 and len(solids(after.shape)) < 2):
        found = zero_thickness(after.shape, 10**6)
        if before is not None and found and len(found) <= len(zero_thickness(before.shape, 10**6)):
            return []
        return found
    old, new = ShapeMap(), ShapeMap()
    for solid in solids(before.shape):
        old.Add(solid)
    for solid in solids(after.shape):
        new.Add(solid)
    made, gone = ShapeMap(), ShapeMap()
    for solid in solids(after.shape):
        if not old.Contains(solid):
            made.Add(solid)
    for solid in solids(before.shape):
        if not new.Contains(solid):
            gone.Add(solid)
    if made.Extent() == 0:
        return []
    found = zero_thickness(after.shape, 10**6, made)
    if not found:
        return []
    had = zero_thickness(before.shape, 10**6, gone) if gone.Extent() else []
    return found if len(found) > len(had) else []


def check_result(
    fid: str,
    name: str,
    before: NamedShape | None,
    after: NamedShape,
    thickness_param: str | None,
) -> list[Issue]:
    """Validity, zero thickness and body count checks after a solid feature."""
    if not is_valid(before, after):
        raise FeatureError(
            f"{name} produced invalid geometry. Change its values slightly or rebuild the sketch."
        )
    issues: list[Issue] = []
    fixes = (
        [
            Fix(
                "Add 0.01 mm",
                "add_to_param",
                {"feature": fid, "param": thickness_param, "delta": 0.01},
            )
        ]
        if thickness_param
        else []
    )
    # Only the feature that makes a touch says so (D1057). The warning used to be
    # repeated by every feature after it, twenty rows of the same words.
    touching = new_touches(before, after)[:20]
    if touching:
        highlight = []
        for sub in touching:
            label = (
                after.edge_name(TopoDS.Edge(sub))
                if sub.ShapeType() == TopAbs_EDGE
                else after.vertex_name(TopoDS.Vertex(sub))
            )
            if label is not None and label not in highlight:
                highlight.append(label)
        issues.append(
            Issue(
                FeatureState.WARNING,
                f"{name} makes bodies that touch only along an edge or at a point "
                "(zero thickness). Change a dimension so they overlap or separate.",
                fixes,
                highlight,
                code="zero_thickness",
            )
        )
    count_before = len(solids(before.shape)) if before else 0
    count_after = len(solids(after.shape))
    if count_after > max(count_before, 1):
        issues.append(
            Issue(
                FeatureState.WARNING,
                f"{name} created a separate body ({count_after} bodies now). "
                "Keep it, or undo and change the feature so it touches the part.",
                [Fix("Keep separate body", "dismiss", {"feature": fid})],
                code="separate_body",
            )
        )
    return issues


def combine(
    fid: str,
    name: str,
    body: NamedShape | None,
    tool: NamedShape,
    operation: str,
    *,
    pieces: bool = False,
    check_tools: bool = True,
) -> NamedShape:
    """Fuse ``tool`` into ``body`` or cut it away, with fuzzy tolerance and merged faces.

    With ``pieces`` a compound tool is passed to the kernel as its separate solids, so
    pieces that overlap each other (copies of an array) are fused with each other too:
    the kernel never intersects the pieces of one compound argument with each other.
    ``check_tools`` False leaves out the point check of each tool (D2619), for a
    feature that checks its own result with a message of its own (Modeled Thread).
    """
    parts = [right_side_out(p) for p in (solids(tool.shape) if pieces else []) or [tool.shape]]
    if body is None:
        if operation == "cut":
            raise FeatureError(f"{name} has nothing to cut. Add a boss feature first.")
        if len(parts) < 2:
            return _unify(tool, fid)
        first = NamedShape(parts[0], [])  # its names are carried with the tool's
        return combine(fid, name, first, NamedShape(compound(parts[1:]), tool.faces),
                       operation, pieces=True)  # fmt: skip
    if operation == "boss":
        reached = _reached(body.shape, tool.shape)
        if reached is not None:
            return _fuse_some(fid, name, body, tool, reached, pieces)
        apart = _beside(fid, body, tool, parts)
        if apart is not None:
            return apart
    if operation == "cut" and len(solids(body.shape)) > 1:
        return each_body(
            fid, body, parts,
            lambda sub: combine(fid, name, sub, tool, "cut",
                                pieces=pieces, check_tools=check_tools),
            f"{name} removes the whole part. Make the cut smaller.",
        )  # fmt: skip
    op: BRepAlgoAPI_BooleanOperation = (
        BRepAlgoAPI_Fuse() if operation == "boss" else BRepAlgoAPI_Cut()
    )
    args, tools = ShapeList(), ShapeList()
    args.Append(body.shape)
    for part in parts:
        tools.Append(part)
    op.SetArguments(args)
    op.SetTools(tools)
    op.SetFuzzyValue(FUZZY_TOLERANCE)
    op.SetRunParallel(True)
    op.SetToFillHistory(True)
    op.Build()
    if not op.IsDone():
        raise FeatureError(
            f"{name} failed: the kernel could not combine it with the part. "
            "Change its values slightly so faces do not almost touch."
        )
    names = carry(body.faces + tool.faces, op.History())
    result = NamedShape(op.Shape(), restrict(names, op.Shape(), fid))
    if operation == "cut" and not solids(result.shape):
        raise WholeBodyCutError(f"{name} removes the whole part. Make the cut smaller.")
    if not volume_sane(operation, body.shape, parts, result.shape):
        raise FeatureError(
            f"{name} failed: the kernel gave a result of the wrong size. "
            "Change its values slightly so faces do not almost touch."
        )
    if check_tools and not tools_kept(operation, body.shape, parts, result.shape):
        lost = (
            "left out the material it adds"
            if operation == "boss"
            else "left material where it cuts"
        )
        raise FeatureError(
            f"{name} failed: the kernel {lost}. "
            "Change its values slightly so faces do not almost touch."
        )
    if not needs_merge(body, result):
        return result
    merged = _unify(result, fid)
    if _LAST_VOLUME:
        _remember_volume(merged.shape, _LAST_VOLUME[0][1])  # merging keeps the volume
    return merged


#: Bodies with more faces than this skip the volume check after a boolean.
_SANITY_FACES = 100
#: The volume of the last boolean result, so the next feature, which usually starts
#: from that body, does not measure it again: ``(shape, volume)``.
_LAST_VOLUME: list[tuple[TopoDS_Shape, float]] = []


def _volume_cached(shape: TopoDS_Shape) -> float:
    for known, value in _LAST_VOLUME:
        if known.IsSame(shape):
            return value
    return volume_of(shape)


def _remember_volume(shape: TopoDS_Shape, value: float) -> None:
    _LAST_VOLUME[:] = [(shape, value)]


def volume_sane(
    operation: str, body: TopoDS_Shape, tools: Sequence[TopoDS_Shape], result: TopoDS_Shape
) -> bool:
    """True when a boolean's volume is possible (spec 2 section 19 item 4, D705).

    A boss ends between the larger of the body and the tools and their sum; a cut
    ends between the body less the tools and the body. A kernel boolean that loses
    or doubles material reports success, so this turns it into a feature error.
    The quick volume can be about 1 percent off on B-spline faces, so only larger
    errors count; inputs that are already inside out are not judged. Bodies with
    more than ``_SANITY_FACES`` faces are not measured, to keep long trees inside
    the rebuild budget (PLAN.md section 11, D705).
    """
    count = ShapeMap()
    TopExp.MapShapes_s(body, TopAbs_FACE, count)
    if count.Extent() > _SANITY_FACES:
        return True
    vb = _volume_cached(body)
    vt = [volume_of(t) for t in tools]
    vr = volume_of(result)
    _remember_volume(result, vr)
    if vb < 0 or any(v < 0 for v in vt):
        return True
    total = vb + sum(vt)
    slack = 0.01 * total + 1e-6
    if operation == "boss":
        return max([vb, *vt]) - slack <= vr <= total + slack
    return vb - sum(vt) - slack <= vr <= vb + slack


def each_body(
    fid: str,
    body: NamedShape,
    tools: Sequence[TopoDS_Shape],
    cut: Callable[[NamedShape], NamedShape],
    all_gone: str,
) -> NamedShape:
    """Cut the bodies of a part one at a time, and put the part together again (D1056).

    The kernel takes for granted that the solids it is given do not touch each other.
    The bodies of a part often do: a cover on its housing, an inlay in its pocket. A
    hole through such a cover, given to the kernel with the whole part, came back with
    its plug still there as a body of its own. So each body the tools can reach (their
    boxes overlap) is cut by ``cut`` alone; the others are kept as they are. A body
    that is cut away whole is left out; when none is left, ``all_gone`` is the error.
    """
    reach = Bnd_Box()
    for tool in tools:
        BRepBndLib.Add_s(tool, reach)
    reach.Enlarge(10 * FUZZY_TOLERANCE)
    shapes: list[TopoDS_Shape] = []
    faces: list[NamedFace] = []
    for piece in solids(body.shape):
        fmap = ShapeMap()
        TopExp.MapShapes_s(piece, TopAbs_FACE, fmap)
        own = [(n, f) for n, f in body.faces if fmap.Contains(f)]
        box = Bnd_Box()
        BRepBndLib.Add_s(piece, box)
        if box.IsOut(reach):
            shapes.append(piece)
            faces.extend(own)
            continue
        try:
            done = cut(NamedShape(piece, own))
        except WholeBodyCutError:
            continue
        shapes.extend(solids(done.shape))
        faces.extend(done.faces)
    if not shapes:
        raise FeatureError(all_gone)
    shape = compound(shapes)
    return NamedShape(shape, restrict(faces, shape, fid))


class WholeBodyCutError(FeatureError):
    """A cut that leaves nothing of the body it was made on."""


def _beside(
    fid: str, body: NamedShape, tool: NamedShape, parts: Sequence[TopoDS_Shape]
) -> NamedShape | None:
    """A boss that touches none of the bodies of a part of several bodies, put beside them
    as new bodies with no kernel call, or None when that is not the case (D1078).

    The fuse was run on the whole part all the same, to add the new body, and the
    kernel then joined bodies of the part that only touch each other: with two blocks
    locked by Interlock teeth in the part, a plain Extrude of a new block somewhere
    else made the two blocks one.
    """
    old = solids(body.shape)
    new = [s for part in parts for s in solids(part)]
    if len(old) < 2 or not new or reached_bodies(body.shape, tool.shape):
        return None
    shape = compound([*old, *new])
    return NamedShape(shape, restrict(body.faces + tool.faces, shape, fid))


def _reached(body: TopoDS_Shape, tool: TopoDS_Shape) -> list[int] | None:
    """Indexes of the bodies a boss tool meets, when it meets some but not all.

    None means fuse with the whole part as before: a one body part, a tool that
    meets every body, or a tool that meets none (a new separate body).
    """
    pieces = solids(body)
    if len(pieces) < 2:
        return None
    out = reached_bodies(body, tool)
    return out if 0 < len(out) < len(pieces) else None


def reached_bodies(body: TopoDS_Shape, tool: TopoDS_Shape) -> list[int]:
    """Indexes of the bodies of ``body`` that ``tool`` touches or enters."""
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape

    pieces = solids(body)
    reach = Bnd_Box()
    BRepBndLib.Add_s(tool, reach)
    reach.Enlarge(10 * FUZZY_TOLERANCE)
    out = []
    for i, piece in enumerate(pieces):
        box = Bnd_Box()
        BRepBndLib.Add_s(piece, box)
        if box.IsOut(reach):
            continue
        dist = BRepExtrema_DistShapeShape(piece, tool)
        if not dist.IsDone() or dist.Value() <= 10 * FUZZY_TOLERANCE:
            out.append(i)
    return out


def _fuse_some(
    fid: str, name: str, body: NamedShape, tool: NamedShape, reached: list[int], separate: bool
) -> NamedShape:
    """Fuse a boss into the bodies it meets and keep the other bodies as they are.

    Bodies left by Split share their cut face, so a fuse with the whole part would
    join them again (D620). The bodies keep their order in the part.
    """
    pieces = solids(body.shape)
    picked = [pieces[i] for i in reached]
    fmap = ShapeMap()
    for piece in picked:
        TopExp.MapShapes_s(piece, TopAbs_FACE, fmap)
    part = picked[0] if len(picked) == 1 else compound(picked)
    sub = NamedShape(part, [(n, f) for n, f in body.faces if fmap.Contains(f)])
    # The tool meets every body of ``sub``, so this fuses with all of them.
    fused = combine(fid, name, sub, tool, "boss", pieces=separate)
    shapes: list[TopoDS_Shape] = []
    for i, piece in enumerate(pieces):
        if i == reached[0]:
            shapes.extend(solids(fused.shape))
        elif i not in reached:
            shapes.append(piece)
    shape = compound(shapes)
    others = [(n, f) for n, f in body.faces if not fmap.Contains(f)]
    return NamedShape(shape, restrict(others + fused.faces, shape, fid))


def combine_or_keep(
    feature: Feature,
    body: NamedShape | None,
    tool: NamedShape,
    operation: str,
    ctx: BuildContext | None = None,
    issues: list[Issue] | None = None,
) -> NamedShape:
    """Combine like ``combine``, or keep a boss as a separate body when ``merge`` is off.

    With ``ctx`` and the feature's Bodies box set to Selected bodies, only the picked
    bodies are cut or joined (TR33, D697). Warnings about the picked bodies (one found
    by its position) go into ``issues``; they were dropped (audit D8 item 3, D746)."""
    if (
        ctx is not None
        and body is not None
        and feature.params.get("bodies_scope", "all") == "selected"
        and not (operation == "boss" and feature.params.get("merge", True) is False)
    ):
        from fdcad.core.features.bodies import scoped

        result, picked = scoped(
            feature, ctx, lambda part: combine(feature.id, feature.name, part, tool, operation)
        )
        if issues is not None:
            issues.extend(picked)
        return result
    if operation == "boss" and body is not None and feature.params.get("merge", True) is False:
        own = _unify(tool, feature.id)
        shape = compound([body.shape, own.shape])
        return NamedShape(shape, restrict(body.faces + own.faces, shape, feature.id))
    return combine(feature.id, feature.name, body, tool, operation)


def expected_issues(feature: Feature, issues: list[Issue]) -> list[Issue]:
    """Drop the separate body warning when the user turned merge result off."""
    if feature.params.get("merge", True) is not False:
        return issues
    return [i for i in issues if i.code != "separate_body"]


def profile_centre(faces: Sequence[TopoDS_Shape]) -> tuple[float, float, float]:
    """Area centre of the profile faces."""
    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(compound(faces), props)
    c = props.CentreOfMass()
    return (c.X(), c.Y(), c.Z())


def _unify(named: NamedShape, fid: str) -> NamedShape:
    """Merge faces that lie on the same surface, so the part has no needless seams."""
    from fdcad.core.unify import unify_faces

    shape, history = unify_faces(named.shape)
    names = carry(named.faces, history) if history is not None else list(named.faces)
    return NamedShape(shape, restrict(names, shape, fid))


def line_ends(edge: TopoDS_Shape) -> tuple[Vec3, Vec3] | None:
    """Start and end points of a straight edge, or None when the edge is curved."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GeomAbs import GeomAbs_Line

    curve = BRepAdaptor_Curve(TopoDS.Edge(edge))
    if curve.GetType() != GeomAbs_Line:
        return None
    a, b = curve.Value(curve.FirstParameter()), curve.Value(curve.LastParameter())
    if a.Distance(b) < 1e-9:
        return None
    return (a.X(), a.Y(), a.Z()), (b.X(), b.Y(), b.Z())


def common(fid: str, name: str, a: NamedShape, b: NamedShape) -> NamedShape:
    """The part of ``a`` inside ``b``, with fuzzy tolerance and names carried from both."""
    from fdcad.core.occ import BRepAlgoAPI_Common

    op = BRepAlgoAPI_Common()
    args, tools = ShapeList(), ShapeList()
    args.Append(a.shape)
    tools.Append(b.shape)
    op.SetArguments(args)
    op.SetTools(tools)
    op.SetFuzzyValue(FUZZY_TOLERANCE)
    op.SetRunParallel(True)
    op.SetToFillHistory(True)
    op.Build()
    if not op.IsDone():
        raise FeatureError(
            f"{name} failed: the kernel could not intersect the shapes. "
            "Change its values slightly so faces do not almost touch."
        )
    names = carry(a.faces + b.faces, op.History())
    return NamedShape(op.Shape(), restrict(names, op.Shape(), fid))


def extent_along(shape: TopoDS_Shape, direction: Vec3) -> tuple[float, float] | None:
    """Smallest and largest ``dot(p, direction)`` over the points of ``shape``.

    ``direction`` is a unit vector. None for an empty shape. The shape is turned
    so the direction is Z and an exact box is taken (no mesh is used).
    """
    from OCP.gp import gp_Ax3, gp_Dir, gp_Pnt
    from OCP.TopLoc import TopLoc_Location

    trsf = gp_Trsf()
    trsf.SetTransformation(gp_Ax3(gp_Pnt(0, 0, 0), gp_Dir(*direction)))
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape.Moved(TopLoc_Location(trsf)), box, False, False)
    if box.IsVoid():
        return None
    return float(box.CornerMin().Z()), float(box.CornerMax().Z())


def polygon_face(points: Sequence[Vec3]) -> TopoDS_Face:
    """A flat face through the corner points, in order."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCP.gp import gp_Pnt

    poly = BRepBuilderAPI_MakePolygon()
    for p in points:
        poly.Add(gp_Pnt(*p))
    poly.Close()
    return BRepBuilderAPI_MakeFace(poly.Wire(), True).Face()


def face_area(shapes: Sequence[TopoDS_Shape]) -> float:
    """Total area of the faces."""
    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(compound(shapes), props)
    return float(props.Mass())


def right_side_out(shape: TopoDS_Shape) -> TopoDS_Shape:
    """``shape`` with every inside out solid made again with its faces pointing out
    (D1049).

    The kernel can return a solid inside out (a face made thick, a swept thread). Its
    volume then reads below zero. Setting the solid's reversed flag makes the volume
    read right, and the kernel's own repair does no more than that, but a fuse or cut
    that gets such a solid inside a compound takes it for the room around it: the fuse
    adds nothing and still reports success. A head badge wrapped on a bike frame's head
    tube was lost that way. Here the solid is made again from its shells turned over,
    with no flag on it. A shape that is not a solid or a compound of solids, or has
    no inside out solid, comes back as it is.
    """
    from OCP.BRep import BRep_Builder
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeSolid
    from OCP.TopAbs import (
        TopAbs_COMPOUND,
        TopAbs_FORWARD,
        TopAbs_REVERSED,
        TopAbs_SHELL,
        TopAbs_SOLID,
    )
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS_Compound, TopoDS_Iterator

    def wrong(solid: TopoDS_Shape) -> bool:
        return bool(solid.Orientation() == TopAbs_REVERSED) or volume_of(solid) < 0

    def remade(solid: TopoDS_Shape, flip: bool) -> TopoDS_Shape | None:
        maker = BRepBuilderAPI_MakeSolid()
        explorer = TopExp_Explorer(solid.Oriented(TopAbs_FORWARD), TopAbs_SHELL)
        count = 0
        while explorer.More():
            shell = explorer.Current()
            maker.Add(TopoDS.Shell(shell.Reversed() if flip else shell))
            count += 1
            explorer.Next()
        if count == 0 or not maker.IsDone():
            return None
        return maker.Solid()

    def turned(solid: TopoDS_Shape) -> TopoDS_Shape:
        for flip in (False, True):
            made = remade(solid, flip)
            if made is not None and volume_of(made) > 0:
                return made
        return solid

    kind = shape.ShapeType()
    if kind == TopAbs_SOLID:
        return turned(shape) if wrong(shape) else shape
    if kind != TopAbs_COMPOUND:
        return shape
    parts = solids(shape)
    if not parts or not any(wrong(p) for p in parts):
        return shape
    out = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(out)
    children = TopoDS_Iterator(shape)
    while children.More():
        builder.Add(out, right_side_out(children.Value()))
        children.Next()
    return out


#: Volumes measured during the current rebuild, newest last, or None outside one (D2661).
_MEASURED: ContextVar[list[tuple[TopoDS_Shape, float]] | None] = ContextVar(
    "fdcad_measured_volumes", default=None
)
#: How many measured volumes a rebuild keeps: the shapes of one feature.
_MEASURED_KEEP = 16


@contextmanager
def measured_volumes() -> Iterator[None]:
    """Within this block ``volume_of`` measures each shape once (D2661).

    A thread's solid was measured four times in one feature (turned right side out
    twice, the boolean's size check, the thread cut check), about 0.1 s each on its
    spline faces. The rebuild engine opens the block around a rebuild; the shapes it
    keeps are let go when the block ends, and other threads never see them.
    """
    token = _MEASURED.set([])
    try:
        yield
    finally:
        _MEASURED.reset(token)


def volume_of(shape: TopoDS_Shape) -> float:
    """Volume of a solid or compound of solids."""
    known = _MEASURED.get()
    if known is not None:
        for kept, value in known:
            # Same shape, place and orientation: an inside out copy has the opposite sign.
            if kept.IsEqual(shape):
                return value
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    value = float(props.Mass())
    _note_volume(shape, value)
    return value


def _note_volume(shape: TopoDS_Shape, value: float) -> None:
    """Keep ``value`` as the volume of ``shape`` for the rest of the rebuild, if one runs.

    A compound that holds one solid (the kernel's boolean result) has exactly the
    volume of that solid, to the last bit, so the solid is kept as well: the next
    feature often measures it as a body of the part.
    """
    known = _MEASURED.get()
    if known is None or shape.IsNull():  # an empty answer (D1086 retries) has no type
        return
    from OCP.TopAbs import TopAbs_COMPOUND
    from OCP.TopoDS import TopoDS_Iterator

    # Copies of the handle: a caller that moves or turns its own shape later does not
    # change the kept one.
    known.append((shape.Oriented(shape.Orientation()), value))
    if shape.ShapeType() == TopAbs_COMPOUND:
        children = TopoDS_Iterator(shape)
        child = children.Value() if children.More() else None
        if child is not None and child.ShapeType() == TopAbs_SOLID:
            children.Next()
            if not children.More():
                only = solids(shape)[0]  # as an explorer gives it: place and turn applied
                known.append((only, value))
    del known[:-_MEASURED_KEEP]


def precise_volume(shape: TopoDS_Shape) -> float:
    """Volume to a relative error of 1e-6, for values shown to the user.

    ``volume_of`` is quick but can be about 1% off on B-spline faces (for
    example a round body after a non-uniform Scale or a deformation).
    """
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props, 1e-6)
    return float(props.Mass())
