"""Sketch blocks (TUTORIAL_REVIEW_SPEC TR34, D1717). No Qt.

A block is a group of sketch entities saved once, in its own axes, and placed as
copies. Each copy is ordinary sketch geometry (so profiles, the solver and the
tools work on it as before) with a map from the block's entity ids to the copy's.
A copy can be moved and turned like any curves (Move and Rotate Entities): where
it now sits is read back from two of its points. Updating the block from one copy
takes that copy's shape as the block's and makes every other copy again in its
own place, so editing the block changes every copy.
"""

from __future__ import annotations

import copy
import math
from typing import Any

from fdcad.core.sketch.model import (
    Point,
    Sketch,
    entity_points,
    remap,
    sketch_from_data,
    sketch_to_data,
)

Vec = tuple[float, float]
Frame = tuple[float, float, float]  # origin x, origin y, angle


class BlockError(ValueError):
    """The block command cannot be done; the message says what to do."""


def _closure(sketch: Sketch, ids: list[str]) -> list[str]:
    """``ids`` with the points their curves use, in sketch order."""
    want = set(ids)
    for eid in ids:
        ent = sketch.entities.get(eid)
        if ent is not None:
            want.update(entity_points(ent))
    return [eid for eid in sketch.entities if eid in want]


def _to_local(frame: Frame, p: Vec) -> Vec:
    ox, oy, a = frame
    c, s = math.cos(a), math.sin(a)
    dx, dy = p[0] - ox, p[1] - oy
    return dx * c + dy * s, -dx * s + dy * c


def _to_sketch(frame: Frame, p: Vec) -> Vec:
    ox, oy, a = frame
    c, s = math.cos(a), math.sin(a)
    return ox + p[0] * c - p[1] * s, oy + p[0] * s + p[1] * c


def _frame_points(block_sketch: Sketch) -> tuple[str, str] | None:
    """Two block points far apart, to read where a copy sits."""
    pts = [e for e in block_sketch.entities.values() if isinstance(e, Point)]
    if len(pts) < 2:
        return None
    first = min(pts, key=lambda p: (p.x, p.y))
    second = max(pts, key=lambda p: math.dist((p.x, p.y), (first.x, first.y)))
    if math.dist((first.x, first.y), (second.x, second.y)) < 1e-9:
        return None
    return first.id, second.id


def block_of(sketch: Sketch, eid: str) -> tuple[dict[str, Any], int] | None:
    """The block and copy index that entity ``eid`` belongs to, or None."""
    for block in sketch.blocks:
        for i, c in enumerate(block["copies"]):
            if eid in c["map"].values():
                return block, i
    return None


def copy_frame(sketch: Sketch, block: dict[str, Any], index: int) -> Frame:
    """Where copy ``index`` of ``block`` sits now: its origin and turn."""
    local = sketch_from_data(block["sketch"])
    pair = _frame_points(local)
    mapping = block["copies"][index]["map"]
    if pair is None:
        only = next(iter(mapping.values()), None)
        p = sketch.xy(only) if only in sketch.entities else (0.0, 0.0)
        return p[0], p[1], 0.0
    a, b = pair
    la, lb = local.xy(a), local.xy(b)
    sa, sb = sketch.xy(mapping[a]), sketch.xy(mapping[b])
    turn = math.atan2(sb[1] - sa[1], sb[0] - sa[0]) - math.atan2(lb[1] - la[1], lb[0] - la[0])
    c, s = math.cos(turn), math.sin(turn)
    return sa[0] - (la[0] * c - la[1] * s), sa[1] - (la[0] * s + la[1] * c), turn


def make_block(sketch: Sketch, ids: list[str], name: str | None = None) -> dict[str, Any]:
    """Save the picked entities as a new block; they become its first copy."""
    picked = [i for i in ids if i in sketch.entities]
    if not picked:
        raise BlockError("Pick the curves for the block first, then make the block.")
    if any(block_of(sketch, i) is not None for i in picked):
        raise BlockError("Some picked curves are already in a block. Explode that block first.")
    members = _closure(sketch, picked)
    xs = [sketch.xy(p)[0] for p in members if isinstance(sketch.entities[p], Point)]
    ys = [sketch.xy(p)[1] for p in members if isinstance(sketch.entities[p], Point)]
    frame: Frame = (min(xs, default=0.0), min(ys, default=0.0), 0.0)
    local = _local_copy(sketch, members, frame)
    number = len(sketch.blocks) + 1
    used = {b["id"] for b in sketch.blocks}
    while f"b{number}" in used:
        number += 1
    block = {
        "id": f"b{number}",
        "name": name or f"Block {number}",
        "sketch": sketch_to_data(local),
        "copies": [{"map": {eid: eid for eid in members}}],
    }
    sketch.blocks.append(block)
    return block


def _local_copy(sketch: Sketch, members: list[str], frame: Frame) -> Sketch:
    """A sketch holding ``members`` in the block's own axes (same ids), with the
    relations and dimensions among them."""
    local = Sketch()
    keep = set(members)
    for eid in members:
        ent = copy.deepcopy(sketch.entities[eid])
        if isinstance(ent, Point):
            ent.x, ent.y = _to_local(frame, (ent.x, ent.y))
        local.entities[eid] = ent
    local.relations = [
        copy.deepcopy(r) for r in sketch.relations if set(r.entities) <= keep and r.type != "fixed"
    ]
    local.dimensions = [copy.deepcopy(d) for d in sketch.dimensions if set(d.entities) <= keep]
    local.next_entity = sketch.next_entity
    return local


def insert_copy(sketch: Sketch, block: dict[str, Any], frame: Frame) -> dict[str, str]:
    """Place a new copy of ``block`` at ``frame``. Returns its map."""
    local = sketch_from_data(block["sketch"])
    mapping: dict[str, str] = {}
    for eid, ent in local.entities.items():
        if isinstance(ent, Point):
            x, y = _to_sketch(frame, (ent.x, ent.y))
            mapping[eid] = sketch.add_point(x, y, ent.construction)
    for eid, ent in local.entities.items():
        if isinstance(ent, Point):
            continue
        new = sketch.new_id()
        sketch.entities[new] = remap(ent, new, lambda p: mapping[p])
        mapping[eid] = new
    for r in local.relations:
        dup = copy.deepcopy(r)
        dup.entities = [mapping[e] for e in r.entities]
        sketch.relations.append(dup)
    for d in local.dimensions:
        dim = sketch.dimension(d.type, [mapping[e] for e in d.entities], copy.deepcopy(d.param))
        dim.driving, dim.measure_to = (
            d.driving,
            {mapping.get(k, k): v for k, v in d.measure_to.items()},
        )
        dim.supplement = d.supplement
    block["copies"].append({"map": mapping})
    return mapping


def _remove_copy(sketch: Sketch, block: dict[str, Any], index: int) -> None:
    ids = set(block["copies"][index]["map"].values())
    for eid in ids:
        sketch.entities.pop(eid, None)
    sketch.relations = [r for r in sketch.relations if not set(r.entities) & ids]
    sketch.dimensions = [d for d in sketch.dimensions if not set(d.entities) & ids]
    del block["copies"][index]


def update_from_copy(sketch: Sketch, block: dict[str, Any], index: int) -> int:
    """Take copy ``index``'s shape as the block's and make every other copy again in
    its own place. Returns how many copies were made again."""
    source = block["copies"][index]["map"]
    if not all(v in sketch.entities for v in source.values()):
        raise BlockError("This copy lost some of its curves. Explode it, then make a new block.")
    frames = [copy_frame(sketch, block, i) for i in range(len(block["copies"]))]
    members = [source[k] for k in source]
    local = _local_copy(sketch, members, frames[index])
    # Back to the block's own ids, so the maps stay readable.
    back = {v: k for k, v in source.items()}
    renamed = Sketch()
    for sid, ent in local.entities.items():
        if isinstance(ent, Point):
            p = copy.deepcopy(ent)
            p.id = back[sid]
            renamed.entities[p.id] = p
    for sid, ent in local.entities.items():
        if not isinstance(ent, Point):
            renamed.entities[back[sid]] = remap(ent, back[sid], lambda p: back[p])
    for r in local.relations:
        r.entities = [back[e] for e in r.entities]
    for d in local.dimensions:
        d.entities = [back[e] for e in d.entities]
        d.measure_to = {back.get(k, k): v for k, v in d.measure_to.items()}
    renamed.relations, renamed.dimensions = local.relations, local.dimensions
    block["sketch"] = sketch_to_data(renamed)
    others = [i for i in range(len(block["copies"])) if i != index]
    kept = block["copies"][index]
    for i in sorted(others, reverse=True):
        _remove_copy(sketch, block, i)
    block["copies"] = [kept]
    for i in others:
        insert_copy(sketch, block, frames[i])
    return len(others)


def explode_copy(sketch: Sketch, block: dict[str, Any], index: int) -> None:
    """Make copy ``index`` plain geometry again; a block with no copies left goes."""
    del block["copies"][index]
    if not block["copies"]:
        sketch.blocks.remove(block)


def prune(sketch: Sketch) -> None:
    """Drop copies whose entities were all deleted, and blocks with no copies."""
    for block in list(sketch.blocks):
        block["copies"] = [
            c for c in block["copies"] if any(v in sketch.entities for v in c["map"].values())
        ]
        if not block["copies"]:
            sketch.blocks.remove(block)
