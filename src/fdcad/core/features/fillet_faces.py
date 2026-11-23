"""Face set helpers for fillets and chamfers (DECISIONS D518 to D520).

- ``shared_edges``: the edges where two face sets meet (face fillet, face to
  face chamfer).
- ``full_round``: replace the centre faces between two parallel flat sides by a
  round tangent to both sides (full round fillet).
- ``edges_by_convexity``: the convex or concave edges of the part or of one
  feature (fillet assistant).
"""

from __future__ import annotations

import math

from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakeWire,
)
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.GC import GC_MakeArcOfCircle
from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt, gp_Vec
from OCP.TopAbs import TopAbs_FACE
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Face

from fdcad.core.document.model import Feature
from fdcad.core.features.base import BuildContext, FeatureError, Issue
from fdcad.core.features.modify import edges_of, require_body, resolve_faces
from fdcad.core.naming.names import NamedShape
from fdcad.core.occ import shape_list

Vec3 = tuple[float, float, float]
_TOL = 1e-6


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _scale(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def _add(*vs: Vec3) -> Vec3:
    return (sum(v[0] for v in vs), sum(v[1] for v in vs), sum(v[2] for v in vs))


def _unit(a: Vec3) -> Vec3:
    size = math.sqrt(_dot(a, a))
    return _scale(a, 1 / size)


def face_sets(
    feature: Feature, ctx: BuildContext, keys: tuple[str, ...], labels: tuple[str, ...]
) -> tuple[list[list[tuple[str, TopoDS_Face]]], list[Issue]]:
    """The picked faces of each set in ``keys``. A missing set is an error naming it."""
    out: list[list[tuple[str, TopoDS_Face]]] = []
    issues: list[Issue] = []
    for key, label in zip(keys, labels, strict=True):
        faces, found = resolve_faces(feature, ctx, key, required=False)
        if not faces:
            raise FeatureError(f"{feature.name}: {label} is empty. Pick its faces in the view.")
        issues.extend(found)
        out.append(faces)
    return out, issues


def shared_edges(
    owner: str, body: NamedShape, first: list[TopoDS_Face], second: list[TopoDS_Face]
) -> list[tuple[str, TopoDS_Edge]]:
    """Edges that belong to a face of ``first`` and a face of ``second``, named."""
    theirs = [e for f in second for e in edges_of(f)]
    out: list[tuple[str, TopoDS_Edge]] = []
    for face in first:
        for edge in edges_of(face):
            if any(edge.IsSame(x) for _n, x in out) or not any(edge.IsSame(t) for t in theirs):
                continue
            name = body.edge_name(edge)
            if name is not None:
                out.append((name, edge))
    if not out:
        raise FeatureError(
            f"{owner}: the two face sets do not meet at an edge. Pick faces that touch each other."
        )
    return out


# Full round ---------------------------------------------------------------------------


def _plane(owner: str, faces: list[tuple[str, TopoDS_Face]], label: str) -> tuple[Vec3, Vec3]:
    """Outward normal and a point of the one plane all ``faces`` lie on."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface

    from fdcad.core.features.face_picks import outward_normal

    normal: Vec3 | None = None
    point: Vec3 | None = None
    for _name, face in faces:
        n = outward_normal(face)
        if n is None:
            raise FeatureError(
                f"{owner}: the {label} must be flat for a full round. Pick flat faces."
            )
        loc = BRepAdaptor_Surface(face).Plane().Location()
        p = (loc.X(), loc.Y(), loc.Z())
        if normal is None or point is None:
            normal, point = n, p
            continue
        off = _dot(_add(p, _scale(point, -1)), normal)
        if _dot(n, normal) < 1 - _TOL or abs(off) > _TOL:
            raise FeatureError(
                f"{owner}: the faces of the {label} are not on one plane. "
                "Pick faces that lie on one flat plane."
            )
    assert normal is not None and point is not None
    return normal, point


def full_round(feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue], NamedShape]:
    """The part with the centre faces replaced by a round (D518 item 3).

    Returns the result, snapshot warnings and the cut tool (for tests and naming).
    """
    from fdcad.core.features.solids import combine, extent_along, is_valid, solids

    owner = feature.name
    body = require_body(feature, ctx)
    (side1, centre, side2), issues = face_sets(
        feature,
        ctx,
        ("faces1", "centre", "faces2"),
        ("Side Face Set 1", "Centre Face Set", "Side Face Set 2"),
    )
    n1, p1 = _plane(owner, side1, "first side")
    n2, p2 = _plane(owner, side2, "second side")
    m, c0 = _plane(owner, centre, "centre face")
    if abs(_dot(n1, n2)) < 1 - _TOL:
        raise FeatureError(
            f"{owner}: a full round needs two parallel side faces. "
            "Pick flat side faces that face away from each other."
        )
    gap = _dot(_add(p2, _scale(p1, -1)), n1)
    if abs(gap) < _TOL:
        raise FeatureError(
            f"{owner}: the two side faces lie on one plane. Pick the faces on both sides."
        )
    n = n1 if gap > 0 else _scale(n1, -1)  # from side 1 towards side 2
    width = abs(gap)
    radius = width / 2
    across = _cross(n, m)
    if math.sqrt(_dot(across, across)) < 1e-3:
        raise FeatureError(
            f"{owner}: the centre face is parallel to the sides. "
            "Pick the face between the two sides as the centre face."
        )
    axis = _unit(across)
    up = _unit(_cross(axis, n))
    if _dot(up, m) < 0:
        up = _scale(up, -1)

    def extent(shapes: list[TopoDS_Face], direction: Vec3) -> tuple[float, float]:
        from fdcad.core.features.solids import compound

        span = extent_along(compound(shapes), direction)
        assert span is not None
        base = _dot(p1, direction)
        return span[0] - base, span[1] - base

    centre_faces = [f for _n, f in centre]
    s_lo, s_hi = extent(centre_faces, n)
    if s_lo < -1e-4 or s_hi > width + 1e-4:
        raise FeatureError(
            f"{owner}: the centre face does not lie between the two side faces. "
            "Pick the face that joins the two sides."
        )
    # Height of the round's axis above p1 along ``up``: the round touches the centre plane.
    t_centre = (_dot(m, c0) - radius - _dot(m, p1) - radius * _dot(m, n)) / _dot(m, up)
    for faces, label in ((side1, "first side"), (side2, "second side")):
        low, _high = extent([f for _n, f in faces], up)
        if low > t_centre + 1e-4:
            raise FeatureError(
                f"{owner}: the {label} is shorter than half the width "
                f"({radius:.4g} mm), so the round does not fit. Use a constant size fillet."
            )
    l_lo, l_hi = extent(centre_faces, axis)
    _t_lo, t_hi = extent(centre_faces, up)
    top = max(t_hi, t_centre + radius) + width

    def at(s: float, t: float) -> gp_Pnt:
        x = _add(p1, _scale(n, s), _scale(up, t), _scale(axis, l_lo))
        return gp_Pnt(*x)

    a, b = at(0, t_centre), at(width, t_centre)
    # The circle's seam points down, away from the arc, so the round stays one face.
    centre_point = at(radius, t_centre)
    frame = gp_Ax2(centre_point, gp_Dir(*axis), gp_Dir(*_scale(up, -1)))
    arc = GC_MakeArcOfCircle(gp_Circ(frame, radius), b, a, True).Value()
    arc_edge = BRepBuilderAPI_MakeEdge(arc).Edge()
    wire = BRepBuilderAPI_MakeWire()
    wire.Add(arc_edge)
    for p, q in ((a, at(0, top)), (at(0, top), at(width, top)), (at(width, top), b)):
        wire.Add(BRepBuilderAPI_MakeEdge(p, q).Edge())
    face = BRepBuilderAPI_MakeFace(wire.Wire(), True).Face()
    maker = BRepPrimAPI_MakePrism(face, gp_Vec(*_scale(axis, l_hi - l_lo)))
    role = f"{feature.id}/full_round/{centre[0][0]}"
    round_faces: list[tuple[str, TopoDS_Face]] = []
    for made in shape_list(maker.Generated(arc_edge)):
        if made.ShapeType() == TopAbs_FACE and not any(made.IsSame(f) for _r, f in round_faces):
            round_faces.append((role, TopoDS.Face(made)))
    tool = NamedShape(maker.Shape(), round_faces)
    result = combine(feature.id, owner, body, tool, "cut")
    # The cut may report the round twice (once per side of the tool); keep one name.
    rounds = [f for n, f in result.faces if n.split("#")[0] == role]
    if rounds and all(f.IsSame(rounds[0]) for f in rounds):
        others = [(n, f) for n, f in result.faces if n.split("#")[0] != role]
        result = NamedShape(result.shape, [*others, (role, rounds[0])])
    if len(solids(result.shape)) != len(solids(body.shape)) or not is_valid(body, result):
        raise FeatureError(
            f"{owner}: the full round could not be built on these faces. "
            "Check that the side faces run the whole length of the centre face."
        )
    return result, issues, tool


# Fillet assistant ---------------------------------------------------------------------


def edges_by_convexity(
    body: NamedShape, convexity: str, faces: list[TopoDS_Face] | None = None
) -> list[tuple[str, TopoDS_Edge]]:
    """Named convex or concave edges of ``body``, or only of ``faces`` (D519 item 1).

    Smooth (tangent) edges and edges with one face are skipped.
    """
    from OCP.BRepOffset import BRepOffset_Analyse
    from OCP.ChFiDS import ChFiDS_Concave, ChFiDS_Convex

    wanted = ChFiDS_Convex if convexity == "convex" else ChFiDS_Concave
    analyse = BRepOffset_Analyse(body.shape, 0.01)
    edges = edges_of(body.shape) if faces is None else [e for f in faces for e in edges_of(f)]
    out: list[tuple[str, TopoDS_Edge]] = []
    for edge in edges:
        if any(edge.IsSame(e) for _n, e in out):
            continue
        types = [iv.Type() for iv in analyse.Type(edge)]
        if not types or any(t != wanted for t in types):
            continue
        name = body.edge_name(edge)
        if name is not None:
            out.append((name, edge))
    return out
