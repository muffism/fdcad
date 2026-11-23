"""Select Previous, Invert Selection and Select All in the 3D view (TR93, D915; D934).

Select Previous brings back the picks from before the selection was last cleared,
while the part has not rebuilt since (a rebuild makes new faces). Invert picks every
face, edge or vertex of the part that is not picked now, of the kinds the selection
filter allows, or of the kinds picked now when the filter is off.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fdcad.ui.viewport.widget import ViewportWidget


class SelectionMemory:
    """Remembers the last non empty selection of one view."""

    def __init__(self, view: ViewportWidget) -> None:
        self.view = view
        self._last: list[Any] = []
        self.previous: list[Any] = []
        self._part: Any = None
        view.selection_changed.connect(self._changed)

    def _changed(self, shapes: list[Any]) -> None:
        part = self.view._part_shape
        if part is not self._part:  # the part rebuilt: old picks are gone
            self._part, self._last, self.previous = part, [], []
        if shapes:
            self._last = list(shapes)
        elif self._last:
            self.previous, self._last = self._last, []

    def restore(self) -> bool:
        """Select the remembered picks again. False when there are none."""
        if not self.previous or self.view._part_shape is not self._part:
            return False
        shapes = self.previous
        self.view.select_shapes(shapes)
        return True


def _kind(shape: Any) -> str:
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE

    t = shape.ShapeType()
    return "face" if t == TopAbs_FACE else "edge" if t == TopAbs_EDGE else "vertex"


def select_all(view: ViewportWidget, allowed: set[str] | None) -> int:
    """Pick every face, edge or vertex of the kinds the filter allows, or of the kinds
    picked now (one edge picked: every edge), or every face (TR380, TR224, D934)."""
    picked = view.selected()
    kinds = allowed if allowed is not None else ({_kind(s) for s in picked} or {"face"})
    return _pick_kinds(view, kinds, [])


def _pick_kinds(view: ViewportWidget, kinds: set[str], keep_out: list[Any]) -> int:
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
    from OCP.TopExp import TopExp

    from fdcad.core.occ import ShapeMap

    part = view._part_shape
    if part is None:
        return 0
    taken = ShapeMap()
    for p in keep_out:
        taken.Add(p)
    out: list[Any] = []
    for kind, top in (("face", TopAbs_FACE), ("edge", TopAbs_EDGE), ("vertex", TopAbs_VERTEX)):
        if kind not in kinds:
            continue
        found = ShapeMap()
        TopExp.MapShapes_s(part, top, found)
        for i in range(1, found.Extent() + 1):
            shape = found.FindKey(i)
            if not taken.Contains(shape):
                out.append(shape)
    view.select_shapes(out)
    return len(out)


def invert(view: ViewportWidget, allowed: set[str] | None) -> int:
    """Select what is not selected; ``allowed`` is the filter's kinds, or None when the
    filter is off. Returns how many items are now picked."""
    if view._part_shape is None:
        return 0
    picked = view.selected()
    kinds = allowed if allowed is not None else ({_kind(s) for s in picked} or {"face"})
    return _pick_kinds(view, kinds, picked)
