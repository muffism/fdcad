"""OpenCascade viewer embedded in a Qt widget.

The widget owns a native window that OCCT draws into with OpenGL. Qt never
paints it. All sizes passed to OCCT are in device pixels, so the view stays
sharp on Retina and high DPI screens.

Input (PLAN section 8 items 9 and 11, WORKFLOW_SPEC W7): middle drag rotates,
Ctrl and middle drag pans, Shift and middle drag zooms, Alt and middle drag
rolls, and the wheel zooms; on a trackpad two finger drag rotates, Shift and
two finger drag pans and pinch zooms. With focus, the arrow keys rotate, Ctrl
and arrows pan, Shift and arrows rotate 90 degrees, and Alt and Left or Right
rolls. Left click selects (Ctrl or Shift adds), left drag on empty space draws
a selection box, Alt and left click selects the next item under the cursor. A
right drag is a mouse gesture; Control and left drag is a gesture on a
trackpad.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from OCP.AIS import (
    AIS_InteractiveContext,
    AIS_RubberBand,
    AIS_SelectionScheme_Replace,
    AIS_SelectionScheme_XOR,
    AIS_Shaded,
    AIS_Shape,
    AIS_TextLabel,
    AIS_WireFrame,
)
from OCP.Aspect import (
    Aspect_DisplayConnection,
    Aspect_GradientFillMethod,
    Aspect_GradientFillMethod_Vertical,
    Aspect_NeutralWindow,
    Aspect_POM_Fill,
    Aspect_TOL_DASH,
    Aspect_TOL_DOTDASH,
    Aspect_TOL_SOLID,
    Aspect_TOTP_LEFT_LOWER,
)
from OCP.collections import Vec2_int
from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
from OCP.Graphic3d import (
    Graphic3d_Camera,
    Graphic3d_HTA_LEFT,
    Graphic3d_TMF_2d,
    Graphic3d_TransformPers,
    Graphic3d_VTA_TOP,
    Graphic3d_ZLayerId_Topmost,
    Graphic3d_ZLayerId_TopOSD,
)
from OCP.OpenGl import OpenGl_GraphicDriver
from OCP.Prs3d import Prs3d_Drawer, Prs3d_LineAspect
from OCP.Quantity import Quantity_Color, Quantity_TOC_sRGB
from OCP.TCollection import TCollection_ExtendedString
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS_Shape
from OCP.V3d import (
    V3d_AmbientLight,
    V3d_DirectionalLight,
    V3d_TypeOfAxe,
    V3d_View,
    V3d_Viewer,
)
from PySide6.QtCore import QElapsedTimer, QEvent, QPoint, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QGuiApplication,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QNativeGestureEvent,
    QPaintEngine,
    QPaintEvent,
    QResizeEvent,
    QShowEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import QWidget

from fdcad.core.features.base import PreviewHandle
from fdcad.ui import strings
from fdcad.ui.icons import ACCENT
from fdcad.ui.input.gesture_guide import GestureTracker
from fdcad.ui.themes.theme import LIGHT, Palette, is_dark
from fdcad.ui.viewport import keynav, look
from fdcad.ui.viewport.handles import (
    MIN_ANGLE,
    MIN_LENGTH,
    RULER_PICK_PX,
    HandleDrag,
    label_box,
    label_hit,
    polyline_distance,
    snap_point,
    spread_labels,
    travel_to,
)
from fdcad.ui.viewport.native import native_window_usable, set_native_handle
from fdcad.ui.viewport.plane_drag import PlaneDrag
from fdcad.ui.viewport.plane_look import (
    FILL_TRANSPARENCY,
    LABEL_HEIGHT,
    OUTLINE_WIDTH,
    PlaneStyle,
    label_anchor,
    label_rows,
    plane_state,
    plane_style,
)
from fdcad.ui.viewport.preview import (
    PREVIEW_OFFSET_FACTOR,
    PREVIEW_OFFSET_UNITS,
    PREVIEW_TRANSPARENCY,
    PreviewData,
    drag_angle,
    drag_distance,
)
from fdcad.ui.viewport.regions import RegionLayer
from fdcad.ui.viewport.value_labels import ValueLabel, starts_typing
from fdcad.ui.viewport.views import (
    STANDARD_VIEWS,
    CameraPose,
    Vec3,
    blend_pose,
    ease,
    view_for_normal,
)

_WHEEL_ZOOM_STEP = 0.15
_TRACKPAD_ROTATE_SCALE = 1.0
_DRAG_PX = 4
_MAX_HISTORY = 20
_TRANSPARENCY = 0.6
#: How see through Isolate draws the other bodies (TR99).
_ISOLATE_TRANSPARENCY = 0.8
#: Display styles drawn by the hidden line computation (TR13).
HIDDEN_LINE_STYLES = ("hidden_lines", "hidden_lines_visible")
_KINDS = {"face": TopAbs_FACE, "edge": TopAbs_EDGE, "vertex": TopAbs_VERTEX}
_HANDLE_PICK_PX = 14  # how close (logical pixels) a press must be to grab a drag arrow
#: How close (logical pixels) the cursor must be to an edge or vertex to pick it. The
#: kernel's default of 2 device pixels made edges hard to hit for Fillet and Chamfer.
PICK_TOLERANCE_PX = 6
#: The note beside a snapped depth value (T5.2.4, D525).
SNAP_NOTES = {"vertex": strings.SNAP_TO_VERTEX, "face": strings.SNAP_TO_FACE}


def _hex(color: str) -> Quantity_Color:
    """A ``#RRGGBB`` colour exactly as Qt paints it (sRGB).

    Until D2760 this passed the numbers on as linear RGB, which the kernel then
    lightened: a red part was drawn salmon and the grey part lost its cool cast.
    """
    text = color.lstrip("#")
    r, g, b = (int(text[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    return Quantity_Color(r, g, b, Quantity_TOC_sRGB)


#: ``_hex`` under its older name.
_srgb_hex = _hex

#: What the graphics card said about its memory, asked once (D2820).
_CARD_MEMORY: list[int] = []


def _card_memory(view: Any) -> int:
    """The graphics card's memory in bytes, or 0 when the driver does not tell."""
    if not _CARD_MEMORY:
        _CARD_MEMORY.append(look.card_memory(view))
    return _CARD_MEMORY[0]


def background(
    palette: Palette,
) -> tuple[Quantity_Color, Quantity_Color, Aspect_GradientFillMethod]:
    """The view's gradient: top colour, bottom colour and a top to bottom fill.

    The theme colours are sRGB hex values, as Qt paints them, so the view
    strip and document tab above the view show exactly the top colour.
    (``Quantity_TOC_RGB`` is linear RGB and would wash them out.)
    """

    srgb = _srgb_hex

    return (
        srgb(palette.viewport_top),
        srgb(palette.viewport_bottom),
        Aspect_GradientFillMethod_Vertical,
    )


#: ``background`` under another name, for methods with a ``background`` argument.
background_of = background


def background_fill_none() -> Aspect_GradientFillMethod:
    """No gradient: a solid background colour (Save Image, TR24)."""
    return Aspect_GradientFillMethod.Aspect_GradientFillMethod_None


#: Line width of the partial (outline) preview, in device independent pixels.
PREVIEW_LINE_WIDTH = 3.0
#: Line width of the cross lines of a Fillet or Chamfer preview (PV3).
PREVIEW_EDGE_WIDTH = 1.0


def unclipped(item: AIS_Shape) -> None:
    """Keep ``item`` whole while the view's section planes cut the part (D586)."""
    from OCP.Graphic3d import Graphic3d_SequenceOfHClipPlane

    planes = Graphic3d_SequenceOfHClipPlane()
    planes.SetOverrideGlobal(True)
    item.SetClipPlanes(planes)


def preview_solid(shape: TopoDS_Shape, accent: Quantity_Color) -> AIS_Shape:
    """The see-through accent solid of a feature preview."""
    solid = AIS_Shape(shape)
    solid.SetColor(accent)
    solid.SetTransparency(PREVIEW_TRANSPARENCY)
    # Own depth buffer: the part never hides a removed volume inside it (PV2.3).
    solid.SetZLayer(Graphic3d_ZLayerId_Topmost)
    unclipped(solid)
    drawer = solid.Attributes()
    drawer.SetFaceBoundaryDraw(True)
    drawer.FaceBoundaryAspect().SetColor(accent)
    # The preview lies on the part's own faces. Pull it a little toward the camera
    # so the two never fight over depth, which shows as stripes and blotches.
    drawer.ShadingAspect().Aspect().SetPolygonOffsets(
        Aspect_POM_Fill, PREVIEW_OFFSET_FACTOR, PREVIEW_OFFSET_UNITS
    )
    return solid


def overlay_solid(faces: list[TopoDS_Shape], color: Quantity_Color) -> AIS_Shape:
    """Some faces a feature makes, see-through in ``color`` over the unchanged part (D1032).

    Drawn in the topmost layer, which has its own depth buffer, so the part never
    hides them while the faces still hide each other. Thin edges in the same colour.
    """
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound

    group = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(group)
    for face in faces:
        builder.Add(group, face)
    return preview_solid(group, color)


_font_set = False


def _use_ui_font() -> None:
    """Point the kernel's own text at the window's font, once (D2762)."""
    global _font_set
    if _font_set:
        return
    _font_set = True
    from contextlib import suppress

    from PySide6.QtWidgets import QApplication

    with suppress(Exception):  # the kernel's own font stays: text is never worth a crash
        look.use_ui_font(QApplication.font().family())


class ViewportWidget(QWidget):
    """3D view of a part with selection, standard views and display styles.

    If the 3D view cannot start, ``failed`` is emitted with a message and the
    widget stays empty. The app keeps running.
    """

    failed = Signal(str)
    selection_changed = Signal(list)  # list of TopoDS_Shape
    #: The turning centre was set (a point) or cleared (None) with a middle click (TR209).
    turn_centre_changed = Signal(object)
    cursor_point = Signal(object)  # (x, y, z) model point under the cursor, or None
    gesture = Signal(float, float)  # drag in pixels, y down
    context_menu = Signal(QPointF)
    plane_picked = Signal(str)  # plane id, while planes are shown for picking (W1)
    axis_picked = Signal(str)  # sketch line id, while axis lines are offered (W6.3)
    #: Ctrl and drag of a shown plane's border: plane id and offset in mm (TR10).
    plane_offset_dragged = Signal(str, float)
    escape_pressed = Signal()  # Escape with no view action (cancels a feature, W6.5)
    label_double_clicked = Signal(str)  # key of a dimension label (W5.4)
    handle_dragged = Signal(str, float)  # parameter name, new value in mm
    handle_released = Signal(str)
    handle_flipped = Signal(str)  # dragged past its start: reverse the direction (T5.2.5)
    #: A handle released while Alt snapped it to a part vertex: parameter name and the
    #: vertex, so the value can follow that point (TR395, D2207).
    handle_snapped = Signal(str, object)
    value_clicked = Signal(str, QPoint)  # the value beside a handle was clicked (T5.2.3)
    markers_boxed = Signal(list, bool)  # pattern instance markers inside a box (TR270, D2401)
    value_typed = Signal(str)  # a digit, minus, dot or = typed while a panel is open (T15.4)
    region_clicked = Signal(str)  # region name, while Selected Regions takes picks (T5.3.2)
    left_clicked = Signal(QPointF)  # a plain left click that selected as usual (T5.4)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_PaintOnScreen)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setMinimumSize(200, 150)

        self._driver = OpenGl_GraphicDriver(Aspect_DisplayConnection())
        self._viewer = V3d_Viewer(self._driver)
        self._setup_lights()
        self._context = AIS_InteractiveContext(self._viewer)
        self._context.SetDisplayMode(AIS_Shaded, True)
        self._context.SetPixelTolerance(PICK_TOLERANCE_PX)
        look.text_over_previews(self._context)  # values read over a preview (D2763)
        look.real_edges_only(self._context)  # no kernel curves across faces (D2823)
        _use_ui_font()
        self._view: V3d_View | None = None
        self._window: Aspect_NeutralWindow | None = None
        self._dpr = 1.0
        self._pending_part: tuple[TopoDS_Shape | None, str] | None = None
        self._part: AIS_Shape | None = None
        self._part_color: str = ""
        self._fitted = False
        self._palette: Palette = LIGHT
        self._drag: str | None = None
        self._triad_pick = "x"  # the corner triad axis pressed (TR210)
        self._large_part = False  # many faces: less smoothing while turning (TR214)
        #: Mouse and key preferences (TR211, D1607).
        self.wheel_reverse = False
        self.zoom_about_cursor = True
        self.arrow_step = keynav.ARROW_DEG
        self.turn_speed = 1.0
        self.fit_on_view = True
        self.mouse_preset = "turn"  # TR312
        self._blend: Any = None  # the before and after slider (TR224 item 4)
        self._future: list[Any] = []  # cameras Previous View left, for a swipe (TR380)
        self._through: tuple[object, Any] | None = None  # see through subshapes (TR224)
        self._turning_simple = False
        #: Smoothing samples of this view (D2820), and whether it has its window yet.
        self._samples = look.MSAA_SAMPLES
        self._drawing = False
        self._last = QPointF()
        self._press: QPointF | None = None
        self._press_twist = 0.0
        self._band: AIS_RubberBand | None = None
        self._failed = False
        self._released = False  # the kernel view was freed: the tab is closing (D2780)
        self.filters: set[str] = {"face", "edge", "vertex"}
        self.filters_on = False  # a selection filter limits the types (T14.3.2)
        #: Select Through Faces (TR64, D1800): clicks take the nearest edge behind faces.
        self.pick_through = False
        self.display_style = "shaded_edges"
        self.transparent = False
        self._see_through: list[TopoDS_Shape] = []  # bodies see through on their own (TR21)
        #: Bodies with their own display mode or transparency (TR216).
        self._body_modes: list[tuple[TopoDS_Shape, str, float]] = []
        self._body_wire: AIS_Shape | None = None
        #: Bodies see through while the section is on, and how much (TR355).
        self._section_see: tuple[list[TopoDS_Shape], float] = ([], 0.0)
        #: Bodies the section leaves whole, and their uncut drawing (TR213, D2500).
        self._section_whole: list[TopoDS_Shape] = []
        self._section_whole_item: AIS_Shape | None = None
        #: The section's cut faces, pickable for Measure (TR213, D2502).
        self._section_faces: AIS_Shape | None = None
        self._locked: list[TopoDS_Shape] = []  # locked bodies: greyed, never picked (TR269)
        self._isolate_others: Any = None  # TR99: bodies left out by Isolate, never picked
        self.isolate_look = "hidden"
        self._locked_map: Any = None
        self.perspective = False  # TR15: parallel until switched
        self.gesture_with_ctrl = False
        #: Shows the gesture guide during a right drag (T10.2).
        self.gesture_tracker = GestureTracker(self)
        self.zoom_area_armed = False
        self.lasso = False  # TR19: a left drag draws a free loop instead of a box
        self.paint = False  # TR329: a left drag picks every face it passes over
        self._loop: list[QPointF] = []
        self._history: list[Graphic3d_Camera] = []
        self._plane_drag: PlaneDrag | None = None  # Ctrl and drag a plane's border (TR10)
        self._highlight: AIS_Shape | None = None
        from fdcad.ui.viewport.edge_look import EdgeLook

        #: Smooth, hidden and feature edge options (TR212).
        self.edge_look = EdgeLook(self)
        self._ghost: AIS_Shape | None = None  # where a lost pick was (TR125)
        self._marked: AIS_Shape | None = None  # Select Other row under the cursor
        self._origin: Any = None  # the origin axes, while View > Origins is on
        self._hidden_faces: list[TopoDS_Shape] = []  # hidden while Select Other is open
        self._sketches: list[AIS_Shape] = []
        self._pending_sketches: list[TopoDS_Shape] | None = None
        self._planes: dict[str, tuple[TopoDS_Shape, AIS_Shape]] = {}
        #: Planes shown on purpose (D114) and their name labels (T13).
        self._shown_planes: dict[str, tuple[TopoDS_Shape, AIS_Shape]] = {}
        self._shown_labels: dict[str, AIS_TextLabel] = {}
        self._plane_labels: dict[str, AIS_TextLabel] = {}  # labels of the planes to pick
        self._plane_hover: str | None = None
        self._selected_planes: set[str] = set()
        self._axes: dict[str, tuple[TopoDS_Shape, AIS_Shape]] = {}
        #: Temporary axes (TR17): line items, and the face each one picks.
        self.temporary_axes_shown = False
        self._temp_axes: dict[str, tuple[TopoDS_Shape, AIS_Shape]] = {}
        self._temp_faces: dict[str, TopoDS_Shape] = {}
        self._part_shape: TopoDS_Shape | None = None
        from fdcad.ui.viewport.select_more import SelectionMemory

        #: The picks before the last clear, for Select Previous (TR93).
        self.selection_memory = SelectionMemory(self)
        from fdcad.ui.viewport.mirror_image import MirrorImage

        #: A see through mirror image of the part, display only (TR309).
        self.mirror_image = MirrorImage(self)
        from fdcad.ui.viewport.rim import HighlightRim

        #: The thin ground coloured line beside the outline of a highlight (D2821).
        self.rim = HighlightRim(self)
        self.selection_changed.connect(self.rim.set_selected)
        #: Sketch regions offered by the Selected Regions box (T5.3.2).
        self._regions = RegionLayer(self._context, lambda: _hex(ACCENT[is_dark()]))
        self._labels: list[tuple[str, tuple[float, float, float], AIS_TextLabel]] = []
        #: Counts user navigation (rotate, pan, zoom), so callers can tell if the view moved.
        self.nav_count = 0
        self._hover_pos: QPointF | None = None
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(16)  # at most 60 hover updates a second (PLAN 11.3.11)
        self._hover_timer.timeout.connect(self._hover)
        # Animated view turns (W1.3): start pose, end pose, clock, what to do after.
        self._turn: tuple[CameraPose, CameraPose, QElapsedTimer, int, Callable[[], None]] | None
        self._turn = None
        #: Length of animated view changes in ms (U6.6); 0 turns at once (reduce motion).
        self.turn_ms = 0
        self._turn_timer = QTimer(self)
        self._turn_timer.setInterval(16)
        self._turn_timer.timeout.connect(self._turn_step)
        # Live feature preview (C2, W6.4): the solid, drag arrows and a value callout.
        self._preview_data: PreviewData | None = None
        self._preview_active = "depth"
        self._preview_label: Callable[[str, float], str] = lambda _n, v: f"{v:.2f}"
        self._preview_shape: AIS_Shape | None = None
        self._wires: AIS_Shape | None = None  # cross lines of a round or chamfer (PV3)
        self._overlay: list[AIS_Shape] = []  # face overlay of a result preview (D1032)
        #: Frame the next feature preview once it shows (the view just turned).
        self.fit_next_preview = False
        self._drag_travel: float | None = None  # where the dragged handle is now
        self._arrows: list[tuple[PreviewHandle, AIS_Shape]] = []
        self._callout: AIS_TextLabel | None = None
        self._grab: tuple[str, float] | None = None  # dragged parameter, grab offset
        self._drag_state: HandleDrag | None = None
        self._ruler: AIS_Shape | None = None
        self._callout_at: tuple[str, Vec3, str] | None = None  # param, anchor, text
        self._snap_mark: Any = None  # the marker on an Alt snapped point (T5.2.4)
        self._snap_vertex: Any = None  # the part vertex of the last Alt snap (TR395)
        #: Click then click handles (TR293, D2209): a handle clicked without a drag
        #: follows the cursor until the next click; arrows nudge it; Escape puts it back.
        self._click_handle = False
        self._handle_press: QPointF | None = None
        self._handle_start_value = 0.0
        self._handle_value = 0.0
        #: Value labels of fields without a handle (T15.2): param, placed point, text, item.
        self._value_items: list[tuple[str, Vec3, str, AIS_TextLabel]] = []

    # Qt plumbing -----------------------------------------------------------

    def paintEngine(self) -> QPaintEngine | None:  # type: ignore[override]  # noqa: N802
        """Return no paint engine: OCCT draws this widget, not Qt."""
        return None

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        """Create the OCCT view the first time the native window exists."""
        super().showEvent(event)
        if self._view is None and not self._failed and not self._released:
            try:
                self._init_view()
            except Exception as exc:  # a viewer failure must never crash the app
                self._failed = True
                self._view = None
                self._window = None
                self.failed.emit(
                    f"The 3D view could not start: {exc}. "
                    "Update your graphics driver, then restart FDCAD."
                )

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Redraw the OCCT view."""
        if self._view is not None:
            self._view.Redraw()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Keep the OCCT window size in device pixels."""
        super().resizeEvent(event)
        self._sync_size()

    def event(self, event: QEvent) -> bool:
        """Handle screen changes (DPI) and trackpad pinch gestures."""
        if event.type() in (QEvent.Type.DevicePixelRatioChange, QEvent.Type.ScreenChangeInternal):
            self._sync_size()
        if (
            isinstance(event, QNativeGestureEvent)
            and event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture
        ):
            self._remember_once()
            self._zoom_at(event.position(), 1.0 + event.value())
            return True
        if isinstance(event, QNativeGestureEvent) and self._gesture(event):
            return True
        return super().event(event)

    def _gesture(self, event: QNativeGestureEvent) -> bool:
        """Trackpad rotate rolls the view, smart zoom fits, and a swipe goes to the
        previous or next view (TR380 item 1, D1612). True when handled."""
        kind = event.gestureType()
        if self._view is None:
            return False
        if kind == Qt.NativeGestureType.RotateNativeGesture:
            self._remember_once()
            self._view.SetTwist(self._view.Twist() - math.radians(event.value()))
            self._view.Redraw()
            return True
        if kind == Qt.NativeGestureType.SmartZoomNativeGesture:
            self.fit_all()
            return True
        if kind == Qt.NativeGestureType.SwipeNativeGesture:
            if keynav.swipe_back(event.value()):
                self.previous_view()
            else:
                self.next_view()
            return True
        return False

    # Public API --------------------------------------------------------------

    def show_part(
        self,
        shape: TopoDS_Shape | None,
        color: str | None = None,
        faces: list[tuple[TopoDS_Shape, str]] | None = None,
    ) -> None:
        """Show the part, replacing what was shown before.

        The first part shown is fitted to the view; later rebuilds keep the camera.
        The selection is cleared, since its shapes belong to the old part.
        """
        color = color or self._palette.face
        self._part_color = color
        if self._view is None:
            self._pending_part = (shape, color)
            self._pending_faces = faces
            return
        had_selection = self._context.NbSelected() > 0
        self.rim.clear()  # its shapes belong to the old part
        if self._part is not None:
            self._context.Remove(self._part, False)
            self._part = None
        self._hidden_faces = []
        if shape is not None:
            from OCP.AIS import AIS_ColoredShape

            self._part_shape = shape  # the edge options read it (TR212)
            from fdcad.ui.viewport.display_quality import is_large

            self._large_part = is_large(shape)  # draw simpler while turning (TR214)
            presentation = AIS_ColoredShape(shape)  # can hide one face (Select Other)
            presentation.SetColor(_hex(color))
            for face, face_color in faces or []:
                presentation.SetCustomColor(face, _hex(face_color))  # P2.11
            for solid in self._see_through:
                presentation.SetCustomTransparency(solid, _TRANSPARENCY)  # TR21
            for solid in self._section_see[0]:
                presentation.SetCustomTransparency(solid, self._section_see[1])  # TR355
            for solid in self._section_whole:
                presentation.CustomAspects(solid).SetHidden(True)  # TR213: drawn uncut
            self._apply_body_modes(presentation)  # TR216
            for solid in self._locked:
                presentation.SetCustomColor(solid, _hex(self._palette.sketch_reference))
            look.style_part(presentation.Attributes(), self._palette, self._dpr)
            self._part = presentation
            self._apply_style(update=False)
            self._context.Display(presentation, False)
            self._draw_whole()
            self.edge_look.refresh()
            self._activate()
            if self.transparent:
                self._context.SetTransparency(presentation, _TRANSPARENCY, False)
        self._part_shape = shape
        if self.temporary_axes_shown:
            self._show_temporary_axes()
        if self.mirror_image.plane is not None:
            self.mirror_image.refresh()  # TR309: follows the rebuilt part
        if had_selection:
            self.selection_changed.emit([])
        if shape is not None and not self._fitted:
            self._fitted = True
            self.fit_all(remember=False)
        else:
            self._context.UpdateCurrentViewer()

    # Live preview ------------------------------------------------------------

    def show_preview(
        self, data: PreviewData, active: str, label: Callable[[str, float], str]
    ) -> None:
        """Show a see-through accent preview with drag arrows, replacing the last one."""
        self._remove_preview()
        self._preview_data, self._preview_active, self._preview_label = data, active, label
        shape = data.geometry.shape
        if self._view is None or (shape is None and not data.arrows):
            return
        accent = _hex(ACCENT[is_dark()])
        if shape is not None and data.geometry.outline:
            # Partial preview: only the outline of the new faces, over the part (D585).
            lines = AIS_Shape(shape)
            lines.SetColor(accent)
            lines.SetWidth(PREVIEW_LINE_WIDTH * self._dpr)
            look.drop_face_curves(lines.Attributes())
            lines.SetZLayer(Graphic3d_ZLayerId_Topmost)
            unclipped(lines)
            self._context.Display(lines, AIS_WireFrame, -1, False)  # -1: never picked
            self._preview_shape = lines
        elif shape is not None and data.geometry.replaces_part and self._part is not None:
            # Fillet, Chamfer, Shell, Draft, Move Face: only the faces the feature makes,
            # see-through over the unchanged part (D1032).
            groups = [
                (data.geometry.accent, accent),
                (data.geometry.held, _hex(self._palette.handle_idle)),
                (data.geometry.stretched, _hex(self._palette.state_warning)),
            ]
            self._overlay = []
            for faces, color in groups:
                if faces:
                    item = overlay_solid(faces, color)
                    self._context.Display(item, AIS_Shaded, -1, False)  # -1: never picked
                    self._overlay.append(item)
            if data.geometry.lines is not None:  # fillet and chamfer cross lines (PV3)
                wires = AIS_Shape(data.geometry.lines)
                wires.SetColor(accent)
                wires.SetWidth(PREVIEW_EDGE_WIDTH * self._dpr)
                wires.SetZLayer(Graphic3d_ZLayerId_Topmost)
                unclipped(wires)
                self._context.Display(wires, AIS_WireFrame, -1, False)
                self._overlay.append(wires)
                self._wires = wires
            self._preview_shape = self._overlay[0] if self._overlay else None
            self._open_blend()  # TR224 item 4
        elif shape is not None:  # a handle only preview (the section view) has no solid
            solid = preview_solid(shape, accent)
            self._context.Display(solid, AIS_Shaded, -1, False)  # -1: never picked
            self._preview_shape = solid
        for handle, arrow in zip(data.handles, data.arrows, strict=False):
            mark = AIS_Shape(arrow)
            mark.SetColor(accent if handle.param == active else _hex(self._palette.handle_idle))
            mark.SetZLayer(Graphic3d_ZLayerId_Topmost)
            unclipped(mark)  # the section view never cuts a handle (D586)
            self._context.Display(mark, AIS_Shaded, -1, False)
            self._arrows.append((handle, mark))
        current = next((h for h in data.handles if h.param == active), None)
        if self._drag_state is not None and self._drag_state.handle.param == active:
            self._show_ruler()
        if current is not None:
            self._show_callout(current, current.value)
        if self.fit_next_preview and self._drag_state is None:
            self.fit_next_preview = False
            self._view.FitAll(0.1, False)  # the whole preview in the middle of the view
        self._context.UpdateCurrentViewer()

    def clear_preview(self) -> None:
        """Remove the preview and forget its shapes."""
        self._remove_preview()
        self._preview_data = None
        self._grab = None
        if self._view is not None:
            self._context.UpdateCurrentViewer()

    def _remove_preview(self) -> None:
        self._remove_value_labels()
        for obj in [
            self._preview_shape, self._callout, self._ruler, *self._overlay,
            *(m for _h, m in self._arrows),
        ]:  # fmt: skip
            if obj is not None:
                self._context.Remove(obj, False)
        self._preview_shape, self._callout, self._arrows = None, None, []
        self._overlay, self._wires = [], None
        self._ruler, self._callout_at = None, None
        self._hide_snap_mark(update=False)
        if self._blend is not None:
            self._blend.hide()

    def _open_blend(self) -> None:
        """Show the before and after slider at After (TR224 item 4)."""
        from fdcad.ui.viewport.blend import BlendSlider

        if self._blend is None:
            self._blend = BlendSlider(self, self.set_preview_blend)
        self._blend.open()

    def set_preview_blend(self, t: float) -> None:
        """Fade a face overlay preview: 0 shows it fully, 1 hides it (PV6, D1032)."""
        if not self._overlay:
            return
        t = max(0.0, min(1.0, t))
        for item in self._overlay:
            if t >= 0.999 or (item is self._wires and t > 0.5):  # lines do not fade
                self._context.Erase(item, False)
                continue
            if item is self._wires:
                self._context.Display(item, AIS_WireFrame, -1, False)
                continue
            self._context.Display(item, AIS_Shaded, -1, False)
            fade = PREVIEW_TRANSPARENCY + t * (1.0 - PREVIEW_TRANSPARENCY)
            self._context.SetTransparency(item, fade, False)
        self._context.UpdateCurrentViewer()

    def _see_through_subshapes(self) -> Any:
        """Every face, edge and vertex of the bodies drawn see through (TR21, TR216,
        TR355), as a shape map, found once per shown part."""
        from OCP.TopExp import TopExp

        from fdcad.core.occ import ShapeMap

        key = (self._part_shape, len(self._see_through), len(self._section_see[0]))
        if self._through is not None and self._through[0] == key:
            return self._through[1]
        found = ShapeMap()
        solids = [*self._see_through, *self._section_see[0]]
        solids += [s for s, _m, t in self._body_modes if t > 0]
        for solid in solids:
            TopExp.MapShapes_s(solid, found)
        self._through = (key, found)
        return found

    def _detected(self) -> list[tuple[bool, TopoDS_Shape | None]]:
        """What the last ``MoveTo`` found, nearest first (D2781): for each item, whether
        it belongs to the part, and the face, edge or vertex it stands for (None for an
        item that is not a shape, such as a label).

        The shape is read from each detected owner. The kernel's
        ``DetectedCurrentShape`` gives the whole shape of the shown item, which for
        the part is the part itself, not the face under the cursor.
        """
        from OCP.StdSelect import StdSelect_BRepOwner

        out: list[tuple[bool, TopoDS_Shape | None]] = []
        ctx = self._context
        ctx.InitDetected()
        while ctx.MoreDetected():
            owner = ctx.DetectedCurrentOwner()
            if owner is not None:
                mine = self._part is not None and owner.IsSameSelectable(self._part)
                shape = owner.Shape() if isinstance(owner, StdSelect_BRepOwner) else None
                out.append((mine, None if shape is None or shape.IsNull() else shape))
            ctx.NextDetected()
        return out

    def _detected_on_part(self) -> list[TopoDS_Shape]:
        """The part's faces, edges and vertices the last ``MoveTo`` found, nearest
        first, without repeats and without faces hidden for now (D2781)."""
        out: list[TopoDS_Shape] = []
        for mine, shape in self._detected():
            if mine and shape is not None and not any(shape.IsSame(s) for s in out):
                out.append(shape)
        return [s for s in out if not any(s.IsSame(h) for h in self._hidden_faces)]

    def _edge_through(self) -> TopoDS_Shape | None:
        """The nearest edge under the cursor, behind any faces, while Select Through
        Faces is on (TR64, D1800); None otherwise."""
        if not self.pick_through or "edge" not in self.filters:
            return None
        from fdcad.ui.viewport.through_edges import first_edge

        edge: TopoDS_Shape | None = first_edge(self._detected_on_part())
        return edge

    def _through_pick(self, mods: Qt.KeyboardModifier) -> TopoDS_Shape | None:
        """The first item under the cursor behind see through bodies, when the top one
        is on a see through body; None to pick as usual. Shift picks the see through
        item itself (TR224 item 1)."""
        if mods & Qt.KeyboardModifier.ShiftModifier or self.transparent:
            return None
        if not (self._see_through or self._section_see[0] or self._body_modes):
            return None
        through = self._see_through_subshapes()
        if through.Extent() == 0:
            return None
        first = True
        for _mine, shape in self._detected():
            if shape is None or not through.Contains(shape):
                return None if first else shape
            first = False
        return None

    def _remove_value_labels(self) -> None:
        for _param, _point, _text, item in self._value_items:
            self._context.Remove(item, False)
        self._value_items = []

    def show_value_labels(self, labels: list[ValueLabel]) -> None:
        """Show the values of fields without a drag handle at their anchor (T15.2).

        Labels never cover each other or the handle's value: later ones move
        down the screen until they are clear.
        """
        self._remove_value_labels()
        if self._view is None or not labels:
            if self._view is not None:
                self._context.UpdateCurrentViewer()
            return
        height = look.VALUE_TEXT_HEIGHT * self._dpr
        taken = []
        if self._callout_at is not None:
            _p, anchor, text = self._callout_at
            taken.append(label_box(self._screen(anchor), text, height))
        screens = [self._screen(label.point) for label in labels]
        boxes = [
            label_box(at, label.text, height) for at, label in zip(screens, labels, strict=True)
        ]
        for label, at, dy in zip(labels, screens, spread_labels(boxes, taken), strict=True):
            point = self._moved_down(label.point, at, dy)
            item = AIS_TextLabel()
            look.style_value(item, self._palette, ACCENT[is_dark()], self._dpr)
            item.SetPosition(gp_Pnt(*point))
            item.SetText(TCollection_ExtendedString(look.value_text(label.text), True))
            self._context.Display(item, 0, -1, False)
            self._value_items.append((label.param, point, label.text, item))
        self._context.UpdateCurrentViewer()

    def _moved_down(self, point: Vec3, at: tuple[float, float], dy: float) -> Vec3:
        """``point`` moved ``dy`` device pixels down the screen, in the view plane."""
        if dy == 0 or self._view is None:
            return point
        x0, y0, z0, *_rest = self._view.ConvertWithProj(int(at[0]), int(at[1]))
        x1, y1, z1, *_more = self._view.ConvertWithProj(int(at[0]), int(at[1] + dy))
        return (point[0] + x1 - x0, point[1] + y1 - y0, point[2] + z1 - z0)

    def value_label_pos(self, param: str) -> QPoint | None:
        """Where the value label of ``param`` is, in widget coordinates, or None (T15.3)."""
        if self._view is None:
            return None
        spots = [(p, a) for p, a, _t, _i in self._value_items]
        if self._callout_at is not None:
            spots.append((self._callout_at[0], self._callout_at[1]))
        for name, anchor in spots:
            if name == param:
                x, y = self._screen(anchor)
                return QPoint(int(x / self._dpr), int(y / self._dpr) - 14)
        return None

    def _show_ruler(self) -> None:
        """Show the ruler of the dragged handle (made on the worker with the preview)."""
        state, data = self._drag_state, self._preview_data
        if state is None or data is None:
            return
        index = next((i for i, h in enumerate(data.handles) if h.param == state.handle.param), -1)
        ruler = data.rulers[index] if 0 <= index < len(data.rulers) else None
        if ruler is None:
            return
        if self._ruler is not None:
            self._context.Remove(self._ruler, False)
        item = AIS_Shape(ruler)
        item.SetColor(_hex(ACCENT[is_dark()]))
        item.SetZLayer(Graphic3d_ZLayerId_Topmost)
        self._context.Display(item, AIS_WireFrame, -1, False)
        self._ruler = item

    def _on_ruler(self, handle: PreviewHandle, pos: QPointF) -> bool:
        """True when the cursor is near the dragged handle's ruler (T5.2.2, T6.3.1)."""
        from fdcad.ui.viewport.handles import ruler_span

        if handle.step <= 0 or self._ruler is None:
            return False
        start, end = ruler_span(handle)
        count = 72 if handle.is_angle else 1
        ts = [start + (end - start) * k / count for k in range(count + 1)]
        points = [self._screen(handle.point(t)) for t in ts]
        return polyline_distance(self._px(pos), points) <= RULER_PICK_PX * self._dpr

    def markers_in(self, press: QPointF, pos: QPointF) -> list[str]:
        """The pattern instance marker labels inside the box from ``press`` to ``pos``
        (TR270 item 3, D2401), in the order shown."""
        from fdcad.ui.viewport.value_labels import MARKER_PREFIX

        if self._view is None:
            return []
        (x0, y0), (x1, y1) = self._px(press), self._px(pos)
        left, right, top, bottom = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
        out = []
        for param, anchor, _text, _item in self._value_items:
            if param.startswith(MARKER_PREFIX):
                x, y = self._screen(anchor)
                if left <= x <= right and top <= y <= bottom:
                    out.append(param)
        return out

    def _value_at(self, pos: QPointF) -> str | None:
        """The value label under the cursor, if any (T5.2.3, T15.3)."""
        if self._view is None:
            return None
        spots = [(p, a, t) for p, a, t, _i in self._value_items]
        if self._callout_at is not None:
            spots.insert(0, self._callout_at)
        for param, anchor, text in spots:
            if label_hit(self._screen(anchor), text, 14.0 * self._dpr, self._px(pos)):
                return param
        return None

    def _show_callout(
        self, handle: PreviewHandle, value: float, flipped: bool = False, note: str = ""
    ) -> None:
        if self._callout is None:
            callout = AIS_TextLabel()
            look.style_value(callout, self._palette, ACCENT[is_dark()], self._dpr)
            self._callout = callout
            self._context.Display(callout, 0, -1, False)
        size = self._preview_data.arrow_size if self._preview_data is not None else 1.0
        if flipped:  # beyond the tip on the other side of the start
            anchor = handle.point(-value / handle.scale - size * 1.4)
        else:
            anchor = handle.beyond(value, size * 1.4)
        text = self._preview_label(handle.param, value)
        if note:
            text = f"{text} {note}"
        self._callout.SetPosition(gp_Pnt(*anchor))
        self._callout.SetText(TCollection_ExtendedString(look.value_text(text), True))
        self._context.Redisplay(self._callout, False)
        self._callout_at = (handle.param, anchor, text)

    def _screen(self, point: Vec3) -> tuple[float, float]:
        assert self._view is not None
        x, y = self._view.Convert(float(point[0]), float(point[1]), float(point[2]))
        return float(x), float(y)

    def ray_at(self, pos: QPointF) -> tuple[Vec3, Vec3] | None:
        """The view ray under widget point ``pos``: a point and a direction into the view."""
        if self._view is None:
            return None
        px, py = self._px(pos)
        x, y, z, _vx, _vy, _vz = self._view.ConvertWithProj(int(px), int(py))
        ex, ey, ez = self._view.Proj()  # from the scene towards the eye
        length = math.hypot(ex, ey, ez)
        if length < 1e-12:
            return None
        ex, ey, ez = ex / length, ey / length, ez / length
        back = 1e6  # start well in front of the part, so every body is ahead
        start = (float(x) + ex * back, float(y) + ey * back, float(z) + ez * back)
        return start, (-ex, -ey, -ez)

    def _handle_at(self, pos: QPointF) -> PreviewHandle | None:
        """The drag arrow under the cursor, if any."""
        if self._view is None or self._preview_data is None:
            return None
        px, py = self._px(pos)
        size = self._preview_data.arrow_size
        best, best_d = None, _HANDLE_PICK_PX * self._dpr
        for handle, _mark in self._arrows:
            tip, d = handle.tip, handle.pointing
            middle = (tip[0] + d[0] * size / 2, tip[1] + d[1] * size / 2, tip[2] + d[2] * size / 2)
            points = [tip, middle]
            if handle.is_angle and handle.radius > 0:
                points.append(handle.beyond(handle.value, -size))  # along the curved shaft
            for point in points:
                sx, sy = self._screen(point)
                dist = ((sx - px) ** 2 + (sy - py) ** 2) ** 0.5
                if dist <= best_d:
                    best, best_d = handle, dist
        return best

    def _handle_distance(self, handle: PreviewHandle, pos: QPointF) -> float | None:
        """How far along the handle the cursor is: mm, or radians for angle handles."""
        px, py = self._px(pos)
        if handle.is_angle:
            previous = self._drag_travel if self._drag_travel is not None else handle.travel
            coarse = [i * math.pi / 90 for i in range(180)]  # every 2 degrees
            samples = [(t, self._screen(handle.point(t))) for t in coarse]
            found = drag_angle(samples, (px, py), previous)
            if found is None:
                return None
            fine = [found + math.radians(0.1) * k for k in range(-20, 21)]
            return drag_angle([(t, self._screen(handle.point(t))) for t in fine], (px, py), found)
        size = self._preview_data.arrow_size if self._preview_data is not None else 1.0
        length = max(abs(handle.travel), size, 1.0)
        b, d = handle.base, handle.direction
        ahead = (b[0] + d[0] * length, b[1] + d[1] * length, b[2] + d[2] * length)
        return drag_distance(self._screen(b), self._screen(ahead), (px, py), length)

    def _start_handle_drag(self, handle: PreviewHandle, pos: QPointF) -> None:
        self._handle_press = pos
        self._handle_start_value = self._handle_value = handle.value
        self._drag_travel = None
        distance = self._handle_distance(handle, pos)
        offset = handle.value_at(distance) - handle.value if distance is not None else 0.0
        self._grab = (handle.param, offset)
        self._drag_state = HandleDrag(handle, offset)
        self._drag_travel = handle.travel
        if handle.param != self._preview_active and self._preview_data is not None:
            self.show_preview(self._preview_data, handle.param, self._preview_label)
        else:
            self._show_ruler()

    def _drag_handle(self, pos: QPointF, snap: bool = False) -> None:
        if self._grab is None or self._view is None:
            return
        param, offset = self._grab
        found = next(((h, m) for h, m in self._arrows if h.param == param), None)
        if found is None:
            return
        current, mark = found
        state = self._drag_state or HandleDrag(current, offset)
        handle = state.handle  # distances are measured along the handle as it was at the press
        was_flipped = state.flipped
        # Alt over a part vertex or face snaps the end to it (T5.2.4, D525).
        self._snap_vertex = None
        snapped = self._snap_target(handle, pos) if snap and handle.snaps else None
        note = ""
        if snapped is not None:
            point, kind = snapped
            value = state.snap_to(travel_to(handle, point))
            note = SNAP_NOTES.get(kind, "")
            self._show_snap_mark(point)
        else:
            self._hide_snap_mark(update=False)
            distance = self._handle_distance(handle, pos)
            if distance is None:
                return
            value = state.update(distance, self._on_ruler(handle, pos))
        travel = state.travel(value)
        self._drag_travel = travel
        # Move the arrow at once; the solid follows when the new preview is built.
        move = gp_Trsf()
        if handle.is_angle:
            assert handle.centre is not None
            axis = gp_Ax1(gp_Pnt(*handle.centre), gp_Dir(*handle.direction))
            move.SetRotation(axis, travel - current.travel)
        else:
            tip, target = current.tip, handle.point(travel)
            move.SetTranslation(gp_Vec(*(target[i] - tip[i] for i in range(3))))
            pointing = handle.pointing if not state.flipped else tuple(-v for v in handle.pointing)
            if sum(pointing[i] * current.pointing[i] for i in range(3)) < 0:
                mirror = gp_Trsf()
                mirror.SetMirror(gp_Pnt(*tip))  # turn the arrow round where it stands
                move.Multiply(mirror)
        self._context.SetLocation(mark, TopLoc_Location(move))
        self._show_callout(handle, value, state.flipped, note)
        self._view.Redraw()
        if state.flipped != was_flipped:
            self.handle_flipped.emit(param)
        self._handle_value = value
        self.handle_dragged.emit(param, value)

    def _snap_target(self, handle: PreviewHandle, pos: QPointF) -> tuple[Vec3, str] | None:
        """The part vertex or face under the cursor as a snap point (T5.2.4, D525).

        Uses the view's own detection (picking only, no kernel builds). A vertex
        wins over a face; a face gives its plane when it is flat and parallel
        to the sketch plane, else the point under the cursor.
        """
        from OCP.BRep import BRep_Tool
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.GeomAbs import GeomAbs_Plane
        from OCP.TopoDS import TopoDS

        if self._view is None or self._part is None or handle.is_angle:
            return None
        x, y = self._px(pos)
        ctx = self._context
        ctx.MoveTo(x, y, self._view, False)
        face = None
        for shape in self._detected_on_part():
            if shape.ShapeType() == TopAbs_VERTEX:
                vertex = TopoDS.Vertex(shape)
                self._snap_vertex = vertex  # TR395: the value can follow it
                p = BRep_Tool.Pnt_s(vertex)
                return (p.X(), p.Y(), p.Z()), "vertex"
            if face is None and shape.ShapeType() == TopAbs_FACE:
                face = shape
        picked = self._point_under_cursor()
        if face is None or picked is None:
            return None
        surface = BRepAdaptor_Surface(TopoDS.Face(face))
        plane = None
        if surface.GetType() == GeomAbs_Plane:
            pln = surface.Plane()
            o, n = pln.Location(), pln.Axis().Direction()
            plane = ((o.X(), o.Y(), o.Z()), (n.X(), n.Y(), n.Z()))
        return snap_point(handle, picked, plane), "face"

    def _show_snap_mark(self, point: Vec3) -> None:
        """A small marker on the snapped point."""
        from OCP.AIS import AIS_Point
        from OCP.Aspect import Aspect_TOM_O_PLUS
        from OCP.Geom import Geom_CartesianPoint

        self._hide_snap_mark(update=False)
        mark = AIS_Point(Geom_CartesianPoint(gp_Pnt(*point)))
        mark.SetMarker(Aspect_TOM_O_PLUS)
        mark.SetColor(_hex(ACCENT[is_dark()]))
        mark.SetZLayer(Graphic3d_ZLayerId_Topmost)
        self._context.Display(mark, 0, -1, False)
        self._snap_mark = mark

    def _hide_snap_mark(self, update: bool = True) -> None:
        if self._snap_mark is not None:
            self._context.Remove(self._snap_mark, update)
            self._snap_mark = None

    def set_palette(self, palette: Palette) -> None:
        """Use the theme's viewport colours."""
        self._palette = palette
        look.style_highlights(self._context, palette, self._dpr)
        self.rim.restyle()
        if self._part is not None:
            look.style_part(self._part.Attributes(), palette, self._dpr)
            self._context.Redisplay(self._part, False)
        if self._origin is not None:  # the origin follows the theme too (D2766)
            look.style_origin(self._origin, palette, self._dpr)
            self._context.Redisplay(self._origin, False)
        if self._view is not None:
            self._view.SetBgGradientColors(*background(palette), False)
            look.show_triad(self._view, palette, self._dpr)
            self._restyle_planes()
            self._context.UpdateCurrentViewer()

    def set_view(self, name: str) -> None:
        """Look along a standard direction (Y up), and fit unless the preference is off
        (TR211)."""
        eye, up = STANDARD_VIEWS[name]
        self._turn_to(eye, up, self.turn_ms, fit=self.fit_on_view)

    def look(self, eye: Vec3, up: Vec3) -> None:
        """Look from direction ``eye`` with ``up`` pointing up, and fit.

        With ``turn_ms`` above 0 the camera turns there smoothly (U6.6).
        """
        self._turn_to(eye, up, self.turn_ms)

    def _triad_axis(self, pos: QPointF) -> str | None:
        """The corner triad axis under ``pos``, or None (TR210)."""
        from fdcad.ui.viewport.triad import axis_at

        pose = self.eye_up() if self._view is not None else None
        if pose is None:
            return None
        dpr = getattr(self, "_dpr", 1.0)
        return axis_at(pos.x() * dpr, pos.y() * dpr, self.height() * dpr, pose[0], pose[1], dpr)

    def click_triad(self, axis: str, quarter: bool = False) -> None:
        """Look along a triad axis, from the other side when already there, or turn a
        quarter turn about it with ``quarter`` (Shift and click, TR210)."""
        from fdcad.ui.viewport.triad import triad_view

        pose = self.eye_up()
        if pose is None:
            return
        self.nav_count += 1
        self.look(*triad_view(axis, pose[0], pose[1], quarter))

    def eye_up(self) -> tuple[Vec3, Vec3] | None:
        """The current direction toward the eye and the up vector (Normal To rules)."""
        if self._view is None:
            return None
        self._finish_turn()
        e, u = self._view.Proj(), self._view.Up()
        return (e[0], e[1], e[2]), (u[0], u[1], u[2])

    def zoom_to(self, shapes: list[TopoDS_Shape]) -> bool:
        """Fit the view to these shapes (Zoom to Selection). False when there is nothing."""
        from OCP.Bnd import Bnd_Box
        from OCP.BRepBndLib import BRepBndLib

        if self._view is None or not shapes:
            return False
        box = Bnd_Box()
        for shape in shapes:
            BRepBndLib.Add_s(shape, box)
        if box.IsVoid():
            return False
        self._remember()
        self._view.FitAll(box, 0.2)
        self._view.Redraw()
        return True

    def set_origin_shown(self, on: bool) -> None:
        """Show or hide the part origin as three small axes (View > Origins, T14.4.3)."""
        from OCP.AIS import AIS_Trihedron
        from OCP.Geom import Geom_Axis2Placement
        from OCP.gp import gp_Ax2

        if self._origin is not None:
            self._context.Remove(self._origin, False)
            self._origin = None
        if on:
            item = AIS_Trihedron(Geom_Axis2Placement(gp_Ax2()))
            item.SetSize(20.0)
            look.style_origin(item, self._palette, self._dpr)
            self._context.Display(item, False)
            self._context.Deactivate(item)  # never picked
            self._origin = item
        if self._view is not None:
            self._context.UpdateCurrentViewer()

    def normal_to(self, normal: Vec3) -> None:
        """Look straight at a face with this outward normal."""
        if self._view is not None:
            u = self._view.Up()
            eye, up = view_for_normal(normal, (u[0], u[1], u[2]))
            self.look(eye, up)

    def animate_normal_to(
        self, normal: Vec3, duration_ms: int, done: Callable[[], None] = lambda: None
    ) -> None:
        """Turn smoothly to look straight at a face, then call ``done`` (W1.3).

        With ``duration_ms`` 0 (animations off) or no 3D view it turns at once.
        """
        if self._view is None:
            done()
            return
        self._finish_turn()
        u = self._view.Up()
        eye, up = view_for_normal(normal, (u[0], u[1], u[2]))
        self._turn_to(eye, up, duration_ms, done)

    def _turn_to(
        self,
        eye: Vec3,
        up: Vec3,
        duration_ms: int,
        done: Callable[[], None] = lambda: None,
        fit: bool = True,
    ) -> None:
        """Turn to look from ``eye`` with ``up``, fitted (unless ``fit`` is False), eased
        over ``duration_ms``."""
        self._finish_turn()
        if self._view is None:
            done()
            return
        self._remember()
        start = self._pose()
        self._view.SetProj(*eye)
        self._view.SetUp(*up)
        if fit:
            self._fit_content(update=False)
        end = self._pose()
        if duration_ms <= 0:
            self._view.Redraw()
            done()
            return
        self._set_pose(start)
        clock = QElapsedTimer()
        clock.start()
        self._turn = (start, end, clock, duration_ms, done)
        self._turn_timer.start()

    def camera_pose(self) -> CameraPose | None:
        """The current camera, to put back later with :meth:`restore_pose`."""
        if self._view is None:
            return None
        self._finish_turn()
        return self._pose()

    def restore_pose(self, pose: CameraPose) -> None:
        """Put the camera back where :meth:`camera_pose` found it (T1.5.2)."""
        if self._view is None:
            return
        self._finish_turn()
        self._remember()
        self._set_pose(pose)
        self._view.Redraw()

    def _pose(self) -> CameraPose:
        assert self._view is not None
        cam = self._view.Camera()
        c, d, u = cam.Center(), cam.Direction(), cam.Up()
        return CameraPose(
            (c.X(), c.Y(), c.Z()),
            (d.X(), d.Y(), d.Z()),
            (u.X(), u.Y(), u.Z()),
            cam.Distance(),
            cam.Scale(),
        )

    def _set_pose(self, pose: CameraPose) -> None:
        assert self._view is not None
        cam = self._view.Camera()
        cam.SetEyeAndCenter(gp_Pnt(*pose.eye), gp_Pnt(*pose.center))
        cam.SetUp(gp_Dir(*pose.up))
        cam.SetScale(pose.scale)

    def _turn_step(self) -> None:
        if self._turn is None or self._view is None:
            self._turn_timer.stop()
            return
        start, end, clock, duration, _done = self._turn
        t = clock.elapsed() / duration
        if t >= 1.0:
            self._finish_turn()
            return
        self._set_pose(blend_pose(start, end, ease(t)))
        self._view.Redraw()

    def _finish_turn(self) -> None:
        """End a running turn at once, at its end pose."""
        self._turn_timer.stop()
        turn, self._turn = self._turn, None
        if turn is None:
            return
        if self._view is not None:
            self._set_pose(turn[1])
            self._view.Redraw()
        turn[4]()

    def fit_all(self, remember: bool = True) -> None:
        """Zoom so everything shown fits in the view."""
        if self._view is not None:
            self._finish_turn()
            if remember:
                self._remember()
            self._fit_content(update=False)
            self._view.Redraw()

    def _fit_content(self, update: bool) -> None:
        """Fit the part, its sketches and the preview, centred in the view.

        Planes, axes, labels and the origin are helpers drawn around the part and
        can be much larger than a small part, so with a part shown they are left
        out and the part fills the view. An empty part frames everything shown.
        """
        assert self._view is not None
        from OCP.Bnd import Bnd_Box
        from OCP.BRepBndLib import BRepBndLib

        if self._part is None:
            self._view.FitAll(look.FIT_MARGIN, update)
            return
        box = Bnd_Box()
        items = [self._part, *self._sketches, self._preview_shape, *self._overlay]
        for item in items:
            if item is not None:
                BRepBndLib.Add_s(item.Shape(), box)
        if box.IsVoid():
            self._view.FitAll(look.FIT_MARGIN, update)
            return
        self._view.FitAll(box, look.FIT_MARGIN, update)

    def _centre_on_part(self) -> None:
        """Move the view so the part's middle is in the middle, keeping zoom and direction."""
        assert self._view is not None
        from OCP.Bnd import Bnd_Box
        from OCP.BRepBndLib import BRepBndLib

        if self._part is None:
            return
        box = Bnd_Box()
        BRepBndLib.Add_s(self._part.Shape(), box)
        if box.IsVoid():
            return
        lo, hi = box.CornerMin(), box.CornerMax()
        middle = gp_Pnt((lo.X() + hi.X()) / 2, (lo.Y() + hi.Y()) / 2, (lo.Z() + hi.Z()) / 2)
        self._view.Camera().SetCenter(middle)  # keeps the direction, moves the eye

    def _sped(self, pos: QPointF) -> QPointF:
        """The pointer as the turn sees it: its move from the press scaled by the turn
        speed preference (TR211)."""
        press = self._press
        if press is None or self.turn_speed == 1.0:
            return pos
        return press + (pos - press) * self.turn_speed

    def zoom_out(self) -> None:
        """Zoom out one step about the view centre (TR211)."""
        if self._view is not None:
            self._remember_once()
            centre = QPointF(self.width() / 2, self.height() / 2)
            self._zoom_at(centre, 1.0 / (1.0 + _WHEEL_ZOOM_STEP * 2))

    def zoom_in(self) -> None:
        """Zoom in one step about the view centre."""
        if self._view is not None:
            self._remember_once()
            centre = QPointF(self.width() / 2, self.height() / 2)
            self._zoom_at(centre, 1.0 + _WHEEL_ZOOM_STEP * 2)

    def start_zoom_area(self) -> None:
        """Zoom to the box of the next left drag (view toolbar, L5)."""
        self.zoom_area_armed = True
        self.setCursor(Qt.CursorShape.CrossCursor)

    def _finish_zoom_area(self, a: QPointF, b: QPointF) -> None:
        self.zoom_area_armed = False
        self._rest_cursor()
        (x1, y1), (x2, y2) = self._px(a), self._px(b)
        if self._view is not None and abs(x2 - x1) > 2 and abs(y2 - y1) > 2:
            self._remember()
            self._view.WindowFitAll(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
            self._view.Redraw()

    def previous_view(self) -> bool:
        """Go back to the camera before the last view change. False when there is none."""
        if self._view is None or not self._history:
            return False
        self._finish_turn()
        self._future.append(Graphic3d_Camera(self._view.Camera()))  # for Next View (TR380)
        self._view.Camera().Copy(self._history.pop())
        self._apply_projection()  # going back keeps the chosen projection (TR15)
        self._view.Redraw()
        return True

    def next_view(self) -> bool:
        """Go forward again after Previous View (a trackpad swipe, TR380). False when
        there is nothing to go forward to."""
        if self._view is None or not self._future:
            return False
        self._finish_turn()
        self._history.append(Graphic3d_Camera(self._view.Camera()))
        self._view.Camera().Copy(self._future.pop())
        self._apply_projection()
        self._view.Redraw()
        return True

    def redraw(self) -> None:
        """Redraw everything."""
        if self._view is not None:
            self._view.Redraw()

    def view_pixels(self) -> tuple[int, int]:
        """The view's size in device pixels (what Save Image uses by default)."""
        return round(self.width() * self._dpr), round(self.height() * self._dpr)

    def render_image(self, width: int, height: int, background: bool = True) -> QImage | None:
        """The view drawn off screen at ``width`` by ``height`` pixels (TR24), or None
        when the view cannot draw. Without the background it is transparent there and
        the axis triad is left out."""
        import tempfile
        from pathlib import Path

        from OCP.Image import Image_AlienPixMap
        from OCP.Quantity import Quantity_Color, Quantity_TOC_RGB

        from fdcad.ui.viewport.image_export import qimage_rgb, rgba_image, without_background

        view = self._view
        if view is None:
            return None

        def draw() -> QImage | None:
            pixmap = Image_AlienPixMap()
            # The picture has its own smoothed buffers, of its own size: it takes the
            # samples the rule gives for that size, and never more than the view (D2820).
            params = view.ChangeRenderingParams()
            samples = params.NbMsaaSamples
            params.NbMsaaSamples = min(
                samples, look.msaa_samples(1.0, width * height, _card_memory(view))
            )
            try:
                drawn = view.ToPixMap(pixmap, width, height)
            finally:
                params.NbMsaaSamples = samples
            if not drawn:
                return None
            with tempfile.TemporaryDirectory() as folder:
                path = str(Path(folder) / "view.png")
                if not pixmap.Save(path):
                    return None
                image = QImage(path)
            return None if image.isNull() else image

        if background:
            return draw()
        shots = []
        view.TriedronErase()
        try:
            for value in (0.0, 1.0):
                solid = Quantity_Color(value, value, value, Quantity_TOC_RGB)
                view.SetBgGradientColors(solid, solid, background_fill_none(), False)
                view.SetBackgroundColor(solid)
                shot = draw()
                if shot is None:
                    return None
                shots.append(qimage_rgb(shot))
        finally:
            view.SetBgGradientColors(*background_of(self._palette), False)
            look.show_triad(view, self._palette, self._dpr)
            view.Redraw()
        return rgba_image(without_background(shots[0], shots[1]))

    def _simple_while_turning(self, on: bool) -> None:
        """Turn smoothing off while a large part turns, back on after (TR214)."""
        if self._view is None or on == self._turning_simple or (on and not self._large_part):
            return
        self._turning_simple = on
        params = self._view.ChangeRenderingParams()
        params.NbMsaaSamples = 0 if on else self._samples
        params.IsAntialiasingEnabled = not on
        if not on:
            self._view.Redraw()

    def set_edge_options(self, smooth: str, hidden: str) -> None:
        """Smooth edges shown, dashed or removed; hidden edges dashed or solid (TR212)."""
        if (smooth, hidden) == (self.edge_look.smooth, self.edge_look.hidden):
            return
        self.edge_look.smooth, self.edge_look.hidden = smooth, hidden
        self._apply_style(update=True)

    def show_feature_edges(self, edges: list[TopoDS_Shape]) -> None:
        """Draw every edge of the feature selected in the tree (TR212); [] clears."""
        self.edge_look.show_feature_edges(edges)

    def set_style(self, style: str) -> None:
        """Shaded with edges, shaded, hidden lines removed, hidden lines visible or
        wireframe."""
        self.display_style = style
        self._apply_style(update=True)

    def set_zebra(self, texture: object | None) -> None:
        """Reflect zebra stripes in the faces, or stop with None (TR18). The stripes are
        the view's environment texture, so they follow the view as it turns."""
        self.zebra_texture = texture
        if self._view is not None:
            self._view.SetTextureEnv(texture)
            self._view.Redraw()

    def set_locked(self, solids: list[TopoDS_Shape]) -> None:
        """The locked bodies (TR269, D836): drawn greyed the next time the part is shown,
        and their faces, edges and vertices are never kept selected."""
        from OCP.TopExp import TopExp

        from fdcad.core.occ import ShapeMap

        self._locked = list(solids)
        found = ShapeMap()
        for solid in self._locked:
            for kind in (TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX):
                TopExp.MapShapes_s(solid, kind, found)
        self._locked_map = found if self._locked else None

    def _drop_locked(self) -> None:
        """Unselect anything on a locked body."""
        found = self._locked_map
        if found is None:
            return
        ctx = self._context
        owners = []
        ctx.InitSelected()
        while ctx.MoreSelected():
            if ctx.HasSelectedShape() and found.Contains(ctx.SelectedShape()):
                owners.append(ctx.SelectedOwner())
            ctx.NextSelected()
        for owner in owners:
            ctx.AddOrRemoveSelected(owner, False)

    def show_isolate_others(self, shape: TopoDS_Shape | None, mode: str) -> None:
        """Draw the bodies Isolate leaves out (TR99, D939): see through for
        "transparent", edges only for "wireframe", nothing for None or "hidden".
        They are never picked."""
        self.isolate_look = mode if shape is not None else "hidden"
        if self._view is None:
            return
        if self._isolate_others is not None:
            self._context.Remove(self._isolate_others, False)
            self._isolate_others = None
        if shape is not None and mode in ("transparent", "wireframe"):
            others = AIS_Shape(shape)
            if mode == "wireframe":
                others.SetColor(_hex(self._palette.sketch_reference))
                others.SetWidth(self._dpr)
                look.drop_face_curves(others.Attributes())
                self._context.Display(others, AIS_WireFrame, -1, False)  # -1: never picked
            else:
                others.SetColor(_hex(self._part_color or self._palette.face))
                look.style_part(others.Attributes(), self._palette, self._dpr)
                self._context.Display(others, AIS_Shaded, -1, False)
                self._context.SetTransparency(others, _ISOLATE_TRANSPARENCY, False)
            self._isolate_others = others
        self._context.UpdateCurrentViewer()

    def set_see_through(self, solids: list[TopoDS_Shape]) -> None:
        """The bodies to draw see through on their own (TR21). Used the next time the
        part is shown, which follows every change."""
        self._see_through = list(solids)

    def set_body_modes(self, modes: list[tuple[TopoDS_Shape, str, float]]) -> None:
        """Bodies with their own display mode ("shaded_edges", "shaded", "wireframe" or
        "" for the view's style) and transparency (TR216). Used the next time the part
        is shown, which follows every change."""
        self._body_modes = list(modes)

    def _apply_body_modes(self, presentation: Any) -> None:
        """Give each body its own mode and transparency; wireframe bodies are drawn as
        their edges only, on a separate drawing that is never picked."""
        from fdcad.core.features.solids import compound

        if self._body_wire is not None:
            self._context.Remove(self._body_wire, False)
            self._body_wire = None
        wires = []
        for solid, mode, transparency in self._body_modes:
            if mode in ("shaded", "shaded_edges"):
                drawer = presentation.CustomAspects(solid)
                drawer.SetFaceBoundaryAspect(presentation.Attributes().FaceBoundaryAspect())
                drawer.SetFaceBoundaryDraw(mode == "shaded_edges")
            elif mode == "wireframe":
                presentation.CustomAspects(solid).SetHidden(True)
                wires.append(solid)
            if transparency > 0 and mode != "wireframe":
                presentation.SetCustomTransparency(solid, transparency)
        if wires:
            item = AIS_Shape(compound(wires))
            item.SetColor(look.colour(look.bare_line_colour(self._palette)))  # D2761
            item.SetWidth(look.edge_width(self._dpr))
            look.drop_face_curves(item.Attributes())
            self._context.Display(item, AIS_WireFrame, -1, False)
            self._context.Deactivate(item)
            self._body_wire = item

    def set_section_see_through(self, solids: list[TopoDS_Shape], level: float) -> None:
        """Draw these bodies see through by ``level`` (0 to 1) while the section is on;
        [] puts them back (TR355 item 2)."""
        old = self._section_see[0]
        self._section_see = (list(solids), max(0.0, min(1.0, level)))
        part = self._part
        if part is None or not hasattr(part, "SetCustomTransparency"):
            return
        for solid in old:
            if not any(solid.IsSame(s) for s in self._see_through):
                part.SetCustomTransparency(solid, 0.0)
        for solid in self._section_see[0]:
            part.SetCustomTransparency(solid, self._section_see[1])
        self._context.Redisplay(part, False)
        if self._view is not None:
            self._context.UpdateCurrentViewer()

    def set_section_whole(self, solids: list[TopoDS_Shape]) -> None:
        """Keep these bodies whole while the section cuts the others; [] cuts every
        body (TR213 item 2, D2500). They are hidden in the part and drawn uncut."""
        old = self._section_whole
        self._section_whole = list(solids)
        part = self._part
        if part is None or self._view is None:
            return
        for solid in old:
            if not any(solid.IsSame(s) for s in self._section_whole):
                part.CustomAspects(solid).SetHidden(False)
        for solid in self._section_whole:
            part.CustomAspects(solid).SetHidden(True)
        self._context.Redisplay(part, False)
        self._draw_whole()
        self._context.UpdateCurrentViewer()

    def set_section_faces(self, faces: list[TopoDS_Shape]) -> None:
        """Draw the section's cut faces over its caps, nearly invisible but pickable,
        so Measure and the selection work on them; [] removes them (TR213, D2502)."""
        from fdcad.core.features.solids import compound

        if self._view is None:
            return
        if self._section_faces is not None:
            self._context.Remove(self._section_faces, False)
            self._section_faces = None
        if faces:
            item = AIS_Shape(compound(faces))
            item.SetColor(_hex(self._palette.face))
            item.SetTransparency(0.95)
            unclipped(item)
            self._context.Display(item, AIS_Shaded, -1, False)
            self._context.Deactivate(item)
            for kind in self.filters:
                self._context.Activate(item, AIS_Shape.SelectionMode_s(_KINDS[kind]))
            self._section_faces = item
        self._context.UpdateCurrentViewer()

    def _draw_whole(self) -> None:
        """Draw the bodies left whole by the section, never clipped and never picked."""
        from fdcad.core.features.solids import compound

        if self._section_whole_item is not None:
            self._context.Remove(self._section_whole_item, False)
            self._section_whole_item = None
        if not self._section_whole or self._view is None:
            return
        item = AIS_Shape(compound(self._section_whole))
        item.SetColor(_hex(self._part_color))
        look.style_part(item.Attributes(), self._palette, self._dpr)
        unclipped(item)
        self._context.Display(item, AIS_Shaded, -1, False)
        self._context.Deactivate(item)
        self._section_whole_item = item

    def toggle_transparency(self) -> bool:
        """Switch the part between opaque and see through. Returns the new state."""
        self.transparent = not self.transparent
        if self._part is not None:
            if self.transparent:
                self._context.SetTransparency(self._part, _TRANSPARENCY, True)
            else:
                self._context.UnsetTransparency(self._part, True)
        return self.transparent

    def set_perspective(self, on: bool) -> bool:
        """Switch between the parallel view and a perspective view (TR15). Returns the
        new state. Measure and dimensions use the model, so they show true values
        either way."""
        self.perspective = on
        if self._view is not None:
            self._apply_projection()
            self._view.Redraw()
        return self.perspective

    def _apply_projection(self) -> None:
        assert self._view is not None
        kind = (
            Graphic3d_Camera.Projection_e.Projection_Perspective
            if self.perspective
            else Graphic3d_Camera.Projection_e.Projection_Orthographic
        )
        camera = self._view.Camera()
        if camera.ProjectionType() != kind:
            camera.SetProjectionType(kind)

    def set_filters(self, kinds: set[str], on: bool = False) -> None:
        """Which kinds of item can be picked: face, edge and vertex. ``on`` says a
        selection filter chose them (T14.3.2), which also sets the filter cursor."""
        self.filters = set(kinds) & set(_KINDS)
        self.filters_on = on
        self._activate()
        if not self.zoom_area_armed:
            self._rest_cursor()

    def _rest_cursor(self) -> None:
        """The arrow, with a small filter mark while selection filters are on."""
        from fdcad.ui.input.filter_cursor import filter_cursor

        if self.filters_on:
            self.setCursor(filter_cursor())
        else:
            self.unsetCursor()

    def selected(self) -> list[TopoDS_Shape]:
        """Picked faces, edges and vertices, in the order they were picked. Items of a
        locked body are unselected first (TR269)."""
        self._drop_locked()
        out: list[TopoDS_Shape] = []
        ctx = self._context
        ctx.InitSelected()
        while ctx.MoreSelected():
            if ctx.HasSelectedShape():
                out.append(ctx.SelectedShape())
            ctx.NextSelected()
        return out

    def shape_under_cursor(self) -> TopoDS_Shape | None:
        """The face, edge or vertex the cursor is over (from the last hover), or None."""
        if self._view is None or not self._context.HasDetected():
            return None
        if not self._context.HasDetectedShape():
            return None
        return self._context.DetectedShape()

    def highlight(self, shapes: list[TopoDS_Shape]) -> None:
        """Show these faces, edges or vertices in red on top of the part (errors panel)."""
        from fdcad.core.features.solids import compound

        if self._highlight is not None:
            self._context.Remove(self._highlight, False)
            self._highlight = None
        if shapes:
            mark = AIS_Shape(compound(shapes))
            mark.SetColor(_hex(self._palette.state_error))
            mark.SetWidth(look.line_width(look.ERROR_WIDTH, self._dpr))
            mark.SetZLayer(Graphic3d_ZLayerId_TopOSD)
            self._context.Display(mark, AIS_Shaded, -1, False)
            self._highlight = mark
        if self._view is not None:
            self._context.UpdateCurrentViewer()

    def show_lost(self, shape: TopoDS_Shape | None) -> None:
        """Draw ``shape`` faintly in the warning colour: where a lost pick was (TR125
        item 2), so the user can see what to pick again. None removes it."""
        if self._ghost is not None:
            self._context.Remove(self._ghost, False)
            self._ghost = None
        if shape is not None:
            mark = AIS_Shape(shape)
            mark.SetColor(_hex(self._palette.state_warning))
            mark.SetWidth(look.line_width(look.LOST_PICK_WIDTH, self._dpr))
            mark.SetTransparency(0.6)
            mark.SetZLayer(Graphic3d_ZLayerId_TopOSD)
            self._context.Display(mark, AIS_Shaded, -1, False)
            self._ghost = mark
        if self._view is not None:
            self._context.UpdateCurrentViewer()

    def eye_direction(self) -> tuple[float, float, float] | None:
        """The direction from the scene toward the viewer, or None before the view exists."""
        if self._view is None:
            return None
        x, y, z = self._view.Proj()
        return (float(x), float(y), float(z))

    def set_section(self, clip: object | None) -> None:
        """Show a section view with this clipping chain, a list of chains (one per zone
        cut away, TR355), or none (P2.13, display only)."""
        old = getattr(self, "_section_clip", None)
        if self._view is None:
            self._section_clip = clip
            return
        for chain in old if isinstance(old, list) else [old]:
            if chain is not None:
                self._view.RemoveClipPlane(chain)
        for chain in clip if isinstance(clip, list) else [clip]:
            if chain is not None:
                self._view.AddClipPlane(chain)
        self._section_clip = clip
        self._view.Redraw()

    def show_preview_marks(self, shapes: list[TopoDS_Shape]) -> None:
        """Preview of reference geometry being made (P2.10), in the preview colour."""
        from fdcad.core.features.solids import compound

        old = getattr(self, "_preview_marks", None)
        if old is not None:
            self._context.Remove(old, False)
            self._preview_marks = None
        if shapes and self._view is not None:
            mark = AIS_Shape(compound(shapes))
            mark.SetColor(_hex(self._palette.selection))
            mark.SetWidth(look.line_width(look.PREVIEW_MARK_WIDTH, self._dpr))
            mark.SetTransparency(0.7)
            self._context.Display(mark, AIS_Shaded, -1, False)
            self._context.Deactivate(mark)
            self._preview_marks = mark
        if self._view is not None:
            self._context.UpdateCurrentViewer()

    def show_sketches(
        self, shapes: list[TopoDS_Shape], colors: list[str | None] | None = None
    ) -> None:
        """Draw finished sketches as lines (C1). They are not pickable. ``colors``
        gives a sketch's own colour (TR233), None for the usual one."""
        if self._view is None:
            self._pending_sketches = list(shapes)
            return
        for item in self._sketches:
            self._context.Remove(item, False)
        self._sketches = []
        own = list(colors or [])
        for i, shape in enumerate(shapes):
            item = AIS_Shape(shape)
            color = own[i] if i < len(own) else None
            item.SetColor(_hex(color or self._palette.sketch_under))
            item.SetWidth(look.line_width(look.SKETCH_WIDTH, self._dpr))
            self._context.Display(item, AIS_WireFrame, -1, False)
            self._context.Deactivate(item)
            self._sketches.append(item)
        if self._part is None and shapes:
            self.fit_all(remember=False)  # an empty part: frame the sketch
        self._context.UpdateCurrentViewer()

    def set_face_colors(self, colors: list[tuple[TopoDS_Shape, str]]) -> None:
        """Colour single faces of the shown part, for example from an imported STEP file."""
        self.face_colors = list(colors)
        if self._view is None or self._part is None or not colors:
            return
        from OCP.AIS import AIS_ColoredShape

        if isinstance(self._part, AIS_ColoredShape):
            for face, color in colors:
                self._part.SetCustomColor(face, _hex(color))
            self._context.Redisplay(self._part, False)
            self._context.UpdateCurrentViewer()

    def show_references(self, shapes: list[TopoDS_Shape]) -> None:
        """Draw reference curves and meshes (P3.6, P3.9). They are not part of the body
        and are not pickable."""
        self.references = list(shapes)
        if self._view is None:
            return
        for item in getattr(self, "_reference_items", []):
            self._context.Remove(item, False)
        self._reference_items: list[AIS_Shape] = []
        from OCP.TopAbs import TopAbs_FACE
        from OCP.TopExp import TopExp_Explorer

        for shape in shapes:
            item = AIS_Shape(shape)
            meshy = TopExp_Explorer(shape, TopAbs_FACE).More()
            item.SetColor(
                _hex(self._palette.mesh_reference if meshy else self._palette.sketch_under)
            )
            item.SetWidth(look.line_width(look.REFERENCE_WIDTH, self._dpr))
            self._context.Display(item, 1 if meshy else AIS_WireFrame, -1, False)
            self._context.Deactivate(item)
            self._reference_items.append(item)
        self._context.UpdateCurrentViewer()

    def show_ghost(self, shapes: list[TopoDS_Shape]) -> None:
        """Draw node graph output as a see-through accent ghost (Phase 7), replacing the
        last one. Display only: never picked. Shapes must be meshed off the UI thread."""
        self.ghosts = list(shapes)
        if self._view is None:
            return
        for item in getattr(self, "_ghost_items", []):
            self._context.Remove(item, False)
        self._ghost_items: list[AIS_Shape] = []
        accent = _hex(ACCENT[is_dark()])
        for shape in shapes:
            item = AIS_Shape(shape)
            item.SetColor(accent)
            item.SetTransparency(PREVIEW_TRANSPARENCY)
            self._context.Display(item, AIS_Shaded, -1, False)
            self._context.Deactivate(item)
            self._ghost_items.append(item)
        self._context.UpdateCurrentViewer()

    def show_combs(self, shapes: list[TopoDS_Shape]) -> None:
        """Draw curvature combs (P3.7), replacing the last ones. Display only."""
        self.combs = list(shapes)
        if self._view is None:
            return
        for item in getattr(self, "_comb_items", []):
            self._context.Remove(item, False)
        self._comb_items: list[AIS_Shape] = []
        for shape in shapes:
            item = AIS_Shape(shape)
            item.SetColor(_hex(self._palette.accent))
            item.SetWidth(look.line_width(look.COMB_WIDTH, self._dpr))
            self._context.Display(item, AIS_WireFrame, -1, False)
            self._context.Deactivate(item)
            self._comb_items.append(item)
        self._context.UpdateCurrentViewer()

    def show_planes(
        self, planes: dict[str, TopoDS_Shape], names: dict[str, str] | None = None
    ) -> None:
        """Show plane faces to pick from (W1, T13). Hover marks one; a click emits its id."""
        self.hide_planes()
        if self._view is None:
            return
        self._plane_hover = None
        rows = label_rows(dict(planes))  # parallel planes' labels one under another (D2630)
        for fid, face in planes.items():
            self._planes[fid] = (face, self._plane_item(face, pickable=True))
            name = (names or {}).get(fid, "")
            self._plane_labels[fid] = self._plane_label(face, name, rows.get(fid, 0))
        self._restyle_planes()
        if self._part is None:
            self.fit_all(remember=False)  # an empty part: frame the planes
        self._context.UpdateCurrentViewer()

    def show_reference_planes(
        self, planes: dict[str, TopoDS_Shape], names: dict[str, str] | None = None
    ) -> None:
        """Draw the planes the user chose to show, replacing the last set (D114, T13)."""
        for _face, item in self._shown_planes.values():
            self._context.Remove(item, False)
        for label in self._shown_labels.values():
            self._context.Remove(label, False)
        self._shown_planes = {}
        self._shown_labels = {}
        if self._view is None:
            return
        rows = label_rows(dict(planes))  # D2630
        for fid, face in planes.items():
            self._shown_planes[fid] = (face, self._plane_item(face, pickable=False))
            name = (names or {}).get(fid, "")
            self._shown_labels[fid] = self._plane_label(face, name, rows.get(fid, 0))
        self._restyle_planes()
        self._context.UpdateCurrentViewer()

    def set_selected_planes(self, ids: set[str]) -> None:
        """Planes selected in the tree: outline and label in the selection colour (T13.4)."""
        if ids == self._selected_planes:
            return
        self._selected_planes = set(ids)
        if self._view is not None:
            self._restyle_planes()
            self._context.UpdateCurrentViewer()

    def plane_styles(self) -> dict[str, PlaneStyle]:
        """The look of every plane on show, by plane id (shown and pickable)."""
        out: dict[str, PlaneStyle] = {}
        for fid in [*self._shown_planes, *self._planes]:
            state = plane_state(fid, self._plane_hover, self._selected_planes)
            out[fid] = plane_style(self._palette, state)
        return out

    # Ctrl and drag a plane's border (TR10) ------------------------------------------

    def _ray(self, pos: QPointF) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        assert self._view is not None
        x, y = self._px(pos)
        px, py, pz, vx, vy, vz = self._view.ConvertWithProj(x, y)
        return (px, py, pz), (vx, vy, vz)

    def _start_plane_drag(self, pos: QPointF) -> bool:
        """Grab the shown plane whose border is under the cursor. False when none is."""
        from OCP.BRep import BRep_Tool
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopoDS import TopoDS

        from fdcad.core.features.datum import line_plane_hit
        from fdcad.ui.viewport.plane_drag import BORDER_PX, border_at

        if self._view is None or not self._shown_planes:
            return False
        outlines: dict[str, list[tuple[float, float]]] = {}
        for fid, (face, _item) in self._shown_planes.items():
            corners = []
            explorer = TopExp_Explorer(face, TopAbs_VERTEX)
            while explorer.More():
                p = BRep_Tool.Pnt_s(TopoDS.Vertex(explorer.Current()))
                sx, sy = self._view.Convert(p.X(), p.Y(), p.Z())
                if (float(sx), float(sy)) not in corners:
                    corners.append((float(sx), float(sy)))
                explorer.Next()
            outlines[fid] = corners
        x, y = self._px(pos)
        grabbed = border_at((float(x), float(y)), outlines, BORDER_PX * self._dpr)
        if grabbed is None:
            return False
        face = self._shown_planes[grabbed][0]
        plane = BRepAdaptor_Surface(TopoDS.Face(face)).Plane()
        o, n = plane.Location(), plane.Axis().Direction()
        origin, normal = (o.X(), o.Y(), o.Z()), (n.X(), n.Y(), n.Z())
        point, direction = self._ray(pos)
        start = line_plane_hit(point, direction, origin, normal) or origin
        self._plane_drag = PlaneDrag(grabbed, start, normal)
        return True

    def _move_plane_drag(self, pos: QPointF) -> None:
        """Show where the new plane would be while the drag goes on."""
        from fdcad.ui.viewport.plane_drag import offset_along

        drag = self._plane_drag
        if drag is None or self._view is None:
            return
        point, direction = self._ray(pos)
        offset = offset_along(drag.start, drag.normal, point, direction)
        if offset is None:
            return
        drag.offset = offset
        if drag.ghost is not None:
            self._context.Remove(drag.ghost, False)
        face = self._shown_planes[drag.fid][0]
        move = gp_Trsf()
        n = drag.normal
        move.SetTranslation(gp_Vec(n[0] * offset, n[1] * offset, n[2] * offset))
        item = AIS_Shape(face.Moved(TopLoc_Location(move)))
        item.SetColor(_hex(self._palette.accent))
        item.SetTransparency(FILL_TRANSPARENCY)
        item.Attributes().SetFaceBoundaryDraw(True)
        self._context.Display(item, AIS_Shaded, -1, False)
        drag.ghost = item
        self._context.UpdateCurrentViewer()

    def _end_plane_drag(self) -> tuple[str, float | None] | None:
        """Remove the preview; the grabbed plane and how far it was dragged."""
        drag, self._plane_drag = self._plane_drag, None
        if drag is None:
            return None
        if drag.ghost is not None:
            self._context.Remove(drag.ghost, True)
        return drag.fid, drag.offset

    def _plane_item(self, face: TopoDS_Shape, pickable: bool) -> AIS_Shape:
        item = AIS_Shape(face)
        item.SetColor(_hex(self._palette.plane_fill))
        item.SetTransparency(FILL_TRANSPARENCY)
        item.Attributes().SetFaceBoundaryDraw(True)
        if pickable:
            # The look of the plane under the cursor comes from _restyle_planes, so the
            # kernel's own hover colour is replaced by the same accent look.
            hover = Prs3d_Drawer()
            hover.SetColor(_hex(self._palette.accent))
            hover.SetTransparency(FILL_TRANSPARENCY)
            hover.SetDisplayMode(1)
            item.SetDynamicHilightAttributes(hover)
        self._context.Display(item, AIS_Shaded, 0 if pickable else -1, False)  # -1: never picked
        return item

    def _plane_label(self, face: TopoDS_Shape, name: str, row: int = 0) -> AIS_TextLabel:
        label = AIS_TextLabel()
        label.SetText(TCollection_ExtendedString(name, True))
        label.SetPosition(gp_Pnt(*label_anchor(face, row)))
        label.SetHeight(LABEL_HEIGHT * self._dpr)
        label.SetZoomable(False)  # the same size in pixels at any zoom (IDEAS 65, D2630)
        label.SetHJustification(Graphic3d_HTA_LEFT)
        label.SetVJustification(Graphic3d_VTA_TOP)
        self._context.Display(label, False)
        self._context.Deactivate(label)  # never picked
        return label

    def _restyle_planes(self) -> None:
        """Colour every plane and label for its state (T13)."""
        styles = self.plane_styles()
        groups = ((self._shown_planes, self._shown_labels), (self._planes, self._plane_labels))
        for items, labels in groups:
            for fid, (_face, item) in items.items():
                style = styles[fid]
                item.SetColor(_hex(style.fill))
                item.SetTransparency(style.transparency)
                item.Attributes().SetFaceBoundaryAspect(
                    Prs3d_LineAspect(
                        _srgb_hex(style.outline), Aspect_TOL_SOLID, OUTLINE_WIDTH * self._dpr
                    )
                )
                self._context.Redisplay(item, False)
                label = labels.get(fid)
                if label is not None:
                    label.SetColor(_srgb_hex(style.label))
                    self._context.Redisplay(label, False)

    def show_axis_choices(self, edges: dict[str, TopoDS_Shape]) -> None:
        """Offer sketch lines as a revolve axis: hover highlights one, a click emits its id."""
        self.hide_axis_choices()
        if self._view is None:
            return
        for eid, edge in edges.items():
            item = AIS_Shape(edge)
            item.SetColor(_hex(self._palette.sketch_under))
            item.SetWidth(look.line_width(look.CHOICE_WIDTH, self._dpr))
            self._context.Display(item, AIS_WireFrame, 0, False)
            self._axes[eid] = (edge, item)
        self._context.UpdateCurrentViewer()

    def set_temporary_axes(self, on: bool) -> int:
        """Show or hide a thin axis through every round face (TR17). Returns how many
        are shown."""
        self.temporary_axes_shown = on
        if on:
            return self._show_temporary_axes()
        self._hide_temporary_axes()
        if self._view is not None:
            self._context.UpdateCurrentViewer()
        return 0

    def _hide_temporary_axes(self) -> None:
        for _edge, item in self._temp_axes.values():
            self._context.Remove(item, False)
        self._temp_axes, self._temp_faces = {}, {}

    def _show_temporary_axes(self) -> int:
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge

        from fdcad.core.temporary_axes import temporary_axes

        self._hide_temporary_axes()
        if self._view is None:
            return 0
        for i, axis in enumerate(temporary_axes(self._part_shape)):
            maker = BRepBuilderAPI_MakeEdge(gp_Pnt(*axis.start), gp_Pnt(*axis.end))
            if not maker.IsDone():
                continue
            edge = maker.Edge()
            item = AIS_Shape(edge)
            # The accent, not the edge colour: edges nearly vanish on the dark themes'
            # backgrounds (audit D11 item 5, D719).
            color = _srgb_hex(self._palette.accent)
            item.SetColor(color)
            item.Attributes().SetWireAspect(
                Prs3d_LineAspect(color, Aspect_TOL_DOTDASH, 1.0 * self._dpr)
            )
            item.SetZLayer(Graphic3d_ZLayerId_Topmost)  # seen through the part, like a datum
            self._context.Display(item, AIS_WireFrame, 0, False)
            key = f"axis{i}"
            self._temp_axes[key] = (edge, item)
            self._temp_faces[key] = axis.faces[0]
        self._context.UpdateCurrentViewer()
        return len(self._temp_axes)

    def temporary_axis_faces(self) -> list[TopoDS_Shape]:
        """The face each shown temporary axis stands for (tests and snapping)."""
        return list(self._temp_faces.values())

    def hide_axis_choices(self) -> None:
        """Stop offering sketch lines as an axis."""
        for _edge, item in self._axes.values():
            self._context.Remove(item, False)
        self._axes = {}
        if self._view is not None:
            self._context.UpdateCurrentViewer()

    def show_regions(self, faces: dict[str, TopoDS_Shape]) -> None:
        """Show a sketch's regions (name to face), replacing the last ones (T5.3.2)."""
        if self._view is None:
            return
        self._regions.show(faces)
        self._context.UpdateCurrentViewer()

    def set_region_state(self, picked: set[str], pickable: bool) -> None:
        """Fill picked regions stronger; with ``pickable`` hover and clicks pick regions."""
        if self._view is None:
            return
        self._regions.set_state(picked, pickable)
        self._context.UpdateCurrentViewer()

    def hide_regions(self) -> None:
        """Stop showing sketch regions."""
        if self._view is None or not self._regions.items:
            return
        self._regions.hide()
        self._context.UpdateCurrentViewer()

    @property
    def region_hover(self) -> str | None:
        """Name of the region under the cursor, or None."""
        return self._regions.hover

    def hide_planes(self) -> None:
        """Remove the planes shown for picking."""
        for _face, item in self._planes.values():
            self._context.Remove(item, False)
        for label in self._plane_labels.values():
            self._context.Remove(label, False)
        self._planes = {}
        self._plane_labels = {}
        self._plane_hover = None
        if self._view is not None:
            self._context.UpdateCurrentViewer()

    def show_labels(self, labels: list[tuple[str, str, tuple[float, float, float]]]) -> None:
        """Show dimension values on the model: (key, text, anchor) (W5.4)."""
        from OCP.gp import gp_Pnt
        from OCP.TCollection import TCollection_ExtendedString

        for _key, _anchor, item in self._labels:
            self._context.Remove(item, False)
        self._labels = []
        if self._view is None:
            return
        for key, text, anchor in labels:
            item = AIS_TextLabel()
            item.SetText(TCollection_ExtendedString(look.value_text(text), True))
            item.SetPosition(gp_Pnt(*anchor))
            look.style_value(item, self._palette, self._palette.sketch_under, self._dpr)
            self._context.Display(item, False)
            self._context.Deactivate(item)
            self._labels.append((key, anchor, item))
        self._context.UpdateCurrentViewer()

    def label_at(self, pos: QPointF, radius: float = 24.0) -> str | None:
        """Key of the dimension label nearest to ``pos`` (widget pixels), or None."""
        if self._view is None:
            return None
        best: tuple[float, str] | None = None
        for key, (x, y, z), _item in self._labels:
            px, py = self._view.Convert(float(x), float(y), float(z))
            d = abs(px / self._dpr - pos.x()) + abs(py / self._dpr - pos.y())
            if d <= radius and (best is None or d < best[0]):
                best = (d, key)
        return best[1] if best else None

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Double click a dimension label to change its value; double middle click
        zooms to fit (TR211)."""
        if event.button() == Qt.MouseButton.MiddleButton:
            self._drag, self._press = None, None
            self.fit_all()
            event.accept()
            return
        key = self.label_at(event.position())
        if key is not None:
            self.label_double_clicked.emit(key)
        event.accept()

    def _picked_in(self, shown: dict[str, tuple[TopoDS_Shape, AIS_Shape]]) -> str | None:
        if not shown or not self._context.HasDetectedShape():
            return None
        shape = self._context.DetectedShape()
        for key, (item_shape, _item) in shown.items():
            if item_shape.IsSame(shape):
                return key
        return None

    def clear_selection(self) -> None:
        """Unselect everything."""
        self._context.ClearSelected(True)
        self.selection_changed.emit([])

    # Right click and Select Other (T9, T14.3.1) -------------------------------------

    # Turning about a picked point (TR209, D832) ------------------------------------

    turn_centre: Vec3 | None = None
    #: Keep the model's Z axis upright while turning (a preference).
    lock_up: bool = False
    #: Turn like a ball under the pointer (TR415, D1001; a preference).
    arcball: bool = False
    _orbit_start: Any = None
    #: Radians turned per pixel dragged.
    ORBIT_RATE = math.pi / 400

    def set_turn_centre(self, point: Vec3 | None) -> None:
        """Turn about ``point`` with the middle button from now on; None goes back to
        the usual turning."""
        self.turn_centre = point
        self.turn_centre_changed.emit(point)

    def _orbit(self, moved: QPointF) -> None:
        """Turn the camera from where the drag started, about the turning centre (or the
        view's centre), keeping Z up when ``lock_up``."""
        from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec

        eye0, centre0, up0 = self._orbit_start
        pivot = gp_Pnt(*self.turn_centre) if self.turn_centre is not None else centre0
        sight = gp_Vec(eye0, centre0)
        if sight.Magnitude() < 1e-12:
            return
        right = sight.Crossed(gp_Vec(up0.XYZ()))
        if right.Magnitude() < 1e-12:
            return
        across = gp_Dir(0, 0, 1) if self.lock_up else up0
        side = gp_Trsf()
        side.SetRotation(gp_Ax1(pivot, across), -moved.x() * self.ORBIT_RATE)
        tilt = gp_Trsf()
        tilt.SetRotation(gp_Ax1(pivot, gp_Dir(right)), -moved.y() * self.ORBIT_RATE)
        turn = side.Multiplied(tilt)
        if self._view is None:
            return
        cam = self._view.Camera()
        cam.SetEyeAndCenter(eye0.Transformed(turn), centre0.Transformed(turn))
        cam.SetUp(up0.Transformed(turn))
        self._view.Redraw()

    def _roll_ball(self, start: QPointF, now: QPointF) -> None:
        """Arcball turn from the drag's start to ``now``, about the turning centre (or
        the view's centre) (TR415, D1001)."""
        from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec

        from fdcad.ui.viewport.arcball import arcball_turn

        eye0, centre0, up0 = self._orbit_start
        pivot = gp_Pnt(*self.turn_centre) if self.turn_centre is not None else centre0
        sight = gp_Vec(eye0, centre0)
        if sight.Magnitude() < 1e-12:
            return
        right = sight.Crossed(gp_Vec(up0.XYZ()))
        if right.Magnitude() < 1e-12:
            return
        right.Normalize()
        up = right.Crossed(sight).Normalized()
        back = sight.Reversed().Normalized()
        axis, angle = arcball_turn(
            (start.x(), start.y()), (now.x(), now.y()), self.width(), self.height()
        )
        if angle == 0.0:
            return
        world = (
            right.Multiplied(axis[0]).Added(up.Multiplied(axis[1])).Added(back.Multiplied(axis[2]))
        )
        turn = gp_Trsf()
        # The model rolls by the angle, so the camera goes the other way.
        turn.SetRotation(gp_Ax1(pivot, gp_Dir(world)), -angle)
        if self._view is None:
            return
        cam = self._view.Camera()
        cam.SetEyeAndCenter(eye0.Transformed(turn), centre0.Transformed(turn))
        cam.SetUp(up0.Transformed(turn))
        self._view.Redraw()

    def detected_at(self, pos: QPointF) -> list[TopoDS_Shape]:
        """Every face, edge and vertex under ``pos``, nearest first (Select Other)."""
        if self._view is None:
            return []
        x, y = self._px(pos)
        self._context.MoveTo(x, y, self._view, False)
        # Only faces, edges and vertices of the part, not previews or labels (D2781).
        return self._detected_on_part()

    def part_point_at(self, pos: QPointF) -> Vec3 | None:
        """The point of the shown part under ``pos``, or None off the part (T5.4)."""
        if self._view is None or self._part is None:
            return None
        x, y = self._px(pos)
        self._context.MoveTo(x, y, self._view, False)
        if not self._context.HasDetected():
            return None
        owner = self._context.DetectedOwner()
        if owner is None or not owner.IsSameSelectable(self._part):
            return None
        return self._point_under_cursor()

    def plane_under(self, pos: QPointF) -> str | None:
        """Id of a shown plane under ``pos`` (planes are never picked by a left click)."""
        if self._view is None or not self._shown_planes:
            return None
        for _face, item in self._shown_planes.values():
            self._context.Activate(item, 0)
        x, y = self._px(pos)
        self._context.MoveTo(x, y, self._view, False)
        found = self._picked_in(self._shown_planes)
        for _face, item in self._shown_planes.values():
            self._context.Deactivate(item)
        return found

    def select_shapes(self, shapes: list[TopoDS_Shape], add: bool = False) -> None:
        """Select these faces, edges or vertices of the part (Select Other, Select Midpoint)."""
        if self._part is None:
            return
        from OCP.StdSelect import StdSelect_BRepOwner

        if not add:
            self._context.ClearSelected(False)
        for shape in shapes:
            # From decomposition: highlight just this face or edge, not the whole part.
            owner = StdSelect_BRepOwner(shape, self._part, 0, True)
            self._context.AddOrRemoveSelected(owner, False)
        if self._view is not None:
            self._context.UpdateCurrentViewer()
        self.selection_changed.emit(self.selected())

    def preview_shapes(self, shapes: list[TopoDS_Shape]) -> None:
        """Mark shapes in the accent colour while a Select Other row is hovered."""
        from fdcad.core.features.solids import compound

        if self._marked is not None:
            self._context.Remove(self._marked, False)
            self._marked = None
        if shapes:
            mark = AIS_Shape(compound(shapes))
            mark.SetColor(_hex(self._palette.accent))
            mark.SetWidth(look.line_width(look.CHOICE_WIDTH, self._dpr))
            mark.SetZLayer(Graphic3d_ZLayerId_TopOSD)
            self._context.Display(mark, AIS_Shaded, -1, False)
            self._marked = mark
        if self._view is not None:
            self._context.UpdateCurrentViewer()

    def hide_face_for_now(self, face: TopoDS_Shape) -> None:
        """Hide one face until :meth:`show_hidden_faces` (Select Other, T14.3.1)."""
        from OCP.AIS import AIS_ColoredShape

        self._hidden_faces.append(face)
        if isinstance(self._part, AIS_ColoredShape):
            self._part.CustomAspects(face).SetHidden(True)
            self._context.Redisplay(self._part, False)
            self._context.UpdateCurrentViewer()

    def show_hidden_faces(self) -> None:
        """Show again the faces hidden while Select Other was open."""
        from OCP.AIS import AIS_ColoredShape

        if not self._hidden_faces:
            return
        if isinstance(self._part, AIS_ColoredShape):
            for face in self._hidden_faces:
                self._part.CustomAspects(face).SetHidden(False)
            self._context.Redisplay(self._part, False)
            self._context.UpdateCurrentViewer()
        self._hidden_faces = []

    def dump(self, path: str) -> bool:
        """Save the current image to a file. Used by manual and debug checks."""
        if self._view is None:
            return False
        self._view.Redraw()
        return bool(self._view.Dump(path))

    def release(self) -> list[str]:
        """Free the kernel view while its native window still exists (D2780).

        Call on the UI thread when the view is going away (its part's tab closes),
        before Qt destroys the window. Left to the garbage collector, the kernel freed
        the view's drawing context after the window was gone: it could not make that
        context current, and the clean up then ran on whichever view's context was
        current, so a live view stopped drawing. The order is fixed: the shown items,
        then the kernel view (which frees its context with the window still there),
        then the window handle. Returns the steps taken, for the tests. The view stays
        blank afterwards and never starts again.
        """
        steps: list[str] = []
        if self._released:
            return steps
        self._released = True
        self._pending_part = None
        self._pending_sketches = None
        if self._view is not None:
            self.rim.forget()
            self._context.RemoveAll(False)
            self._part = None
            steps.append("shown items")
            self._view.Remove()
            self._view = None
            steps.append("kernel view")
        if self._window is not None:
            self._window = None
            steps.append("window handle")
        return steps

    @property
    def released(self) -> bool:
        """True once ``release`` has freed the kernel view."""
        return self._released

    @property
    def device_pixel_ratio(self) -> float:
        """Device pixel ratio the OCCT window was last sized with."""
        return self._dpr

    # Navigation and selection -----------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Rotate, pan, zoom or roll (middle), select or box (left), gesture (right)."""
        self._finish_turn()  # the user takes over: end a view turn at once
        self.setFocus()
        if self._view is None:
            return super().mousePressEvent(event)
        button = event.button()
        mods = event.modifiers()
        self._last = event.position()
        if button == Qt.MouseButton.MiddleButton:
            self.nav_count += 1
            self._drag = keynav.middle_drag(self.mouse_preset, mods)  # TR312
            self._press = event.position()
            self._remember()
            if self._drag == "rotate":
                self._simple_while_turning(True)
            if self._drag == "rotate" and (
                self.turn_centre is not None or self.lock_up or self.arcball
            ):
                cam = self._view.Camera()
                self._orbit_start = (cam.Eye(), cam.Center(), cam.Up())
            elif self._drag == "rotate":
                x, y = self._px(event.position())
                self._view.StartRotation(x, y)
            elif self._drag == "roll":
                self._press_twist = self._view.Twist()
        elif button == Qt.MouseButton.LeftButton and self._click_handle:
            self.finish_click_handle()  # TR293 (D2209): the second click sets the value
        elif button == Qt.MouseButton.RightButton:
            self._drag = "gesture"
            self._press = event.position()
            self.gesture_tracker.press(event.position())
        elif button == Qt.MouseButton.LeftButton and (axis := self._triad_axis(event.position())):
            self._drag = "triad"
            self._triad_pick = axis
        elif button == Qt.MouseButton.LeftButton and (value := self._value_at(event.position())):
            self.value_clicked.emit(value, event.position().toPoint())
        elif button == Qt.MouseButton.LeftButton and (handle := self._handle_at(event.position())):
            self._drag = "handle"
            self._start_handle_drag(handle, event.position())
        elif (
            button == Qt.MouseButton.LeftButton
            and mods & Qt.KeyboardModifier.ControlModifier
            and self._start_plane_drag(event.position())
        ):
            self._drag = "plane_offset"
            self._press = event.position()
        elif button == Qt.MouseButton.LeftButton:
            if self.gesture_with_ctrl and mods & Qt.KeyboardModifier.MetaModifier:
                self._drag = "gesture"
                self.gesture_tracker.press(event.position())
            else:
                self._drag = "pick"
            self._press = event.position()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Continue the current drag, or update the hover highlight."""
        if self._view is None:
            return super().mouseMoveEvent(event)
        pos = event.position()
        if self._drag == "handle" or (self._drag is None and self._click_handle):
            alt = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
            self._drag_handle(pos, snap=alt)
        elif self._drag == "rotate" and self._orbit_start is not None and self._press is not None:
            if self.arcball and not self.lock_up:
                self._roll_ball(self._press, self._sped(pos))
            else:
                self._orbit(self._sped(pos) - self._press)
        elif self._drag == "rotate":
            x, y = self._px(self._sped(pos))
            self._view.Rotation(x, y)
        elif self._drag == "pan":
            self._pan_by(pos - self._last)
        elif self._drag == "zoom" and self._press is not None:
            self._zoom_at(self._press, keynav.zoom_factor(pos.y() - self._press.y()))
        elif self._drag == "roll" and self._press is not None:
            deg = keynav.roll_degrees(pos.x() - self._press.x())
            self._view.SetTwist(self._press_twist + math.radians(deg))
        elif self._drag == "gesture":
            self.gesture_tracker.move(pos)
        elif self._drag == "plane_offset":
            self._move_plane_drag(pos)
        elif self._drag == "lasso":
            self._loop.append(pos)
            self._show_loop()
        elif self._drag == "paint":
            self.paint_at(pos)
        elif self._drag in ("pick", "box") and self._press is not None:
            if (pos - self._press).manhattanLength() > _DRAG_PX:
                if self.paint and not self.zoom_area_armed:  # TR329 (D2208)
                    self._drag = "paint"
                    self._start_paint()
                    self.paint_at(self._press)
                    self.paint_at(pos)
                elif self.lasso and not self.zoom_area_armed:
                    self._drag = "lasso"
                    self._loop = [self._press, pos]
                    self._show_loop()
                else:
                    self._drag = "box"
                    self._show_band(self._press, pos)
        elif self._drag is None:
            if self._preview_data is not None and self._handle_at(pos) is not None:
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            elif not self.zoom_area_armed:
                self._rest_cursor()
            self._hover_pos = pos
            if not self._hover_timer.isActive():
                self._hover_timer.start()
        self._last = pos
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Finish a drag: select, box select or run a gesture."""
        if self._view is None:
            return super().mouseReleaseEvent(event)
        drag, press = self._drag, self._press
        self._drag, self._press = None, None
        self._orbit_start = None
        self._simple_while_turning(False)
        if (
            (drag == "rotate" or (drag == "pan" and not event.modifiers()))  # TR312
            and press is not None
            and event.button() == Qt.MouseButton.MiddleButton
            and (event.position() - press).manhattanLength() <= _DRAG_PX
        ):
            # A middle click without a drag: turn about the point under it from now on,
            # or the usual way when clicked off the part (TR209, D832).
            self.set_turn_centre(self.part_point_at(event.position()))
            event.accept()
            return
        mods = event.modifiers()
        add = bool(mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier))
        pos = event.position()
        if drag == "triad":
            self.click_triad(self._triad_pick, bool(mods & Qt.KeyboardModifier.ShiftModifier))
            event.accept()
            return
        if drag == "plane_offset":
            moved = press is not None and (pos - press).manhattanLength() > _DRAG_PX
            grabbed = self._end_plane_drag()
            if moved:
                if grabbed is not None and grabbed[1] is not None:
                    self.plane_offset_dragged.emit(grabbed[0], grabbed[1])
                event.accept()
                return
            drag = "pick"  # a Ctrl click with no drag picks as usual
        if (
            drag == "handle"
            and self._grab is not None
            and self._handle_press is not None
            and (pos - self._handle_press).manhattanLength() <= _DRAG_PX
        ):
            # TR293 (D2209): a click without a drag: the handle follows the cursor until
            # the next click (arrows nudge it, Escape puts it back).
            self._click_handle = True
            event.accept()
            return
        if drag == "handle":
            if self._grab is not None:
                vertex, self._snap_vertex = self._snap_vertex, None
                if vertex is not None:  # TR395 (D2207): follow the snapped vertex
                    self.handle_snapped.emit(self._grab[0], vertex)
                self.handle_released.emit(self._grab[0])
            self._grab, self._drag_state = None, None
            self._hide_snap_mark(update=False)
            if self._ruler is not None:
                self._context.Remove(self._ruler, True)
                self._ruler = None
        elif drag == "pick":
            x, y = self._px(pos)
            self._context.MoveTo(x, y, self._view, False)
            plane = self._picked_in(self._planes)
            if plane is not None:
                self.plane_picked.emit(plane)
                event.accept()
                return
            axis = self._picked_in(self._axes)
            if axis is not None:
                self.axis_picked.emit(axis)
                event.accept()
                return
            temp = self._picked_in(self._temp_axes)
            if temp is not None:
                # A temporary axis picks its round face, which axis picks accept (TR17).
                self.select_shapes([self._temp_faces[temp]], add=add)
                self._view.Redraw()
                self.selection_changed.emit(self.selected())
                event.accept()
                return
            region = self._regions.under_cursor()
            if region is not None:
                self.region_clicked.emit(region)
                event.accept()
                return
            behind = self._edge_through()  # TR64: Select Through Faces
            if behind is None:
                behind = self._through_pick(mods)  # TR224: pick through see through bodies
            if behind is not None:
                self.select_shapes([behind], add=add)
                self._view.Redraw()
                self.selection_changed.emit(self.selected())
                event.accept()
                return
            if mods & Qt.KeyboardModifier.AltModifier and self._context.HasNextDetected():
                self._context.HilightNextDetected(self._view, False)
            scheme = AIS_SelectionScheme_XOR if add else AIS_SelectionScheme_Replace
            self._context.SelectDetected(scheme)
            self._view.Redraw()
            self.selection_changed.emit(self.selected())
            plain = Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier
            if not add and not mods & plain:
                self.left_clicked.emit(pos)
        elif drag == "paint":  # TR329 (D2208)
            self.paint_at(pos)
            self._activate()
            self.selection_changed.emit(self.selected())
        elif drag == "lasso":
            self._loop.append(pos)
            self._hide_band()
            self._lasso_select(mods)
        elif drag == "box" and press is not None and self.zoom_area_armed:
            self._hide_band()
            self._finish_zoom_area(press, pos)
        elif drag == "box" and press is not None and (boxed := self.markers_in(press, pos)):
            self._hide_band()  # a box over pattern markers skips those copies (TR270, D2401)
            self.markers_boxed.emit(boxed, bool(mods & Qt.KeyboardModifier.ControlModifier))
        elif drag == "box" and press is not None:
            self._hide_band()
            self._box_select(press, pos, mods)
        elif drag == "gesture" and press is not None:
            self.gesture_tracker.release()
            d = pos - press
            if d.manhattanLength() > _DRAG_PX:
                self.gesture.emit(d.x(), d.y())
            elif event.button() == Qt.MouseButton.RightButton:
                self.context_menu.emit(pos)
        event.accept()

    def _box_select(self, press: QPointF, pos: QPointF, mods: Qt.KeyboardModifier) -> None:
        """Box selection (T14.3.3): left to right takes what lies inside, right to left
        also what the box crosses. Edges by default, or the filtered types. Shift adds,
        Ctrl toggles, else the box replaces the selection."""
        from OCP.AIS import AIS_SelectionScheme_Add

        from fdcad.ui.input import selection_rules as rules

        assert self._view is not None
        how = rules.scheme(
            bool(mods & Qt.KeyboardModifier.ShiftModifier),
            bool(mods & Qt.KeyboardModifier.ControlModifier),
        )
        schemes = {
            "replace": AIS_SelectionScheme_Replace,
            "add": AIS_SelectionScheme_Add,
            "toggle": AIS_SelectionScheme_XOR,
        }
        crossing = rules.is_crossing((press.x(), press.y()), (pos.x(), pos.y()))
        kinds = self.box_kinds()
        if self._part is not None:
            self._context.Deactivate(self._part)
            for kind in kinds:
                self._context.Activate(self._part, AIS_Shape.SelectionMode_s(_KINDS[kind]))
        selector = self._context.MainSelector()
        selector.AllowOverlapDetection(crossing)
        (x1, y1), (x2, y2) = self._px(press), self._px(pos)
        try:
            self._context.SelectRectangle(
                Vec2_int(min(x1, x2), min(y1, y2)),
                Vec2_int(max(x1, x2), max(y1, y2)),
                self._view,
                schemes[how],
            )
        finally:
            selector.AllowOverlapDetection(False)
            self._activate()
        self._view.Redraw()
        self.selection_changed.emit(self.selected())

    def set_paint(self, on: bool) -> None:
        """Left drags pick every face they pass over (TR329, D2208) instead of a box."""
        self.paint = on

    def _start_paint(self) -> None:
        """Only faces of the part pick while painting."""
        if self._part is not None:
            self._context.Deactivate(self._part)
            self._context.Activate(self._part, AIS_Shape.SelectionMode_s(_KINDS["face"]))

    def paint_at(self, pos: QPointF) -> bool:
        """Add the part face under ``pos`` to the selection (paint pick). True when one
        was added."""
        from OCP.AIS import AIS_SelectionScheme_Add

        if self._view is None or self._part is None:
            return False
        x, y = self._px(pos)
        self._context.MoveTo(x, y, self._view, False)
        if not self._context.HasDetected():
            return False
        self._context.SelectDetected(AIS_SelectionScheme_Add)
        self._view.Redraw()
        return True

    def set_lasso(self, on: bool) -> None:
        """Left drags draw a free loop (TR19) instead of a box."""
        self.lasso = on

    def _show_loop(self) -> None:
        """Draw the lasso so far as a closed outline."""
        assert self._view is not None
        self._show_band(self._loop[0], self._loop[0])  # makes the band and shows it
        assert self._band is not None
        self._band.ClearPoints()
        h = round(self.height() * self._dpr)
        for p in self._loop:
            x, y = self._px(p)
            self._band.AddPoint(Vec2_int(x, h - y))
        self._band.SetPolygonClosed(True)
        self._context.Redisplay(self._band, False)
        self._view.Redraw()

    def _lasso_select(self, mods: Qt.KeyboardModifier) -> None:
        """Select with the loop: clockwise takes what lies inside, counter clockwise
        also what it crosses (TR19). Shift adds, Ctrl toggles, as for the box."""
        from OCP.AIS import AIS_SelectionScheme_Add
        from OCP.collections import Array1_gp_Pnt2d
        from OCP.gp import gp_Pnt2d

        from fdcad.ui.input import selection_rules as rules

        assert self._view is not None
        points = rules.thin_loop([self._px(p) for p in self._loop], step=2.0)
        self._loop = []
        if len(points) < 3:
            return
        how = rules.scheme(
            bool(mods & Qt.KeyboardModifier.ShiftModifier),
            bool(mods & Qt.KeyboardModifier.ControlModifier),
        )
        schemes = {
            "replace": AIS_SelectionScheme_Replace,
            "add": AIS_SelectionScheme_Add,
            "toggle": AIS_SelectionScheme_XOR,
        }
        polygon = Array1_gp_Pnt2d(1, len(points))
        for i, (x, y) in enumerate(points, start=1):
            polygon.SetValue(i, gp_Pnt2d(float(x), float(y)))
        kinds = self.box_kinds()
        if self._part is not None:
            self._context.Deactivate(self._part)
            for kind in kinds:
                self._context.Activate(self._part, AIS_Shape.SelectionMode_s(_KINDS[kind]))
        selector = self._context.MainSelector()
        selector.AllowOverlapDetection(rules.lasso_is_crossing(points))
        try:
            self._context.SelectPolygon(polygon, self._view, schemes[how])
        finally:
            selector.AllowOverlapDetection(False)
            self._activate()
        self._view.Redraw()
        self.selection_changed.emit(self.selected())

    def box_kinds(self) -> set[str]:
        """What a box picks: edges by default, or every type the filters let through."""
        if self.filters_on:
            return set(self.filters)
        return {"edge"} & set(self.filters) or set(self.filters)

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802
        """Drop the hover highlight and the cursor position when the cursor leaves."""
        if self._view is not None:
            self._context.ClearDetected(True)
            self.sync_hover_rim()
        self.cursor_point.emit(None)
        super().leaveEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        """Mouse wheel zooms. Trackpad scrolling rotates, or pans with Shift."""
        self._finish_turn()  # the user takes over: end a view turn at once
        if self._view is None:
            return
        self._remember_once()
        self.nav_count += 1
        pixel = event.pixelDelta()
        is_trackpad = not pixel.isNull() and event.phase() != Qt.ScrollPhase.NoScrollPhase
        if is_trackpad:
            delta = QPointF(pixel) * _TRACKPAD_ROTATE_SCALE
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._pan_by(delta)
            else:
                self._rotate_by(delta)
        else:
            steps = event.angleDelta().y() / 120.0
            if self.wheel_reverse:
                steps = -steps
            if steps:
                at = (
                    event.position()
                    if self.zoom_about_cursor
                    else QPointF(self.width() / 2, self.height() / 2)
                )
                self._zoom_at(at, (1.0 + _WHEEL_ZOOM_STEP) ** steps)
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Arrow keys rotate, pan or roll the view. Other keys pass through."""
        if self._click_handle and self.handle_key(event.key(), event.modifiers()):
            event.accept()
            return
        if self._view is not None:
            action = keynav.key_action(event.key(), event.modifiers(), self.arrow_step)
            if action is not None:
                self._remember()
                self.nav_count += 1
                self._apply_action(action)
                event.accept()
                return
        if event.key() == Qt.Key.Key_Escape:
            self.escape_pressed.emit()
            event.accept()
            return
        if starts_typing(event.text(), event.modifiers()) and self._typing_wanted():
            self.value_typed.emit(event.text())  # open the value box with it (T15.4)
            event.accept()
            return
        super().keyPressEvent(event)

    def handle_key(self, key: int, mods: Qt.KeyboardModifier) -> bool:
        """Arrows nudge a clicked handle by its ruler step (a tenth with Shift), Enter
        sets it and Escape puts it back (TR293, D2209). True when the key was used."""
        if self._grab is None or self._drag_state is None:
            return False
        param = self._grab[0]
        handle = self._drag_state.handle
        if key in (Qt.Key.Key_Escape,):
            self._handle_value = self._handle_start_value
            self.handle_dragged.emit(param, self._handle_start_value)
            self.finish_click_handle()
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.finish_click_handle()
            return True
        sign = {
            Qt.Key.Key_Up: 1,
            Qt.Key.Key_Right: 1,
            Qt.Key.Key_Down: -1,
            Qt.Key.Key_Left: -1,
        }.get(Qt.Key(key))
        if sign is None:
            return False
        step = handle.step if handle.step > 0 else (math.radians(1) if handle.is_angle else 1.0)
        if mods & Qt.KeyboardModifier.ShiftModifier:
            step /= 10
        smallest = MIN_ANGLE if handle.is_angle else MIN_LENGTH
        self._handle_value = max(self._handle_value + sign * step, smallest)
        self.handle_dragged.emit(param, self._handle_value)
        return True

    def finish_click_handle(self) -> None:
        """End a click then click handle: the value stays where it is now (TR293)."""
        self._click_handle = False
        if self._grab is not None:
            vertex, self._snap_vertex = self._snap_vertex, None
            if vertex is not None:
                self.handle_snapped.emit(self._grab[0], vertex)
            self.handle_released.emit(self._grab[0])
        self._grab, self._drag_state, self._handle_press = None, None, None
        self._hide_snap_mark(update=False)
        if self._ruler is not None:
            self._context.Remove(self._ruler, True)
            self._ruler = None

    def _typing_wanted(self) -> bool:
        """True while something listens for typed values (a feature panel is open)."""
        from PySide6.QtCore import QMetaMethod

        return self.isSignalConnected(QMetaMethod.fromSignal(self.value_typed))

    # Internals ---------------------------------------------------------------

    def _hover(self) -> None:
        if self._view is not None and self._hover_pos is not None and self._drag is None:
            x, y = self._px(self._hover_pos)
            self._context.MoveTo(x, y, self._view, True)
            self.sync_hover_rim()
            hover = self._picked_in(self._planes)
            if hover != self._plane_hover:
                self._plane_hover = hover
                self._restyle_planes()
                self._context.UpdateCurrentViewer()
            if self._regions.set_hover(self._regions.under_cursor()):
                self._context.UpdateCurrentViewer()
            self.cursor_point.emit(self._point_under_cursor())

    def sync_hover_rim(self) -> None:
        """Give the face or edge under the cursor its rim, after a hover (D2821)."""
        if self.rim.sync_hover() and self._view is not None:
            self._context.UpdateCurrentViewer()

    def _point_under_cursor(self) -> Vec3 | None:
        """The model point under the cursor after a hover, or None off the part."""
        if self._part is None or not self._context.HasDetected():
            return None
        selector = self._context.MainSelector()
        if selector.NbPicked() < 1:
            return None
        p = selector.PickedPoint(1)
        return (p.X(), p.Y(), p.Z())

    def _activate(self) -> None:
        faces = getattr(self, "_section_faces", None)
        if faces is not None:  # the section's cut faces follow the filters (TR213)
            self._context.Deactivate(faces)
            for kind in self.filters:
                self._context.Activate(faces, AIS_Shape.SelectionMode_s(_KINDS[kind]))
        if self._part is None:
            return
        self._context.Deactivate(self._part)
        for kind in self.filters:
            self._context.Activate(self._part, AIS_Shape.SelectionMode_s(_KINDS[kind]))

    def _apply_style(self, update: bool) -> None:
        computed = self.display_style in HIDDEN_LINE_STYLES
        if self._part is not None:
            drawer = self._part.Attributes()
            # The hidden line pass copies the flag from the default drawer each time it
            # runs, so it is set there; the part's own drawer holds the dashed look.
            visible = self.display_style == "hidden_lines_visible"
            solid = self.edge_look.hidden == "solid"
            look.style_hidden_lines(drawer, self._palette, self._dpr, solid=solid)
            self.edge_look.style(drawer)
            for d in (drawer, self._context.DefaultDrawer()):
                if visible:
                    d.EnableDrawHiddenLine()
                else:
                    d.DisableDrawHiddenLine()
            drawer.SetFaceBoundaryDraw(self.display_style == "shaded_edges")
            shaded = self.display_style in ("shaded_edges", "shaded")
            self._context.SetDisplayMode(self._part, AIS_Shaded if shaded else AIS_WireFrame, False)
            if update:
                self._context.Redisplay(self._part, False)
                self.edge_look.refresh()
        if self._view is not None:
            if computed:
                # Off then on recomputes the hidden lines, also when only the flag changed.
                self._view.SetComputedMode(False)
            self._view.SetComputedMode(computed)
        if update and self._part is not None:
            self._context.UpdateCurrentViewer()

    def _remember(self) -> None:
        self._future = []  # a new view change: nothing to go forward to
        if self._view is not None:
            self._history.append(Graphic3d_Camera(self._view.Camera()))
            del self._history[:-_MAX_HISTORY]
            self._remembered_at = self._event_counter()

    def _remember_once(self) -> None:
        """Remember the camera at the start of a burst of wheel or pinch steps."""
        if getattr(self, "_remembered_at", -10) < self._event_counter() - 1:
            self._remember()
        self._remembered_at = self._event_counter()

    def _event_counter(self) -> int:
        # Half second buckets: wheel steps closer than that count as one change.
        from time import monotonic

        return int(monotonic() * 2)

    def _show_band(self, a: QPointF, b: QPointF) -> None:
        assert self._view is not None
        if self._band is None:
            mark = look.colour(self._palette.selection)
            band = AIS_RubberBand(mark, Aspect_TOL_DASH, mark, 0.88, 1.0, True)
            band.SetTransformPersistence(
                Graphic3d_TransformPers(Graphic3d_TMF_2d, Aspect_TOTP_LEFT_LOWER)
            )
            band.SetZLayer(Graphic3d_ZLayerId_TopOSD)
            band.SetMutable(True)
            self._band = band
        (x1, y1), (x2, y2) = self._px(a), self._px(b)
        h = round(self.height() * self._dpr)
        self._band.SetRectangle(min(x1, x2), h - max(y1, y2), max(x1, x2), h - min(y1, y2))
        if not self._context.IsDisplayed(self._band):
            self._context.Display(self._band, 0, -1, False)
        else:
            self._context.Redisplay(self._band, False)
        self._view.Redraw()

    def _hide_band(self) -> None:
        if self._band is not None and self._context.IsDisplayed(self._band):
            self._context.Remove(self._band, False)
            if self._view is not None:
                self._view.Redraw()

    def _setup_lights(self) -> None:
        # Key and fill lights follow the camera but come from the sides, so the
        # faces of a box get different shades in standard views (U6.3).
        for spec in look.LIGHTS:
            if spec.kind == "ambient":
                light: Any = V3d_AmbientLight(look.grey(spec.strength))
            else:
                light = V3d_DirectionalLight(
                    gp_Dir(*spec.direction), look.grey(spec.strength), True
                )
            self._viewer.AddLight(light)
            self._viewer.SetLightOn(light)

    def _init_view(self) -> None:
        if not native_window_usable(QGuiApplication.platformName()):
            raise RuntimeError("this Qt platform has no window to draw in")  # D2705
        view = self._viewer.CreateView()
        window = Aspect_NeutralWindow()
        set_native_handle(window, int(self.winId()))
        self._window = window
        self._view = view
        self._sync_size(force=True)
        view.SetWindow(window)
        look.apply_rendering(view)
        self._drawing = True
        self._apply_smoothing()
        self.set_palette(self._palette)
        eye, up = STANDARD_VIEWS["iso"]
        view.SetProj(*eye)
        view.SetUp(*up)
        view.MustBeResized()
        if self._pending_part is not None:
            shape, color = self._pending_part
            self._pending_part = None
            self.show_part(shape, color, getattr(self, "_pending_faces", None))
        if self._pending_sketches is not None:
            sketches, self._pending_sketches = self._pending_sketches, None
            self.show_sketches(sketches)
        view.Redraw()  # draw the background at once: no black first frame (U6.8)

    def apply_pick_size(self) -> None:
        """Set the kernel's pick distance from the preference (TR313) and the screen."""
        from fdcad.ui.input.pick_size import scale

        px = PICK_TOLERANCE_PX * scale() * getattr(self, "_dpr", 1.0)
        self._context.SetPixelTolerance(max(1, round(px)))

    def _sync_size(self, force: bool = False) -> None:
        if self._window is None:
            return
        dpr = self.devicePixelRatioF()
        width = max(1, round(self.width() * dpr))
        height = max(1, round(self.height() * dpr))
        changed = self._window.SetSize(width, height)
        scale_changed = dpr != getattr(self, "_dpr", dpr)
        self._dpr = dpr
        self.apply_pick_size()
        self._apply_smoothing()
        if scale_changed and self._view is not None and self._drawing:
            # Another screen: the triad, the part's lines, the highlights and the rim
            # take its scale (D2822).
            self.set_palette(self._palette)
        if self._view is not None and (changed or force):
            self._view.MustBeResized()
            self._view.Redraw()

    def _apply_smoothing(self) -> None:
        """Set the smoothing samples for this screen scale, view size and graphics
        card (D2820). A view that turns a large part simply keeps none until it stops."""
        if self._view is None or not self._drawing:
            return
        width, height = self.view_pixels()
        self._samples = look.msaa_samples(self._dpr, width * height, _card_memory(self._view))
        params = self._view.ChangeRenderingParams()
        if not self._turning_simple and params.NbMsaaSamples != self._samples:
            params.NbMsaaSamples = self._samples

    def _px(self, pos: QPointF) -> tuple[int, int]:
        return round(pos.x() * self._dpr), round(pos.y() * self._dpr)

    def _rotate_by(self, delta: QPointF) -> None:
        assert self._view is not None
        cx, cy = round(self.width() * self._dpr / 2), round(self.height() * self._dpr / 2)
        self._view.StartRotation(cx, cy)
        self._view.Rotation(cx + round(delta.x() * self._dpr), cy + round(delta.y() * self._dpr))

    def _pan_by(self, delta: QPointF) -> None:
        assert self._view is not None
        self._view.Pan(round(delta.x() * self._dpr), round(-delta.y() * self._dpr))

    def _zoom_at(self, pos: QPointF, factor: float) -> None:
        if self._view is None or factor <= 0:
            return
        # V3d_View.ZoomAtPoint scales by 1 + d / 100 for a pointer move of d pixels,
        # or by 1 / (1 - d / 100) when d is negative.
        d = 100.0 * (factor - 1.0) if factor >= 1.0 else -100.0 * (1.0 / factor - 1.0)
        x, y = self._px(pos)
        self._view.StartZoomAtPoint(x, y)
        self._view.ZoomAtPoint(x, y, x + round(d), y)

    def _apply_action(self, action: keynav.Action) -> None:
        assert self._view is not None
        assert action is not None
        if len(action) == 2:
            _kind, deg = action
            self._view.SetTwist(self._view.Twist() + math.radians(deg))
            self._view.Redraw()
            return
        kind, a, b = action
        if kind == "rotate":
            # V3d_X turns the view left and right, V3d_Y turns it up and down.
            self._view.Rotate(V3d_TypeOfAxe.V3d_X, math.radians(a))
            self._view.Rotate(V3d_TypeOfAxe.V3d_Y, math.radians(b))
            if max(abs(a), abs(b)) >= keynav.SHIFT_ARROW_DEG:
                self._centre_on_part()  # a quarter turn is a new view: the part in the middle
        else:
            self._view.Pan(
                round(a * self.width() * self._dpr),
                round(b * self.height() * self._dpr),
            )
        self._view.Redraw()
