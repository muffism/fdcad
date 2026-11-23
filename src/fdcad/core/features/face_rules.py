"""Rules that add faces to a Move Face (TR263, DECISIONS D788).

With a rule ticked, faces of the body that stand in that relation to a picked
face join the move, so a design intent (two coplanar pads, the two halves of a
hole, a filleted wall) survives a direct edit. Rules are booleans on the
feature (``rule_<name>``); ``suspend_rules`` turns every rule off for the edit,
and ``refs.rule_exclude`` lists faces no rule may add.

- ``coplanar``: flat faces on the same plane, facing the same way.
- ``concentric``: round faces (cylinder, cone, sphere, torus) on the same axis
  as a picked round face.
- ``tangent``: faces that meet a picked face smoothly along an edge, followed
  along the chain.
- ``equal_radius``: cylinders with the same radius as a picked cylinder.
- ``symmetric`` (D798): the mirror image of a picked face about a symmetry plane
  (``refs.symmetry_plane``, else each main plane through the origin) joins the
  move, moving the mirrored way. Offset and Resize only: the mirror face gets
  the same offset.

Holding rules (D798) add no faces; they say which faces next to the moved
faces must keep their direction, so a way of following that would tilt them
fails (and Move Face tries the next one, TR264):

- ``parallel``: neighbours parallel or square to a moved flat face.
- ``main_planes``: neighbours that face along X, Y or Z.

``refs.rule_exclude`` lists faces no rule adds or holds; ``refs.rule_exclude_<rule>``
faces that one rule leaves alone (TR263 item 3).

Pure geometry, no Qt.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepLProp import BRepLProp_SLProps
from OCP.GeomAbs import GeomAbs_SurfaceType
from OCP.ShapeAnalysis import ShapeAnalysis_Surface
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Face

from fdcad.core.naming.names import NamedShape

V3 = tuple[float, float, float]
Axis = tuple[V3, V3]

#: Rules that add faces to the move.
ADDING = ("coplanar", "concentric", "tangent", "equal_radius", "symmetric")
#: Rules that hold neighbouring faces to their direction.
HOLDING = ("parallel", "main_planes")
RULES = ADDING + HOLDING
#: Distances and angles closer than these count as the same.
LINEAR = 1e-4
ANGULAR = math.radians(0.05)

_ROUND = (
    GeomAbs_SurfaceType.GeomAbs_Cylinder,
    GeomAbs_SurfaceType.GeomAbs_Cone,
    GeomAbs_SurfaceType.GeomAbs_Sphere,
    GeomAbs_SurfaceType.GeomAbs_Torus,
)


def active_rules(params: Mapping[str, object]) -> list[str]:
    """The ticked rules, or none while ``suspend_rules`` is on."""
    if params.get("suspend_rules") is True:
        return []
    return [r for r in RULES if params.get(f"rule_{r}") is True]


def _vec(d: object) -> tuple[float, float, float]:
    return (d.X(), d.Y(), d.Z())  # type: ignore[attr-defined]


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _plane(face: TopoDS_Face) -> tuple[tuple[float, float, float], float] | None:
    """Outward normal and offset of a flat face."""
    surface = BRepAdaptor_Surface(face)
    if surface.GetType() != GeomAbs_SurfaceType.GeomAbs_Plane:
        return None
    pln = surface.Plane()
    n = _vec(pln.Axis().Direction())
    if face.Orientation().name == "TopAbs_REVERSED":
        n = (-n[0], -n[1], -n[2])
    p = _vec(pln.Location())
    return n, _dot(n, p)


def _axis(
    face: TopoDS_Face,
) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
    """Axis point and direction of a round face."""
    surface = BRepAdaptor_Surface(face)
    kind = surface.GetType()
    if kind == GeomAbs_SurfaceType.GeomAbs_Cylinder:
        ax = surface.Cylinder().Axis()
    elif kind == GeomAbs_SurfaceType.GeomAbs_Cone:
        ax = surface.Cone().Axis()
    elif kind == GeomAbs_SurfaceType.GeomAbs_Torus:
        ax = surface.Torus().Axis()
    elif kind == GeomAbs_SurfaceType.GeomAbs_Sphere:
        c = _vec(surface.Sphere().Location())
        return c, (0.0, 0.0, 0.0)  # a sphere: any axis through its centre
    else:
        return None
    return _vec(ax.Location()), _vec(ax.Direction())


def _same_axis(a: Axis, b: Axis) -> bool:
    (pa, da), (pb, db) = a, b
    if da == (0.0, 0.0, 0.0) or db == (0.0, 0.0, 0.0):
        # A sphere: concentric when the other axis passes through its centre.
        point, (p, d) = (pa, (pb, db)) if da == (0.0, 0.0, 0.0) else (pb, (pa, da))
        if d == (0.0, 0.0, 0.0):
            return math.dist(point, p) < LINEAR
        rel = (point[0] - p[0], point[1] - p[1], point[2] - p[2])
        along = _dot(rel, d)
        off = math.sqrt(max(_dot(rel, rel) - along * along, 0.0))
        return off < LINEAR
    if abs(abs(_dot(da, db)) - 1.0) > ANGULAR:
        return False
    rel = (pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2])
    along = _dot(rel, da)
    off = math.sqrt(max(_dot(rel, rel) - along * along, 0.0))
    return off < LINEAR


def _radius(face: TopoDS_Face) -> float | None:
    surface = BRepAdaptor_Surface(face)
    if surface.GetType() == GeomAbs_SurfaceType.GeomAbs_Cylinder:
        return float(surface.Cylinder().Radius())
    return None


def _edges(face: TopoDS_Face) -> list[TopoDS_Edge]:
    out = []
    ex = TopExp_Explorer(face, TopAbs_EDGE)
    while ex.More():
        out.append(TopoDS.Edge(ex.Current()))
        ex.Next()
    return out


def _normal_at(face: TopoDS_Face, point: object) -> tuple[float, float, float] | None:
    surface = BRep_Tool.Surface_s(face)
    uv = ShapeAnalysis_Surface(surface).ValueOfUV(point, 1e-6)
    props = BRepLProp_SLProps(BRepAdaptor_Surface(face), uv.X(), uv.Y(), 1, 1e-6)
    if not props.IsNormalDefined():
        return None
    n = _vec(props.Normal())
    if face.Orientation().name == "TopAbs_REVERSED":
        n = (-n[0], -n[1], -n[2])
    return n


def _tangent(a: TopoDS_Face, b: TopoDS_Face, edge: TopoDS_Edge) -> bool:
    """True when ``a`` and ``b`` meet smoothly at the middle of ``edge``."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve

    curve = BRepAdaptor_Curve(edge)
    mid = curve.Value((curve.FirstParameter() + curve.LastParameter()) / 2)
    na, nb = _normal_at(a, mid), _normal_at(b, mid)
    if na is None or nb is None:
        return False
    return _dot(na, nb) > math.cos(math.radians(1.0))


#: A symmetry plane: a point on it and its unit normal.
Mirror = tuple[V3, V3]
MAIN_PLANES: tuple[Mirror, ...] = (
    ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
    ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    ((0.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
)


def _mirror_point(p: V3, plane: Mirror) -> V3:
    (o, n) = plane
    d = 2 * _dot((p[0] - o[0], p[1] - o[1], p[2] - o[2]), n)
    return (p[0] - d * n[0], p[1] - d * n[1], p[2] - d * n[2])


def _mirror_dir(v: V3, plane: Mirror) -> V3:
    n = plane[1]
    d = 2 * _dot(v, n)
    return (v[0] - d * n[0], v[1] - d * n[1], v[2] - d * n[2])


def _mirror_of(face: TopoDS_Face, others: list[tuple[str, TopoDS_Face]], plane: Mirror) -> int:
    """Index in ``others`` of the face that is ``face`` mirrored in ``plane``, or -1."""
    from fdcad.core.naming.resolve import face_snapshot

    snap = face_snapshot(face)
    centre = _mirror_point(tuple(snap["point"]), plane)
    if math.dist(centre, snap["point"]) < LINEAR:
        return -1  # the face lies across the plane: it is its own mirror
    normal = _mirror_dir(tuple(snap["normal"]), plane) if "normal" in snap else None
    for i, (_name, other) in enumerate(others):
        mine = face_snapshot(other)
        if mine["surface"] != snap["surface"] or math.dist(mine["point"], centre) > LINEAR:
            continue
        if abs(float(mine["area"]) - float(snap["area"])) > max(1e-4 * float(snap["area"]), 1e-6):
            continue
        if normal is not None and _dot(normal, tuple(mine.get("normal", (0, 0, 0)))) < math.cos(
            ANGULAR
        ):
            continue
        return i
    return -1


def rule_faces(
    body: NamedShape,
    picked: list[TopoDS_Face],
    rules: list[str],
    exclude: list[TopoDS_Face],
    exclude_by: Mapping[str, list[TopoDS_Face]] | None = None,
    mirrors: Sequence[Mirror] = MAIN_PLANES,
) -> list[tuple[str, TopoDS_Face, str]]:
    """Faces of ``body`` the ``rules`` add to ``picked``: (name, face, rule), in body order.
    Faces in ``exclude`` are never added, nor faces in ``exclude_by[rule]`` by that rule."""
    rules = [r for r in rules if r in ADDING]
    if not rules:
        return []
    added: list[tuple[str, TopoDS_Face, str]] = []
    rule_now = [""]
    by = exclude_by or {}

    def taken(face: TopoDS_Face) -> bool:
        return (
            any(face.IsSame(p) for p in picked)
            or any(face.IsSame(f) for _n, f, _r in added)
            or any(face.IsSame(x) for x in exclude)
            or any(face.IsSame(x) for x in by.get(rule_now[0], []))
        )

    named = list(body.faces)
    rule_now[0] = "coplanar"
    if "coplanar" in rules:
        planes = [p for p in (_plane(f) for f in picked) if p is not None]
        for name, face in named:
            mine = _plane(face)
            if mine is None or taken(face):
                continue
            n, d = mine
            if any(_dot(n, pn) > math.cos(ANGULAR) and abs(d - pd) < LINEAR for pn, pd in planes):
                added.append((name, face, "coplanar"))
    rule_now[0] = "concentric"
    if "concentric" in rules:
        axes = [a for a in (_axis(f) for f in picked) if a is not None]
        for name, face in named:
            axis = _axis(face)
            if axis is None or taken(face):
                continue
            if any(_same_axis(axis, a) for a in axes):
                added.append((name, face, "concentric"))
    rule_now[0] = "equal_radius"
    if "equal_radius" in rules:
        radii = [r for r in (_radius(f) for f in picked) if r is not None]
        for name, face in named:
            r = _radius(face)
            if r is None or taken(face):
                continue
            if any(abs(r - x) < LINEAR for x in radii):
                added.append((name, face, "equal_radius"))
    rule_now[0] = "symmetric"
    if "symmetric" in rules:
        for face in list(picked) + [f for _n, f, _r in added]:
            for plane in mirrors:
                index = _mirror_of(face, named, plane)
                if index >= 0 and not taken(named[index][1]):
                    added.append((named[index][0], named[index][1], "symmetric"))
    rule_now[0] = "tangent"
    if "tangent" in rules:
        front = list(picked) + [f for _n, f, _r in added]
        while front:
            current = front.pop()
            for edge in _edges(current):
                for name, face in named:
                    if taken(face) or face.IsSame(current):
                        continue
                    if not any(edge.IsSame(e) for e in _edges(face)):
                        continue
                    if _tangent(current, face, edge):
                        added.append((name, face, "tangent"))
                        front.append(face)
    return added


def held_faces(
    body: NamedShape,
    moved: list[TopoDS_Face],
    rules: list[str],
    exclude: list[TopoDS_Face],
    exclude_by: Mapping[str, list[TopoDS_Face]] | None = None,
) -> list[tuple[str, TopoDS_Face, str]]:
    """Faces next to ``moved`` that a holding rule keeps facing the same way: (name, face,
    rule), in body order (D798)."""
    rules = [r for r in rules if r in HOLDING]
    if not rules:
        return []
    by = exclude_by or {}
    moved_edges = [e for f in moved for e in _edges(f)]
    normals = [p[0] for p in (_plane(f) for f in moved) if p is not None]
    out: list[tuple[str, TopoDS_Face, str]] = []
    for name, face in body.faces:
        if any(face.IsSame(m) for m in moved) or any(face.IsSame(x) for x in exclude):
            continue
        if any(face.IsSame(f) for _n, f, _r in out):
            continue
        if not any(e.IsSame(m) for e in _edges(face) for m in moved_edges):
            continue
        mine = _plane(face)
        if mine is None:
            continue
        n = mine[0]
        for rule in rules:
            if any(face.IsSame(x) for x in by.get(rule, [])):
                continue
            if rule == "parallel":
                hit = any(
                    abs(abs(_dot(n, m)) - 1.0) < ANGULAR or abs(_dot(n, m)) < ANGULAR
                    for m in normals
                )
            else:
                hit = any(abs(abs(c) - 1.0) < ANGULAR for c in n)
            if hit:
                out.append((name, face, rule))
                break
    return out


def facing(face: TopoDS_Face) -> V3 | None:
    """The outward normal of a flat face, or None (for the hold check)."""
    found = _plane(face)
    return found[0] if found is not None else None
