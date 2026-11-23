"""Mirror image display (TR309, D926): a see through copy of the part reflected about
a plane, drawn by the graphics only (a display transform, no kernel work), so the
user can judge symmetry. It follows each rebuild and is never picked or saved.

It is drawn with its edges (D2825). As a see through fill alone its faces were one
flat grey on the light themes, a shadow with no form to compare with the part."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fdcad.ui.viewport.widget import ViewportWidget

Vec3 = tuple[float, float, float]
#: How see through the mirror image is (0 solid, 1 invisible).
MIRROR_TRANSPARENCY = 0.65


class MirrorImage:
    """The mirrored copy shown in one view."""

    def __init__(self, view: ViewportWidget) -> None:
        self.view = view
        self.plane: tuple[Vec3, Vec3] | None = None
        self.item: Any = None

    def set_plane(self, plane: tuple[Vec3, Vec3] | None) -> bool:
        """Show the image about ``plane`` (origin, normal), or hide it for None. True
        when an image is shown."""
        self.plane = plane
        return self.refresh()

    def refresh(self) -> bool:
        """Draw the image again for the part shown now."""
        view = self.view
        context = view._context
        if self.item is not None:
            context.Remove(self.item, False)
            self.item = None
        shape = view._part_shape
        shown = False
        if self.plane is not None and shape is not None:
            from OCP.AIS import AIS_Shape
            from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf

            origin, normal = self.plane
            mirror = gp_Trsf()
            mirror.SetMirror(gp_Ax2(gp_Pnt(*origin), gp_Dir(*normal)))
            item = AIS_Shape(shape)
            item.SetLocalTransformation(mirror)
            from OCP.Aspect import Aspect_TOL_SOLID
            from OCP.Prs3d import Prs3d_LineAspect

            from fdcad.ui.viewport import look
            from fdcad.ui.viewport.widget import _hex

            grey = _hex(view._palette.sketch_reference)
            item.SetColor(grey)
            item.SetTransparency(MIRROR_TRANSPARENCY)
            drawer = item.Attributes()
            scale = float(getattr(view, "_dpr", 1.0))
            drawer.SetFaceBoundaryDraw(True)
            drawer.SetFaceBoundaryAspect(
                Prs3d_LineAspect(grey, Aspect_TOL_SOLID, look.edge_width(scale))
            )
            context.Display(item, False)
            context.Deactivate(item)  # never picked
            self.item = item
            shown = True
        if view._view is not None:
            context.UpdateCurrentViewer()
        return shown
