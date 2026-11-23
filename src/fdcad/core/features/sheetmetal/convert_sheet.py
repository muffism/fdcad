"""Convert to Sheet Metal (PHASE5_SPEC P5.6, DECISIONS D537) and its shared builder.

Type ``convert_sheet``. Params: ``gap`` (bend corners and rips, default 0.1 mm in
the panel), ``keep_body`` (keep the solid beside the sheet, TR171, D2307) and
``rip_type`` ("overlap" default, "underlap", "open" or "butt", see ``_rips``).
Refs: ``face`` (the fixed flat face), ``bends`` (straight edges between flat faces),
``sheet_metal``.

The solid's faces become the outer faces of the sheet; the material goes inward.

Face roles: walls ``<fid>/face<i>/<role>`` (``bottom`` is the solid's face, ``top``
the inside, ``side`` the cut edges), bends ``<fid>/bend<i>/<role>``, trims
``<fid>/trim<i>p`` and ``<fid>/trim<i>c``, rips ``<fid>/rip<i>``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.GeomAbs import GeomAbs_Plane
from OCP.gp import gp_Trsf, gp_Vec
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Face

from fdcad.core.document.model import Feature
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
from fdcad.core.features.lookup import resolve_edge, resolve_face
from fdcad.core.features.sheetmetal.common import latest_sheet, value
from fdcad.core.features.sheetmetal.locate import face_normal
from fdcad.core.features.sheetmetal.model import (
    Bend,
    SheetModel,
    SheetResult,
    Vec2,
    Wall,
    along,
    apply,
    frame,
    inside,
    oriented_box,
    unit2,
)
from fdcad.core.features.sheetmetal.params import BendRule, bend_allowance, sheet_defaults
from fdcad.core.features.solids import line_ends, transform
from fdcad.core.naming.names import NamedShape, centroid, faces_of
from fdcad.core.occ import ShapeListMap, shape_list
from fdcad.core.units import Kind

_TOL = 1e-5
#: How the walls meet at a rip (TR171, D2307).
RIP_TYPES = ("overlap", "underlap", "open", "butt")


@dataclass
class _Link:
    """A bend from face ``parent`` to face ``child`` along ``edge``."""

    parent: int
    child: int
    edge: TopoDS_Edge


def _flat(face: TopoDS_Face) -> bool:
    return bool(BRepAdaptor_Surface(face).GetType() == GeomAbs_Plane)


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


class Solid:
    """Faces of a solid with the faces on each side of every edge."""

    def __init__(self, shape: object) -> None:
        self.shape = shape
        self.faces: list[TopoDS_Face] = faces_of(shape)
        self.edge_faces = ShapeListMap()
        TopExp.MapShapesAndAncestors_s(shape, TopAbs_EDGE, TopAbs_FACE, self.edge_faces)

    def index(self, face: TopoDS_Face) -> int:
        """Index of ``face`` in ``faces``."""
        for i, f in enumerate(self.faces):
            if f.IsSame(face):
                return i
        raise FeatureError("The picked face is not on the part. Pick the face again.")

    def sides(self, edge: TopoDS_Edge) -> list[int]:
        """Indices of the faces on each side of ``edge``."""
        if not self.edge_faces.Contains(edge):
            return []
        out: list[int] = []
        for f in shape_list(self.edge_faces.FindFromKey(edge)):
            i = self.index(TopoDS.Face(f))
            if i not in out:
                out.append(i)
        return out

    def edges(self) -> list[TopoDS_Edge]:
        """Every edge of the solid."""
        return [
            TopoDS.Edge(self.edge_faces.FindKey(i)) for i in range(1, self.edge_faces.Extent() + 1)
        ]


def tree(
    solid: Solid, fixed: int, bends: list[TopoDS_Edge], owner: str
) -> tuple[list[int], list[_Link]]:
    """Faces reached from ``fixed`` across bend edges, in order, and the bend links."""
    order = [fixed]
    links: list[_Link] = []
    left = list(bends)
    grew = True
    while grew:
        grew = False
        for edge in list(left):
            sides = solid.sides(edge)
            if len(sides) != 2:
                raise FeatureError(
                    f"{owner}: a bend edge is not between two faces. "
                    "Pick edges where two picked faces meet."
                )
            a, b = sides
            if a in order and b in order:
                raise FeatureError(
                    f"{owner}: the bend edges close a loop. Leave one of them out; "
                    "it becomes a rip."
                )
            if a in order or b in order:
                parent, child = (a, b) if a in order else (b, a)
                order.append(child)
                links.append(_Link(parent, child, edge))
                left.remove(edge)
                grew = True
    if left:
        raise FeatureError(
            f"{owner}: some bend edges are not joined to the fixed face. Pick bend edges that "
            "link every wall to the fixed face."
        )
    for i in order:
        if not _flat(solid.faces[i]):
            raise FeatureError(
                f"{owner}: a face to convert is curved. Only flat faces convert. "
                "Pick flat faces only."
            )
    return order, links


def _plate(
    prefix: str, face: TopoDS_Face, place: gp_Trsf, thickness: float, owner: str
) -> NamedShape:
    """The face moved into a wall frame and thickened by ``thickness`` along +z."""
    moved = TopoDS.Face(BRepBuilderAPI_Transform(face, place.Inverted(), True).Shape())
    if abs(centroid(moved)[2]) > 1e-4:
        raise FeatureError(f"{owner}: a wall does not line up with its bend. Check the bend edges.")
    shape = BRepPrimAPI_MakePrism(moved, gp_Vec(0, 0, thickness)).Shape()
    names = []
    for f in faces_of(shape):
        z = centroid(f)[2]
        role = "bottom" if abs(z) < 1e-7 else "top" if abs(z - thickness) < 1e-7 else "side"
        names.append((f"{prefix}/{role}", f))
    return NamedShape(shape, names)


def convert(
    fid: str,
    solid: Solid,
    fixed: int,
    bends: list[TopoDS_Edge],
    thickness: float,
    rule: BendRule,
    gap: float,
    owner: str,
    rip_type: str = "overlap",
) -> SheetModel:
    """Build the sheet model of a solid's faces (D537)."""
    order, links = tree(solid, fixed, bends, owner)
    t = thickness
    wid_of = {face: f"{fid}/face{k}" for k, face in enumerate(order)}
    f0 = solid.faces[fixed]
    n0 = face_normal(f0)
    c0 = centroid(f0)
    ref = next(e for e in solid.edges() if fixed in solid.sides(e) and line_ends(e) is not None)
    ends = line_ends(ref)
    assert ends is not None
    x = unit3(_sub(ends[1], ends[0]))
    model = SheetModel(t, wid_of[fixed], frame(c0, x, (-n0[0], -n0[1], -n0[2])))
    model.walls[model.root] = Wall(model.root, fid, _plate(model.root, f0, model.frame, t, owner))
    setbacks: dict[int, float] = {}
    plans: list[tuple[_Link, int, float]] = []  # link, bend direction, angle
    for k, link in enumerate(links):
        n_p, n_c = face_normal(solid.faces[link.parent]), face_normal(solid.faces[link.child])
        angle = math.acos(max(-1.0, min(1.0, _dot(n_p, n_c))))
        if angle < 1e-6 or angle > math.pi - 1e-6:
            raise FeatureError(
                f"{owner}: bend edge {k + 1} joins faces that do not form a corner. "
                "Pick an edge where two walls meet at an angle."
            )
        child_c = centroid(solid.faces[link.child])
        convex = _dot(_sub(child_c, centroid(solid.faces[link.parent])), n_p) < 0
        layer = rule.radius + t if convex else rule.radius
        setbacks[k] = layer * math.tan(angle / 2)
        plans.append((link, 1 if convex else -1, angle))
    # Shorten bends that share a corner with another bend edge.
    ends_of = {k: line_ends(link.edge) for k, link in enumerate(links)}
    for k in range(len(links)):
        if ends_of[k] is None:
            raise FeatureError(
                f"{owner}: bend edge {k + 1} is not straight. Pick straight edges only."
            )
    for k, (link, up, angle) in enumerate(plans):
        places = model.placements(False)
        place = places[wid_of[link.parent]]
        inv = place.Inverted()
        ea, eb = ends_of[k]  # type: ignore[misc]
        a3, b3 = apply(inv, ea), apply(inv, eb)
        if abs(a3[2]) > 1e-4 or abs(b3[2]) > 1e-4:
            raise FeatureError(
                f"{owner}: bend edge {k + 1} is not on the outer face of its wall. "
                "Pick the edge on the outside of the corner."
            )
        a, b = (a3[0], a3[1]), (b3[0], b3[1])
        d = unit2((b[0] - a[0], b[1] - a[1]))
        piece = model.piece(wid_of[link.parent])
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        w: Vec2 = (d[1], -d[0])
        probe = (mid[0] - w[0] * 1e-3, mid[1] - w[1] * 1e-3, t / 2)
        if not inside(piece.shape, probe):
            w = (-w[0], -w[1])
        e = along(w)
        if a[0] * e[0] + a[1] * e[1] > b[0] * e[0] + b[1] * e[1]:
            a, b = b, a
            ea, eb = eb, ea
        cut = [0.0, 0.0]
        for j, other in ends_of.items():
            if j == k or other is None:
                continue
            for p in other:
                for side, q in enumerate((ea, eb)):
                    if math.dist(p, q) < 1e-5:
                        cut[side] = max(cut[side], setbacks[j] + gap)
        span = math.dist(a, b)
        run = span - cut[0] - cut[1]
        if run <= 1e-6:
            raise FeatureError(
                f"{owner}: bend edge {k + 1} is too short for the bends at its ends. "
                "Reduce the bend radius or leave this edge out."
            )
        s = setbacks[k]
        p0 = (a[0] + e[0] * cut[0] - w[0] * s, a[1] + e[1] * cut[0] - w[1] * s)
        ba = bend_allowance(rule, t, angle, owner)
        child = wid_of[link.child]
        bend = Bend(f"{fid}/bend{k + 1}", fid, wid_of[link.parent], child, p0, w, run, up,
                    rule.radius, angle, ba)  # fmt: skip
        model.bends[bend.bid] = bend
        margin = [(cut[i] + t + 1.0) if cut[i] > 0 else 0.0 for i in (0, 1)]
        start = (a[0] - e[0] * margin[0] - w[0] * s, a[1] - e[1] * margin[0] - w[1] * s)
        model.walls[bend.parent].cuts.append(
            oriented_box(f"{fid}/trim{k + 1}p", start, w, (0.0, 0.0, -1.0),
                         (span + margin[0] + margin[1], s + t + 1.0, t + 1.0))
        )  # fmt: skip
        child_place = model.placements(False)[child]
        plate = _plate(child, solid.faces[link.child], child_place, t, owner)
        trim = oriented_box(
            f"{fid}/trim{k + 1}c", (0.0, 0.0), (0.0, 1.0),
            (-cut[0] - margin[0], -(s + t + 1.0), -1.0), (run + cut[1] + margin[1], 0.0, t + 1.0),
        )  # fmt: skip
        model.walls[child] = Wall(child, fid, plate, [trim])
    _rips(fid, solid, order, links, model, wid_of, gap, owner, rip_type)
    return model


def unit3(v: Vec3) -> Vec3:
    """``v`` scaled to length one."""
    n = math.sqrt(_dot(v, v))
    return (v[0] / n, v[1] / n, v[2] / n)


def _rips(
    fid: str,
    solid: Solid,
    order: list[int],
    links: list[_Link],
    model: SheetModel,
    wid_of: dict[int, str],
    gap: float,
    owner: str,
    rip_type: str = "overlap",
) -> None:
    """Edges between kept faces that are not bends (D537). ``rip_type`` (TR171, D2307):
    "overlap" (the later wall stops the gap short of the earlier wall's inside face, so
    the earlier one covers the corner), "underlap" (the other way round), "open" (both
    stop the gap short of the other's inside face, so the corner is left open) or
    "butt" (both stop half the gap short of the plane that halves the corner)."""
    t = model.thickness
    bend_edges = [link.edge for link in links]
    places = model.placements(False)
    count = 0
    for edge in solid.edges():
        sides = solid.sides(edge)
        if len(sides) != 2 or not all(s in order for s in sides):
            continue
        if any(edge.IsSame(b) for b in bend_edges):
            continue
        ends = line_ends(edge)
        if ends is None:
            raise FeatureError(
                f"{owner}: a rip edge between two walls is curved. Pick straight rip edges."
            )
        first, later = sorted(sides, key=order.index)
        n_first = face_normal(solid.faces[first])
        c_later = centroid(solid.faces[later])
        mid = tuple((ends[0][i] + ends[1][i]) / 2 for i in range(3))
        if _dot(_sub(c_later, mid), n_first) > 0:  # type: ignore[arg-type]
            raise FeatureError(
                f"{owner}: a rip edge is an inside corner. Make it a bend edge instead."
            )
        count += 1
        if rip_type == "butt":
            _butt(fid, count, solid, first, later, ends, model, wid_of, gap)
            continue
        pairs = {"overlap": [(first, later)], "underlap": [(later, first)],
                 "open": [(first, later), (later, first)]}[rip_type]  # fmt: skip
        for keep, cut_wall in pairs:
            inv = places[wid_of[keep]].Inverted()
            a, b = apply(inv, ends[0]), apply(inv, ends[1])
            d = unit2((b[0] - a[0], b[1] - a[1]))
            w: Vec2 = (-d[1], d[0])
            reach = 4 * (t + gap) + 10.0
            length = math.dist(a, b)
            tag = "" if rip_type == "overlap" else ("b" if cut_wall == first else "a")
            cut = oriented_box(
                f"{fid}/rip{count}{tag}", (a[0], a[1]), w,
                (-reach, -reach, -reach), (length + reach, reach, t + gap),
            )  # fmt: skip
            to = places[wid_of[cut_wall]].Inverted().Multiplied(places[wid_of[keep]])
            model.walls[wid_of[cut_wall]].cuts.append(transform(cut, to))


def _butt(
    fid: str,
    count: int,
    solid: Solid,
    first: int,
    later: int,
    ends: tuple[Vec3, Vec3],
    model: SheetModel,
    wid_of: dict[int, str],
    gap: float,
) -> None:
    """A butt rip: each wall is cut back to the plane that halves the corner (D2307)."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt

    places = model.placements(False)
    n_first, n_later = face_normal(solid.faces[first]), face_normal(solid.faces[later])
    normal = unit3(_sub(n_first, n_later))  # points from the later wall to the first
    along3 = unit3(_sub(ends[1], ends[0]))
    mid = tuple((ends[0][i] + ends[1][i]) / 2 for i in range(3))
    size = 4 * (math.dist(ends[0], ends[1]) + model.thickness + gap) + 10.0
    for wall, sign in ((first, -1.0), (later, 1.0)):
        # The first wall loses what lies on the later wall's side of the plane, and
        # the other way round, each half the gap past it.
        origin = tuple(mid[i] - normal[i] * sign * gap / 2 for i in range(3))
        z = tuple(normal[i] * sign for i in range(3))
        place = frame(origin, along3, z)  # type: ignore[arg-type]
        shape = BRepPrimAPI_MakeBox(gp_Pnt(-size, -size, 0.0), 2 * size, 2 * size, size).Shape()
        tag = "a" if wall == first else "b"
        named = NamedShape(shape, [(f"{fid}/rip{count}{tag}/side", f) for f in faces_of(shape)])
        world = transform(named, place)
        model.walls[wid_of[wall]].cuts.append(transform(world, places[wid_of[wall]].Inverted()))


def pick_edges(
    feature: Feature, ctx: BuildContext, key: str
) -> tuple[list[TopoDS_Edge], list[Issue]]:
    """The edges of ``refs[key]``."""
    refs = feature.refs.get(key)
    out: list[TopoDS_Edge] = []
    issues: list[Issue] = []
    if isinstance(refs, list):
        for ref in refs:
            if not isinstance(ref, dict):
                raise FeatureError(f"{feature.name}: an edge pick is damaged. Pick it again.")
            edge, found = resolve_edge(ctx.body, ref, feature.name)
            issues.extend(found)
            out.append(edge)
    return out, issues


def start_check(feature: Feature, ctx: BuildContext) -> None:
    """The part must be a solid that is not sheet metal yet."""
    if ctx.body is None:
        raise FeatureError(f"{feature.name} needs a solid to convert. Make a solid first.")
    last, _blocker = latest_sheet(feature, ctx)
    if last is not None:
        raise FeatureError(
            f"{feature.name}: the part is already sheet metal. "
            "Delete this feature and use the sheet metal tools."
        )


@register
class ConvertSheet(FeatureType):
    """Turns the faces of a solid into a sheet metal part."""

    type_name = "convert_sheet"
    makes_solid = True
    params = (
        ParamSpec("gap", kind=Kind.LENGTH, optional=True),
        ParamSpec("keep_body", default=False, optional=True),  # TR171 (D2307)
        ParamSpec("rip_type", choices=RIP_TYPES, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Build the sheet from the solid's faces."""
        name = feature.name
        start_check(feature, ctx)
        assert ctx.body is not None
        defaults = sheet_defaults(feature, ctx)
        ref = feature.refs.get("face")
        if not isinstance(ref, dict):
            raise FeatureError(f"{name}: pick the flat face that stays fixed.")
        face, issues = resolve_face(ctx.body, ref, name)
        solid = Solid(ctx.body.shape)
        fixed = solid.index(face)
        bends, found = pick_edges(feature, ctx, "bends")
        if not bends:
            raise FeatureError(f"{name}: pick the edges to bend.")
        gap = value(feature, "gap", 0.0)
        if gap < 0:
            raise FeatureError(f"{name}: the gap cannot be negative. Enter zero or more.")
        rip_type = str(feature.params.get("rip_type", "overlap"))
        if rip_type not in RIP_TYPES:
            raise FeatureError(f"{name}: the rip type is not known. Choose one in the list.")
        model = convert(
            feature.id, solid, fixed, bends, defaults.thickness, defaults.rule, gap, name,
            rip_type,
        )  # fmt: skip
        if feature.params.get("keep_body") is True:  # TR171 (D2307)
            from fdcad.core.features.bodies import solid_of_face, sub_body

            model.kept.append(sub_body(ctx.body, [solid_of_face(ctx.body.shape, face)], feature.id))
        body = model.build(feature.id, name)
        return SheetResult(body=body, issues=[*issues, *found], sheet=model)
