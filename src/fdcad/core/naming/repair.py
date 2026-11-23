"""Find lost references and offer one clear replacement for each (TR125, D795).

A reference is lost when its face, edge or vertex cannot be found on the part
before its feature (``resolve``), or when it points at a feature that no longer
exists (a pattern seed). For a lost face, edge or vertex the part is searched
for one clear match to the stored position snapshot: same kind of surface or
curve, facing the same way, and clearly nearer (and closer in size) than any
other. Nothing is changed here: the user confirms every replacement
(CLAUDE.md section 5 item 12). No Qt.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from fdcad.core.document.model import Document, Feature
from fdcad.core.features.base import FeatureError, FeatureResult
from fdcad.core.naming import weak
from fdcad.core.naming.names import NamedShape

#: A step from ``feature.refs`` down to one reference: a key or a list index.
Path = tuple[str | int, ...]
_TOPOLOGY = ("face", "edge", "vertex")
#: A match farther than this many times the picked item's size is no match.
_REACH = 3.0
#: ... but never nearer than this (mm), so small items moved a little still match.
_MIN_REACH = 5.0


@dataclass(frozen=True)
class LostRef:
    """One lost reference of one feature, with the replacement offered (or None)."""

    fid: str
    feature_name: str
    path: Path
    ref: dict[str, Any]
    #: The new reference to use, or None when no single clear match exists.
    suggestion: dict[str, Any] | None

    @property
    def kind(self) -> str:
        """``face``, ``edge``, ``vertex`` or ``feature`` (a seed or other feature pick)."""
        return str(self.ref.get("kind", "feature"))

    @property
    def name(self) -> str:
        """The stored name, or the id of the missing feature."""
        return str(self.ref.get("name", self.ref.get("feature", "")))


def references(refs: Any, path: Path = ()) -> Iterator[tuple[Path, dict[str, Any]]]:
    """Every face, edge, vertex or feature reference in ``refs``, with its path."""
    if isinstance(refs, dict):
        if refs.get("kind") in _TOPOLOGY and "name" in refs:
            yield path, refs
            return
        if isinstance(refs.get("feature"), str) and "kind" not in refs:
            yield path, refs
        for key, value in refs.items():
            if isinstance(value, dict | list):
                yield from references(value, (*path, key))
    elif isinstance(refs, list):
        for index, value in enumerate(refs):
            yield from references(value, (*path, index))


def _lost(body: NamedShape | None, ref: dict[str, Any], doc: Document) -> bool:
    from fdcad.core.naming.resolve import resolve_edge, resolve_face, resolve_vertex

    kind = ref.get("kind")
    if kind is None:  # a feature pick: lost when the feature was deleted
        return not any(f.id == ref.get("feature") for f in doc.features)
    if body is None:
        return False  # nothing to check against; the feature reports the empty part
    resolver = {"face": resolve_face, "edge": resolve_edge, "vertex": resolve_vertex}[str(kind)]
    try:
        resolver(body, ref, "")
    except FeatureError:
        return True
    except Exception:  # a kernel failure on a damaged shape: leave it to the rebuild
        return False
    return False


def find_lost(
    doc: Document,
    results: Mapping[str, FeatureResult],
    only: Sequence[str] | None = None,
) -> list[LostRef]:
    """Every lost reference of the part (or of the features in ``only``), in tree order.

    Only features that report an error or a warning are checked, so a part that
    built cleanly costs nothing. Run it on a worker thread: it resolves against
    the part (CLAUDE.md rule 2).
    """
    from fdcad.core.features.preview import body_before

    out: list[LostRef] = []
    for feature in doc.features:
        if feature.suppressed or (only is not None and feature.id not in only):
            continue
        result = results.get(feature.id)
        if result is None or not result.issues:
            continue
        body = body_before(doc, feature, results)
        for path, ref in references(feature.refs):
            if _lost(body, ref, doc):
                offer = suggest(body, ref) if body is not None else None
                out.append(LostRef(feature.id, feature.name, path, copy.deepcopy(ref), offer))
    return out


def _candidates(body: NamedShape, kind: str) -> list[tuple[Any, dict[str, Any]]]:
    """(shape, snapshot) for every face, edge or vertex of ``body``."""
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_VERTEX
    from OCP.TopExp import TopExp
    from OCP.TopoDS import TopoDS

    from fdcad.core.naming.names import faces_of
    from fdcad.core.naming.resolve import face_snapshot
    from fdcad.core.naming.select import curve_snapshot, vertex_snapshot
    from fdcad.core.occ import ShapeMap

    if kind == "face":
        return [(f, face_snapshot(f)) for f in faces_of(body.shape)]
    smap = ShapeMap()
    TopExp.MapShapes_s(body.shape, TopAbs_EDGE if kind == "edge" else TopAbs_VERTEX, smap)
    shapes = [smap.FindKey(i) for i in range(1, smap.Extent() + 1)]
    if kind == "edge":
        return [(e, curve_snapshot(TopoDS.Edge(e))) for e in shapes]
    return [(v, vertex_snapshot(v)) for v in shapes]


def _score(stored: dict[str, Any], current: dict[str, Any]) -> float:
    """How far apart two snapshots are: the move, plus the change in size."""
    return weak.distance(stored, current) + abs(weak.size(stored) - weak.size(current))


def suggest(body: NamedShape, ref: dict[str, Any]) -> dict[str, Any] | None:
    """The one clear replacement for a lost face, edge or vertex, or None.

    Clear means: compatible with the snapshot (same surface or curve kind, same
    side), within reach (three times the item's size, at least 5 mm) and scoring
    at least a third better than the next candidate. Faces or edges whose name
    has the same root as the lost one are tried first, so a renumbered piece of
    the same feature wins over a look alike elsewhere.
    """
    from fdcad.core.naming.select import reference_for

    kind = str(ref.get("kind", ""))
    stored = ref.get("snapshot")
    if kind not in _TOPOLOGY or not isinstance(stored, dict):
        return None
    reach = max(_REACH * weak.size(stored), _MIN_REACH)
    ranked: list[tuple[float, Any]] = []
    for shape, snap in _candidates(body, kind):
        if kind != "vertex" and not weak.compatible(stored, snap):
            continue
        score = _score(stored, snap)
        if score <= reach:
            ranked.append((score, shape))
    if not ranked:
        return None
    ranked.sort(key=lambda pair: pair[0])
    root = weak.family_root(str(ref.get("name", "")))
    family = []
    for score, shape in ranked:
        new = reference_for(body, shape)
        if new is not None and weak.family_root(str(new.get("name", ""))) == root:
            family.append((score, shape))
    for pool in (family, ranked):
        pick = _clear(pool)
        if pick is not None:
            new = reference_for(body, pick)
            if new is not None:
                return new
    return None


def _clear(ranked: list[tuple[float, Any]]) -> Any:
    """The best of ``ranked`` (sorted) when it clearly beats the next one, else None."""
    if not ranked:
        return None
    best = ranked[0][0]
    if len(ranked) == 1 or ranked[1][0] >= weak.CLEAR_RATIO * best + weak.POINT_TOL:
        return ranked[0][1]
    return None


def replaced(feature: Feature, changes: Sequence[tuple[Path, dict[str, Any] | None]]) -> Feature:
    """A copy of ``feature`` with each reference at a path replaced, or removed (None).

    Removals inside one list run from the last index down, so earlier paths stay valid.
    """
    out = copy.deepcopy(feature)
    order = sorted(changes, key=lambda c: tuple(_sortable(p) for p in c[0]), reverse=True)
    for path, new in order:
        if not path:
            continue
        holder: Any = out.refs
        try:
            for step in path[:-1]:
                holder = holder[step]
            last = path[-1]
            if new is not None:
                holder[last] = copy.deepcopy(new)
            elif isinstance(holder, list) and isinstance(last, int):
                del holder[last]
            elif isinstance(holder, dict):
                holder.pop(last, None)
        except (KeyError, IndexError, TypeError):
            continue  # the reference moved since it was found: leave it
    _drop_empty(out.refs)
    return out


def _sortable(step: str | int) -> tuple[int, str, int]:
    return (1, "", step) if isinstance(step, int) else (0, step, 0)


def _drop_empty(refs: dict[str, Any]) -> None:
    """Remove top level lists left empty, so a feature with no picks says so plainly."""
    for key in [k for k, v in refs.items() if isinstance(v, list) and not v]:
        del refs[key]


def describe(lost: LostRef, doc: Document) -> str:
    """One line for a lost reference, for lists and messages."""
    if lost.kind == "feature":
        return f"{lost.feature_name}: the picked feature {lost.name} was deleted."
    return f"{lost.feature_name}: {lost.kind} {lost.name} is missing."


def total_distance(a: Mapping[str, Any], b: Mapping[str, Any]) -> float:
    """How far a replacement is from where the lost item was, for the list (mm)."""
    pa, pb = a.get("snapshot"), b.get("snapshot")
    if not isinstance(pa, dict) or not isinstance(pb, dict):
        return math.nan
    return weak.distance(pa, pb)


def ghost(ref: Mapping[str, Any]) -> Any:
    """A shape drawn where a lost item was, from its snapshot (TR125 item 2), or None.

    A flat face becomes a disc of the same area facing the same way; a round face a
    ring around its axis; a straight edge a line of its length; a round edge its
    circle; anything else, or a vertex, a small cross at its centre. Kernel work:
    call it from a worker thread.
    """
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace
    from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt

    snap = ref.get("snapshot")
    if not isinstance(snap, dict):
        return None
    point = snap.get("point", snap.get("midpoint"))
    if not isinstance(point, list) or len(point) != 3:
        return None
    centre = gp_Pnt(*(float(v) for v in point))
    try:
        if isinstance(snap.get("normal"), list):
            radius = math.sqrt(max(float(snap.get("area", 1.0)), 1e-6) / math.pi)
            circle = gp_Circ(gp_Ax2(centre, gp_Dir(*snap["normal"])), radius)
            from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeWire

            wire = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(circle).Edge()).Wire()
            return BRepBuilderAPI_MakeFace(wire).Face()
        axis = snap.get("axis")
        if isinstance(axis, list) and len(axis) == 6:
            radius = float(snap.get("radius", 0.0)) or max(weak.size(snap) / 2, 0.5)
            circle = gp_Circ(gp_Ax2(gp_Pnt(*axis[:3]), gp_Dir(*axis[3:])), radius)
            return BRepBuilderAPI_MakeEdge(circle).Edge()
        direction = snap.get("direction")
        if isinstance(direction, list) and len(direction) == 3:
            half = float(snap.get("length", 1.0)) / 2
            a = gp_Pnt(*(c - d * half for c, d in zip(point, direction, strict=True)))
            b = gp_Pnt(*(c + d * half for c, d in zip(point, direction, strict=True)))
            return BRepBuilderAPI_MakeEdge(a, b).Edge()
        return _cross(point, max(weak.size(snap) / 4, 1.0))
    except Exception:  # a damaged snapshot: draw nothing
        return None


def _cross(point: Sequence[float], size: float) -> Any:
    from OCP.BRep import BRep_Builder
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.gp import gp_Pnt
    from OCP.TopoDS import TopoDS_Compound

    compound = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(compound)
    for axis in range(3):
        a = [float(v) for v in point]
        b = list(a)
        a[axis] -= size
        b[axis] += size
        builder.Add(compound, BRepBuilderAPI_MakeEdge(gp_Pnt(*a), gp_Pnt(*b)).Edge())
    return compound
