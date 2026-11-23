"""Linked dimension values (TR193, D978).

Several dimensions of one sketch can share a name. They then always have the same
value: changing any one of them changes the others, with no formula to write. Only
dimensions of one kind link (lengths with lengths, angles with angles). No Qt; the
caller takes the undo checkpoint.
"""

from __future__ import annotations

import copy

from fdcad.core.sketch.model import Dimension, Sketch


class LinkError(ValueError):
    """The dimensions cannot be linked; the message says what to pick."""


def _kind(dim: Dimension) -> str:
    return "angle" if dim.type == "angle" else "length"


def valid_name(name: str) -> bool:
    """A link name: letters, digits and underscores, starting with a letter."""
    return bool(name) and name[0].isalpha() and all(c.isalnum() or c == "_" for c in name)


def link(sketch: Sketch, dids: list[str], name: str) -> list[str]:
    """Link the dimensions under ``name``; all take the first one's value. Returns the
    ids linked."""
    name = name.strip()
    if not valid_name(name):
        raise LinkError(
            "A link name starts with a letter and has only letters, digits and underscores. "
            "Type another name."
        )
    found = [d for d in sketch.dimensions if d.id in set(dids)]
    if len(found) < 2:
        raise LinkError("Pick two or more dimensions to link.")
    if len({_kind(d) for d in found}) > 1:
        raise LinkError("Lengths and angles cannot share a value. Pick dimensions of one kind.")
    first = found[0]
    for dim in found:
        dim.link = name
        if dim is not first:
            dim.param = copy.deepcopy(first.param)
    return [d.id for d in found]


def unlink(sketch: Sketch, dids: list[str]) -> int:
    """Take the dimensions out of their links; they keep their values."""
    count = 0
    for dim in sketch.dimensions:
        if dim.id in set(dids) and dim.link:
            dim.link = None
            count += 1
    return count


def follow(sketch: Sketch, changed: Dimension) -> list[str]:
    """Give every dimension linked to ``changed`` its value. Returns their ids."""
    if not changed.link:
        return []
    out = []
    for dim in sketch.dimensions:
        if dim is not changed and dim.link == changed.link and _kind(dim) == _kind(changed):
            dim.param = copy.deepcopy(changed.param)
            out.append(dim.id)
    return out
