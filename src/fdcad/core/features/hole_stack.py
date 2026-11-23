"""Custom holes from a stack of elements (TR144 item 1, D1912).

``stack`` is text such as ``counterbore 10 3; countersink 8 90; straight 5 12``: from
the face inward, each element is a kind, a diameter (mm) and a length (mm), or for
a countersink its included angle (degrees): the cone runs from that diameter down to
the next element's. Kinds: ``straight``, ``counterbore`` (both a plain bore),
``tapped`` (a bore at the tap drill diameter that also gets a cosmetic thread mark
in a later version) and ``countersink``. The last element must be a bore. The order
is the text's order, so elements are reordered by editing it. No Qt.
"""

from __future__ import annotations

import itertools
import math
import re

from fdcad.core.features.base import FeatureError

KINDS = ("straight", "counterbore", "tapped", "countersink")


def parse_stack(name: str, text: str) -> list[tuple[str, float, float]]:
    """(kind, radius in mm, length in mm or angle in radians) for each element."""
    out: list[tuple[str, float, float]] = []
    for part in text.split(";"):
        part = part.strip()
        if not part:
            continue
        found = re.fullmatch(r"([a-z]+)\s+([0-9.]+)\s*(?:x\s*)?([0-9.]+)", part.lower())
        if found is None or found.group(1) not in KINDS:
            raise FeatureError(
                f"{name}: each hole element must read like straight 5 12 or countersink 8 90. "
                f"Fix '{part}'."
            )
        kind, size, value = found.group(1), float(found.group(2)), float(found.group(3))
        if size <= 0 or value <= 0:
            raise FeatureError(f"{name}: '{part}' needs sizes above 0. Enter larger values.")
        if kind == "countersink":
            if value >= 180:
                raise FeatureError(
                    f"{name}: a countersink angle must be below 180 degrees. Fix '{part}'."
                )
            out.append((kind, size / 2, math.radians(value)))
        else:
            out.append((kind, size / 2, value))
    if not out:
        raise FeatureError(f"{name}: the hole has no elements. Enter one, such as straight 5 10.")
    if out[-1][0] == "countersink":
        raise FeatureError(
            f"{name}: the last element must be a bore, not a countersink. Add a straight "
            "element after it."
        )
    for (k1, r1, _v1), (_k2, r2, _v2) in itertools.pairwise(out):
        if k1 == "countersink" and r2 >= r1:
            raise FeatureError(
                f"{name}: a countersink must be wider than the element after it. Enter a "
                "larger countersink diameter."
            )
    return out


def stack_profile(
    stack: list[tuple[str, float, float]], top: float, drill: bool, tip: float
) -> list[tuple[float, float, str]]:
    """The half section (r, z, role) of a stacked hole, as ``hole._profile`` gives."""
    z = -top
    pts: list[tuple[float, float, str]] = [(0.0, z, "")]
    last = len(stack) - 1
    for k, (kind, r, value) in enumerate(stack):
        role = "wall" if k == last else f"step{k + 1}"
        if k == 0:
            pts.append((r, z, "head"))
        else:
            pts.append((r, z, f"step{k}_floor"))
        if kind == "countersink":
            nxt = stack[k + 1][1]
            if k == 0 and z < 0:
                pts.append((r, 0.0, "head_wall"))
                z = 0.0
            z += (r - nxt) / math.tan(value / 2.0)
            pts.append((nxt, z, role))
            continue
        z += value
        pts.append((r, z, role))
    r_end = stack[-1][1]
    if drill:
        pts.append((0.0, z + r_end / math.tan(tip / 2.0), "tip"))
    else:
        pts.append((0.0, z, "bottom"))
    out: list[tuple[float, float, str]] = []
    for p in pts:
        if out and abs(out[-1][0] - p[0]) < 1e-9 and abs(out[-1][1] - p[1]) < 1e-9:
            continue
        out.append(p)
    return out


def stack_depth(stack: list[tuple[str, float, float]]) -> float:
    """How deep the stack reaches from the face (the bores' lengths and the cones)."""
    depth = 0.0
    for k, (kind, r, value) in enumerate(stack):
        depth += (r - stack[k + 1][1]) / math.tan(value / 2.0) if kind == "countersink" else value
    return depth


__all__ = ["KINDS", "parse_stack", "stack_depth", "stack_profile"]
