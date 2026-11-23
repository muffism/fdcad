"""The 2D sketch editor shown in place of the 3D view while a sketch is open.

The view always looks normal to the sketch plane (DECISIONS D72). It draws
the part's outline on the plane as reference, the sketch in its status
colours (PLAN section 8 item 5), dimensions, and the active tool's preview.
Left click draws or selects, left drag moves geometry through the solver or
draws a selection box, middle drag pans and the wheel zooms.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable
from typing import Any

import numpy as np
from PySide6.QtCore import QEvent, QLineF, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QImage,
    QKeyEvent,
    QKeySequence,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QTransform,
    QWheelEvent,
)
from PySide6.QtWidgets import QLineEdit, QWidget

from fdcad.core.document.model import Param
from fdcad.core.sketch.curvature import curvature_comb
from fdcad.core.sketch.curve_convert import ProjectedCurve
from fdcad.core.sketch.freeform import sample
from fdcad.core.sketch.links import ModelCircle, ModelGeometry, ModelLine
from fdcad.core.sketch.model import (
    Arc,
    Circle,
    Curve,
    Dimension,
    Ellipse,
    EllipseArc,
    Entity,
    Line,
    Point,
    Sketch,
    Spline,
    entity_points,
)
from fdcad.core.sketch.ops.clipboard import Clip
from fdcad.core.sketch.picture import block_bytes
from fdcad.core.sketch.reference import Polyline, RefCircle
from fdcad.core.units import ExpressionError, Kind, UnitSystem, evaluate
from fdcad.ui import clipboard, strings
from fdcad.ui.input.gesture_guide import GestureTracker
from fdcad.ui.sketch_tools import tool_text
from fdcad.ui.sketch_tools.edit import (
    LOCKABLE,
    SketchEdit,
    arc_length_started,
    centres_for_distance,
    dimension_kind,
    distance_ends,
    label_anchor,
    label_position,
    locked_type,
    mirrored_middle,
    preview_dimension,
    shift_sides,
    smart_dimension,
    sticky_diameter,
)
from fdcad.ui.sketch_tools.geometry import (
    Vec,
    arc_angles,
    dist,
    distance_to,
    nearest_on_segment,
    straight_polyline,
)
from fdcad.ui.sketch_tools.inference import Snap, find_snap
from fdcad.ui.sketch_tools.model_snap import ModelSnapIndex
from fdcad.ui.sketch_tools.options import OverDefine, SketchOptions
from fdcad.ui.sketch_tools.over_define import OverDefinePrompt
from fdcad.ui.sketch_tools.tools import Preview, Tool, make_tool
from fdcad.ui.sketch_tools.typed_values import CanvasValues
from fdcad.ui.sketch_tools.value_box import ValueBox
from fdcad.ui.themes.theme import LIGHT, Palette
from fdcad.ui.themes.typography import Role, type_font

#: Pick and snap distance in screen pixels.
PICK_PX = 10.0
#: A strong snap holds until the cursor is this many pick distances away from it,
#: so it does not flicker off just before a click (D434).
STICKY = 1.5
#: Snap kinds that hold (stick) while the cursor stays near them.
STRONG_KINDS = ("point", "center", "midpoint", "quadrant", "intersection")
#: Snap kinds whose relations a dragged point gets when it is dropped there.
DROP_KINDS = ("point", "center", "midpoint", "quadrant", "intersection")
#: Distance of a dimension line from the geometry, in screen pixels.
DIM_OFFSET_PX = 24.0
#: A press and release further apart than this (pixels) is a drag (T1.1.3, T4.4.2).
DRAG_PX = 5.0


def format_length(value: float, units: UnitSystem) -> str:
    """A length in the part's units for dimension labels, in the number style
    chosen in Preferences (TR350, D949)."""
    from fdcad.core.units import number_display as shown

    if units is UnitSystem.IN:
        return shown.length(value / 25.4, 3, True)
    return shown.fixed(value, 2)


def plain_length(value: float, units: UnitSystem) -> str:
    """A length as text a value field reads back (a point, decimals)."""
    if units is UnitSystem.IN:
        return f"{value / 25.4:.3f}"
    return f"{value:.2f}"


#: Linear dimension types whose first two lines are extension lines (TR111, D1708).
_LINEAR = ("distance", "horizontal_distance", "vertical_distance", "doubled_distance")


def shown_segments(
    dim: Dimension, segments: list[tuple[QPointF, QPointF]]
) -> list[tuple[QPointF, QPointF]]:
    """The lines of a dimension less those its display hides: the extension lines and
    the dimension line of a linear dimension (TR111 item 3, D1708)."""
    d = dim.display or {}
    if dim.type not in _LINEAR or len(segments) < 3:
        return segments
    out = list(segments)
    if d.get("hide_line"):
        out = out[:2]
    if d.get("hide_extension"):
        out = out[2:]
    return out


def ask_delete_unmet(parent: QWidget, count: int) -> bool:
    """Ask whether to delete the ``count`` relations and dimensions a drag without
    solving broke (TR112, D1716). Tests replace this."""
    from PySide6.QtWidgets import QMessageBox

    answer = QMessageBox.question(
        parent,
        strings.FREE_DRAG_TITLE,
        strings.FREE_DRAG_QUESTION.format(count=count),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    return answer == QMessageBox.StandardButton.Yes


class SketchCanvas(QWidget):
    #: Show each dimension's formula beside its value (TR235, D921); every sketch.
    show_formulas = False
    #: Construction curves of this sketch hidden and not picked (TR419, D932).
    hide_construction = False
    #: Every closed region shaded faintly (TR335, D952); every sketch, this session.
    shade_regions = False
    #: Sketch points drawn; off hides every point not picked or hovered (TR335).
    show_points = True
    #: Open end points of profiles get a ring while you draw (TR341, D964).
    mark_open_ends = True
    #: Crossing curves get an X and forks of three or more curves a square (TR238).
    mark_crossings = True
    #: New dimensions are reference dimensions, for measuring only (TR111, D965).
    reference_mode = False
    #: Lock All Points: dragging moves nothing, to compare with a shake (TR372, D970).
    points_locked = False
    #: TR112 item 3 (D1716): Detach Segment on Drag, per open sketch (Drag Without
    #: Solving is ``edit.free_drag``).
    detach_drag = False
    #: Relation kinds whose tags are hidden; driving and reference dimensions shown;
    #: the tag text size as a factor of the caption size (TR341). Every sketch.
    hidden_tags: frozenset[str] = frozenset()
    #: The part's own grid (D860): major spacing in mm, or None for the automatic grid.
    grid_spacing: float | None = None
    grid_minor: int = 1
    show_driving = True
    show_reference = True
    tag_scale = 1.0
    #: Line weight and point size as a factor (TR341 item 5, D1013). Every sketch.
    line_scale = 1.0

    """Edits one :class:`SketchEdit`."""

    edited = Signal()  # the sketch changed
    selection_changed = Signal()
    exit_requested = Signal()  # TR120: a double click on nothing or a last Esc
    status_message = Signal(str)
    cursor_moved = Signal(float, float)  # sketch millimetres
    tool_changed = Signal(str)  # tool name, "" for none
    #: Dynamic mirror turned on or off (P2.8 item 4, D514).
    mirror_changed = Signal(bool)
    #: Curvature combs turned on or off (P2.8 item 10, D514).
    curvature_toggled = Signal(bool)
    tool_values_changed = Signal()  # a tool option was set from the canvas (T15.5)
    curves_wanted = Signal(str)  # a tool needs part curves not worked out yet (D2609)
    gesture = Signal(float, float)  # right drag in pixels, y down
    #: The dimension the Dimension panel shows changed (preview, placed or edited).
    dimension_focus = Signal()

    def __init__(
        self,
        edit: SketchEdit,
        units: UnitSystem,
        variables: dict[str, tuple[Kind, float]] | None = None,
        palette: Palette = LIGHT,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.edit = edit
        self.units = units
        self.variables = variables or {}
        self.palette_colors = palette
        self.reference: list[Polyline] = []
        self.reference_circles: list[RefCircle] = []
        #: Curve features above the sketch, projected onto it, for Convert (D517).
        self.curve_sources: list[ProjectedCurve] = []
        #: Intersection curves and silhouette of the part (TR6), once worked out.
        self.model_curves: dict[str, ProjectedCurve] = {}
        #: Part geometry projected onto the sketch plane, for snapping (T1.2.2, D250).
        self.model_index: ModelSnapIndex | None = None
        #: Model circle centres revealed by hovering the circle's edge (W3.2).
        self.revealed: list[Vec] = []
        #: Previous cursor position in sketch millimetres, for segment based reveal.
        self._prev_cursor: Vec | None = None
        #: Show relation tags beside the geometry (W3.3, View menu).
        self.show_relations = True
        #: Painted relation tags: (rectangle, relation type, relation index).
        self._tags: list[tuple[QRectF, str, int]] = []
        self.scale = 4.0  # pixels per mm
        self.center: Vec = (0.0, 0.0)
        self.tool: Tool | None = None
        self.dimension_mode = False
        #: The faint dimension of a selection, placed by a click (TR110).
        self.selection_preview: Dimension | None = None
        self.dim_picks: list[str] = []
        #: Fixed construction copies of part edges made for the picks under way, with
        #: the undo depth before each, so Escape takes them away again (D2648).
        self.dim_copies: dict[str, int] = {}
        from fdcad.ui.sketch_tools.guides import Guides

        #: Temporary guide lines while a drawing tool is active (TR232, D1714).
        self.guides = Guides()
        self._rest: tuple[str, int] | None = None
        #: A dimension type locked by a right click while placing (TR111, D1707).
        self.dim_lock: str | None = None
        #: Where Shift clicked circles and arcs were picked (T4.3.3, D516).
        self.dim_clicks: dict[str, Vec] = {}
        self.selection: list[str] = []
        self.hover: str | None = None
        self.snap: Snap | None = None
        self.mouse: QPointF | None = None
        self._press: QPointF | None = None
        self._drag: dict[str, object] | None = None
        self._pan: QPointF | None = None
        self._right: QPointF | None = None
        self._box: tuple[QPointF, QPointF] | None = None
        self._labels: dict[str, QRectF] = {}
        self.editor: QLineEdit | None = None
        self.value_box: ValueBox | None = None
        #: Tool values typed in the canvas (T15.5, T15.6).
        self.values = CanvasValues(self)
        self._editing_dim: str | None = None
        self._new_dim_depth: int | None = None
        #: The dimension that follows the cursor before placement (T4.2.1).
        self.dim_preview: Dimension | None = None
        #: The dimension placed last in Smart Dimension, shown in its panel (T4.2.5).
        self.last_dimension: str | None = None
        #: A dimension label being dragged (T4.4.2): id, press position, moved.
        self._label_drag: dict[str, object] | None = None
        #: The question shown when a new dimension over defines the sketch (T1.4.4).
        self.over_prompt: OverDefinePrompt | None = None
        #: Where the left button went down while a drawing tool is active (T1.1.3).
        self._tool_press: QPointF | None = None
        #: The relation whose row is hovered in the panel; its tag is highlighted (T14.1.3).
        self.hot_relation: int | None = None
        #: The next click picks the dynamic mirror line (D514).
        self.mirror_pick = False
        #: Draw curvature combs on splines (P2.8 item 10, D514). View state only.
        self.show_curvature = False
        #: Sketch preferences (T11); the window sets them with :meth:`set_options`.
        self.options = SketchOptions()
        #: Ctrl is held during the current mouse event: no snapping (T1.2.7).
        self._ctrl = False
        #: The last strong snap and the exclude list it was found with (D434).
        self._sticky: tuple[Snap, tuple[str, ...]] | None = None
        #: Shows the gesture guide during a right drag (T10.2).
        self.gesture_tracker = GestureTracker(self)
        #: Opens the right click menu at a canvas point; None ends the tool instead.
        self.menu_handler: Callable[[QPointF], object] | None = None
        #: The selection filter (T14.3.2): False for items that may not be selected.
        self.select_filter: Callable[[str], bool] | None = None
        self._box_mods = (False, False)  # Shift, Ctrl when the box started
        self._defined_timer = QTimer(self)
        self._defined_timer.setSingleShot(True)
        self._defined_timer.setInterval(120)
        self._defined_timer.timeout.connect(self._update_defined)
        self._status = edit.status()
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(200, 150)
        self.fit()

    # View -----------------------------------------------------------------------------

    def to_screen(self, p: Vec) -> QPointF:
        """Sketch millimetres to widget pixels (Y up)."""
        return QPointF(
            self.width() / 2 + (p[0] - self.center[0]) * self.scale,
            self.height() / 2 - (p[1] - self.center[1]) * self.scale,
        )

    def to_sketch(self, p: QPointF) -> Vec:
        """Widget pixels to sketch millimetres."""
        return (
            self.center[0] + (p.x() - self.width() / 2) / self.scale,
            self.center[1] - (p.y() - self.height() / 2) / self.scale,
        )

    @property
    def tolerance(self) -> float:
        """Pick distance in millimetres at the current zoom (the preference scales it, TR313)."""
        from fdcad.ui.input.pick_size import scale

        return PICK_PX * scale() / self.scale

    def fit(self) -> None:
        """Zoom so the sketch and the reference outline fit, with a margin."""
        xs: list[float] = []
        ys: list[float] = []
        sk = self.edit.sketch
        for e in sk.entities.values():
            if isinstance(e, Point):
                xs.append(e.x)
                ys.append(e.y)
            elif isinstance(e, Circle):
                cx, cy = sk.xy(e.center)
                xs += [cx - e.radius, cx + e.radius]
                ys += [cy - e.radius, cy + e.radius]
        for line in self.reference:
            xs += [p[0] for p in line]
            ys += [p[1] for p in line]
        if not xs or (max(xs) - min(xs) < 1e-6 and max(ys) - min(ys) < 1e-6):
            self.center = (xs[0], ys[0]) if xs else (0.0, 0.0)
            self.scale = 4.0
        else:
            w = max(max(xs) - min(xs), 1e-3)
            h = max(max(ys) - min(ys), 1e-3)
            self.center = ((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2)
            self.scale = 0.8 * min(max(self.width(), 200) / w, max(self.height(), 150) / h)
        self.update()

    def set_reference(self, lines: list[Polyline], circles: list[RefCircle] | None = None) -> None:
        """Show the part outline on the sketch plane. ``circles`` are its round edges."""
        first = not self.reference
        self.reference = lines
        self.reference_circles = list(circles or [])
        if hasattr(self.tool, "model_lines"):
            self.tool.model_lines = self.reference  # type: ignore[union-attr]
            self.tool.model_circles = self.reference_circles  # type: ignore[union-attr]
        if first and len(self.edit.sketch.entities) <= 1:
            self.fit()
        self.update()

    def set_model_curves(self, curves: dict[str, ProjectedCurve]) -> None:
        """Intersection curves and silhouette (TR6); they arrive off the UI thread."""
        self.model_curves = dict(curves)
        if hasattr(self.tool, "model_curves"):
            self.tool.model_curves = dict(curves)  # type: ignore[union-attr]
            self.tool_values_changed.emit()  # the prompt changes
        self.update()

    def set_curve_sources(self, curves: list[ProjectedCurve]) -> None:
        """Curve features Convert Entities can copy (D517); they arrive off the UI thread."""
        self.curve_sources = curves
        if hasattr(self.tool, "curve_sources"):
            self.tool.curve_sources = curves  # type: ignore[union-attr]
        self.update()

    def pick_feature(self, fid: str, name: str = "") -> bool:
        """A feature clicked in the tree while a tool is active (Convert, D517).

        True when the sketch changed. Tools that take no tree picks ignore it.
        """
        pick = getattr(self.tool, "pick_feature", None)
        if pick is None:
            return False
        changed = bool(pick(fid, name))
        if changed:
            self.changed()
        self._tool_note()
        self.update()
        return changed

    def set_model(self, geometry: ModelGeometry | None) -> None:
        """Use the projected part geometry as snap targets (T1.2.2). Built once per sketch."""
        self.model_index = ModelSnapIndex(geometry) if geometry is not None else None
        self.update()

    def set_options(self, options: SketchOptions) -> None:
        """Follow new sketch preferences, also while the sketch is open."""
        self.options = options
        self.edit.auto_relations = options.auto_relations
        self.edit.lock_changed = options.lock_changed_dimensions  # TR238 (D1706)
        self.edit.drag_changes_dimensions = options.drag_changes_dimensions  # TR112
        from fdcad.ui.sketch_tools.options import AUTO_KINDS

        self.edit.auto_off = {k for k in AUTO_KINDS if not getattr(options, f"auto_{k}", True)}
        if not options.model_snaps:
            self.revealed = []
        self.update()

    # Tools ----------------------------------------------------------------------------

    def _drop_copy(self, pick: str) -> None:
        """Take away the part edge copy made for ``pick``, if one was (D2648).

        Bug hunt O10a-6: Escape dropped the pick but left its fixed construction
        line in the sketch. A copy that a placed dimension uses is never in
        ``dim_copies``: placing one clears it.
        """
        depth = self.dim_copies.pop(pick, None)
        if depth is None or pick not in self.edit.sketch.entities:
            return
        if self.edit.undo_depth == depth + 1:
            self.edit.rollback(depth)  # nothing changed since the copy was made
        else:
            self.edit.checkpoint()
            self.edit.delete({pick})
        self.changed()

    def _drop_copies(self) -> None:
        """Take away every part edge copy of the picks under way, newest first."""
        for pick in sorted(self.dim_copies, key=self.dim_copies.__getitem__, reverse=True):
            self._drop_copy(pick)

    def set_tool(self, name: str | None) -> None:
        """Start a drawing tool, ``"dimension"`` for smart dimension, or None to select."""
        self.values.tool_changed()
        self.dimension_mode = name == "dimension"
        self._drop_copies()  # picks left unused take their part edge copies along
        self.dim_picks = []
        self.dim_lock = None
        self.guides.clear()  # TR232: guides vanish when the tool ends
        self.dim_clicks = {}
        self.dim_preview = None
        self.last_dimension = None
        #: The centerline of the last diameter placed: later lines parallel to it are
        #: diameters too, until Esc or another tool (TR361, D951).
        self.diameter_axis: str | None = None
        self._close_prompt()
        self.tool = make_tool(name, self.edit) if name and not self.dimension_mode else None
        if hasattr(self.tool, "model_lines"):
            # Pick tools (P2.8) can use the part outline on the sketch plane.
            self.tool.model_lines = self.reference  # type: ignore[union-attr]
            self.tool.model_circles = self.reference_circles  # type: ignore[union-attr]
        if hasattr(self.tool, "curve_sources"):
            self.tool.curve_sources = self.curve_sources  # type: ignore[union-attr]
        if hasattr(self.tool, "model_curves"):  # TR6
            self.tool.model_curves = dict(self.model_curves)  # type: ignore[union-attr]
            for kind in getattr(self.tool, "needs", ()):  # worked out on demand (D2609)
                if kind not in self.model_curves:
                    self.curves_wanted.emit(kind)
        if hasattr(self.tool, "pixels_of"):  # TR116 item 2: trace a picture
            self.tool.pixels_of = self.picture_pixels  # type: ignore[union-attr]
        if hasattr(self.tool, "units"):  # plain numbers in typed curves (TR28)
            self.tool.units = self.units  # type: ignore[union-attr]
        take = getattr(self.tool, "take_selection", None)
        if take is not None:
            # Tools that work on entities picked before they start (TR1.1).
            take([s for s in self.selection if s in self.edit.sketch.entities])
        self.snap = None
        self.revealed = []
        self._prev_cursor = None
        self.setCursor(tool_cursor(name))
        self.tool_changed.emit(name or "")
        if self.tool is not None:
            self.status_message.emit(strings.SKETCH_TOOL_HINT.format(tool=self.tool.label))
        elif self.dimension_mode:
            self.status_message.emit(strings.DIMENSION_HINT)
        else:
            self.status_message.emit(strings.READY)
        self.dimension_focus.emit()
        self.update()

    def set_tool_option(self, key: str, value: object) -> None:
        """Set a tool option, as its panel field does (the panel and the canvas labels, T15.5)."""
        tool = self.tool
        if tool is None:
            return
        setattr(tool, key, value)
        option_changed = getattr(tool, "option_changed", None)
        if option_changed is not None and option_changed(key):
            self.changed()
        take_focus = getattr(tool, "take_focus", None)
        focus = take_focus() if take_focus is not None else None
        if focus is not None:  # Zoom to Problem (TR36): centre there and select it
            at, ids = focus
            if at is not None:
                self.center = at
                self.scale = max(self.scale, 8.0)
            self.selection = [i for i in ids if i in self.edit.sketch.entities]
        self._tool_note()
        self.update()
        self.tool_values_changed.emit()

    def panel_dimension(self) -> Dimension | None:
        """The dimension the Dimension panel shows (T4.2.5, T7.4), or None.

        In Smart Dimension: the preview that follows the cursor, then the one being
        typed, then the one placed last. Otherwise a single selected dimension.
        """
        if self.dimension_mode and self.dim_preview is not None:
            return self.dim_preview
        if self._editing_dim is not None:
            return self._dimension(self._editing_dim)
        dims = [d for d in self.edit.sketch.dimensions if d.id in self.selection]
        if len(dims) == 1:
            return dims[0]
        if self.dimension_mode and self.last_dimension is not None and not self.selection:
            return self._dimension(self.last_dimension)
        return None

    @property
    def tool_name(self) -> str:
        """Active tool name, or ""."""
        if self.dimension_mode:
            return "dimension"
        return self.tool.name if self.tool else ""

    def changed(self) -> None:
        """Solve now and work out the defined state shortly after."""
        self.edit.refresh(full=False)
        self.edit.refuse_broken_locks()  # Keep This Side (TR338, D1302)
        weak = self.edit.replace_weak()  # TR362 (D1310)
        if weak:
            self.status_message.emit(weak)
        jump = self.edit.take_jump_note()
        if jump:
            self.status_message.emit(jump)
        if (
            self.edit.mirror_axis is not None
            and self.edit.mirror_axis not in self.edit.sketch.entities
        ):
            self.set_dynamic_mirror(None)  # the mirror line was deleted or undone (D514)
        self._sticky = None  # geometry may have moved under a held snap
        self._status = self.edit.status()
        self._defined_timer.start()
        self.selection = [s for s in self.selection if self._exists(s)]
        self.edited.emit()
        self.update()

    def _update_defined(self) -> None:
        self.edit.refresh(full=True)
        self.edited.emit()
        self.update()

    def _exists(self, item: str) -> bool:
        sk = self.edit.sketch
        index = relation_index(item)
        if index is not None:
            return index < len(sk.relations)
        return item in sk.entities or any(d.id == item for d in sk.dimensions)

    def selected_relations(self) -> list[int]:
        """Indexes of the relations in the selection (picked by their tag, T1.3.2)."""
        out = []
        for item in self.selection:
            index = relation_index(item)
            if index is not None and index < len(self.edit.sketch.relations):
                out.append(index)
        return out

    def set_hot_relation(self, index: int | None) -> None:
        """Highlight the tag of relation ``index`` (a hovered panel row), or none."""
        if index != self.hot_relation:
            self.hot_relation = index
            self.update()

    def select_relations(self, indexes: list[int]) -> None:
        """Select relations by index, so Delete removes them (T1.3.2, T3.3)."""
        self.selection = [f"r{i}" for i in indexes]
        self.selection_changed.emit()
        self.update()

    # Actions used by the panel and shortcuts -------------------------------------------

    def run(self, change: Callable[[], object]) -> None:
        """Make an undoable change to the sketch."""
        self.edit.checkpoint()
        change()
        self.changed()

    def delete_selection(self) -> None:
        """Delete the selected entities and dimensions."""
        if self.selection:
            from fdcad.core.sketch.ops.split import join, joinable

            items = set(self.selection)
            self.selection = []
            self.edit.checkpoint()
            # A split point puts its two pieces back together (TR2.2), in the same step.
            sk = self.edit.sketch
            splits = {i for i in items if i in sk.entities and joinable(sk, i) is not None}
            self.edit.delete(items - splits)
            leftover = {i for i in splits if i in sk.entities and not join(sk, i)}
            if leftover:
                self.edit.delete(leftover)
            self.edit.drop_if_unchanged()  # only the origin was picked: nothing to undo
            self.changed()
            self.selection_changed.emit()

    def copy_selection(self) -> int:
        """Ctrl+C: copy the selected entities with the relations and dimensions among
        them to the clipboard (TR3.1). Returns how many entities were copied."""
        import json

        from PySide6.QtCore import QMimeData

        from fdcad.core.sketch.ops.clipboard import ClipError, clip_to_data, extract
        from fdcad.ui.sketch_tools.paste_tool import CLIPBOARD_FORMAT

        ids = [s for s in self.selection if s in self.edit.sketch.entities]
        try:
            clip = extract(self.edit.sketch, ids)
        except ClipError as exc:
            self.status_message.emit(str(exc))
            return 0
        text = json.dumps(clip_to_data(clip))
        mime = QMimeData()
        mime.setData(CLIPBOARD_FORMAT, text.encode("utf-8"))
        clipboard.put(mime)
        n = len(clip.top)
        self.status_message.emit(
            f"Copied {n} entit{'ies' if n != 1 else 'y'}. Press Ctrl+V to paste."
        )
        return n

    def start_paste(self, clip: Clip | None = None, verb: str = "Pasted") -> bool:
        """Ctrl+V: the copied entities (or ``clip``, an inserted DXF drawing) follow the
        cursor until a click places them. The clipboard is read as data only. False
        when it holds no sketch entities."""
        import json

        from PySide6.QtGui import QGuiApplication

        from fdcad.core.sketch.ops.clipboard import ClipError, clip_from_data
        from fdcad.ui.sketch_tools.paste_tool import CLIPBOARD_FORMAT, PasteTool

        if clip is None:
            mime = QGuiApplication.clipboard().mimeData()
            if mime is None or not mime.hasFormat(CLIPBOARD_FORMAT):
                self.status_message.emit(
                    "Nothing to paste. Select sketch entities and press Ctrl+C."
                )
                return False
            try:
                raw = json.loads(bytes(mime.data(CLIPBOARD_FORMAT).data()).decode("utf-8"))
                clip = clip_from_data(raw)
            except (ValueError, ClipError):
                self.status_message.emit("The clipboard does not hold sketch entities.")
                return False
        self.set_tool(None)
        self.tool = PasteTool(self.edit, clip, verb)
        self.tool.tolerance = self.tolerance
        if self.mouse is not None:
            self.tool.hover(self._snap_at(self.mouse))
        self.status_message.emit(self.tool.prompt)
        self.update()
        return True

    def _end_finished_tool(self) -> None:
        """A one shot tool (Paste) is done: select what it made and go back to selecting."""
        made = [e for e in getattr(self.tool, "placed", []) if e in self.edit.sketch.entities]
        self.set_tool(None)
        if made:
            self.selection = made
            self.selection_changed.emit()
        self.update()

    def undo(self) -> None:
        """Undo inside the sketch."""
        self.edit.undo()
        self.changed()

    def redo(self) -> None:
        """Redo inside the sketch."""
        self.edit.redo()
        self.changed()

    def _on_locked_layer(self, eid: str) -> bool:
        """True when the item (or the curve a point belongs to) is on a locked layer."""
        sk = self.edit.sketch
        if not sk.layers:
            return False
        from fdcad.core.sketch.layers import layer_style
        from fdcad.core.sketch.model import entity_points

        owners = [eid] + [
            c.id
            for c in sk.entities.values()
            if not isinstance(c, Point) and eid in entity_points(c)
        ]
        return any((layer_style(sk, o) or {}).get("locked") is True for o in owners)

    def hidden_construction(self, entity: object) -> bool:
        """True for a curve that is not shown or picked: construction while Hide
        Construction is on (TR419), or a curve on a hidden layer (TR389)."""
        if isinstance(entity, Point):
            return False
        if self.edit.sketch.layers:
            from fdcad.core.sketch.layers import hidden

            if hidden(self.edit.sketch, str(getattr(entity, "id", ""))):
                return True
        return self.hide_construction and bool(getattr(entity, "construction", False))

    def set_hide_construction(self, on: bool) -> None:
        """Hide or show this sketch's construction curves; picked ones are let go."""
        self.hide_construction = on
        if on:
            sk = self.edit.sketch
            self.selection = [
                s for s in self.selection if not self.hidden_construction(sk.entities.get(s))
            ]
            self.selection_changed.emit()
        self.update()

    # Hit testing ----------------------------------------------------------------------

    def pick(self, pos: QPointF, skip: set[str] | None = None) -> str | None:
        """Entity or dimension under the cursor. Points win over curves. ``skip``
        items are passed over."""
        for did, rect in self._labels.items():
            if rect.adjusted(-3, -3, 3, 3).contains(pos):
                return did
        p = self.to_sketch(pos)
        tol = self.tolerance
        best: tuple[float, str] | None = None
        for e in self.edit.sketch.entities.values():
            if self.hidden_construction(e) or (skip and e.id in skip):
                continue
            d = distance_to(self.edit.sketch, e.id, p)
            if isinstance(e, Point):
                d -= tol  # a point in reach wins over the curve through it (D434)
            if d <= tol and (best is None or d < best[0]):
                best = (d, e.id)
        return best[1] if best else None

    # Mouse ----------------------------------------------------------------------------

    def _snap_at(self, pos: QPointF, exclude: list[str] | None = None) -> Snap:
        """Snap for drawing, Smart Dimension and dragging, with a little stickiness.

        A strong snap (a point, centre, midpoint, quadrant or intersection) found
        before holds while the cursor stays within ``STICKY`` pick distances of it
        and nothing stronger is closer, so the click lands where the snap was shown
        even if the hand drifts a little (D434).
        """
        snap = self._find_snap_at(pos, exclude)
        key = tuple(exclude or [])
        if not self.options.snapping or self._ctrl or getattr(self.tool, "raw_cursor", False):
            self._sticky = None
            return snap
        if snap.kind in STRONG_KINDS:
            self._sticky = (snap, key)
            return snap
        if self._sticky is not None:
            held, held_key = self._sticky
            cursor = self.to_sketch(pos)
            alive = held.target is None or held.target in self.edit.sketch.entities
            near = dist(held.xy, cursor) <= self.tolerance * STICKY
            if held_key == key and alive and near:
                return held
            self._sticky = None
        return snap

    def _find_snap_at(self, pos: QPointF, exclude: list[str] | None = None) -> Snap:
        """Snap for drawing, Smart Dimension and dragging (T1.2), in the T1.2.3 order.

        Ctrl held or snapping off in the options gives a free point (T1.2.7).
        """
        snap = self._find_snap_base(pos, exclude)
        return self._stepped(snap)

    def _stepped(self, snap: Snap) -> Snap:
        """The snap with the one shot snap filter, Snap to Grid and, with Alt held, length
        and angle steps from the last click (TR102, D860)."""
        only = getattr(self, "snap_only", None)
        if only is not None and snap.kind != only:
            snap = Snap("free", snap.x, snap.y)
        if snap.kind not in ("free", "aligned"):
            return snap
        from PySide6.QtWidgets import QApplication

        alt = bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.AltModifier)
        clicks = getattr(self.tool, "clicks", None) if self.tool is not None else None
        if alt and clicks:
            ax, ay = clicks[-1].xy
            dx, dy = snap.x - ax, snap.y - ay
            length = math.hypot(dx, dy)
            if length > 1e-9:
                step = max(self.options.length_step, 1e-6)
                turn = math.radians(max(self.options.angle_step, 0.1))
                length = max(round(length / step), 1) * step
                angle = round(math.atan2(dy, dx) / turn) * turn
                return Snap("free", ax + length * math.cos(angle), ay + length * math.sin(angle))
        grid = self.options.grid_snap
        if grid == "always" or (grid == "shown" and self.options.show_grid):
            step = self._grid_step()
            if self.options.grid_kind == "polar":  # TR238 (D1014): ring and spoke
                from fdcad.ui.sketch_tools.polar_grid import polar_snap

                return Snap("free", *polar_snap(snap.x, snap.y, step, self.options.polar_angle))
            return Snap("free", round(snap.x / step) * step, round(snap.y / step) * step)
        return snap

    def _find_snap_base(self, pos: QPointF, exclude: list[str] | None = None) -> Snap:
        snapping = self.options.snapping and not self._ctrl
        if self.tool is not None:
            self.tool.snapping = snapping
            self.tool.tolerance = self.tolerance
        cursor = self.to_sketch(pos)
        if not snapping or getattr(self.tool, "raw_cursor", False):
            return Snap("free", *cursor)
        if not self.options.model_snaps:
            snap = find_snap(self.edit.sketch, cursor, self.tolerance, exclude or [])
            guide = self.guides.snap(cursor, self.tolerance)  # TR232 (D1714)
            if guide is not None and snap.kind in ("free", "aligned", "on_curve"):
                return Snap("guide", guide[0], guide[1])
            return snap
        self.reveal_centres(cursor)
        snap = find_snap(
            self.edit.sketch,
            cursor,
            self.tolerance,
            exclude or [],
            extra=self.revealed,
            model=self.model_index,
        )
        if snap.kind in ("free", "aligned", "on_curve"):
            guide = self.guides.snap(cursor, self.tolerance)  # TR232 (D1714)
            if guide is not None:
                return Snap("guide", guide[0], guide[1])
            # A revealed centre of the part's outline: tied to a fixed copy (D116 item 3).
            for c in self.revealed:
                if dist(c, cursor) <= self.tolerance:
                    centre = self.model_index.centre_at(c) if self.model_index else None
                    source = centre.source if centre is not None else None
                    return Snap("center", c[0], c[1], model=c, model_source=source)
        return snap

    def centre_marks(self) -> list[Vec]:
        """Centres drawn as a small cross: revealed part centres, and the centres of
        sketch circles and arcs that are hovered or selected (T2.5.4)."""
        sk = self.edit.sketch
        marks = list(self.revealed)
        for eid in [self.hover, *self.selection]:
            ent = sk.entities.get(eid) if eid else None
            if isinstance(ent, Circle | Arc):
                c = sk.xy(ent.center)
                if c not in marks:
                    marks.append(c)
        return marks

    def _drag_exclude(self, pid: str) -> list[str]:
        """Items that move with a dragged point, so it never snaps to them."""
        sk = self.edit.sketch
        group = {pid}
        grown = True
        while grown:
            grown = False
            for rel in sk.relations:
                if rel.type == "coincident" and set(rel.entities) & group:
                    new = {e for e in rel.entities if isinstance(sk.entities.get(e), Point)}
                    if not new <= group:
                        group |= new
                        grown = True
        curves = [c.id for c in sk.curves(True) if group & set(_points_of_entity(c))]
        return [*group, *curves]

    def reveal_centres(self, cursor: Vec) -> None:
        """Hovering a model circle's edge reveals its centre (W3.2).

        A single mouse move can jump over the edge, so the segment from the
        previous cursor position is tested as well as the point itself. Sketch
        circles need no reveal: ``find_snap`` already returns their centres.
        """
        a = self._prev_cursor if self._prev_cursor is not None else cursor
        self._prev_cursor = cursor
        rings = self.model_index.ring_circles() if self.model_index is not None else []
        for c, r in [*self.reference_circles, *rings]:
            seg = dist(c, nearest_on_segment(c, a, cursor))
            far = max(dist(c, a), dist(c, cursor))
            if seg <= r + self.tolerance and far >= r - self.tolerance and c not in self.revealed:
                self.revealed.append(c)

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802
        """The cursor left the canvas: forget the previous position."""
        self._prev_cursor = None
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Draw, pick for a dimension, select, or start a drag."""
        self.setFocus()
        pos = event.position()
        self._ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan = pos
            return
        if event.button() == Qt.MouseButton.RightButton:
            self._right = pos
            self.gesture_tracker.press(pos)
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        try:
            self._left_press(event, pos)
        finally:
            self._sticky = None  # a click uses the held snap once, then lets go

    def _left_press(self, event: QMouseEvent, pos: QPointF) -> None:
        """Left button: draw, pick for a dimension, select, or start a drag."""
        self._commit_editor()
        self._close_prompt()
        if self.mirror_pick:
            self._pick_mirror_line(pos)
            return
        if self.values.is_open():
            self.values.click_through()  # an untouched automatic box gives way (D513)
        if self.tool is not None and (key := self.values.label_at(pos)) is not None:
            self.values.open_option(key)  # a value label opens the value box (T15.5)
            return
        if self.tool is not None:
            self._set_tool_keys(event.modifiers())
            snap = self._snap_at(pos)
            if self.tool.click(snap):
                self.changed()
                self.edit.skip_next = False  # Tab skips one click's relations (TR231)
            self._tool_note()
            if self.tool.finished:
                self._end_finished_tool()
                return
            self.snap = self.tool.cursor
            self._tool_press = pos if self.tool.busy else None
            self.values.auto_open()  # on screen value input (T11.6, D513)
            self.update()
            return
        if self.dimension_mode:
            shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            self._dimension_click(pos, shift)
            return
        ctrl = bool(
            event.modifiers()
            & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
        )
        tag = self.tag_index_at(pos)
        if tag is not None:
            item = f"r{tag}"
            if not ctrl:
                self.selection = [item]
            elif item in self.selection:
                self.selection.remove(item)
            else:
                self.selection.append(item)
            self.selection_changed.emit()
            self.update()
            return
        hit = self.pick(pos)
        if hit is not None and self.select_filter is not None and not self.select_filter(hit):
            hit = None  # the selection filter leaves this type out (T14.3.2)
        if hit is None and not ctrl:
            # Decide by where the click is, not by the last hover (a click can come
            # without a move first): only a click near the picks places the dimension.
            self._update_selection_preview(pos, None)
        if hit is None and not ctrl and getattr(self, "selection_preview", None) is not None:
            # The faint dimension of the selection: a click places it (TR110, D862).
            picks = [s for s in self.selection if s in self.edit.sketch.entities][:2]
            self.selection_preview = None
            self.set_tool("dimension")
            self.dim_picks = picks
            self._dimension_click(pos)
            self.update()
            return
        if hit is None:
            #: A click in empty space first clears; on an empty selection it picks the
            #: region under it (TR39).
            self._box_cleared = bool(self.selection) and not ctrl
            if not ctrl:
                self.selection = []
                self.selection_changed.emit()
            self._box = (pos, pos)
            mods = event.modifiers()
            self._box_mods = (
                bool(mods & Qt.KeyboardModifier.ShiftModifier),
                bool(mods & Qt.KeyboardModifier.ControlModifier),
            )
        else:
            if ctrl:
                if hit in self.selection:
                    self.selection.remove(hit)
                else:
                    self.selection.append(hit)
            elif hit not in self.selection:
                self.selection = [hit]
            self.selection_changed.emit()
            if hit in self.edit.sketch.entities and self.points_locked:
                self.status_message.emit(strings.POINTS_LOCKED)  # TR372
            elif hit in self.edit.sketch.entities and self._on_locked_layer(hit):
                self.status_message.emit(strings.LAYER_LOCKED)  # TR419 item 2
            elif hit in self.edit.sketch.entities:
                self._drag = {"id": hit, "start": self.to_sketch(pos), "moved": False}
            elif self._dimension(hit) is not None and not ctrl:
                self._label_drag = {"id": hit, "press": pos, "moved": False, "click": False}
        self._press = pos
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Hover, rubber band, drag, pan."""
        pos = event.position()
        self.mouse = pos
        self._ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        x, y = self.to_sketch(pos)
        self.cursor_moved.emit(x, y)
        if self._right is not None:
            self.gesture_tracker.move(pos)
        if self._pan is not None:
            d = pos - self._pan
            self._pan = pos
            self.center = (self.center[0] - d.x() / self.scale, self.center[1] + d.y() / self.scale)
            self.update()
            return
        if self._label_drag is not None:
            self._move_label(pos)
            return
        if self.tool is not None:
            self._set_tool_keys(event.modifiers())
            self.snap = self.tool.track(self._snap_at(pos))
            self._watch_rest(self.snap)  # TR232: resting on a point makes a guide
            self.values.follow(pos)
            self.update()
            return
        if self.dimension_mode:
            self.snap = self._snap_at(pos)
            self.hover = self.pick(pos)
            self._update_preview(pos)
            self.update()
            return
        if self._box is not None:
            self._box = (self._box[0], pos)
            self.update()
            return
        if self._drag is not None and self._press is not None:
            if not self._drag["moved"] and (pos - self._press).manhattanLength() < 3:
                return
            self._drag_move(pos)
            return
        hover = self.pick(pos)
        if hover is not None and self.select_filter is not None and not self.select_filter(hover):
            hover = None
        tag = self.tag_at(pos)
        self.setToolTip(strings.RELATION_NAMES.get(tag, tag) if tag else "")
        self._update_selection_preview(pos, hover)  # TR110
        before = len(self.revealed)
        self.reveal_centres(self.to_sketch(pos))
        if hover != self.hover or len(self.revealed) != before:
            self.hover = hover
            self.update()

    def _drag_move(self, pos: QPointF) -> None:
        drag = self._drag
        assert drag is not None
        sk = self.edit.sketch
        if not drag["moved"]:
            self.edit.checkpoint()
            drag["moved"] = True
            eid = str(drag["id"])
            ent = sk.entities[eid]
            pts = _points_of_entity(ent)
            picked = [s for s in self.selection if s in sk.entities]
            # A point or circle of a picked group moves the group too (TR53, D973).
            drag["group"] = eid in picked and len(picked) > 1
            if (not isinstance(ent, Point | Circle) or drag["group"]) and eid in self.selection:
                # A region or several curves picked: the whole shape moves (TR39).
                for other in self.selection:
                    shape = sk.entities.get(other)
                    if shape is not None and (not isinstance(shape, Point) or drag["group"]):
                        pts = [*pts, *(p for p in _points_of_entity(shape) if p not in pts)]
            drag["orig"] = {p: sk.xy(p) for p in pts}
            if self.detach_drag and isinstance(ent, Point) and not drag["group"]:
                from fdcad.core.sketch.free_drag import detach_end

                keep = next(
                    (
                        s
                        for s in self.selection
                        if s in sk.entities and eid in _points_of_entity(sk.entities[s])
                    ),
                    None,
                )
                detach_end(sk, eid, keep)  # TR112 item 3: break the join
        eid = str(drag["id"])
        ent = sk.entities[eid]
        cursor = self.to_sketch(pos)
        start = drag["start"]
        assert isinstance(start, tuple)
        dx, dy = cursor[0] - start[0], cursor[1] - start[1]
        if isinstance(ent, Point) and not drag.get("group"):
            # Dragged points snap like drawing does (T1.2); relations are added on release.
            snap = self._snap_at(pos, self._drag_exclude(eid))
            drag["snap"] = snap
            self.snap = snap if snap.kind not in ("free",) else None
            self.edit.drag_to({eid: snap.xy})
        elif isinstance(ent, Circle) and not drag.get("group"):
            center = sk.xy(ent.center)
            radius = math.hypot(cursor[0] - center[0], cursor[1] - center[1])
            if self.edit.free_drag and radius > 0:
                ent.radius = radius  # TR112 item 1: no solve
            else:
                self.edit.drag_radius(eid, radius)
        else:
            orig = drag["orig"]
            assert isinstance(orig, dict)
            self.edit.drag_to({p: (xy[0] + dx, xy[1] + dy) for p, xy in orig.items()})
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Finish a drag or a selection box."""
        if self.tool is not None and event.button() == Qt.MouseButton.LeftButton:
            self.snap_only = None  # the snap filter lasts one click (TR102)
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan = None
            return
        if event.button() == Qt.MouseButton.LeftButton and self._label_drag is not None:
            self._finish_label_drag()
            return
        if event.button() == Qt.MouseButton.LeftButton and self._tool_press is not None:
            self._release_tool(event)
            return
        if event.button() == Qt.MouseButton.RightButton and self._right is not None:
            d = event.position() - self._right
            self._right = None
            self.gesture_tracker.release()
            if d.manhattanLength() > 6:
                self.gesture.emit(d.x(), d.y())
            elif self.toggle_dimension_lock():
                pass  # TR111 item 1: a right click while placing locks the type
            elif self.menu_handler is not None:
                self.menu_handler(event.position())  # right click menu (T9.2, T9.3)
            elif self.tool is not None and self.tool.busy:
                self._cancel_tool()
            elif self.tool is not None or self.dimension_mode:
                self.set_tool(None)
            self.update()
            return
        if self._box is not None:
            a, b = self._box
            self._box = None
            if (a - b).manhattanLength() > 3:
                self._select_box(a, b)
            elif not getattr(self, "_box_cleared", False):
                self.select_region_at(self.to_sketch(b), add=self._box_mods[1])  # TR39
            self.update()
        if self._drag is not None:
            moved = bool(self._drag["moved"])
            snap = self._drag.get("snap")
            eid = str(self._drag["id"])
            self._drag = None
            self.snap = None
            if moved and isinstance(snap, Snap) and not self.edit.free_drag:
                self._attach_after_drag(eid, snap)
            if moved and self.edit.free_drag:
                self._after_free_drag()  # TR112 item 1
            if moved:
                self.edit.drop_if_unchanged()  # fully defined geometry did not move
                self.changed()
        self._press = None

    def _after_free_drag(self) -> None:
        """After a drag with no solve, offer to delete what no longer holds (TR112)."""
        from fdcad.core.sketch.free_drag import delete_items, unmet

        broken = unmet(self.edit.sketch)
        if not broken:
            return
        if ask_delete_unmet(self, len(broken)):
            delete_items(self.edit.sketch, broken)
            self.status_message.emit(strings.FREE_DRAG_DELETED.format(count=len(broken)))
        else:
            self.status_message.emit(strings.FREE_DRAG_KEPT.format(count=len(broken)))

    def _attach_after_drag(self, pid: str, snap: Snap) -> None:
        """A point dropped on a point snap gets the snap's relations, unless they over define.

        Dropping near a curve (on curve) or on a guide adds nothing, so a drag
        that only passes a line does not tie the point to it.
        """
        linked = snap.model is not None or snap.model_curve is not None
        if snap.kind not in DROP_KINDS or (not snap.relations and not linked):
            return
        before = len(self.edit.sketch.relations)
        points = len(self.edit.sketch.entities)
        self.edit.attach(pid, snap)
        if len(self.edit.sketch.relations) == before:
            return
        self.edit.refresh(full=False)
        result = self.edit.result
        if result is None or not result.solved or result.conflicting or result.redundant:
            # Keep the move, drop what it would have added.
            sk = self.edit.sketch
            added = set(list(sk.entities)[points:])
            sk.relations = sk.relations[:before]
            for eid in added:
                sk.entities.pop(eid, None)
            sk.relations = [r for r in sk.relations if not set(r.entities) & added]

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Double click a dimension to change it; double click ends a line chain."""
        if self.tool is not None:
            self._cancel_tool()
            self.update()
            return
        hit = self.pick(event.position())
        if hit is not None and hit.startswith("d"):
            self.edit_dimension(hit)
        elif hit is None and self.options.double_click_exit and not self.dimension_mode:
            self.exit_requested.emit()  # TR120 (D941)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        """Zoom about the cursor."""
        steps = event.angleDelta().y() / 120.0
        if not steps:
            return
        pos = event.position()
        before = self.to_sketch(pos)
        self.scale = max(1e-3, min(1e5, self.scale * (1.2**steps)))
        after = self.to_sketch(pos)
        self.center = (
            self.center[0] + before[0] - after[0],
            self.center[1] + before[1] - after[1],
        )
        self.update()

    def _select_box(self, a: QPointF, b: QPointF) -> None:
        """Box selection (T14.3.3): left to right takes items inside, right to left also
        items the box crosses; Shift adds, Ctrl toggles, else the box replaces."""
        from fdcad.ui.input import selection_rules as rules

        rect = rules.rect_of((a.x(), a.y()), (b.x(), b.y()))
        crossing = rules.is_crossing((a.x(), a.y()), (b.x(), b.y()))
        found: list[str] = []
        for eid, pts in self.box_shapes().items():
            if self.select_filter is not None and not self.select_filter(eid):
                continue
            if rules.picked(rect, pts, crossing):
                found.append(eid)
        shift, ctrl = self._box_mods
        self.selection = rules.apply(self.selection, found, rules.scheme(shift, ctrl))
        self.selection_changed.emit()

    def box_shapes(self) -> dict[str, list[tuple[float, float]]]:
        """Every entity and dimension label as screen points, for box selection."""
        sk = self.edit.sketch
        out: dict[str, list[tuple[float, float]]] = {}

        def screen(p: Vec) -> tuple[float, float]:
            q = self.to_screen(p)
            return (q.x(), q.y())

        for e in sk.entities.values():
            if isinstance(e, Point):
                out[e.id] = [screen(sk.xy(e.id))]
            elif isinstance(e, Line):
                out[e.id] = [screen(sk.xy(e.p1)), screen(sk.xy(e.p2))]
            elif isinstance(e, Circle | Arc):
                c, r = sk.xy(e.center), sk.radius(e.id)
                a0, a1 = (0.0, 2 * math.pi) if isinstance(e, Circle) else arc_angles(sk, e)
                n = 48
                out[e.id] = [
                    screen(
                        (
                            c[0] + r * math.cos(a0 + (a1 - a0) * i / n),
                            c[1] + r * math.sin(a0 + (a1 - a0) * i / n),
                        )
                    )
                    for i in range(n + 1)
                ]
        for did, rect in self._labels.items():
            if self._exists(did):
                out[did] = [
                    (rect.left(), rect.top()),
                    (rect.right(), rect.top()),
                    (rect.right(), rect.bottom()),
                    (rect.left(), rect.bottom()),
                    (rect.left(), rect.top()),
                ]
        return out

    # Dimensions -----------------------------------------------------------------------

    def reference_line_at(self, pos: QPointF) -> tuple[Vec, Vec] | None:
        """The straight edge of the part outline under the cursor, if any."""
        p = self.to_sketch(pos)
        for line in self.reference:
            ends = straight_polyline(line)
            if ends is not None and dist(p, nearest_on_segment(p, *ends)) <= self.tolerance:
                return ends
        return None

    def _model_copy(self, snap: Snap) -> str:
        """The fixed copy of the part item a snap landed on (D113, D250). Checkpoint first."""
        curve = snap.model_curve
        if snap.model is not None:
            return self.edit.reference_point(snap.model, snap.model_source)
        if isinstance(curve, ModelLine):
            return self.edit.reference_line(curve.a, curve.b, curve.source)
        assert isinstance(curve, ModelCircle)
        return self.edit.reference_circle(curve.centre, curve.radius, curve.source)

    def _dimension_may_pick(self, pid: str) -> bool:
        """False for an end point or centre while the Sketch preferences turn Smart
        Dimension picks of that kind off (TR418)."""
        sk = self.edit.sketch
        if not isinstance(sk.entities.get(pid), Point):
            return True
        for e in sk.entities.values():
            if isinstance(e, Circle | Arc) and e.center == pid:
                return self.options.dimension_centres
            ends = (
                (e.p1, e.p2)
                if isinstance(e, Line)
                else (e.start, e.end)
                if isinstance(e, Arc)
                else ()
            )
            if pid in ends and not self.options.dimension_ends:
                return False
        return True

    def _dimension_midpoint(self, snap: Snap) -> str | None:
        """A construction point held at the midpoint the snap shows, for Smart Dimension
        (TR418): on a sketch line or arc, or on a fixed copy of a part edge. Takes the
        undo checkpoint. None when the snap is on nothing that has a midpoint."""
        sk = self.edit.sketch
        target = snap.target if isinstance(sk.entities.get(snap.target or ""), Line | Arc) else None
        if target is None and not isinstance(snap.model_curve, ModelLine):
            return None
        for rel in sk.relations:  # a curve's midpoint point is shared, not added again
            if target and rel.type == "midpoint" and rel.entities[1:] == [target]:
                point = sk.entities.get(rel.entities[0])
                if isinstance(point, Point):
                    return point.id
        self.edit.checkpoint()
        if target is None:
            target = self._model_copy(snap)
        pid = sk.add_point(snap.x, snap.y, construction=True)
        sk.relate("midpoint", pid, target)
        return pid

    def _dimension_click(self, pos: QPointF, shift: bool = False) -> None:
        # With two items picked, the next click places the dimension (T4.2.1), unless
        # it completes an arc and its two end points (arc length, T4.1, D515).
        hit = self.pick(pos) if len(self.dim_picks) < 3 else None
        if hit is not None and not self._dimension_may_pick(hit):
            hit = self.pick(pos, {hit})  # TR418: that kind of point is off, take the curve
        if len(self.dim_picks) == 2:
            snap = self._snap_at(pos)
            if snap.kind == "point" and snap.target in self.edit.sketch.entities:
                hit = snap.target
            if hit is None or not arc_length_started(self.edit.sketch, self.dim_picks, hit):
                hit = None
        elif len(self.dim_picks) < 2 and (hit is None or hit in self.edit.sketch.entities):
            snap = self._snap_at(pos)
            if snap.kind == "midpoint" and self.options.dimension_middles:
                middle = self._dimension_midpoint(snap)  # TR418 (D953)
                if middle is not None:
                    if middle not in self.dim_picks:
                        self.dim_picks.append(middle)
                    self.changed()
                    return
            if (snap.model is not None or snap.model_curve is not None) and hit is None:
                # A part point or edge: measure to a fixed construction copy (D116 item 3).
                self.edit.checkpoint()
                ref = self._model_copy(snap)
                if ref not in self.dim_picks:
                    self.dim_picks.append(ref)
                self.changed()
                return
            allowed = (snap.kind == "point" and self.options.dimension_ends) or (
                snap.kind == "center" and self.options.dimension_centres
            )  # TR418: the Sketch preferences can turn either off
            if allowed and snap.target in self.edit.sketch.entities:
                hit = snap.target  # the highlighted point wins over a curve (D434)
        if hit is not None and hit in self.edit.sketch.entities:
            if hit not in self.dim_picks and len(self.dim_picks) < 3:
                self.dim_picks.append(hit)
                if shift and isinstance(self.edit.sketch.entities[hit], Circle | Arc):
                    # Shift picks the near or far side from the click (T4.3.3, D516).
                    self.dim_clicks[hit] = self.to_sketch(pos)
                else:
                    self.dim_clicks.pop(hit, None)
            self.update()
            return
        if hit is not None and self._dimension(hit) is not None:
            # A label: drag it, or click it to type a new value (T4.4.1, T4.4.2).
            self.selection = [hit]
            self.selection_changed.emit()
            self._label_drag = {"id": hit, "press": pos, "moved": False, "click": True}
            self.update()
            return
        edge = self.reference_line_at(pos) if hit is None and len(self.dim_picks) < 2 else None
        if edge is not None:
            # A part edge: measure to a fixed construction copy of it (D113).
            depth = self.edit.undo_depth
            before = set(self.edit.sketch.entities)
            self.edit.checkpoint()
            lid = self.edit.reference_line(*edge)
            if lid in before:
                self.edit.drop_if_unchanged()  # a copy already there is reused
            else:
                self.dim_copies[lid] = depth
            self.dim_picks.append(lid)
            self.changed()
            return
        if not self.dim_picks:
            return
        place = self.to_sketch(pos)
        sides = shift_sides(self.edit.sketch, self.dim_picks, self.dim_clicks)
        self.dim_clicks = {}
        sticky = sticky_diameter(self.edit.sketch, self.dim_picks, self.diameter_axis)
        self.dim_picks = sticky or centres_for_distance(self.edit.sketch, self.dim_picks)
        dtype = (
            "doubled_distance"
            if sticky
            else smart_dimension(self.edit.sketch, self.dim_picks, place)
        )
        dtype = locked_type(dtype, self.dim_lock)  # TR111 item 1 (D1707)
        self.dim_lock = None
        if dtype is None:
            self.status_message.emit(strings.DIMENSION_NOT_POSSIBLE)
            self._drop_copies()
            self.dim_picks = []
            self.update()
            return
        ids = list(self.dim_picks)
        self.dim_picks = []
        self.dim_copies = {}  # the dimension uses them now
        self.dim_preview = None
        depth = self.edit.undo_depth
        self.edit.checkpoint()
        # The text stays where it was placed (T4.2.1, D150).
        dim = self.edit.add_dimension(dtype, ids, None, place, keep_label=True)
        if dtype == "distance" and sides:
            for rid, side in sides.items():
                self.edit.set_measure(dim.id, rid, side)
            self.edit.set_label(dim.id, place)
        self.last_dimension = dim.id
        if dim.type == "doubled_distance" and len(dim.entities) == 2:
            self.diameter_axis = dim.entities[1]  # TR361: diameter mode stays on
            self.status_message.emit(strings.DIAMETER_MODE_ON)
        over = self.edit.over_defines(dim.id)
        made_reference = over and self.options.over_define is OverDefine.REFERENCE
        made_reference = made_reference or self.reference_mode  # TR111: measure only
        if made_reference:
            self.edit.set_driving(dim.id, False)
        self.changed()
        self.dimension_focus.emit()
        if made_reference:
            # A reference dimension only measures, so there is no value to type (T11.5).
            self.status_message.emit(strings.DIMENSION_MADE_REFERENCE)
            return
        if over:
            self.ask_over_define(dim.id, depth)
            return
        self.edit_dimension(dim.id, new_depth=depth)

    def toggle_dimension_lock(self) -> bool:
        """While a point to point dimension follows the cursor, lock its type
        (horizontal, vertical or aligned) so moving the cursor no longer changes it, or
        unlock it again (TR111 item 1, D1707). False when nothing is being placed."""
        preview = self.dim_preview
        if not self.dimension_mode or not self.dim_picks or preview is None:
            return False
        if self.dim_lock is not None:
            self.dim_lock = None
            self.status_message.emit(strings.DIMENSION_UNLOCKED)
            return True
        if preview.type not in LOCKABLE:
            return False
        self.dim_lock = preview.type
        self.status_message.emit(
            strings.DIMENSION_LOCKED.format(kind=strings.DIMENSION_KINDS[preview.type])
        )
        self.update()
        return True

    # Over define prompt (T1.4.4) ---------------------------------------------------------

    def ask_over_define(self, did: str, depth: int) -> None:
        """Ask beside the new dimension whether it becomes a reference dimension.

        The question is a small frame in the sketch, not a modal dialog, so the
        sketch stays visible. Make Reference turns it into a reference dimension;
        Keep Driving opens the value box; Escape removes the new dimension.
        """
        self._close_prompt()
        prompt = OverDefinePrompt(self)
        prompt.make_reference.connect(lambda: self._prompt_reference(did))
        prompt.keep_driving.connect(lambda: self._prompt_keep(did, depth))
        prompt.cancelled.connect(lambda: self._prompt_cancel(depth))
        prompt.adjustSize()
        x, y = beside(self.label_rect(did), prompt.width(), prompt.height(), *self._size())
        prompt.open_at(x, y)
        self.over_prompt = prompt
        self.status_message.emit(strings.OVER_DEFINE_QUESTION)

    def _size(self) -> tuple[int, int]:
        return self.width(), self.height()

    def _prompt_reference(self, did: str) -> None:
        self._close_prompt()
        self.run(lambda: self.edit.set_driving(did, False))
        self.dimension_focus.emit()
        self.status_message.emit(strings.DIMENSION_MADE_REFERENCE)

    def _prompt_keep(self, did: str, depth: int) -> None:
        self._close_prompt()
        self.edit_dimension(did, new_depth=depth)

    def _prompt_cancel(self, depth: int) -> None:
        self._close_prompt()
        self.edit.rollback(depth)
        self.last_dimension = None
        self.changed()
        self.dimension_focus.emit()

    def _close_prompt(self) -> None:
        prompt = getattr(self, "over_prompt", None)
        if prompt is not None:
            self.over_prompt = None
            prompt.hide()
            prompt.deleteLater()
            self.setFocus()

    # Preview and label drag (T4.2.1, T4.4.2) -------------------------------------------

    def _update_preview(self, pos: QPointF) -> None:
        """The dimension follows the cursor once its items are picked (T4.2.1)."""
        before = self.dim_preview
        self.dim_preview = None
        over_item = self.hover is not None and self.hover in self.edit.sketch.entities
        completes = (
            over_item
            and len(self.dim_picks) == 2
            and arc_length_started(self.edit.sketch, self.dim_picks, str(self.hover))
        )
        if self.dim_picks and (len(self.dim_picks) >= 2 or not over_item) and not completes:
            sides = shift_sides(self.edit.sketch, self.dim_picks, self.dim_clicks)
            self.dim_preview = preview_dimension(
                self.edit.sketch,
                self.dim_picks,
                self.to_sketch(pos),
                sides,
                getattr(self, "diameter_axis", None),
                self.dim_lock,
            )
        if before is not None or self.dim_preview is not None:
            self.dimension_focus.emit()

    def _move_label(self, pos: QPointF) -> None:
        drag = self._label_drag
        assert drag is not None
        press = drag["press"]
        assert isinstance(press, QPointF)
        if not drag["moved"]:
            if (pos - press).manhattanLength() < DRAG_PX:
                return
            self.edit.checkpoint()
            drag["moved"] = True
        self.edit.set_label(str(drag["id"]), self.to_sketch(pos))
        self.update()

    def _finish_label_drag(self) -> None:
        drag = self._label_drag
        assert drag is not None
        self._label_drag = None
        self._press = None
        did = str(drag["id"])
        if drag["moved"]:
            self.changed()  # one step on the sketch's undo list
        elif drag["click"]:
            self.edit_dimension(did)

    def label_at(self, did: str) -> QPointF:
        """Centre of a dimension's text on screen."""
        return self.label_rect(did).center()

    # Click drag in drawing tools (T1.1.3) ------------------------------------------------

    def _set_tool_keys(self, modifiers: Qt.KeyboardModifier) -> None:
        """Hand Shift to the tool (square rectangles, T2.3.2), and Ctrl to tools that
        want it."""
        if self.tool is not None:
            self.tool.shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
            if hasattr(self.tool, "ctrl"):  # Convert: Ctrl click takes a loop (TR118)
                self.tool.ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)

    def _cancel_tool(self) -> bool:
        """Escape, double click or right click in a tool. A tool that finishes a shape
        on cancel (the spline, P2.8 item 10) reports it, so the sketch refreshes."""
        assert self.tool is not None
        tool = self.tool
        ended = tool.cancel()
        take = getattr(tool, "take_changed", None)
        if take is not None and take():
            if self.edit.mirror_axis is not None:
                self.status_message.emit(tool_text.MIRROR_SKIPPED)  # splines are not mirrored
            self.changed()
        return ended

    # Dynamic mirror (P2.8 item 4, D514) -------------------------------------------------

    def start_dynamic_mirror(self) -> bool:
        """Turn dynamic mirror on about the one selected line, or ask for a line.

        Returns True when it is on now; False while waiting for the line's click.
        """
        sk = self.edit.sketch
        picked = [i for i in self.selection if i in sk.entities]
        if len(picked) == 1 and isinstance(sk.entities[picked[0]], Line):
            self.set_dynamic_mirror(picked[0])
            return True
        self.mirror_pick = True
        self.status_message.emit(tool_text.MIRROR_PICK)
        return False

    def set_dynamic_mirror(self, axis: str | None) -> None:
        """Mirror new shapes about line ``axis``; None turns dynamic mirror off."""
        was = self.edit.mirror_axis is not None
        self.mirror_pick = False
        self.edit.mirror_axis = axis
        if axis is not None:
            self.status_message.emit(tool_text.MIRROR_ON)
        elif was:
            self.status_message.emit(tool_text.MIRROR_OFF)
        self.mirror_changed.emit(axis is not None)
        self.update()

    def set_show_curvature(self, on: bool) -> None:
        """Draw curvature combs on the splines, or stop (view state only, D514)."""
        if self.show_curvature == on:
            return
        self.show_curvature = on
        self.curvature_toggled.emit(on)
        self.update()

    def _pick_mirror_line(self, pos: QPointF) -> None:
        hit = self.pick(pos)
        if hit is not None and isinstance(self.edit.sketch.entities.get(hit), Line):
            self.set_dynamic_mirror(hit)
        else:
            self.status_message.emit(tool_text.MIRROR_NOT_LINE)

    def _tool_note(self) -> None:
        """Show the status note a Phase 2 tool left (P2.8: what a trim removed)."""
        take = getattr(self.tool, "take_message", None)
        note = (take() if take is not None else "") or self.edit.take_note()
        if note:
            self.status_message.emit(note)

    def _release_tool(self, event: QMouseEvent) -> None:
        """Press, drag, release places the next point like a second click does."""
        press = self._tool_press
        self._tool_press = None
        pos = event.position()
        if self.tool is None or press is None or not self.tool.busy:
            return
        release = getattr(self.tool, "release", None)
        if release is not None:
            # Tools that act on the release themselves (drag trim, P2.8 item 2).
            moved = (pos - press).manhattanLength() >= DRAG_PX
            if release(self._snap_at(pos), moved):
                self.changed()
            self._tool_note()
            self.update()
            return
        if (pos - press).manhattanLength() < DRAG_PX:
            return
        self._ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        self._set_tool_keys(event.modifiers())
        if self.tool.click(self._snap_at(pos)):
            self.changed()
            self.edit.skip_next = False
        self.snap = self.tool.cursor
        self.values.auto_open()
        self.update()

    def edit_dimension(self, did: str, new_depth: int | None = None) -> None:
        """Open the value box beside a dimension label (T4.2.2).

        ``new_depth`` is the sketch undo depth before a dimension that was just
        placed; Escape then removes that dimension again (T4.2.4).
        """
        dim = self._dimension(did)
        if dim is None:
            return
        self._commit_editor()
        if not dim.driving:
            # Reference dimensions update but cannot be typed (T1.4.4).
            self.status_message.emit(strings.DIMENSION_VALUE_TIP)
            return
        rect = self.label_rect(did)
        box = ValueBox(dim.param.expr, self, dimension_kind(dim.type), self.units, self.variables)
        box.accepted.connect(self._commit_editor)
        box.rejected.connect(self._cancel_editor)
        box.applied.connect(lambda: self._commit_editor(close=False))
        box.adjustSize()
        x, y = beside(rect, box.width(), box.height(), self.width(), self.height())
        box.open_at(x, y)
        self.value_box = box
        self.editor = box.edit
        self._editing_dim = did
        self._new_dim_depth = new_depth
        self.dimension_focus.emit()

    def label_rect(self, did: str) -> QRectF:
        """Screen rectangle of a dimension's text, worked out without painting."""
        dim = self._dimension(did)
        if dim is not None:
            try:
                anchor, _segments = self._dimension_geometry(dim)
            except (KeyError, TypeError, ZeroDivisionError):
                pass
            else:
                return self._label_box(
                    anchor, self._dimension_text(dim), QFontMetrics(self._label_font())
                )
        return self._labels.get(did, QRectF(self.width() / 2, self.height() / 2, 80, 20))

    def _label_font(self) -> QFont:
        return type_font(Role.BODY, self.font())

    @staticmethod
    def _label_box(anchor: QPointF, text: str, metrics: QFontMetrics) -> QRectF:
        w = metrics.horizontalAdvance(text) + 8
        h = metrics.height() + 2
        return QRectF(anchor.x() - w / 2, anchor.y() - h / 2, w, h)

    def _dimension(self, did: str) -> Dimension | None:
        return next((d for d in self.edit.sketch.dimensions if d.id == did), None)

    def _commit_editor(self, close: bool = True) -> bool:
        """Apply the value box. Returns False and keeps it open when the value is wrong.

        With ``close`` False the value is applied and the box stays open (rebuild arrow).
        """
        if self.editor is None or self._editing_dim is None:
            return True
        text = self.editor.text().strip()
        error = self.apply_dimension_text(self._editing_dim, text)
        if error:
            self.editor.setToolTip(error)
            self.editor.setProperty("error", True)
            self.editor.style().unpolish(self.editor)
            self.editor.style().polish(self.editor)
            return False
        if close:
            self._close_editor()
        else:
            self._new_dim_depth = None  # applied: no longer a dimension to drop on Escape
        return True

    def apply_dimension_text(self, did: str, text: str) -> str:
        """Set a driving dimension from typed text (value box or Dimension panel).

        Returns "" when it applied, or the message saying what is wrong.
        """
        dim = self._dimension(did)
        if dim is None or not dim.driving or text == dim.param.expr:
            return ""
        try:
            value = evaluate(text, dimension_kind(dim.type), self.units, self.variables)
        except ExpressionError as exc:
            self.status_message.emit(str(exc))
            return str(exc)
        if dim.type in ("horizontal_distance", "vertical_distance") and value <= 0:
            # TR111 item 4 (D1312): zero lines the points up; a negative value puts the
            # second item on the other side, at the size typed.
            if value < 0:
                text = text.strip()[1:].strip() if _plain_negative(text) else f"-({text})"
                value = -value
                flip = _side_of(self.edit.sketch, dim)
                keep = self.options.keep_proportions

                def change() -> None:
                    target = self._dimension(did)
                    if target is not None:
                        target.side = -flip
                    self.edit.set_dimension(did, Param(text, value), keep)

                self.run(change)
                self.dimension_focus.emit()
                return ""
        elif value <= 0 and dim.type != "angle":
            self.status_message.emit(strings.DIMENSION_POSITIVE)
            return strings.DIMENSION_POSITIVE
        if dim.type == "angle" and not 0 < value < math.pi - 1e-9:
            # The solver measures 0 to 180 degrees; other values would show a size
            # the geometry does not have.
            self.status_message.emit(strings.DIMENSION_ANGLE_RANGE)
            return strings.DIMENSION_ANGLE_RANGE
        keep = self.options.keep_proportions  # TR119 (D938)
        self.run(lambda: self.edit.set_dimension(did, Param(text, value), keep))
        self.dimension_focus.emit()
        return ""

    def apply_shape_value(self, change: Callable[[], bool]) -> bool:
        """Run a typed parameter change (T7.3) as one undoable step.

        ``change`` goes through the solver and returns False when relations or
        dimensions hold the value; then the sketch goes back to how it was.
        """
        depth = self.edit.undo_depth
        self.edit.checkpoint()
        if not change():
            self.edit.rollback(depth)
            self.changed()
            return False
        self.changed()
        return True

    def toggle_line_arc(self) -> bool:
        """The Switch Line and Arc command (T2.1.3, T12.5). False when the Line tool has
        no segment to continue."""
        tool = self.tool
        toggle = getattr(tool, "toggle_arc", None)
        if toggle is None or not toggle():
            self.status_message.emit(strings.LINE_ARC_NONE)
            return False
        arc = bool(getattr(tool, "arc_mode", False))
        self.status_message.emit(strings.LINE_ARC_ON if arc else strings.LINE_ARC_OFF)
        self.update()
        return True

    def set_dimension_driving(self, did: str, driving: bool) -> bool:
        """Make a dimension driving or a reference, as one undoable step (T4.2.5).

        Driving is refused when it would over define the sketch; the status bar says so.
        """
        depth = self.edit.undo_depth
        self.edit.checkpoint()
        if not self.edit.set_driving(did, driving):
            self.edit.rollback(depth)
            self.status_message.emit(strings.DIMENSION_STAYS_REFERENCE)
            self.changed()
            return False
        self.changed()
        self.dimension_focus.emit()
        return True

    def dimension_value_text(self, dim: Dimension) -> str:
        """The size of ``dim`` as shown in its label, without brackets or signs."""
        value = dim.param.value
        if dim.type == "angle":
            return f"{math.degrees(value):.2f}deg"
        unit = "in" if self.units is UnitSystem.IN else "mm"
        return f"{plain_length(value, self.units)}{unit}"  # goes in a field

    def _cancel_editor(self) -> None:
        """Escape or the cross: close the box; a just placed dimension goes away (T4.2.4)."""
        depth = self._new_dim_depth
        self._close_editor()
        if depth is not None:
            self.edit.rollback(depth)
            self.changed()

    def _close_editor(self) -> None:
        if self.value_box is not None:
            self.value_box.hide()
            self.value_box.deleteLater()
        self.value_box = None
        self.editor = None
        self._editing_dim = None
        self._new_dim_depth = None
        self.setFocus()
        self.dimension_focus.emit()

    # Keys -----------------------------------------------------------------------------

    def event(self, event: QEvent) -> bool:
        """Take undo, redo and delete from the window while the sketch has focus."""
        if (
            event.type() == QEvent.Type.ShortcutOverride
            and isinstance(event, QKeyEvent)
            and (
                _sketch_key(event)
                or (self.editor is not None and _is_return(event))
                or (_is_return(event) and self._tool_wants_enter())
                or self._typing_key(event)
            )
        ):
            event.accept()
            return True
        return super().event(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Escape, Delete, undo and redo inside the sketch."""
        if event.key() == Qt.Key.Key_Escape:
            if self.mirror_pick:
                self.set_dynamic_mirror(None)  # Escape cancels picking the mirror line
            elif self.over_prompt is not None:
                self.over_prompt.cancelled.emit()
            elif self.editor is not None:
                self._cancel_editor()
            elif self.tool is not None:
                if self._cancel_tool():
                    self.set_tool(None)
            elif self.dimension_mode:
                if self.dim_picks:
                    self._drop_copy(self.dim_picks.pop())  # Esc drops the last pick (T4.1)
                    self.dim_preview = None
                    self.dimension_focus.emit()
                else:
                    self.set_tool(None)
            elif not self.selection and self.options.escape_exit:
                self.exit_requested.emit()  # TR120 (D941): nothing left to cancel
            else:
                self.selection = []
                self.selection_changed.emit()
            self.update()
        elif self.editor is None and _is_return(event) and self.values.finish():
            pass  # Enter again finishes a shape with a typed size (T15.6)
        elif self.editor is None and _is_return(event) and self.tool_enter():
            pass  # Enter applies a tool's typed values (T15.5, TR1.7)
        elif self.editor is None and self._typing_key(event):
            self.values.type_key(event.text())  # a digit opens the value box (T15.5, T15.6)
        elif event.key() == Qt.Key.Key_Tab and self.tool is not None:
            # TR231 (D1309): skip the automatic relations of the next click, or keep them.
            self.edit.skip_next = not self.edit.skip_next
            self.status_message.emit(
                strings.SKIP_RELATIONS_ON if self.edit.skip_next else strings.SKIP_RELATIONS_OFF
            )
        elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selection()
        elif self.tool is None and self.selection and event.key() in _NUDGE:
            # TR293 (D2209): arrows nudge the picked items (Shift: a tenth of the step).
            dx, dy = _NUDGE[Qt.Key(event.key())]
            shift = event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            step = self.nudge_step / (10 if shift else 1)
            self.nudge(dx * step, dy * step)
        elif event.key() == Qt.Key.Key_Tab and self._point_picked():
            self.pick_next_point()  # TR293 (D2209): Tab picks the next sketch point
        elif event.matches(QKeySequence.StandardKey.Copy):
            self.copy_selection()  # TR3.1
        elif event.matches(QKeySequence.StandardKey.Paste):
            self.start_paste()
        elif event.matches(QKeySequence.StandardKey.Undo):
            self.undo()
        elif event.matches(QKeySequence.StandardKey.Redo) or (
            event.key() == Qt.Key.Key_Y and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self.redo()
        else:
            super().keyPressEvent(event)

    #: How far one arrow key press moves picked sketch items, in mm (TR293, D2209).
    nudge_step = 1.0

    def nudge(self, dx: float, dy: float) -> bool:
        """Move the picked points and curves by ``dx``, ``dy`` mm as a drag would, keeping
        relations: one sketch undo step (TR293, D2209). True when anything moved."""
        from fdcad.core.sketch.model import entity_points

        sk = self.edit.sketch
        points: set[str] = set()
        for item in self.selection:
            ent = sk.entities.get(item)
            if ent is not None:
                points.update(entity_points(ent))
        if not points:
            return False
        targets = {p: (sk.xy(p)[0] + dx, sk.xy(p)[1] + dy) for p in points}
        self.edit.checkpoint()
        moved = self.edit.drag_to(targets)
        self.changed()
        return moved

    def _point_picked(self) -> bool:
        """True when the selection holds a sketch point and no tool is active."""
        from fdcad.core.sketch.model import Point

        sk = self.edit.sketch
        return self.tool is None and any(
            isinstance(sk.entities.get(i), Point) for i in self.selection
        )

    def pick_next_point(self) -> str | None:
        """Pick the sketch point after the one picked now, in drawing order, or the first
        (TR293, D2209). Returns its id."""
        from fdcad.core.sketch.model import Point

        sk = self.edit.sketch
        ids = [e.id for e in sk.entities.values() if isinstance(e, Point)]
        if not ids:
            return None
        current = next((i for i in reversed(self.selection) if i in ids), None)
        nxt = ids[(ids.index(current) + 1) % len(ids)] if current is not None else ids[0]
        self.selection = [nxt]
        self.selection_changed.emit()
        self.update()
        return nxt

    def focusNextPrevChild(self, next_: bool) -> bool:  # noqa: N802  (Qt override)
        """Tab stays in the sketch while a tool is active (TR231): it skips relations; and
        while a point is picked (TR293): it picks the next point."""
        if self.tool is not None or self._point_picked():
            return False
        return super().focusNextPrevChild(next_)

    def _tool_wants_enter(self) -> bool:
        """True when the tool's Enter step has something to apply (TR1.7)."""
        ready = getattr(self.tool, "enter_ready", None)
        return bool(ready is not None and ready())

    def set_dimension_name(self, did: str, name: str) -> str:
        """Name dimension ``did`` for formulas (TR32), one sketch undo step. Returns why
        the name cannot be used, or "" when it was set ("" also clears it)."""
        from fdcad.core.equations.engine import VARIABLE_NAME

        dim = self._dimension(did)
        if dim is None:
            return ""
        clean = name.strip()
        if clean and not VARIABLE_NAME.match(clean):
            return strings.DIMENSION_NAME_BAD
        from fdcad.core.units.expressions import reserved_name

        clash = reserved_name(clean) if clean else None
        if clash:  # TR310 (D919)
            return clash
        others = [d for d in self.edit.sketch.dimensions if d.id != did]
        if clean and any(clean in (d.id, d.name) for d in others):
            return strings.DIMENSION_NAME_TAKEN.format(name=clean)
        self.edit.checkpoint()
        dim.name = clean or None
        self.changed()
        return ""

    def tool_enter(self) -> bool:
        """Enter with no value box: a tool with an ``enter`` step applies its typed
        values and keeps going. False when the tool has nothing to apply."""
        enter = getattr(self.tool, "enter", None)
        if enter is None or self.values.is_open():
            return False
        done = enter()
        if done is None:
            return False
        if done:
            self.changed()
        self._tool_note()
        self.tool_values_changed.emit()
        self.update()
        return True

    def _typing_key(self, event: QKeyEvent) -> bool:
        """True for a typed digit, minus, dot or = that opens the tool's value box."""
        from fdcad.ui.viewport.value_labels import starts_typing

        if self.tool is None or self.editor is not None or self.values.is_open():
            return False
        if _is_return(event):
            return bool(self.tool.locks)
        return starts_typing(event.text(), event.modifiers()) and self.values.wants_typing()

    # Painting -------------------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Draw everything."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = self.palette_colors
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor(pal.viewport_top))
        gradient.setColorAt(1, QColor(pal.viewport_bottom))
        painter.fillRect(self.rect(), QBrush(gradient))
        if self.options.show_grid:
            self._paint_grid(painter)
        self._paint_origin(painter)
        self._paint_pictures(painter)
        self._paint_reference(painter)
        if self.shade_regions:
            self._paint_all_regions(painter)  # TR335
        self._paint_region(painter)  # TR39
        self._paint_sketch(painter)
        self._paint_handles(painter)  # TR43
        if self.show_curvature:
            self._paint_combs(painter)
        if self.mark_open_ends:
            self._paint_open_ends(painter)  # TR341
        if self.mark_crossings:
            self._paint_crossings(painter)  # TR238
        self._paint_relations(painter)
        self._paint_dimensions(painter)
        self._paint_dimension_preview(painter)
        self._paint_preview(painter)
        if self._box is not None:
            a, b = self._box
            accent = QColor(self.palette_colors.accent)
            painter.setPen(QPen(accent, 1, Qt.PenStyle.DashLine))
            accent.setAlpha(40)
            painter.setBrush(accent)
            painter.drawRect(QRectF(a, b).normalized())
        painter.end()

    def picture_image(self, block: str) -> QImage | None:
        """The decoded image of an embedded block (cached), or None (P2.9)."""
        cache: dict[str, QImage] = self.__dict__.setdefault("_picture_images", {})
        if block not in cache:
            raw = self.edit.blocks.get(block)
            image = QImage()
            if isinstance(raw, dict):
                try:
                    image = QImage.fromData(block_bytes(raw))
                except ValueError:
                    image = QImage()
            cache[block] = image
        image = cache[block]
        return None if image.isNull() else image

    def picture_pixels(self, block: str) -> Any:
        """The RGBA pixels of an embedded picture as a numpy array (rows from the top),
        or None (TR116 item 2, D1711)."""
        import numpy as np

        image = self.picture_image(block)
        if image is None:
            return None
        argb = image.convertToFormat(QImage.Format.Format_RGBA8888)
        h, w = argb.height(), argb.width()
        raw = np.frombuffer(argb.constBits(), dtype=np.uint8)
        return raw.reshape(h, argb.bytesPerLine())[:, : 4 * w].reshape(h, w, 4).copy()

    def see_through(self, block: str, image: QImage, colour: str, tolerance: float) -> QImage:
        """``image`` with the pixels near ``colour`` made see through (cached, TR116)."""
        import numpy as np

        from fdcad.core.sketch.picture import clear_mask

        cache: dict[tuple[str, str, float], QImage] = self.__dict__.setdefault("_see_through", {})
        key = (block, colour, round(tolerance, 4))
        if key not in cache:
            argb = image.convertToFormat(QImage.Format.Format_RGBA8888)
            h, w = argb.height(), argb.width()
            raw = np.frombuffer(argb.constBits(), dtype=np.uint8)
            pixels = raw.reshape(h, argb.bytesPerLine())[:, : 4 * w].reshape(h, w, 4).copy()
            pixels[clear_mask(pixels, colour, tolerance), 3] = 0
            out = QImage(pixels.data, w, h, 4 * w, QImage.Format.Format_RGBA8888).copy()
            cache[key] = out
        return cache[key]

    def _paint_pictures(self, painter: QPainter) -> None:
        """Sketch pictures under the geometry, with their transparency (P2.9 item 2)."""
        for pic in self.edit.sketch.pictures:
            image = self.picture_image(pic.block)
            if image is None:
                continue
            if pic.clear_colour:  # TR116: one colour shown see through
                image = self.see_through(pic.block, image, pic.clear_colour, pic.clear_tolerance)
            ll, lr, ur, ul = (self.to_screen(c) for c in pic.corners())
            if pic.flip_h:
                ll, lr, ur, ul = lr, ll, ul, ur
            if pic.flip_v:
                ll, lr, ur, ul = ul, ur, lr, ll
            w, h = image.width(), image.height()
            transform = QTransform(
                (ur.x() - ul.x()) / w,
                (ur.y() - ul.y()) / w,
                (ll.x() - ul.x()) / h,
                (ll.y() - ul.y()) / h,
                ul.x(),
                ul.y(),
            )
            painter.save()
            painter.setTransform(transform, combine=True)
            painter.setOpacity(1.0 - pic.transparency)
            painter.drawImage(0, 0, image)
            painter.restore()

    def _grid_step(self) -> float:
        spacing = getattr(self, "grid_spacing", None)
        if isinstance(spacing, float) and spacing > 0:  # the part's own spacing (TR102)
            minor = max(int(getattr(self, "grid_minor", 1) or 1), 1)
            step = spacing / minor
            while step * self.scale < 6:  # never denser than 6 px
                step *= 2
            return step
        target = 40.0 / self.scale  # about 40 px between lines
        power = 10.0 ** math.floor(math.log10(target))
        for m in (1, 2, 5, 10):
            if m * power >= target:
                return m * power
        return 10 * power

    def _paint_polar_grid(self, painter: QPainter, step: float) -> None:
        """Rings round the origin and spokes from it (TR238, D1014)."""
        from fdcad.ui.sketch_tools.polar_grid import rings_and_spokes

        w, h = self.width(), self.height()
        corners = [self.to_sketch(QPointF(x, y)) for x, y in ((0, 0), (w, 0), (0, h), (w, h))]
        rings, spokes, far = rings_and_spokes(corners, step, self.options.polar_angle)
        centre = self.to_screen((0.0, 0.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for radius in rings:
            r = radius * self.scale
            painter.drawEllipse(centre, r, r)
        for a in spokes:
            painter.drawLine(centre, self.to_screen((far * math.cos(a), far * math.sin(a))))

    def _paint_grid(self, painter: QPainter) -> None:
        step = self._grid_step()
        if self.options.grid_kind == "polar":
            painter.setPen(QPen(QColor(self.palette_colors.grid), 1))
            self._paint_polar_grid(painter, step)
            return
        x0, y1 = self.to_sketch(QPointF(0, 0))
        x1, y0 = self.to_sketch(QPointF(self.width(), self.height()))
        painter.setPen(QPen(QColor(self.palette_colors.grid), 1))
        x = math.floor(x0 / step) * step
        while x <= x1:
            sx = self.to_screen((x, 0)).x()
            painter.drawLine(QPointF(sx, 0), QPointF(sx, self.height()))
            x += step
        y = math.floor(y0 / step) * step
        while y <= y1:
            sy = self.to_screen((0, y)).y()
            painter.drawLine(QPointF(0, sy), QPointF(self.width(), sy))
            y += step

    def _paint_origin(self, painter: QPainter) -> None:
        """Short red and green marks for the sketch X and Y directions at the origin."""
        origin = self.to_screen((0, 0))
        x_mark, y_mark = QColor(self.palette_colors.axis_x), QColor(self.palette_colors.axis_y)
        x_mark.setAlpha(170)
        y_mark.setAlpha(170)
        painter.setPen(QPen(x_mark, 1))
        painter.drawLine(origin, origin + QPointF(30, 0))
        painter.setPen(QPen(y_mark, 1))
        painter.drawLine(origin, origin - QPointF(0, 30))

    def _paint_reference(self, painter: QPainter) -> None:
        if self.model_index is not None and self.options.model_snaps:
            # Projected part edges (T1.2.2): thin and dotted under the outline.
            pen = QPen(QColor(self.palette_colors.sketch_reference), 1.0, Qt.PenStyle.DotLine)
            painter.setPen(pen)
            for poly in self.model_index.geometry.polylines:
                painter.drawPolyline([self.to_screen(p) for p in poly])
        if hasattr(self.tool, "curve_sources"):
            # Curve features Convert can copy (D517): dotted, like projected part edges.
            painter.setPen(
                QPen(QColor(self.palette_colors.sketch_reference), 1.2, Qt.PenStyle.DotLine)
            )
            for curve in self.curve_sources:
                for poly in curve.polylines:
                    painter.drawPolyline([self.to_screen(p) for p in poly])
        painter.setPen(QPen(QColor(self.palette_colors.sketch_reference), 1.5))
        for line in self.reference:
            pts = [self.to_screen(p) for p in line]
            for a, b in itertools.pairwise(pts):
                painter.drawLine(a, b)

    def _color(self, eid: str, conflicting: set[str]) -> QColor:
        pal = self.palette_colors
        if eid in self.selection or eid in self.dim_picks or eid in self._related():
            return self.selected_color()
        if eid == self.hover:
            return self.hover_color()
        if eid in conflicting:
            return QColor(pal.sketch_over)
        if eid in self.edit.defined:
            return QColor(pal.sketch_full)
        return QColor(pal.sketch_under)

    def preview_color(self) -> QColor:
        """Drawing tool previews and snap marks: the theme's selection colour (U1.6)."""
        return QColor(self.palette_colors.selection)

    def selected_color(self) -> QColor:
        """Selected items: the theme accent (T1.4.1, D111)."""
        return QColor(self.palette_colors.accent)

    def hover_color(self) -> QColor:
        """Hovered items: the theme's pre-selection colour, as in the 3D view, which reads
        at 3:1 on the view in every theme (TR292 item 2, D769). It was a lighter accent,
        too faint on the light themes."""
        return QColor(self.palette_colors.preselection)

    def _status_of(self, eid: str, conflicting: set[str]) -> str:
        """``under``, ``full`` or ``over``: drawn by line and point shape too (TR292)."""
        if eid in conflicting:
            return "over"
        return "full" if eid in self.edit.defined else "under"

    def _related(self) -> set[str]:
        """Entities of the selected relations, drawn highlighted (T3.3.2)."""
        rels = self.edit.sketch.relations
        return {e for i in self.selected_relations() for e in rels[i].entities}

    def _paint_sketch(self, painter: QPainter) -> None:
        sk = self.edit.sketch
        conflicting = self._status.conflicting
        painter.setBrush(Qt.BrushStyle.NoBrush)
        halo = self.selected_color()
        halo.setAlpha(70)
        for e in sk.entities.values():
            if isinstance(e, Point) or self.hidden_construction(e):
                continue
            if e.id in self.selection or e.id in self.dim_picks:
                # The accent is close to the under defined blue, so a soft band marks the
                # selection as well (D119).
                band = QPen(halo, 6.0)
                band.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(band)
                self._draw_curve(painter, e)
            from fdcad.ui.sketch_tools.status_style import line_style

            width, style = line_style(
                self._status_of(e.id, conflicting), e.construction, e.id in self.selection
            )
            color = self._color(e.id, conflicting)
            if sk.layers:  # TR389: the layer's own colour and line style
                from fdcad.core.sketch.layers import layer_style

                layer = layer_style(sk, e.id)
                plain = e.id not in self.selection and e.id != self.hover
                if layer is not None and plain and e.id not in conflicting:
                    if layer.get("colour"):
                        color = QColor(str(layer["colour"]))
                    if layer.get("style") == "dashed":
                        style = Qt.PenStyle.DashLine
            pen = QPen(color, width * self.line_scale)
            pen.setStyle(style)
            painter.setPen(pen)
            self._draw_curve(painter, e)
        for pid, mark in self.point_marks().items():
            e = sk.point(pid)
            color = self._color(pid, conflicting)
            big = pid in self.selection or pid == self.hover
            p = self.to_screen((e.x, e.y))
            if mark == "plus":
                # Circle and arc centres are a plus mark (T2.4.1).
                arm = (5.0 if big else 4.0) * self.line_scale
                painter.setPen(QPen(color, (1.6 if big else 1.2) * self.line_scale))
                painter.drawLine(p - QPointF(arm, 0), p + QPointF(arm, 0))
                painter.drawLine(p - QPointF(0, arm), p + QPointF(0, arm))
                continue
            if mark == "corner":  # a kept corner: a small x (TR105)
                arm = (4.0 if big else 3.0) * self.line_scale
                painter.setPen(QPen(color, (1.6 if big else 1.2) * self.line_scale))
                painter.drawLine(p - QPointF(arm, arm), p + QPointF(arm, arm))
                painter.drawLine(p - QPointF(arm, -arm), p + QPointF(arm, -arm))
                continue
            from fdcad.ui.sketch_tools.status_style import POINT_SHAPES

            shape = POINT_SHAPES[self._status_of(pid, conflicting)]
            size = (5.0 if big else 3.5) * self.line_scale
            half = size / 2 + 0.5
            if shape == "ring":  # under defined: hollow, so it reads without colour (TR292)
                painter.setPen(QPen(color, 1.3 * self.line_scale))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(p, half, half)
                continue
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            if shape == "square":  # over defined
                painter.drawRect(QRectF(p.x() - half, p.y() - half, 2 * half, 2 * half))
            else:
                painter.drawEllipse(p, half, half)
            painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def _draw_curve(self, painter: QPainter, e: Curve) -> None:
        sk = self.edit.sketch
        if isinstance(e, Line):
            painter.drawLine(self.to_screen(sk.xy(e.p1)), self.to_screen(sk.xy(e.p2)))
        elif isinstance(e, Circle):
            c = self.to_screen(sk.xy(e.center))
            r = e.radius * self.scale
            painter.drawEllipse(c, r, r)
        elif isinstance(e, Arc):
            self._draw_arc(painter, sk.xy(e.center), sk.radius(e.id), *arc_angles(sk, e))
        elif isinstance(e, Ellipse | EllipseArc | Spline):
            # Ellipses and splines draw from their samples (D278).
            pts = [self.to_screen(p) for p in sample(sk, e)]
            painter.drawPolyline(pts)

    def handle_marks(self) -> list[tuple[Vec, Vec, bool]]:
        """Tangent handles to draw (TR43, D1305): (through point, handle, pinned) in
        sketch mm, for splines that are selected or whose points are selected."""
        from fdcad.core.sketch.handles import handle_lines

        sk = self.edit.sketch
        chosen = set(self.selection)
        shown: set[str] = set()
        for e in sk.entities.values():
            if isinstance(e, Spline) and (e.id in chosen or chosen & {*e.points, *e.handles}):
                shown |= set(e.points)
        return [(sk.xy(p), sk.xy(h), pinned) for p, h, pinned in handle_lines(sk) if p in shown]

    def _paint_handles(self, painter: QPainter) -> None:
        """A dashed line from each shown through point to its handle; a pinned handle
        gets a filled square (TR43)."""
        marks = self.handle_marks()
        if not marks:
            return
        color = QColor(self.palette_colors.accent)
        for p, h, pinned in marks:
            a, b = self.to_screen(p), self.to_screen(h)
            painter.setPen(QPen(color, 1.0, Qt.PenStyle.DashLine))
            painter.drawLine(a, b)
            painter.setPen(QPen(color, 1.5))
            painter.setBrush(color if pinned else Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(b.x() - 3.5, b.y() - 3.5, 7, 7))
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def comb_lines(self) -> list[tuple[QPointF, QPointF]]:
        """The curvature comb of every spline in widget pixels: the teeth, then the
        lines that join their tips (P2.8 item 10, D514)."""
        sk = self.edit.sketch
        out: list[tuple[QPointF, QPointF]] = []
        half = (self.width() / 2, self.height() / 2)
        for e in sk.entities.values():
            if not isinstance(e, Spline):
                continue
            comb = curvature_comb(sk, e)
            if not len(comb.bases):
                continue
            ends = np.stack([comb.bases, comb.tips])  # 2, n, 2 in mm
            sx = half[0] + (ends[..., 0] - self.center[0]) * self.scale
            sy = half[1] - (ends[..., 1] - self.center[1]) * self.scale
            base = [QPointF(x, y) for x, y in zip(sx[0], sy[0], strict=True)]
            tip = [QPointF(x, y) for x, y in zip(sx[1], sy[1], strict=True)]
            out += list(zip(base, tip, strict=True))
            out += list(itertools.pairwise(tip))
        return out

    def _paint_combs(self, painter: QPainter) -> None:
        lines = self.comb_lines()
        if not lines:
            return
        color = QColor(self.palette_colors.accent)
        color.setAlpha(170)
        painter.setPen(QPen(color, 1.0))
        painter.drawLines([QLineF(a, b) for a, b in lines])
        self._paint_spline_aids(painter, color)

    def spline_aid_marks(self) -> list[tuple[str, Any]]:
        """Display aids of every spline (TR44, D900), in widget pixels: ("polygon",
        [points]), ("inflection", point) and ("tightest", (point, radius in mm))."""
        from fdcad.core.sketch.curvature import spline_aids

        sk = self.edit.sketch
        out: list[tuple[str, Any]] = []
        for e in sk.entities.values():
            if not isinstance(e, Spline):
                continue
            aids = spline_aids(sk, e)
            out.append(("polygon", [self.to_screen((float(x), float(y))) for x, y in aids.polygon]))
            for x, y in aids.inflections:
                out.append(("inflection", self.to_screen((float(x), float(y)))))
            if aids.tightest is not None and aids.radius is not None:
                out.append(("tightest", (self.to_screen(aids.tightest), aids.radius)))
        return out

    def _paint_spline_aids(self, painter: QPainter, color: QColor) -> None:
        """Control polygon (dashed), inflections (small squares) and the tightest point
        with its radius, shown with the combs; never saved (TR44, D900)."""
        for kind, data in self.spline_aid_marks():
            if kind == "polygon":
                pen = QPen(color, 1.0, Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.drawPolyline(data)
            elif kind == "inflection":
                painter.setPen(QPen(color, 1.5))
                painter.drawRect(QRectF(data.x() - 3, data.y() - 3, 6, 6))
            else:
                at, radius = data
                painter.setPen(QPen(color, 1.5))
                painter.drawEllipse(at, 3.5, 3.5)
                painter.drawText(at + QPointF(6, -6), "R " + format_length(radius, self.units))

    # Regions (TR39, D849) ----------------------------------------------------------

    def region_at(self, at: Vec) -> Any:
        """The smallest closed region of the sketch under ``at``, or None (an outline
        with a gap is not a region, so it never shades)."""
        from fdcad.core.sketch.regions import compute

        try:
            found = compute(self.edit.sketch)
        except Exception:  # a sketch that cannot be split into regions has none
            return None
        self._region_pieces = found.pieces
        under = [r for r in found.regions if r.contains(at[0], at[1])]
        return min(under, key=lambda r: abs(r.area)) if under else None

    def select_region_at(self, at: Vec, add: bool = False) -> list[str]:
        """Select every curve around the region under ``at`` and shade it. Returns the
        selected curves ([] when no region is there)."""
        region = self.region_at(at)
        self.shaded_region = region
        if region is None:
            return []
        border: list[str] = []
        pieces = self._region_pieces
        keep = self.select_filter
        for loop in region.loops():
            for index, _forward in loop:
                eid = pieces[index].entity
                known = eid not in border and eid in self.edit.sketch.entities
                if known and (keep is None or keep(eid)):  # the selection filter applies too
                    border.append(eid)
        if not border:
            self.shaded_region = None
            return []
        if add:
            self.selection = [*self.selection, *(e for e in border if e not in self.selection)]
        else:
            self.selection = list(border)
        self.selection_changed.emit()
        self.update()
        return border

    def _paint_region(self, painter: QPainter) -> None:
        region = getattr(self, "shaded_region", None)
        if region is None:
            return
        pieces = self._region_pieces
        if not any(pieces[i].entity in self.selection for loop in region.loops() for i, _f in loop):
            self.shaded_region = None
            return
        from PySide6.QtGui import QPainterPath, QPolygonF

        path = QPainterPath()
        for poly in (region.polygon, *region.hole_polygons):
            path.addPolygon(QPolygonF([self.to_screen(p) for p in poly]))
            path.closeSubpath()
        path.setFillRule(Qt.FillRule.OddEvenFill)
        fill = QColor(self.selected_color())
        fill.setAlpha(45)
        painter.fillPath(path, fill)

    def closed_regions(self) -> list[Any]:
        """Every closed region of the sketch, kept until the sketch changes (TR335)."""
        from fdcad.core.sketch.model import sketch_to_data
        from fdcad.core.sketch.regions import compute

        key = repr(sketch_to_data(self.edit.sketch))
        cached = getattr(self, "_regions_cache", None)
        if cached is not None and cached[0] == key:
            return list(cached[1])
        try:
            regions = list(compute(self.edit.sketch).regions)
        except Exception:  # a sketch that cannot be split into regions has none
            regions = []
        self._regions_cache = (key, regions)
        return regions

    def _paint_all_regions(self, painter: QPainter) -> None:
        from PySide6.QtGui import QPainterPath, QPolygonF

        fill = QColor(self.selected_color())
        fill.setAlpha(22)
        for region in self.closed_regions():
            path = QPainterPath()
            for poly in (region.polygon, *region.hole_polygons):
                path.addPolygon(QPolygonF([self.to_screen(p) for p in poly]))
                path.closeSubpath()
            path.setFillRule(Qt.FillRule.OddEvenFill)
            painter.fillPath(path, fill)

    def open_ends(self) -> list[str]:
        """Open end points of the profiles, kept until the sketch changes (TR341)."""
        from fdcad.core.sketch.model import sketch_to_data
        from fdcad.core.sketch.open_ends import open_end_points

        key = repr(sketch_to_data(self.edit.sketch))
        cached = getattr(self, "_open_cache", None)
        if cached is not None and cached[0] == key:
            return list(cached[1])
        try:
            found = open_end_points(self.edit.sketch)
        except Exception:  # a sketch that cannot be checked shows no marks
            found = []
        self._open_cache = (key, found)
        return found

    def crossing_marks(self) -> tuple[list[Vec], list[Vec]]:
        """Crossings and forks of the profiles, kept until the sketch changes (TR238)."""
        from fdcad.core.sketch.crossing_marks import branch_points, crossing_points
        from fdcad.core.sketch.model import sketch_to_data

        key = repr(sketch_to_data(self.edit.sketch))
        cached = getattr(self, "_crossing_cache", None)
        if cached is not None and cached[0] == key:
            return cached[1]  # type: ignore[no-any-return]
        try:
            found = (crossing_points(self.edit.sketch), branch_points(self.edit.sketch))
        except Exception:  # a sketch that cannot be checked shows no marks
            found = ([], [])
        self._crossing_cache = (key, found)
        return found

    def _paint_crossings(self, painter: QPainter) -> None:
        crosses, forks = self.crossing_marks()
        painter.setPen(QPen(QColor(self.palette_colors.state_warning), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for xy in crosses:
            p = self.to_screen(xy)
            painter.drawLine(p + QPointF(-5, -5), p + QPointF(5, 5))
            painter.drawLine(p + QPointF(-5, 5), p + QPointF(5, -5))
        for xy in forks:
            p = self.to_screen(xy)
            painter.drawRect(QRectF(p.x() - 5, p.y() - 5, 10, 10))

    def _paint_open_ends(self, painter: QPainter) -> None:
        pen = QPen(QColor(self.palette_colors.state_warning), 1.5)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for pid in self.open_ends():
            if pid in self.edit.sketch.entities:
                painter.drawEllipse(self.to_screen(self.edit.sketch.xy(pid)), 6.0, 6.0)

    def point_marks(self) -> dict[str, str]:
        """How each shown point is drawn: "plus" for circle and arc centres (T2.4.1),
        "corner" for a kept corner of a sketch fillet or chamfer (a construction point where
        two lines would meet, TR105), or "dot"."""
        sk = self.edit.sketch
        hidden = self._hidden_points()
        centres = {e.center for e in sk.entities.values() if isinstance(e, Circle | Arc)}
        corners = {
            r.entities[0] for r in sk.relations if r.type == "intersection" and len(r.entities) == 3
        }

        def mark(e: Point) -> str:
            if e.id in centres:
                return "plus"
            return "corner" if e.id in corners and e.construction else "dot"

        return {
            e.id: mark(e)
            for e in sk.entities.values()
            if isinstance(e, Point) and e.id not in hidden
        }

    def _hidden_points(self) -> set[str]:
        """Points the preferences hide: centres (T11.2) and curve end points (T11.3).

        Selected and hovered points always show.
        """
        sk = self.edit.sketch
        hidden: set[str] = set()
        if not self.show_points:  # TR335: every point hidden
            hidden = {e.id for e in sk.entities.values() if isinstance(e, Point)}
        for e in sk.entities.values():
            if not self.options.show_centres and isinstance(e, Circle | Arc):
                hidden.add(e.center)
            if not self.options.end_point_dots:
                if isinstance(e, Line):
                    hidden |= {e.p1, e.p2}
                elif isinstance(e, Arc):
                    hidden |= {e.start, e.end}
        return hidden - set(self.selection) - {self.hover}

    def _draw_arc(self, painter: QPainter, c: Vec, r: float, a0: float, a1: float) -> None:
        center = self.to_screen(c)
        rect = QRectF(
            center.x() - r * self.scale,
            center.y() - r * self.scale,
            2 * r * self.scale,
            2 * r * self.scale,
        )
        # Qt angles are in 1/16 degree, counter clockwise on screen, which matches Y up.
        painter.drawArc(rect, round(math.degrees(a0) * 16), round(math.degrees(a1 - a0) * 16))

    def _paint_preview(self, painter: QPainter) -> None:
        preview = self.tool.preview() if self.tool is not None else Preview()
        pen = QPen(self.preview_color(), 1.4, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        for a, b in preview.lines:
            painter.drawLine(self.to_screen(a), self.to_screen(b))
        for c, r in preview.circles:
            painter.drawEllipse(self.to_screen(c), r * self.scale, r * self.scale)
        for c, r, a0, a1 in preview.arcs:
            self._draw_arc(painter, c, r, a0, a1)
        self._paint_arrows(painter, preview.arrows)
        self._paint_guides(painter)
        painter.setPen(QPen(self.preview_color(), 1.2))
        for c in self.centre_marks():
            p = self.to_screen(c)
            painter.drawLine(p - QPointF(5, 0), p + QPointF(5, 0))
            painter.drawLine(p - QPointF(0, 5), p + QPointF(0, 5))
        showing = self.tool is not None or self.dimension_mode or self._drag is not None
        if self.snap is not None and showing:
            self._paint_snap(painter, self.snap)
        text = self.cursor_text()
        if text and self.tool is not None and self.tool.cursor is not None:
            painter.setPen(QPen(self.preview_color(), 1))
            painter.setFont(type_font(Role.CAPTION, self.font()))
            painter.drawText(self.to_screen(self.tool.cursor.xy) + QPointF(12, 18), text)
        self.values.paint(painter, self.palette_colors.selection)

    #: Length of a direction arrow and its head, in pixels (TR341 item 2, D1705).
    ARROW_PX, ARROW_HEAD_PX = 22.0, 7.0

    def arrow_segments(self, arrows: list[tuple[Vec, Vec]]) -> list[tuple[QPointF, QPointF]]:
        """Screen segments of each arrow: the shaft and the two sides of its head."""
        out: list[tuple[QPointF, QPointF]] = []
        for tail, (dx, dy) in arrows:
            n = math.hypot(dx, dy)
            if n < 1e-12:
                continue
            ux, uy = dx / n, -dy / n  # screen y runs down
            a = self.to_screen(tail)
            b = a + QPointF(ux * self.ARROW_PX, uy * self.ARROW_PX)
            out.append((a, b))
            h = self.ARROW_HEAD_PX
            for side in (1.0, -1.0):
                back = QPointF(-ux * h - side * uy * h * 0.6, -uy * h + side * ux * h * 0.6)
                out.append((b, b + back))
        return out

    def _paint_arrows(self, painter: QPainter, arrows: list[tuple[Vec, Vec]]) -> None:
        if not arrows:
            return
        painter.setPen(QPen(self.preview_color(), 1.6))
        for a, b in self.arrow_segments(arrows):
            painter.drawLine(a, b)

    def cursor_text(self) -> str:
        """Size of the shape being drawn, shown next to the cursor (T2.1.5).

        Lines show their length and angle, circles their radius.
        """
        tool = self.tool
        if tool is None or not tool.clicks or tool.cursor is None:
            return ""
        start, end = tool.clicks[0].xy, tool.cursor.xy
        if tool.name in ("line", "centerline") and not getattr(tool, "arc_mode", False):
            angle = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0]))
            return f"{format_length(dist(start, end), self.units)}  {angle:.2f}°"
        if tool.name == "circle":
            return "R" + format_length(dist(start, end), self.units)
        return ""

    # Relation tags ----------------------------------------------------------------------

    def tag_items(self) -> list[tuple[Vec, str]]:
        """Relation tags to draw: (anchor in sketch mm, relation type) (W3.3).

        Corner joins between end points and the origin's own fixed relation are left out.
        """
        return [(anchor, rtype) for anchor, rtype, _index in self._tag_entries()]

    def _tag_entries(self) -> list[tuple[Vec, str, int]]:
        """Like ``tag_items`` with each relation's index in the sketch."""
        from fdcad.ui.sketch_tools.edit import group_numbers

        sk = self.edit.sketch
        out: list[tuple[Vec, str, int]] = []
        groups = group_numbers(sk)
        for index, rel in enumerate(sk.relations):
            ents = [sk.entities.get(e) for e in rel.entities]
            if not ents or any(e is None for e in ents):
                continue
            if rel.type == "coincident" and all(isinstance(e, Point) for e in ents):
                continue
            if rel.type == "fixed" and all(isinstance(e, Point) and e.construction for e in ents):
                continue
            if rel.type in self.hidden_tags:  # TR341: that kind of tag is hidden
                continue
            if index in groups:  # TR108: a group shows its numbered tag at every member
                out.extend((_anchor_of(sk, e), rel.type, index) for e in ents if e is not None)
                continue
            first = ents[0]
            assert first is not None
            out.append((_anchor_of(sk, first), rel.type, index))
        return out

    def tag_at(self, pos: QPointF) -> str | None:
        """Relation type of the tag under ``pos``, or None."""
        return next((rtype for rect, rtype, _i in self._tags if rect.contains(pos)), None)

    def tag_index_at(self, pos: QPointF) -> int | None:
        """Index of the relation whose tag is under ``pos``, or None."""
        return next((index for rect, _t, index in self._tags if rect.contains(pos)), None)

    def _paint_relations(self, painter: QPainter) -> None:
        self._tags = []
        if not self.show_relations:
            return
        # TR341: the tags have their own size on the type scale, apart from labels.
        font = type_font(Role.BODY if self.tag_scale > 1.0 else Role.CAPTION, self.font())
        painter.setFont(font)
        metrics = painter.fontMetrics()
        stacks: dict[tuple[int, int], int] = {}
        fill = QColor(self.palette_colors.tag_fill)
        chosen = set(self.selected_relations())
        if self.hot_relation is not None:
            chosen.add(self.hot_relation)
        sk_relations = self.edit.sketch.relations
        from fdcad.ui.sketch_tools.edit import group_numbers

        numbers = group_numbers(self.edit.sketch)
        for anchor, rtype, index in self._tag_entries():
            p = self.to_screen(anchor)
            key = (round(p.x()), round(p.y()))
            k = stacks.get(key, 0)
            stacks[key] = k + 1
            text = strings.RELATION_TAGS.get(rtype, rtype[:1].upper())
            if index in numbers:  # TR108: the group's number
                text = f"{text}{numbers[index]}"
            w = metrics.horizontalAdvance(text) + 6
            h = metrics.height()
            rect = QRectF(p.x() + 6 + k * (w + 2), p.y() + 4, w, h)
            picked = index in chosen
            off = sk_relations[index].off if index < len(sk_relations) else False
            weak = sk_relations[index].weak if index < len(sk_relations) else False
            line = QColor(self.palette_colors.tag_line)
            if off:  # switched off (TR109): greyed and dashed
                line = QColor(self.palette_colors.sketch_reference)
            painter.setPen(
                QPen(
                    self.selected_color() if picked else line,
                    2 if picked else 1,
                    Qt.PenStyle.DashLine
                    if off and not picked
                    else Qt.PenStyle.DotLine
                    if weak and not picked  # TR362: automatic relations are dotted
                    else Qt.PenStyle.SolidLine,
                )
            )
            painter.setBrush(self.hover_color() if picked else fill)
            painter.drawRoundedRect(rect, 2, 2)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
            self._tags.append((rect, rtype, index))
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def snap_extension(self, snap: Snap) -> tuple[Vec, Vec] | None:
        """The line a snap on a line lies on, carried across the view (TR341 item 3,
        D1316): a point on the line past its ends still sits on it. Sketch mm."""
        if snap.kind != "on_curve" or snap.target is None:
            return None
        line = self.edit.sketch.entities.get(snap.target)
        if not isinstance(line, Line):
            return None
        a, b = self.edit.sketch.xy(line.p1), self.edit.sketch.xy(line.p2)
        length = dist(a, b)
        if length < 1e-9:
            return None
        reach = (self.width() + self.height()) / max(self.scale, 1e-9)
        ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
        return (a[0] - ux * reach, a[1] - uy * reach), (b[0] + ux * reach, b[1] + uy * reach)

    def _watch_rest(self, snap: Snap | None) -> None:
        """Start the rest timer when the cursor comes onto a sketch point (TR232)."""
        target = snap.target if snap is not None and snap.kind == "point" else None
        if target is None:
            self._rest = None
            timer = getattr(self, "_rest_timer", None)
            if timer is not None:
                timer.stop()
            return
        if self._rest is not None and self._rest[0] == target:
            return
        from PySide6.QtCore import QTimer

        from fdcad.ui.sketch_tools.guides import DWELL_MS

        timer = getattr(self, "_rest_timer", None)
        if timer is None:
            # A child of the canvas, so it goes with it (no call after it is deleted).
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self._rested)
            self._rest_timer = timer
        self._rest = (target, 0)
        timer.start(DWELL_MS)

    def _rested(self) -> None:
        """The cursor stayed on the point: start or finish a guide."""
        if self._rest is None or self.tool is None:
            return
        pid = self._rest[0]
        if pid in self.edit.sketch.entities:
            self.rest_on_point(pid)

    def rest_on_point(self, pid: str) -> str:
        """Use sketch point ``pid`` for a guide (TR232, D1714)."""
        done = self.guides.rest_on(self.edit.sketch.xy(pid))
        if done == "started":
            self.status_message.emit(strings.GUIDE_STARTED)
        elif done == "made":
            self.status_message.emit(strings.GUIDE_MADE)
        self.update()
        return done

    def _paint_guides(self, painter: QPainter) -> None:
        """The temporary guides, dashed, with a dot at each snap point (TR232)."""
        if not self.guides.lines and self.guides.anchor is None:
            return
        faint = QColor(self.preview_color())
        faint.setAlpha(140)
        painter.setPen(QPen(faint, 1, Qt.PenStyle.DashLine))
        for a, b in self.guides.lines:
            painter.drawLine(self.to_screen(a), self.to_screen(b))
        painter.setPen(QPen(faint, 1))
        for p in self.guides.points():
            painter.drawEllipse(self.to_screen(p), 2.0, 2.0)
        if self.guides.anchor is not None:
            painter.drawEllipse(self.to_screen(self.guides.anchor), 6.0, 6.0)

    def _paint_snap(self, painter: QPainter, snap: Snap) -> None:
        p = self.to_screen(snap.xy)
        extension = self.snap_extension(snap)
        if extension is not None:
            faint = QColor(self.preview_color())
            faint.setAlpha(90)
            painter.setPen(QPen(faint, 1, Qt.PenStyle.DashLine))
            painter.drawLine(self.to_screen(extension[0]), self.to_screen(extension[1]))
        painter.setPen(QPen(self.preview_color(), 1, Qt.PenStyle.DotLine))
        for a, b in snap.guides:
            painter.drawLine(self.to_screen(a), self.to_screen(b))
        painter.setPen(QPen(self.preview_color(), 1.5))
        if snap.kind in ("point", "center", "midpoint", "quadrant", "intersection"):
            painter.drawRect(QRectF(p.x() - 5, p.y() - 5, 10, 10))
        elif snap.kind == "guide":  # TR232
            painter.drawEllipse(p, 5, 5)
        elif snap.kind == "on_curve":
            painter.drawEllipse(p, 4, 4)
        label = self._snap_label(snap)
        if label:
            painter.setFont(type_font(Role.CAPTION, self.font()))
            painter.drawText(p + QPointF(9, -8), label)

    def _snap_label(self, snap: Snap) -> str | None:
        """The label drawn beside a snap; the fixed sketch origin reads Origin."""
        if snap.kind == "point" and snap.target is not None and self._is_origin(snap.target):
            return strings.SNAP_ORIGIN
        return strings.SNAP_LABELS.get(snap.kind)

    def _is_origin(self, pid: str) -> bool:
        """True when ``pid`` is the fixed construction point at the sketch origin."""
        sk = self.edit.sketch
        p = sk.entities.get(pid)
        return (
            isinstance(p, Point)
            and p.construction
            and abs(p.x) < 1e-12
            and abs(p.y) < 1e-12
            and any(r.type == "fixed" and r.entities == [pid] for r in sk.relations)
        )

    def _paint_dimensions(self, painter: QPainter) -> None:
        self._labels = {}
        sk = self.edit.sketch
        _rels, bad = self.edit.conflicting_items()
        painter.setFont(self._label_font())
        metrics = painter.fontMetrics()
        for dim in sk.dimensions:
            if not (self.show_driving if dim.driving else self.show_reference):
                continue  # TR341: that kind of dimension is hidden
            try:
                anchor, segments = self._dimension_geometry(dim)
            except (KeyError, TypeError, ZeroDivisionError):
                continue
            if dim.id in bad:
                color = QColor(self.palette_colors.sketch_over)
            elif dim.id in self.selection:
                color = self.selected_color()
            elif dim.id == self.hover:
                color = self.hover_color()
            else:
                color = QColor(
                    self.palette_colors.sketch_full
                    if dim.driving and not dim.off
                    else self.palette_colors.sketch_reference
                )
            painter.setPen(
                QPen(color, 1, Qt.PenStyle.DashLine if dim.off else Qt.PenStyle.SolidLine)
            )
            for a, b in shown_segments(dim, segments):
                painter.drawLine(a, b)
            text = self._dimension_text(dim)
            rect = self._label_box(anchor, text, metrics)
            painter.fillRect(rect, QColor(self.palette_colors.label_plate))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
            self._labels[dim.id] = rect

    def _dimension_text(self, dim: Dimension) -> str:
        value = dim.param.value
        if dim.display:  # tolerance, decimals, radius or diameter (TR46, D901)
            from fdcad.core.sketch.dimension_display import label, round_kind

            shown = round_kind(dim.type, dim.display)
            if shown != dim.type:
                value = value * 2 if shown == "diameter" else value / 2
            inch = self.units is UnitSystem.IN
            kind = "angle" if dim.type == "angle" else "length"
            text = label(value, kind, dim.display, inch)
            if shown == "radius":
                text = "R" + text
            elif shown in ("diameter", "doubled_distance"):
                text = "⌀" + text
        elif dim.type == "angle":
            from fdcad.core.units.number_display import fixed

            text = f"{fixed(math.degrees(value), 2)}°"
        else:
            text = format_length(value, self.units)
            if dim.type == "radius":
                text = "R" + text
            elif dim.type in ("diameter", "doubled_distance"):
                text = "⌀" + text
        if dim.link:  # TR193: a linked value shows its shared name
            text = f"{dim.link}: {text}"
        if dim.param.expr.startswith("="):
            formula = dim.param.expr[1:].strip()
            # TR235: the formula itself, beside the value it gives.
            text = f"{formula} = {text}" if SketchCanvas.show_formulas else "= " + text
        if dim.off:
            return f"{text} {strings.SWITCHED_OFF}"
        return text if dim.driving else f"({text})"

    def _update_selection_preview(self, pos: QPointF, hover: str | None) -> None:
        """With one or two sketch items selected and no tool, the dimension they would
        get follows the cursor in empty space (TR110, D862)."""
        from fdcad.ui.sketch_tools.edit import preview_dimension

        picks = [s for s in self.selection if s in self.edit.sketch.entities]
        found = None
        cursor = self.to_sketch(pos)
        if (
            self.tool is None
            and hover is None
            and 1 <= len(picks) <= 2
            and len(picks) == len(self.selection)
            and self._near_items(cursor, picks, 40.0)
        ):
            found = preview_dimension(self.edit.sketch, picks, cursor)
        if found is not None or getattr(self, "selection_preview", None) is not None:
            self.selection_preview = found
            self.update()

    def _near_items(self, at: Vec, ids: list[str], pixels: float) -> bool:
        """True when ``at`` is within ``pixels`` of one of the items (so a click far away
        still clears the selection)."""
        from fdcad.core.sketch.ops.geom import geo

        reach = pixels / max(self.scale, 1e-9)
        for eid in ids:
            ent = self.edit.sketch.entities.get(eid)
            if isinstance(ent, Point):
                near = self.edit.sketch.xy(eid)
            else:
                try:
                    g = geo(self.edit.sketch, eid)
                    near = g.at(g.param(at))
                except Exception:  # a curve the plain geometry cannot measure
                    continue
            if math.dist(near, at) <= reach:
                return True
        return False

    def _paint_dimension_preview(self, painter: QPainter) -> None:
        """The dimension that follows the cursor, half transparent (T4.2.1)."""
        dim = self.dim_preview if self.dimension_mode else getattr(self, "selection_preview", None)
        if dim is None:
            return
        try:
            anchor, segments = self._dimension_geometry(dim)
        except (KeyError, TypeError, ZeroDivisionError):
            return
        color = self.selected_color()
        color.setAlpha(140)
        painter.setPen(QPen(color, 1, Qt.PenStyle.DashLine))
        for a, b in segments:
            painter.drawLine(a, b)
        painter.setFont(self._label_font())
        text = self._dimension_text(dim)
        rect = self._label_box(anchor, text, painter.fontMetrics())
        painter.fillRect(rect, QColor(self.palette_colors.label_plate_faint))
        painter.setPen(QPen(color, 1))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def _dimension_geometry(self, dim: Dimension) -> tuple[QPointF, list[tuple[QPointF, QPointF]]]:
        """Label position and the lines to draw, in screen pixels."""
        sk = self.edit.sketch
        placed = label_position(sk, dim)
        if placed is not None:
            return self._placed_geometry(dim, placed)
        ents = [sk.entities[e] for e in dim.entities]
        off = DIM_OFFSET_PX
        if dim.type == "path_length":  # TR45: a leader from the middle of the chain
            start = self.to_screen(label_anchor(sk, dim))
            out = start + QPointF(off, -off)
            return out, [(start, out)]
        if dim.type == "arc_length":
            arc = ents[0]
            assert isinstance(arc, Arc)
            return self._arc_length_geometry(arc, sk.radius(arc.id) + off / self.scale, None)
        if dim.type in ("radius", "diameter"):
            e = ents[0]
            assert isinstance(e, Circle | Arc)
            c = sk.xy(e.center)
            r = sk.radius(e.id)
            angle = math.pi / 4
            if isinstance(e, Arc):
                a0, a1 = arc_angles(sk, e)
                angle = (a0 + a1) / 2
            edge = self.to_screen((c[0] + r * math.cos(angle), c[1] + r * math.sin(angle)))
            start = (
                self.to_screen(c)
                if dim.type == "radius"
                else self.to_screen((c[0] - r * math.cos(angle), c[1] - r * math.sin(angle)))
            )
            out = edge + QPointF(math.cos(angle) * off, -math.sin(angle) * off)
            return out, [(start, out)]
        if dim.type == "angle":
            l1, l2 = ents
            assert isinstance(l1, Line) and isinstance(l2, Line)
            m1 = _mid(sk.xy(l1.p1), sk.xy(l1.p2))
            m2 = _mid(sk.xy(l2.p1), sk.xy(l2.p2))
            a, b = self.to_screen(m1), self.to_screen(m2)
            anchor = (a + b) / 2
            leaders = [(a, anchor), (b, anchor)]
            mirrored = mirrored_middle(sk, dim)  # TR111 (D2200)
            if mirrored is not None:
                leaders.append((self.to_screen(mirrored), anchor))
            return anchor, leaders
        # Linear dimensions: two points, a line, a point and a line, two lines,
        # the side of a circle or arc, or a doubled distance to an axis.
        p1, p2 = distance_ends(sk, dim)
        if dist(p1, p2) < 1e-12:
            return self.to_screen(p1), []
        s1, s2 = self.to_screen(p1), self.to_screen(p2)
        if dim.type == "horizontal_distance":
            y = min(s1.y(), s2.y()) - off
            a, b = QPointF(s1.x(), y), QPointF(s2.x(), y)
        elif dim.type == "vertical_distance":
            x = max(s1.x(), s2.x()) + off
            a, b = QPointF(x, s1.y()), QPointF(x, s2.y())
        else:
            dx, dy = s2.x() - s1.x(), s2.y() - s1.y()
            n = math.hypot(dx, dy) or 1.0
            nx, ny = dy / n * off, -dx / n * off
            a, b = s1 + QPointF(nx, ny), s2 + QPointF(nx, ny)
        return (a + b) / 2, [(s1, a), (s2, b), (a, b)]

    def _arc_length_geometry(
        self, arc: Arc, radius: float, label: QPointF | None
    ) -> tuple[QPointF, list[tuple[QPointF, QPointF]]]:
        """An arc length dimension (T4.1, D515): an arc concentric with ``arc`` at
        ``radius`` (mm), with extension lines from the arc's end points."""
        sk = self.edit.sketch
        c, r = sk.xy(arc.center), sk.radius(arc.id)
        a0, a1 = arc_angles(sk, arc)
        steps = max(8, min(64, round((a1 - a0) / (math.pi / 32))))
        pts = [
            self.to_screen(
                (
                    c[0] + radius * math.cos(a0 + (a1 - a0) * i / steps),
                    c[1] + radius * math.sin(a0 + (a1 - a0) * i / steps),
                )
            )
            for i in range(steps + 1)
        ]
        segments = list(itertools.pairwise(pts))
        for angle, end in ((a0, pts[0]), (a1, pts[-1])):
            on_arc = (c[0] + r * math.cos(angle), c[1] + r * math.sin(angle))
            segments.append((self.to_screen(on_arc), end))
        mid = (a0 + a1) / 2
        anchor = self.to_screen((c[0] + radius * math.cos(mid), c[1] + radius * math.sin(mid)))
        return (label if label is not None else anchor), segments

    def _placed_geometry(
        self, dim: Dimension, label: Vec
    ) -> tuple[QPointF, list[tuple[QPointF, QPointF]]]:
        """Dimension lines for text the user placed at ``label`` (sketch mm, T4.4.2)."""
        sk = self.edit.sketch
        at = self.to_screen(label)
        if dim.display and dim.display.get("style") == "ordinate":  # TR45: a leader only
            px, py = sk.xy(dim.entities[1])
            foot = (px, label[1]) if dim.type == "horizontal_distance" else (label[0], py)
            return at, [(self.to_screen((px, py)), self.to_screen(foot))]
        if dim.type == "path_length":  # TR45
            return at, [(self.to_screen(label_anchor(sk, dim)), at)]
        if dim.type == "arc_length":
            arc = sk.entities[dim.entities[0]]
            assert isinstance(arc, Arc)
            return self._arc_length_geometry(arc, dist(sk.xy(arc.center), label), at)
        if dim.type in ("radius", "diameter"):
            e = sk.entities[dim.entities[0]]
            assert isinstance(e, Circle | Arc)
            c = sk.xy(e.center)
            r = sk.radius(e.id)
            gap = dist(c, label)
            ux, uy = ((label[0] - c[0]) / gap, (label[1] - c[1]) / gap) if gap > 1e-12 else (1, 0)
            start = c if dim.type == "radius" else (c[0] - r * ux, c[1] - r * uy)
            far = label if gap >= r else (c[0] + r * ux, c[1] + r * uy)
            return at, [(self.to_screen(start), self.to_screen(far))]
        if dim.type == "angle":
            mids = []
            for eid in dim.entities:
                line = sk.entities[eid]
                assert isinstance(line, Line)
                mids.append(self.to_screen(_mid(sk.xy(line.p1), sk.xy(line.p2))))
            mirrored = mirrored_middle(sk, dim)  # TR111 (D2200)
            if mirrored is not None:
                mids.append(self.to_screen(mirrored))
            return at, [(m, at) for m in mids]
        p1, p2 = distance_ends(sk, dim)
        if dist(p1, p2) < 1e-12:
            return at, []
        if dim.type == "horizontal_distance":
            d: Vec = (1.0, 0.0)
        elif dim.type == "vertical_distance":
            d = (0.0, 1.0)
        else:
            length = dist(p1, p2)
            d = ((p2[0] - p1[0]) / length, (p2[1] - p1[1]) / length)
        n = (-d[1], d[0])

        def onto(p: Vec) -> Vec:
            h = (label[0] - p[0]) * n[0] + (label[1] - p[1]) * n[1]
            return p[0] + n[0] * h, p[1] + n[1] * h

        a, b = onto(p1), onto(p2)
        segments = [(p1, a), (p2, b), (a, b)]
        t = (label[0] - a[0]) * d[0] + (label[1] - a[1]) * d[1]
        tb = (b[0] - a[0]) * d[0] + (b[1] - a[1]) * d[1]
        if t < min(0.0, tb) or t > max(0.0, tb):
            # Text beyond the ends: the dimension line reaches out to it.
            near = a if abs(t) < abs(t - tb) else b
            segments.append((near, label))
        return at, [(self.to_screen(x), self.to_screen(y)) for x, y in segments]


#: Arrow keys to a nudge direction in sketch axes (TR293, D2209).
_NUDGE = {
    Qt.Key.Key_Left: (-1.0, 0.0),
    Qt.Key.Key_Right: (1.0, 0.0),
    Qt.Key.Key_Up: (0.0, 1.0),
    Qt.Key.Key_Down: (0.0, -1.0),
}


def beside(rect: QRectF, w: int, h: int, width: int, height: int) -> tuple[int, int]:
    """Top left of a ``w`` by ``h`` box right of ``rect``, or left of it when there is no room.

    The box is centred on the label vertically and kept inside the widget.
    """
    gap = 6
    x = rect.right() + gap
    if x + w > width:
        x = rect.left() - gap - w
    y = rect.center().y() - h / 2
    return int(min(max(0.0, x), max(0, width - w))), int(min(max(0.0, y), max(0, height - h)))


def relation_index(item: str) -> int | None:
    """The relation index of a selection item ``r<index>``, or None for other items."""
    if item.startswith("r") and item[1:].isdigit():
        return int(item[1:])
    return None


def tool_cursor(name: str | None) -> QCursor:
    """Cursor for a sketch tool: a small copy of its icon (W3.2, L8), or an arrow."""
    if not name:
        return QCursor(Qt.CursorShape.ArrowCursor)
    from fdcad.ui.icons import icon

    pixmap = icon(f"sketch.{name}").pixmap(20, 20)
    if pixmap.isNull():
        return QCursor(Qt.CursorShape.CrossCursor)
    return QCursor(pixmap, 0, 0)


def _anchor_of(sk: Sketch, e: Entity) -> Vec:
    """Where a relation tag of entity ``e`` goes, in sketch mm."""
    if isinstance(e, Point):
        return e.x, e.y
    if isinstance(e, Ellipse | EllipseArc | Spline):
        pts = sample(sk, e, 8)
        return pts[len(pts) // 2]
    if isinstance(e, Line):
        return _mid(sk.xy(e.p1), sk.xy(e.p2))
    c = sk.xy(e.center)
    r = sk.radius(e.id)
    angle = math.pi / 4
    if isinstance(e, Arc):
        a0, a1 = arc_angles(sk, e)
        angle = (a0 + a1) / 2
    return c[0] + r * math.cos(angle), c[1] + r * math.sin(angle)


def _is_return(event: QKeyEvent) -> bool:
    return event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)


def _sketch_key(event: QKeyEvent) -> bool:
    """Keys the sketch handles itself while it has focus."""
    ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
    return (
        event.matches(QKeySequence.StandardKey.Undo)
        or event.matches(QKeySequence.StandardKey.Redo)
        or event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Escape)
        or (event.key() == Qt.Key.Key_Y and ctrl)
        or event.matches(QKeySequence.StandardKey.Copy)
        or event.matches(QKeySequence.StandardKey.Paste)
    )


def _mid(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0]) / 2, (a[1] + b[1]) / 2


def _points_of_entity(e: Entity) -> list[str]:
    return entity_points(e)


def _plain_negative(text: str) -> bool:
    """True for typed text that is a minus sign before a plain term, such as -5 or -5mm."""
    import re

    return re.fullmatch(r"\s*-\s*[0-9.]+\s*[a-z]*\s*", text) is not None


def _side_of(sketch: Sketch, dim: Dimension) -> int:
    """The side a horizontal or vertical distance keeps now: its stored side, or the
    sign of the second item's offset from the first along the axis (TR337, TR111)."""
    if dim.side in (1, -1):
        return dim.side
    from fdcad.ui.sketch_tools.edit import distance_ends

    a, b = distance_ends(sketch, dim)
    axis = 0 if dim.type == "horizontal_distance" else 1
    return 1 if b[axis] - a[axis] >= 0 else -1
