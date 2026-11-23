"""The sheet model shared by the sheet metal features (PHASE5_SPEC P5.2 to P5.5, D333).

A sheet metal part is a tree of flat walls joined by bends. Each wall is a
plate of the sheet thickness in its own local frame: the sheet lies between
z = 0 and z = thickness. A bend joins a straight line on its parent wall's
z = 0 face to the start of its child wall. The same data builds the folded
part and the flat pattern, so the flat length is exact for the bend
allowance of each bend (P5.5 item 2).

Bend geometry, in the parent's local frame:

- ``p0`` is where the bend starts on the parent's z = 0 face, ``w`` the unit
  direction across the bend (away from the parent), ``e = (w.y, -w.x)`` the
  direction along it, and ``length`` how far it runs along ``e``.
- ``up`` is +1 when the bend turns toward +z (the z = thickness face is then
  on the inside) and -1 when it turns toward -z.
- Folded, the child starts where ``p0`` lands after turning by ``angle`` about
  the bend axis. Flat, it starts at ``p0 + w * allowance``.

The child's local frame has x along ``e``, y away from the bend and z the
parent's z turned with it, so the same face stays z = 0 through every bend.

Face roles: walls ``<wall>/bottom`` (z = 0), ``<wall>/top``, ``<wall>/end``,
``<wall>/start``, ``<wall>/side1``, ``<wall>/side2``; bends
``<bend>/inner``, ``<bend>/outer``, ``<bend>/side1``, ``<bend>/side2``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.BRepGProp import BRepGProp
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeRevol
from OCP.gp import gp_Ax1, gp_Ax2, gp_Ax3, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_EDGE, TopAbs_IN
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape

from fdcad.core.features.base import FeatureError, FeatureResult, Vec3
from fdcad.core.features.solids import FUZZY_TOLERANCE, solids, transform
from fdcad.core.naming.names import NamedFace, NamedShape, carry, centroid, faces_of, restrict
from fdcad.core.occ import (
    BRepAlgoAPI_BooleanOperation,
    BRepAlgoAPI_Common,
    BRepAlgoAPI_Cut,
    BRepAlgoAPI_Fuse,
    ShapeList,
    shape_list,
)

Vec2 = tuple[float, float]


def along(w: Vec2) -> Vec2:
    """The direction along a bend whose across direction is ``w``."""
    return (w[1], -w[0])


@dataclass
class Wall:
    """A flat plate in its own frame: ``plate`` minus ``cuts`` (both in local coordinates).

    ``folded_cuts`` and then ``adds`` change the folded part only (forming tools, D546).
    """

    wid: str
    owner: str
    plate: NamedShape
    cuts: list[NamedShape] = field(default_factory=list)
    adds: list[NamedShape] = field(default_factory=list)
    folded_cuts: list[NamedShape] = field(default_factory=list)


@dataclass(frozen=True)
class Bend:
    """A bend from ``parent`` to ``child`` (see the module docstring)."""

    bid: str
    owner: str
    parent: str
    child: str
    p0: Vec2
    w: Vec2
    length: float
    up: int
    radius: float
    angle: float
    allowance: float
    #: Cut outlines on the bend strip, in the strip's flat frame (Fold, D541).
    cuts: tuple[NamedShape, ...] = ()


#: A cosmetic line on a wall's z = thickness face: wall id, ends in its frame, title.
Mark = tuple[str, Vec2, Vec2, str]


@dataclass
class SheetModel:
    """Walls and bends of a sheet metal part. ``frame`` places the root wall."""

    thickness: float
    root: str
    frame: gp_Trsf
    walls: dict[str, Wall] = field(default_factory=dict)
    bends: dict[str, Bend] = field(default_factory=dict)
    #: Bends shown flat in the folded part (Unfold, D541).
    unfolded: set[str] = field(default_factory=set)
    #: Cosmetic lines (Cross Break, D539).
    marks: list[Mark] = field(default_factory=list)
    #: Cuts of the flat pattern only: (wall id, solid in that wall's flat frame), such as
    #: the cut out a gusset leaves (TR12, D700).
    flat_cuts: list[tuple[str, NamedShape]] = field(default_factory=list)
    #: Folded part only, across walls and bends: cuts, then adds, each (wall id, solid in
    #: that wall's folded frame). A gusset presses its shape in and adds its rib (D700).
    part_cuts: list[tuple[str, NamedShape]] = field(default_factory=list)
    part_adds: list[tuple[str, NamedShape]] = field(default_factory=list)
    #: Solid bodies carried beside the sheet in the folded part, such as the solid that
    #: Convert to Sheet Metal keeps (TR171, D2307); never in the flat pattern.
    kept: list[NamedShape] = field(default_factory=list)
    #: The Sheet Metal folder this sheet belongs to: a part may hold several sheets,
    #: one per folder (TR281, D2312); empty for a sheet built without one.
    folder: str = ""

    def copy(self) -> SheetModel:
        """A copy that a later feature may change without touching this one."""
        walls = {
            k: replace(w, cuts=list(w.cuts), adds=list(w.adds), folded_cuts=list(w.folded_cuts))
            for k, w in self.walls.items()
        }
        return SheetModel(
            self.thickness,
            self.root,
            self.frame.Multiplied(gp_Trsf()),
            walls,
            dict(self.bends),
            set(self.unfolded),
            list(self.marks),
            list(self.flat_cuts),
            list(self.part_cuts),
            list(self.part_adds),
            list(self.kept),
            self.folder,
        )

    def children(self, wid: str) -> list[Bend]:
        """Bends that start on wall ``wid``."""
        return [b for b in self.bends.values() if b.parent == wid]

    def parent_bend(self, wid: str) -> Bend | None:
        """The bend that leads to wall ``wid`` (None for the root)."""
        for bend in self.bends.values():
            if bend.child == wid:
                return bend
        return None

    def piece(self, wid: str) -> NamedShape:
        """Wall ``wid`` with its cuts, in local coordinates."""
        wall = self.walls[wid]
        return cut_all(wall.plate, wall.cuts, wall.owner)

    def add_material(self, wid: str, extra: list[NamedShape]) -> None:
        """Join ``extra`` to wall ``wid`` after the cuts made so far (tabs, D533 and D536)."""
        wall = self.walls[wid]
        wall.plate = fuse_all(wall.owner, wall.owner, [self.piece(wid), *extra])
        wall.cuts = []

    def folded_piece(self, wid: str) -> NamedShape:
        """Wall ``wid`` as it is in the folded part: with its forms (D546)."""
        wall = self.walls[wid]
        base = cut_all(wall.plate, [*wall.cuts, *wall.folded_cuts], wall.owner)
        if not wall.adds:
            return base
        return fuse_all(wall.owner, wall.owner, [base, *wall.adds])

    def placements(self, flat: bool) -> dict[str, gp_Trsf]:
        """Local to world transform of every wall, folded or flat."""
        out = {self.root: self.frame.Multiplied(gp_Trsf())}
        todo = [self.root]
        while todo:
            parent = todo.pop(0)
            for bend in self.bends.values():
                if bend.parent != parent:
                    continue
                lay = flat or bend.bid in self.unfolded
                move = flat_child(bend) if lay else folded_child(bend, self.thickness)
                out[bend.child] = out[parent].Multiplied(move)
                todo.append(bend.child)
        return out

    def pieces(self, flat: bool) -> list[tuple[str, NamedShape]]:
        """Every wall and bend as a placed solid, with its owner feature id."""
        places = self.placements(flat)
        out: list[tuple[str, NamedShape]] = []
        for wid, wall in self.walls.items():
            if wid in places:
                local = self.piece(wid) if flat else self.folded_piece(wid)
                out.append((wall.owner, transform(local, places[wid])))
        for bend in self.bends.values():
            if bend.parent not in places:
                continue
            if flat or bend.bid in self.unfolded:
                local = flat_bend(bend, self.thickness)
            else:
                local = folded_bend(bend, self.thickness)
            out.append((bend.owner, transform(local, places[bend.parent])))
        return out

    def build(self, fid: str, name: str, flat: bool = False, merge: bool = True) -> NamedShape:
        """The whole part as one solid, folded or flat. ``merge`` False keeps the faces of
        walls and bends apart (Merge Faces off, TR76, D1105)."""
        part = fuse_all(fid, name, [p for _o, p in self.pieces(flat)], merge)
        if flat and self.flat_cuts:
            places = self.placements(True)
            holes = [transform(c, places[w]) for w, c in self.flat_cuts if w in places]
            part = cut_all(part, holes, fid, merge)
        if not flat and (self.part_cuts or self.part_adds):
            places = self.placements(False)
            cuts = [transform(c, places[w]) for w, c in self.part_cuts if w in places]
            adds = [transform(a, places[w]) for w, a in self.part_adds if w in places]
            if cuts:
                part = cut_all(part, cuts, fid)
            if adds:
                part = fuse_all(fid, name, [part, *adds])
        if not flat and self.kept:  # TR171 (D2307): separate bodies, not fused
            from fdcad.core.features.bodies import join

            joined = join([part, *self.kept], fid)
            if joined is not None:
                part = joined
        return part

    def bend_lines(self) -> list[tuple[Vec3, Vec3, Bend]]:
        """Centre line of every bend on the flat pattern's top face, in world coordinates."""
        places = self.placements(True)
        t = self.thickness
        out = []
        for bend in self.bends.values():
            if bend.parent not in places:
                continue
            e, w = along(bend.w), bend.w
            half = bend.allowance / 2
            a = (bend.p0[0] + w[0] * half, bend.p0[1] + w[1] * half, t)
            b = (a[0] + e[0] * bend.length, a[1] + e[1] * bend.length, t)
            trsf = places[bend.parent]
            out.append((_apply(trsf, a), _apply(trsf, b), bend))
        return out

    def mark_lines(self, flat: bool) -> list[tuple[Vec3, Vec3, str]]:
        """Cosmetic lines (Cross Break) in world coordinates, folded or flat."""
        places = self.placements(flat)
        t = self.thickness
        out = []
        for wid, a, b, title in self.marks:
            if wid in places:
                trsf = places[wid]
                out.append((_apply(trsf, (a[0], a[1], t)), _apply(trsf, (b[0], b[1], t)), title))
        return out


@dataclass
class SheetResult(FeatureResult):
    """Result of a sheet metal feature: the part plus the sheet model it was built from."""

    sheet: SheetModel | None = None
    #: This sheet's own solid, without the part's other bodies (TR281, D2312).
    own: NamedShape | None = None


# Transforms ---------------------------------------------------------------------


def _apply(trsf: gp_Trsf, p: Vec3) -> Vec3:
    q = gp_Pnt(*p).Transformed(trsf)
    return (q.X(), q.Y(), q.Z())


def apply(trsf: gp_Trsf, p: Vec3) -> Vec3:
    """``p`` moved by ``trsf``."""
    return _apply(trsf, p)


def basis(origin: Vec2, w: Vec2) -> gp_Trsf:
    """Maps coordinates (x along ``along(w)``, y along ``w``, z) at ``origin`` to the parent's."""
    e = along(w)
    ax = gp_Ax3(gp_Pnt(origin[0], origin[1], 0.0), gp_Dir(0, 0, 1), gp_Dir(e[0], e[1], 0.0))
    trsf = gp_Trsf()
    trsf.SetTransformation(ax)
    return trsf.Inverted()


def frame(origin: Vec3, x: Vec3, z: Vec3) -> gp_Trsf:
    """Local to world transform of a frame with origin, x axis and z axis."""
    trsf = gp_Trsf()
    trsf.SetTransformation(gp_Ax3(gp_Pnt(*origin), gp_Dir(*z), gp_Dir(*x)))
    return trsf.Inverted()


def bend_centre(bend: Bend, thickness: float) -> Vec3:
    """The bend axis point at ``p0``, in the parent's frame."""
    z = thickness + bend.radius if bend.up > 0 else -bend.radius
    return (bend.p0[0], bend.p0[1], z)


def _axis(bend: Bend, thickness: float) -> gp_Ax1:
    e = along(bend.w)
    return gp_Ax1(gp_Pnt(*bend_centre(bend, thickness)), gp_Dir(e[0] * bend.up, e[1] * bend.up, 0))


def folded_child(bend: Bend, thickness: float) -> gp_Trsf:
    """Child frame to parent frame, folded."""
    turn = gp_Trsf()
    turn.SetRotation(_axis(bend, thickness), bend.angle)
    return turn.Multiplied(basis(bend.p0, bend.w))


def flat_child(bend: Bend) -> gp_Trsf:
    """Child frame to parent frame, flat."""
    w = bend.w
    origin = (bend.p0[0] + w[0] * bend.allowance, bend.p0[1] + w[1] * bend.allowance)
    return basis(origin, w)


# Solids ---------------------------------------------------------------------------


def _name_box(prefix: str, shape: TopoDS_Shape, lo: Vec3, hi: Vec3) -> NamedShape:
    """Name the six faces of an axis aligned box by where their centres lie."""
    names: list[NamedFace] = []
    roles = (("side1", "side2"), ("start", "end"), ("bottom", "top"))
    for face in faces_of(shape):
        c = centroid(face)
        for axis in range(3):
            if abs(c[axis] - lo[axis]) < 1e-9:
                names.append((f"{prefix}/{roles[axis][0]}", face))
            elif abs(c[axis] - hi[axis]) < 1e-9:
                names.append((f"{prefix}/{roles[axis][1]}", face))
    return NamedShape(shape, names)


def box(prefix: str, lo: Vec3, hi: Vec3) -> NamedShape:
    """An axis aligned box with named faces (see the module docstring)."""
    if any(h - lo_ <= 1e-9 for lo_, h in zip(lo, hi, strict=True)):
        raise FeatureError(f"{prefix}: a wall or cut has no size. Check the lengths.")
    shape = BRepPrimAPI_MakeBox(gp_Pnt(*lo), gp_Pnt(*hi)).Shape()
    return _name_box(prefix, shape, lo, hi)


def oriented_box(prefix: str, origin: Vec2, w: Vec2, lo: Vec3, hi: Vec3) -> NamedShape:
    """A box given in the (along, across, z) frame at ``origin``, placed in local coordinates."""
    return transform(box(prefix, lo, hi), basis(origin, w))


def rounded_slot(
    prefix: str, origin: Vec2, w: Vec2, x0: float, x1: float, y0: float, y1: float, z: float
) -> NamedShape:
    """An oriented box from ``y0`` to ``y1`` whose ``y0`` end is a half round (obround relief)."""
    width = x1 - x0
    radius = width / 2
    body = box(prefix, (x0, y0 + radius, -z), (x1, y1, 2 * z))
    axis = gp_Ax2(gp_Pnt(x0 + radius, y0 + radius, -z), gp_Dir(0, 0, 1))
    cyl = BRepPrimAPI_MakeCylinder(axis, radius, 3 * z).Shape()
    round_end = NamedShape(cyl, [(f"{prefix}/round", f) for f in faces_of(cyl)])
    joined = fuse_all(prefix, prefix, [body, round_end])
    return transform(joined, basis(origin, w))


def folded_bend(bend: Bend, thickness: float) -> NamedShape:
    """The bend as a solid, folded, in the parent's frame."""
    e = along(bend.w)
    p, t, length = bend.p0, thickness, bend.length
    corners = [
        (p[0], p[1], 0.0),
        (p[0] + e[0] * length, p[1] + e[1] * length, 0.0),
        (p[0] + e[0] * length, p[1] + e[1] * length, t),
        (p[0], p[1], t),
    ]
    poly = BRepBuilderAPI_MakePolygon()
    for c in corners:
        poly.Add(gp_Pnt(*c))
    poly.Close()
    face = BRepBuilderAPI_MakeFace(poly.Wire(), True).Face()
    maker = BRepPrimAPI_MakeRevol(face, _axis(bend, thickness), bend.angle)
    maker.Build()
    if not maker.IsDone():
        raise FeatureError(f"{bend.bid}: the bend could not be made. Check the radius and angle.")
    low, high = ("outer", "inner") if bend.up > 0 else ("inner", "outer")
    names: list[NamedFace] = []
    explorer = TopExp_Explorer(face, TopAbs_EDGE)
    while explorer.More():
        edge = explorer.Current()
        explorer.Next()
        mid = edge_centre(edge)
        along_edge = (mid[0] - p[0]) * e[0] + (mid[1] - p[1]) * e[1]
        if abs(mid[2]) < 1e-9:
            role = low
        elif abs(mid[2] - t) < 1e-9:
            role = high
        else:
            role = "side1" if along_edge < length / 2 else "side2"
        for made in shape_list(maker.Generated(edge)):
            names.append((f"{bend.bid}/{role}", TopoDS.Face(made)))
    names.append((f"{bend.bid}/start", TopoDS.Face(maker.FirstShape())))
    names.append((f"{bend.bid}/end", TopoDS.Face(maker.LastShape())))
    solid = NamedShape(maker.Shape(), restrict(names, maker.Shape(), bend.bid))
    if bend.cuts:
        from fdcad.core.features.sheetmetal.wrap import wrapped_cuts

        solid = cut_all(solid, wrapped_cuts(bend, thickness), bend.owner)
    return solid


def edge_centre(edge: TopoDS_Shape) -> Vec3:
    """Centre of length of an edge."""
    props = GProp_GProps()
    BRepGProp.LinearProperties_s(edge, props)
    c = props.CentreOfMass()
    return (c.X(), c.Y(), c.Z())


def flat_bend(bend: Bend, thickness: float) -> NamedShape:
    """The bend's flat strip, in the parent's frame."""
    low, high = ("outer", "inner") if bend.up > 0 else ("inner", "outer")
    shape = box(bend.bid, (0.0, 0.0, 0.0), (bend.length, bend.allowance, thickness))
    rename = {"bottom": low, "top": high}
    names = []
    for n, f in shape.faces:
        role = n.rsplit("/", 1)[1]
        names.append((f"{bend.bid}/{rename.get(role, role)}", f))
    strip = cut_all(NamedShape(shape.shape, names), list(bend.cuts), bend.owner)
    return transform(strip, basis(bend.p0, bend.w))


def _boolean(
    op: BRepAlgoAPI_BooleanOperation, first: NamedShape, others: list[NamedShape]
) -> tuple[TopoDS_Shape, list[NamedFace]]:
    args, tools = ShapeList(), ShapeList()
    args.Append(first.shape)
    for other in others:
        tools.Append(other.shape)
    op.SetArguments(args)
    op.SetTools(tools)
    op.SetFuzzyValue(FUZZY_TOLERANCE)
    op.SetToFillHistory(True)
    op.Build()
    if not op.IsDone():
        raise FeatureError("The sheet could not be built. Change the values slightly.")
    faces = first.faces + [nf for o in others for nf in o.faces]
    return op.Shape(), carry(faces, op.History())


def unify(named: NamedShape, fid: str) -> NamedShape:
    """Merge faces on the same surface so the part has no needless seams."""
    from fdcad.core.unify import unify_faces

    shape, history = unify_faces(named.shape)
    names = carry(named.faces, history) if history is not None else list(named.faces)
    return NamedShape(shape, restrict(names, shape, fid))


def fuse_all(fid: str, name: str, pieces: list[NamedShape], merge: bool = True) -> NamedShape:
    """Fuse every piece in one boolean (CLAUDE.md 5A item 5). ``merge`` joins faces on
    the same surface."""
    if not pieces:
        raise FeatureError(
            f"{name}: the sheet has no walls. Edit the Base Flange so it makes a wall."
        )
    if len(pieces) == 1:
        return pieces[0]
    shape, names = _boolean(BRepAlgoAPI_Fuse(), pieces[0], pieces[1:])
    named = NamedShape(shape, restrict(names, shape, fid))
    return unify(named, fid) if merge else named


def cut_all(plate: NamedShape, cuts: list[NamedShape], fid: str, merge: bool = True) -> NamedShape:
    """``plate`` minus every cut, in one boolean."""
    if not cuts:
        return plate
    shape, names = _boolean(BRepAlgoAPI_Cut(), plate, cuts)
    if not solids(shape):
        raise FeatureError(f"{fid}: the cuts remove a whole wall. Make them smaller.")
    named = NamedShape(shape, restrict(names, shape, fid))
    return unify(named, fid) if merge else named


def common_with(fid: str, a: NamedShape, b: NamedShape) -> NamedShape:
    """The part of ``a`` inside ``b``."""
    shape, names = _boolean(BRepAlgoAPI_Common(), a, [b])
    return NamedShape(shape, restrict(names, shape, fid))


def volume(shape: TopoDS_Shape) -> float:
    """Volume of a solid in cubic mm."""
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    return float(props.Mass())


def inside(shape: TopoDS_Shape, p: Vec3) -> bool:
    """True when ``p`` is inside the solid."""
    classifier = BRepClass3d_SolidClassifier(shape, gp_Pnt(*p), 1e-7)
    return bool(classifier.State() == TopAbs_IN)


def unit2(v: Vec2) -> Vec2:
    """``v`` scaled to length one."""
    n = math.hypot(v[0], v[1])
    if n < 1e-12:
        raise FeatureError("A direction has no length. Pick two different points.")
    return (v[0] / n, v[1] / n)


def translate(named: NamedShape, v: Vec3) -> NamedShape:
    """Move a named shape by ``v``."""
    trsf = gp_Trsf()
    trsf.SetTranslation(gp_Vec(*v))
    return transform(named, trsf)


def face_shapes(named: NamedShape) -> list[TopoDS_Face]:
    """The faces of a named shape, in a stable order."""
    return faces_of(named.shape)
