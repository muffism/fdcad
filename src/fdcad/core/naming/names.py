"""Persistent face names carried through kernel operations (PLAN section 6, FDEF_SPEC 8).

A :class:`NamedShape` is a solid (or compound of solids) plus a name list for
its faces. A face may carry several names when faces merge; every one of them
still resolves. Edges and vertices are named from their neighbouring faces.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Face, TopoDS_Shape, TopoDS_Vertex

from fdcad.core.occ import ShapeList, ShapeListMap, ShapeMap, shape_list

NamedFace = tuple[str, TopoDS_Face]


class History(Protocol):
    """What naming needs from an operation's history (BRepTools_History and booleans)."""

    def Modified(self, shape: TopoDS_Shape, /) -> ShapeList: ...  # noqa: N802

    def IsRemoved(self, shape: TopoDS_Shape, /) -> bool: ...  # noqa: N802


def faces_of(shape: TopoDS_Shape) -> list[TopoDS_Face]:
    """Distinct faces of ``shape`` in a stable order."""
    fmap = ShapeMap()
    TopExp.MapShapes_s(shape, TopAbs_FACE, fmap)
    return [TopoDS.Face(fmap.FindKey(i)) for i in range(1, fmap.Extent() + 1)]


def _list(shapes: ShapeList) -> list[TopoDS_Shape]:
    return shape_list(shapes)


def centroid(shape: TopoDS_Shape) -> tuple[float, float, float]:
    """Centre of area of a face (or of mass for other shapes)."""
    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(shape, props)
    p = props.CentreOfMass()
    return p.X(), p.Y(), p.Z()


#: Centroid coordinates nearer than this, in mm, count as equal when faces are put in
#: order (FDEF_SPEC 8.2 orders to six decimals).
ORDER_TOLERANCE = 1e-6


def order_by_position(faces: Sequence[TopoDS_Face]) -> list[TopoDS_Face]:
    """Faces sorted by centroid X, then Y, then Z (FDEF_SPEC 8.2).

    Coordinates within ``ORDER_TOLERANCE`` of each other count as equal, and the next
    coordinate decides (D1052). The coordinates used to be rounded to six decimals
    instead. Two mirror image faces have the same X and Y but for the last digits of
    the arithmetic, and when their X fell on either side of a rounding step, that
    noise ordered them, not their Z. Such faces swapped their numbers between a part
    as built and the same part opened from its file, where numbers are stored to
    twelve digits.

    One face needs no order, so its centroid is not measured (D2661): on a thread's
    spline face that took about 0.1 s for nothing.
    """
    if len(faces) < 2:
        return list(faces)
    placed = [(centroid(face), face) for face in faces]
    return [face for _point, face in _in_order(placed, 0)]


def in_order(shape: TopoDS_Shape) -> list[TopoDS_Face]:
    """The faces of ``shape`` in position order, for numbering them (D1068).

    The order in which the kernel lists the faces of a shape it made (a boolean, an
    offset) is not the same from one run to the next, so numbers given in that order
    named different faces in a session and in the part opened from its file.
    """
    return order_by_position(faces_of(shape))


def _in_order(
    placed: list[tuple[tuple[float, float, float], TopoDS_Face]], axis: int
) -> list[tuple[tuple[float, float, float], TopoDS_Face]]:
    """``placed`` sorted along ``axis``; runs of equal values sorted by the next axis."""
    if len(placed) < 2 or axis > 2:
        return placed
    ordered = sorted(placed, key=lambda item: item[0][axis])
    out: list[tuple[tuple[float, float, float], TopoDS_Face]] = []
    run = [ordered[0]]
    for item in ordered[1:]:
        if item[0][axis] - run[-1][0][axis] <= ORDER_TOLERANCE:
            run.append(item)
            continue
        out.extend(_in_order(run, axis + 1))
        run = [item]
    out.extend(_in_order(run, axis + 1))
    return out


@dataclass
class _Lookup:
    """What ``NamedShape`` keeps to name edges and vertices quickly (D1058)."""

    key: tuple[int, int]
    faces: ShapeMap
    #: Face index in ``faces`` to the face's first name.
    first: dict[int, str]
    #: Edge or vertex kind to its map of neighbouring faces.
    ancestors: dict[int, ShapeListMap] = field(default_factory=dict)
    by_name: dict[str, list[TopoDS_Edge]] | None = None


@dataclass
class NamedShape:
    """A shape with names for its faces."""

    shape: TopoDS_Shape
    faces: list[NamedFace] = field(default_factory=list)

    def face(self, name: str) -> TopoDS_Face | None:
        """The face called ``name``, or None when the name does not resolve."""
        for n, f in self.faces:
            if n == name:
                return f
        return None

    def names_of(self, face: TopoDS_Shape) -> list[str]:
        """All names of ``face``, in the order they were given."""
        return [n for n, f in self.faces if f.IsSame(face)]

    def primary_name(self, face: TopoDS_Shape) -> str | None:
        """The first name of ``face``: the one used to name its edges and vertices."""
        names = self.names_of(face)
        return names[0] if names else None

    def _lookup(self) -> _Lookup:
        """Maps for naming edges and vertices, made once for this shape (D1058).

        Naming one edge used to map every edge of the part to its faces again, and
        finding an edge by name named every edge: for the four corners of a cover on
        a housing of 1900 edges that was 15 000 maps and 30 seconds. The maps are made
        again when the shape or the number of names has changed.
        """
        key = (id(self.shape), len(self.faces))
        kept = self.__dict__.get("_kept_lookup")
        if kept is None or kept.key != key:
            fmap = ShapeMap()
            TopExp.MapShapes_s(self.shape, TopAbs_FACE, fmap)
            first: dict[int, str] = {}
            for name, face in self.faces:
                index = fmap.FindIndex(face)
                if index and index not in first:
                    first[index] = name
            kept = _Lookup(key, fmap, first)
            self.__dict__["_kept_lookup"] = kept
        return kept

    def _ancestor_names(self, sub: TopoDS_Shape, kind: int) -> list[str]:
        kept = self._lookup()
        amap = kept.ancestors.get(kind)
        if amap is None:
            amap = ShapeListMap()
            TopExp.MapShapesAndAncestors_s(self.shape, kind, TopAbs_FACE, amap)
            kept.ancestors[kind] = amap
        index = amap.FindIndex(sub)
        if index == 0:
            return []
        names = {kept.first.get(kept.faces.FindIndex(f)) for f in _list(amap.FindFromIndex(index))}
        return sorted(n for n in names if n is not None)

    def edge_name(self, edge: TopoDS_Edge) -> str | None:
        """``edge(<face>|<face>)`` from the two neighbouring faces (FDEF_SPEC 8.3)."""
        names = self._ancestor_names(edge, TopAbs_EDGE)
        if not names:
            return None
        if len(names) == 1:
            names = names * 2  # seam edge: the same face on both sides
        return f"edge({'|'.join(names)})"

    def vertex_name(self, vertex: TopoDS_Vertex) -> str | None:
        """``vertex(<face>|<face>|...)`` from its neighbouring faces (FDEF_SPEC 8.4)."""
        names = self._ancestor_names(vertex, TopAbs_VERTEX)
        return f"vertex({'|'.join(names)})" if len(names) >= 3 else None

    def edge(self, name: str) -> TopoDS_Edge | None:
        """The edge called ``name``, or None."""
        found = self.edges(name)
        return found[0] if found else None

    def edges(self, name: str) -> list[TopoDS_Edge]:
        """Every edge called ``name``. Two faces can meet along several edges (D606)."""
        kept = self._lookup()
        if kept.by_name is None:
            emap = ShapeMap()
            TopExp.MapShapes_s(self.shape, TopAbs_EDGE, emap)
            by_name: dict[str, list[TopoDS_Edge]] = {}
            for i in range(1, emap.Extent() + 1):
                edge = TopoDS.Edge(emap.FindKey(i))
                label = self.edge_name(edge)
                if label is not None:
                    by_name.setdefault(label, []).append(edge)
            kept.by_name = by_name
        return list(kept.by_name.get(name, []))


def carry(named: Iterable[NamedFace], history: History) -> list[NamedFace]:
    """Follow named faces through one operation.

    Unchanged faces keep their names, a face modified into one face passes its
    name on, and a face split into several gives ``name#1``, ``name#2`` and so
    on, ordered by position. Removed faces drop out.
    """
    out: list[NamedFace] = []
    for name, face in named:
        if history.IsRemoved(face):
            continue
        modified = [
            TopoDS.Face(s) for s in _list(history.Modified(face)) if s.ShapeType() == TopAbs_FACE
        ]
        if not modified:
            out.append((name, face))
        elif len(modified) == 1:
            out.append((name, modified[0]))
        else:
            for k, piece in enumerate(order_by_position(modified), start=1):
                out.append((f"{name}#{k}", piece))
    return out


def restrict(
    named: Iterable[NamedFace], shape: TopoDS_Shape, fallback_prefix: str
) -> list[NamedFace]:
    """Keep only names of faces that exist in ``shape``; name any leftover face.

    Leftover faces get ``<fallback_prefix>/face#k``. That should not happen; when
    it does, references to them will fall back to their position snapshot.
    """
    fmap = ShapeMap()
    TopExp.MapShapes_s(shape, TopAbs_FACE, fmap)
    kept: list[NamedFace] = []
    seen: set[tuple[str, int]] = set()
    named_index: set[int] = set()
    for name, face in named:
        index = fmap.FindIndex(face)
        if index == 0 or (name, index) in seen:
            continue
        seen.add((name, index))
        named_index.add(index)
        kept.append((name, TopoDS.Face(fmap.FindKey(index))))
    leftovers = [
        TopoDS.Face(fmap.FindKey(i)) for i in range(1, fmap.Extent() + 1) if i not in named_index
    ]
    for k, face in enumerate(order_by_position(leftovers), start=1):
        kept.append((f"{fallback_prefix}/face#{k}", face))
    return kept
