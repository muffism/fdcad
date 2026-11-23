"""Selection sets (TR94, D944).

A selection set has a name and one of:

- ``items``: the stable names of picked faces, edges and vertices;
- ``rule``: a pick by property that runs again each time the set is used:
  ``{"kind": "feature", "feature": fid}`` (the faces a feature made),
  ``{"kind": "colour", "colour": "#RRGGBB"}`` (the faces drawn in that colour) or
  ``{"kind": "edge_length", "min": mm}`` (the edges at least that long);
- ``combine``: ``{"op": "union" | "subtract" | "intersect", "of": [set names]}``.

Sets are kept in the part (``Document.extra["selection_sets"]``). Using a set picks
what it resolves to now; names that no longer resolve are skipped and counted. No Qt;
resolving calls the kernel, so the UI runs it in a background job.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fdcad.core.document.model import Document
from fdcad.core.naming.names import NamedShape

#: Where the sets are kept in the part.
KEY = "selection_sets"
RULE_KINDS = ("feature", "colour", "edge_length")
OPS = ("union", "subtract", "intersect")


class SelectionSetError(ValueError):
    """A set cannot be made or used; the message says why and what to do."""


def sets_of(doc: Document) -> list[dict[str, Any]]:
    """The part's selection sets (copies), in the order they were made."""
    raw = doc.extra.get(KEY)
    if not isinstance(raw, list):
        return []
    return [dict(s) for s in raw if isinstance(s, dict) and isinstance(s.get("name"), str)]


def with_set(sets: list[dict[str, Any]], new: dict[str, Any]) -> list[dict[str, Any]]:
    """``sets`` with ``new`` added, or replacing the set of the same name."""
    name = str(new.get("name", "")).strip()
    if not name:
        raise SelectionSetError("A selection set needs a name. Type a name.")
    out = [s for s in sets if s.get("name") != name]
    out.append({**new, "name": name})
    return out


def names_for(named: NamedShape, shapes: list[Any]) -> list[str]:
    """Stable names of picked faces, edges and vertices; picks without one are left out."""
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
    from OCP.TopoDS import TopoDS

    out: list[str] = []
    for shape in shapes:
        kind = shape.ShapeType()
        name: str | None = None
        if kind == TopAbs_FACE:
            name = named.primary_name(shape)
        elif kind == TopAbs_EDGE:
            name = named.edge_name(TopoDS.Edge(shape))
        elif kind == TopAbs_VERTEX:
            name = named.vertex_name(TopoDS.Vertex(shape))
        if name is not None and name not in out:
            out.append(name)
    return out


@dataclass
class Resolved:
    """What a set picks now, and how many saved names no longer resolve."""

    shapes: list[Any] = field(default_factory=list)
    missing: int = 0


def _vertex(named: NamedShape, name: str) -> Any:
    from OCP.TopAbs import TopAbs_VERTEX
    from OCP.TopExp import TopExp
    from OCP.TopoDS import TopoDS

    from fdcad.core.occ import ShapeMap

    found = ShapeMap()
    TopExp.MapShapes_s(named.shape, TopAbs_VERTEX, found)
    for i in range(1, found.Extent() + 1):
        vertex = TopoDS.Vertex(found.FindKey(i))
        if named.vertex_name(vertex) == name:
            return vertex
    return None


def _from_names(named: NamedShape, names: list[str]) -> Resolved:
    out = Resolved()
    for name in names:
        if name.startswith("edge("):
            edges = named.edges(name)
            out.shapes += edges
            out.missing += 0 if edges else 1
        elif name.startswith("vertex("):
            vertex = _vertex(named, name)
            if vertex is None:
                out.missing += 1
            else:
                out.shapes.append(vertex)
        else:
            face = named.face(name)
            if face is None:
                out.missing += 1
            else:
                out.shapes.append(face)
    return out


def _from_rule(doc: Document, named: NamedShape, rule: dict[str, Any]) -> Resolved:
    kind = rule.get("kind")
    if kind == "feature":
        prefix = f"{rule.get('feature')}/"
        faces: list[Any] = []
        for name, face in named.faces:
            if name.startswith(prefix) and not any(face.IsSame(f) for f in faces):
                faces.append(face)
        return Resolved(faces)
    if kind == "colour":
        from fdcad.core.appearance import face_colors, part_color, propagating

        wanted = str(rule.get("colour", "")).upper()
        coloured = face_colors(named, doc.appearance, propagating(doc))
        if wanted == part_color(doc.appearance).upper():
            others = [f for f, _c in coloured]
            plain = [f for _n, f in named.faces if not any(f.IsSame(o) for o in others)]
            unique: list[Any] = []
            for f in plain:
                if not any(f.IsSame(u) for u in unique):
                    unique.append(f)
            return Resolved(unique)
        return Resolved([f for f, c in coloured if c.upper() == wanted])
    if kind == "edge_length":
        from OCP.BRepGProp import BRepGProp
        from OCP.GProp import GProp_GProps
        from OCP.TopAbs import TopAbs_EDGE
        from OCP.TopExp import TopExp

        from fdcad.core.occ import ShapeMap

        least = float(rule.get("min", 0.0))
        found = ShapeMap()
        TopExp.MapShapes_s(named.shape, TopAbs_EDGE, found)
        edges = []
        for i in range(1, found.Extent() + 1):
            edge = found.FindKey(i)
            props = GProp_GProps()
            BRepGProp.LinearProperties_s(edge, props)
            if props.Mass() >= least - 1e-9:
                edges.append(edge)
        return Resolved(edges)
    raise SelectionSetError(f"Unknown rule '{kind}'. Make the set again.")


def resolve(
    doc: Document, named: NamedShape, name: str, _seen: frozenset[str] = frozenset()
) -> Resolved:
    """What set ``name`` picks in ``named`` now."""
    if name in _seen:
        raise SelectionSetError(
            f'Selection set "{name}" uses itself. Remove it from its own combination.'
        )
    found = next((s for s in sets_of(doc) if s["name"] == name), None)
    if found is None:
        raise SelectionSetError(f'There is no selection set named "{name}". Pick another set.')
    if isinstance(found.get("items"), list):
        return _from_names(named, [str(n) for n in found["items"]])
    if isinstance(found.get("rule"), dict):
        return _from_rule(doc, named, found["rule"])
    combine = found.get("combine")
    if isinstance(combine, dict) and combine.get("op") in OPS:
        parts = [resolve(doc, named, str(n), _seen | {name}) for n in combine.get("of", [])]
        if not parts:
            return Resolved()
        shapes = list(parts[0].shapes)
        for part in parts[1:]:
            if combine["op"] == "union":
                shapes += [s for s in part.shapes if not any(s.IsSame(t) for t in shapes)]
            elif combine["op"] == "subtract":
                shapes = [s for s in shapes if not any(s.IsSame(t) for t in part.shapes)]
            else:
                shapes = [s for s in shapes if any(s.IsSame(t) for t in part.shapes)]
        return Resolved(shapes, sum(p.missing for p in parts))
    raise SelectionSetError(f'Selection set "{name}" cannot be read. Delete it and make it again.')


def users_of(sets: list[dict[str, Any]], name: str) -> list[str]:
    """The combined sets that use set ``name``."""
    out = []
    for s in sets:
        combine = s.get("combine")
        if isinstance(combine, dict) and name in combine.get("of", []):
            out.append(str(s["name"]))
    return out
