"""Edge display options in the 3D view (TR212, D1602).

- Smooth edges, where two faces meet tangent: shown, dashed or removed. They are
  left out of the face boundaries (the kernel skips edges marked smooth when the
  upper continuity is C0) and, when dashed, drawn again as thin dashed lines.
- Hidden edges in Hidden Lines Visible: dashed (the default) or solid.
- Feature edges: every edge of the feature selected in the tree, drawn in the
  selection colour on top of the part.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fdcad.ui.viewport.widget import ViewportWidget

SMOOTH_CHOICES = ("shown", "dashed", "removed")
HIDDEN_CHOICES = ("dashed", "solid")


class EdgeLook:
    """The extra edge drawings of one 3D view."""

    def __init__(self, view: ViewportWidget) -> None:
        self.view = view
        self.smooth = "shown"
        self.hidden = "dashed"
        self._smooth_edges: list[Any] = []
        self._smooth_of: Any = None
        self._smooth_item: Any = None
        self._feature_item: Any = None

    # Smooth edges ----------------------------------------------------------------------

    def smooth_edges(self) -> list[Any]:
        """The smooth edges of the shown part (found once per part)."""
        from fdcad.core.edge_display import smooth_edges

        shape = self.view._part_shape
        if shape is None:
            return []
        if self._smooth_of is not shape:
            try:
                self._smooth_edges = smooth_edges(shape)
            except Exception:
                self._smooth_edges = []
            self._smooth_of = shape
        return self._smooth_edges

    def style(self, drawer: Any) -> None:
        """Set the part's face boundaries to leave smooth edges out when asked."""
        from OCP.GeomAbs import GeomAbs_C0, GeomAbs_CN

        if self.smooth != "shown" and self.smooth_edges():
            drawer.SetFaceBoundaryUpperContinuity(GeomAbs_C0)
        else:
            drawer.SetFaceBoundaryUpperContinuity(GeomAbs_CN)

    def refresh(self) -> None:
        """Draw the dashed smooth edges again (after a rebuild or a style change)."""
        from OCP.AIS import AIS_Shape, AIS_WireFrame
        from OCP.Aspect import Aspect_TOL_DOT
        from OCP.Prs3d import Prs3d_LineAspect

        from fdcad.core.features.solids import compound
        from fdcad.ui.viewport import look

        view = self.view
        context = view._context
        if self._smooth_item is not None:
            context.Remove(self._smooth_item, False)
            self._smooth_item = None
        wanted = (
            self.smooth == "dashed"
            and view._part is not None
            and view.display_style == "shaded_edges"
        )
        edges = self.smooth_edges() if wanted else []
        if edges:
            item = AIS_Shape(compound(edges))
            aspect = Prs3d_LineAspect(
                look.colour(view._palette.edge),
                Aspect_TOL_DOT,
                look.line_width(look.HIDDEN_WIDTH, view._dpr),
            )
            item.Attributes().SetWireAspect(aspect)
            item.Attributes().SetLineAspect(aspect)
            context.Display(item, AIS_WireFrame, -1, False)
            context.Deactivate(item)  # never picked
            self._smooth_item = item

    # Feature edges ---------------------------------------------------------------------

    def show_feature_edges(self, edges: list[Any]) -> None:
        """Draw these edges in the selection colour on top of the part; [] clears."""
        from OCP.AIS import AIS_Shape, AIS_WireFrame
        from OCP.Graphic3d import Graphic3d_ZLayerId_Topmost

        from fdcad.core.features.solids import compound
        from fdcad.ui.viewport import look

        view = self.view
        context = view._context
        if self._feature_item is not None:
            context.Remove(self._feature_item, False)
            self._feature_item = None
        if edges:
            item = AIS_Shape(compound(edges))
            item.SetColor(look.colour(view._palette.selection))
            item.SetWidth(look.SELECTED_WIDTH * max(1.0, view._dpr))
            item.SetZLayer(Graphic3d_ZLayerId_Topmost)
            context.Display(item, AIS_WireFrame, -1, False)
            context.Deactivate(item)
            self._feature_item = item
        if view._view is not None:
            context.UpdateCurrentViewer()
