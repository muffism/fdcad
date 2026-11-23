"""The FDCAD main window (PLAN section 8).

The window appears first with only Qt loaded. ``finish_setup`` then imports the
kernel, feature tree and panels (lazy startup, PLAN 11.3 item 8).
"""

from __future__ import annotations

import contextlib
import weakref
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any

import shiboken6
from PySide6.QtCore import (
    QEvent,
    QObject,
    QPointF,
    QRunnable,
    QSize,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QCursor,
    QGuiApplication,
    QKeySequence,
    QUndoGroup,
)
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedLayout,
    QStackedWidget,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from fdcad import __version__
from fdcad.core.io.export import ExportError
from fdcad.core.io.fdef import PART_SUFFIX
from fdcad.core.io.migrations import FileFormatError
from fdcad.core.kernel import kernel_job
from fdcad.ui import strings, strings_a11y, strings_extra
from fdcad.ui import strings_feedback as feedback
from fdcad.ui import strings_phase3 as text3
from fdcad.ui.errors.message import show_error
from fdcad.ui.main_window.actions import CommandActions
from fdcad.ui.main_window.phase4_features import PHASE4_INSERTS
from fdcad.ui.main_window.view_bar import DISPLAY_STYLES
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.themes import motion
from fdcad.ui.themes.style import unit
from fdcad.ui.themes.theme import apply_theme, palette
from fdcad.ui.themes.typography import tabular

if TYPE_CHECKING:
    from fdcad.core.document.model import Document
    from fdcad.core.rebuild.engine import RebuildReport
    from fdcad.ui.command_tabs.custom import TabCustomizer
    from fdcad.ui.errors.panel import ErrorsPanel
    from fdcad.ui.main_window.curvature_graph import CurvatureGraph
    from fdcad.ui.main_window.imports import ImportFlow
    from fdcad.ui.main_window.left_tabs import LeftTabs
    from fdcad.ui.main_window.recovery import Autosaver
    from fdcad.ui.main_window.sketch_mode import SketchMode
    from fdcad.ui.main_window.start_page import StartPage
    from fdcad.ui.print_tools.build_volume import BuildVolume
    from fdcad.ui.print_tools.draft_analysis import DraftAnalysis
    from fdcad.ui.print_tools.edge_angles import EdgeAngleAnalysis
    from fdcad.ui.print_tools.estimate import PrintEstimate
    from fdcad.ui.print_tools.fit_tool import FitTool
    from fdcad.ui.print_tools.geometry_check import GeometryCheck
    from fdcad.ui.print_tools.layer_preview import LayerPreview
    from fdcad.ui.print_tools.orientation import OrientationTool
    from fdcad.ui.print_tools.overhang import OverhangAnalysis
    from fdcad.ui.print_tools.undercut import UndercutAnalysis
    from fdcad.ui.print_tools.wall_thickness import WallThicknessAnalysis
    from fdcad.ui.property_panel.panel import PropertyPanel
    from fdcad.ui.property_panel.variables import VariablesPanel
    from fdcad.ui.session import DocumentSession
    from fdcad.ui.tree.feature_tree import FeatureTree
    from fdcad.ui.viewport.preview import FeaturePreview


#: Phase 2 feature commands: command id, feature type, operation (PHASE2_SPEC P2.2 to P2.7).
PHASE2_INSERTS = (
    ("feature.sweep", "sweep", "boss"),
    ("feature.swept_cut", "sweep", "cut"),
    ("feature.loft", "loft", "boss"),
    ("feature.lofted_cut", "loft", "cut"),
    ("feature.fillet", "fillet", "boss"),
    ("feature.chamfer", "chamfer", "boss"),
    ("feature.shell", "shell", "boss"),
    ("feature.draft", "draft", "boss"),
)
#: Fix actions that change a feature's data (``core.features.fixes``).
FIX_ACTIONS = ("skip_items", "set_param", "add_refs", "set_ref")  # TR278 (D1406), D2627


def added(param: Any, delta: float, session: Any) -> Any:
    """``param`` plus ``delta`` millimetres, keeping a formula as a formula."""
    from fdcad.core.document.model import Param
    from fdcad.core.units import UnitSystem

    value = param.value + delta
    if param.expr.strip().startswith("="):
        return Param(f"{param.expr.strip()} + {delta:g}mm", value)
    inch = session.document.units is UnitSystem.IN
    shown = value / 25.4 if inch else value
    return Param(f"{shown:.6g}", value)


def _codes_for(session: Any, fid: str, fix: Any) -> list[tuple[str, str]]:
    report = session.report
    result = report.results.get(fid) if report is not None else None
    if result is None:
        return []
    return [(fid, i.code) for i in result.issues if fix in i.fixes and i.code]


def selection_text(shapes: list[Any]) -> str:
    """Status bar text such as "2 faces, 1 edge selected"."""
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX

    names = {TopAbs_FACE: "face", TopAbs_EDGE: "edge", TopAbs_VERTEX: "vertex"}
    counts: dict[str, int] = {}
    for shape in shapes:
        kind = names.get(shape.ShapeType(), "item")
        counts[kind] = counts.get(kind, 0) + 1
    parts = []
    for kind, n in counts.items():
        plural = "vertices" if kind == "vertex" else kind + "s"
        parts.append(f"{n} {kind if n == 1 else plural}")
    return strings.SELECTED.format(items=", ".join(parts))


#: The window's size on the first start, when the screen has room for it.
START_SIZE = QSize(1400, 900)


def start_size(available: QSize | None) -> QSize:
    """The first window size: ``START_SIZE``, made smaller to fit a small screen (D635)."""
    if available is None or available.isEmpty():
        return START_SIZE
    return QSize(
        min(START_SIZE.width(), int(available.width() * 0.95)),
        min(START_SIZE.height(), int(available.height() * 0.9)),
    )


def viewport_supported() -> bool:
    """Return False on platforms with no GPU window, such as Qt's offscreen platform."""
    return QGuiApplication.platformName() not in ("offscreen", "minimal")


#: File suffixes Save As and Export know; any other text after a dot is part of the name.
KNOWN_SUFFIXES = (PART_SUFFIX, ".fdef", ".step", ".stp", ".stl", ".3mf")


def with_suffix(path: Path, suffix: str) -> Path:
    """``path`` ending in ``suffix``: a known suffix is replaced, other text is kept.

    A name such as "v1.2 bracket" keeps its dot, so it becomes "v1.2 bracket.stl"
    and not "v1.stl".
    """
    if path.suffix.lower() == suffix:
        return path
    if path.suffix.lower() in KNOWN_SUFFIXES:
        return path.with_suffix(suffix)
    return path.with_name(path.name + suffix)


def _reference_mesh(doc: Any, report: Any) -> str | None:
    """The name of an imported mesh shown only as a reference, or None."""
    for feature in doc.features:
        result = report.results.get(feature.id)
        if feature.type == "import_mesh" and result is not None and "mesh" in result.extras:
            return str(feature.name)
    return None


class _JobSignals(QObject):
    done = Signal(str)


class _Job(QRunnable):
    """Runs kernel work (exports) off the UI thread."""

    def __init__(self, work: Callable[[], str]) -> None:
        super().__init__()
        self.work = work
        self.signals = _JobSignals()

    @kernel_job
    def run(self) -> None:
        try:
            message = self.work()
        except ExportError as exc:  # FDCAD's own reason already says what to do
            message = strings.EXPORT_REFUSED.format(reason=exc)
        except Exception as exc:  # report, never crash
            message = strings.EXPORT_FAILED.format(reason=strings.clause(exc))
        self.signals.done.emit(message)


#: Commands that start reference geometry (P2.10) and the feature type they make.
REFERENCE_COMMANDS = (
    ("feature.ref_plane", "ref_plane"),
    ("feature.ref_axis", "ref_axis"),
    ("feature.ref_point", "ref_point"),
    ("feature.coord_system", "coord_system"),
)


#: Features kept in the Recently Edited list (TR221).
RECENT_EDITS = 10


class DocumentTab(QWidget):
    """One open part: its session and 3D view."""

    def __init__(self, session: DocumentSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from fdcad.ui.main_window.recovery import Autosaver

        self.session = session
        self.autosaver: Autosaver = Autosaver()
        self.selection: list[Any] = []  # picked faces, edges and vertices (TopoDS_Shape)
        #: Sketch of the feature open in the panel, kept visible under the preview.
        self.editing_sketch: str | None = None
        #: The selection breadcrumbs over the view (TR20), set by the view bar.
        self.breadcrumbs: Any = None
        #: Hide All Reference Geometry is on: no planes in the 3D view (T12.4, view state).
        self.reference_hidden = False
        #: View > Sketches is off: no sketches in the 3D view (T14.4.3, view state).
        self.sketches_hidden = False
        #: View > Origins is on: the origin axes show (T14.4.3, view state).
        self.origin_shown = False
        #: Kinds hidden with View > Show Types (TR215): planes, axes, points, frames, curves.
        self.hidden_types: set[str] = set()
        #: Face names of the isolated bodies while I is on, else None (D410, view state).
        self.isolated: set[str] | None = None
        #: How the other bodies look while isolating (TR99, D939).
        self.isolate_look = "hidden"
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.view_bar = QToolBar()
        self.view_bar.setObjectName("view_bar")
        self.view_bar.setAccessibleName(strings_a11y.NAME_VIEW_TOOLS)
        self.view_toolbar: Any = None  # filled by view_bar.fill_view_bar
        self.corner = QWidget()
        self.corner.setObjectName("confirmation_corner")
        corner_layout = QHBoxLayout(self.corner)
        corner_layout.setContentsMargins(0, 0, 4, 0)
        self.corner_ok = QPushButton(strings.OK)
        self.corner_cancel = QPushButton(strings.CANCEL)
        self.corner_action: QAction | None = None
        corner_layout.addWidget(self.corner_ok)
        corner_layout.addWidget(self.corner_cancel)
        outer.addWidget(self.view_bar)
        from fdcad.ui.main_window.message_bars import MessageBars

        #: Information and warning bars above the view (TR203, D959).
        self.message_bars = MessageBars(self)
        outer.addWidget(self.message_bars)
        # A 2 px frame round the view turns accent with keyboard focus (U4.1, D662).
        holder = QFrame()
        holder.setObjectName("view_focus")
        outer.addWidget(holder, 1)
        layout = QStackedLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        self.stack = layout
        self.sketch_canvas: QWidget | None = None
        self.viewport: Any
        if viewport_supported():
            from fdcad.ui.viewport.widget import ViewportWidget

            self.viewport = ViewportWidget(self)
            self.viewport.set_palette(palette())
            self.viewport.selection_changed.connect(self._picked)
        else:
            # The message wraps and sits in the middle (D2805). As one line it was the
            # least width of the whole tab: 1209 px in the font Qt falls back to
            # offscreen on Windows, more than the window, so Qt took the difference
            # from the left panel and left it at its least width, not its default.
            self.viewport = QLabel(strings.NO_3D_VIEW, self)
            self.viewport.setWordWrap(True)
            self.viewport.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.viewport.setAccessibleName(strings_a11y.NAME_VIEW)
        # The main view sits in a grid from the start, so Split View adds panes beside
        # it without moving its native window (TR16).
        self.view_host = QWidget()
        self.view_grid = QGridLayout(self.view_host)
        self.view_grid.setContentsMargins(0, 0, 0, 0)
        self.view_grid.setSpacing(2)
        self.view_grid.addWidget(self.viewport, 0, 0)
        layout.addWidget(self.view_host)
        #: Split View: the extra panes, the layout name and the active pane (None: main).
        self.panes: list[Any] = []
        self.split = "one"
        self.active_pane: Any = None
        self.viewport.installEventFilter(self)
        session.rebuilt.connect(self._show)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """A click in the main view makes it the active view again (TR16)."""
        if watched is self.viewport and event.type() == QEvent.Type.MouseButtonPress:
            self.active_pane = None
        return super().eventFilter(watched, event)

    def set_split(self, layout: str) -> bool:
        """Show one, two (side by side or stacked) or four views (TR16). False when the
        part has no 3D view (the test platform)."""
        from fdcad.ui.viewport import split

        if not hasattr(self.viewport, "_viewer"):
            return False
        cells = split.cells(layout)
        starts = split.start_views(layout)
        for pane in self.panes:
            self.view_grid.removeWidget(pane)
            pane.close_view()
            pane.deleteLater()
        self.panes = []
        self.active_pane = None
        from fdcad.ui.viewport.view_pane import ViewPane

        for (row, col), start in zip(cells[1:], starts[1:], strict=True):
            pane = ViewPane(self.viewport, self.view_host)
            pane.pending_view = start or "iso"
            pane.activated.connect(self._pane_activated)
            self.view_grid.addWidget(pane, row, col)
            pane.show()
            self.panes.append(pane)
        for r in range(2):
            self.view_grid.setRowStretch(r, 1 if any(c[0] == r for c in cells) else 0)
            self.view_grid.setColumnStretch(r, 1 if any(c[1] == r for c in cells) else 0)
        if starts[0] is not None:
            self.viewport.set_view(starts[0])
        self.split = layout
        return True

    def release_views(self) -> None:
        """Free the kernel views of this part while their windows still exist: the
        split panes first, then the main view (D2780). Call before the tab is deleted."""
        for pane in self.panes:
            pane.close_view()
        release = getattr(self.viewport, "release", None)
        if release is not None:
            release()

    def _pane_activated(self, pane: Any) -> None:
        self.active_pane = pane

    @property
    def corner_shown(self) -> bool:
        """True while the confirmation corner is shown."""
        return self.corner_action is not None and self.corner_action.isVisible()

    def _picked(self, shapes: list[Any]) -> None:
        self.selection = list(shapes)

    def refresh_part(self) -> None:
        """Draw the part in its colours: part, body, feature and face (P2.11)."""
        report = self.session.report
        see_through = getattr(self.viewport, "set_see_through", None)
        if see_through is not None and report is not None:
            see_through(self.see_through_solids())  # TR21: before the part is drawn
        locked = getattr(self.viewport, "set_locked", None)
        if locked is not None and report is not None:
            locked(self.locked_solids())  # TR269
        modes = getattr(self.viewport, "set_body_modes", None)
        if modes is not None and report is not None:
            from fdcad.ui.main_window.body_modes_ui import solids_with_modes

            modes(solids_with_modes(self))  # TR216
        show = getattr(self.viewport, "show_part", None)
        if show is None or report is None:
            return
        from fdcad.ui.appearance.tool import part_display

        color, faces = part_display(self)
        show(self.shown_part(), color, faces)
        others = getattr(self.viewport, "show_isolate_others", None)
        if others is not None:  # TR99: the other bodies, see through or as edges
            look = self.isolate_look if self.isolated is not None else "hidden"
            others(self.isolate_others() if look != "hidden" else None, look)

    def isolate_others(self) -> Any:
        """The bodies Isolate leaves out (not hidden, not isolated), as one shape, or
        None (TR99)."""
        from fdcad.core.body_visibility import hidden_names, shown_shape, visible_indices

        report = self.session.report
        body = report.body if report is not None else None
        if body is None or self.isolated is None:
            return None
        hidden = hidden_names(self.session.document)
        isolated = set(visible_indices(body, hidden, self.isolated))
        rest = [i for i in visible_indices(body, hidden) if i not in isolated]
        return shown_shape(body, rest) if rest else None

    def see_through_solids(self) -> list[Any]:
        """The bodies drawn see through on their own (TR21), as solids of the part."""
        from fdcad.core.body_visibility import hidden_indices, see_through_names
        from fdcad.core.features.solids import solids

        report = self.session.report
        body = report.body if report is not None else None
        names = see_through_names(self.session.document)
        if body is None or not names:
            return []
        parts = solids(body.shape)
        return [parts[i] for i in hidden_indices(body, names) if i < len(parts)]

    def locked_solids(self) -> list[Any]:
        """The locked bodies (TR269), as solids of the part."""
        from fdcad.core.body_visibility import hidden_indices, locked_names
        from fdcad.core.features.solids import solids

        report = self.session.report
        body = report.body if report is not None else None
        names = locked_names(self.session.document)
        if body is None or not names:
            return []
        parts = solids(body.shape)
        return [parts[i] for i in hidden_indices(body, names) if i < len(parts)]

    def shown_part(self) -> Any:
        """The part's shape without its hidden bodies, or only the isolated ones (D410)."""
        from fdcad.core.body_visibility import hidden_names, shown_shape, visible_indices

        report = self.session.report
        body = report.body if report is not None else None
        if body is None:
            return None
        hidden = hidden_names(self.session.document)
        if not hidden and self.isolated is None:
            return body.shape
        return shown_shape(body, visible_indices(body, hidden, self.isolated))

    def show_sketch(self, canvas: QWidget) -> None:
        """Show the sketch editor in place of the 3D view."""
        self.hide_sketch()
        self.sketch_canvas = canvas
        canvas.setAccessibleName(strings_a11y.NAME_SKETCH)
        self.stack.addWidget(canvas)
        self.stack.setCurrentWidget(canvas)

    def hide_sketch(self) -> None:
        """Go back to the 3D view."""
        if self.sketch_canvas is not None:
            self.stack.removeWidget(self.sketch_canvas)
            self.sketch_canvas = None
        self.stack.setCurrentWidget(self.view_host)

    def _show(self, report: RebuildReport) -> None:
        self.selection = []  # picked shapes belong to the old part
        self.refresh_types()

    def refresh_types(self) -> None:
        """Draw the part and everything shown with it: planes, axes, points, sketches.

        View > Show Types redrew only the part, so turning Planes off left every plane
        on screen until the next rebuild (D1092)."""
        self.refresh_part()
        report = self.session.report
        if report is not None:
            from fdcad.ui.viewport.references import show_extras

            show_extras(self.viewport, report, self.session.document, self.hidden_types)
        self.refresh_sketches()

    def visible_sketch_ids(self) -> list[str]:
        """Sketches drawn in the 3D view: finished, unused or shown on purpose (C1)."""
        from fdcad.ui.main_window.visibility import visible_sketches

        report = self.session.report
        if report is None:
            return []
        s = self.session
        shown = s.shown | ({self.editing_sketch} if self.editing_sketch else set())
        return visible_sketches(s.document, report.results, s.hidden, shown)

    def axis_lines(self, sketch_id: str) -> dict[str, Any]:
        """The sketch's lines as 3D edges, by entity id (tiny kernel work, D75)."""
        from fdcad.core.sketch.display import line_edges

        report = self.session.report
        result = report.results.get(sketch_id) if report is not None else None
        if result is None or result.sketch is None:
            return {}
        return line_edges(result.sketch.model, result.sketch.plane)

    def refresh_sketches(self) -> None:
        """Draw the visible sketches and planes in the 3D view."""
        report = self.session.report
        if report is None:
            return
        show = getattr(self.viewport, "show_sketches", None)
        if show is not None:
            edges = report.sketch_edges
            ids = [] if self.sketches_hidden else self.visible_sketch_ids()
            threads = [report.thread_edges] if report.thread_edges is not None else []
            from fdcad.ui.sheet_metal.flow import bend_line_shapes

            extra = self.datum_shapes() + threads + bend_line_shapes(report)
            from fdcad.core.appearance import sketch_color

            drawn = [i for i in ids if i in edges]
            appearance = self.session.document.appearance
            colors = [sketch_color(appearance, i) for i in drawn] + [None] * len(extra)
            show([edges[i] for i in drawn] + extra, colors)
        planes = getattr(self.viewport, "show_reference_planes", None)
        if planes is not None:
            from fdcad.ui.main_window.plane_pick import plane_faces, plane_names

            plane_ids = set(self.visible_plane_ids())
            faces = {fid: face for fid, face in plane_faces(self).items() if fid in plane_ids}
            planes(faces, plane_names(self))

    def visible_plane_ids(self) -> list[str]:
        """Planes shown on purpose in the 3D view (D114); none while reference is hidden."""
        from fdcad.ui.main_window.visibility import visible_planes

        report = self.session.report
        if report is None or self.reference_hidden or "planes" in self.hidden_types:
            return []
        return visible_planes(
            self.session.document, report.results, self.session.shown, self.session.hidden
        )

    def visible_datum_ids(self) -> list[str]:
        """Reference axes, points and coordinate systems on show (P2.10, D251)."""
        from fdcad.ui.main_window.visibility import visible_datums

        report = self.session.report
        if report is None or self.reference_hidden:
            return []
        found = visible_datums(self.session.document, report.results, self.session.hidden)
        kinds = {"ref_axis": "axes", "ref_point": "points", "coord_system": "frames"}
        doc = self.session.document
        return [f for f in found if kinds.get(doc.feature(f).type, "") not in self.hidden_types]

    def datum_shapes(self) -> list[Any]:
        """Edges drawing the visible axes, points and coordinate systems (tiny, like D75)."""
        from fdcad.core.features.datum import datum_shape
        from fdcad.ui.main_window.plane_pick import part_half_size

        report = self.session.report
        if report is None:
            return []
        half = part_half_size(self)
        out = []
        for fid in self.visible_datum_ids():
            datum = report.results[fid].datum
            if datum is not None:
                out.append(datum_shape(datum, half))
        out += pattern_datum_shapes(self.session.document, report.results, half)
        return out


def pattern_datum_shapes(doc: Any, results: Any, half: float) -> list[Any]:
    """Edges of the reference geometry copied by patterns (TR142, D2402); an exploded
    plane copy is drawn as a plane face instead, so it is left out here."""
    from fdcad.core.features.pattern_datums import DATUM_PATTERN_TYPES, copy_shape

    out = []
    for feature in doc.features:
        result = results.get(feature.id)
        if feature.type not in DATUM_PATTERN_TYPES or feature.suppressed or result is None:
            continue
        if result.plane is not None:
            continue
        out += [copy_shape(datum, half) for _label, datum in result.extras.get("datums", [])]
    return out


def export_warning(doc: Any, report: Any) -> str:
    """What an export leaves out: features with errors, or those below the rollback bar
    (audit D3 item 4, D710). Empty when the file holds the whole part."""
    from fdcad.core.features.base import FeatureState

    if getattr(doc, "rollback", None):
        return strings.EXPORT_ROLLED_BACK
    if getattr(report, "simplified", None):  # TR347 (D1921)
        return strings.EXPORT_SIMPLIFIED
    failed = sum(1 for r in report.results.values() if r.state is FeatureState.ERROR)
    if failed:
        return strings.EXPORT_ERRORS.format(
            n=failed, s="s" if failed != 1 else "", are="are" if failed != 1 else "is"
        )
    return ""


def _round_face_reference(body: Any, face: Any) -> dict[str, Any] | None:
    """A reference to a cylinder or cone face, whose axis can be a revolve axis; None
    for other faces (D712)."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder
    from OCP.TopoDS import TopoDS

    from fdcad.core.naming.select import reference_for

    kind = BRepAdaptor_Surface(TopoDS.Face(face)).GetType()
    if kind not in (GeomAbs_Cylinder, GeomAbs_Cone):
        return None
    return reference_for(body, face)


class MainWindow(QMainWindow):
    """Top level window with document tabs, feature tree and property panel."""

    # Set by the install modules while the window is built (imports.py and
    # print_tools). Declared here for type checking only: no value at class level.
    import_flow: ImportFlow
    curvature_graph: CurvatureGraph
    print_orientation: OrientationTool
    build_volume: BuildVolume
    overhang_analysis: OverhangAnalysis
    wall_thickness: WallThicknessAnalysis
    draft_analysis: DraftAnalysis
    start_page: StartPage  # TR218 (D2504)
    #: Features FDCAD closed on last time, set at start (crash_guard, D1035).
    crash_suspects: list[Any]
    #: The status bar's Report Problem button after such a close, until used (D2871).
    crash_report: Any = None
    tab_customizer: TabCustomizer  # TR222 (D2508)
    print_fit: FitTool
    undercut_analysis: UndercutAnalysis
    edge_angle_analysis: EdgeAngleAnalysis
    layer_preview: LayerPreview
    pause_action: QAction
    _bodies_jobs: set[Any]
    print_estimate: PrintEstimate
    geometry_check: GeometryCheck

    def __init__(self, settings: Settings | None = None) -> None:
        super().__init__()
        from fdcad.ui import gc_guard

        gc_guard.install()  # collect cycles on the UI thread only (D639)
        self.settings = settings or Settings()
        from fdcad.ui.input import pick_size

        pick_size.set_size(self.settings.pick_size)  # TR313 (D917)
        motion.set_reduce_motion(self.settings.reduce_motion)
        from fdcad.ui.command_tabs import ribbon as _ribbon

        _ribbon.set_scale(1.5 if self.settings.large_controls else 1.0)  # TR294 (D2017)
        self.setWindowTitle(f"{strings.APP} {__version__}")
        screen = QGuiApplication.primaryScreen()
        self.resize(start_size(screen.availableSize() if screen is not None else None))
        self.tabs = QTabWidget()
        self.tabs.setObjectName("document_tabs")
        self.tabs.setTabsClosable(True)
        self.tabs.setDocumentMode(True)
        self.setCentralWidget(self.tabs)
        self.undo_group = QUndoGroup(self)
        self.status = QLabel(strings.READY)
        #: A status note to show instead of the next "Rebuilt in" (D708).
        self.note_after_rebuild = ""
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(180)
        # A slim bar without the percent (D2697): the figure was drawn in the text
        # colour over the accent fill, in a bar shorter than its own letters, and
        # the status text beside it already names the step.
        self.progress.setTextVisible(False)
        self.progress.hide()
        from fdcad.ui.main_window.status_bar import SketchStatusLabel, UnitSelector

        self.unit_button = UnitSelector()
        self.unit_button.unit_chosen.connect(self.set_units)
        self.unit_button.hide()
        self.sketch_status = SketchStatusLabel()
        self.coords = QLabel()
        self.coords.setObjectName("cursor_coordinates")
        self.coords.setFont(tabular(self.coords.font()))  # digits don't jump (U2.4)
        self.bodies = QLabel()
        # Left: messages. Right, in order: bodies, progress, sketch status,
        # cursor coordinates and the unit selector at the far right (L6).
        self.statusBar().addWidget(self.status, 1)
        self.statusBar().addPermanentWidget(self.bodies)
        self.statusBar().addPermanentWidget(self.progress)
        from fdcad.ui.main_window.feedback import StatusFeedback

        #: Delayed progress, Cancel and short confirmations (U8.1, U8.4).
        self.feedback = StatusFeedback(self)
        self.statusBar().addPermanentWidget(self.feedback.cancel_button)
        self.statusBar().addPermanentWidget(self.sketch_status)
        self.statusBar().addPermanentWidget(self.coords)
        self.statusBar().addPermanentWidget(self.unit_button)
        self.tree: FeatureTree | None = None
        self.panel: PropertyPanel | None = None
        self.preview: FeaturePreview | None = None
        self.variables: VariablesPanel | None = None
        self.left: LeftTabs | None = None
        self.properties: QStackedWidget | None = None
        self.sketch_mode: SketchMode | None = None
        self.errors: ErrorsPanel | None = None
        self.commands = CommandActions(self, self.settings)
        self.ready = False
        from fdcad.ui.main_window.dev_overlay import DevOverlays
        from fdcad.ui.main_window.window_details import WindowMemory

        #: Size, place and panel widths kept between runs (U9.1).
        self.memory = WindowMemory(self.settings.store)
        #: Frame and rebuild times in the view corner, behind a preference (U10.4).
        self.dev_overlays = DevOverlays(self)
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self.autosave)
        #: Low disk space and memory are checked once a minute (TR220, D968).
        self.resource_timer = QTimer(self)
        self.resource_timer.timeout.connect(self.check_resources)
        self.resource_timer.start(60_000)

    # Setup ----------------------------------------------------------------------------

    def _name_areas(self) -> None:
        """Accessible names for the main areas of the window (U4.3)."""
        names = strings_a11y
        assert self.tree is not None and self.panel is not None
        assert self.left is not None and self.variables is not None and self.errors is not None
        areas: tuple[tuple[QWidget, str], ...] = (
            (self.tree, names.NAME_TREE),
            (self.panel, names.NAME_PROPERTY_PANEL),
            (self.left, names.NAME_SIDE_PANEL),
            (self.variables, names.NAME_VARIABLES),
            (self.errors, names.NAME_ERRORS),
            (self.tabs, names.NAME_DOCUMENTS),
            (self.statusBar(), names.NAME_STATUS_BAR),
            (self.context_bar, names.NAME_QUICK_ACTIONS),
        )
        for widget, name in areas:
            widget.setAccessibleName(name)

    def finish_setup(self) -> None:
        """Load the heavy parts after the window is visible."""
        from fdcad.ui.property_panel.panel import PropertyPanel
        from fdcad.ui.property_panel.variables import VariablesPanel
        from fdcad.ui.tree.feature_tree import FeatureTree

        self.tree = FeatureTree()
        from fdcad.ui.tree.empty_hint import EmptyTreeHint

        self.empty_tree_hint = EmptyTreeHint(self.tree)  # what to do first (U8.3)
        self.tree.edit_requested.connect(self.edit_feature)
        self.tree.itemDoubleClicked.connect(self._appearance_row_clicked)
        self.tree.sketch_requested.connect(self._start_sketch_on_plane)
        self.tree.visibility_changed.connect(self._refresh_sketches)
        self.tree.body_requested.connect(lambda a, i: self.body_display.from_tree(a, i))
        self.tree.appearance_requested.connect(self.appearance_for)
        self.tree.message_shown.connect(self.status.setText)
        from fdcad.ui.main_window.feature_dims import ModelDimensions

        self.model_dims = ModelDimensions(self)
        self.tree.currentItemChanged.connect(self.model_dims.refresh)
        self.tree.itemClicked.connect(self.model_dims.clicked_in_tree)
        self.tree.currentItemChanged.connect(lambda *_a: self._plane_selection())
        self.tree.currentItemChanged.connect(lambda *_a: self._feature_edges())  # TR212
        from fdcad.ui.main_window.context_bar import ContextBar

        self.context_bar = ContextBar(self)
        self.tree.itemClicked.connect(self.context_bar.for_tree)
        from fdcad.ui.main_window.context_menu import ContextMenus

        self.context_menus = ContextMenus(self)
        from fdcad.ui.main_window.tree_follow import TreeFollow

        self.tree_follow = TreeFollow(self)  # TR200
        self.tree.normal_to_requested.connect(self.context_menus.normal_to_feature)
        self.panel = PropertyPanel()
        self.panel.escape_hook = self.stop_long_work  # type: ignore[attr-defined]  # TR126
        self.panel.started.connect(self._feature_started)
        self.panel.started.connect(self._show_feature_panel)  # D1040
        self.panel.finished.connect(self._feature_finished)
        self.panel.applied.connect(self._feature_applied)  # TR221 (D963)
        self.panel.again.connect(self.commands.repeat)  # TR206: Pin
        self.panel.finished.connect(lambda: self._left_tab(0))
        self.panel.finished.connect(self.update_corner)
        self.panel.started.connect(self.update_corner)
        self.panel.started.connect(self._undo_for_editing)
        self.panel.finished.connect(self._undo_for_editing)
        from fdcad.ui.viewport.preview import FeaturePreview

        self.preview = FeaturePreview(self)
        self.preview.bind(self.panel, lambda: self.current.viewport if self.current else None)
        self.variables = VariablesPanel()
        from fdcad.ui.main_window.left_tabs import LeftTabs

        # One icon per tab, the name as tooltip, so every tab fits (D436).
        self.left = LeftTabs()
        from fdcad.ui.tree.tree_filter import TreeFilter

        self.tree_filter = TreeFilter(self.tree)  # TR95
        self.left.addTab(self.tree_filter, strings.TAB_TREE)
        self.properties = QStackedWidget()
        self.properties.addWidget(self.panel)
        self.left.addTab(self.properties, strings.TAB_PROPERTIES)
        self.left.addTab(self.variables, strings.TAB_VARIABLES)
        from fdcad.ui.errors.panel import ErrorsPanel

        self.errors = ErrorsPanel()
        self.errors.highlight_requested.connect(self.highlight_names)
        self.errors.feature_requested.connect(self._open_from_errors)
        self.errors.fix_requested.connect(self.apply_fix)
        self.errors.count_changed.connect(self._errors_count)
        self.left.addTab(self.errors, strings.TAB_ERRORS)
        self._name_areas()
        dock = QDockWidget(self)
        dock.setObjectName("left_panel")
        dock.setTitleBarWidget(QWidget())
        dock.setWidget(self.left)
        dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        em = self.fontMetrics().horizontalAdvance("M")
        # The tree may be made narrow (IDEAS 19, D1033): the panel widens itself while
        # a property panel that needs more room is open (_fit_left_panel).
        self.left.setMinimumWidth(max(200, 18 * em))
        self.left_dock = dock
        self._left_width_before: int | None = None
        self._fitters: list[Any] = []
        self.resizeDocks([dock], [self.default_left_width()], Qt.Orientation.Horizontal)
        # After the panel has laid out its fields, so their width is known.
        self.panel.started.connect(lambda: QTimer.singleShot(0, self._fit_while_editing))
        self.panel.finished.connect(lambda: self._fit_left_panel(False))
        self.left.currentChanged.connect(self._fit_left_tab)
        self.fit_panels()  # and from now on whenever a panel's layout changes (D2791)
        from fdcad.ui.main_window.sketch_mode import SketchMode

        self.sketch_mode = SketchMode(self)
        from fdcad.ui.reference_geometry.tool import ReferenceTool

        #: Reference plane, axis, point and coordinate system panels (P2.10).
        self.reference_tool = ReferenceTool(self)
        from fdcad.ui.main_window.sketch_drag import SketchDragTool

        #: Extrude by dragging a sketch region without the panel (T5.4, D525).
        self.sketch_drag = SketchDragTool(self)
        from fdcad.ui.measure.tool import MeasureTool

        #: The Measure box and the selection values in the status bar (P2.12).
        self.measure_tool = MeasureTool(self)
        from fdcad.ui.section.tool import SectionTool

        #: Section view of each open part, a view state (P2.13).
        self.section_tool = SectionTool(self)
        from fdcad.ui.appearance.tool import AppearanceTool

        #: Part, body, feature and face colours (P2.11).
        self.appearance_tool = AppearanceTool(self)
        self._build_menus()
        self._build_command_tabs()
        self.tabs.currentChanged.connect(self._tab_changed)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.autosave_timer.start(self.settings.autosave_minutes * 60_000)
        self.memory.restore_state(self)  # the left panel width from the last run (U9.1)
        self.ready = True

    def _action(
        self, menu: Any, text: str, slot: Callable[[], object], shortcut: Any = None
    ) -> QAction:
        action = QAction(text, self)
        if shortcut is not None:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(lambda _checked=False: slot())
        menu.addAction(action)
        return action

    def _build_menus(self) -> None:
        a = self.commands
        assert self.tree is not None
        bar = self.menuBar()
        file = bar.addMenu(strings.MENU_FILE)
        file.addAction(a.add("file.new", self.new_part))
        file.addAction(a.add("file.open", self.open_dialog))
        self.recent_menu = file.addMenu(strings.MENU_RECENT)
        self.recent_menu.aboutToShow.connect(self._fill_recent)
        self.sample_menu = file.addMenu(strings.MENU_SAMPLES)
        self.sample_menu.aboutToShow.connect(self._fill_samples)
        file.addSeparator()
        file.addAction(a.add("file.save", self.save))
        file.addAction(a.add("file.save_as", self.save_as_any))
        file.addAction(a.add("file.save_increment", self.save_increment))  # TR305
        file.addAction(a.add("file.save_copy", self.save_copy))  # TR97
        file.addAction(a.add("file.save_copy_open", lambda: self.save_copy(open_it=True)))
        from fdcad.ui.main_window.templates import save_as_template

        file.addAction(a.add("file.save_template", lambda: save_as_template(self)))  # TR217
        from fdcad.ui.main_window.mirror_part import mirror_part

        file.addAction(a.add("file.mirror_part", lambda: mirror_part(self)))  # TR73
        from fdcad.ui.main_window.save_image import save_image

        file.addAction(a.add("file.save_image", lambda: save_image(self)))  # TR24
        export = file.addMenu(strings.MENU_EXPORT)
        self._action(export, strings.EXPORT_STEP, lambda: self.export("step"))
        self._action(export, strings.EXPORT_STL, lambda: self.export("stl"))
        self._action(export, strings.EXPORT_3MF, lambda: self.export("3mf"))
        from fdcad.ui.main_window.export_configs import export_configurations

        export.addAction(a.add("file.export_configs", lambda: export_configurations(self)))
        from fdcad.ui.main_window.export_variants import batch_export

        export.addAction(a.add("file.batch_export", lambda: batch_export(self)))  # TR368
        from fdcad.ui import strings_sheetmetal
        from fdcad.ui.build123d_export import export_build123d

        self._action(export, strings_sheetmetal.EXPORT_BUILD123D, lambda: export_build123d(self))
        from fdcad.ui import print_tools

        print_tools.install(self, export)  # Phase 2 print and evaluate tools (D350)
        file.addSeparator()
        file.addAction(a.add("file.close", lambda: self.close_tab(self.tabs.currentIndex())))
        file.addAction(a.add("file.save_all", self.save_all))  # TR218 (D961)
        file.addAction(a.add("file.close_all", self.close_all))
        file.addAction(a.add("file.revert", self.revert_to_saved))
        file.addAction(a.add("file.open_view_only", lambda: self.open_view_only()))  # TR356
        quit_action = self._action(file, strings.QUIT, self.close, QKeySequence.StandardKey.Quit)
        quit_action.setMenuRole(QAction.MenuRole.QuitRole)  # the Mac application menu (TR376)

        edit = bar.addMenu(strings.MENU_EDIT)
        edit.addAction(a.adopt("edit.undo", self.undo_group.createUndoAction(self, strings.UNDO)))
        edit.addAction(a.adopt("edit.redo", self.undo_group.createRedoAction(self, strings.REDO)))
        self.undo_menu = edit.addMenu(strings.UNDO_TO)  # TR208
        self.undo_menu.setObjectName("undo_to")
        self.undo_menu.aboutToShow.connect(self.fill_undo_menu)
        edit.addAction(a.add("edit.repeat", self._enter, scope=self.tabs))
        edit.addSeparator()
        edit.addAction(a.add("edit.delete", self.tree.delete_selected, scope=self.tree))
        # Delete in the 3D view with faces picked offers Delete Feature or Delete Face (TR201).
        self.view_delete = QAction(self.tabs)
        self.view_delete.setShortcuts(a.actions["edit.delete"].shortcuts())
        self.view_delete.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.view_delete.triggered.connect(lambda _c=False: self.delete_in_view())
        self.tabs.addAction(self.view_delete)
        # Copy and paste of sketches and features (TR3.2, TR9). The open sketch takes
        # the same keys for its own entities while it has focus (TR3.1).
        from fdcad.ui.main_window.feature_clipboard import FeatureClipboard

        self.feature_clipboard = FeatureClipboard(self)
        from fdcad.ui.main_window.file_drop import FileDrop

        self.file_drop = FileDrop(self)  # drop files on the window to open them (TR377)
        self.file_drop.watch(self)
        if self.tree is not None:
            self.file_drop.watch(self.tree.viewport())
        edit.addAction(a.add("edit.copy", self.feature_clipboard.copy_command))
        edit.addAction(a.add("edit.paste", self.feature_clipboard.paste_command))
        edit.addAction(a.add("edit.appearance", self.appearance_tool.open))
        edit.addAction(a.add("edit.copy_appearance", self.appearance_tool.copy))
        edit.addAction(a.add("edit.paste_appearance", self.appearance_tool.paste))
        edit.addAction(a.add("edit.rebuild", self.rebuild))
        edit.addAction(a.add("edit.force_rebuild", self.force_rebuild))
        from fdcad.ui.main_window.pause_rebuilds import install as pause_install

        pause_install(self, edit)  # TR276
        edit.addSeparator()
        edit.addAction(a.add("tree.find", lambda: self._tree_find()))
        a.add("tree.top", self.tree.scrollToTop, scope=self.tree)
        a.add("tree.bottom", self.tree.scrollToBottom, scope=self.tree)
        self.flat_tree_action = a.add("tree.flat", self.toggle_flat_tree, checkable=True)
        rolls = edit.addMenu(strings_extra.ROLLBACK_MENU)
        rolls.addAction(a.add("tree.roll_back", self.tree.roll_back_one))
        rolls.addAction(a.add("tree.roll_forward", self.tree.roll_forward))
        rolls.addAction(a.add("tree.roll_previous", self.tree.roll_previous))
        rolls.addAction(a.add("tree.roll_end", self.tree.roll_end))
        from fdcad.ui.tree import purge as purge_ui

        def session_now() -> Any:
            return getattr(self.current, "session", None)

        def report(message: str) -> None:
            self.statusBar().showMessage(message)

        rolls.addAction(  # TR159 (D956)
            a.add(
                "tree.delete_below_bar",
                lambda: purge_ui.delete_below_bar(session_now(), self, report),
            )
        )
        edit.addAction(
            a.add("tree.purge_unused", lambda: purge_ui.purge_unused(session_now(), self, report))
        )
        from fdcad.ui.main_window.remove_history import RemoveHistory

        #: Remove History (TR158, D983).
        self.remove_history = RemoveHistory(self)
        edit.addAction(a.add("tree.remove_history", self.remove_history.run))
        from fdcad.ui.tree import copy_values as copy_ui

        edit.addAction(  # TR160 (D957)
            a.add("edit.edit_by_rule", lambda: copy_ui.edit_by_rule(session_now(), self, report))
        )

        view = bar.addMenu(strings.MENU_VIEW)
        for name in (
            "front",
            "back",
            "left",
            "right",
            "top",
            "bottom",
            "iso",
            "dimetric",
            "trimetric",
        ):
            view.addAction(a.add(f"view.{name}", partial(self.set_view, name)))
        from fdcad.ui.main_window.saved_views import SavedViews

        #: Save View and the saved views (TR14.2).
        self.saved_views = SavedViews(self)
        view.addAction(a.add("view.save_view", lambda: self.saved_views.save()))
        from fdcad.ui.main_window.view_frame import ViewFrame

        #: Home, Set Current View As and Reset Standard Views (TR333).
        self.view_frame = ViewFrame(self)
        view.addAction(a.add("view.home", lambda: self.view_frame.look("home")))
        view.addAction(a.add("view.set_view_as", lambda: self.view_frame.set_current_as()))
        view.addAction(a.add("view.reset_views", self.view_frame.reset))
        saved_menu = view.addMenu(strings.SAVED_VIEWS)

        def fill_saved() -> None:
            saved_menu.clear()
            self.saved_views.fill(saved_menu)

        saved_menu.aboutToShow.connect(fill_saved)
        view.addAction(a.add("view.normal_to", self.normal_to))
        split_menu = view.addMenu(strings.SPLIT_VIEW)  # TR16
        split_group = QActionGroup(self)
        for name in ("one", "side", "stacked", "four"):
            action = a.add(f"view.split_{name}", partial(self.set_split, name), checkable=True)
            action.setChecked(name == "one")
            split_group.addAction(action)
            split_menu.addAction(action)
        view.addAction(a.add("view.selector", self.show_view_selector))
        view.addAction(a.add("view.orientation", self.show_orientation_popup))  # TR210
        view.addAction(a.add("view.display_quality", self.display_quality))  # TR214
        view.addAction(a.add("view.display_states", self.display_states))  # TR88
        view.addSeparator()
        view.addAction(a.add("view.hide_show", self.hide_or_show))
        from fdcad.ui.main_window.body_display import BodyDisplay

        #: Isolate, hide and show bodies (P3.4 item 6, D410).
        self.body_display: BodyDisplay = BodyDisplay(self)
        bodies = view.addMenu(text3.BODIES_MENU)
        bodies.addAction(a.add("view.isolate", self.body_display.isolate))
        bodies.addAction(a.add("view.show_hovered", lambda: self.body_display.show_hovered()))
        bodies.addAction(a.add("view.show_all_bodies", self.body_display.show_all))
        view.addAction(a.add("view.hide_reference", self.toggle_reference_geometry))
        view.addAction(self.flat_tree_action)
        if self.tree is not None:  # TR221 (D1611): no default key, the owner chooses it
            view.addAction(a.add("tree.collapse_all", self.tree.collapseAll))
        view.addSeparator()
        view.addAction(a.add("view.fit", self.zoom_to_fit))
        from fdcad.ui.accessibility import show_description

        view.addAction(a.add("view.describe_part", lambda: show_description(self)))  # TR294
        from fdcad.ui.compare_tool import show_changes

        view.addAction(a.add("view.before_after", lambda: show_changes(self)))  # TR289
        view.addAction(a.add("view.zoom_area", self.zoom_to_area))
        view.addAction(a.add("view.zoom_selection", self.zoom_to_selection))
        view.addAction(a.add("view.zoom_in", self.zoom_in))
        view.addAction(a.add("view.zoom_out", self.zoom_out))  # TR211
        view.addAction(a.add("view.previous", self.previous_view))
        view.addAction(a.add("view.redraw", self.redraw))
        view.addSeparator()
        styles = QActionGroup(self)
        style_menu = view.addMenu(strings.DISPLAY_STYLE)
        for style in DISPLAY_STYLES:
            action = a.add(f"view.{style}", partial(self.set_style, style), checkable=True)
            action.setChecked(style == "shaded_edges")
            styles.addAction(action)
            style_menu.addAction(action)
        view.addAction(a.add("view.transparency", self.toggle_transparency, checkable=True))
        view.addAction(a.add("view.perspective", self.toggle_perspective, checkable=True))
        view.addAction(
            a.add("view.temporary_axes", self.toggle_temporary_axes, checkable=True)  # TR17
        )
        view.addAction(a.add("view.mirror_image", self.toggle_mirror_image, checkable=True))
        all_dims = a.add(
            "view.all_dimensions",
            lambda: self.model_dims.set_show_all(
                self.commands.actions["view.all_dimensions"].isChecked()
            ),
            checkable=True,
        )  # TR32
        view.addAction(all_dims)
        if self.tree is not None:
            self.tree.part_actions.append(all_dims)
            material = a.add("tools.material", self.edit_material)  # TR78
            self.tree.part_actions.append(material)
            props = a.add("tools.properties", self.edit_properties)  # TR82
            self.tree.part_actions.append(props)
            self.tree.material_requested.connect(self.edit_material)
        self._build_show_menu(view)
        self._build_filters(view.addMenu(strings.SELECTION_FILTER))
        view.addSeparator()
        view.addAction(a.add("view.section", self.section_tool.toggle, checkable=True))
        view.addAction(a.add("ui.toggle_left", self.toggle_left_panel))
        view.addAction(a.add("ui.toggle_toolbars", self.toggle_command_tabs))
        view.addAction(a.add("ui.fullscreen", self.toggle_fullscreen))
        a.add("ui.confirm_corner", self.corner_at_cursor)
        a.add("ui.context_menu", lambda: self.context_menus.for_selection())
        a.add("ui.next_tab", lambda: self._step_command_tab(1))
        a.add("ui.previous_tab", lambda: self._step_command_tab(-1))
        # TR22 (D683, D687): only while the 3D view (in the document tabs) or the tree has focus.
        for cid, step in (("ui.next_part", 1), ("ui.previous_part", -1)):
            action = a.add(cid, partial(self.step_part, step), scope=self.tabs)
            if self.tree is not None:
                self.tree.addAction(action)

        insert = bar.addMenu(strings.MENU_INSERT)
        self._insert_actions(insert)
        from fdcad.ui.body_tools import flow as phase3

        phase3.register(self)  # Phase 3 commands (ui/body_tools/flow.py)
        insert.addSeparator()
        for cid in phase3.COMMAND_TYPES:
            insert.addAction(self.commands.actions[cid])
        from fdcad.ui.main_window import imports

        imports.install(self, insert)
        from fdcad.ui.sheet_metal import flow as sheet_metal

        sheet_metal.register(self)  # Sheet Metal tab commands (ui/sheet_metal/flow.py)
        insert.addSeparator()
        for cid in sheet_metal.COMMANDS:
            insert.addAction(self.commands.actions[cid])
        tools = bar.addMenu(strings.MENU_TOOLS)
        tools.addAction(a.add("ui.shortcut_bar", self.show_shortcut_bar))
        tools.addAction(a.add("tools.stats", self.show_stats))
        tools.addAction(a.add("evaluate.measure", self.measure_tool.toggle))
        from fdcad.ui.node_editor import install as node_editor

        node_editor.install(self, tools)  # Phase 7 (ui/node_editor/install.py)
        from fdcad.ui.equations import install as equations

        equations.install(self, tools)  # equations, configurations (ui/equations)
        from fdcad.ui.main_window import zebra

        self.zebra = zebra.install(self)  # TR18
        from fdcad.ui.main_window import curvature_colors

        self.curvature_colors = curvature_colors.install(self)  # TR199 (D2503)
        from fdcad.ui.main_window import start_page

        start_page.install(self)  # TR218 item 2 (D2504)
        from fdcad.ui.main_window import compare_bodies

        self.compare_bodies = compare_bodies.install(self)  # TR27
        from fdcad.ui.main_window import mass_properties

        self.mass_properties = mass_properties.install(self)  # TR79
        from fdcad.ui.main_window import interference_tool

        self.interference = interference_tool.install(self)  # TR150
        from fdcad.ui.main_window import cavities_tool

        self.cavities = cavities_tool.install(self)  # TR284
        from fdcad.ui.main_window import change_test_tool

        self.change_test = change_test_tool.install(self)  # TR287
        from fdcad.ui.main_window import health_tool

        self.model_health = health_tool.install(self)  # TR286
        from fdcad.ui.main_window import repair_tool

        self.repair_references = repair_tool.install(self)  # TR125
        from fdcad.ui.main_window import manufacturing_tool

        self.manufacturing = manufacturing_tool.install(self)  # TR295
        tools.addSeparator()
        preferences = a.add("ui.preferences", self.preferences)
        preferences.setMenuRole(QAction.MenuRole.PreferencesRole)  # TR376
        tools.addAction(preferences)
        from fdcad.ui.main_window.mac_menus import build_window_menu

        self.window_menu = build_window_menu(self, bar)  # Mac only (TR376)
        help_menu = bar.addMenu(strings.MENU_HELP)
        from fdcad.ui.help import HelpMenu

        #: Welcome, user guide, shortcuts list and About (D551 to D554).
        self.help = HelpMenu(self, help_menu)
        if self.panel is not None:  # TR291 item 1 (D2018): the panel's help and hints
            self.panel.help_requested.connect(lambda: self.help.help_for_tool())
            self.panel.hint_store = self.settings.store
        from fdcad.ui.main_window.menu_keys import MenuLetters

        #: Letter keys inside open menus (TR205, D916).
        self.menu_letters = MenuLetters(self)
        self.menu_letters.watch_bar(bar)

    def _insert_actions(self, target: Any) -> None:
        a = self.commands
        for cid, ftype, operation in (
            ("feature.extrude", "extrude", "boss"),
            ("feature.extruded_cut", "extrude", "cut"),
            ("feature.revolve", "revolve", "boss"),
            ("feature.revolved_cut", "revolve", "cut"),
            *PHASE2_INSERTS,
            *PHASE4_INSERTS,
        ):
            action = a.actions.get(cid) or a.add(
                cid, partial(self.insert_feature, ftype, operation), repeatable=True
            )
            target.addAction(action)
        reference = target.addMenu(strings.GROUP_REFERENCE)
        for cid, ftype in REFERENCE_COMMANDS:
            action = a.actions.get(cid) or a.add(
                cid, partial(self.reference_tool.start, ftype), repeatable=True
            )
            reference.addAction(action)

    def _build_command_tabs(self) -> None:
        from fdcad.ui.command_tabs.ribbon import RibbonPanel
        from fdcad.ui.command_tabs.tabs import (
            CommandTabs,
            build_bodies_panel,
            build_evaluate_panel,
            build_features_panel,
            build_print_panel,
            remember_groups,
        )

        tabs = CommandTabs(self.commands)
        tabs.add_panel(build_features_panel(self.commands.actions), strings.TAB_FEATURES)
        if self.sketch_mode is not None:
            tabs.add_panel(self.sketch_mode.toolbar, strings.TAB_SKETCH)
        tabs.add_panel(build_bodies_panel(self.commands.actions), strings.TAB_BODIES)
        tabs.add_panel(build_print_panel(self.commands.actions), strings.TAB_PRINT)
        from fdcad.ui import strings_sheetmetal
        from fdcad.ui.sheet_metal.flow import build_tab

        tabs.add_panel(build_tab(self.commands.actions), strings_sheetmetal.TAB_SHEET_METAL)
        tabs.add_panel(build_evaluate_panel(self.commands.actions), strings.TAB_EVALUATE)
        from fdcad.ui.node_editor import install as node_editor
        from fdcad.ui.node_editor import strings as node_strings

        tabs.add_panel(node_editor.build_graph_panel(self.commands.actions), node_strings.TAB_GRAPH)
        tabs.apply_saved_order()
        for i in range(tabs.count()):
            panel = tabs.widget(i)
            if isinstance(panel, RibbonPanel):
                remember_groups(panel, self.commands.actions, self.settings)
        tabs.refresh()
        tabs.icons_changed.connect(self._icons_changed)
        from fdcad.ui.input.commands import search_words
        from fdcad.ui.main_window.command_search import CommandSearch

        actions = self.commands.actions

        def words() -> dict[int, str]:
            overrides = self.settings.search_words
            return {id(a): search_words(c, overrides) for c, a in actions.items()}

        # Find any command by name or search word, at the top right (owner request).
        self.command_search = CommandSearch(lambda: list(actions.values()), words, self)
        self.command_search.setAccessibleName(strings_a11y.NAME_SEARCH)
        tabs.setCornerWidget(self.command_search, Qt.Corner.TopRightCorner)
        tabs.setMaximumHeight(tabs.sizeHint().height())
        holder = QToolBar()
        holder.setObjectName("command_tabs")
        holder.setMovable(False)
        holder.addWidget(tabs)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, holder)
        self.command_tabs = tabs
        self.command_holder = holder
        from fdcad.ui.command_tabs import custom

        custom.install(self)  # TR222 (D2508): My Commands, hidden buttons, simple mode

    def _icons_changed(self) -> None:
        """The theme changed: recolour the icons outside the command tabs."""
        from fdcad.ui.main_window.view_bar import refresh_view_bar

        if self.tree is not None:
            self.tree.refresh()
        if self.left is not None:
            self.left.refresh_icons()
        if self.panel is not None:
            self.panel.refresh_icons()  # Help and Pin in the header (D2701)
        self.sketch_status.restyle()
        from fdcad.ui.icons import icon

        bar = self.tabs.tabBar()
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if isinstance(tab, DocumentTab):
                refresh_view_bar(tab)
                tab.message_bars.restyle()  # the bars sit on the view's top colour
            close = bar.tabButton(i, self._close_side())
            if close is not None and close.objectName() == "tab_close":
                close.setIcon(icon("ui.close_tab"))  # type: ignore[attr-defined]
        self.update_corner()

    # Documents --------------------------------------------------------------------------

    @property
    def current(self) -> DocumentTab | None:
        """The active document tab."""
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, DocumentTab) else None

    def add_session(self, session: DocumentSession) -> DocumentTab:
        """Show a session in a new tab and rebuild it."""
        self._name_untitled(session)  # Untitled 2 and so on (D2682)
        session.engine.full_sketches_only = self.settings.full_sketches_only  # TR36 item 6
        session.engine.simplify_threads = self.settings.simplify_threads  # TR347 (D1921)
        self._set_printer(session)  # TR180
        tab = DocumentTab(session)
        tab.message_bars.settings = self.settings  # TR203: Don't Show Again is kept
        from fdcad.ui.main_window import pause_rebuilds

        session.pause_changed.connect(lambda: pause_rebuilds.show(self))  # TR276
        session.rebuilt.connect(  # after the usual "Rebuilt in" message
            lambda _r, s=session: (
                QTimer.singleShot(0, lambda: pause_rebuilds.show(self)) if s.stopped_at else None
            )
        )
        tab.hidden_types = {  # View > Show Types applies to new parts too (TR215)
            k for k, a in getattr(self, "type_actions", {}).items() if not a.isChecked()
        }
        self._fill_view_bar(tab)
        viewport = tab.viewport
        if hasattr(viewport, "gesture"):
            viewport.gesture.connect(lambda dx, dy: self.commands.gesture("part", dx, dy))
            viewport.context_menu.connect(lambda pos: self.viewport_menu(pos))
            viewport.label_double_clicked.connect(self.model_dims.edit)
            viewport.selection_changed.connect(self.context_bar.for_faces)
            viewport.escape_pressed.connect(self._escape)
            viewport.escape_pressed.connect(self.sketch_drag.cancel)
            viewport.left_clicked.connect(lambda pos: self.sketch_drag.clicked(tab, pos))
            viewport.axis_picked.connect(self._axis_picked)
            viewport.selection_changed.connect(lambda shapes: self._selection_changed(tab, shapes))
            viewport.cursor_point.connect(lambda point: self.model_cursor(tab, point))
            model = getattr(self, "selection_filter", None)
            viewport.set_filters(self._filters(), model is not None and model.is_on())
            viewport.gesture_with_ctrl = self.settings.navigation.value == "trackpad"
            viewport.turn_ms = self.view_turn_ms()
            viewport.gesture_tracker.source = lambda: self.commands.gesture_labels("part")
            viewport.lock_up = self.settings.lock_up  # TR209
            viewport.arcball = self.settings.turn_style == "arcball"  # TR415
            from fdcad.ui.main_window import view_prefs

            view_prefs.apply_to(viewport, self.settings.store)  # round 12 view options
            viewport.turn_centre_changed.connect(
                lambda point: self.status.setText(
                    strings.TURN_CENTRE_SET if point is not None else strings.TURN_CENTRE_CLEARED
                )
            )
        shown = getattr(self, "show_sketches_action", None)
        tab.sketches_hidden = shown is not None and not shown.isChecked()
        origins = getattr(self, "show_origins_action", None)
        if origins is not None and origins.isChecked():
            tab.origin_shown = True
            fn = getattr(viewport, "set_origin_shown", None)
            if fn is not None:
                fn(True)
        session.changed.connect(lambda: self._retitle(tab))

        # Weak, so the undo stack never keeps a closed tab (and its part) alive.
        tab_ref = weakref.ref(tab)

        def retitle_when_saved(_clean: bool) -> None:
            # The session can outlive this window (tests, closing); skip then.
            current = tab_ref()
            if current is not None and shiboken6.isValid(self) and shiboken6.isValid(current):
                self._retitle(current)

        session.undo.cleanChanged.connect(retitle_when_saved)  # the unsaved mark (U9.3)
        self.dev_overlays.attach(tab)
        self.feature_clipboard.watch(viewport)  # Ctrl and drag a tree row onto a face (TR9.3)
        self.file_drop.watch(viewport)  # files dropped on the view open (TR377)
        offset_drag = getattr(viewport, "plane_offset_dragged", None)
        if offset_drag is not None:  # Ctrl and drag a plane's border (TR10)
            offset_drag.connect(self.offset_plane_from_drag)
        axes = self.commands.actions.get("view.temporary_axes")
        if axes is not None and axes.isChecked() and hasattr(viewport, "set_temporary_axes"):
            viewport.set_temporary_axes(True)
        lasso = self.commands.actions.get("select.lasso")
        if lasso is not None and lasso.isChecked() and hasattr(viewport, "set_lasso"):
            viewport.set_lasso(True)
        paint = self.commands.actions.get("select.paint")  # TR329 (D2208)
        if paint is not None and paint.isChecked() and hasattr(viewport, "set_paint"):
            viewport.set_paint(True)
        perspective = self.commands.actions.get("view.perspective")
        if perspective is not None and perspective.isChecked():
            fn = getattr(viewport, "set_perspective", None)
            if fn is not None:
                fn(True)
        session.display_changed.connect(tab.refresh_sketches)
        session.display_changed.connect(tab.refresh_part)
        if self.tree is not None:
            session.display_changed.connect(self._refresh_tree_for(session))
        session.rebuild_started.connect(lambda: self._rebuild_started(tab))
        session.rebuild_progress.connect(lambda i, n, name: self._progress(tab, i, n, name))
        session.rebuilt.connect(lambda report: self._rebuilt(tab, report))
        self.undo_group.addStack(session.undo)
        index = self.tabs.addTab(tab, session.title.replace("&", "&&"))  # keep a & (D738)
        self._add_close_button(tab)
        self.tabs.setCurrentIndex(index)
        self._tab_changed(index)
        section = getattr(self, "section_tool", None)
        if section is not None:
            section.restore_saved(tab)  # a section saved with the part (TR213)
        self._show_load_warnings(tab)
        from fdcad.ui.main_window import crash_guard

        crash_guard.apply(self, session, tab)  # D1035: stop before a feature that crashed
        session.helper_lost.connect(  # D2600: the rebuild helper ended on a feature
            lambda fid, name: crash_guard.helper_lost(session, tab, fid, name)
        )
        session.request_rebuild()
        self._drop_unused_blank(tab)
        return tab

    def _show_load_warnings(self, tab: DocumentTab) -> None:
        """A warning bar listing what opening the file left out or changed, such as
        a damaged configuration entry (audit D3 item 21, D2678). Shown once: the
        notes are taken from the document, so they never show again for this part."""
        notes = list(tab.session.document.load_warnings)
        tab.session.document.load_warnings.clear()
        if not notes:
            return
        bar = tab.message_bars.show_message(
            "load_warnings",
            strings.LOAD_WARNINGS_BAR.format(
                name=tab.session.title.rstrip("*"), notes=" ".join(notes)
            ),
            "warning",
        )
        if bar is not None:
            bar.never_button.hide()  # each damaged file is its own news

    def _drop_unused_blank(self, keep: DocumentTab) -> None:
        """Close the empty part made at start once another part opens, if it was never
        touched, so opening a file does not leave a spare Untitled tab (D1033)."""
        for i in reversed(range(self.tabs.count())):
            other = self.tabs.widget(i)
            if other is keep or not isinstance(other, DocumentTab):
                continue
            if _unused_blank(other.session):
                self.close_tab(i, ask=False)

    def _name_untitled(self, session: DocumentSession) -> None:
        """A new part with no file and no name is called Untitled, or Untitled 2 and so
        on when an open part has that name, so tabs, the window title and the close
        prompt tell new parts apart (bug hunt O10a-9, D2682). The empty start part
        about to close (D1033) does not count."""
        from fdcad.ui.session import free_untitled

        if session.path is not None or session.name:
            return
        used = set()
        for i in range(self.tabs.count()):
            other = self.tabs.widget(i)
            if isinstance(other, DocumentTab) and not _unused_blank(other.session):
                used.add(other.session.title.rstrip("*").casefold())
        session.untitled = free_untitled(used)

    def _fit_left_tab(self, index: int) -> None:
        """Widen the left panel for a tab that asks for room (Variables), and put the
        width back when another tab shows (D1034)."""
        if self.left is None or (self.panel is not None and self.panel.is_editing):
            return
        dock = self.left_dock
        want = int(getattr(self.left.widget(index), "preferred_width", 0) or 0)
        if want and dock.width() < want and self._left_width_before is None:
            self._left_width_before = dock.width()
            self.resizeDocks([dock], [want], Qt.Orientation.Horizontal)
        elif not want and self._left_width_before is not None:
            width, self._left_width_before = self._left_width_before, None
            self.resizeDocks([dock], [width], Qt.Orientation.Horizontal)

    def _fit_while_editing(self) -> None:
        if self.panel is not None and self.panel.is_editing:
            self._fit_left_panel(True)

    def default_left_width(self) -> int:
        """The width the left panel starts with (D1033): 22 em, 260 px or more."""
        return max(260, 22 * self.fontMetrics().horizontalAdvance("M"))

    def fit_panels(self) -> bool:
        """Fit the open tool's panel to the left panel's default width (D2791): the
        feature panel's groups and every other panel shown in its place. True when all
        fit. Runs again by itself when a panel's layout changes."""
        from PySide6.QtWidgets import QStyle

        from fdcad.ui.property_panel.narrow import Fitter

        if self.properties is None or self.panel is None:
            return True
        if not self._fitters:
            from fdcad.ui.property_panel.columns import set_narrow

            set_narrow(self.panel.groups_box)
            bar = self.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
            self._fitters = [
                Fitter(self.panel.groups_box, lambda: self.default_left_width() - bar - 2),
                Fitter(self.properties, self.default_left_width),
            ]
        if self.panel.is_editing:
            self.panel.align_columns()
        return all([fitter.run() for fitter in self._fitters])

    def panel_width_needed(self) -> int:
        """The least width the left panel needs to show the open property panel."""
        if self.properties is None:
            return 0
        need = int(self.properties.minimumSizeHint().width())
        groups = getattr(self.panel, "groups_box", None)
        if groups is not None:  # the fields scroll up and down only: fit their width
            from PySide6.QtWidgets import QStyle

            bar = self.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
            need = max(need, groups.minimumSizeHint().width() + bar + 2)
        return need

    def _fit_left_panel(self, editing: bool) -> None:
        """Widen the left panel to fit an open property panel, and put the width back
        when the panel closes (D1033)."""
        dock = self.left_dock
        if self.properties is None:
            return
        if editing:
            # Never wider than the default for a panel (D2791): its rows are fitted to
            # that width first. A user who made the panel wider keeps that width.
            self.fit_panels()
            need = min(self.panel_width_needed(), self.default_left_width())
            if dock.width() < need and self._left_width_before is None:
                self._left_width_before = dock.width()
                self.resizeDocks([dock], [need], Qt.Orientation.Horizontal)
        elif self._left_width_before is not None:
            width, self._left_width_before = self._left_width_before, None
            self.resizeDocks([dock], [width], Qt.Orientation.Horizontal)

    def _add_close_button(self, tab: DocumentTab) -> None:
        """A close button in the theme's colours on the document tab (D111)."""
        from PySide6.QtCore import QSize
        from PySide6.QtWidgets import QToolButton

        from fdcad.ui.command_tabs.ribbon import small_icon_size
        from fdcad.ui.icons import icon

        button = QToolButton()
        button.setObjectName("tab_close")
        button.setAutoRaise(True)
        size = small_icon_size(button)
        button.setIconSize(QSize(size * 3 // 4, size * 3 // 4))
        # A 24 by 24 px hit area or more, even though the icon is small (U3.3).
        side = max(size, 6 * unit(button.font()))
        button.setFixedSize(QSize(side, side))
        button.setIcon(icon("ui.close_tab"))
        button.setToolTip(strings.CLOSE_TAB)
        button.clicked.connect(lambda: self.close_tab(self.tabs.indexOf(tab)))
        self.tabs.tabBar().setTabButton(self.tabs.indexOf(tab), self._close_side(), button)

    def _close_side(self) -> Any:
        """The side of a document tab where the style puts its close button."""
        from PySide6.QtWidgets import QStyle, QTabBar

        bar = self.tabs.tabBar()
        hint = bar.style().styleHint(QStyle.StyleHint.SH_TabBar_CloseButtonPosition, None, bar)
        return QTabBar.ButtonPosition(hint)

    def _retitle(self, tab: DocumentTab) -> None:
        index = self.tabs.indexOf(tab)
        if index >= 0:
            title = tab.session.title
            if tab.session.view_only:  # TR356
                title = strings.VIEW_ONLY_TAB.format(name=title)
            self.tabs.setTabText(index, title.replace("&", "&&"))
        if tab is self.current:
            from fdcad.ui.main_window.window_details import update_title

            update_title(self, tab.session)  # name, unsaved mark, FDCAD (U9.3)
            self._update_unit_button()

    def _tab_changed(self, _index: int) -> None:
        mode = self.sketch_mode
        leaving = mode is not None and mode.is_open and mode.tab is not self.current
        if leaving and mode is not None and not mode.accept() and mode.tab is not None:
            # A value box holds a bad value: stay on the sketch's part (D592).
            self.tabs.blockSignals(True)
            self.tabs.setCurrentWidget(mode.tab)
            self.tabs.blockSignals(False)
            return
        tab = self.current
        session = tab.session if tab else None
        if tab is not None:
            self.undo_group.setActiveStack(tab.session.undo)
            self._retitle(tab)
        else:
            self.setWindowTitle(f"{strings.APP} {__version__}")  # no part open (F7)
        self.update_corner()
        if self.panel is not None and self.panel.is_editing:
            self.panel.cancel()
        # Panels and boxes of the part left behind would change that part (round 10c).
        self.appearance_tool.tab_changed()
        self.section_tool.tab_changed()
        self.measure_tool.tab_changed()
        if self.tree is not None:
            self.tree.set_session(session)
        if self.variables is not None:
            self.variables.set_session(session)
        errors = getattr(self, "errors", None)
        if errors is not None:
            errors.set_session(session)
        stats = getattr(self, "stats", None)
        if stats is not None:
            stats.set_session(session)
        self._update_unit_button()

    def _update_unit_button(self) -> None:
        tab = self.current
        if tab is None:
            self.unit_button.hide()
            return
        self.unit_button.set_unit(tab.session.document.units)
        self.unit_button.show()

    def toggle_units(self) -> None:
        """Switch the part's display units. Stored values never change."""
        from fdcad.core.units import UnitSystem

        tab = self.current
        if tab is not None:
            current = tab.session.document.units
            self.set_units(UnitSystem.IN if current is UnitSystem.MM else UnitSystem.MM)

    def set_units(self, unit: Any) -> None:
        """Use ``unit`` (a UnitSystem) to show sizes in the active part, as an undoable step."""
        from fdcad.ui.commands.document import SetUnits

        tab = self.current
        if tab is not None and tab.session.document.units is not unit:
            tab.session.undo.push(SetUnits(tab.session, unit))
        self._update_unit_button()

    def _rebuild_started(self, tab: DocumentTab) -> None:
        motion.rebuild_started(tab.session)  # no animation during a slow rebuild (U7.2)
        if tab is self.current:
            self.feedback.begin("rebuild", tab.session.cancel_rebuild)

    def _progress(self, tab: DocumentTab, index: int, total: int, name: str) -> None:
        if tab is self.current:
            self.feedback.step(index, total)
            self.status.setText(strings.REBUILDING.format(name=name, index=index + 1, total=total))

    def _rebuilt(self, tab: DocumentTab, report: RebuildReport) -> None:
        self.feedback.end("rebuild")  # even when another tab is active now
        if tab is not self.current:
            return
        count = report.body_count
        self.bodies.setText(
            strings.BODY_COUNT.get(count, strings.BODY_COUNT_MANY.format(count=count))
            if count
            else ""
        )
        self.model_dims.refresh()
        held = getattr(self, "note_after_rebuild", "")
        self.note_after_rebuild = ""
        if report.variable_error:
            self.status.setText(strings.VARIABLE_ERROR.format(reason=report.variable_error))
        elif report.variable_warnings:  # TR274
            self.status.setText(report.variable_warnings[0])
        elif report.cancelled:
            self.status.setText(strings.REBUILD_STOPPED)  # was "Rebuilt in" (D710)
        elif held:
            self.status.setText(held)  # a note that asks for something, kept (D708)
        elif getattr(tab.session, "not_rebuilt", False):
            self.status.setText(strings.SHOWN_SAVED)  # D1106
        else:
            from fdcad.ui.main_window.expected_values import status_suffix

            self.status.setText(
                (change_text(report, tab) or strings.REBUILT.format(seconds=report.seconds))
                + status_suffix(report)  # TR359
            )
            announce(self.status)
        graph = getattr(self, "curvature_graph", None)
        if graph is not None:
            graph.refresh()

    # File commands ----------------------------------------------------------------------

    def new_part(self) -> None:
        """Ask for units and open a new part."""
        from fdcad.ui.main_window.new_part_dialog import NewPartDialog
        from fdcad.ui.main_window.templates import new_from_template, templates
        from fdcad.ui.session import DocumentSession

        dialog = NewPartDialog(self.settings.default_units, self, templates())
        if dialog.exec():
            chosen = dialog.template()
            if chosen is not None:
                new_from_template(self, chosen)  # TR217
            else:
                self.add_session(DocumentSession.new(dialog.units(), self))
        dialog.deleteLater()  # closed dialogs stayed alive (D637)

    def open_dialog(self) -> None:
        """Choose a part to open."""
        from fdcad.ui.strings_import import FILTER_OPENABLE

        filters = f"{FILTER_OPENABLE};;{strings.FILTER_PARTS_OPEN}"
        path, _ = QFileDialog.getOpenFileName(self, strings.OPEN, "", filters)
        if path:
            self.open_path(Path(path))

    def open_view_only(self, path: Path | None = None) -> bool:
        """Open a part for viewing only (TR356, D971): every change is refused until
        Edit on the bar above the view. A part already open is left as it is."""
        if path is None:
            name, _ = QFileDialog.getOpenFileName(self, strings.OPEN, "", strings.FILTER_PARTS_OPEN)
            if not name:
                return False
            path = Path(name)
        count = self.tabs.count()
        self.open_path(path)
        tab = self.current
        if tab is None or self.tabs.count() == count:
            return False  # not opened, or it was open already
        session = tab.session
        session.view_only = True
        name = session.title.rstrip("*")
        session.undo.blocked.connect(
            lambda: self.status.setText(strings.VIEW_ONLY_BLOCKED.format(name=name))
        )
        tab.message_bars.show_message(
            "view_only",
            strings.VIEW_ONLY_BAR.format(name=name),
            "info",
            (strings.VIEW_ONLY_EDIT, lambda t=tab: self.edit_view_only(t)),
        )
        self._retitle(tab)
        return True

    def edit_view_only(self, tab: DocumentTab) -> None:
        """Switch a part opened for viewing to full editing."""
        tab.session.view_only = False
        tab.message_bars.close_message("view_only")
        self._retitle(tab)

    def open_path(self, path: Path) -> None:
        """Open a part file, or switch to it when it is already open.

        A STEP or mesh file opens as a new part that imports it (P3.5, P3.9).
        """
        import os

        from fdcad.ui.main_window.imports import is_import
        from fdcad.ui.session import DocumentSession

        # A full path, so the recent list works from any folder and a file opens once (F5).
        path = Path(os.path.abspath(path))
        same = os.path.normcase(path)
        if is_import(path):
            for i in range(self.tabs.count()):
                tab = self.tabs.widget(i)
                session = getattr(tab, "session", None)
                source = getattr(session, "opened_from", None)
                unsaved = source is not None and session is not None and session.path is None
                if unsaved and os.path.normcase(os.path.abspath(str(source))) == same:
                    self.tabs.setCurrentIndex(i)  # opens once, like a part (D741)
                    return
            if self.import_flow.open_file(path) is not None:
                self.settings.add_recent(str(path))  # was left out (audit C item 18)
            return

        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if (
                isinstance(tab, DocumentTab)
                and tab.session.path is not None
                and os.path.normcase(os.path.abspath(tab.session.path)) == same
            ):
                self.tabs.setCurrentIndex(i)
                return
        try:
            session = DocumentSession.open(path, self)
        except FileFormatError as exc:  # FDCAD's own reason already says what to do
            show_error(
                self,
                strings.OPEN_FAILED.format(name=path.name, reason=exc),
                exc,
                feedback.OPEN_FAILED_CONTEXT.format(path=path),
            )
            return
        except (OSError, ValueError) as exc:
            if isinstance(exc, FileNotFoundError):
                self.settings.remove_recent(str(path))  # never offer it again (F8)
            show_error(
                self,
                strings.OPEN_FAILED_SYSTEM.format(name=path.name, reason=strings.clause(exc)),
                exc,
                feedback.OPEN_FAILED_CONTEXT.format(path=path),
            )
            return
        self.settings.add_recent(str(path))
        note = session.read_linked_equations(undoable=False)  # TR25: read on open
        self.add_session(session)
        if note:
            self.feedback.flash(note)

    def _fill_samples(self) -> None:
        from fdcad.samples.location import sample_files

        self.sample_menu.clear()
        for path in sample_files():
            label = path.stem.replace("_", " ").capitalize()
            self._action(self.sample_menu, label, partial(self.open_sample, path))

    def open_sample(self, path: Path) -> None:
        """Open a sample as a new untitled part, so the shipped file is never changed."""
        from fdcad.core.io import fdef
        from fdcad.ui.session import DocumentSession

        session = DocumentSession(fdef.load(path), None, self)
        session.name = path.stem.replace("_", " ").capitalize()
        self.add_session(session)

    def _fill_recent(self) -> None:
        self.recent_menu.clear()
        for item in self.settings.recent_files:
            label = item.replace("&", "&&")  # a folder named "R&D" is not a shortcut key
            self._action(self.recent_menu, label, partial(self.open_path, Path(item)))
        if not self.settings.recent_files:
            empty = self.recent_menu.addAction(feedback.NO_RECENT)  # empty state (U8.3)
            empty.setEnabled(False)
        self.recent_menu.addSeparator()
        self._action(self.recent_menu, strings.CLEAR_RECENT, self.settings.clear_recent)

    def save(self) -> bool:
        """Save the active part. Returns False when it was not saved."""
        tab = self.current
        if tab is None or not self._finish_sketch(tab):
            return False
        if tab.session.path is None:
            return self.save_as()
        return self._save_to(tab, tab.session.path)

    def save_increment(self) -> bool:
        """Save under the next numbered name beside the file and keep working in it
        (TR305, D923). A part never saved asks for a name first."""
        from fdcad.core.io.increment import next_path

        tab = self.current
        if tab is None or not self._finish_sketch(tab):
            return False
        if tab.session.path is None:
            return self.save_as()
        target = next_path(tab.session.path)
        if self._open_elsewhere(tab, target):
            self.status.setText(strings.SAVE_AS_OPEN.format(name=target.name))
            return False
        return self._save_to(tab, target)

    def _finish_sketch(self, tab: DocumentTab) -> bool:
        """Close an open sketch of ``tab`` as OK does, so a save includes it (D590).

        Returns False when the sketch could not be closed (a value box holds a bad value).
        """
        mode = self.sketch_mode
        if mode is None or not mode.is_open or mode.tab is not tab:
            return True
        return mode.accept()

    def save_as(self) -> bool:
        """Save the active part under a new name."""
        tab = self.current
        if tab is None or not self._finish_sketch(tab):
            return False
        default = self._default_name(tab, PART_SUFFIX)
        path, _ = QFileDialog.getSaveFileName(self, strings.SAVE_AS, default, strings.FILTER_FDEF)
        if not path:
            return False
        target = self._named(Path(path), PART_SUFFIX)
        if target is not None and self._open_elsewhere(tab, target):
            # Two tabs on one file would overwrite each other (audit D3 item 14, D723).
            self.status.setText(strings.SAVE_AS_OPEN.format(name=target.name))
            return False
        return target is not None and self._save_to(tab, target)

    def delete_in_view(self) -> QMenu | None:
        """Delete with faces picked in the view (TR201, D807): a menu with Delete Feature
        (the feature that made the first face) and Delete Face (the Delete Face feature
        on every picked face). Returns the menu shown, or None when nothing is picked."""
        from OCP.TopAbs import TopAbs_FACE

        from fdcad.ui.body_tools import flow as phase3

        tab = self.current
        faces = [
            s for s in (tab.selection if tab is not None else []) if s.ShapeType() == TopAbs_FACE
        ]
        if tab is None or not faces or self.tree is None:
            return None
        menu = QMenu(self)
        menu.setObjectName("view_delete")
        fid = self.context_menus.feature_of(tab, faces[0])
        if fid is not None:
            name = tab.session.document.feature(fid).name
            feature_item = menu.addAction(strings.DELETE_FEATURE.format(name=name))
            feature_item.triggered.connect(lambda _c=False: self.tree.delete(fid))
        face_item = menu.addAction(strings.DELETE_FACES.format(count=len(faces)))
        face_item.triggered.connect(
            lambda _c=False: phase3.start(self, "feature.delete_face", faces[0])
        )
        menu.popup(QCursor.pos())
        return menu

    def fill_undo_menu(self) -> None:
        """Edit, Undo To (TR208, D807): the last steps of the active part, newest first;
        choosing one undoes it and every step after it, in one go."""
        menu = self.undo_menu
        menu.clear()
        stack = self.undo_group.activeStack()
        if stack is None or stack.index() == 0:
            empty = menu.addAction(strings.UNDO_TO_NONE)
            empty.setEnabled(False)
            return
        for i in range(stack.index() - 1, max(stack.index() - 25, 0) - 1, -1):
            action = menu.addAction(stack.text(i) or strings.UNDO)
            action.triggered.connect(lambda _c=False, k=i: self.undo_to(k))

    def undo_to(self, index: int) -> None:
        """Undo the step at ``index`` of the active part and every step after it."""
        stack = self.undo_group.activeStack()
        if stack is not None and 0 <= index < stack.index():
            stack.setIndex(index)

    def save_copy(self, open_it: bool = False) -> bool:
        """File, Save a Copy (TR97, D806): write the part to a new file and keep the open
        part as it is, under its own name and unsaved state. With ``open_it`` the copy
        opens in a new tab."""
        from fdcad.core.io import fdef

        tab = self.current
        if tab is None or not self._finish_sketch(tab):
            return False
        session = tab.session
        stem = session.path.stem if session.path is not None else session.display_name
        default = (
            str(session.path.with_name(f"{stem} copy{PART_SUFFIX}"))
            if session.path is not None
            else f"{stem} copy{PART_SUFFIX}"
        )
        path, _ = QFileDialog.getSaveFileName(self, strings.SAVE_COPY, default, strings.FILTER_FDEF)
        if not path:
            return False
        target = self._named(Path(path), PART_SUFFIX)
        if target is None:
            return False
        if self._open_elsewhere(None, target) or (
            session.path is not None and _same_file(session.path, target)
        ):
            self.status.setText(strings.SAVE_AS_OPEN.format(name=target.name))
            return False
        try:
            fdef.save(session.document, target)
        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.warning(
                self, strings.APP, strings.SAVE_REFUSED.format(name=target.name, reason=exc)
            )
            return False
        self.settings.add_recent(str(target))
        self.feedback.flash(strings.SAVED_COPY.format(name=target.name))
        if open_it:
            self.open_path(target)
        return True

    def _open_elsewhere(self, tab: DocumentTab | None, target: Path) -> bool:
        """True when another open tab already uses ``target``."""
        for i in range(self.tabs.count()):
            other = self.tabs.widget(i)
            path = getattr(getattr(other, "session", None), "path", None)
            if other is not tab and path is not None:
                try:
                    if Path(path).resolve() == target.resolve():
                        return True
                except OSError:
                    continue
        return False

    @staticmethod
    def _default_name(tab: DocumentTab, suffix: str) -> str:
        """The name a save dialog offers: in the part's own folder once it has a file (F13)."""
        session = tab.session
        if session.path is None:
            return session.display_name + suffix
        return str(session.path.with_name(session.path.stem + suffix))

    def _named(self, typed: Path, suffix: str) -> Path | None:
        """``typed`` with ``suffix``, or None when the user declines to replace a file.

        A name with another or no suffix gets ``suffix`` added, never swapped in:
        "rev 1.2" becomes "rev 1.2.fdprt", not "rev 1.fdprt" (bug hunt F3). An older
        ``.fdef`` name becomes ``.fdprt`` (D575). The file dialog only confirmed
        replacing the name typed, so a different existing file is confirmed here.
        """
        if typed.suffix.lower() == suffix:
            return typed
        if suffix == PART_SUFFIX and typed.suffix.lower() == ".fdef":
            target = typed.with_suffix(PART_SUFFIX)
        else:
            target = typed.with_name(typed.name + suffix)
        if target.exists():
            answer = QMessageBox.question(
                self, strings.SAVE_AS_TITLE, strings.FILE_EXISTS.format(name=target.name)
            )
            if answer != QMessageBox.StandardButton.Yes:
                return None
        return target

    def save_as_any(self) -> bool:
        """File, Save As: an FDCAD part, or a copy as STEP, STL or 3MF (D435).

        Choosing STEP, STL or 3MF exports the part like File, Export does; the
        part itself stays unsaved under its current name.
        """
        tab = self.current
        if tab is None:
            return False
        default = self._default_name(tab, PART_SUFFIX)
        kinds = {
            strings.FILTER_FDEF: "fdef",
            strings.FILTER_STEP: "step",
            strings.FILTER_STL: "stl",
            strings.FILTER_3MF: "3mf",
            # TR369 (D989)
            strings.FILTER_IGES: "iges",
            strings.FILTER_BREP: "brep",
            strings.FILTER_PLY: "ply",
            strings.FILTER_GLB: "glb",
            strings.FILTER_OBJ: "obj",  # TR336 (D995)
            strings.FILTER_DXF3D: "dxf3d",  # TR369 (D1010)
        }
        path, chosen = QFileDialog.getSaveFileName(self, strings.SAVE_AS, default, ";;".join(kinds))
        if not path:
            return False
        target = Path(path)
        by_suffix = {
            PART_SUFFIX: "fdef",
            ".fdef": "fdef",
            ".step": "step",
            ".stp": "step",
            ".stl": "stl",
            ".3mf": "3mf",
            ".igs": "iges",
            ".iges": "iges",
            ".brep": "brep",
            ".ply": "ply",
            ".glb": "glb",
            ".obj": "obj",
            ".dxf": "dxf3d",
        }
        kind = by_suffix.get(target.suffix.lower()) or kinds.get(chosen, "fdef")
        if kind == "fdef":
            named = self._named(target, PART_SUFFIX)
            return named is not None and self._finish_sketch(tab) and self._save_to(tab, named)
        if target.suffix.lower() not in by_suffix:
            named = self._named(target, ".dxf" if kind == "dxf3d" else "." + kind)
            if named is None:
                return False
            target = named
        self.export(kind, target)
        return True

    def _save_to(self, tab: DocumentTab, path: Path) -> bool:
        from fdcad.core.io.backups import keep_backup

        # TR218 (D961): the old file is kept as a numbered copy; a failed copy never
        # stops the save.
        keep_backup(path, self.settings.backup_count, self.settings.backup_folder)
        from fdcad.ui.main_window import start_page

        picture = start_page.keep_thumbnail(tab, path)  # TR218 item 2 (D2504)
        try:
            tab.session.save(path)
        except OSError as exc:
            show_error(
                self,
                strings.SAVE_FAILED.format(name=path.name, reason=strings.clause(exc)),
                exc,
                feedback.SAVE_FAILED_CONTEXT.format(path=path),
            )
            return False
        except (ValueError, TypeError) as exc:  # FDCAD's own reason names the fix (F11)
            QMessageBox.warning(
                self, strings.APP, strings.SAVE_REFUSED.format(name=path.name, reason=exc)
            )
            return False
        tab.autosaver.discard()
        start_page.saved(path, picture)
        self.settings.add_recent(str(path))
        self._retitle(tab)
        self.feedback.flash(feedback.SAVED.format(name=path.name))  # not a dialog (U8.4)
        return True

    def check_resources(self, found: list[Any] | None = None) -> list[Any]:
        """Warn on the current part's view when disk space (where the open parts and
        the recovery copies are kept) or memory runs low, with a Save button; the bars
        go when there is room again (TR220, D968). ``found`` replaces the check."""
        from fdcad.core.resources import shortages
        from fdcad.ui.main_window.recovery import data_dir

        if found is None:
            folders = [data_dir()]
            for i in range(self.tabs.count()):
                tab = self.tabs.widget(i)
                if isinstance(tab, DocumentTab) and tab.session.path is not None:
                    folders.append(tab.session.path.parent)
            found = shortages(folders)
        tab = self.current
        bars = getattr(tab, "message_bars", None)
        if bars is None:
            return found
        kinds = {s.kind: s for s in found}
        save = (strings.SAVE_ALL_BUTTON, self.save_all)
        for kind, key, words in (
            ("disk", "low_disk", strings.LOW_DISK),
            ("memory", "low_memory", strings.LOW_MEMORY),
        ):
            short = kinds.get(kind)
            if short is None:
                bars.close_message(key)
                continue
            mb = max(1, short.free // (1024 * 1024))
            bars.show_message(key, words.format(mb=mb, where=short.where), "warning", save)
        return found

    def save_all(self) -> int:
        """Save every part with unsaved changes (TR218). Returns how many were saved;
        stops at the first one whose save is cancelled or fails."""
        widgets = [self.tabs.widget(i) for i in range(self.tabs.count())]
        dirty = [w for w in widgets if isinstance(w, DocumentTab) and w.session.is_dirty]
        if not dirty:
            self.status.setText(strings.SAVE_ALL_NOTHING)
            return 0
        saved = 0
        for tab in dirty:
            self.tabs.setCurrentWidget(tab)
            if not self.save():
                break
            saved += 1
        self.status.setText(strings.SAVE_ALL_DONE.format(count=saved))
        return saved

    def ask_close_all(self) -> bool:
        """Ask about every unsaved part, save the ones chosen. False when cancelled;
        nothing is closed until every part has an answer (as on quit, D710)."""
        mode = self.sketch_mode
        if mode is not None and mode.is_open and not mode.accept():
            return False
        to_save: list[DocumentTab] = []
        for index in reversed(range(self.tabs.count())):
            tab = self.tabs.widget(index)
            if not isinstance(tab, DocumentTab) or not tab.session.is_dirty:
                continue
            answer = self._ask_unsaved(index)
            if answer == QMessageBox.StandardButton.Cancel:
                return False
            if answer == QMessageBox.StandardButton.Save:
                to_save.append(tab)
        for tab in to_save:
            self.tabs.setCurrentWidget(tab)
            if not self.save():
                return False
        return True

    def close_all(self) -> bool:
        """Close every part (TR218), asking about unsaved changes first."""
        if not self.ask_close_all():
            return False
        while self.tabs.count():
            self.close_tab(self.tabs.count() - 1, ask=False)
        return True

    def confirm_revert(self, name: str) -> bool:
        """Ask before throwing changes away (a seam for tests). No is the default."""
        answer = QMessageBox.question(
            self,
            strings.REVERT_TITLE,
            strings.REVERT_PROMPT.format(name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def revert_to_saved(self) -> bool:
        """Drop the active part's changes and open its saved file again (TR218)."""
        tab = self.current
        if tab is None:
            return False
        name = tab.session.title.rstrip("*")
        path = tab.session.path
        if path is None:
            self.status.setText(strings.REVERT_NOT_SAVED.format(name=name))
            return False
        if not tab.session.is_dirty:
            self.status.setText(strings.REVERT_CLEAN.format(name=name))
            return False
        if not self.confirm_revert(name):
            return False
        index = self.tabs.indexOf(tab)
        if not self.close_tab(index, ask=False):
            return False
        self.open_path(path)
        opened = self.current
        if opened is not None and index < self.tabs.count():
            self.tabs.tabBar().moveTab(self.tabs.indexOf(opened), index)
            self.tabs.setCurrentWidget(opened)
        return True

    def _ask_unsaved(self, index: int) -> QMessageBox.StandardButton:
        """Save, Discard or Cancel for the unsaved part at ``index``."""
        tab = self.tabs.widget(index)
        assert isinstance(tab, DocumentTab)
        self.tabs.setCurrentIndex(index)
        return QMessageBox.question(
            self,
            strings.UNSAVED_TITLE,
            feedback.UNSAVED.format(name=tab.session.title.rstrip("*")),
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,  # the safe button (U8.5)
        )

    def close_tab(self, index: int, ask: bool = True) -> bool:
        """Close a part, asking to save unsaved changes. Returns False when cancelled.
        With ``ask`` False the caller has already asked (quitting, D710)."""
        tab = self.tabs.widget(index)
        if not isinstance(tab, DocumentTab):
            return True
        mode = self.sketch_mode
        if mode is not None and mode.is_open and mode.tab is tab and not mode.accept():
            return False
        if ask and tab.session.is_dirty:
            answer = self._ask_unsaved(index)
            if answer == QMessageBox.StandardButton.Cancel:
                return False
            if answer == QMessageBox.StandardButton.Save and not self.save():
                return False
        tab.session.cancel_rebuild()
        tab.session.wait(10000)
        tab.autosaver.discard()
        self.undo_group.removeStack(tab.session.undo)
        self.tabs.removeTab(index)
        # Sections are kept by id(tab); a later part could get the same id (round 10c).
        self.section_tool.states.pop(id(tab), None)
        tab.session.close()  # free shapes and undo history (PLAN 11.4 item 6, D633)
        tab.release_views()  # before Qt destroys the view's window (D2780)
        tab.deleteLater()
        return True

    def _wait_for_export(self, limit_ms: int = 60000) -> bool:
        """Let a running export finish before quitting, so its file is not left half
        written (audit D3 item 24, D744). False when it is still running at the limit."""
        from PySide6.QtCore import QElapsedTimer, QEventLoop

        if not self.feedback.running("export"):
            return True
        self.status.setText(strings.EXPORT_WAIT)
        clock = QElapsedTimer()
        clock.start()
        while self.feedback.running("export") and clock.elapsed() < limit_ms:
            QApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        if self.feedback.running("export"):
            self.status.setText(strings.EXPORT_STILL_RUNNING)
            return False
        return True

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Ask about every unsaved part first, then save and close them all.

        Nothing closes until every part has an answer, so Cancel on a later part
        leaves the earlier ones open with their changes (audit D3 item 12, D710).
        """
        self.memory.save(self)  # size, place and panels for the next start (U9.1)
        if not self._wait_for_export():
            event.ignore()
            return
        mode = self.sketch_mode
        if mode is not None and mode.is_open and not mode.accept():
            event.ignore()
            return
        to_save: list[DocumentTab] = []
        for index in reversed(range(self.tabs.count())):
            tab = self.tabs.widget(index)
            if not isinstance(tab, DocumentTab) or not tab.session.is_dirty:
                continue
            answer = self._ask_unsaved(index)
            if answer == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if answer == QMessageBox.StandardButton.Save:
                to_save.append(tab)
        for tab in to_save:
            self.tabs.setCurrentWidget(tab)
            if not self.save():
                event.ignore()  # the save was cancelled or failed: keep everything open
                return
        self.settings.last_session = [  # TR218: for Open the parts from last time
            str(t.session.path)
            for t in (self.tabs.widget(i) for i in range(self.tabs.count()))
            if isinstance(t, DocumentTab) and t.session.path is not None
        ]
        while self.tabs.count():
            self.close_tab(self.tabs.count() - 1, ask=False)
        event.accept()

    def autosave(self) -> None:
        """Write autosave copies of parts with unsaved changes."""
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if not isinstance(tab, DocumentTab):
                continue
            mode = self.sketch_mode
            if mode is not None and mode.is_open and mode.tab is tab:
                document = mode.document_with_sketch()  # keep the open sketch's edits (D590)
                if document is not None:
                    tab.autosaver.save(document, tab.session.path)
                    continue
            if tab.session.is_dirty:
                tab.autosaver.save(tab.session.document, tab.session.path, wait=False)
            if tab.autosaver.error and not getattr(tab, "autosave_warned", False):
                # Say once that autosave is not working (audit D3 item 10, D724).
                tab.autosave_warned = True  # type: ignore[attr-defined]
                self.status.setText(strings.AUTOSAVE_FAILED.format(reason=tab.autosaver.error))

    def recover(self) -> None:
        """Offer to reopen parts autosaved before a crash."""
        from fdcad.ui.main_window.recovery import discard_all, find_recoverable
        from fdcad.ui.session import DocumentSession

        found = find_recoverable()
        if not found:
            return
        buttons = (
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        answer = QMessageBox.question(
            self,
            strings.RECOVERY_TITLE,
            strings.RECOVERY.format(count=len(found)),
            buttons,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return  # Later: the copies wait for the next start (audit D3 item 9, D724)
        if answer == QMessageBox.StandardButton.Yes:
            for item in found:
                # Keep the file it came from, so Save puts the work back there (F4),
                # unless that file was saved again after the autosave.
                session = DocumentSession(item.document, item.original, self)
                session.mark_recovered()
                self.add_session(session)
            if any(item.original_newer for item in found):
                self.status.setText(strings.RECOVERY_NEWER)
        discard_all(found)

    # Export -----------------------------------------------------------------------------

    def export(self, kind: str, target: Path | None = None) -> None:
        """Export the active part in the background, to ``target`` or a chosen file."""
        from fdcad.core.io import export

        tab = self.current
        report = tab.session.report if tab else None
        if tab is not None and tab.session.is_rebuilding:
            # Not built yet, or the body shown is older than the part (F9, D710).
            self.status.setText(strings.EXPORT_WAIT)
            return
        if report is not None and report.cancelled:
            self.status.setText(strings.EXPORT_STOPPED)  # a partial body (audit D3 item 4)
            return
        if tab is None or report is None or report.body is None:
            mesh = _reference_mesh(tab.session.document, report) if tab and report else None
            if mesh is not None:
                self.status.setText(strings.EXPORT_MESH_ONLY.format(name=mesh))
            else:
                self.status.setText(strings.NOTHING_TO_EXPORT)
            return
        filters = {
            "step": strings.FILTER_STEP,
            "stl": strings.FILTER_STL,
            "3mf": strings.FILTER_3MF,
            "iges": strings.FILTER_IGES,  # TR369 (D989)
            "brep": strings.FILTER_BREP,
            "ply": strings.FILTER_PLY,
            "glb": strings.FILTER_GLB,
            "obj": strings.FILTER_OBJ,  # TR336 (D995)
            "dxf3d": strings.FILTER_DXF3D,  # TR369 (D1010)
        }
        if target is None:
            ending = ".dxf" if kind == "dxf3d" else "." + kind
            default = self._default_name(tab, ending)
            chosen, _ = QFileDialog.getSaveFileName(
                self, strings.MENU_EXPORT, default, filters[kind]
            )
            if not chosen:
                return
            # A name typed without the suffix still gets one (".stp" is also a STEP file).
            typed = Path(chosen)
            if not (kind == "step" and typed.suffix.lower() == ".stp"):
                typed = with_suffix(typed, ending)
            if typed != Path(chosen) and typed.exists():
                # The dialog asked about the typed name, not the one with the ending
                # added (audit D3 item 17, D744).
                answer = QMessageBox.question(
                    self,
                    strings.MENU_EXPORT,
                    strings.EXPORT_REPLACE.format(name=typed.name),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
            path = str(typed)
        else:
            path = str(target)
        shape = report.body.shape
        settings, keep = self._mesh_options(tab, kind, shape, ask=target is None)
        if settings is None:
            return
        step_options = self._step_options(tab, ask=target is None) if kind == "step" else None
        if kind == "step" and step_options is None:
            return
        from fdcad.ui.appearance.tool import part_display
        from fdcad.ui.main_window.phase4_features import thread_notes
        from fdcad.ui.preferences.print_settings import active_profile
        from fdcad.ui.print_tools.orientation import (
            print_shape_work,
            print_transform_work,
            thumbnail,
        )

        color, faces = part_display(tab)
        notes = thread_notes(tab.session.document, report)
        warn = export_warning(tab.session.document, report)
        printed = print_shape_work(tab, active_profile(self.settings))  # D353
        placed = print_transform_work(tab, active_profile(self.settings))  # TR381
        picture = thumbnail(tab) if kind == "3mf" else None
        from fdcad.core.body_titles import report_marks
        from fdcad.core.printing.body_roles import roles_of, status_line

        given_roles = report_marks(report, "body_roles")  # TR386 (D1205)
        given_titles = report_marks(report, "body_titles")
        all_roles = (
            roles_of(tab.session.document, report.body, given_roles) if kind == "3mf" else []
        )
        from fdcad.core.properties import metadata as property_texts

        props = property_texts(tab.session.document) if kind == "3mf" else {}  # TR82
        roles = all_roles if keep is None else [all_roles[i] for i in keep if i < len(all_roles)]
        from fdcad.core.body_titles import stored as stored_titles
        from fdcad.core.body_titles import titles_of

        all_titles = (
            titles_of(tab.session.document, report.body, given_titles)
            if kind in ("3mf", "step") and (stored_titles(tab.session.document) or given_titles)
            else []
        )  # TR183 (D1201)
        titles = (
            all_titles if keep is None else [all_titles[i] for i in keep if i < len(all_titles)]
        )

        from fdcad.core.printing.body_settings import settings_of
        from fdcad.core.printing.body_settings import stored as stored_settings

        all_tuned = (
            settings_of(tab.session.document, report.body)
            if kind == "3mf" and stored_settings(tab.session.document)
            else []
        )  # TR383 (D1207)
        tuned = all_tuned if keep is None else [all_tuned[i] for i in keep if i < len(all_tuned)]
        from fdcad.core.printing.heights import HEIGHT_CHANGES, clean

        heights = clean((tab.session.document.print_setup or {}).get(HEIGHT_CHANGES))  # TR384
        from fdcad.core.printing.coating import thickness

        coat = thickness(tab.session.document.print_setup)  # TR307 (D1214)
        from fdcad.ui.print_tools.coating_tool import coated

        step_bodies: list[tuple[int, str]] = []  # TR302 (D1202): (index, name) to write
        if step_options is not None:
            from fdcad.core.body_titles import labels_of
            from fdcad.core.body_visibility import hidden_names, visible_indices

            labels = labels_of(tab.session.document, report.body, given_titles)
            if len(labels) == 1:
                own = all_titles[0] if all_titles else None
                labels = [own or (tab.session.name or "Part")]
            shown = (
                range(len(labels))
                if step_options.hidden
                else visible_indices(report.body, hidden_names(tab.session.document), None)
            )
            step_bodies = [(i, labels[i]) for i in shown]

        def overlap_rule(part: Any) -> tuple[Any, str]:
            """TR411 (D907): join overlaps, give them to the earlier body, or say so."""
            from fdcad.core.printing import overlaps

            if settings.overlaps != "warn":
                return overlaps.resolve(part, settings.overlaps), ""
            return part, overlaps.warning(overlaps.find(part))

        def work() -> str:
            if kind in ("iges", "brep", "ply", "glb", "obj", "dxf3d"):  # TR369, TR336
                from fdcad.core.io import more_formats

                if kind == "iges":
                    more_formats.export_iges(shape, path)
                elif kind == "brep":
                    more_formats.export_brep(shape, path)
                elif kind == "ply":
                    more_formats.export_ply(shape, path, settings)
                elif kind == "obj":
                    more_formats.export_obj(shape, path, settings)
                elif kind == "dxf3d":
                    more_formats.export_dxf3d(shape, path)
                else:
                    more_formats.export_glb(shape, path, settings)
                return f"{strings.EXPORT_DONE.format(name=Path(path).name)} {warn}".strip()
            if kind == "step":
                assert step_options is not None
                done = _write_step_files(
                    shape, Path(path), step_options, step_bodies, color, faces, notes
                )
                return f"{done} {warn}".strip()
            if kind == "stl":
                mesh_shape, note = printed()  # STL and 3MF follow the print orientation
                mesh_shape, overlap_note = overlap_rule(_only(mesh_shape, keep))
                mesh_shape, _f, coat_note = coated(mesh_shape, coat, None)  # TR307
                export.export_stl(mesh_shape, path, settings)
                note = " ".join(t for t in (note, overlap_note, coat_note) if t)
            else:
                # The model keeps its place and colours; the print orientation is the
                # build item's transform (TR381, D777).
                trsf, note = placed()
                part, overlap_note = overlap_rule(_only(shape, keep))
                part, coat_faces, coat_note = coated(part, coat, faces)  # TR307
                note = " ".join(t for t in (note, overlap_note, coat_note) if t)
                export.export_3mf(
                    part,
                    path,
                    color=color,
                    faces=coat_faces,
                    settings=settings,
                    transform=export.transform_of(trsf) if trsf is not None else None,
                    thumbnail=picture,
                    roles=roles if settings.overlaps == "warn" else [],
                    metadata=props,
                    titles=titles if settings.overlaps == "warn" else [],
                    body_settings=tuned if settings.overlaps == "warn" else [],
                    heights=heights,
                )
                note = " ".join(t for t in (note, status_line(settings.slicer, roles)) if t)
            done = strings.EXPORT_DONE.format(name=Path(path).name)
            return " ".join(t for t in (done, note, warn) if t)

        job = _Job(work)
        self.feedback.begin("export")
        job.signals.done.connect(self._export_finished)  # a QObject slot: queued to this thread
        QThreadPool.globalInstance().start(job)

    def _step_options(self, tab: DocumentTab, ask: bool) -> Any:
        """The STEP options (TR302, D1202): asked when ``ask``, else the ones kept in the
        part; None when the dialog is cancelled."""
        from fdcad.core.io.step_options import StepOptions

        doc = tab.session.document
        kept = StepOptions.from_data((doc.print_setup or {}).get("step_export"))
        if not ask:
            return kept
        from fdcad.ui.main_window import step_export_dialog

        dialog = step_export_dialog.StepExportDialog(kept, self)
        accepted = step_export_dialog.run(dialog)
        options = dialog.options
        dialog.deleteLater()
        if not accepted:
            return None
        if options != kept:
            from fdcad.ui.commands.print_setup import SetPrintSetupKey

            tab.session.undo.push(
                SetPrintSetupKey(tab.session, "step_export", options.to_data(), strings.STEP_UNDO)
            )
        return options

    def _mesh_options(
        self, tab: DocumentTab, kind: str, shape: Any, ask: bool
    ) -> tuple[Any, list[int] | None]:
        """The STL or 3MF options (TR182): asked in a dialog when ``ask``, else the ones
        kept in the part. (None, None) when the dialog is cancelled; for STEP, defaults."""
        from fdcad.core.io.export import MeshSettings

        doc = tab.session.document
        kept = MeshSettings.from_data((doc.print_setup or {}).get("mesh_export"))
        if kind in ("step", "iges", "brep", "ply", "glb", "obj", "dxf3d") or not ask:
            return kept, None  # TR369: the new formats use the part's kept mesh settings
        from fdcad.ui.main_window.mesh_export_dialog import MeshExportDialog, run

        dialog = MeshExportDialog(kind, kept, shape, self, viewport=tab.viewport)
        accepted = run(dialog)
        dialog.done(int(accepted))  # also takes the mesh preview out of the view (TR336)
        settings, choice = dialog.settings, dialog.body_choice
        dialog.deleteLater()
        if not accepted:
            return None, None
        if settings.to_data() != kept.to_data():
            from fdcad.ui.commands.print_setup import SetMeshExport

            tab.session.undo.push(
                SetMeshExport(tab.session, settings.to_data(), strings.MESH_EXPORT_UNDO)
            )
        return settings, self._bodies_for(tab, choice)

    @staticmethod
    def _bodies_for(tab: DocumentTab, choice: str) -> list[int] | None:
        """Body indices to export: None for all of them."""
        from fdcad.core.body_visibility import bodies_of, hidden_names, visible_indices

        report = tab.session.report
        body = report.body if report is not None else None
        if body is None or choice == "all":
            return None
        if choice == "picked":
            picked = bodies_of(body.shape, tab.selection)
            return picked or None
        return visible_indices(body, hidden_names(tab.session.document), tab.isolated)

    def _export_finished(self, message: str) -> None:
        self.feedback.end("export")
        self.feedback.flash(message)  # a short confirmation, not a dialog (U8.4)

    # Features ---------------------------------------------------------------------------

    def insert_feature(self, ftype: str, operation: str) -> None:
        """Start an extrude or revolve, feature first (W2, ``new_feature.py``)."""
        from fdcad.ui.main_window.new_feature import FeatureFlow

        if getattr(self, "feature_flow", None) is None:
            self.feature_flow = FeatureFlow(self)
        self.feature_flow.insert(ftype, operation)

    def edit_feature(self, fid: str) -> None:
        """Open an existing feature in the property panel."""
        tab = self.current
        if tab is None or self.panel is None:
            return
        feature = tab.session.document.feature(fid)
        from fdcad.core.document import freeze

        if freeze.is_frozen(tab.session.document, fid):  # TR98 (D2507)
            self.status.setText(freeze.message(feature.name))
            return
        if feature.type == "sketch" and self.sketch_mode is not None:
            self.sketch_mode.edit(fid)
            return
        from fdcad.ui.property_panel.forms import FORMS

        if feature.type in ("extrude", "revolve") or feature.type in FORMS:
            self.panel.begin(tab.session, feature, is_new=False)
            self._left_tab(1)
        elif feature.type in ("ref_plane", "ref_axis", "ref_point", "coord_system"):
            self.reference_tool.edit(fid)
        else:
            from fdcad.ui.body_tools import flow as phase3
            from fdcad.ui.sheet_metal import flow as sheet_metal
            from fdcad.ui.sheet_metal.forms import SHEET_FORMS

            if feature.type in SHEET_FORMS:
                sheet_metal.edit(self, fid)
            else:
                phase3.edit(self, fid)

    def _feature_started(self) -> None:
        """Keep the feature's sketch visible under the preview, and offer its lines as
        a revolve axis in the view (W6.3, W6.4)."""
        from fdcad.ui.main_window.visibility import sketch_of

        tab, panel = self.current, self.panel
        if tab is None or panel is None or panel.feature is None:
            return
        sid = sketch_of(panel.feature)
        tab.editing_sketch = sid
        tab.refresh_sketches()
        offer = getattr(tab.viewport, "show_axis_choices", None)
        if offer is not None and panel.feature.type == "revolve" and sid is not None:
            offer(tab.axis_lines(sid))

    def _feature_applied(self, fid: str, was_new: bool) -> None:
        """Note a feature for Recently Edited; a new one gets its name typed at once
        when the preference asks for it (TR221, D963)."""
        tab = self.current
        if tab is None:
            return
        session = tab.session
        recent = [f for f in getattr(session, "recent_edits", []) if f != fid]
        session.recent_edits = [fid, *recent][:RECENT_EDITS]  # type: ignore[attr-defined]
        if not (was_new and self.settings.name_new_features):
            return

        def rename(*_args: object) -> None:
            with contextlib.suppress(RuntimeError, TypeError):
                session.rebuilt.disconnect(rename)
            tree = self.tree
            if tree is not None and any(f.id == fid for f in session.document.features):
                QTimer.singleShot(0, lambda: tree.rename(fid))

        session.rebuilt.connect(rename)  # the row exists once the tree is filled again

    def _feature_finished(self) -> None:
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if isinstance(tab, DocumentTab) and tab.editing_sketch is not None:
                tab.editing_sketch = None
                tab.refresh_sketches()
                hide = getattr(tab.viewport, "hide_axis_choices", None)
                if hide is not None:
                    hide()

    def _axis_picked(self, entity_id: str) -> None:
        """A sketch line clicked in the view becomes the revolve axis."""
        if self.panel is not None and self.panel.is_editing:
            self.panel.set_axis(entity_id)

    def _refresh_sketches(self) -> None:
        if self.current is not None:
            self.current.refresh_sketches()

    def _start_sketch_on_plane(self, fid: str) -> None:
        """Start a new sketch on a default plane from the feature tree."""
        if self.sketch_mode is not None:
            self.sketch_mode.start(plane_id=fid)

    def show_side_panel(self, widget: QWidget) -> None:
        """Show ``widget`` in the Properties tab (the sketch panel)."""
        drag = getattr(self, "sketch_drag", None)
        if drag is not None:
            drag.cancel()
        # Closing a side panel removes every extra one, so a panel left under this one
        # would vanish while its tool still runs: close it first (Section as with OK).
        appearance = getattr(self, "appearance_tool", None)
        if appearance is not None and appearance.panel not in (None, widget):
            appearance.close()
        section = getattr(self, "section_tool", None)
        if section is not None and section.panel not in (None, widget):
            section.accept()
        if self.properties is not None:
            self.properties.addWidget(widget)
            self.properties.setCurrentWidget(widget)
            self.fit_panels()  # a tool's own panel fits the default width too (D2791)
            self._left_tab(1)

    def hide_side_panel(self) -> None:
        """Return the Properties tab to the property panel."""
        if self.properties is not None and self.panel is not None:
            while self.properties.count() > 1:
                extra = self.properties.widget(1)
                if extra is None:
                    break
                self.properties.removeWidget(extra)
            self.properties.setCurrentWidget(self.panel)
            # A feature that is open keeps its panel in front; else back to the tree.
            self._left_tab(1 if self.panel.is_editing else 0)

    def _show_feature_panel(self) -> None:
        """Put the feature panel in front when a feature opens (D1040).

        A side panel left open (Appearance, Section View, a reference plane) used to
        stay over it, so the feature was open with its fields, OK and Cancel hidden.
        Appearance closes, Section View closes as with its OK (the section stays on)
        and an unfinished reference feature closes as with its Cancel. A sketch that
        is open keeps its own panel.
        """
        if self.properties is None or self.panel is None:
            return
        if self.sketch_mode is not None and self.sketch_mode.is_open:
            return
        appearance = getattr(self, "appearance_tool", None)
        if appearance is not None and appearance.panel is not None:
            appearance.close()
        section = getattr(self, "section_tool", None)
        if section is not None and section.panel is not None:
            section.accept()
        reference = getattr(self, "reference_tool", None)
        if reference is not None and reference.panel is not None:
            reference.close()
        if self.properties.currentWidget() is not self.panel:
            self.properties.setCurrentWidget(self.panel)
        self._left_tab(1)

    def _fill_view_bar(self, tab: DocumentTab) -> None:
        """The view toolbar at the top centre of the view, and the confirmation corner (L5)."""
        from fdcad.ui.main_window.view_bar import fill_view_bar

        fill_view_bar(self, tab)

    @property
    def editing(self) -> str:
        """ "sketch" or "feature" while something is open for editing, else ""."""
        if self.sketch_mode is not None and self.sketch_mode.is_open:
            return "sketch"
        if self.panel is not None and self.panel.is_editing:
            return "feature"
        return ""

    def _undo_for_editing(self) -> None:
        """Undo and Redo are off while a feature panel is open, as in a sketch: they
        would change the part under the panel, and its OK would then fail."""
        tab = self.current
        if self.editing:
            self.undo_group.setActiveStack(None)  # type: ignore[arg-type]  # Qt allows no stack
        elif tab is not None:
            self.undo_group.setActiveStack(tab.session.undo)

    def update_corner(self) -> None:
        """Show the confirmation corner at the top right of the view while editing.

        While sketching it shows an exit sketch mark and a red cross that discards
        the changes (W5.1); while a feature is open, OK and Cancel (PLAN 8 item 3).
        """
        from fdcad.ui.main_window.view_bar import set_corner_icons

        editing = bool(self.editing)
        drag = getattr(self, "sketch_drag", None)
        if drag is not None and (editing or drag.tab not in (None, self.current)):
            drag.cancel()  # a sketch drag (T5.4) ends when editing starts or the tab changes
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if isinstance(tab, DocumentTab) and tab.corner_action is not None:
                tab.corner_action.setVisible(editing and tab is self.current)
                set_corner_icons(tab, self.editing == "sketch")

    def appearance_for(self, fid: str) -> None:
        """Open Appearance for feature ``fid`` from the tree, or for the part with ``""``."""
        tab = self.current
        if tab is None:
            return
        # Faces picked earlier would come first in the panel; the tree row is what was asked for.
        tab.selection = []
        clear = getattr(tab.viewport, "select_shapes", None)
        if clear is not None:
            clear([])
        if self.tree is not None:
            if fid:
                self.tree.select(fid)
            else:
                from PySide6.QtCore import QModelIndex

                self.tree.setCurrentIndex(QModelIndex())
        self.appearance_tool.open()

    def viewport_menu(self, pos: Any = None) -> QMenu | None:
        """Right click in the 3D view opens the menu for what is under the cursor (T9,
        D116 item 2). The shortcut bar opens with Q only."""
        from PySide6.QtCore import QPointF

        tab = self.current
        if tab is None:
            return None
        return self.context_menus.view_menu(tab, pos if pos is not None else QPointF(-1, -1))

    def _face_under_cursor(self) -> Any:
        """The face under the cursor in the 3D view, or None."""
        tab = self.current
        under = getattr(tab.viewport, "shape_under_cursor", None) if tab is not None else None
        shape = under() if under is not None else None
        if shape is None and tab is not None and len(tab.selection) == 1:
            shape = tab.selection[0]
        from OCP.TopAbs import TopAbs_FACE

        return shape if shape is not None and shape.ShapeType() == TopAbs_FACE else None

    def confirm_ok(self) -> None:
        """OK in the confirmation corner."""
        if self.editing == "sketch" and self.sketch_mode is not None:
            self.sketch_mode.accept()
        elif self.editing == "feature" and self.panel is not None:
            self.panel.accept()
        self.update_corner()

    def confirm_cancel(self) -> None:
        """Cancel in the confirmation corner."""
        if self.editing == "sketch" and self.sketch_mode is not None:
            self.sketch_mode.cancel()
        elif self.editing == "feature" and self.panel is not None:
            self.panel.reject()
        self.update_corner()

    def _enter(self) -> None:
        """Enter in the view: OK while a feature is open (W6.5), else repeat the last command."""
        if self.editing == "feature":
            self.confirm_ok()
        else:
            self.commands.repeat()

    def _escape(self) -> None:
        """Escape in the 3D view stops a running rebuild or slow preview after a confirm
        (TR126, D814), else cancels an open feature (W6.5), else leaves Isolate (T12.4,
        audit D11 item 3, D719)."""
        if self.stop_long_work():
            return
        if self.editing == "feature":
            self.confirm_cancel()
            return
        tab = self.current
        if tab is not None and tab.isolated is not None:
            self.body_display.isolate()  # pressing I again leaves isolate

    def stop_long_work(self) -> bool:
        """Esc while a rebuild or a feature preview is running: ask, then stop it (TR126).
        The part keeps its last finished state. True when something was running."""
        tab = self.current
        rebuilding = tab is not None and tab.session.is_rebuilding
        previewing = (
            self.editing == "feature" and self.preview is not None and self.preview.is_running
        )
        if not rebuilding and not previewing:
            return False
        answer = QMessageBox.question(
            self,
            strings.APP,
            strings.STOP_REBUILD if rebuilding else strings.STOP_PREVIEW,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return True
        if rebuilding and tab is not None:
            tab.session.cancel_rebuild()
            self.status.setText(strings.REBUILD_STOPPED)
        elif self.preview is not None:
            self.preview.stop()
            self.status.setText(strings.PREVIEW_STOPPED)
        return True

    def corner_at_cursor(self) -> QMenu | None:
        """Show OK and Cancel at the cursor (shortcut A)."""
        from PySide6.QtGui import QCursor

        if not self.editing:
            return None
        menu = QMenu(self)
        menu.setObjectName("confirmation_popup")
        self._action(menu, strings.OK, self.confirm_ok)
        self._action(menu, strings.CANCEL, self.confirm_cancel)
        if self.isVisible():
            menu.popup(QCursor.pos())
        return menu

    def _errors_count(self, count: int) -> None:
        if self.left is not None and self.errors is not None:
            self.left.set_count(self.errors, strings.TAB_ERRORS, count)

    def highlight_names(self, names: list[str]) -> None:
        """Highlight named faces, edges and vertices of the active part."""
        tab = self.current
        highlight = getattr(tab.viewport, "highlight", None) if tab else None
        report = tab.session.report if tab else None
        if highlight is None or report is None or report.body is None:
            return
        from fdcad.core.naming.select import shapes_for_names

        highlight(shapes_for_names(report.body, names) if names else [])

    def _set_printer(self, session: Any) -> bool:
        """Give the part the printer in use's fit tolerance for equations (TR180, D812).
        True when it changed."""
        from fdcad.core.equations.engine import PRINTER_KEY
        from fdcad.ui.preferences.print_settings import active_profile

        values = {"fit_tolerance": active_profile(self.settings).fit_tolerance}
        if session.document.measured.get(PRINTER_KEY) == values:
            return False
        session.document.measured[PRINTER_KEY] = values
        return True

    def _printer_changed(self) -> None:
        """Another printer or tolerance: parts whose formulas use it rebuild."""
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            session = getattr(tab, "session", None)
            if session is not None and self._set_printer(session):
                session.request_rebuild()

    def edit_properties(self) -> bool:
        """Custom Properties (TR82, D810). False when no part is open or it is cancelled."""
        from fdcad.ui.commands.print_setup import SetProperties
        from fdcad.ui.main_window.properties_dialog import PropertiesDialog, run

        tab = self.current
        if tab is None:
            return False
        session = tab.session
        dialog = PropertiesDialog(session.document, self)
        accepted = run(dialog)
        found = dialog.data()
        dialog.deleteLater()
        if not accepted or isinstance(found, str) or found == session.document.properties:
            return False
        session.undo.push(SetProperties(session, found, strings.PROPS_UNDO))
        return True

    def edit_material(self) -> bool:
        """Choose the part's material (TR78, D803). False when no part is open or the
        dialog is cancelled."""
        from fdcad.ui.commands.print_setup import SetMaterial
        from fdcad.ui.main_window.material_dialog import MaterialDialog, run
        from fdcad.ui.preferences.print_settings import densities

        tab = self.current
        if tab is None:
            return False
        session = tab.session
        dialog = MaterialDialog(session.document, densities(self.settings), self)
        accepted = run(dialog)
        material, colour = dialog.material(), dialog.colour()
        dialog.deleteLater()
        if not accepted:
            return False
        if material == session.document.material and colour is None:
            return False
        session.undo.push(SetMaterial(session, material, colour, strings.MATERIAL_UNDO))
        return True

    def show_lost_ghost(self, ref: dict[str, Any] | None) -> None:
        """Draw where a lost pick was, faintly (TR125 item 2); None clears it. The shape
        is made on a worker thread (CLAUDE.md rule 2)."""
        from fdcad.ui.print_tools import jobs

        tab = self.current
        show = getattr(tab.viewport, "show_lost", None) if tab is not None else None
        if show is None:
            return
        self._ghost_round = getattr(self, "_ghost_round", 0) + 1
        if ref is None:
            show(None)
            return
        from fdcad.core.naming.repair import ghost

        wanted = self._ghost_round

        def done(shape: Any) -> None:
            if wanted == self._ghost_round:
                show(shape)

        jobs.start(lambda: ghost(ref), done, lambda _m: None)

    def _open_from_errors(self, fid: str) -> None:
        if self.tree is not None:
            self.tree.select(fid)
        self.edit_feature(fid)

    def apply_fix(self, fid: str, fix: Any) -> None:
        """Run a fix the user clicked (never automatically, CLAUDE.md rule 12)."""
        from fdcad.core.document.model import Param
        from fdcad.ui.commands.document import SetParam

        tab = self.current
        if tab is None:
            return
        from fdcad.ui.body_tools import flow as phase3

        if phase3.apply_fix(self, fid, fix):
            return
        session = tab.session
        if fix.action == "show_cause":  # TR288: select the feature that took the face away
            cause = str(fix.data.get("feature", ""))
            if self.tree is not None and any(f.id == cause for f in session.document.features):
                self.tree.select(cause)
                self.status.setText(
                    strings.SHOW_CAUSE_DONE.format(name=session.document.feature(cause).name)
                )
            return
        if fix.action == "add_to_param":
            feature = session.document.feature(str(fix.data.get("feature", fid)))
            name = str(fix.data["param"])
            current = feature.params.get(name)
            if not isinstance(current, Param):
                return
            delta = float(fix.data["delta"])
            session.undo.push(SetParam(session, feature.id, name, added(current, delta, session)))
        elif fix.action == "update_links":
            if not self._update_links(session, fix):
                return
        elif fix.action == "tie_values":  # a picked face that split (D2628)
            from fdcad.core.features.fixes import tied_values
            from fdcad.ui.commands.document import TieValues

            tied = tied_values(session.document, fix)
            if tied is None:
                return
            session.undo.push(TieValues(session, tied[0], tied[1], fix.label))
        elif fix.action == "split_fillet":  # TR346 (D1405)
            from fdcad.ui.tree.change_fillets import split_fillet_command

            split_fillet_command(session, fid, fix)
        elif fix.action == "limit_failing":  # TR271 (D1802)
            from fdcad.ui.tree.change_fillets import limit_failing_command

            limit_failing_command(session, fid, fix)
        elif fix.action in FIX_ACTIONS:
            from fdcad.core.features.fixes import fixed_feature
            from fdcad.ui.commands.document import ReplaceFeature

            edited = fixed_feature(session.document, fid, fix)
            if edited is None:
                return
            session.undo.push(ReplaceFeature(session, edited))
        elif fix.action == "dismiss":
            from fdcad.ui.commands.document import SetKeepSeparateBody

            for issue_fid, code in _codes_for(session, fid, fix):
                if code == "separate_body":  # saved in the part (D527)
                    session.undo.push(SetKeepSeparateBody(session, issue_fid, True))
                else:
                    session.dismissed.add((issue_fid, code))
            if self.errors is not None:
                self.errors.refresh()
        self.status.setText(strings.FIX_APPLIED.format(label=fix.label))

    def _refresh_tree_for(self, session: DocumentSession) -> Callable[[], None]:
        """Refresh the tree after a display change of the part it shows (Appearances row)."""

        def refresh() -> None:
            from fdcad.ui.appearance.tree_rows import update_row

            if self.tree is not None and self.tree.session is session:
                update_row(self.tree, session.document)

        return refresh

    def _appearance_row_clicked(self, item: Any, _column: int) -> None:
        """The Appearances row of the tree opens the Appearance panel (P2.11 item 1)."""
        from fdcad.ui.appearance.entries import LABEL_ROLE, TARGETS_ROLE, change_color, row_targets
        from fdcad.ui.appearance.tree_rows import APPEARANCE_ROLE
        from fdcad.ui.tree.feature_tree import FID_ROLE, MATERIAL_MARK

        if item.data(0, FID_ROLE) == MATERIAL_MARK:  # the Material row (TR78)
            self.edit_material()
            return
        targets = row_targets(item.data(0, TARGETS_ROLE))
        session = self.tree.session if self.tree is not None else None
        if targets and session is not None:  # a colour row: change that colour (D584)
            change_color(session, targets, str(item.data(0, LABEL_ROLE) or ""), self)
        elif item.data(0, APPEARANCE_ROLE) is not None:
            self.appearance_tool.open()

    def _update_links(self, session: Any, fix: Any) -> bool:
        """Update Copies: move a sketch's stale part copies, one undoable step (D250)."""
        import contextlib
        import copy

        from fdcad.core.sketch.links import apply_links, updates_from_data
        from fdcad.core.sketch.model import sketch_from_data, sketch_to_data
        from fdcad.core.sketch.solver import SketchSolveError, solve
        from fdcad.ui.commands.document import ReplaceFeature

        try:
            feature = copy.deepcopy(session.document.feature(str(fix.data["feature"])))
        except KeyError:
            return False
        sketch = sketch_from_data(feature.data)
        if not apply_links(sketch, updates_from_data(fix.data.get("updates"))):
            return False
        with contextlib.suppress(SketchSolveError):
            solve(sketch)  # tied geometry follows the copies; kept as is when unsolvable
        feature.data.update(sketch_to_data(sketch))
        session.undo.push(ReplaceFeature(session, feature, f"Update Copies in {feature.name}"))
        return True

    def _left_tab(self, index: int) -> None:
        if self.left is not None:
            self.left.setCurrentIndex(index)

    # View and tools ---------------------------------------------------------------------

    def rebuild(self) -> None:
        """Rebuild the active part, reading its linked equations file first (TR25). While
        rebuilds are paused, Rebuild applies the edits and leaves the pause (TR276)."""
        if self.current is not None:
            note = self.current.session.read_linked_equations()
            if note:
                self.feedback.flash(note)
            if self.current.session.paused:
                self.current.session.rebuild_paused(stay=False)
            else:
                self.current.session.request_rebuild()

    def force_rebuild(self) -> None:
        """Rebuild every feature from scratch, ignoring cached results. Threads shown as
        cosmetic while editing are made real (TR347, D1921) until the next edit."""
        if self.current is not None:
            engine = self.current.session.engine
            engine.cache.clear()
            engine.real_once = True
            self.current.session.release_hold()  # asked for by name: build it all (D1035)
            self.current.session.request_rebuild()

    def _active_view(self) -> Any:
        """The sketch canvas while sketching, else the 3D view of the active part."""
        mode = self.sketch_mode
        if mode is not None and mode.is_open and mode.canvas is not None:
            return mode.canvas
        return self.current.viewport if self.current else None

    def _call_view(self, name: str, *args: Any) -> Any:
        view = self._active_view()
        tab = self.current
        pane = getattr(tab, "active_pane", None) if tab is not None else None
        if pane is not None and view is getattr(tab, "viewport", None):
            # Split View: the active pane takes the view commands it has (TR16).
            fn = getattr(pane, name, None)
            if fn is not None:
                return fn(*args)
        fn = getattr(view, name, None)
        return fn(*args) if fn is not None else None

    def set_split(self, layout: str) -> None:
        """Split View for the active part (TR16)."""
        tab = self.current
        if tab is None:
            return
        if not tab.set_split(layout):
            self.status.setText(strings.SPLIT_NO_VIEW)
        for name in ("one", "side", "stacked", "four"):
            action = self.commands.actions.get(f"view.split_{name}")
            if action is not None:
                action.setChecked(name == tab.split)

    def _plane_selection(self) -> None:
        """A plane selected in the tree shows in the selection colour in the 3D view (T13)."""
        tab, tree = self.current, self.tree
        if tab is None or tree is None:
            return
        mark = getattr(tab.viewport, "set_selected_planes", None)
        fid = tree.selected_id()
        if mark is not None:
            is_plane = fid is not None and tab.session.document.feature(fid).type in (
                "plane",
                "ref_plane",
            )
            mark({fid} if is_plane and fid is not None else set())

    # Shortcuts of TOOL_SPEC T12.4 ----------------------------------------------------------

    def _feature_edges(self) -> None:
        """Draw the selected feature's edges when the preference is on (TR212)."""
        from fdcad.ui.main_window import view_prefs

        view_prefs.feature_edges(self)

    def display_states(self) -> bool:
        """Display States for the active part (TR88, D1608)."""
        from fdcad.ui.main_window import display_states_ui

        return display_states_ui.run(self)

    def display_quality(self) -> bool:
        """Display Quality for the active part (TR214, D1605)."""
        from fdcad.ui.viewport import display_quality

        return display_quality.run(self)

    def show_orientation_popup(self) -> None:
        """The orientation popup at the cursor (TR210 item 2, D1601)."""
        from fdcad.ui.main_window import orientation_popup

        orientation_popup.show(self)

    def show_view_selector(self) -> QWidget:
        """The view selector cube at the centre of the view (Ctrl+Space, T14.4.2)."""
        from fdcad.ui.viewport.view_selector import ViewSelector

        old = getattr(self, "view_selector", None)
        if old is not None:
            old.deleteLater()  # one selector at a time; old ones stayed (D637)
        selector = ViewSelector(self)
        selector.chosen.connect(lambda eye, up: self._call_view("look", eye, up))
        view = self._active_view()
        # At the centre of the view (T14.4.2), or at the cursor with no view.
        at = view.mapToGlobal(view.rect().center()) if view is not None else QCursor.pos()
        if self.isVisible():
            selector.open_at(at)
        self.view_selector = selector
        return selector

    def hide_or_show(self) -> bool:
        """Hide the selected bodies, sketch or plane, or show them again (H).

        Bodies picked in the view (or a body row in the tree) come first (D410).
        False when nothing that can be hidden is selected.
        """
        if self.body_display.hide_or_show():
            return True
        tab, tree = self.current, self.tree
        fid = tree.selected_id() if tree is not None else None
        if tab is None or tree is None or fid is None:
            self.status.setText(strings.HIDE_SHOW_NOTHING)
            return False
        kind = tab.session.document.feature(fid).type
        if kind == "sketch":
            shown = fid in tab.visible_sketch_ids()
        elif kind in ("plane", "ref_plane"):
            shown = fid in tab.visible_plane_ids()
        elif kind in ("ref_axis", "ref_point", "coord_system"):
            shown = fid in tab.visible_datum_ids()
        else:
            self.status.setText(strings.HIDE_SHOW_NOTHING)
            return False
        tree.set_visible(fid, not shown)
        return True

    def toggle_reference_geometry(self) -> None:
        """Hide every plane, axis, point and coordinate system in the 3D view, or show them
        again (Ctrl+H)."""
        tab = self.current
        if tab is None:
            return
        tab.reference_hidden = not tab.reference_hidden
        tab.refresh_sketches()
        action = getattr(self, "show_planes_action", None)
        if action is not None:
            action.setChecked(not tab.reference_hidden)
        self.status.setText(
            strings.REFERENCE_HIDDEN if tab.reference_hidden else strings.REFERENCE_SHOWN
        )

    def toggle_flat_tree(self) -> None:
        """Show the feature tree as one flat list, or nested again (Ctrl+T)."""
        if self.tree is not None:
            self.tree.set_flat(self.flat_tree_action.isChecked())

    def show_snap_options(self) -> QWidget:
        """The snap settings as a small popup at the cursor (F3)."""
        from fdcad.ui.main_window.snap_popup import SnapOptions

        old = getattr(self, "snap_popup", None)
        if old is not None:
            old.deleteLater()  # one popup at a time; old ones stayed (D637)
        popup = SnapOptions(self.settings, self)
        popup.changed.connect(self._sketch_options_changed)
        if self.isVisible():
            popup.open_at(QCursor.pos())
        self.snap_popup = popup
        return popup

    def _sketch_options_changed(self) -> None:
        mode = self.sketch_mode
        if mode is not None and mode.canvas is not None:
            mode.canvas.set_options(self.settings.sketch_options)

    def zoom_to_fit(self) -> None:
        """Fit the part, or the sketch, in the view."""
        if self._call_view("fit_all") is None:
            self._call_view("fit")

    def zoom_to_area(self) -> None:
        """Zoom to a box the user drags next in the 3D view."""
        start = getattr(self._active_view(), "start_zoom_area", None)
        if start is not None:
            start()
            self.status.setText(strings.ZOOM_AREA_HINT)

    def zoom_in(self) -> None:
        """Zoom in one step."""
        self._call_view("zoom_in")

    def zoom_out(self) -> None:
        """Zoom out one step (TR211)."""
        self._call_view("zoom_out")

    def view_turn_ms(self) -> int:
        """How long standard view changes animate: 0 when animations are off (U6.6, U7)."""
        from fdcad.ui.viewport.views import TURN_MS

        return TURN_MS if self.settings.animations else 0

    def set_view(self, name: str) -> None:
        """Switch to a standard view, turned as this part's own views say (TR333)."""
        from fdcad.core.document.view_frame import KEY

        session = getattr(self.current, "session", None)
        frame = getattr(self, "view_frame", None)
        if session is not None and frame is not None and KEY in session.document.extra:
            frame.look(name)
            return
        self._call_view("set_view", name)

    def previous_view(self) -> None:
        """Go back to the view before the last view change."""
        self._call_view("previous_view")

    def redraw(self) -> None:
        """Redraw the view."""
        view = self._active_view()
        if view is not None:
            if hasattr(view, "redraw"):
                view.redraw()
            else:
                view.update()

    def set_style(self, style: str) -> None:
        """Change the display style of every open part."""
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            fn = getattr(getattr(tab, "viewport", None), "set_style", None)
            if fn is not None:
                fn(style)

    def toggle_mirror_image(self) -> bool:
        """Show a mirror image of the part about the plane picked in the tree, or the
        Right plane, display only (TR309, D926). Returns True when it is shown."""
        from fdcad.ui import strings_extra as text

        action = self.commands.actions["view.mirror_image"]
        tab = self.current
        image = getattr(getattr(tab, "viewport", None), "mirror_image", None)
        if tab is None or image is None:
            action.setChecked(False)
            return False
        if not action.isChecked():
            image.set_plane(None)
            self.status.setText(text.MIRROR_IMAGE_OFF)
            return False
        plane, name = self._mirror_plane(tab)
        image.set_plane((plane.origin, plane.normal))
        self.status.setText(text.MIRROR_IMAGE_ON.format(name=name))
        return True

    def _mirror_plane(self, tab: DocumentTab) -> tuple[Any, str]:
        """The plane feature picked in the tree, else the Right plane, and its name."""
        from fdcad.core.sketch.profiles import BASIS_PLANES

        fid = self.tree.selected_id() if self.tree is not None else None
        report = tab.session.report
        if fid is not None and report is not None and fid in report.results:
            feature = tab.session.document.feature(fid)
            plane = report.results[fid].plane
            if plane is None and feature.type == "plane":
                plane = BASIS_PLANES.get(str(feature.params.get("basis")))
            if plane is not None:
                return plane, feature.name
        right = next(
            (
                f.name
                for f in tab.session.document.features
                if f.type == "plane" and f.params.get("basis") == "yz"
            ),
            "Right Plane",
        )
        return BASIS_PLANES["yz"], right

    def toggle_temporary_axes(self) -> None:
        """Show or hide the temporary axes in every open part (TR17)."""
        on = self.commands.actions["view.temporary_axes"].isChecked()
        for i in range(self.tabs.count()):
            fn = getattr(getattr(self.tabs.widget(i), "viewport", None), "set_temporary_axes", None)
            if fn is not None:
                fn(on)

    def offset_plane_from_drag(self, plane_id: str, offset_mm: float) -> bool:
        """Open the Plane panel for a plane offset from ``plane_id`` by the dragged
        distance, rounded, so a typed value can replace it (TR10). False when the drag
        was too short to round to a distance or no part is open."""
        from fdcad.core.document.model import Feature, Param
        from fdcad.ui.viewport.plane_drag import rounded

        tab = self.current
        if tab is None:
            return False
        doc = tab.session.document
        mm, typed = rounded(offset_mm, doc.units)
        if mm <= 0:
            return False
        feature = Feature(
            doc.new_feature_id(),
            "ref_plane",
            self.reference_tool.new_name("ref_plane"),
            params={"method": "offset", "distance": Param(typed, mm), "flip": offset_mm < 0},
            refs={"first": {"feature": plane_id}},
        )
        self.reference_tool.start_with(feature)
        return True

    def toggle_lasso(self) -> None:
        """Lasso selection on or off in every open part (TR19)."""
        on = self.commands.actions["select.lasso"].isChecked()
        for i in range(self.tabs.count()):
            fn = getattr(getattr(self.tabs.widget(i), "viewport", None), "set_lasso", None)
            if fn is not None:
                fn(on)

    def _pick_only_slot(self, kind: str) -> Callable[..., object]:
        """A menu slot that limits picking to ``kind`` (TR329)."""
        return lambda *_args: self.pick_only(kind)

    def pick_only(self, kind: str) -> bool:
        """Pick Bodies, Faces or Edges Only (TR329, D2208): the filter takes that type
        alone; the same command again lets every type pick. Returns True when on."""
        on = self.selection_filter.only(kind)
        if self._filter_bar is not None:
            self._filter_bar.sync()
        self._filters_changed()
        return on

    def toggle_paint(self) -> None:
        """Paint Selection on or off in every open part (TR329, D2208)."""
        on = self.commands.actions["select.paint"].isChecked()
        for i in range(self.tabs.count()):
            fn = getattr(getattr(self.tabs.widget(i), "viewport", None), "set_paint", None)
            if fn is not None:
                fn(on)

    def pick_in_volume(self) -> Any:
        """Pick in Volume (TR329, D2208): ask for the volume, then pick in a job."""
        from fdcad.ui.main_window.pick_volume import open_pick_volume

        return open_pick_volume(self)

    def toggle_perspective(self) -> None:
        """Perspective or parallel view in every open part (TR15)."""
        on = self.commands.actions["view.perspective"].isChecked()
        for i in range(self.tabs.count()):
            fn = getattr(getattr(self.tabs.widget(i), "viewport", None), "set_perspective", None)
            if fn is not None:
                fn(on)

    def toggle_transparency(self) -> None:
        """Make the active part see through, or opaque again."""
        self._call_view("toggle_transparency")

    def normal_to(self) -> None:
        """Normal To with the rules of T14.4.1 (``view_commands.normal_to``)."""
        from fdcad.ui.main_window.view_commands import normal_to

        normal_to(self)

    def zoom_to_selection(self) -> None:
        """Fit the view to the selection (D106, T14.4.3)."""
        from fdcad.ui.main_window.view_commands import zoom_to_selection

        zoom_to_selection(self)

    def _build_show_menu(self, view: QMenu) -> None:
        """View > Hide or Show: planes, origins, sketches and sketch relations (T14.4.3)."""
        from fdcad.ui import strings_extra as text
        from fdcad.ui.main_window import view_commands as vc

        a = self.commands
        menu = view.addMenu(text.SHOW_MENU)
        self.show_planes_action = a.add(
            "view.show_planes",
            lambda: vc.set_planes_shown(self, self.show_planes_action.isChecked()),
            checkable=True,
        )
        self.show_planes_action.setChecked(True)
        self.show_origins_action = a.add(
            "view.show_origins",
            lambda: vc.set_origins_shown(self, self.show_origins_action.isChecked()),
            checkable=True,
        )
        self.show_sketches_action = a.add(
            "view.show_sketches",
            lambda: vc.set_sketches_shown(self, self.show_sketches_action.isChecked()),
            checkable=True,
        )
        self.show_sketches_action.setChecked(True)
        for action in (
            self.show_planes_action,
            self.show_origins_action,
            self.show_sketches_action,
        ):
            menu.addAction(action)
        if self.sketch_mode is not None:
            menu.addAction(self.sketch_mode.relations_action)
            menu.addAction(self.sketch_mode.combs_action)  # curvature combs (D514)
        self._build_type_menu(view)  # TR215

    def _build_type_menu(self, view: QMenu) -> None:
        """View > Show Types: a tick per kind of item drawn in the view, and Hide All Types,
        which turns every kind off and back on as it was (TR215, D819)."""
        menu = view.addMenu(strings.SHOW_TYPES)
        menu.setObjectName("show_types")
        self.type_actions: dict[str, QAction] = {}
        for key in ("planes", "axes", "points", "frames", "curves"):
            action = menu.addAction(strings.SHOW_TYPE_NAMES[key])
            action.setCheckable(True)
            action.setChecked(True)
            action.toggled.connect(lambda on, k=key: self.set_type_shown(k, on))
            self.type_actions[key] = action
        others = [
            self.show_sketches_action,
            self.show_origins_action,
            self.commands.actions.get("view.temporary_axes"),
            self.commands.actions.get("view.all_dimensions"),
        ]
        if self.sketch_mode is not None:
            others.append(self.sketch_mode.relations_action)
        menu.addSeparator()
        for extra in others:
            if extra is not None:
                menu.addAction(extra)
        menu.addSeparator()
        self._types_before: dict[QAction, bool] | None = None
        hide_all = menu.addAction(strings.HIDE_ALL_TYPES)
        hide_all.setObjectName("hide_all_types")
        hide_all.triggered.connect(lambda _c=False: self.hide_all_types())
        self._type_toggles = [*self.type_actions.values(), *(a for a in others if a is not None)]

    def set_type_shown(self, key: str, on: bool) -> None:
        """Show or hide one kind in every open part's view (view state, not saved)."""
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            hidden = getattr(tab, "hidden_types", None)
            if hidden is None:
                continue
            if on:
                hidden.discard(key)
            else:
                hidden.add(key)
            refresh = getattr(tab, "refresh_types", None)
            if refresh is not None:
                refresh()

    def hide_all_types(self) -> None:
        """Hide All Types, or when every kind was hidden by it, show them as they were."""
        if self._types_before is not None:
            for action, was in self._types_before.items():
                if action.isCheckable() and action.isChecked() != was:
                    action.trigger()
            self._types_before = None
            return
        self._types_before = {a: a.isChecked() for a in self._type_toggles if a.isCheckable()}
        for action in self._types_before:
            if action.isChecked():
                action.trigger()

    def _build_filters(self, menu: QMenu) -> None:
        """Selection filter keys and menu items (T14.3.2); the bar is made on first use."""
        from fdcad.ui.input.selection_rules import SelectionFilter

        a = self.commands
        self.selection_filter = SelectionFilter()
        self._filter_bar: Any = None
        menu.addAction(a.add("select.filter_bar", lambda: self.filter_bar.toggle_shown()))
        menu.addAction(a.add("select.filters_toggle", self.toggle_filters))
        menu.addSeparator()
        for cid, kind in (
            ("select.filter_edges", "edge"),
            ("select.filter_faces", "face"),
            ("select.filter_vertices", "vertex"),
        ):
            menu.addAction(a.add(cid, partial(self.toggle_filter, kind)))
        menu.addAction(a.add("select.other", self.select_other_at_cursor))
        menu.addAction(a.add("select.previous", self.select_previous))  # TR93
        menu.addAction(a.add("select.invert", self.invert_selection))
        menu.addAction(a.add("select.all", self.select_all))  # TR380, TR224
        from fdcad.ui.main_window.select_similar import SelectSimilar

        self.select_similar = SelectSimilar(self)  # TR303 (D943)
        menu.addAction(a.add("select.similar", lambda: self.select_similar.similar()))
        menu.addAction(a.add("select.to_edges", lambda: self.select_similar.convert("edges")))
        menu.addAction(a.add("select.to_faces", lambda: self.select_similar.convert("faces")))
        menu.addAction(a.add("select.to_bodies", lambda: self.select_similar.convert("bodies")))
        from fdcad.ui.main_window.selection_sets import SelectionSets

        self.selection_sets = SelectionSets(self)  # TR94 (D944)
        menu.addAction(a.add("select.save_set", lambda: self.selection_sets.save_picks()))
        menu.addAction(a.add("select.sets", self.selection_sets.show))
        menu.addAction(a.add("select.lasso", self.toggle_lasso, checkable=True))  # TR19
        # TR329 (D2208): one pick type at once, paint pick and pick by volume.
        for kind in ("body", "face", "edge"):
            name = f"select.only_{kind}s" if kind != "body" else "select.only_bodies"
            menu.addAction(a.add(name, self._pick_only_slot(kind)))
        menu.addAction(a.add("select.paint", self.toggle_paint, checkable=True))
        menu.addAction(a.add("select.in_volume", self.pick_in_volume))

    @property
    def filter_bar(self) -> Any:
        """The selection filter bar, made the first time it is needed (startup memory)."""
        if self._filter_bar is None:
            from fdcad.ui.main_window.filter_bar import FilterBar

            bar = FilterBar(self.selection_filter, self)
            self.addToolBar(Qt.ToolBarArea.RightToolBarArea, bar)
            bar.hide()
            bar.changed.connect(self._filters_changed)
            self._filter_bar = bar
        return self._filter_bar

    def toggle_filter(self, kind: str) -> bool:
        """E, X, V: switch one type's selection filter. Returns its new state."""
        on = self.selection_filter.toggle(kind)
        if self._filter_bar is not None:
            self._filter_bar.sync()
        self._filters_changed()
        return on

    def toggle_filters(self) -> bool:
        """F6: turn the chosen selection filters on or off at once."""
        on = self.selection_filter.toggle_enabled()
        if self._filter_bar is not None:
            self._filter_bar.sync()
        self._filters_changed()
        return on

    def _filters(self) -> set[str]:
        model = getattr(self, "selection_filter", None)
        return model.view_kinds() if model is not None else {"face", "edge", "vertex"}

    def _filters_changed(self) -> None:
        """Send the selection filter to every 3D view and the open sketch (T14.3.2)."""
        from fdcad.ui import strings_extra as text

        model = getattr(self, "selection_filter", None)
        on = model is not None and model.is_on()
        for i in range(self.tabs.count()):
            fn = getattr(getattr(self.tabs.widget(i), "viewport", None), "set_filters", None)
            if fn is not None:
                fn(self._filters(), on)
        self._filter_sketch()
        if model is not None:
            names = ", ".join(text.FILTER_NAMES[k] for k in sorted(model.active))
            self.status.setText(
                text.FILTER_STATUS.format(names=names) if on else text.FILTER_STATUS_NONE
            )

    def _filter_sketch(self, *_args: object) -> None:
        """The open sketch selects only the filtered types and shows the filter cursor."""
        from fdcad.core.sketch.model import Point
        from fdcad.ui.input.filter_cursor import filter_cursor
        from fdcad.ui.input.selection_rules import SelectionFilter, sketch_kind

        model: SelectionFilter | None = getattr(self, "selection_filter", None)
        mode = self.sketch_mode
        canvas = mode.canvas if mode is not None else None
        if canvas is None or model is None:
            return
        if not model.is_on():
            canvas.select_filter = None
        else:

            def allowed(item: str) -> bool:
                sk = canvas.edit.sketch
                points = [e.id for e in sk.entities.values() if isinstance(e, Point)]
                return model.allows(sketch_kind(item, points))

            canvas.select_filter = allowed
        if canvas.tool is None and not canvas.dimension_mode:
            if model.is_on():
                canvas.setCursor(filter_cursor())
            else:
                canvas.unsetCursor()

    def select_previous(self) -> bool:
        """Pick again what was picked before the selection was cleared (TR93, D915)."""
        from fdcad.ui import strings_extra as text

        tab = self.current
        if tab is None or self.editing == "sketch":
            return False
        memory = getattr(tab.viewport, "selection_memory", None)
        if memory is None or not memory.restore():
            self.status.setText(text.SELECT_PREVIOUS_NONE)
            return False
        return True

    def select_all(self) -> int:
        """Select All (TR380, TR224, D934): in a sketch, every sketch item; in the 3D view,
        every face, or every item of the kinds picked or allowed by the filter."""
        from fdcad.ui import strings_extra as text

        tab = self.current
        if tab is None:
            return 0
        mode = self.sketch_mode
        if self.editing == "sketch" and mode is not None and mode.canvas is not None:
            canvas = mode.canvas
            sk = canvas.edit.sketch
            canvas.selection = [
                e.id for e in sk.entities.values() if not canvas.hidden_construction(e)
            ]
            canvas.selection_changed.emit()
            canvas.update()
            self.status.setText(text.INVERTED.format(count=len(canvas.selection)))
            return len(canvas.selection)
        if not hasattr(tab.viewport, "_part_shape"):
            return 0
        from fdcad.ui.viewport.select_more import select_all

        model = getattr(self, "selection_filter", None)
        allowed = model.view_kinds() if model is not None and model.is_on() else None
        count = select_all(tab.viewport, allowed)
        self.status.setText(text.INVERTED.format(count=count))
        return count

    def invert_selection(self) -> int:
        """Pick what is not picked, of the kinds the filter allows (TR93, D915)."""
        from fdcad.ui import strings_extra as text
        from fdcad.ui.viewport.select_more import invert

        tab = self.current
        if tab is None or self.editing == "sketch" or not hasattr(tab.viewport, "_part_shape"):
            return 0
        model = getattr(self, "selection_filter", None)
        allowed = model.view_kinds() if model is not None and model.is_on() else None
        count = invert(tab.viewport, allowed)
        self.status.setText(text.INVERTED.format(count=count))
        return count

    def select_other_at_cursor(self) -> object:
        """Select Other for what lies under the cursor in the 3D view (T14.3.1)."""
        tab = self.current
        if tab is None or self.editing == "sketch":
            return None
        view = tab.viewport
        pos = view.mapFromGlobal(QCursor.pos())
        return self.context_menus.select_other(tab, QPointF(pos))

    def _selection_changed(self, tab: DocumentTab, shapes: list[Any]) -> None:
        tab.selection = list(shapes)
        crumbs = getattr(tab, "breadcrumbs", None)
        if crumbs is not None:  # TR20: the chain of the last picked item
            from fdcad.ui.main_window.breadcrumbs import chain_for

            crumbs.set_chain(chain_for(tab, shapes))
        follow = getattr(self, "tree_follow", None)
        if follow is not None and tab is self.current:
            follow.picked(tab, shapes)  # TR200
        if tab is self.current:
            base = selection_text(shapes) if shapes else strings.READY
            self.status.setText(base)
            self.measure_tool.status_for(shapes, base)
            from fdcad.ui.body_tools import flow as phase3

            if phase3.picked(self, tab, shapes):
                return
            self._edge_as_axis(tab, shapes)
            self._pick_for_start(tab, shapes)
            from fdcad.ui.main_window.feature_picks import route_pick

            route_pick(self, tab, shapes)
            graph = getattr(self, "curvature_graph", None)
            if graph is not None:
                graph.refresh()

    def model_cursor(self, tab: DocumentTab, point: tuple[float, float, float] | None) -> None:
        """Show the model point under the cursor in the status bar, or nothing (L6, W8)."""
        tab.cursor_model = point  # type: ignore[attr-defined]  # hole clicks (P4.1)
        if tab is not self.current or (self.sketch_mode is not None and self.sketch_mode.is_open):
            return
        if point is None:
            self.coords.setText("")
            return
        from fdcad.ui.sketch_tools.canvas import format_length

        units = tab.session.document.units
        x, y, z = (format_length(v, units) for v in point)
        text = strings.MODEL_CURSOR.format(x=x, y=y, z=z)
        from fdcad.ui.main_window.hover_status import hover_text

        extra = hover_text(tab)  # TR221: the hovered edge or the angle between faces
        self.coords.setText(f"{text}   {extra}" if extra else text)

    def _edge_as_axis(self, tab: DocumentTab, shapes: list[Any]) -> None:
        """While a revolve is open, a clicked straight part edge becomes its axis (W6.3)."""
        from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE

        from fdcad.core.naming.select import straight_edge_reference

        panel, report = self.panel, tab.session.report
        if panel is None or panel.feature is None or panel.feature.type != "revolve":
            return
        edges = [s for s in shapes if s.ShapeType() == TopAbs_EDGE]
        faces = [s for s in shapes if s.ShapeType() == TopAbs_FACE]
        if report is None or report.body is None or len(edges) + len(faces) != 1:
            return
        if faces:
            # A round face gives its axis, the temporary axis (spec 2 section 20 item 4).
            ref = _round_face_reference(report.body, faces[0])
        else:
            ref = straight_edge_reference(report.body, edges[0])
        problem = strings.AXIS_EDGE_NOT_STRAIGHT if ref is None else panel.set_axis_edge(ref)
        if problem:
            self.status.setText(problem)

    def _pick_for_start(self, tab: DocumentTab, shapes: list[Any]) -> None:
        """While an extrude's From takes a pick, a clicked face or vertex becomes it (T5.1.2)."""
        from fdcad.core.naming.select import reference_for

        panel, report = self.panel, tab.session.report
        start = getattr(panel, "start", None) if panel is not None else None
        if panel is None or start is None or start.current not in ("surface", "vertex"):
            return
        if len(shapes) != 1 or report is None or report.body is None:
            return
        ref = reference_for(report.body, shapes[0])
        problem = panel.set_start_pick(ref) if ref is not None else strings.START_PICK_FACE
        if problem:
            self.status.setText(problem)

    def show_stats(self) -> None:
        """Open the rebuild statistics panel for the active part."""
        from fdcad.ui.main_window.stats import RebuildStats

        if getattr(self, "stats", None) is None:
            self.stats = RebuildStats(self)
        self.stats.set_session(self.current.session if self.current else None)
        self.stats.show()
        self.stats.raise_()

    def show_shortcut_bar(self) -> None:
        """Show the shortcut bar for the current context at the cursor."""
        from PySide6.QtGui import QCursor

        context = "sketch" if self.sketch_mode is not None and self.sketch_mode.is_open else "part"
        self.commands.shortcut_bar(context, QCursor.pos())

    def toggle_left_panel(self) -> None:
        """Show or hide the left panel."""
        dock = self.findChild(QDockWidget, "left_panel")
        if dock is not None:
            dock.setVisible(not dock.isVisible())

    def toggle_command_tabs(self) -> None:
        """Show or hide the command tabs."""
        holder = getattr(self, "command_holder", None)
        if holder is not None:
            holder.setVisible(not holder.isVisible())

    def toggle_fullscreen(self) -> None:
        """Switch full screen on or off."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def step_part(self, step: int) -> bool:
        """Bring the next (``step`` 1) or previous (-1) open part tab forward, wrapping
        round (TR22). False with fewer than two parts open."""
        count = self.tabs.count()
        if count < 2:
            return False
        self.tabs.setCurrentIndex((self.tabs.currentIndex() + step) % count)
        return True

    def _step_command_tab(self, step: int) -> None:
        tabs = getattr(self, "command_tabs", None)
        if tabs is not None and tabs.count():
            tabs.setCurrentIndex((tabs.currentIndex() + step) % tabs.count())

    def _tree_find(self) -> None:
        if self.tree is not None:
            self._left_tab(0)
            self.tree.find_feature()

    def _full_sketches_changed(self) -> None:
        """Use Only Fully Defined Sketches changed: rebuild the parts it changes (TR36).
        Simplify Threads While Editing too (TR347, D1921)."""
        wanted = self.settings.full_sketches_only
        threads = self.settings.simplify_threads
        for i in range(self.tabs.count()):
            session = getattr(self.tabs.widget(i), "session", None)
            engine = getattr(session, "engine", None)
            if engine is None:
                continue
            if engine.full_sketches_only != wanted or engine.simplify_threads != threads:
                engine.full_sketches_only = wanted
                engine.simplify_threads = threads
                session.request_rebuild()  # type: ignore[union-attr]

    def preferences(self) -> None:
        """Edit preferences and apply them."""
        from fdcad.ui.preferences.dialog import PreferencesDialog

        theme = self.settings.theme
        dialog = PreferencesDialog(self.settings, self)
        accepted = dialog.exec()
        # Each closed dialog stayed alive; every later restyle then got slower (D637).
        dialog.deleteLater()
        if accepted:
            app = QApplication.instance()
            from fdcad.ui.themes import theme as theme_module

            safe_changed = theme_module._colour_safe != self.settings.colour_safe
            theme_module.set_colour_safe(self.settings.colour_safe)  # TR292
            # Restyling repolishes every widget: only when the theme changed (D638).
            if isinstance(app, QApplication) and (self.settings.theme != theme or safe_changed):
                apply_theme(app, self.settings.theme)
            motion.set_reduce_motion(self.settings.reduce_motion)
            from fdcad.ui.accessibility import apply_large_controls

            apply_large_controls(self, self.settings.large_controls)  # TR294 (D2017)
            from fdcad.ui.input import pick_size

            pick_size.set_size(self.settings.pick_size)  # TR313
            self.settings.apply_number_style()  # TR350
            from fdcad.ui.main_window.window_details import set_dark_title_bar
            from fdcad.ui.themes.theme import is_dark

            set_dark_title_bar(self, is_dark())  # Windows title bar follows the theme (U9.5)
            self.dev_overlays.refresh()
            self.empty_tree_hint.restyle()
            self.autosave_timer.start(self.settings.autosave_minutes * 60_000)
            self.commands.reload()
            tabs = getattr(self, "command_tabs", None)
            if tabs is not None:
                tabs.theme_changed()  # new icon colours everywhere, shortcuts in tooltips
            trackpad = self.settings.navigation.value == "trackpad"
            for i in range(self.tabs.count()):
                tab_view = getattr(self.tabs.widget(i), "viewport", None)
                if tab_view is not None and hasattr(tab_view, "gesture_with_ctrl"):
                    tab_view.gesture_with_ctrl = trackpad
                    tab_view.turn_ms = self.view_turn_ms()
                    tab_view.lock_up = self.settings.lock_up
                    tab_view.arcball = self.settings.turn_style == "arcball"
                if tab_view is not None and hasattr(tab_view, "apply_pick_size"):
                    tab_view.apply_pick_size()  # TR313
            from fdcad.ui.main_window import view_prefs

            view_prefs.apply_all(self)  # round 12 view options
            for i in range(self.tabs.count()):
                tab = self.tabs.widget(i)
                set_palette = getattr(getattr(tab, "viewport", None), "set_palette", None)
                if set_palette is not None:
                    set_palette(palette())
            self._sketch_options_changed()
            self._full_sketches_changed()
            self._printer_changed()  # TR180
            if self.tree is not None:
                self.tree.refresh()

    def about(self) -> None:
        """Show the version, the license and the third party licenses."""
        self.help.show_about()

    def open_document(self, document: Document) -> DocumentTab:
        """Open an in memory document (tests and samples)."""
        from fdcad.ui.session import DocumentSession

        return self.add_session(DocumentSession(document, None, self))


def _write_step_files(
    shape: Any,
    target: Path,
    options: Any,
    bodies: list[tuple[int, str]],
    color: str | None,
    faces: Any,
    notes: Any,
) -> str:
    """Write STEP with the options of TR302 (D1202): the bodies listed (hidden ones are
    left out by the caller), named, Y up and in the unit asked, in one file or one file
    per body. Returns the status text."""
    from fdcad.core.features.solids import solids
    from fdcad.core.io import export
    from fdcad.core.io.step_options import body_paths

    parts = solids(shape) or [shape]
    chosen = [(i, name) for i, name in bodies if 0 <= i < len(parts)]
    if not chosen:
        raise export.ExportError(
            "Every body is hidden. Use Show Body on one, or tick Include hidden bodies."
        )

    def write(part: Any, path: Path, names: list[str]) -> None:
        export.export_step(
            part,
            path,
            color=color,
            faces=faces,
            notes=notes,
            unit=options.unit,
            y_up=options.y_up,
            names=names if options.names else None,
        )

    if options.per_body:
        paths = body_paths(target, [name for _i, name in chosen])
        for (i, name), path in zip(chosen, paths, strict=True):
            write(parts[i], path, [name])
        return strings.STEP_EXPORTED_FILES.format(
            count=len(paths), names=", ".join(p.name for p in paths)
        )
    part = _only(shape, [i for i, _n in chosen])
    write(part, target, [name for _i, name in chosen])
    return strings.EXPORT_DONE.format(name=target.name)


def _only(shape: Any, keep: list[int] | None) -> Any:
    """The bodies of ``shape`` at ``keep`` (all of them for None), for mesh export (TR182)."""
    if keep is None:
        return shape
    from fdcad.core.features.solids import compound, solids

    parts = solids(shape)
    chosen = [parts[i] for i in keep if 0 <= i < len(parts)]
    if not chosen or len(chosen) == len(parts):
        return shape
    return chosen[0] if len(chosen) == 1 else compound(chosen)


def _same_file(a: Path, b: Path) -> bool:
    """True when ``a`` and ``b`` name one file."""
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return False


def _unused_blank(session: Any) -> bool:
    """True for the empty part made at start while it is untouched (D1033)."""
    unused = session.undo.count() == 0 and not session.is_dirty
    return bool(getattr(session, "auto_blank", False) and unused and session.path is None)


def change_text(report: RebuildReport, tab: DocumentTab) -> str:
    """The result line for the changed feature, in the part's units (TR290), or ""."""
    from fdcad.core.units import UnitSystem

    change = report.change
    if change is None:
        return ""
    if getattr(change, "failed", False):  # D1041: not "built; the solid did not change"
        return strings.CHANGE_ERROR.format(name=change.name)
    inch = tab.session.document.units is UnitSystem.IN
    scale, unit = (1 / 16387.064, "in3") if inch else (1 / 1000.0, "cm3")
    parts = []
    if change.added > 1e-6:
        parts.append(strings.CHANGE_ADDED.format(v=change.added * scale, unit=unit))
    if change.removed > 1e-6:
        parts.append(strings.CHANGE_REMOVED.format(v=change.removed * scale, unit=unit))
    if change.faces:
        key = "CHANGE_FACES_MORE" if change.faces > 0 else "CHANGE_FACES_LESS"
        parts.append(getattr(strings, key).format(n=abs(change.faces)))
    if not parts:
        return strings.CHANGE_NONE.format(name=change.name)
    return strings.CHANGE_LINE.format(name=change.name, what=strings.CHANGE_AND.join(parts))


def announce(label: object) -> None:
    """Tell a screen reader the status line changed (TR290)."""
    from PySide6.QtGui import QAccessible, QAccessibleEvent
    from PySide6.QtWidgets import QWidget

    if isinstance(label, QWidget) and QAccessible.isActive():
        QAccessible.updateAccessibility(QAccessibleEvent(label, QAccessible.Event.NameChanged))
