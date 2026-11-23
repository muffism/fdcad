"""Merge two sketches on the same plane (TR122 item 1, D986).

Everything in ``other`` (curves, points, relations, dimensions, pictures and text)
is added to ``into`` with new ids, at the same sketch coordinates. ``other``'s
fixed origin point becomes ``into``'s, so what was tied to one origin stays tied.
Dimension names that ``into`` already uses are dropped (the dimension keeps its
value). No Qt; the caller removes ``other`` from the part.
"""

from __future__ import annotations

import copy

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Point, Relation, Sketch, remap


def _origin_of(sketch: Sketch) -> str | None:
    """The sketch's fixed construction point at 0, 0 (every sketch has one)."""
    for eid, ent in sketch.entities.items():
        fixed = any(r.type == "fixed" and r.entities == [eid] for r in sketch.relations)
        at_zero = isinstance(ent, Point) and abs(ent.x) < 1e-12 and abs(ent.y) < 1e-12
        if at_zero and ent.construction and fixed:
            return eid
    return None


def merge(into: Sketch, other: Sketch) -> dict[str, str]:
    """Add ``other`` to ``into``. Returns the map from ``other``'s ids to the new ones."""
    mapped: dict[str, str] = {}
    origin_other, origin_into = _origin_of(other), _origin_of(into)
    if origin_other is not None and origin_into is not None:
        mapped[origin_other] = origin_into
    for eid, ent in other.entities.items():
        if isinstance(ent, Point) and eid not in mapped:
            nid = into.new_id()
            point = copy.deepcopy(ent)
            point.id = nid
            into.entities[nid] = point
            mapped[eid] = nid
    for eid, ent in other.entities.items():
        if isinstance(ent, Point):
            continue
        nid = into.new_id()
        into.entities[nid] = remap(ent, nid, lambda pid: mapped[pid])
        mapped[eid] = nid
    for rel in other.relations:
        if origin_other is not None and rel.type == "fixed" and rel.entities == [origin_other]:
            continue  # the kept sketch has its own fixed origin
        into.relations.append(
            Relation(rel.type, [mapped.get(e, e) for e in rel.entities], rel.value, rel.off)
        )
    names = {d.name for d in into.dimensions if d.name}
    for dim in other.dimensions:
        new = into.dimension(
            dim.type,
            [mapped.get(e, e) for e in dim.entities],
            Param(dim.param.expr, dim.param.value),
            dim.driving,
        )
        new.measure_to = {mapped.get(e, e): v for e, v in dim.measure_to.items()}
        new.supplement, new.label, new.side, new.off = dim.supplement, dim.label, dim.side, dim.off
        new.display = copy.deepcopy(dim.display)
        new.name = dim.name if dim.name and dim.name not in names else None
        new.link = dim.link
    used_pictures = {p.id for p in into.pictures}
    for pic in other.pictures:
        new_pic = copy.deepcopy(pic)
        k = 1
        while f"p{k}" in used_pictures:
            k += 1
        new_pic.id = f"p{k}"
        used_pictures.add(new_pic.id)
        into.pictures.append(new_pic)
    used_texts = {t.id for t in into.texts}
    for text in other.texts:
        new_text = copy.deepcopy(text)
        k = 1
        while f"t{k}" in used_texts:
            k += 1
        new_text.id = f"t{k}"
        new_text.curve = mapped.get(new_text.curve, new_text.curve)
        used_texts.add(new_text.id)
        into.texts.append(new_text)
    for layer in other.layers:
        if not any(x.get("name") == layer.get("name") for x in into.layers):
            into.layers.append(copy.deepcopy(layer))
    for eid, name in other.layer_of.items():
        if eid in mapped:
            into.layer_of[mapped[eid]] = name
    return mapped
