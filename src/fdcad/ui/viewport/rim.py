"""The rim of a highlight (D2821): a thin line in the view's ground colour beside the
outline of what is selected and of what is under the cursor.

The highlight colours are made to read on the view. On a part of a near colour (burnt
orange on a red part) the tint is weak and the outline all but gone. The rim gives
the outline a neighbour it always reads against, whatever the part's colour.

It is the same edges drawn again, wider and under the outline, in the part's own
layer: the kernel draws highlights after that layer, so the outline lies on top and
the rim shows on both sides of it. It is never picked, and it is not part of the
hidden line pass. The colours and widths are in ``look`` and are tested there.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fdcad.ui.viewport.widget import ViewportWidget

HOVER, SELECTED = "hover", "selected"


class HighlightRim:
    """The rims shown in one 3D view: one item for the selection, one for the hover."""

    def __init__(self, view: ViewportWidget) -> None:
        self.view = view
        self._items: dict[str, Any] = {HOVER: None, SELECTED: None}
        self._shapes: dict[str, list[Any]] = {HOVER: [], SELECTED: []}

    # What has a rim -------------------------------------------------------------------

    def shapes(self, kind: str) -> list[Any]:
        """The shapes that have a rim now (``"hover"`` or ``"selected"``)."""
        return list(self._shapes[kind])

    def set_selected(self, shapes: list[Any]) -> None:
        """Rim the selected faces and edges; the view's ``selection_changed`` calls it."""
        self._shapes[SELECTED] = [s for s in shapes if _has_edges(s)]
        self._show(SELECTED)
        self._update()

    def sync_hover(self) -> bool:
        """Rim the face or edge of the part under the cursor, after the kernel has
        looked. True when the rim changed, so the caller draws the view again."""
        shape = self._detected()
        old = self._shapes[HOVER]
        if (shape is None and not old) or (shape is not None and old and old[0].IsSame(shape)):
            return False
        self._shapes[HOVER] = [] if shape is None else [shape]
        self._show(HOVER)
        return True

    def clear(self) -> None:
        """Remove both rims: the part they lay on is going."""
        for kind in (HOVER, SELECTED):
            self._shapes[kind] = []
            self._show(kind)

    def forget(self) -> None:
        """Drop the items without touching the view, which is being freed."""
        self._items = {HOVER: None, SELECTED: None}
        self._shapes = {HOVER: [], SELECTED: []}

    def restyle(self) -> None:
        """Draw both rims again: the theme or the screen scale changed."""
        for kind in (HOVER, SELECTED):
            self._show(kind)

    # Internals ------------------------------------------------------------------------

    def _detected(self) -> Any:
        """The face or edge of the part the kernel found under the cursor, or None."""
        view = self.view
        context = view._context
        part = view._part
        if view._view is None or part is None or not context.HasDetected():
            return None
        owner = context.DetectedOwner()
        if owner is None or not owner.IsSameSelectable(part):
            return None
        shape = owner.Shape() if hasattr(owner, "Shape") else None
        return shape if shape is not None and _has_edges(shape) else None

    def _show(self, kind: str) -> None:
        view = self.view
        context = view._context
        old = self._items[kind]
        if old is not None:
            context.Remove(old, False)
            self._items[kind] = None
        shapes = self._shapes[kind]
        if not shapes or view._view is None:
            return
        from OCP.AIS import AIS_Shape, AIS_WireFrame
        from OCP.PrsMgr import PrsMgr_TOP_AllView

        from fdcad.core.features.solids import compound
        from fdcad.ui.viewport import look

        palette = view._palette
        highlight = palette.selection if kind == SELECTED else palette.preselection
        item = AIS_Shape(shapes[0] if len(shapes) == 1 else compound(shapes))
        item.SetTypeOfPresentation(PrsMgr_TOP_AllView)  # not for the hidden line pass
        item.SetColor(look.colour(look.rim_colour(palette, highlight)))
        item.SetWidth(look.rim_width(kind == SELECTED, view._dpr))
        look.drop_face_curves(item.Attributes())  # the outline only, on curved faces too
        context.Display(item, AIS_WireFrame, -1, False)  # -1: never picked
        context.Deactivate(item)
        self._items[kind] = item

    def _update(self) -> None:
        if self.view._view is not None:
            self.view._context.UpdateCurrentViewer()


def _has_edges(shape: Any) -> bool:
    """Whether a shape has an outline to rim: anything but a lone vertex."""
    from OCP.TopAbs import TopAbs_VERTEX

    return bool(shape is not None and shape.ShapeType() != TopAbs_VERTEX)
