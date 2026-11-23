"""Selection filters and box selection rules (TOOL_SPEC T14.3.2, T14.3.3).

Pure Python, no Qt, so the rules are tested without a GPU.

Filters: each item type can be switched on. While at least one type is on and
the filters are enabled, only those types highlight and select; with none on,
or with the filters disabled (F6), everything selects as usual.

Box selection: dragging left to right selects items fully inside the box
(window); dragging right to left also selects items the box crosses (crossing).
Shift adds what the box finds, Ctrl toggles it, and with neither the box
replaces the selection.

Lasso selection (TR19): with the lasso on, dragging draws a free loop. A loop
drawn clockwise selects items fully inside it; counter clockwise also selects
items it crosses. Shift and Ctrl work as for the box.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

#: Filter types, in the order the filter bar shows them.
FILTER_KINDS = (
    "vertex",
    "edge",
    "face",
    "body",
    "plane",
    "axis",
    "sketch",
    "segment",
    "point",
    "dimension",
)
#: Types the 3D view picks on the part.
VIEW_KINDS = ("face", "edge", "vertex")
#: Filter types the 3D view cannot pick: chosen in the feature tree instead (D719).
TREE_KINDS = ("plane", "axis", "sketch")
#: Types of sketch items in the sketch editor.
SKETCH_KINDS = ("segment", "point", "dimension")

Rect = tuple[float, float, float, float]  # x0, y0, x1, y1 with x0 <= x1 and y0 <= y1
Pt = tuple[float, float]


@dataclass
class SelectionFilter:
    """Which item types may be selected."""

    active: set[str] = field(default_factory=set)
    enabled: bool = True

    def is_on(self) -> bool:
        """True while filters limit the selection."""
        return self.enabled and bool(self.active)

    def allows(self, kind: str) -> bool:
        """True when an item of ``kind`` may highlight and select."""
        return not self.is_on() or kind in self.active

    def toggle(self, kind: str) -> bool:
        """Switch one type on or off (E, X, V and the bar buttons). Returns its new state.

        Switching a type on also enables the filters, so the key acts at once.
        """
        if kind in self.active:
            self.active.discard(kind)
            return False
        self.active.add(kind)
        self.enabled = True
        return True

    def only(self, kind: str) -> bool:
        """Pick only ``kind`` (TR329, D2208): that type alone, filters on. Asked again
        while it is the only type, every type picks again. Returns True when on."""
        if self.is_on() and self.active == {kind}:
            self.active.clear()
            return False
        self.active = {kind}
        self.enabled = True
        return True

    def toggle_enabled(self) -> bool:
        """Turn the chosen filters on or off at once (F6). Returns the new state."""
        self.enabled = not self.enabled
        return self.enabled

    def clear(self) -> None:
        """Clear All: no type chosen, so everything selects."""
        self.active.clear()

    def select_all(self) -> None:
        """Select All: every type chosen."""
        self.active = set(FILTER_KINDS)
        self.enabled = True

    def view_kinds(self) -> set[str]:
        """Which of face, edge and vertex the 3D view may pick. A body is picked by
        clicking one of its faces, so the body filter lets faces through (audit D11
        item 2, D719)."""
        kinds = {k for k in VIEW_KINDS if self.allows(k)}
        if self.is_on() and "body" in self.active:
            kinds.add("face")
        return kinds


def sketch_kind(item: str, points: Iterable[str]) -> str:
    """Filter type of a sketch selection item: dimension, point or segment."""
    if item.startswith("d"):
        return "dimension"
    if item in set(points):
        return "point"
    return "segment"


# Box selection -----------------------------------------------------------------------


def is_crossing(start: Pt, end: Pt) -> bool:
    """True for a right to left drag, which also takes items the box crosses."""
    return end[0] < start[0]


def lasso_is_crossing(loop: Sequence[Pt]) -> bool:
    """True for a lasso drawn counter clockwise on screen, which also takes items the
    loop crosses (TR19); clockwise takes only items inside, like a left to right box.
    Screen y grows downward, so a clockwise loop has a positive shoelace sum."""
    if len(loop) < 3:
        return False
    total = 0.0
    for (x0, y0), (x1, y1) in itertools.pairwise([*loop, loop[0]]):
        total += x0 * y1 - x1 * y0
    return total < 0


def thin_loop(points: Sequence[Pt], step: float) -> list[Pt]:
    """The lasso's points with those closer than ``step`` to the last kept one left out."""
    out: list[Pt] = []
    for p in points:
        if not out or abs(p[0] - out[-1][0]) + abs(p[1] - out[-1][1]) >= step:
            out.append(p)
    return out


def scheme(shift: bool, ctrl: bool) -> str:
    """How a box changes the selection: "toggle" with Ctrl, "add" with Shift, else "replace"."""
    if ctrl:
        return "toggle"
    if shift:
        return "add"
    return "replace"


def apply(selection: Sequence[str], found: Sequence[str], how: str) -> list[str]:
    """The new selection after a box found ``found`` (items outside the box stay as they were)."""
    if how == "replace":
        return list(dict.fromkeys(found))
    out = list(selection)
    for item in dict.fromkeys(found):
        if item in out:
            if how == "toggle":
                out.remove(item)
        else:
            out.append(item)
    return out


def rect_of(a: Pt, b: Pt) -> Rect:
    """The box spanned by two corners."""
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))


def inside(rect: Rect, p: Pt) -> bool:
    """True when ``p`` lies in the box (edges included)."""
    return rect[0] <= p[0] <= rect[2] and rect[1] <= p[1] <= rect[3]


def _segments_cross(a: Pt, b: Pt, c: Pt, d: Pt) -> bool:
    def orient(p: Pt, q: Pt, r: Pt) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    o1, o2 = orient(a, b, c), orient(a, b, d)
    o3, o4 = orient(c, d, a), orient(c, d, b)
    return (o1 * o2 <= 0) and (o3 * o4 <= 0) and not (o1 == o2 == o3 == o4 == 0)


def polyline_inside(rect: Rect, points: Sequence[Pt]) -> bool:
    """True when every point of a polyline lies in the box (window selection)."""
    return bool(points) and all(inside(rect, p) for p in points)


def polyline_touches(rect: Rect, points: Sequence[Pt]) -> bool:
    """True when a polyline lies in the box or crosses its edge (crossing selection)."""
    if any(inside(rect, p) for p in points):
        return True
    x0, y0, x1, y1 = rect
    sides = (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0)))
    for a, b in itertools.pairwise(points):
        if any(_segments_cross(a, b, c, d) for c, d in sides):
            return True
    return False


def picked(rect: Rect, points: Sequence[Pt], crossing: bool) -> bool:
    """Whether a box picks an item drawn as ``points`` (screen pixels)."""
    return polyline_touches(rect, points) if crossing else polyline_inside(rect, points)
