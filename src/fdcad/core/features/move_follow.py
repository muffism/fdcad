"""How the faces around a moved face follow it (TR264, DECISIONS D797).

Move Face has three ways to rejoin the moved faces to the body:

- ``extend``: the neighbours keep their angle and are extended or trimmed to
  meet the moved face (the offset and volume methods in ``direct``; the way
  Move Face always worked).
- ``tip``: the neighbours tilt to meet it. Every corner of the picked faces
  moves with them and every other corner stays, so each neighbour is made
  again through its corners. This needs flat neighbours with straight edges
  where they touch a moved corner, and each of them must stay flat; otherwise
  the move fails with a message that says to use Extend.
- ``lift``: the picked faces move unchanged and new side faces join them to
  where they were: the face is swept along the move and the swept solid is
  added (moving out) or cut away (moving in). Translate and Offset only.

Kernel work: call from the rebuild (CLAUDE.md rule 2). Kernel exceptions turn
into FeatureError (rule 7).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakeSolid,
    BRepBuilderAPI_MakeWire,
    BRepBuilderAPI_Sewing,
    BRepBuilderAPI_Transform,
)
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.BRepTools import BRepTools, BRepTools_WireExplorer
from OCP.GeomAbs import GeomAbs_Line, GeomAbs_Plane
from OCP.gp import gp_Pnt, gp_Trsf, gp_Vec
from OCP.ShapeFix import ShapeFix_Face, ShapeFix_Solid
from OCP.TopAbs import TopAbs_FACE, TopAbs_SHELL, TopAbs_VERTEX, TopAbs_WIRE
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape, TopoDS_Wire

from fdcad.core.features.base import FeatureError, Vec3
from fdcad.core.features.solids import combine, volume_of
from fdcad.core.naming.names import NamedFace, NamedShape, faces_of, restrict
from fdcad.core.occ import ShapeMap

FOLLOW = ("extend", "tip", "lift")
#: What happens to rounds on the moved faces' edges (TR264 item 3): they follow the move
#: (the offset grows or shrinks them), or they are taken off and made again after it.
ROUNDS = ("follow", "remake")
#: How far a remade neighbour may be from flat (mm) before Tip refuses it.
_FLAT_TOL = 1e-6
_SEW_TOL = 1e-6


def follow_order(chosen: str) -> list[str]:
    """The ways to try: the chosen one first, then the others in ``FOLLOW`` order.

    This is also the order Next and Previous step through in the panel (TR264 item 2).
    """
    first = chosen if chosen in FOLLOW else "extend"
    return [first, *(f for f in FOLLOW if f != first)]


# Lift ------------------------------------------------------------------------------


def lift_faces(
    body: NamedShape,
    faces: Sequence[TopoDS_Face],
    moves: Sequence[Vec3],
    fid: str,
    name: str,
    labels: Sequence[str],
) -> NamedShape:
    """Sweep each flat face along its move and add the sweep (moving out of the body) or
    cut it away (moving in). The face keeps its name at its new place; the new side
    faces are ``<fid>/lift/<k>/face#j``."""
    from fdcad.core.features.direct import outward_normal, rename_moved

    result = body
    for k, (face, move) in enumerate(zip(faces, moves, strict=True), start=1):
        v = gp_Vec(*move)
        if v.Magnitude() < 1e-9:
            raise FeatureError(f"{name}: the move is zero. Type a distance.")
        normal = outward_normal(face)
        if normal is None:
            raise FeatureError(
                f"{name}: Lift moves flat faces only. {labels[k - 1]} is curved. "
                "Choose Extend for curved faces.",
                highlight=[labels[k - 1]],
            )
        along = sum(a * b for a, b in zip(normal, move, strict=True))
        if abs(along) < 1e-9:
            raise FeatureError(
                f"{name}: Lift needs a move into or out of {labels[k - 1]}; this one slides "
                "along it. Choose Extend.",
                highlight=[labels[k - 1]],
            )
        try:
            prism = BRepPrimAPI_MakePrism(face, v).Shape()
        except Exception as exc:  # kernel failure
            raise FeatureError(
                f"{name} failed: {labels[k - 1]} cannot be swept ({type(exc).__name__}). "
                "Choose Extend.",
                highlight=[labels[k - 1]],
            ) from exc
        tool = NamedShape(prism, restrict([], prism, f"{fid}/lift/{k}"))
        result = combine(fid, name, result, tool, "boss" if along > 0 else "cut")
    for face, move in zip(faces, moves, strict=True):
        trsf = gp_Trsf()
        trsf.SetTranslation(gp_Vec(*move))
        result = rename_moved(result, body, [face], trsf)
    return result


# Tip -------------------------------------------------------------------------------


def _point(vertex: Any) -> gp_Pnt:
    return BRep_Tool.Pnt_s(TopoDS.Vertex(vertex))


def tip_faces(
    body: NamedShape,
    faces: Sequence[TopoDS_Face],
    trsf: gp_Trsf,
    fid: str,
    name: str,
    labels: Sequence[str],
) -> NamedShape:
    """Move the picked faces by ``trsf`` and tilt the faces around them to meet them."""
    picked = ShapeMap()
    moved_vertices = ShapeMap()
    for face in faces:
        picked.Add(face)
        TopExp.MapShapes_s(face, TopAbs_VERTEX, moved_vertices)

    def place(vertex: Any) -> gp_Pnt:
        p = _point(vertex)
        return p.Transformed(trsf) if moved_vertices.Contains(vertex) else p

    remade: list[tuple[TopoDS_Face, TopoDS_Shape]] = []
    for face in faces_of(body.shape):
        if picked.Contains(face):
            new = BRepBuilderAPI_Transform(face, trsf, True).Shape()
        elif _touches(face, moved_vertices):
            new = _remade(face, place, moved_vertices, name, body)
        else:
            new = face
        remade.append((face, new))
    shape, sewing = _sewn([n for _f, n in remade], name, labels)
    named: list[NamedFace] = []
    for old_name, old_face in body.faces:
        index = next((i for i, (f, _n) in enumerate(remade) if f.IsSame(old_face)), None)
        if index is None:
            continue
        new = remade[index][1]
        image = sewing.Modified(new) if sewing.IsModified(new) else new
        ex = TopExp_Explorer(image, TopAbs_FACE)
        while ex.More():
            named.append((old_name, TopoDS.Face(ex.Current())))
            ex.Next()
    return NamedShape(shape, restrict(named, shape, f"{fid}/tip"))


def _touches(face: TopoDS_Face, vertices: ShapeMap) -> bool:
    ex = TopExp_Explorer(face, TopAbs_VERTEX)
    while ex.More():
        if vertices.Contains(ex.Current()):
            return True
        ex.Next()
    return False


def _remade(
    face: TopoDS_Face,
    place: Callable[[Any], gp_Pnt],
    moved: ShapeMap,
    name: str,
    body: NamedShape,
) -> TopoDS_Face:
    """``face`` made again through its moved corners. It must be flat and stay flat."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface

    label = _label(body, face)
    if BRepAdaptor_Surface(face).GetType() != GeomAbs_Plane:
        raise FeatureError(
            f"{name}: Tip cannot tilt {label}, which is curved. Choose Extend or Lift.",
            highlight=[label],
        )
    outer = BRepTools.OuterWire_s(face)
    wires = [outer]
    ex = TopExp_Explorer(face, TopAbs_WIRE)
    while ex.More():
        wire = TopoDS.Wire(ex.Current())
        if not wire.IsSame(outer):
            wires.append(wire)
        ex.Next()
    rebuilt = [_rewire(w, place, moved, name, label) for w in wires]
    points = np.array(
        [[p.X(), p.Y(), p.Z()] for w in rebuilt for p in _wire_points(w)], dtype=float
    )
    centre = points.mean(axis=0)
    _u, s, vt = np.linalg.svd(points - centre)
    off = np.abs((points - centre) @ vt[2])
    if float(off.max(initial=0.0)) > _FLAT_TOL * max(1.0, float(s[0])):
        raise FeatureError(
            f"{name}: Tip would bend {label}, so it cannot stay flat. Choose Extend or Lift.",
            highlight=[label],
        )
    maker = BRepBuilderAPI_MakeFace(rebuilt[0], True)
    for wire in rebuilt[1:]:
        maker.Add(wire)
    if not maker.IsDone():
        raise FeatureError(
            f"{name}: Tip cannot make {label} again. Choose Extend or Lift.", highlight=[label]
        )
    fix = ShapeFix_Face(maker.Face())
    fix.FixOrientation()
    fix.Perform()
    return TopoDS.Face(fix.Face())


def _rewire(
    wire: TopoDS_Wire, place: Callable[[Any], gp_Pnt], moved: ShapeMap, name: str, label: str
) -> TopoDS_Wire:
    maker = BRepBuilderAPI_MakeWire()
    walk = BRepTools_WireExplorer(wire)
    while walk.More():
        edge = walk.Current()
        first = TopExp.FirstVertex_s(edge, True)
        last = TopExp.LastVertex_s(edge, True)
        if moved.Contains(first) or moved.Contains(last):
            if BRepAdaptor_Curve(edge).GetType() != GeomAbs_Line:
                raise FeatureError(
                    f"{name}: Tip needs straight edges where {label} meets the moved faces. "
                    "Choose Extend or Lift.",
                    highlight=[label],
                )
            a, b = place(first), place(last)
            if a.Distance(b) < 1e-7:
                raise FeatureError(
                    f"{name}: Tip would shrink an edge of {label} to nothing. Move less far.",
                    highlight=[label],
                )
            maker.Add(BRepBuilderAPI_MakeEdge(a, b).Edge())
        else:
            maker.Add(edge)
        walk.Next()
    if not maker.IsDone():
        raise FeatureError(
            f"{name}: Tip cannot close the outline of {label}. Choose Extend or Lift.",
            highlight=[label],
        )
    return maker.Wire()


def _wire_points(wire: TopoDS_Wire) -> list[gp_Pnt]:
    out = []
    ex = TopExp_Explorer(wire, TopAbs_VERTEX)
    while ex.More():
        out.append(_point(ex.Current()))
        ex.Next()
    return out


def _label(body: NamedShape, face: TopoDS_Face) -> str:
    from fdcad.core.features.direct import short_name

    found = body.primary_name(face)
    return short_name(found) if found else "a neighbouring face"


def _sewn(
    faces: Sequence[TopoDS_Shape], name: str, labels: Sequence[str]
) -> tuple[TopoDS_Shape, BRepBuilderAPI_Sewing]:
    sewing = BRepBuilderAPI_Sewing(_SEW_TOL)
    for face in faces:
        sewing.Add(face)
    try:
        sewing.Perform()
        sewn = sewing.SewedShape()
        ex = TopExp_Explorer(sewn, TopAbs_SHELL)
        if not ex.More():
            raise ValueError("no shell")
        solid_maker = BRepBuilderAPI_MakeSolid(TopoDS.Shell(ex.Current()))
        fix = ShapeFix_Solid(solid_maker.Solid())
        fix.Perform()
        shape = fix.Solid()
    except Exception as exc:
        raise FeatureError(
            f"{name}: Tip could not close the body around {', '.join(labels)}. "
            "Choose Extend or Lift, or move less far.",
            highlight=list(labels),
        ) from exc
    if not BRepCheck_Analyzer(shape).IsValid() or volume_of(shape) <= 1e-9:
        raise FeatureError(
            f"{name}: Tip made an invalid body around {', '.join(labels)}. "
            "Choose Extend or Lift, or move less far.",
            highlight=list(labels),
        )
    return shape, sewing


# Rounds -----------------------------------------------------------------------------


#: A round to make again: its old face names, its radius and the edge name it rounded.
RoundPlan = list[tuple[list[str], float, str]]


def _round_radius(face: TopoDS_Face) -> float | None:
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Torus

    surface = BRepAdaptor_Surface(face)
    kind = surface.GetType()
    if kind == GeomAbs_Cylinder:
        return float(surface.Cylinder().Radius())
    if kind == GeomAbs_Torus:
        return float(surface.Torus().MinorRadius())
    return None


def strip_rounds(
    body: NamedShape, faces: list[TopoDS_Face], labels: list[str], fid: str, name: str
) -> tuple[NamedShape, list[TopoDS_Face], RoundPlan]:
    """Take off the rounds (fillet faces) that touch the picked faces, so the move runs
    on sharp edges; returns the part, the picked faces in it and what to make again."""
    from OCP.TopAbs import TopAbs_EDGE

    from fdcad.core.features.direct import patch, short_name
    from fdcad.core.occ import ShapeListMap, shape_list

    amap = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(body.shape, TopAbs_EDGE, TopAbs_FACE, amap)
    picked = ShapeMap()
    for face in faces:
        picked.Add(face)
    names: dict[int, list[str]] = {}
    fmap = ShapeMap()
    for face_name, face in body.faces:
        index = fmap.Add(face)
        names.setdefault(index, []).append(face_name)
    plan: RoundPlan = []
    rounds: list[TopoDS_Face] = []
    seen = ShapeMap()
    for i in range(1, amap.Extent() + 1):
        around = [TopoDS.Face(f) for f in shape_list(amap.FindFromIndex(i))]
        if not any(picked.Contains(f) for f in around):
            continue
        for face in around:
            if picked.Contains(face) or seen.Contains(face):
                continue
            own = names.get(fmap.FindIndex(face), [])
            edge_name = next((n.split("/fillet/", 1)[1] for n in own if "/fillet/" in n), None)
            radius = _round_radius(face)
            if edge_name is None or radius is None:
                continue
            seen.Add(face)
            rounds.append(face)
            plan.append((own, radius, edge_name))
    if not rounds:
        return body, faces, []
    picked_names = [body.primary_name(f) for f in faces]
    patched = patch(body, rounds, fid, name, [short_name(p[0][0]) for p in plan])
    found = []
    for face, picked_name in zip(faces, picked_names, strict=True):
        again = patched.face(picked_name) if picked_name is not None else None
        if again is None:
            raise FeatureError(
                f"{name}: taking the rounds off lost {labels[faces.index(face)]}. "
                "Choose Follow for Rounds.",
                highlight=list(labels),
            )
        found.append(again)
    return patched, found, plan


def remake_rounds(body: NamedShape, plan: RoundPlan, fid: str, name: str) -> NamedShape:
    """Round each planned edge again with its old radius; the new faces take the old
    round's names, so features on the round stay attached."""
    if not plan:
        return body
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet

    from fdcad.core.features.modify import MakerHistory
    from fdcad.core.naming.names import carry

    maker = BRepFilletAPI_MakeFillet(body.shape)
    edges = []
    for own, radius, edge_name in plan:
        found = body.edges(edge_name)
        if not found:
            raise FeatureError(
                f"{name}: the edge a round was on ({edge_name}) is gone after the move, so the "
                "round cannot be made again. Choose Follow for Rounds.",
            )
        for edge in found:
            maker.Add(radius, edge)
            edges.append((own, edge))
    try:
        maker.Build()
        ok = maker.IsDone()
        shape = maker.Shape() if ok else None
    except Exception:  # kernel failure
        ok, shape = False, None
    if not ok or shape is None or not BRepCheck_Analyzer(shape).IsValid():
        raise FeatureError(
            f"{name}: the rounds cannot be made again after the move. Move less far or "
            "choose Follow for Rounds."
        )
    named = carry(body.faces, MakerHistory(maker))
    for own, edge in edges:
        made = maker.Generated(edge)
        for face in shape_list_of(made):
            named.extend((n, TopoDS.Face(face)) for n in own)
    return NamedShape(shape, restrict(named, shape, f"{fid}/round"))


def shape_list_of(shapes: Any) -> list[TopoDS_Shape]:
    """A kernel list of shapes as a Python list."""
    from fdcad.core.occ import shape_list

    return list(shape_list(shapes))


__all__ = [
    "FOLLOW",
    "ROUNDS",
    "follow_order",
    "lift_faces",
    "remake_rounds",
    "strip_rounds",
    "tip_faces",
]
