"""Resolve stored references to current geometry (PLAN 6 item 6, FDEF_SPEC 7).

Name first. If the name fails, look for one clear match to the stored position
snapshot and return a warning. If there is no confident match, raise a
"missing reference" error. Never pick between equally good matches.

A weak name (a split piece, a position fallback name or an imported face index,
see ``fdcad.core.naming.weak``) can resolve to another face after an upstream
edit, so the face it finds is checked against the snapshot first (D720).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import Any

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepGProp import BRepGProp
from OCP.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_SurfaceType
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Face, TopoDS_Shape

from fdcad.core.features.base import FeatureError, FeatureState, Issue
from fdcad.core.naming import weak
from fdcad.core.naming.names import NamedShape, faces_of
from fdcad.core.plane_normal import plane_normal

_SURFACES: dict[GeomAbs_SurfaceType, str] = {
    GeomAbs_Plane: "plane",
    GeomAbs_Cylinder: "cylinder",
    GeomAbs_Cone: "cone",
}
_POINT_TOL = 1e-3  # mm
_RELATIVE_TOL = 1e-4


def face_snapshot(face: TopoDS_Face) -> dict[str, Any]:
    """Position snapshot of a face (FDEF_SPEC 7.3.1)."""
    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, props)
    c = props.CentreOfMass()
    surface = BRepAdaptor_Surface(face)
    kind = surface.GetType()
    snap: dict[str, Any] = {
        "surface": _SURFACES.get(kind, "other"),
        "point": [c.X(), c.Y(), c.Z()],
        "area": props.Mass(),
    }
    normal = plane_normal(face) if kind == GeomAbs_Plane else None
    if normal is not None:
        snap["normal"] = list(normal)
    elif kind in (GeomAbs_Cylinder, GeomAbs_Cone):
        axis = (surface.Cylinder() if kind == GeomAbs_Cylinder else surface.Cone()).Axis()
        d, p = axis.Direction(), axis.Location()
        snap["axis"] = [p.X(), p.Y(), p.Z(), d.X(), d.Y(), d.Z()]
    return snap


def _matches(stored: dict[str, Any], current: dict[str, Any]) -> bool:
    if stored.get("surface") != current.get("surface"):
        return False
    if math.dist(stored["point"], current["point"]) > _POINT_TOL:
        return False
    area = float(stored.get("area", 0.0))
    if abs(area - float(current["area"])) > max(_RELATIVE_TOL * abs(area), 1e-6):
        return False
    if "normal" not in stored:
        return True
    return math.dist(stored["normal"], current.get("normal", [9, 9, 9])) <= 1e-6


_KEEP, _FOUND, _MOVED, _LOST = "keep", "found", "moved", "lost"


def _judge[T](
    stored: dict[str, Any],
    family: Sequence[T],
    snaps: list[dict[str, Any]],
    named: int | None,
    matches: Callable[[dict[str, Any], dict[str, Any]], bool],
    everywhere: Callable[[], Sequence[T]],
) -> tuple[T | None, str]:
    """Which member of a weak name's family the reference means (D720, D2602).

    ``family[named]`` is what the name gives (None when the name gives nothing). It
    is kept silently when it still matches the snapshot, or when it is the clearly
    nearest member and has not moved far for its size. Otherwise one exact snapshot
    match (in the family, else anywhere), one member still centred where the pick
    was, or another member that is the clearly nearest and has not moved far for
    its size is used with a warning: the numbers of two pieces can swap with a
    small edit. Failing that, the named one is used with a warning when it is still
    the clearly nearest; else the reference is lost.
    """
    if named is not None and matches(stored, snaps[named]):
        return family[named], _KEEP
    best = weak.nearest(stored, snaps)
    if named is not None and best == named and weak.close(stored, snaps[named]):
        return family[named], _KEEP
    exact: Sequence[T] = [
        item for item, snap in zip(family, snaps, strict=True) if matches(stored, snap)
    ]
    if not exact:
        exact = everywhere()
    if len(exact) > 1:
        return None, _LOST  # equally good matches: never pick one
    if exact:
        return exact[0], _FOUND
    same = weak.same_place(stored, snaps)
    if len(same) == 1:
        return family[same[0]], _FOUND
    if best is not None and best != named and weak.close(stored, snaps[best]):
        return family[best], _FOUND  # the numbers moved to other pieces (D2602)
    if named is not None and best == named:
        return family[named], _MOVED
    return None, _LOST


def _weak_issue(owner: str, what: str, name: str, how: str) -> list[Issue]:
    if how == _FOUND:
        text = (
            f"{owner}: {what} {name} now names another {what}, so the picked {what} was "
            "found by its position. Check it and reselect it if it is wrong."
        )
    else:
        text = (
            f"{owner}: {what} {name} is far from where it was picked. Check it and reselect "
            "it if it is wrong."
        )
    return [Issue(FeatureState.WARNING, text, highlight=[name])]


def _lost_weak(owner: str, what: str, name: str) -> FeatureError:
    return FeatureError(
        f"{owner}: missing reference {name}. The name now belongs to another {what} and no "
        f"{what} matches the one picked. Reselect the {what}.",
        highlight=[name],
    )


def _face_family(body: NamedShape, name: str, face: TopoDS_Face | None) -> list[TopoDS_Face]:
    """``face`` first (when given), then every other face whose name has the same root."""
    from fdcad.core.occ import ShapeMap

    root = weak.family_root(name)
    seen = ShapeMap()
    out = []
    if face is not None:
        seen.Add(face)
        out.append(face)
    for other_name, other in body.faces:
        if not seen.Contains(other) and weak.family_root(other_name) == root:
            seen.Add(other)
            out.append(other)
    return out


def _weak_face(
    body: NamedShape, name: str, face: TopoDS_Face, snapshot: dict[str, Any], owner: str
) -> tuple[TopoDS_Face, list[Issue]]:
    family = _face_family(body, name, face)
    snaps = [face_snapshot(f) for f in family]

    def everywhere() -> list[TopoDS_Face]:
        return [f for f in faces_of(body.shape) if _matches(snapshot, face_snapshot(f))]

    found, how = _judge(snapshot, family, snaps, 0, _matches, everywhere)
    if found is None:
        raise _lost_weak(owner, "face", name)
    return found, [] if how == _KEEP else _weak_issue(owner, "face", name, how)


def _by_position(owner: str, what: str, name: str) -> list[Issue]:
    return [
        Issue(
            FeatureState.WARNING,
            f"{owner}: {what} {name} was found by its position. Check it and reselect "
            "it if it is wrong.",
        )
    ]


def _family_pick[T](
    stored: dict[str, Any],
    family: Sequence[T],
    snaps: list[dict[str, Any]],
    matches: Callable[[dict[str, Any], dict[str, Any]], bool],
    everywhere: Callable[[], Sequence[T]],
) -> T | None:
    """The member of a weak name's family meant when the name itself gives nothing
    (D2602): the number went to a piece that no longer meets the other face."""
    found, _how = _judge(stored, family, snaps, None, matches, everywhere)
    return found


def resolve_face(
    body: NamedShape | None, ref: dict[str, Any], owner: str
) -> tuple[TopoDS_Face, list[Issue]]:
    """The face a reference points at, plus a warning when the snapshot was used."""
    name = str(ref.get("name", ""))
    if body is None:
        raise FeatureError(f"{owner}: missing reference {name}. The part is empty. Reselect it.")
    face = body.face(name)
    snapshot = ref.get("snapshot")
    checked = isinstance(snapshot, dict) and "point" in snapshot and weak.is_weak(name)
    if face is not None and not checked:
        return face, []
    if face is not None:
        assert isinstance(snapshot, dict)
        return _weak_face(body, name, face, snapshot, owner)
    if isinstance(snapshot, dict) and "point" in snapshot:
        found = [f for f in faces_of(body.shape) if _matches(snapshot, face_snapshot(f))]
        if len(found) == 1:
            return found[0], _by_position(owner, "face", name)
        if checked and not found:
            family = _face_family(body, name, None)
            pick = _family_pick(
                snapshot, family, [face_snapshot(f) for f in family], _matches, lambda: []
            )
            if pick is not None:
                return pick, _by_position(owner, "face", name)
    raise FeatureError(f"{owner}: missing reference {name}. Reselect the face.", highlight=[name])


def _edge_matches(stored: dict[str, Any], current: dict[str, Any]) -> bool:
    if stored.get("curve") != current.get("curve"):
        return False
    if math.dist(stored["midpoint"], current["midpoint"]) > _POINT_TOL:
        return False
    length = float(stored.get("length", 0.0))
    if abs(length - float(current["length"])) > max(_RELATIVE_TOL * abs(length), 1e-6):
        return False
    if "direction" in stored:
        a, b = stored["direction"], current.get("direction", [0, 0, 0])
        if abs(sum(float(x) * float(y) for x, y in zip(a, b, strict=False))) < 1 - 1e-6:
            return False
    return True


def resolve_edge(
    body: NamedShape | None, ref: dict[str, Any], owner: str
) -> tuple[TopoDS_Edge, list[Issue]]:
    """The edge a reference points at, plus a warning when the snapshot was used."""
    from fdcad.core.naming.select import edge_snapshot
    from fdcad.core.occ import ShapeMap

    name = str(ref.get("name", ""))
    if body is None:
        raise FeatureError(f"{owner}: missing reference {name}. The part is empty. Reselect it.")
    named = body.edges(name)
    snapshot = ref.get("snapshot")
    checked = isinstance(snapshot, dict) and "midpoint" in snapshot and weak.is_weak(name)
    if len(named) == 1 and checked:
        assert isinstance(snapshot, dict)
        return _weak_edge(body, name, named[0], snapshot, owner)
    if len(named) == 1:
        return named[0], []
    if named:
        return _one_piece(body, named, snapshot, name, owner)
    if isinstance(snapshot, dict) and "midpoint" in snapshot:
        emap = ShapeMap()
        TopExp.MapShapes_s(body.shape, TopAbs_EDGE, emap)
        edges = [TopoDS.Edge(emap.FindKey(i)) for i in range(1, emap.Extent() + 1)]
        found = [e for e in edges if _edge_matches(snapshot, edge_snapshot(e, body.shape))]
        if len(found) == 1:
            return found[0], _by_position(owner, "edge", name)
        if checked and not found:
            from fdcad.core.naming.select import curve_snapshot

            root = weak.family_root(name)
            family = [e for e, n in _edge_names(body) if weak.family_root(n) == root]
            pick = _family_pick(
                snapshot, family, [curve_snapshot(e) for e in family], _edge_matches, lambda: []
            )
            if pick is not None:
                return pick, _by_position(owner, "edge", name)
    raise FeatureError(f"{owner}: missing reference {name}. Reselect the edge.", highlight=[name])


def _edge_names(body: NamedShape) -> list[tuple[TopoDS_Edge, str]]:
    """Every edge of ``body`` with its name, in one pass (``NamedShape.edge_name`` for all)."""
    from fdcad.core.occ import ShapeListMap, ShapeMap, shape_list

    fmap = ShapeMap()
    primary: list[str] = []
    for face_name, face in body.faces:
        if not fmap.Contains(face):
            fmap.Add(face)
            primary.append(face_name)
    amap = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(body.shape, TopAbs_EDGE, TopAbs_FACE, amap)
    out: list[tuple[TopoDS_Edge, str]] = []
    for i in range(1, amap.Extent() + 1):
        faces: list[TopoDS_Shape] = shape_list(amap.FindFromIndex(i))
        names = sorted({primary[k - 1] for k in (fmap.FindIndex(f) for f in faces) if k})
        if not names:
            continue
        if len(names) == 1:
            names = names * 2
        out.append((TopoDS.Edge(amap.FindKey(i)), f"edge({'|'.join(names)})"))
    return out


def _weak_edge(
    body: NamedShape, name: str, edge: TopoDS_Edge, snapshot: dict[str, Any], owner: str
) -> tuple[TopoDS_Edge, list[Issue]]:
    from fdcad.core.naming.select import curve_snapshot

    root = weak.family_root(name)
    pairs = _edge_names(body)
    family = [edge] + [e for e, n in pairs if weak.family_root(n) == root and not e.IsSame(edge)]
    snaps = [curve_snapshot(e) for e in family]

    def everywhere() -> list[TopoDS_Edge]:
        return [e for e, _n in pairs if _edge_matches(snapshot, curve_snapshot(e))]

    found, how = _judge(snapshot, family, snaps, 0, _edge_matches, everywhere)
    if found is None:
        raise _lost_weak(owner, "edge", name)
    return found, [] if how == _KEEP else _weak_issue(owner, "edge", name, how)


def _one_piece(
    body: NamedShape, named: list[TopoDS_Edge], snapshot: Any, name: str, owner: str
) -> tuple[TopoDS_Edge, list[Issue]]:
    """The piece the user picked when two faces meet along several edges (D606).

    The piece whose snapshot still matches is used. Otherwise the piece nearest
    to where the edge was picked is used, with a warning.
    """
    from fdcad.core.naming.select import edge_snapshot

    if not isinstance(snapshot, dict) or "midpoint" not in snapshot:
        nearest = named[0]
    else:
        snaps = [edge_snapshot(e, body.shape) for e in named]
        exact = [e for e, s in zip(named, snaps, strict=True) if _edge_matches(snapshot, s)]
        if len(exact) == 1:
            return exact[0], []
        dists = [math.dist(snapshot["midpoint"], s["midpoint"]) for s in snaps]
        nearest = named[dists.index(min(dists))]
    return nearest, [
        Issue(
            FeatureState.WARNING,
            f"{owner}: edge {name} is in {len(named)} pieces now; the piece nearest to where "
            "it was picked is used. Check it and reselect it if it is wrong.",
        )
    ]


def resolve_edge_pieces(
    body: NamedShape | None, ref: dict[str, Any], owner: str
) -> tuple[list[TopoDS_Edge], list[Issue]]:
    """Like ``resolve_edge``, but every piece when the picked edge was split (D606).

    An edit before the feature (a notch across the edge) can split the picked
    edge into pieces with the same name. The pieces that lie inside the edge as
    it was picked are all returned, so a fillet or chamfer rounds the whole edge.
    """
    from fdcad.core.naming.select import edge_snapshot

    name = str(ref.get("name", ""))
    snapshot = ref.get("snapshot")
    named = body.edges(name) if body is not None else []
    if len(named) > 1 and isinstance(snapshot, dict) and "midpoint" in snapshot:
        snaps = [edge_snapshot(e, body.shape) for e in named]  # type: ignore[union-attr]
        if not any(_edge_matches(snapshot, s) for s in snaps):
            inside = [e for e, s in zip(named, snaps, strict=True) if _inside(snapshot, s)]
            if len(inside) > 1:
                return inside, []
    edge, issues = resolve_edge(body, ref, owner)
    return [edge], issues


def _inside(stored: dict[str, Any], piece: dict[str, Any]) -> bool:
    """True when ``piece`` could be part of the edge described by ``stored``."""
    if stored.get("curve") != piece.get("curve"):
        return False
    length = float(stored.get("length", 0.0))
    if float(piece["length"]) > length * (1 + _RELATIVE_TOL) + 1e-6:
        return False
    if math.dist(stored["midpoint"], piece["midpoint"]) > length / 2 + _POINT_TOL:
        return False
    if "direction" in stored:
        a, b = stored["direction"], piece.get("direction", [0, 0, 0])
        if abs(sum(float(x) * float(y) for x, y in zip(a, b, strict=False))) < 1 - 1e-6:
            return False
    return True


def resolve_vertex(
    body: NamedShape | None, ref: dict[str, Any], owner: str
) -> tuple[tuple[float, float, float], list[Issue]]:
    """The point of the vertex a reference points at, plus a warning when the snapshot was used."""
    from OCP.BRep import BRep_Tool
    from OCP.TopAbs import TopAbs_VERTEX

    from fdcad.core.occ import ShapeMap

    name = str(ref.get("name", ""))
    if body is None:
        raise FeatureError(f"{owner}: missing reference {name}. The part is empty. Reselect it.")
    vmap = ShapeMap()
    TopExp.MapShapes_s(body.shape, TopAbs_VERTEX, vmap)
    snapshot = ref.get("snapshot")
    checked = isinstance(snapshot, dict) and "point" in snapshot and weak.is_weak(name)
    root = weak.family_root(name)
    points: list[tuple[float, float, float]] = []
    named: tuple[float, float, float] | None = None
    family: list[tuple[float, float, float]] = []
    for i in range(1, vmap.Extent() + 1):
        vertex = TopoDS.Vertex(vmap.FindKey(i))
        p = BRep_Tool.Pnt_s(vertex)
        point = (p.X(), p.Y(), p.Z())
        vname = body.vertex_name(vertex)
        if vname == name and not checked:
            return point, []
        if vname == name and named is None:
            named = point
        elif checked and vname is not None and weak.family_root(vname) == root:
            family.append(point)
        points.append(point)
    if named is not None:
        assert isinstance(snapshot, dict)
        return _weak_vertex(snapshot, [named, *family], points, name, owner)
    if isinstance(snapshot, dict) and "point" in snapshot:
        stored = [float(v) for v in snapshot["point"]]
        found = [p for p in points if math.dist(stored, p) <= _POINT_TOL]
        if len(found) == 1:
            return found[0], _by_position(owner, "vertex", name)
        if checked and not found and family:
            snaps = [{"point": list(p)} for p in family]
            pick = _family_pick(snapshot, family, snaps, _point_matches, lambda: [])
            if pick is not None:
                return pick, _by_position(owner, "vertex", name)
    raise FeatureError(f"{owner}: missing reference {name}. Reselect the vertex.", highlight=[name])


def _point_matches(stored: dict[str, Any], current: dict[str, Any]) -> bool:
    return weak.distance(stored, current) <= _POINT_TOL


def _weak_vertex(
    snapshot: dict[str, Any],
    family: list[tuple[float, float, float]],
    points: list[tuple[float, float, float]],
    name: str,
    owner: str,
) -> tuple[tuple[float, float, float], list[Issue]]:
    snaps = [{"point": list(p)} for p in family]

    def everywhere() -> list[tuple[float, float, float]]:
        return [p for p in points if _point_matches(snapshot, {"point": list(p)})]

    found, how = _judge(snapshot, family, snaps, 0, _point_matches, everywhere)
    if found is None:
        raise _lost_weak(owner, "vertex", name)
    return found, [] if how == _KEEP else _weak_issue(owner, "vertex", name, how)
