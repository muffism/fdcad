"""Sketch mode: open a sketch in the 2D editor, then write it back with OK.

While a sketch is open the document tab shows the sketch canvas instead of
the 3D view, the Properties tab shows the sketch panel, and the window's
undo and redo act inside the sketch. OK writes the sketch to the document as
one undoable command; Cancel drops the changes.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from functools import partial
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QDialog, QMessageBox

from fdcad.core.document.model import Document, Feature
from fdcad.core.features.names import default_name
from fdcad.core.kernel import kernel_job
from fdcad.core.sketch.links import LinkUpdate
from fdcad.core.sketch.profiles import BASIS_PLANES, SketchPlane
from fdcad.ui import strings
from fdcad.ui.background import start_job
from fdcad.ui.sketch_tools.edit import SketchEdit, new_sketch_data
from fdcad.ui.sketch_tools.registry import EXTRA_TOOL_NAMES
from fdcad.ui.themes import motion
from fdcad.ui.viewport.views import TURN_MS

if TYPE_CHECKING:
    from OCP.TopoDS import TopoDS_Shape

    from fdcad.core.naming.names import NamedShape
    from fdcad.core.sketch.curve_convert import ProjectedCurve
    from fdcad.core.sketch.links import ModelGeometry
    from fdcad.core.sketch.reference import Polyline, RefCircle
    from fdcad.ui.command_tabs.ribbon import RibbonPanel
    from fdcad.ui.main_window.window import DocumentTab, MainWindow
    from fdcad.ui.sketch_tools.canvas import SketchCanvas
    from fdcad.ui.sketch_tools.link_bar import LinkBar
    from fdcad.ui.sketch_tools.panel import SketchPanel
    from fdcad.ui.sketch_tools.relations_panel import RelationsPanel

TOOL_ORDER = [
    "line",
    "centerline",
    "corner_rectangle",
    "center_rectangle",
    "circle",
    "center_arc",
    "tangent_arc",
    "three_point_arc",
    "point",
    "dimension",
    *EXTRA_TOOL_NAMES,
]
# The layout of these tools in the Sketch command tab, with the dropdown
# groups, is in ``fdcad.ui.command_tabs.tabs``.


#: How many sketch tools the Recent Sketch Tools list keeps (TR204, D918).
RECENT_SKETCH_TOOLS = 8


class _OutlineSignals(QObject):
    done = Signal(object)


class _OutlineJob(QRunnable):
    """Cuts the part with the sketch plane off the UI thread (CLAUDE.md rule 2)."""

    def __init__(self, shape: TopoDS_Shape, plane: SketchPlane) -> None:
        super().__init__()
        self.shape, self.plane = shape, plane
        self.signals = _OutlineSignals()

    @kernel_job
    def run(self) -> None:
        from fdcad.core.sketch.reference import plane_section

        try:
            section = plane_section(self.shape, self.plane)
        except Exception:  # reference only, never break sketching
            section = ([], [])
        self.signals.done.emit(section)


#: Projected part geometry of recently opened sketches, keyed by the part's rebuild
#: key and the plane, so reopening a sketch does not project again (D250).
_MODEL_CACHE: dict[tuple[str, SketchPlane], ModelGeometry] = {}
_MODEL_CACHE_SIZE = 4


class _ModelJob(QRunnable):
    """Projects part edges, vertices and the origin off the UI thread (WP14, rule 2)."""

    def __init__(
        self,
        body: NamedShape | None,
        plane: SketchPlane,
        key: str,
        axes: bool = False,
        cut_away: bool = False,
    ) -> None:
        super().__init__()
        self.body, self.plane, self.key = body, plane, key
        #: Leave out the part in front of the sketch plane (TR113).
        self.cut_away = cut_away
        #: Add the temporary axes as snap lines (TR17).
        self.axes = axes
        self.signals = _OutlineSignals()

    @kernel_job
    def run(self) -> None:
        from fdcad.core.sketch.projection import project_model

        try:
            body = self.body
            if self.cut_away and body is not None:
                from fdcad.core.naming.names import NamedShape
                from fdcad.core.sketch.reference import behind

                kept = behind(body.shape, self.plane)
                body = NamedShape(kept, list(body.faces))  # names of faces kept whole
            geometry = project_model(body, self.plane)
            if self.axes and self.body is not None:
                from fdcad.core.temporary_axes import temporary_axes, with_axes

                geometry = with_axes(geometry, temporary_axes(self.body.shape), self.plane)  # type: ignore[assignment]
        except Exception:  # snap targets only, never break sketching
            geometry = None
        self.signals.done.emit((self.key, self.plane, geometry))


class _CurveJob(QRunnable):
    """Projects curve features onto the sketch plane for Convert (D517, rule 2)."""

    def __init__(self, sources: list[tuple[str, str, TopoDS_Shape]], plane: SketchPlane) -> None:
        super().__init__()
        self.sources, self.plane = sources, plane
        self.signals = _OutlineSignals()

    @kernel_job
    def run(self) -> None:
        from fdcad.core.sketch.curve_projection import project_curves

        self.signals.done.emit(project_curves(self.sources, self.plane))


class _ModelCurvesJob(QRunnable):
    """Part curves of the kinds in ``kinds``: the part turned about the sketch's X axis
    (TR319), the cut with the sketch plane (TR6) or its outline seen square to the plane.
    The cut and the outline are only worked out when a tool asks (D2609, D2683)."""

    def __init__(
        self,
        shape: TopoDS_Shape,
        plane: SketchPlane,
        cut_away: bool = False,
        kinds: tuple[str, ...] = (),
        tag: int = 0,
    ) -> None:
        super().__init__()
        self.shape, self.plane = shape, plane
        self.cut_away = cut_away  # TR113
        #: On a threaded part the kernel's hidden line removal took 28 s (D2609) and its
        #: cut along the thread 8.3 s (D2683), so only what a tool needs is worked out.
        self.kinds = kinds
        self.tag = tag  # which opening of the sketch the curves are for
        self.signals = _OutlineSignals()

    @kernel_job
    def run(self) -> None:
        if self.cut_away:
            from fdcad.core.sketch.reference import behind

            self.shape = behind(self.shape, self.plane)
        from fdcad.core.sketch.model_curves import (
            INTERSECTION,
            SILHOUETTE,
            intersection_curves,
            silhouette,
        )
        from fdcad.core.sketch.turned import TURNED, turned_outline

        makers = {
            SILHOUETTE: silhouette,
            INTERSECTION: intersection_curves,
            TURNED: turned_outline,  # TR319
        }
        curves = {kind: makers[kind](self.shape, self.plane) for kind in self.kinds}
        self.signals.done.emit((self.tag, curves))


def curve_sources(tab: DocumentTab, feature: Feature) -> list[tuple[str, str, TopoDS_Shape]]:
    """Curve features above ``feature`` in the tree (all of them for a new sketch) with
    their curve shapes from the last rebuild (D517)."""
    report = tab.session.report
    if report is None:
        return []
    out = []
    for f in tab.session.document.features:
        if f.id == feature.id:
            break
        result = report.results.get(f.id)
        curve = result.extras.get("curve") if result is not None else None
        if curve is None and f.type == "sketch":
            # A sketch that shows its construction geometry in the part (TR339, D1703).
            curve = report.construction_edges.get(f.id)
        if curve is not None and not f.suppressed:
            out.append((f.id, f.name, curve))
    return out


def plane_of_feature(tab: DocumentTab, feature: Feature) -> SketchPlane | None:
    """Placement of a sketch's plane from the last rebuild, or from a default plane."""
    report = tab.session.report
    if report is not None:
        result = report.results.get(feature.id)
        if result is not None and result.sketch is not None:
            return result.sketch.plane
    ref = feature.refs.get("plane")
    if isinstance(ref, dict) and "feature" in ref:
        if report is not None:
            plane_result = report.results.get(str(ref["feature"]))
            if plane_result is not None and plane_result.plane is not None:
                return plane_result.plane
        try:
            plane_feature = tab.session.document.feature(str(ref["feature"]))
        except KeyError:
            return None
        basis = plane_feature.params.get("basis")
        if isinstance(basis, str):
            return BASIS_PLANES.get(basis)
    return None


class SketchMode:
    """Owns the Sketch command tab and the open sketch of the active document."""

    def __init__(self, window: MainWindow) -> None:
        self.window = window
        self.tab: DocumentTab | None = None
        self.canvas: SketchCanvas | None = None
        self.panel: SketchPanel | None = None
        self.relations_panel: RelationsPanel | None = None
        self.is_new = False
        self.tool_actions: dict[str, QAction] = {}
        self._jobs: list[QRunnable] = []  # outline and model jobs kept alive while they run
        #: The part, plane and cut away state the part curves are for, and a count that
        #: changes with them, so curves for an older state are dropped (D2609).
        self._curve_args: tuple[TopoDS_Shape, SketchPlane, bool] | None = None
        self._curve_tag = 0
        self._asked: set[str] = set()  # kinds a tool asked for (D2609, D2683)
        self.after_accept: Callable[[str], None] | None = None
        #: Warning bar for part copies that no longer match the part (D250).
        self.link_bar: LinkBar | None = None
        #: The 3D view's navigation count when the last sketch closed (W2.4).
        self.exit_nav = 0
        #: The 3D camera before the open sketch turned the view (T1.5.2).
        self.view_before: object | None = None
        #: The last sketch tool used, for the right click menu (T9.2).
        self.last_tool = ""
        #: Sketch tools used lately, newest first, kept apart from part commands (TR204).
        self.recent_tools: list[str] = []
        from fdcad.ui.main_window.plane_pick import PlanePicker

        self.picker = PlanePicker(window)
        from fdcad.ui.main_window.sketch_plane import EditSketchPlane

        #: Edit Sketch Plane (T14.2), from the tree menu or its command.
        self.plane_editor = EditSketchPlane(window)
        if window.tree is not None:
            window.tree.edit_plane_requested.connect(self.plane_editor.start)
            window.tree.itemClicked.connect(self._tree_clicked)
        self.toolbar = self._build_toolbar()
        #: The sketch problem list, while open (TR38, D1301).
        self.problems_dialog: QDialog | None = None
        window.sketch_status.clicked.connect(self.show_problems)

    def show_problems(self) -> None:
        """Open the sketch problem list (TR38) for the open sketch."""
        from PySide6.QtCore import Qt

        from fdcad.ui.sketch_tools.problem_list import ProblemListDialog

        if self.canvas is None:
            return
        if self.problems_dialog is not None:
            self.problems_dialog.close()
        dialog = ProblemListDialog(self.canvas, self.window)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.destroyed.connect(lambda *_a: setattr(self, "problems_dialog", None))
        self.problems_dialog = dialog
        dialog.show()

    # Commands ------------------------------------------------------------------------

    def _build_toolbar(self) -> RibbonPanel:
        """Make the sketch commands, then lay them out as the Sketch command tab."""
        from fdcad.ui.command_tabs.tabs import build_sketch_panel

        a = self.window.commands
        self.sketch_action = a.add("sketch.sketch", lambda: self.start(), repeatable=True)
        self.exit_action = a.add("sketch.exit", lambda: self.accept())
        self.discard_action = a.add("sketch.discard", lambda: self.cancel())  # TR120
        self.select_action = a.add("sketch.select", self.select_tool)
        self.relations_action = a.add(
            "view.sketch_relations", self._toggle_relations, checkable=True
        )
        self.relations_action.setChecked(True)
        #: Dynamic mirror and curvature combs (P2.8 items 4 and 10, D514).
        self.mirror_action = a.add("sketch.dynamic_mirror", self._dynamic_mirror, checkable=True)
        self.combs_action = a.add("view.curvature_combs", self._toggle_combs, checkable=True)
        group = QActionGroup(self.window)
        group.setExclusionPolicy(QActionGroup.ExclusionPolicy.ExclusiveOptional)
        for name in TOOL_ORDER:
            action = a.add(
                f"sketch.{name}",
                partial(self._tool_from_command, name),
                checkable=True,
                repeatable=True,
            )
            group.addAction(action)
            self.tool_actions[name] = action
        a.add("sketch.construction", self._construction)
        a.add("sketch.snap_options", lambda: self.window.show_snap_options())
        a.add("sketch.line_arc", self._line_arc)
        a.add("sketch.edit_plane", self.edit_plane)
        a.add("sketch.text", self.edit_texts)  # PHASE4_SPEC P4.8
        a.add("sketch.insert_dxf", self.insert_dxf)  # TR5
        a.add("sketch.insert_svg", self.insert_svg)  # TR117
        self.cut_away_action = a.add("sketch.cut_away", self.toggle_cut_away, checkable=True)
        self.hide_construction_action = a.add(  # TR419
            "sketch.hide_construction", self.toggle_hide_construction, checkable=True
        )
        self.show_construction_action = a.add(  # TR339
            "sketch.show_construction", self.toggle_show_construction, checkable=True
        )
        self.relations_panel_action = a.add("sketch.relations", self.show_relations_panel)
        self._update_actions()
        return build_sketch_panel(a.actions)

    # Cut away the part in front of the sketch plane (TR113, D844) -------------------

    @staticmethod
    def cut_away_on(feature: Feature) -> bool:
        """True when the sketch hides the part in front of its plane."""
        return feature.data.get("cut_away") is True

    def toggle_hide_construction(self) -> bool:
        """Hide or show the open sketch's construction curves (TR419, D932). Display
        only: nothing in the sketch changes. Returns the new state."""
        canvas = self.canvas
        if canvas is None:
            self.hide_construction_action.setChecked(False)
            return False
        on = not canvas.hide_construction
        canvas.set_hide_construction(on)
        self.hide_construction_action.setChecked(on)
        return on

    def toggle_show_construction(self) -> bool:
        """Show or hide the open sketch's construction geometry in the part once it is
        closed (TR339, D1703); kept in the sketch. Returns the new state."""
        from fdcad.core.sketch.construction_refs import (
            set_shows_construction,
            shows_construction,
        )

        canvas = self.canvas
        if canvas is None:
            self.show_construction_action.setChecked(False)
            return False
        feature = canvas.edit.feature
        on = not shows_construction(feature.data)
        set_shows_construction(feature.data, on)
        self.show_construction_action.setChecked(on)
        return on

    def toggle_cut_away(self) -> bool:
        """Hide or show the part in front of the sketch plane; kept in the sketch (display
        only). Returns the new state."""
        canvas, tab = self.canvas, self.tab
        if canvas is None or tab is None:
            return False
        feature = canvas.edit.feature
        on = not self.cut_away_on(feature)
        if on:
            feature.data["cut_away"] = True
        else:
            feature.data.pop("cut_away", None)
        self.cut_away_action.setChecked(on)
        plane = plane_of_feature(tab, feature)
        report = tab.session.report
        if plane is not None:
            self._start_model(tab, feature, plane, canvas)
            if report is not None and report.body is not None:
                self._start_curves(report.body.shape, plane, on)
        self.window.status.setText(strings.CUT_AWAY_ON if on else strings.CUT_AWAY_OFF)
        return on

    def insert_dxf(self) -> None:
        """Insert DXF into the open sketch (TR5)."""
        if self.canvas is None:
            self.window.status.setText(text_open_sketch())
            return
        from fdcad.ui.sketch_tools.dxf_dialog import insert_dxf

        insert_dxf(self.canvas)

    def insert_svg(self) -> None:
        """Insert SVG into the open sketch (TR117, D863)."""
        if self.canvas is None:
            self.window.status.setText(text_open_sketch())
            return
        from fdcad.ui.sketch_tools.dxf_dialog import insert_svg

        insert_svg(self.canvas)

    def edit_texts(self) -> None:
        """Open the Text dialog on the open sketch (PHASE4_SPEC P4.8)."""
        if self.canvas is None:
            self.window.status.setText(text_open_sketch())
            return
        from fdcad.ui.sketch_tools.text_dialog import edit_texts

        edit_texts(self.canvas, self.window)

    def _tool_from_command(self, name: str) -> None:
        action = self.tool_actions[name]
        self._tool_triggered(name, action.isChecked() or self.canvas is None)

    def _tool_triggered(self, name: str, checked: bool = True) -> None:
        if self.canvas is None:
            self.start(then_tool=name)
            return
        self.canvas.set_tool(name if checked else None)

    def select_tool(self) -> None:
        """End the active tool and go back to selecting (W3.1)."""
        if self.canvas is not None:
            self.canvas.set_tool(None)

    def _toggle_relations(self) -> None:
        """Show or hide the relation tags (W3.3)."""
        if self.canvas is not None:
            self.canvas.show_relations = self.relations_action.isChecked()
            self.canvas.update()

    def _dynamic_mirror(self) -> None:
        """Turn dynamic mirror on (about the selected line, or the next clicked one) or off."""
        from fdcad.ui.sketch_tools import tool_text

        if self.canvas is None:
            self.mirror_action.setChecked(False)
            self.window.status.setText(tool_text.MIRROR_NO_SKETCH)
            return
        if self.mirror_action.isChecked():
            self.canvas.start_dynamic_mirror()
        else:
            self.canvas.set_dynamic_mirror(None)

    def _mirror_changed(self, on: bool) -> None:
        self.mirror_action.setChecked(on)
        self._edited()

    def _toggle_combs(self) -> None:
        """Show or hide curvature combs on splines (view state, kept for the session)."""
        if self.canvas is not None:
            self.canvas.set_show_curvature(self.combs_action.isChecked())

    def _panel_ok(self) -> None:
        """OK in the sketch panel ends the active tool first, then exits the sketch."""
        canvas = self.canvas
        if canvas is not None and (canvas.tool is not None or canvas.dimension_mode):
            canvas.set_tool(None)
            return
        self.accept()

    def show_relations_panel(self) -> None:
        """Show the Relations panel in the left panel (T3.3); Back returns to the sketch panel."""
        from fdcad.ui.sketch_tools.relations_panel import RelationsPanel

        if self.canvas is None:
            return
        if self.relations_panel is None:
            self.relations_panel = RelationsPanel(self.canvas)
            self.relations_panel.closed.connect(self.hide_relations_panel)
        self.window.show_side_panel(self.relations_panel)

    def hide_relations_panel(self) -> None:
        """Go back from the Relations panel to the sketch panel."""
        props = self.window.properties
        if props is not None and self.panel is not None:
            props.setCurrentWidget(self.panel)

    def _construction(self) -> None:
        if self.panel is not None:
            self.panel._toggle_construction()

    def _tool_changed(self, name: str) -> None:
        if name:
            self.last_tool = name  # offered again in the right click menu (T9.2)
            recent = [name, *[t for t in self.recent_tools if t != name]]
            self.recent_tools = recent[:RECENT_SKETCH_TOOLS]
        for tool, action in self.tool_actions.items():
            action.setChecked(tool == name)

    def _update_actions(self) -> None:
        open_ = self.canvas is not None
        self.exit_action.setEnabled(open_)
        self.relations_panel_action.setEnabled(open_)
        shown = getattr(self, "show_construction_action", None)
        if shown is not None:  # TR339: the tick follows the open sketch
            from fdcad.core.sketch.construction_refs import shows_construction

            shown.setEnabled(open_)
            shown.setChecked(
                open_
                and self.canvas is not None
                and shows_construction(self.canvas.edit.feature.data)
            )
        cut = getattr(self, "cut_away_action", None)
        if cut is not None:  # TR113: the tick follows the open sketch
            cut.setEnabled(open_)
            cut.setChecked(
                open_ and self.canvas is not None and self.cut_away_on(self.canvas.edit.feature)
            )
        if not open_:
            for action in self.tool_actions.values():
                action.setChecked(False)

    @property
    def is_open(self) -> bool:
        """True while a sketch is being edited."""
        return self.canvas is not None

    # Opening -------------------------------------------------------------------------

    def start(
        self,
        then_tool: str | None = None,
        plane_id: str | None = None,
        after_accept: Callable[[str], None] | None = None,
    ) -> None:
        """Start a new sketch on the selected plane or face, or ask for one (W1).

        ``after_accept`` runs with the new sketch's id when the user exits the
        sketch and keeps it (feature first workflow, W2).
        """
        from fdcad.ui.main_window.plane_pick import flat_face

        w = self.window
        tab = w.current
        if tab is None:
            return
        if self.is_open:
            if then_tool is not None and self.canvas is not None:
                self.canvas.set_tool(then_tool)
            return
        face = flat_face(tab) if plane_id is None else None
        if face is not None:
            self._open_new(tab, face[0], face[1], then_tool, after_accept)
            return
        doc = tab.session.document
        if plane_id is None and w.tree is not None:
            selected = w.tree.selected_id()
            if any(f.id == selected and f.type in ("plane", "ref_plane") for f in doc.features):
                plane_id = selected
        if plane_id is None:
            self.picker.start(
                tab,
                lambda ref, placement: self._open_new(tab, ref, placement, then_tool, after_accept),
            )
            if then_tool is not None:  # TR123 (D974): say what the pick is for
                label = strings.SKETCH_TOOLS.get(then_tool, then_tool)
                w.status.setText(strings.SELECT_PLANE_FOR_TOOL.format(tool=label))
            return
        self._open_new(tab, {"feature": plane_id}, None, then_tool, after_accept)

    def _open_new(
        self,
        tab: DocumentTab,
        ref: dict[str, object],
        placement: SketchPlane | None,
        then_tool: str | None,
        after_accept: Callable[[str], None] | None,
    ) -> None:
        doc = tab.session.document
        name = default_name(doc, "sketch")
        feature = Feature(
            doc.new_feature_id(),
            "sketch",
            name,
            refs={"plane": ref},
            data=new_sketch_data(),
        )
        self.open(tab, feature, is_new=True, plane=placement)
        self.after_accept = after_accept
        if then_tool is not None and self.canvas is not None:
            self.canvas.set_tool(then_tool)

    def _line_arc(self) -> None:
        """Line to arc switch (T2.1.3, T12.5): the next Line segment becomes a tangent arc."""
        if self.canvas is not None and self.canvas.tool_name == "line":
            self.canvas.toggle_line_arc()

    def edit_plane(self) -> None:
        """Edit Sketch Plane for the open sketch, or the sketch selected in the tree."""
        w = self.window
        sid: str | None = None
        if self.canvas is not None and not self.is_new:
            sid = self.canvas.edit.feature.id
        elif w.tree is not None and w.current is not None:
            fid = w.tree.selected_id()
            doc = w.current.session.document
            if fid is not None and doc.feature(fid).type == "sketch":
                sid = fid
        if sid is None:
            w.status.setText(strings.SKETCH_PLANE_NONE)
            return
        self.plane_editor.start(sid)

    def edit(self, fid: str) -> None:
        """Open an existing sketch."""
        tab = self.window.current
        if tab is None:
            return
        if self.is_open and not self.accept():
            return  # the open sketch keeps a wrong typed value; its box says why
        if tab.session.document.feature(fid).refs.get("derived_from"):
            # A linked copy cannot change shape (TR49, D845).
            self.window.status.setText(strings.DERIVED_NO_EDIT)
            return
        self.open(tab, tab.session.document.feature(fid), is_new=False)

    def open(
        self,
        tab: DocumentTab,
        feature: Feature,
        is_new: bool,
        plane: SketchPlane | None = None,
    ) -> None:
        """Show ``feature`` in the sketch editor."""
        from fdcad.core.rebuild.engine import document_variables
        from fdcad.ui.commands.pictures import picture_blocks
        from fdcad.ui.sketch_tools.canvas import SketchCanvas
        from fdcad.ui.sketch_tools.panel import SketchPanel
        from fdcad.ui.themes.theme import palette

        w = self.window
        if w.panel is not None and w.panel.is_editing:
            w.panel.cancel()
        edit = SketchEdit(feature)
        doc = tab.session.document
        edit.blocks = picture_blocks(doc, edit)
        canvas = SketchCanvas(edit, doc.units, document_variables(doc), palette())
        options = w.settings.sketch_options
        canvas.set_options(options)
        # Discarding the sketch puts the 3D view back where it was (T1.5.2).
        pose = getattr(tab.viewport, "camera_pose", None)
        self.view_before = pose() if pose is not None else None
        self.tab, self.canvas, self.is_new = tab, canvas, is_new
        panel = SketchPanel(canvas)
        panel.accepted.connect(self._panel_ok)
        canvas.show_relations = self.relations_action.isChecked()
        canvas.set_show_curvature(self.combs_action.isChecked())
        canvas.curvature_toggled.connect(self.combs_action.setChecked)
        canvas.mirror_changed.connect(self._mirror_changed)
        panel.rejected.connect(self.cancel)
        self.panel = panel
        w.show_side_panel(panel)
        canvas.status_message.connect(w.status.setText)
        canvas.cursor_moved.connect(self._cursor)
        canvas.edited.connect(self._edited)
        # TR120 (D941): leave after the event that asked, since leaving deletes the canvas.
        canvas.exit_requested.connect(lambda: QTimer.singleShot(0, self.accept))
        canvas.tool_changed.connect(self._tool_changed)
        canvas.curves_wanted.connect(self._curves_wanted)  # D2609
        self._asked = set()
        canvas.gesture.connect(lambda dx, dy: w.commands.gesture("sketch", dx, dy))
        canvas.menu_handler = lambda pos: w.context_menus.sketch_menu(canvas, pos)
        canvas.selection_changed.connect(lambda: w.context_bar.for_sketch(canvas))
        canvas.tool_changed.connect(w._filter_sketch)  # keep the filter cursor (T14.3.2)
        w._filter_sketch()
        canvas.gesture_tracker.source = lambda: w.commands.gesture_labels("sketch")
        w.command_tabs.setCurrentWidget(self.toolbar)
        w.undo_group.setActiveStack(None)  # type: ignore[arg-type]  # Qt allows no stack
        plane = plane or plane_of_feature(tab, feature)
        # The 3D view turns to face the sketch (animated, W1.3), then the sketch
        # editor takes its place (D72).
        turn = getattr(tab.viewport, "animate_normal_to", None)
        if plane is not None and turn is not None and options.normal_to_on_open:
            duration = motion.duration(TURN_MS) if w.settings.animations else 0
            turn(plane.normal, duration, lambda: self._reveal(tab, canvas))
        else:
            self._reveal(tab, canvas)
        report = tab.session.report
        if plane is not None and report is not None and report.body is not None:
            job = _OutlineJob(report.body.shape, plane)
            job.signals.done.connect(self._outline_ready)
            self._jobs.append(job)
            start_job(QThreadPool.globalInstance(), job)
            self._start_curves(report.body.shape, plane, self.cut_away_on(feature))  # TR6
        if plane is not None:
            self._start_model(tab, feature, plane, canvas)
            sources = curve_sources(tab, feature)
            if sources:
                curves = _CurveJob(sources, plane)
                curves.signals.done.connect(self._curves_ready)
                self._jobs.append(curves)
                start_job(QThreadPool.globalInstance(), curves)
        self._edited()
        self._update_actions()
        w.update_corner()

    def _reveal(self, tab: DocumentTab, canvas: SketchCanvas) -> None:
        """Show the sketch editor in place of the 3D view, unless it closed meanwhile."""
        if self.canvas is canvas and self.tab is tab:
            grid = tab.session.document.extra.get("sketch_grid")  # TR102
            if isinstance(grid, dict) and float(grid.get("major", 0) or 0) > 0:
                canvas.grid_spacing = float(grid["major"])
                canvas.grid_minor = int(grid.get("minor", 1) or 1)
            tab.show_sketch(canvas)
            canvas.setFocus()

    def _start_model(
        self, tab: DocumentTab, feature: Feature, plane: SketchPlane, canvas: SketchCanvas
    ) -> None:
        """Project the part for model snaps once per opened sketch (T1.2.2, D250).

        The part is the one the sketch sees: before the sketch for an existing
        sketch, the finished part for a new one. Stale copies come from the rebuild.
        """
        from fdcad.core.sketch.links import updates_from_data
        from fdcad.ui.sketch_tools.link_bar import LinkBar

        report = tab.session.report
        result = report.results.get(feature.id) if report is not None else None
        body = result.body if result is not None else (report.body if report else None)
        bar = LinkBar(canvas)
        bar.update_requested.connect(self._update_links)
        self.link_bar = bar
        updates: list[LinkUpdate] = []
        for issue in result.issues if result is not None else []:
            if issue.code == "stale_links" and issue.fixes:
                updates += updates_from_data(issue.fixes[0].data.get("updates"))
            elif issue.code == "lost_links":
                updates += [LinkUpdate(eid, None) for eid in issue.highlight]
        bar.set_updates(updates)
        axes_action = self.window.commands.actions.get("view.temporary_axes")
        axes = axes_action is not None and axes_action.isChecked()
        cut = self.cut_away_on(feature)
        key = f"{result.key if result is not None else ''}:{id(body)}:{axes}:{cut}"
        cached = _MODEL_CACHE.get((key, plane))
        if cached is not None:
            canvas.set_model(cached)
            return
        job = _ModelJob(body, plane, key, axes, cut)
        job.signals.done.connect(self._model_ready)
        self._jobs.append(job)
        start_job(QThreadPool.globalInstance(), job)

    def _model_ready(self, done: tuple[str, SketchPlane, ModelGeometry | None]) -> None:
        key, plane, geometry = done
        if geometry is None:
            return
        _MODEL_CACHE[(key, plane)] = geometry
        while len(_MODEL_CACHE) > _MODEL_CACHE_SIZE:
            _MODEL_CACHE.pop(next(iter(_MODEL_CACHE)))
        if self.canvas is not None:
            self.canvas.set_model(geometry)
        self._jobs = self._jobs[-4:]

    def _update_links(self) -> None:
        """The Update button: move stale part copies, one sketch undo step (rule 12)."""
        bar, canvas = self.link_bar, self.canvas
        if bar is None or canvas is None:
            return
        moved = canvas.edit.link_updates(bar.updates)
        bar.set_updates([u for u in bar.updates if u.lost])
        if moved:
            canvas.changed()
            self.window.status.setText(strings.LINKS_UPDATED.format(count=moved))

    def _start_curves(self, shape: TopoDS_Shape, plane: SketchPlane, cut_away: bool) -> None:
        """Work out the part curves for the open sketch: the turned outline at once, the
        cut and the silhouette only when a tool has asked for them (D2609, D2683)."""
        from fdcad.core.sketch.turned import TURNED

        self._curve_args = (shape, plane, cut_away)
        self._curve_tag += 1
        asked, self._asked = self._asked, set()
        if self.canvas is not None:
            for kind in asked:
                self.canvas.model_curves.pop(kind, None)  # it was for the old state
        self._run_curves((TURNED,))
        for kind in sorted(asked):
            self._curves_wanted(kind)

    def _run_curves(self, kinds: tuple[str, ...]) -> None:
        if self._curve_args is None:
            return
        shape, plane, cut_away = self._curve_args
        model = _ModelCurvesJob(shape, plane, cut_away, kinds, self._curve_tag)
        model.signals.done.connect(self._model_curves_ready)
        self._jobs.append(model)
        start_job(QThreadPool.globalInstance(), model)

    def _curves_wanted(self, kind: str) -> None:
        """A sketch tool needs part curves that are not worked out yet (D2609, D2683)."""
        from fdcad.core.sketch.model_curves import INTERSECTION, SILHOUETTE

        if kind in (INTERSECTION, SILHOUETTE) and kind not in self._asked:
            self._asked.add(kind)
            self._run_curves((kind,))

    def _model_curves_ready(self, done: tuple[int, dict[str, ProjectedCurve]]) -> None:
        tag, curves = done
        if self.canvas is not None and tag == self._curve_tag:
            self.canvas.set_model_curves({**self.canvas.model_curves, **curves})

    def _curves_ready(self, curves: list[ProjectedCurve]) -> None:
        if self.canvas is not None:
            self.canvas.set_curve_sources(curves)

    def _tree_clicked(self) -> None:
        """A tree click while Convert Entities is active copies that curve feature (D517)."""
        tree, canvas, tab = self.window.tree, self.canvas, self.tab
        if tree is None or canvas is None or tab is None or canvas.tool_name != "convert":
            return
        fid = tree.selected_id()
        if fid is None:
            return
        try:
            name = tab.session.document.feature(fid).name
        except KeyError:
            return
        canvas.pick_feature(fid, name)

    def _outline_ready(self, section: tuple[list[Polyline], list[RefCircle]]) -> None:
        if self.canvas is not None:
            self.canvas.set_reference(section[0], section[1])
        self._jobs = self._jobs[-4:]  # keep running jobs alive, drop old ones

    def _cursor(self, x: float, y: float) -> None:
        from fdcad.ui.sketch_tools.canvas import format_length

        if self.tab is not None:
            units = self.tab.session.document.units
            self.window.coords.setText(
                strings.SKETCH_CURSOR.format(x=format_length(x, units), y=format_length(y, units))
            )

    def _edited(self) -> None:
        if self.canvas is None:
            return
        from fdcad.ui.sketch_tools import tool_text

        status = self.canvas.edit.status()
        text = strings.SKETCH_STATUS[status.display or status.state.value].format(
            dof=status.dof, message=status.message
        )
        if self.canvas.edit.mirror_axis is not None:
            text = f"{text} {tool_text.MIRROR_STATUS}"
        self.window.sketch_status.setText(text)

    # Closing -------------------------------------------------------------------------

    def accept(self) -> bool:
        """Write the sketch to the document and close it."""
        from fdcad.ui.commands.document import AddFeature, ReplaceFeature
        from fdcad.ui.commands.pictures import with_pictures

        if self.canvas is None or self.tab is None:
            return True
        canvas = self.canvas
        if not canvas._commit_editor():
            return False
        feature = canvas.edit.to_feature()
        session = self.tab.session
        after = self.after_accept
        self._close()
        if self.is_new:
            session.undo.push(with_pictures(session, AddFeature(session, feature), canvas.edit))
        elif canvas.edit.changed:
            command = ReplaceFeature(session, feature, f"{strings.EDIT_SKETCH} {feature.name}")
            session.undo.push(with_pictures(session, command, canvas.edit))
        if self.window.tree is not None:
            self.window.tree.select(feature.id)
        if after is not None:
            after(feature.id)
        return True

    def document_with_sketch(self) -> Document | None:
        """A copy of the part with the open sketch as it stands, for autosave (D590).

        None when the sketch has no changes, so the part itself can be autosaved.
        """
        from fdcad.core.document.rollback import current, insert_index

        if self.canvas is None or self.tab is None:
            return None
        edit = self.canvas.edit
        if not self.is_new and not edit.changed:
            return None
        feature = edit.to_feature()
        document = copy.copy(self.tab.session.document)
        features = list(document.features)
        if self.is_new:
            index = insert_index(document)
            if current(document) is not None and index < len(features):
                document.rollback = feature.id  # as AddFeature does while rolled back
            features.insert(index, feature)
        else:
            features = [feature if f.id == feature.id else f for f in features]
        document.features = features
        return document

    def cancel(self) -> bool:
        """Drop the changes, asking first when there are any."""
        if self.canvas is None:
            return True
        if self.canvas.edit.changed and self.window.isVisible():
            answer = QMessageBox.question(
                self.window,
                strings.DISCARD_SKETCH_TITLE,
                strings.DISCARD_SKETCH.format(name=self.canvas.edit.feature.name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,  # the safe button (U8.5)
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False
        tab, before = self.tab, self.view_before
        self._close()
        restore = getattr(tab.viewport, "restore_pose", None) if tab is not None else None
        if restore is not None and before is not None:
            restore(before)
        return True

    def _close(self) -> None:
        w = self.window
        self.after_accept = None
        if self.tab is not None:
            self.exit_nav = getattr(self.tab.viewport, "nav_count", 0)
            self.tab.hide_sketch()
            w.undo_group.setActiveStack(self.tab.session.undo)
        w.hide_side_panel()
        w.command_tabs.show_tab("features")
        if self.canvas is not None:
            self.canvas.deleteLater()
        if self.panel is not None:
            self.panel.deleteLater()
        if self.relations_panel is not None:
            self.relations_panel.deleteLater()
        if self.problems_dialog is not None:  # it acts on the canvas that goes now
            self.problems_dialog.close()
            self.problems_dialog = None
        self.tab, self.canvas, self.panel = None, None, None
        self.relations_panel = None
        self.mirror_action.setChecked(False)  # dynamic mirror ends with the sketch (D514)
        self.link_bar = None
        w.sketch_status.setText("")
        w.coords.setText("")
        self._update_actions()
        w.update_corner()


def text_open_sketch() -> str:
    """Status text when Text is used with no sketch open."""
    from fdcad.ui.strings_phase4 import TEXT_NEEDS_SKETCH

    return TEXT_NEEDS_SKETCH
