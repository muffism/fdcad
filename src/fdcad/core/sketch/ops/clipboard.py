"""Copy and paste sketch entities, and move whole sketches to another plane (TR3, TR9).

``extract`` takes picked entities with their points and the relations and
dimensions among them as plain sketch data; ``insert`` adds such data to a
sketch with new ids, moved by an offset. ``unlink_model`` makes a copied sketch
fit another plane or face: part geometry links cannot carry over (DECISIONS
D685). No Qt; the data is plain JSON values, so it can go through the system
clipboard and is read as data only (CLAUDE.md rule 10).
"""

from __future__ import annotations

import copy as _copy
from dataclasses import dataclass, field
from typing import Any

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import (
    Circle,
    Dimension,
    Entity,
    Line,
    Point,
    Relation,
    Sketch,
    entity_points,
    remap,
    sketch_from_data,
    sketch_to_data,
)
from fdcad.core.sketch.ops.geom import Vec
from fdcad.core.sketch.ops.pieces import _origin


class ClipError(ValueError):
    """Nothing can be copied or pasted; the message says why."""


@dataclass
class Clip:
    """Copied sketch entities: their sketch data, the point they are placed by
    (the middle of their extent) and how many relations and dimensions to items
    that were not copied were left behind."""

    data: dict[str, Any]
    anchor: Vec
    left_behind: int = 0
    top: list[str] = field(default_factory=list)


def extract(sketch: Sketch, ids: list[str]) -> Clip:
    """The picked entities (the origin left out) with their points, and the relations
    and dimensions among them. Part geometry links are copied as plain geometry."""
    picked = [i for i in dict.fromkeys(ids) if i in sketch.entities and not _origin(sketch, i)]
    if not picked:
        raise ClipError("Select the sketch entities to copy.")
    keep: set[str] = set()
    for eid in picked:
        keep.update(entity_points(sketch.entities[eid]))
        keep.add(eid)
    keep = {k for k in keep if not _origin(sketch, k)}
    out = Sketch()
    for eid, ent in sketch.entities.items():
        if eid in keep:
            new = _copy.deepcopy(ent)
            if isinstance(new, Point | Line | Circle):
                new.source = None
            out.entities[eid] = new
    out.next_entity = sketch.next_entity
    touched = 0
    for rel in sketch.relations:
        if set(rel.entities) <= keep:
            out.relations.append(Relation(rel.type, list(rel.entities), rel.value, rel.off))
        elif set(rel.entities) & keep:
            touched += 1
    for dim in sketch.dimensions:
        if set(dim.entities) <= keep:
            out.dimensions.append(_copy.deepcopy(dim))
        elif set(dim.entities) & keep:
            touched += 1
    xs = [e.x for e in out.entities.values() if isinstance(e, Point)]
    ys = [e.y for e in out.entities.values() if isinstance(e, Point)]
    anchor = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2) if xs else (0.0, 0.0)
    return Clip(sketch_to_data(out), anchor, touched, picked)


def clip_from_data(raw: Any) -> Clip:
    """A clip read back from the clipboard. Raises ClipError on anything unexpected."""
    try:
        data = dict(raw["data"])
        anchor = (float(raw["anchor"][0]), float(raw["anchor"][1]))
        top = [str(t) for t in raw.get("top", [])]
        sketch_from_data(data)  # checks the data
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise ClipError("The clipboard does not hold sketch entities.") from exc
    return Clip(data, anchor, int(raw.get("left_behind", 0) or 0), top)


def clip_to_data(clip: Clip) -> dict[str, Any]:
    """A clip as plain JSON values, for the clipboard."""
    data = _copy.deepcopy(clip.data)
    for dim in data.get("dimensions", []):
        p = dim.get("param")
        if isinstance(p, Param):
            dim["param"] = {"expr": p.expr, "value": p.value}
    return {
        "data": data,
        "anchor": list(clip.anchor),
        "left_behind": clip.left_behind,
        "top": list(clip.top),
    }


def insert(sketch: Sketch, clip: Clip, offset: Vec) -> list[str]:
    """Add the clip's entities to ``sketch`` with new ids, moved by ``offset``.

    Returns the new ids of the copied top level entities (the picks), in order.
    """
    src = sketch_from_data(clip.data)
    mapped: dict[str, str] = {}

    def twin(pid: str) -> str:
        if pid not in mapped:
            p = src.point(pid)
            mapped[pid] = sketch.add_point(p.x + offset[0], p.y + offset[1], p.construction)
        return mapped[pid]

    for eid, ent in src.entities.items():
        if isinstance(ent, Point):
            twin(eid)
    for eid, ent in src.entities.items():
        if isinstance(ent, Point):
            continue
        nid = sketch.new_id()
        new: Entity = remap(ent, nid, twin)
        sketch.entities[nid] = new
        mapped[eid] = nid
    for rel in src.relations:
        sketch.relations.append(
            Relation(rel.type, [mapped[e] for e in rel.entities], rel.value, rel.off)
        )
    for dim in src.dimensions:
        nd = sketch.dimension(
            dim.type,
            [mapped[e] for e in dim.entities],
            Param(dim.param.expr, dim.param.value),
            dim.driving,
        )
        nd.measure_to = {mapped[e]: v for e, v in dim.measure_to.items() if e in mapped}
        nd.supplement, nd.label = dim.supplement, dim.label
    top = clip.top or [e for e in src.entities if not isinstance(src.entities[e], Point)]
    return [mapped[t] for t in top if t in mapped]


@dataclass
class Unlinked:
    """A sketch made fit for another plane: its data and what was dropped."""

    data: dict[str, Any]
    #: Relations and dimensions to part geometry that were removed.
    removed: int = 0
    #: Part geometry copies (construction helpers) in the sketch, before unlinking.
    links: int = 0


def model_links(sketch: Sketch) -> list[str]:
    """Entities that copy part geometry (they carry a ``source``)."""
    return [
        e.id
        for e in sketch.entities.values()
        if isinstance(e, Point | Line | Circle) and e.source is not None
    ]


def unlink_model(data: dict[str, Any], keep: bool = False) -> Unlinked:
    """A copy of sketch data for another plane or face (TR3.3, TR9.2, D685).

    With ``keep`` the part geometry copies stay as fixed geometry where they are,
    so the sketch keeps its shape and relations, but they no longer follow the
    part. Without it, construction copies go with every relation and dimension
    that names them, and drawn curves that were copied from the part lose their
    Fix, so the pasted sketch can be moved and dimensioned.
    """
    sketch = sketch_from_data(_copy.deepcopy(data))
    links = model_links(sketch)
    removed = 0
    if keep:
        for eid in links:
            ent = sketch.entities[eid]
            assert isinstance(ent, Point | Line | Circle)
            ent.source = None
        return Unlinked(sketch_to_data(sketch), 0, len(links))
    gone: set[str] = set()
    unfix: set[str] = set()
    for eid in links:
        ent = sketch.entities[eid]
        assert isinstance(ent, Point | Line | Circle)
        ent.source = None
        if ent.construction:
            gone.add(eid)
            if not isinstance(ent, Point):
                gone.update(entity_points(ent))
        else:
            unfix.add(eid)
    kept_r: list[Relation] = []
    for rel in sketch.relations:
        if set(rel.entities) & gone or (rel.type == "fixed" and set(rel.entities) <= unfix):
            removed += 1
        else:
            kept_r.append(rel)
    sketch.relations = kept_r
    kept_d: list[Dimension] = []
    for dim in sketch.dimensions:
        if set(dim.entities) & gone:
            removed += 1
        else:
            kept_d.append(dim)
    sketch.dimensions = kept_d
    for eid in gone:
        sketch.entities.pop(eid, None)
    return Unlinked(sketch_to_data(sketch), removed, len(links))


__all__ = [
    "Clip",
    "ClipError",
    "Unlinked",
    "clip_from_data",
    "clip_to_data",
    "extract",
    "insert",
    "model_links",
    "unlink_model",
]
