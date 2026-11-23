"""Hidden and isolated bodies of a multibody part (PHASE3_SPEC P3.4 item 6, DECISIONS D410).

A body is known by the names of its faces, the same way features refer to
bodies (D233). Hiding a body stores one of its face names in
``appearance.hidden_bodies``; a body is hidden while any of its face names is
listed, so the choice survives rebuilds that renumber the bodies. Hiding is
display only: hidden bodies still take part in features and exports.

Every function here is a small topology query or builds a compound of shapes
that already exist (DECISIONS D75), so the UI thread may call them. The ray
test of ``first_hit`` intersects geometry and runs in a kernel job.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from OCP.BRepIntCurveSurface import BRepIntCurveSurface_Inter
from OCP.gp import gp_Dir, gp_Lin, gp_Pnt
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SOLID, TopAbs_VERTEX
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.document.model import Document
from fdcad.core.features.solids import compound, solids
from fdcad.core.naming.names import NamedShape
from fdcad.core.occ import ShapeMap

HIDDEN_BODIES = "hidden_bodies"
#: Bodies drawn see through on their own (TR21, D753), marked the same way.
SEE_THROUGH_BODIES = "see_through_bodies"
#: Locked bodies (TR269, D836): drawn greyed, shown, but never picked.
LOCKED_BODIES = "locked_bodies"

Vec3 = tuple[float, float, float]


def _order(name: str) -> tuple[int, str]:
    return (len(name), name)


def _names(doc: Document, key: str) -> set[str]:
    value = doc.appearance.get(key)
    if not isinstance(value, list):
        return set()
    return {v for v in value if isinstance(v, str)}


def _set_names(doc: Document, key: str, names: Iterable[str]) -> None:
    kept = sorted(set(names), key=_order)
    doc.appearance.pop(key, None)
    if kept:
        doc.appearance[key] = kept


def hidden_names(doc: Document) -> set[str]:
    """Face names marking the bodies hidden on purpose (saved in the file)."""
    return _names(doc, HIDDEN_BODIES)


def set_hidden_names(doc: Document, names: Iterable[str]) -> None:
    """Store the hidden body marks, sorted; the key is left out while empty."""
    _set_names(doc, HIDDEN_BODIES, names)


def see_through_names(doc: Document) -> set[str]:
    """Face names marking the bodies drawn see through (TR21, saved in the file)."""
    return _names(doc, SEE_THROUGH_BODIES)


def set_see_through_names(doc: Document, names: Iterable[str]) -> None:
    """Store the see through body marks, sorted; the key is left out while empty."""
    _set_names(doc, SEE_THROUGH_BODIES, names)


def locked_names(doc: Document) -> set[str]:
    """Face names marking the locked bodies (TR269, saved in the file)."""
    return _names(doc, LOCKED_BODIES)


def set_locked_names(doc: Document, names: Iterable[str]) -> None:
    """Store the locked body marks, sorted; the key is left out while empty."""
    _set_names(doc, LOCKED_BODIES, names)


def body_names(named: NamedShape | None) -> list[frozenset[str]]:
    """The face names of every body, in Solid Bodies order."""
    if named is None:
        return []
    parts = solids(named.shape)
    maps = []
    for solid in parts:
        fmap = ShapeMap()
        TopExp.MapShapes_s(solid, TopAbs_FACE, fmap)
        maps.append(fmap)
    out: list[set[str]] = [set() for _ in parts]
    for name, face in named.faces:
        for i, fmap in enumerate(maps):
            if fmap.Contains(face):
                out[i].add(name)
                break
    return [frozenset(names) for names in out]


def mark_of(names: frozenset[str]) -> str | None:
    """The face name stored to hide a body: its shortest, first name."""
    return min(names, key=_order) if names else None


def hidden_indices(named: NamedShape | None, hidden: set[str]) -> list[int]:
    """Indices of the bodies with a face name in ``hidden``."""
    return [i for i, names in enumerate(body_names(named)) if names & hidden]


def marks_for(named: NamedShape | None, indices: Iterable[int]) -> set[str]:
    """The marks that hide the bodies at ``indices``."""
    all_names = body_names(named)
    out = set()
    for i in indices:
        if 0 <= i < len(all_names):
            mark = mark_of(all_names[i])
            if mark is not None:
                out.add(mark)
    return out


def without_bodies(hidden: set[str], named: NamedShape | None, indices: Iterable[int]) -> set[str]:
    """``hidden`` minus every mark that hides a body at ``indices`` (show them)."""
    all_names = body_names(named)
    out = set(hidden)
    for i in indices:
        if 0 <= i < len(all_names):
            out -= all_names[i]
    return out


def shown_shape(named: NamedShape | None, keep: Sequence[int]) -> TopoDS_Shape | None:
    """The bodies at ``keep`` as one shape for the view, or None when none is kept."""
    if named is None:
        return None
    parts = solids(named.shape)
    picked = [parts[i] for i in keep if 0 <= i < len(parts)]
    if not picked:
        return None
    if len(picked) == len(parts):
        return named.shape
    return picked[0] if len(picked) == 1 else compound(picked)


def visible_indices(
    named: NamedShape | None, hidden: set[str], isolated: set[str] | None = None
) -> list[int]:
    """Bodies to draw: not hidden, and while isolating, one of the isolated bodies.

    ``isolated`` holds face names like ``hidden``; None means no isolate.
    """
    out = []
    for i, names in enumerate(body_names(named)):
        if names & hidden:
            continue
        if isolated is not None and not names & isolated:
            continue
        out.append(i)
    return out


_KINDS = {TopAbs_FACE: TopAbs_FACE, TopAbs_EDGE: TopAbs_EDGE, TopAbs_VERTEX: TopAbs_VERTEX}


def body_of(shape: TopoDS_Shape, sub: TopoDS_Shape) -> int:
    """Index of the body holding the face, edge, vertex or solid ``sub``, or -1."""
    kind = sub.ShapeType()
    for i, solid in enumerate(solids(shape)):
        if kind == TopAbs_SOLID:
            if solid.IsSame(sub):
                return i
            continue
        if kind not in _KINDS:
            return -1
        found = ShapeMap()
        TopExp.MapShapes_s(solid, _KINDS[kind], found)
        if found.Contains(sub):
            return i
    return -1


def bodies_of(shape: TopoDS_Shape | None, picks: Iterable[TopoDS_Shape]) -> list[int]:
    """Distinct body indices of picked faces, edges or vertices, in pick order."""
    if shape is None:
        return []
    out: list[int] = []
    for pick in picks:
        index = body_of(shape, pick)
        if index >= 0 and index not in out:
            out.append(index)
    return out


def first_hit(
    named: NamedShape | None, indices: Sequence[int], origin: Vec3, direction: Vec3
) -> int | None:
    """The body among ``indices`` that the ray from ``origin`` meets first, or None.

    Kernel work: call it from a kernel job, not the UI thread.
    """
    if named is None:
        return None
    parts = solids(named.shape)
    line = gp_Lin(gp_Pnt(*origin), gp_Dir(*direction))
    best: tuple[float, int] | None = None
    for i in indices:
        if not 0 <= i < len(parts):
            continue
        inter = BRepIntCurveSurface_Inter()
        inter.Init(parts[i], line, 1e-7)
        while inter.More():
            w = inter.W()
            if w >= 0 and (best is None or w < best[0]):
                best = (w, i)
            inter.Next()
    return best[1] if best is not None else None
