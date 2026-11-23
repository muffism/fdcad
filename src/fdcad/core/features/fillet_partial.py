"""Partial edge fillets (PHASE2_SPEC P2.4 item 6, DECISIONS D519).

The kernel cannot round only part of an edge (a radius law may not drop to
zero), so each edge is handled in four steps:

1. The part is split by the planes square to the edge at the start and end
   points of the range.
2. In the piece that holds the middle of the range, that piece of the edge is
   rounded. The round ends square at the split planes.
3. The pieces are fused again and faces on the same surface are merged.

Face names are carried through every step. Faces only split and merged again
get their names back; new fillet faces are named ``fillet/<edge name>`` as for
a whole edge.

The same steps bevel part of an edge for Chamfer (TR64 item 5, D1012): a symmetric
distance chamfer, named ``chamfer/<edge name>``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.GCPnts import GCPnts_AbscissaPoint
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt, gp_Vec
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_ShapeEnum, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Shape

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureError
from fdcad.core.features.modify import MakerHistory
from fdcad.core.naming.names import NamedFace, NamedShape, carry, order_by_position, restrict
from fdcad.core.occ import BRepAlgoAPI_Fuse, BRepAlgoAPI_Splitter, ShapeList, shape_list

PARTIAL_KINDS = ("distance", "percent", "reference")  # reference: TR64 (D1401)
_MARK = "\x00"


def _all(shape: TopoDS_Shape, kind: TopAbs_ShapeEnum) -> list[TopoDS_Shape]:
    explorer = TopExp_Explorer(shape, kind)
    out: list[TopoDS_Shape] = []
    while explorer.More():
        out.append(explorer.Current())
        explorer.Next()
    return out


def _number(feature: Feature, name: str, label: str) -> float:
    value = feature.params.get(name)
    if not isinstance(value, Param):
        raise FeatureError(f"{feature.name}: the {label} is missing. Enter a value.")
    return value.value


def edge_range(
    feature: Feature,
    edge: TopoDS_Edge,
    name: str,
    ends: list[Any] | tuple[float, float] | None = None,
) -> tuple[float, float, float]:
    """Curve parameters of the start and end of the range on ``edge``, and its middle.

    Distances and percentages are measured along the edge from its first end, or
    from its other end with ``partial_flip``. ``ends`` (kind "reference", TR64,
    D1401) are the two resolved end picks; flip does not apply to them.
    """
    kind = feature.params.get("partial")
    curve = BRepAdaptor_Curve(edge)
    u0, u1 = curve.FirstParameter(), curve.LastParameter()
    total = GCPnts_AbscissaPoint.Length_s(curve)
    if isinstance(ends, tuple):  # TR271 (D1407): the range in mm, worked out already
        start, end = ends
    elif kind == "reference":
        from fdcad.core.features.partial_refs import lengths

        if ends is None:
            raise FeatureError(f"{feature.name}: pick the two partial ends. Pick them again.")
        start, end = lengths(feature.name, edge, name, ends)
    elif kind == "percent":
        start = _number(feature, "start_percent", "start percent") / 100 * total
        end = _number(feature, "end_percent", "end percent") / 100 * total
    else:
        start = _number(feature, "start_distance", "start distance")
        end = _number(feature, "end_distance", "end distance")
    if not 0 <= start < end <= total + 1e-9:
        raise FeatureError(
            f"{feature.name}: the partial range on edge {name} must start before it ends and "
            f"stay on the edge (0 to {total:.4g} mm long). Change the start or the end."
        )
    if (
        feature.params.get("partial_flip") is True
        and kind != "reference"
        and not isinstance(ends, tuple)
    ):
        start, end = total - end, total - start

    def at(length: float) -> float:
        if length <= 0:
            return float(u0)
        if length >= total:
            return float(u1)
        return float(GCPnts_AbscissaPoint(curve, length, u0).Parameter())

    return at(start), at(end), at((start + end) / 2)


def _marked(named: list[NamedFace], marks: list[str]) -> list[NamedFace]:
    out: list[NamedFace] = []
    for name, face in named:
        out.append((f"{_MARK}{len(marks)}", face))
        marks.append(name)
    return out


def _unmarked(named: list[NamedFace], marks: list[str]) -> list[NamedFace]:
    """Real names again: pieces of one face that merged back take its name."""
    groups: dict[int, list[TopoDS_Shape]] = {}
    out: list[NamedFace] = []
    for name, face in named:
        if not name.startswith(_MARK):
            out.append((name, face))
            continue
        index = int(name[1:].split("#")[0])
        faces = groups.setdefault(index, [])
        if not any(face.IsSame(f) for f in faces):
            faces.append(face)
    for index, faces in sorted(groups.items()):
        if len(faces) == 1:
            out.append((marks[index], TopoDS.Face(faces[0])))
        else:
            pieces = order_by_position([TopoDS.Face(f) for f in faces])
            out.extend((f"{marks[index]}#{k}", f) for k, f in enumerate(pieces, start=1))
    return out


def _one_edge(
    fid: str,
    current: NamedShape,
    edge: TopoDS_Edge,
    span: tuple[float, float, float],
    radius: float,
    role: str,
    marks: list[str],
    chamfer: bool = False,
    split_ends: tuple[bool, bool] = (False, False),
    apply: Callable[[Any, TopoDS_Edge], None] | None = None,
) -> NamedShape | None:
    """Round (or bevel) the ``span`` of ``edge`` in its own split piece of ``current``.

    ``split_ends`` forces a split at the start or end of the span even when it is an
    end of the edge (TR131, D1400: the round stops at a smooth join). ``apply`` adds
    the edge to the maker itself (a radius law) instead of one constant ``radius``.
    """
    curve = BRepAdaptor_Curve(edge)
    u0, u1 = curve.FirstParameter(), curve.LastParameter()
    ua, ub, middle = span
    from fdcad.core.features.solids import bounding_size

    size = 2 * bounding_size(current.shape) + 10
    tools = ShapeList()
    for u, force in zip((ua, ub), split_ends, strict=True):
        if not force and (abs(u - u0) < 1e-9 or abs(u - u1) < 1e-9):
            continue
        p, v = gp_Pnt(), gp_Vec()
        curve.D1(u, p, v)
        plane = gp_Pln(p, gp_Dir(v))
        tools.Append(BRepBuilderAPI_MakeFace(plane, -size, size, -size, size).Face())
    if tools.Size() == 0:  # the range covers the whole edge: nothing to split (D609)
        split = list(current.faces)
        pieces = _all(current.shape, TopAbs_SOLID)
    else:
        args = ShapeList()
        args.Append(current.shape)
        splitter = BRepAlgoAPI_Splitter()
        splitter.SetArguments(args)
        splitter.SetTools(tools)
        splitter.Build()
        if not splitter.IsDone():
            return None
        split = carry(current.faces, splitter.History())
        pieces = _all(splitter.Shape(), TopAbs_SOLID)
    target = curve.Value(middle)
    chosen: tuple[TopoDS_Shape, TopoDS_Edge] | None = None
    for piece in pieces:
        for e in _all(piece, TopAbs_EDGE):
            c = BRepAdaptor_Curve(TopoDS.Edge(e))
            if c.Value((c.FirstParameter() + c.LastParameter()) / 2).Distance(target) < 1e-6:
                chosen = (piece, TopoDS.Edge(e))
                break
        if chosen:
            break
    if chosen is None:
        return None
    solid, piece_edge = chosen
    maker: Any
    if chamfer:  # TR64 (D1012): ``radius`` is the chamfer distance
        from OCP.BRepFilletAPI import BRepFilletAPI_MakeChamfer

        maker = BRepFilletAPI_MakeChamfer(solid)
        maker.Add(radius, piece_edge)
    elif apply is not None:
        maker = BRepFilletAPI_MakeFillet(solid)
        apply(maker, piece_edge)
    else:
        maker = BRepFilletAPI_MakeFillet(solid)
        maker.Add(radius, piece_edge)
    maker.Build()
    if not maker.IsDone():
        return None
    in_solid = _all(solid, TopAbs_FACE)
    mine = [(n, f) for n, f in split if any(f.IsSame(g) for g in in_solid)]
    rest = [(n, f) for n, f in split if not any(f.IsSame(g) for g in in_solid)]
    named = carry(mine, MakerHistory(maker)) + rest
    made: list[TopoDS_Shape] = []
    for s in shape_list(maker.Generated(piece_edge)):
        if s.ShapeType() == TopAbs_FACE and not any(s.IsSame(f) for f in made):
            made.append(s)
    named += [(f"{_MARK}{len(marks)}", TopoDS.Face(f)) for f in made]
    marks.append(role)
    first, others = ShapeList(), ShapeList()
    first.Append(maker.Shape())
    for piece in pieces:
        if not piece.IsSame(solid):
            others.Append(piece)
    joined = maker.Shape()
    if others.Size():
        fuse = BRepAlgoAPI_Fuse()
        fuse.SetArguments(first)
        fuse.SetTools(others)
        fuse.Build()
        if not fuse.IsDone():
            return None
        named = carry(named, fuse.History())
        joined = fuse.Shape()
    from fdcad.core.unify import unify_faces

    shape, history = unify_faces(joined)
    if history is not None:
        named = carry(named, history)
    if len(_all(shape, TopAbs_SOLID)) != 1:
        return None
    return NamedShape(shape, restrict(named, shape, f"{fid}/corner"))


def partial_chamfer(
    feature: Feature,
    body: NamedShape,
    edges: list[tuple[str, TopoDS_Edge]],
    distance: float,
    ends: list[Any] | None = None,
) -> NamedShape:
    """Bevel the partial range of every edge, one edge at a time (TR64, D1012)."""
    return partial_fillet(feature, body, edges, lambda _name: distance, chamfer=True, ends=ends)


def partial_fillet(
    feature: Feature,
    body: NamedShape,
    edges: list[tuple[str, TopoDS_Edge]],
    radius_of: Callable[[str], float],
    chamfer: bool = False,
    ends: list[Any] | None = None,
    spans_of: Callable[[str, TopoDS_Edge], tuple[float, float]] | None = None,
) -> NamedShape:
    """Round the partial range of every edge, one edge at a time."""
    from fdcad.core.features.solids import is_valid, solids

    what, size = ("chamfer", "distance") if chamfer else ("fillet", "radius")
    if len(solids(body.shape)) != 1 and chamfer:
        raise FeatureError(
            f"{feature.name}: partial edge chamfers work on a part with one body. "
            "Turn off Partial Edges, or split the part first."
        )
    if len(solids(body.shape)) != 1:
        raise FeatureError(
            f"{feature.name}: partial edge fillets work on a part with one body. "
            "Round whole edges, or split the part first."
        )
    if spans_of is not None:  # TR271 (D1407): each edge's own range
        spans = [edge_range(feature, edge, name, spans_of(name, edge)) for name, edge in edges]
    else:
        spans = [edge_range(feature, edge, name, ends) for name, edge in edges]
    marks: list[str] = []
    current = NamedShape(body.shape, _marked(list(body.faces), marks))
    for (name, edge), span in zip(edges, spans, strict=True):
        role = f"{feature.id}/{what}/{name}"
        try:
            step = _one_edge(feature.id, current, edge, span, radius_of(name), role, marks, chamfer)
        except Exception:  # kernel failure: reported below
            step = None
        if step is None:
            raise FeatureError(
                f"{feature.name}: the partial {what} on edge {name} failed. "
                f"Reduce the {size}, or move the start and end away from the corners."
            )
        current = step
    result = NamedShape(current.shape, _unmarked(current.faces, marks))
    if not is_valid(body, result):
        raise FeatureError(
            f"{feature.name}: the partial {what} made invalid geometry. "
            f"Reduce the {size}, or change the start or end."
        )
    return result
