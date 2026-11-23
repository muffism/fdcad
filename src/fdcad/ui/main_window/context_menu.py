"""Right click menus in the 3D view and the sketch editor (TOOL_SPEC T9, owner note 6).

Each menu is built for what lies under the cursor, without running it, so
tests can read it (``build_*``). Items that do not apply are left out, not
greyed. Every action carries its key in ``QAction.data()``.

A plain right click opens the menu; a right drag still runs a gesture (T10.2),
because the views only ask for a menu when the mouse did not move. While the
context toolbar is shown, the menu opens just below it (T8.3).
"""

from __future__ import annotations

import contextlib
import math
import re
from collections.abc import Callable
from functools import partial
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QPoint, QPointF
from PySide6.QtGui import QAction, QCursor
from PySide6.QtWidgets import QMenu

from fdcad.ui import menu_icons, strings
from fdcad.ui import strings_extra as text

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab, MainWindow
    from fdcad.ui.sketch_tools.canvas import SketchCanvas

_FEATURE_OF_NAME = re.compile(r"(?<![A-Za-z0-9_])(f\d+)/")

#: Feature types that are solid features with a sketch (the feature menu of T9.10).
SKETCH_FEATURES = ("extrude", "revolve")


def add(menu: QMenu, key: str, label: str, slot: Callable[[], object]) -> QAction:
    """Add an action that runs ``slot`` and remembers ``key`` in its data. It shows
    the icon of its command, when the command has one (D2703)."""
    action = menu.addAction(label)
    action.setData(key)
    action.triggered.connect(lambda _checked=False: slot())
    return menu_icons.apply(action, key)


def keys(menu: QMenu) -> list[str]:
    """Keys of a menu's actions in order, separators and submenus included by title."""
    out: list[str] = []
    for action in menu.actions():
        if action.isSeparator():
            continue
        sub = action.menu()
        title = sub.title() if isinstance(sub, QMenu) else ""
        out.append(str(action.data()) if action.data() else title)
    return out


class ContextMenus:
    """Builds and shows the right click menus of one window."""

    def __init__(self, window: MainWindow) -> None:
        self.window = window
        #: Select Loop on the same edge again turns to the next face (TR92).
        self._loop_turn: tuple[Any, int] | None = None
        #: The first edge of Select Partial Loop, until the last one is picked.
        self.loop_start: Any = None
        self.last: QMenu | None = None

    # Showing ---------------------------------------------------------------------------

    def popup(self, menu: QMenu | None, at: QPoint | None = None) -> QMenu | None:
        """Show ``menu`` at ``at`` (screen pixels), or below the context toolbar (T8.3)."""
        if menu is None or menu.isEmpty():
            return None
        bar = getattr(self.window, "context_bar", None)
        if bar is not None and bar.isVisible():
            at = bar.frameGeometry().bottomLeft() + QPoint(0, 2)
        elif at is None:
            at = QCursor.pos()
        self.last = menu
        if self.window.isVisible():
            menu.popup(at)
        return menu

    def view_menu(self, tab: DocumentTab, pos: QPointF) -> QMenu | None:
        """Right click in the 3D view at ``pos`` (view pixels)."""
        view = tab.viewport
        shapes: list[Any] = []
        plane = None
        if self.window.editing != "feature":
            detect = getattr(view, "detected_at", None)
            shapes = list(detect(pos)) if detect is not None else []
            if not shapes:
                under = getattr(view, "plane_under", None)
                plane = under(pos) if under is not None else None
            if shapes and not any(shapes[0].IsSame(s) for s in tab.selection):
                select = getattr(view, "select_shapes", None)
                if select is not None:
                    select([shapes[0]])
                tab.selection = [shapes[0]]
        if self.window.editing == "feature":
            moved = self.next_pick_box()
            if moved:  # right click moves on to the next pick box (TR207)
                self.window.status.setText(strings.NEXT_PICK_BOX.format(name=moved))
                return None
        menu = self.build_view_menu(tab, shapes[:1], plane, pos)
        at = view.mapToGlobal(pos.toPoint()) if hasattr(view, "mapToGlobal") else None
        return self.popup(menu, at)

    def next_pick_box(self) -> str | None:
        """Move the open panel to its next pick box; its label, or None when there is no
        next box (then the menu offers OK and Cancel)."""
        panel = self.window.panel
        for attr in ("body_form", "form"):
            form = getattr(panel, attr, None) if panel is not None else None
            mover = getattr(form, "next_pick", None)
            result = mover() if callable(mover) else None
            if isinstance(result, str):
                return result
        return None

    # 3D view -------------------------------------------------------------------------

    def build_view_menu(
        self,
        tab: DocumentTab,
        shapes: list[Any],
        plane: str | None = None,
        pos: QPointF | None = None,
    ) -> QMenu:
        """The menu for the 3D view: feature panel open (T9.4), a plane (T9.5), a face
        (T9.6), an edge or vertex (T9.7), or empty space (T9.1)."""
        w = self.window
        menu = QMenu(w)
        menu.setObjectName("view_context_menu")
        if w.editing == "feature":
            self._feature_panel_items(menu)
            menu.addSeparator()
            self._view_items(menu)
            return menu
        if plane is not None:
            self.plane_items(menu, tab, plane)
            menu.addSeparator()
            self._view_items(menu, short=True)
            return menu
        if shapes:
            self._shape_items(menu, tab, shapes[0], pos)
            menu.addSeparator()
            self._view_items(menu, short=True)
            return menu
        from fdcad.ui.input.commands import BY_ID

        add(menu, "select", text.SELECT, self._select)
        add(menu, "appearance", BY_ID["edit.appearance"].label, lambda: w.appearance_for(""))
        self._view_items(menu)
        self._recent(menu)
        return menu

    def _select(self) -> None:
        """Select in the part: drop the selection and any armed zoom box."""
        tab = self.window.current
        if tab is None:
            return
        view = tab.viewport
        if getattr(view, "zoom_area_armed", False):
            view.zoom_area_armed = False
            view.unsetCursor()
        clear = getattr(view, "clear_selection", None)
        if clear is not None:
            clear()
        tab.selection = []

    def _feature_panel_items(self, menu: QMenu) -> None:
        w = self.window
        add(menu, "ok", strings.OK, w.confirm_ok)
        add(menu, "cancel", strings.CANCEL, w.confirm_cancel)
        panel = w.panel
        if panel is not None and panel.flags.get("reverse") is not None:
            add(menu, "reverse", text.REVERSE_DIRECTION, lambda: panel.flip("depth"))

    def plane_items(self, menu: QMenu, tab: DocumentTab, fid: str) -> None:
        """Sketch, Normal To, Hide or Show and Rename for a plane (T9.5)."""
        w = self.window
        tree = w.tree
        shown = fid in tab.visible_plane_ids()
        add(menu, "sketch", text.SKETCH, lambda: w._start_sketch_on_plane(fid))
        add(menu, "normal_to", text.NORMAL_TO, lambda: self.normal_to_feature(fid))
        if tree is not None:
            add(
                menu,
                "hide_show",
                text.HIDE if shown else text.SHOW,
                lambda: tree.set_visible(fid, not shown),
            )
            add(menu, "rename", text.RENAME, lambda: tree.rename(fid))

    def normal_to_feature(self, fid: str) -> None:
        """Look at a plane, a sketch or a feature's sketch from the tree or a menu."""
        w = self.window
        if w.tree is not None:
            w.tree.select(fid)
        current = self.window.current
        if current is not None:
            current.selection = []
        w.normal_to()

    def _shape_items(self, menu: QMenu, tab: DocumentTab, shape: Any, pos: QPointF | None) -> None:
        from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE

        from fdcad.core.naming.select import is_planar_face

        w = self.window
        kind = shape.ShapeType()
        if kind == TopAbs_FACE:
            if is_planar_face(shape):
                add(menu, "sketch", text.SKETCH, lambda: self._run_sketch(tab, shape))
            if face_axis(shape) is not None or is_planar_face(shape):
                add(menu, "normal_to", text.NORMAL_TO, w.normal_to)
        if pos is None:
            pos = _cursor_in(tab)  # opened from the keyboard (audit D11 item 9, D745)
        if pos is not None:
            at = pos
            add(menu, "select_other", text.SELECT_OTHER, lambda: self.select_other(tab, at))
        if kind == TopAbs_FACE:
            # Hide the clicked face's body; it was only on the tree (T9.6, audit D11 item 8).
            from fdcad.ui.strings_phase3 import HIDE_BODY

            add(menu, "hide", HIDE_BODY, lambda: self._hide_body(tab, shape))
        if kind == TopAbs_FACE:
            # Direct editing on the clicked face (PHASE3_SPEC P3.1, owner favourites).
            from fdcad.ui.body_tools import flow as phase3
            from fdcad.ui.input.commands import BY_ID

            for cid in ("feature.move_face", "feature.offset_face", "feature.delete_face"):
                add(menu, cid, BY_ID[cid].label, partial(phase3.start, w, cid, shape))
        if kind == TopAbs_FACE:  # TR132 (D1404): one edge of a fillet
            self._fillet_edge_item(menu, tab, shape)
            from fdcad.ui.property_panel.forms.replace_face_form import start_replace

            # TR130 (D1412): the clicked face becomes the face to replace.
            add(menu, "replace_face", strings.REPLACE_FACE, lambda: start_replace(w, tab))
            from fdcad.ui.property_panel.forms.push_pull_form import start_push_pull

            add(menu, "push_pull", strings.PUSH_PULL, lambda: start_push_pull(w, tab))  # TR267
            from fdcad.ui.property_panel.forms.split_line_form import start_split_line

            add(menu, "split_line", strings.SPLIT_LINE, lambda: start_split_line(w, tab))  # TR60
            from fdcad.ui.property_panel.forms.parting_line_form import start_parting_line

            add(menu, "parting_line", strings.PARTING_LINE, lambda: start_parting_line(w, tab))
        if kind == TopAbs_FACE:
            # Colour the clicked face; the panel also offers its feature, bodies and the part.
            add(menu, "appearance", BY_ID["edit.appearance"].label, w.appearance_tool.open)
        if kind == TopAbs_EDGE:
            add(menu, "select_midpoint", text.SELECT_MIDPOINT, lambda: self.midpoint(tab, shape))
            add(menu, "select_loop", strings.SELECT_LOOP, lambda: self.select_loop(tab, shape))
            near = getattr(tab.viewport, "_point_under_cursor", lambda: None)()
            add(  # TR51: a sketch square to the edge at its nearer end
                menu,
                "sketch_normal",
                strings.SKETCH_NORMAL_TO_EDGE,
                lambda: sketch_normal_to(self.window, tab, shape, near),
            )
            if self.loop_start is not None and not self.loop_start.IsSame(shape):
                add(
                    menu,
                    "end_partial_loop",
                    strings.END_PARTIAL_LOOP,
                    lambda: self.end_partial_loop(tab, shape),
                )
            else:
                add(
                    menu,
                    "start_partial_loop",
                    strings.START_PARTIAL_LOOP,
                    lambda: self.start_partial_loop(tab, shape),
                )
        if kind in (TopAbs_EDGE, TopAbs_FACE):
            add(
                menu,
                "select_tangent",
                strings.SELECT_TANGENT,
                lambda: self.select_tangent(tab, shape),
            )
        others = [s for s in tab.selection if not s.IsSame(shape)]
        if kind == TopAbs_FACE and others:  # TR328 (D2108): the picks are the boundary
            from fdcad.ui.strings_config import SEED_PICK

            add(menu, "select_between", SEED_PICK, lambda: self.select_between(tab, shape))
        if kind in (TopAbs_EDGE, TopAbs_FACE):  # TR152 (D2105)
            from fdcad.ui.main_window.named_items import name_item
            from fdcad.ui.strings_config import NAMED_TITLE

            add(menu, "name_item", NAMED_TITLE, lambda: name_item(w, tab, shape))
        fid = self.feature_of(tab, shape)
        if fid is not None and kind in (TopAbs_FACE, TopAbs_EDGE):
            add(menu, "go_to_feature", text.GO_TO_FEATURE, lambda: w.tree_follow.go_to(tab, shape))
        seed = self.seed_of(tab, shape) if kind == TopAbs_FACE else None
        if seed is not None:  # TR142 (D1016): a pattern copy opens the original
            add(menu, "edit_seed", strings.EDIT_SEED, lambda: w.edit_feature(seed))
            copy = self.instance_of(tab, shape)
            if copy is not None:  # TR59 item 3 (D1900): this copy's own values
                add(
                    menu,
                    "copy_values",
                    strings.COPY_VALUES,
                    lambda: self.edit_copy_values(copy[0], copy[1]),
                )
        if fid is not None and w.tree is not None:
            item = w.tree.item_for(fid)
            sub = w.tree._context_menu(tab.session, item) if item is not None else None
            if sub is not None:
                sub.setTitle(tab.session.document.feature(fid).name)
                menu.addSeparator()
                menu.addMenu(sub)

    def _fillet_edge_item(self, menu: QMenu, tab: DocumentTab, shape: Any) -> None:
        from fdcad.core.fillet_edit import edge_index, fillet_face_owner

        body = tab.session.report.body if tab.session.report is not None else None
        if body is None:
            return
        owner = fillet_face_owner(tab.session.document, body.names_of(shape))
        if owner is None or not edge_index(tab.session.document.feature(owner[0]), owner[1]):
            return
        from fdcad.ui.tree.change_fillets import EdgeDialog

        fid, edge = owner
        add(
            menu,
            "change_fillet_edge",
            strings.CHANGE_FILLET_EDGE,
            lambda: EdgeDialog(tab.session, fid, edge, self.window).exec(),
        )

    def _run_sketch(self, tab: DocumentTab, shape: Any) -> None:
        tab.selection = [shape]
        if self.window.sketch_mode is not None:
            self.window.sketch_mode.start()

    @staticmethod
    def instance_of(tab: DocumentTab, shape: Any) -> tuple[str, tuple[int, int]] | None:
        """The pattern and instance number of the copy ``shape`` is on, or None (TR59)."""
        from fdcad.core.features.seed_of import instance_of
        from fdcad.core.naming.select import reference_for

        report = tab.session.report
        if report is None or report.body is None:
            return None
        ref = reference_for(report.body, shape)
        name = ref.get("name") if ref is not None else None
        return instance_of(tab.session.document, name) if isinstance(name, str) else None

    def edit_copy_values(self, fid: str, index: tuple[int, int]) -> None:
        """Open the pattern with an entry for this copy started in Copy values (TR59,
        D1900), so the user types only the values."""
        from fdcad.core.features.seed_of import add_instance_values

        w = self.window
        w.edit_feature(fid)
        panel = w.panel
        form = getattr(panel, "body_form", None) if panel is not None else None
        line = form.widgets.get("instance_values") if form is not None else None
        if line is None:
            return
        line.setText(add_instance_values(line.text(), index))
        line.setFocus()
        line.setCursorPosition(len(line.text()))

    @staticmethod
    def seed_of(tab: DocumentTab, shape: Any) -> str | None:
        """The seed feature of the pattern copy ``shape`` belongs to, or None (TR142)."""
        from fdcad.core.features.seed_of import seed_of
        from fdcad.core.naming.select import reference_for

        report = tab.session.report
        if report is None or report.body is None:
            return None
        ref = reference_for(report.body, shape)
        name = ref.get("name") if ref is not None else None
        return seed_of(tab.session.document, name) if isinstance(name, str) else None

    @staticmethod
    def feature_of(tab: DocumentTab, shape: Any) -> str | None:
        """The feature that made a face, edge or vertex of the part, or None."""
        from fdcad.core.naming.select import reference_for

        report = tab.session.report
        if report is None or report.body is None:
            return None
        ref = reference_for(report.body, shape)
        name = ref.get("name") if ref is not None else None
        match = _FEATURE_OF_NAME.search(name) if isinstance(name, str) else None
        if match is None:
            return None
        fid = match.group(1)
        return fid if any(f.id == fid for f in tab.session.document.features) else None

    def _hide_body(self, tab: DocumentTab, face: Any) -> bool:
        """Hide the body of ``face``, as H does with the face picked."""
        tab.selection = [face]
        return bool(self.window.body_display.hide_or_show())

    def select_other(self, tab: DocumentTab, pos: QPointF) -> Any:
        """Open the Select Other list for the items under ``pos`` (T9.13, T14.3.1)."""
        from fdcad.ui.viewport.select_other import open_select_other

        return open_select_other(self.window, tab, pos)

    # Loops and tangent sets (TR92, D823) ------------------------------------------------

    @staticmethod
    def _body(tab: DocumentTab) -> Any:
        report = tab.session.report
        return report.body.shape if report is not None and report.body is not None else None

    @staticmethod
    def _pick_shapes(tab: DocumentTab, shapes: list[Any]) -> list[Any]:
        tab.selection = list(shapes)
        pick = getattr(tab.viewport, "select_shapes", None)
        if pick is not None:
            pick(shapes)
        return shapes

    def select_loop(self, tab: DocumentTab, edge: Any) -> list[Any]:
        """Select the loop of edges through ``edge``: on a picked face that holds it (its
        inner loop for a hole edge), else on one of its faces; choosing it again on the
        same edge turns to the next face."""
        from OCP.TopAbs import TopAbs_FACE

        from fdcad.core.naming.loops import loop_of, select_loop

        body = self._body(tab)
        if body is None:
            return []
        for face in tab.selection:
            if face.ShapeType() == TopAbs_FACE and loop_of(face, edge):
                self._loop_turn = None
                return self._pick_shapes(tab, loop_of(face, edge))
        turn = 0
        if self._loop_turn is not None and self._loop_turn[0].IsSame(edge):
            turn = self._loop_turn[1] + 1
        self._loop_turn = (edge, turn)
        found = self._pick_shapes(tab, select_loop(body, edge, turn))
        self.window.status.setText(strings.LOOP_SELECTED.format(n=len(found)))
        return found

    def start_partial_loop(self, tab: DocumentTab, edge: Any) -> None:
        """Remember the first edge; right click the last edge to finish."""
        self.loop_start = edge
        self._pick_shapes(tab, [edge])
        self.window.status.setText(strings.PARTIAL_LOOP_STARTED)

    def end_partial_loop(self, tab: DocumentTab, edge: Any) -> list[Any]:
        """Select the edges from the first edge to ``edge`` along their loop."""
        from OCP.TopAbs import TopAbs_FACE

        from fdcad.core.naming.loops import partial_loop

        body, first = self._body(tab), self.loop_start
        self.loop_start = None
        if body is None or first is None:
            return []
        face = next((f for f in tab.selection if f.ShapeType() == TopAbs_FACE), None)
        found = self._pick_shapes(tab, partial_loop(body, first, edge, face))
        self.window.status.setText(strings.LOOP_SELECTED.format(n=len(found)))
        return found

    def select_between(self, tab: DocumentTab, seed: Any) -> list[Any]:
        """Select every face reached from the seed face without crossing the picked
        faces and edges (TR328, D2108)."""
        from fdcad.core.seed_pick import faces_between
        from fdcad.ui.strings_config import SEED_PICK_DONE, SEED_PICK_FAILED

        body = self._body(tab)
        if body is None:
            return []
        boundaries = [s for s in tab.selection if not s.IsSame(seed)]
        try:
            found = faces_between(body, seed, boundaries)
        except ValueError as exc:
            self.window.status.setText(SEED_PICK_FAILED.format(reason=exc))
            return []
        self._pick_shapes(tab, found)
        self.window.status.setText(SEED_PICK_DONE.format(n=len(found)))
        return found

    def select_tangent(self, tab: DocumentTab, shape: Any) -> list[Any]:
        """Select every face or edge joined smoothly to ``shape``."""
        from OCP.TopAbs import TopAbs_FACE

        from fdcad.core.naming.loops import tangent_edges, tangent_faces

        body = self._body(tab)
        if body is None:
            return []
        if shape.ShapeType() == TopAbs_FACE:
            found = tangent_faces(body, shape)
        else:
            found = tangent_edges(body, shape)
        self._pick_shapes(tab, found)
        self.window.status.setText(strings.TANGENT_SELECTED.format(n=len(found)))
        return found

    def midpoint(self, tab: DocumentTab, edge: Any) -> tuple[float, float, float] | None:
        """Select the midpoint of an edge (T9.7); used by later picks such as a From vertex."""
        from fdcad.core.naming.edges import edge_midpoint

        point = edge_midpoint(edge)
        if point is None:
            return None
        vertex = make_vertex(point)
        tab.selection = [vertex]
        highlight = getattr(tab.viewport, "preview_shapes", None)
        if highlight is not None:
            highlight([vertex])
        from fdcad.ui.sketch_tools.canvas import format_length

        units = tab.session.document.units
        shown = ", ".join(format_length(v, units) for v in point)
        self.window.status.setText(text.MIDPOINT_SELECTED.format(point=shown))
        return point

    def _view_items(self, menu: QMenu, short: bool = False) -> None:
        """Zoom to Fit, then (unless ``short``) Previous View, orientations and styles."""
        w = self.window
        add(menu, "zoom_fit", text.ZOOM_TO_FIT, w.zoom_to_fit)
        if short:
            menu.addMenu(self._orientations(menu))
            return
        add(menu, "previous_view", text.PREVIOUS_VIEW, w.previous_view)
        menu.addMenu(self._orientations(menu))
        styles = QMenu(text.DISPLAY_STYLE, menu)
        for style, label in text.STYLE_NAMES.items():
            action = add(styles, f"style.{style}", label, partial(self._style, style))
            action.setCheckable(True)
            current = w.commands.actions.get(f"view.{style}")
            action.setChecked(current is not None and current.isChecked())
        menu.addMenu(styles)

    def _style(self, style: str) -> None:
        action = self.window.commands.actions.get(f"view.{style}")
        if action is not None:
            action.setChecked(True)
        self.window.set_style(style)

    def _orientations(self, parent: QMenu) -> QMenu:
        sub = QMenu(text.VIEW_ORIENTATION, parent)
        for name, label in text.VIEW_NAMES.items():
            add(sub, f"view.{name}", label, partial(self.window.set_view, name))
        add(sub, "normal_to", text.NORMAL_TO, self.window.normal_to)
        saved = getattr(self.window, "saved_views", None)
        if saved is not None:
            saved.fill(sub, manage=False)  # TR14.2
        return sub

    def _recent(self, menu: QMenu) -> None:
        from fdcad.ui.input.commands import BY_ID

        a = self.window.commands
        sub = QMenu(text.RECENT_COMMANDS, menu)
        for cid in a.recent:
            if cid in BY_ID and cid in a.actions:
                add(sub, cid, BY_ID[cid].label, partial(a.trigger, cid))
        if sub.isEmpty():
            empty = sub.addAction(text.NO_RECENT)
            empty.setEnabled(False)
        menu.addMenu(sub)

    # Sketch editor -------------------------------------------------------------------

    def sketch_menu(self, canvas: SketchCanvas, pos: QPointF) -> QMenu | None:
        """Right click in the sketch editor at ``pos`` (canvas pixels)."""
        menu = self.build_sketch_menu(canvas, pos)
        return self.popup(menu, canvas.mapToGlobal(pos.toPoint()))

    def build_sketch_menu(self, canvas: SketchCanvas, pos: QPointF | None = None) -> QMenu:
        """The menu while a tool is active (T9.3), on a dimension (T9.9), on sketch items
        (T9.8), or in empty space (T9.2)."""
        menu = QMenu(self.window)
        menu.setObjectName("sketch_context_menu")
        if canvas.tool is not None or canvas.dimension_mode:
            self._tool_items(menu, canvas)
            return menu
        hit = canvas.pick(pos) if pos is not None else None
        if hit is not None and hit not in canvas.selection:
            canvas.selection = [hit]
            canvas.selection_changed.emit()
            canvas.update()
        dims = [s for s in canvas.selection if s.startswith("d") and canvas._exists(s)]
        ents = [s for s in canvas.selection if s in canvas.edit.sketch.entities]
        from fdcad.ui.sketch_tools.canvas import relation_index

        rels = [s for s in canvas.selection if relation_index(s) is not None]
        if dims and not ents and len(dims) > 1 and (hit is None or hit in dims):
            self._dimensions_items(menu, canvas, dims)  # TR111: several at once
        elif dims and not ents and (hit is None or hit.startswith("d")):
            self._dimension_items(menu, canvas, dims[0] if hit is None else hit)
        elif rels and not ents and not dims:
            if len(rels) == 1:  # TR237
                one = rels[0]
                add(
                    menu, "explain", strings.EXPLAIN_RELATION, lambda: explain_relation(canvas, one)
                )
            self._off_item(menu, canvas, rels)  # TR109
            picked = [relation_index(r) for r in rels]
            indexes = [i for i in picked if i is not None]
            sk_rels = canvas.edit.sketch.relations
            if any(i < len(sk_rels) and sk_rels[i].weak for i in indexes):  # TR362
                add(
                    menu,
                    "keep_relation",
                    strings.KEEP_RELATION,
                    lambda: canvas.run(lambda: canvas.edit.make_strong(indexes)),
                )
            add(menu, "delete", text.DELETE, canvas.delete_selection)
        elif ents:
            self._entity_items(menu, canvas, ents, hit)
            menu.addMenu(layers_menu(canvas, menu, ents))  # TR389
        else:
            self._empty_sketch_items(menu, canvas)
        return menu

    def _tool_items(self, menu: QMenu, canvas: SketchCanvas) -> None:
        add(menu, "select", text.SELECT, lambda: canvas.set_tool(None))
        tool = canvas.tool
        if tool is not None and tool.name in ("line", "centerline") and tool.busy:
            add(menu, "end_chain", text.END_CHAIN, lambda: self._end_chain(canvas))
        self._snapping(menu)
        add(menu, "zoom_fit", text.ZOOM_TO_FIT, canvas.fit)
        snaps = QMenu(strings.SNAP_ONLY, menu)  # TR102: the next click snaps to one kind
        for kind, label in strings.SNAP_ONLY_CHOICES.items():
            item = add(
                snaps, f"snap_only.{kind}", label, partial(setattr, canvas, "snap_only", kind)
            )
            item.setCheckable(True)
            item.setChecked(getattr(canvas, "snap_only", None) == kind)
        menu.addMenu(snaps)

    @staticmethod
    def _end_chain(canvas: SketchCanvas) -> None:
        if canvas.tool is not None:
            canvas.tool.cancel()
            canvas.update()

    def _snapping(self, menu: QMenu) -> None:
        from dataclasses import replace

        w = self.window
        on = w.settings.sketch_options.snapping

        def toggle() -> None:
            w.settings.sketch_options = replace(w.settings.sketch_options, snapping=not on)
            w._sketch_options_changed()

        action = add(menu, "snapping", text.SNAPPING, toggle)
        action.setCheckable(True)
        action.setChecked(on)

    def _empty_sketch_items(self, menu: QMenu, canvas: SketchCanvas) -> None:
        w = self.window
        mode = w.sketch_mode
        add(menu, "select", text.SELECT, lambda: canvas.set_tool(None))
        if mode is not None:
            add(menu, "exit_sketch", text.EXIT_SKETCH, mode.accept)
            add(menu, "discard", text.DISCARD_CHANGES, mode.cancel)
        add(menu, "dimension", text.SMART_DIMENSION, lambda: canvas.set_tool("dimension"))
        if canvas.edit.jump_sides:  # TR338 (D1302)
            add(menu, "keep_side", strings.KEEP_THIS_SIDE, lambda: _keep_side(canvas))
        if canvas.edit.sketch.keep_sides:
            add(menu, "remove_side_locks", strings.REMOVE_SIDE_LOCKS, lambda: _unlock(canvas))
        self._snapping(menu)
        last = getattr(mode, "last_tool", "") if mode is not None else ""
        if last and last != "dimension":
            label = strings.SKETCH_TOOLS.get(last, last)
            add(menu, "last_tool", text.LAST_TOOL.format(tool=label), lambda: canvas.set_tool(last))
        recent = list(getattr(mode, "recent_tools", [])) if mode is not None else []
        if len(recent) >= 2:  # TR204: sketch tools only, apart from part commands
            sub = QMenu(strings.RECENT_SKETCH_TOOLS, menu)
            for name in recent:
                add(
                    sub,
                    f"tool.{name}",
                    strings.SKETCH_TOOLS.get(name, name),
                    partial(canvas.set_tool, name),
                )
            menu.addMenu(sub)
        add(menu, "zoom_fit", text.ZOOM_TO_FIT, canvas.fit)
        add(menu, "normal_to", strings.NORMAL_TO, w.normal_to)  # T9.2 (audit D11 item 7)
        add(menu, "grid_spacing", strings.GRID_SPACING, lambda: grid_spacing(w, canvas))  # TR102
        formulas = add(  # TR235
            menu, "show_formulas", strings.SHOW_FORMULAS, lambda: toggle_formulas(canvas)
        )
        formulas.setCheckable(True)
        formulas.setChecked(type(canvas).show_formulas)
        shade = add(  # TR335 (D952)
            menu,
            "shade_regions",
            strings.SHADE_REGIONS,
            lambda: toggle_class(canvas, "shade_regions"),
        )
        shade.setCheckable(True)
        shade.setChecked(type(canvas).shade_regions)
        points = add(
            menu, "show_points", strings.SHOW_POINTS, lambda: toggle_class(canvas, "show_points")
        )
        points.setCheckable(True)
        points.setChecked(type(canvas).show_points)
        menu.addMenu(sketch_display_menu(canvas, menu))  # TR341 (D964)
        menu.addMenu(layers_menu(canvas, menu, []))  # TR389 (D982)
        reference = add(  # TR111 (D965)
            menu, "reference_mode", strings.REFERENCE_MODE, lambda: toggle_reference_mode(canvas)
        )
        reference.setCheckable(True)
        reference.setChecked(type(canvas).reference_mode)
        add(menu, "shake", strings.SHAKE_TITLE, lambda: shake_sketch(canvas))  # TR372 (D970)
        lock = add(menu, "lock_points", strings.LOCK_POINTS, lambda: toggle_lock(canvas))
        lock.setCheckable(True)
        lock.setChecked(canvas.points_locked)
        free = add(menu, "free_drag", strings.FREE_DRAG, lambda: toggle_free_drag(canvas))
        free.setCheckable(True)  # TR112 item 1 (D1716)
        free.setChecked(canvas.edit.free_drag)
        detach = add(menu, "detach_drag", strings.DETACH_DRAG, lambda: toggle_detach(canvas))
        detach.setCheckable(True)  # TR112 item 3
        detach.setChecked(canvas.detach_drag)
        if mode is not None and getattr(mode, "cut_away_action", None) is not None:
            cut = add(menu, "cut_away", mode.cut_away_action.text(), mode.toggle_cut_away)  # TR113
            cut.setCheckable(True)
            cut.setChecked(mode.cut_away_action.isChecked())
        from fdcad.ui.sketch_tools.airfoil_dialog import insert_airfoil

        add(menu, "airfoil", strings.AIRFOIL_TITLE, lambda: insert_airfoil(canvas))  # TR257
        if canvas.edit.sketch.texts:  # TR121 item 1 (D1713)
            from fdcad.ui.sketch_tools.text_explode_job import explode_texts

            add(menu, "explode_text", strings.TEXT_EXPLODE, lambda: explode_texts(canvas))
        from fdcad.ui.sketch_tools.gear_dialog import insert_gear

        add(menu, "gear", strings.GEAR_TITLE, lambda: insert_gear(canvas))  # TR161
        from fdcad.ui import strings_print
        from fdcad.ui.sketch_tools.code_tag_dialog import insert_code_tag

        add(menu, "code_tag", strings_print.CODE_TAG_TITLE, lambda: insert_code_tag(canvas))
        from fdcad.ui.sketch_tools.shape_dialog import insert_shape

        add(menu, "shapes", strings.PRESET_TITLE, lambda: insert_shape(canvas))  # TR228
        from fdcad.ui.sketch_tools.point_file_import import points_from_file

        add(menu, "points_file", strings.POINT_FILE_TITLE, lambda: points_from_file(canvas))
        from fdcad.ui.sketch_tools.modify_dialog import modify

        add(menu, "modify_sketch", strings.MODIFY_SKETCH_TITLE, lambda: modify(canvas))  # TR50
        from fdcad.ui.sketch_tools.find_relations_dialog import find_relations

        add(menu, "find_relations", strings.FIND_RELATIONS_TITLE, lambda: find_relations(canvas))
        self._mean_item(menu, canvas)  # TR306

    @staticmethod
    def _mean_item(menu: QMenu, canvas: SketchCanvas) -> None:
        """Mean Dimensions, or Typed Dimensions when they are at the mean (TR306, D911).
        Shown only when a dimension has an uneven tolerance."""
        from fdcad.core.sketch.mean_dimensions import can_mean, is_meaned, to_mean, to_nominal

        sketch = canvas.edit.sketch
        if is_meaned(sketch):

            def back() -> None:
                canvas.run(lambda: to_nominal(canvas.edit.sketch))
                canvas.status_message.emit(strings.MEAN_DIMS_BACK)

            add(menu, "mean_dimensions", strings.MEAN_DIMS_NOMINAL, back)
        elif any(can_mean(d) for d in sketch.dimensions):

            def mean() -> None:
                count = sum(1 for d in canvas.edit.sketch.dimensions if can_mean(d))
                canvas.run(lambda: to_mean(canvas.edit.sketch))
                canvas.status_message.emit(strings.MEAN_DIMS_DONE.format(count=count))

            add(menu, "mean_dimensions", strings.MEAN_DIMS_TITLE, mean)

    def _dimensions_items(self, menu: QMenu, canvas: SketchCanvas, dids: list[str]) -> None:
        """Several picked dimensions: make them all reference, or all driving when they
        are all reference already (TR111, D965), turn off, delete."""
        found = [d for d in (canvas._dimension(i) for i in dids) if d is not None]
        if not found:
            return
        driving = any(d.driving for d in found)
        label = text.MAKE_REFERENCE if driving else text.MAKE_DRIVING
        ids = [d.id for d in found]
        add(menu, "reference", label, lambda: set_reference(canvas, ids, driving))
        add(menu, "link_values", strings.LINK_VALUES, lambda: link_values(canvas, ids))  # TR193
        if any(d.link for d in found):
            add(menu, "unlink_values", strings.UNLINK_VALUES, lambda: unlink_values(canvas, ids))
        self._off_item(menu, canvas, ids)  # TR109
        add(menu, "delete", text.DELETE, canvas.delete_selection)

    def _dimension_items(self, menu: QMenu, canvas: SketchCanvas, did: str) -> None:
        dim = canvas._dimension(did)
        if dim is None:
            return
        if dim.driving:
            add(menu, "edit_value", text.EDIT_VALUE, lambda: canvas.edit_dimension(did))
        label = text.MAKE_REFERENCE if dim.driving else text.MAKE_DRIVING
        add(menu, "reference", label, lambda: toggle_reference(canvas, did))
        from fdcad.ui.sketch_tools.dimension_display_dialog import edit_display

        add(menu, "display", strings.DIM_DISPLAY_TITLE, lambda: edit_display(canvas, did))
        if dim.link:  # TR193
            add(menu, "unlink_values", strings.UNLINK_VALUES, lambda: unlink_values(canvas, [did]))
        if dim.driving and not dim.off:  # TR236
            from fdcad.ui.sketch_tools.step_dimension import step_dimension

            add(menu, "step_values", strings.STEP_TITLE, lambda: step_dimension(canvas, did))
        self._off_item(menu, canvas, [did])  # TR109
        if dim.driving:  # TR342 (D1311)
            sub = QMenu(strings.DIM_LIMIT, menu)
            for key, label in strings.DIM_LIMITS.items():
                item = add(
                    sub, f"limit.{key or 'exact'}", label, partial(set_limit, canvas, did, key)
                )
                item.setCheckable(True)
                item.setChecked((dim.limit or "") == key)
            menu.addMenu(sub)
        add(menu, "delete", text.DELETE, canvas.delete_selection)

    @staticmethod
    def _off_item(menu: QMenu, canvas: SketchCanvas, ids: list[str]) -> None:
        """Turn Off, or Turn On when every picked relation or dimension is off (TR109)."""
        sk = canvas.edit.sketch
        found = []
        for item in ids:
            if item.startswith("r") and item[1:].isdigit() and int(item[1:]) < len(sk.relations):
                found.append(sk.relations[int(item[1:])].off)
            dim = canvas._dimension(item) if item.startswith("d") else None
            if dim is not None:
                found.append(dim.off)
        if not found:
            return
        label = strings.TURN_ON if all(found) else strings.TURN_OFF
        add(menu, "switch_off", label, lambda: canvas.run(lambda: canvas.edit.toggle_off(ids)))

    def _entity_items(
        self, menu: QMenu, canvas: SketchCanvas, ids: list[str], hit: str | None
    ) -> None:
        from fdcad.ui.sketch_tools.edit import relations_for

        add(menu, "delete", text.DELETE, canvas.delete_selection)
        add(menu, "construction", text.CONSTRUCTION, lambda: toggle_construction(canvas))
        from fdcad.core.sketch.links import detach, linked_in

        if linked_in(canvas.edit.sketch, ids):  # TR340: copies of model edges
            add(
                menu,
                "detach",
                text.DETACH,
                lambda: canvas.run(lambda: detach(canvas.edit.sketch, ids)),
            )
        add(menu, "dimension", text.SMART_DIMENSION, lambda: dimension_selection(canvas))
        fitting = [r for r in relations_for(canvas.edit.sketch, ids) if r != "fixed"]
        if fitting:
            sub = QMenu(text.ADD_RELATION, menu)
            for rtype in fitting:
                add(
                    sub,
                    f"relation.{rtype}",
                    strings.RELATION_NAMES[rtype],
                    partial(relate, canvas, rtype),
                )
            menu.addMenu(sub)
        if "fixed" in relations_for(canvas.edit.sketch, ids):
            add(menu, "fix", text.FIX, lambda: relate(canvas, "fixed"))
        if hit is not None and hit in canvas.edit.sketch.entities:
            add(menu, "select_chain", text.SELECT_CHAIN, lambda: select_chain(canvas, hit))
        else:  # opened from the keyboard or off the items: chain from the selection (D2681)
            add(menu, "select_chain", text.SELECT_CHAIN, lambda: select_chain(canvas, *ids))
        from fdcad.core.sketch.model import Line, Point

        tab = self.window.current
        if len(ids) == 1 and isinstance(canvas.edit.sketch.entities.get(ids[0]), Point):
            _handle_items(menu, canvas, ids[0])  # TR43 (D1305)
        from fdcad.core.sketch.model import Spline

        _block_items(menu, canvas, ids)  # TR34 (D1717)
        if len(ids) == 1 and isinstance(canvas.edit.sketch.entities.get(ids[0]), Line):
            from fdcad.ui.sketch_tools.polygon_dialog import edit_polygon_values, polygon_of

            side = ids[0]
            if polygon_of(canvas, side) is not None:  # TR114 item 2 (D1709)
                add(
                    menu,
                    "edit_polygon",
                    strings.POLYGON_EDIT_TITLE,
                    lambda: edit_polygon_values(canvas, side),
                )
        if len(ids) == 1 and isinstance(canvas.edit.sketch.entities.get(ids[0]), Spline):
            spline_id = ids[0]  # TR115 item 4 (D1314)
            add(menu, "relax_spline", strings.RELAX_SPLINE, lambda: _relax(canvas, spline_id))
            add(  # TR115 item 4 (D2201)
                menu,
                "spline_length",
                strings.SPLINE_LENGTH,
                lambda: _path_length(canvas, [spline_id]),
            )
        if _is_chain(canvas, ids):  # TR45 (D1307)
            add(menu, "path_length", strings.PATH_LENGTH, lambda: _path_length(canvas, ids))
        if len(ids) == 1 and isinstance(canvas.edit.sketch.entities.get(ids[0]), Line):
            one_line = ids[0]  # TR111 item 2 (D1312)
            add(
                menu,
                "angle_horizontal",
                strings.ANGLE_TO_HORIZONTAL,
                partial(_angle_to_axis, canvas, one_line, "horizontal"),
            )
            add(
                menu,
                "angle_vertical",
                strings.ANGLE_TO_VERTICAL,
                partial(_angle_to_axis, canvas, one_line, "vertical"),
            )
        if len(ids) == 1:
            from fdcad.ui.sketch_tools.datum_dimensions import chamfer_problem

            if chamfer_problem(canvas.edit.sketch, ids[0]) is None:  # TR45 (D1307)
                sub = QMenu(strings.CHAMFER_DIMENSION, menu)
                one = ids[0]
                add(
                    sub,
                    "chamfer.angle",
                    strings.CHAMFER_ANGLE,
                    partial(_chamfer, canvas, one, "angle"),
                )
                add(
                    sub,
                    "chamfer.lengths",
                    strings.CHAMFER_LENGTHS,
                    partial(_chamfer, canvas, one, "lengths"),
                )
                menu.addMenu(sub)
        if len(ids) == 1 and isinstance(canvas.edit.sketch.entities.get(ids[0]), Point) and tab:
            from fdcad.ui.sketch_tools import pierce as pc

            pid = ids[0]
            if pc.pierced(canvas, pid):  # TR101
                add(menu, "unpierce", strings.PIERCE_REMOVE, lambda: pc.unpierce(canvas, pid))
            else:
                doc = tab.session.document
                add(
                    menu,
                    "pierce",
                    strings.PIERCE,
                    lambda: pc.pierce(canvas, pid, doc, self.window.status),
                )
        from fdcad.core.sketch.model import Arc

        if len(ids) == 1 and isinstance(canvas.edit.sketch.entities.get(ids[0]), Line | Arc):
            one = ids[0]  # TR103
            add(
                menu,
                "segment",
                strings.SEGMENT,
                lambda: segment_curve(canvas, one, False, self.window.status),
            )
            add(
                menu,
                "segment_points",
                strings.SEGMENT_POINTS,
                lambda: segment_curve(canvas, one, True, self.window.status),
            )
        curves = [i for i in ids if not isinstance(canvas.edit.sketch.entities.get(i), Point)]
        if len(ids) == 2 and len(curves) == 2:  # TR104: the first picked is replaced
            add(
                menu,
                "replace_entity",
                strings.REPLACE_ENTITY,
                lambda: replace_entity(canvas, ids, False, self.window.status),
            )
            add(
                menu,
                "replace_entity_keep",
                strings.REPLACE_ENTITY_KEEP,
                lambda: replace_entity(canvas, ids, True, self.window.status),
            )
        if sum(1 for i in ids if isinstance(canvas.edit.sketch.entities.get(i), Line)) >= 2:
            from fdcad.ui.sketch_tools.round_all import round_all_corners

            add(  # TR227
                menu,
                "round_all",
                strings.ROUND_ALL_TITLE,
                lambda: round_all_corners(canvas, self.window.status),
            )
        if len(ids) >= 2:  # TR229 (D912)
            add(menu, "convex_hull", strings.HULL_TITLE, lambda: convex_hull(canvas, ids))
        if any(isinstance(canvas.edit.sketch.entities.get(i), Line | Arc) for i in ids):
            add(menu, "slot_along", strings.SLOT_ALONG_TITLE, lambda: slot_along(canvas, ids))
        if _has_axis_relations(canvas, ids):  # TR124 (D950)
            add(menu, "swap_axis", strings.SWAP_AXIS_TITLE, lambda: swap_axis(canvas, ids))

    # Keyboard (Shift+F10, Menu key) ------------------------------------------------------

    def for_selection(self) -> QMenu | None:
        """Open the menu for the current selection where the focus is (T9.12)."""
        w = self.window
        tree = w.tree
        mode = w.sketch_mode
        if tree is not None and tree.hasFocus():
            item = tree.currentItem()
            session = tree.session
            if item is None or session is None:
                return None
            menu = tree._context_menu(session, item)
            rect = tree.visualItemRect(item)
            return self.popup(menu, tree.viewport().mapToGlobal(rect.bottomLeft()))
        if mode is not None and mode.canvas is not None:
            canvas = mode.canvas
            menu = self.build_sketch_menu(canvas, None)
            centre = QPoint(canvas.width() // 2, canvas.height() // 2)
            return self.popup(menu, canvas.mapToGlobal(centre))
        tab = w.current
        if tab is None:
            return None
        menu = self.build_view_menu(tab, tab.selection[:1])
        view = tab.viewport
        centre = QPoint(view.width() // 2, view.height() // 2)
        return self.popup(menu, view.mapToGlobal(centre))


# Sketch actions shared with the context toolbar --------------------------------------------


def selected_entities(canvas: SketchCanvas) -> list[str]:
    """The selected sketch entities (no dimensions or relations)."""
    return [s for s in canvas.selection if s in canvas.edit.sketch.entities]


def relate(canvas: SketchCanvas, rtype: str) -> None:
    """Add a relation between the selected entities, as one sketch undo step."""
    from fdcad.ui.sketch_tools.edit import ordered_for

    sk = canvas.edit.sketch
    ids = ordered_for(sk, rtype, selected_entities(canvas))
    if rtype in ("length_ratio", "length_difference"):  # TR226: ask for the value
        value = ask_relation_value(canvas, rtype, ids)
        if value is not None:
            canvas.run(lambda: canvas.edit.relate_value(rtype, ids, value))
        return
    canvas.run(lambda: canvas.edit.relate(rtype, ids))


def ask_relation_value(canvas: SketchCanvas, rtype: str, ids: list[str]) -> float | None:
    """The ratio or difference to hold, starting at today's value (TR226). Tests
    replace this."""
    from PySide6.QtWidgets import QInputDialog

    from fdcad.core.sketch.solver import length_value

    ratio = rtype == "length_ratio"
    start = length_value(canvas.edit.sketch, rtype, ids)
    value, ok = QInputDialog.getDouble(
        canvas,
        strings.RELATION_NAMES[rtype],
        text.RELATION_VALUE_PROMPTS[rtype],
        round(start, 4),
        0.0001 if ratio else -1e6,
        1e6,
        4,
    )
    return value if ok else None


def ask_layer(canvas: SketchCanvas) -> tuple[str, str, str] | None:
    """Name, colour (#RRGGBB or "") and style of a new layer, or None (a test seam)."""
    from PySide6.QtWidgets import QColorDialog, QInputDialog

    name, ok = QInputDialog.getText(canvas, strings.LAYERS, strings.LAYER_NAME_PROMPT)
    if not ok or not name.strip():
        return None
    chosen = QColorDialog.getColor(parent=canvas, title=strings.LAYER_COLOUR)
    colour = chosen.name().upper() if chosen.isValid() else ""
    style, ok = QInputDialog.getItem(
        canvas,
        strings.LAYERS,
        strings.LAYER_STYLE_PROMPT,
        list(strings.LAYER_STYLES.values()),
        0,
        False,
    )
    key = next((k for k, v in strings.LAYER_STYLES.items() if v == style), "solid")
    return name.strip(), colour, key if ok else "solid"


def layers_menu(canvas: SketchCanvas, parent: QMenu, ids: list[str]) -> QMenu:
    """Layers: show or hide each layer, a new layer (with the picked curves), put the
    picked curves on a layer or on none, delete a layer (TR389, D982)."""
    from fdcad.core.sketch import layers as core

    sk = canvas.edit.sketch
    sub = QMenu(strings.LAYERS, parent)
    sub.setObjectName("sketch_layers")
    for layer in sk.layers:
        name = str(layer.get("name"))
        show = sub.addAction(strings.LAYER_SHOWN.format(name=name))
        show.setCheckable(True)
        show.setChecked(layer.get("visible") is not False)
        show.triggered.connect(lambda _c=False, n=name: toggle_layer(canvas, n))
    for layer in sk.layers:  # TR419 item 2: pick or lock a group together
        name = str(layer.get("name"))
        pick = sub.addAction(strings.LAYER_PICK.format(name=name))
        pick.triggered.connect(lambda _c=False, n=name: pick_layer(canvas, n))
        lock = sub.addAction(strings.LAYER_LOCK.format(name=name))
        lock.setCheckable(True)
        lock.setChecked(layer.get("locked") is True)
        lock.triggered.connect(lambda _c=False, n=name: lock_layer(canvas, n))
    if sk.layers:
        sub.addSeparator()
    new = sub.addAction(strings.LAYER_NEW)
    new.triggered.connect(lambda: new_layer(canvas, ids))
    if ids:
        for layer in sk.layers:
            name = str(layer.get("name"))
            move = sub.addAction(strings.LAYER_PUT_ON.format(name=name))
            move.triggered.connect(lambda _c=False, n=name: put_on_layer(canvas, ids, n))
        if any(i in sk.layer_of for i in ids):
            off = sub.addAction(strings.LAYER_TAKE_OFF)
            off.triggered.connect(lambda: put_on_layer(canvas, ids, None))
    for layer in sk.layers:
        name = str(layer.get("name"))
        gone = sub.addAction(strings.LAYER_DELETE.format(name=name))
        gone.triggered.connect(
            lambda _c=False, n=name: canvas.run(lambda: core.remove_layer(canvas.edit.sketch, n))
        )
    return sub


def toggle_layer(canvas: SketchCanvas, name: str) -> bool:
    """Show or hide one layer, as a sketch undo step (it is saved with the sketch)."""
    from fdcad.core.sketch.layers import find

    shown: list[bool] = []

    def change() -> None:
        layer = find(canvas.edit.sketch, name)
        if layer is not None:
            layer["visible"] = layer.get("visible") is False
            shown.append(bool(layer["visible"]))

    canvas.run(change)
    canvas.selection = [
        s
        for s in canvas.selection
        if not canvas.hidden_construction(canvas.edit.sketch.entities.get(s))
    ]
    return bool(shown and shown[0])


def pick_layer(canvas: SketchCanvas, name: str) -> list[str]:
    """Pick every curve on a layer (TR419 item 2)."""
    sk = canvas.edit.sketch
    found = [eid for eid, layer in sk.layer_of.items() if layer == name and eid in sk.entities]
    canvas.selection = found
    canvas.selection_changed.emit()
    canvas.update()
    return found


def lock_layer(canvas: SketchCanvas, name: str) -> bool:
    """Lock or unlock a layer: its curves cannot be dragged (TR419 item 2)."""
    from fdcad.core.sketch.layers import find

    locked: list[bool] = []

    def change() -> None:
        layer = find(canvas.edit.sketch, name)
        if layer is not None:
            layer["locked"] = layer.get("locked") is not True
            locked.append(bool(layer["locked"]))

    canvas.run(change)
    return bool(locked and locked[0])


def new_layer(canvas: SketchCanvas, ids: list[str]) -> bool:
    """Ask for a new layer and put the picked curves on it, one undo step."""
    from fdcad.core.sketch.layers import LayerError, add_layer, put_on

    asked = ask_layer(canvas)
    if asked is None:
        return False
    name, colour, style = asked
    problem: list[str] = []

    def change() -> None:
        try:
            add_layer(canvas.edit.sketch, name, colour, style)
            put_on(canvas.edit.sketch, ids, name)
        except LayerError as exc:
            problem.append(str(exc))

    depth = canvas.edit.undo_depth
    canvas.run(change)
    if problem:
        if canvas.edit.undo_depth > depth:
            canvas.edit.undo()
        canvas.status_message.emit(problem[0])
        return False
    canvas.status_message.emit(strings.LAYER_MADE.format(name=name))
    return True


def put_on_layer(canvas: SketchCanvas, ids: list[str], name: str | None) -> int:
    """Put the picked curves on a layer (None: on no layer), one undo step."""
    from fdcad.core.sketch.layers import put_on

    count: list[int] = []
    canvas.run(lambda: count.append(put_on(canvas.edit.sketch, ids, name)))
    return count[0] if count else 0


def sketch_display_menu(canvas: SketchCanvas, parent: QMenu) -> QMenu:
    """Show in Sketch: open end marks, each kind of relation tag, driving and reference
    dimensions, and the tag size, for every sketch this session (TR341, D964)."""
    kind = type(canvas)
    sub = QMenu(strings.SKETCH_DISPLAY, parent)
    sub.setObjectName("sketch_display")

    def check(text: str, on: bool, slot: Any) -> None:
        action = sub.addAction(text)
        action.setCheckable(True)
        action.setChecked(on)
        action.triggered.connect(slot)

    check(
        strings.SHOW_OPEN_ENDS, kind.mark_open_ends, lambda: toggle_class(canvas, "mark_open_ends")
    )
    check(  # TR238 (D987)
        strings.SHOW_CROSSINGS, kind.mark_crossings, lambda: toggle_class(canvas, "mark_crossings")
    )
    check(strings.SHOW_DRIVING, kind.show_driving, lambda: toggle_class(canvas, "show_driving"))
    check(
        strings.SHOW_REFERENCE, kind.show_reference, lambda: toggle_class(canvas, "show_reference")
    )
    sub.addSeparator()
    used = sorted({r.type for r in canvas.edit.sketch.relations})
    for rtype in used:
        label = strings.RELATION_NAMES.get(rtype, rtype.replace("_", " ").capitalize())
        check(
            strings.SHOW_TAGS_OF.format(kind=label),
            rtype not in kind.hidden_tags,
            lambda _c=False, r=rtype: toggle_tag_kind(canvas, r),
        )
    sub.addSeparator()
    for scale, label in strings.TAG_SIZES.items():
        check(
            label,
            abs(kind.tag_scale - scale) < 1e-9,
            lambda _c=False, s=scale: set_tag_scale(canvas, s),
        )
    sub.addSeparator()
    for scale, label in strings.LINE_WEIGHTS.items():  # TR341 (D1013)
        check(
            label,
            abs(kind.line_scale - scale) < 1e-9,
            lambda _c=False, s=scale: set_line_scale(canvas, s),
        )
    return sub


def toggle_tag_kind(canvas: SketchCanvas, rtype: str) -> bool:
    """Hide or show the tags of one relation kind in every sketch (TR341)."""
    kind = type(canvas)
    hidden = set(kind.hidden_tags)
    hidden.symmetric_difference_update({rtype})
    kind.hidden_tags = frozenset(hidden)
    canvas.update()
    return rtype not in hidden


def set_tag_scale(canvas: SketchCanvas, scale: float) -> None:
    """The relation tag text size as a factor of the caption size (TR341)."""
    type(canvas).tag_scale = scale
    canvas.update()


def set_line_scale(canvas: SketchCanvas, scale: float) -> None:
    """The sketch line weight and point size as a factor (TR341 item 5, D1013)."""
    type(canvas).line_scale = scale
    canvas.update()


def toggle_class(canvas: SketchCanvas, name: str) -> bool:
    """Switch a display toggle kept for every sketch this session (TR335)."""
    kind = type(canvas)
    setattr(kind, name, not getattr(kind, name))
    canvas.update()
    return bool(getattr(kind, name))


def toggle_formulas(canvas: SketchCanvas) -> bool:
    """Show or hide the formulas on dimension labels in every sketch (TR235, D921)."""
    kind = type(canvas)
    kind.show_formulas = not kind.show_formulas
    canvas.update()
    return kind.show_formulas


def explain_relation(canvas: SketchCanvas, item: str) -> str:
    """Say in the status bar what relation tag ``item`` holds (TR237, D920)."""
    from fdcad.core.sketch.explain import explain
    from fdcad.ui.sketch_tools.canvas import relation_index

    index = relation_index(item)
    relations = canvas.edit.sketch.relations
    if index is None or not 0 <= index < len(relations):
        return ""
    words = explain(canvas.edit.sketch, relations[index])
    canvas.status_message.emit(words)
    canvas.setToolTip(words)
    return words


def ask_slot_width(canvas: SketchCanvas) -> float | None:
    """The slot width in mm, or None when cancelled (a seam for tests)."""
    from PySide6.QtWidgets import QInputDialog

    value, ok = QInputDialog.getDouble(
        canvas, strings.SLOT_ALONG_TITLE, strings.SLOT_ALONG_WIDTH, 5.0, 0.001, 100000.0, 3
    )
    return value if ok else None


def slot_along(canvas: SketchCanvas, ids: list[str]) -> bool:
    """A slot of one width round the picked lines and arcs, one undo step (TR225)."""
    from fdcad.core.sketch.slot_along import SlotAlongError
    from fdcad.core.sketch.slot_along import slot_along as make

    width = ask_slot_width(canvas)
    if width is None:
        return False
    made: list[str] = []
    problem: list[str] = []

    def change() -> None:
        try:
            made.extend(make(canvas.edit.sketch, ids, width).curves)
        except SlotAlongError as exc:
            problem.append(str(exc))

    depth = canvas.edit.undo_depth
    canvas.run(change)
    if problem:
        if canvas.edit.undo_depth > depth:
            canvas.edit.undo()  # nothing was made: drop the empty step
        canvas.status_message.emit(problem[0])
        return False
    canvas.selection = list(made)
    canvas.status_message.emit(strings.SLOT_ALONG_DONE.format(count=len(made)))
    return True


def _has_axis_relations(canvas: SketchCanvas, ids: list[str]) -> bool:
    """True when a picked line has a Horizontal or Vertical relation of its own."""
    from fdcad.core.sketch.model import Line

    picked = set(ids)
    return any(
        r.type in ("horizontal", "vertical")
        and not r.off
        and len(r.entities) == 1
        and r.entities[0] in picked
        and isinstance(canvas.edit.sketch.entities.get(r.entities[0]), Line)
        for r in canvas.edit.sketch.relations
    )


def swap_axis(canvas: SketchCanvas, ids: list[str]) -> bool:
    """Turn the picked lines' Horizontal and Vertical relations into Parallel and
    Perpendicular, one undo step (TR124)."""
    from fdcad.core.sketch.swap_axis import SwapAxisError, swap_axis_relations

    found: list[int] = []
    problem: list[str] = []

    def change() -> None:
        try:
            found.append(len(swap_axis_relations(canvas.edit.sketch, ids).removed))
        except SwapAxisError as exc:
            problem.append(str(exc))

    depth = canvas.edit.undo_depth
    canvas.run(change)
    if problem:
        if canvas.edit.undo_depth > depth:
            canvas.edit.undo()  # nothing changed: drop the empty step
        canvas.status_message.emit(problem[0])
        return False
    canvas.status_message.emit(strings.SWAP_AXIS_DONE.format(count=found[0]))
    return True


def convex_hull(canvas: SketchCanvas, ids: list[str]) -> bool:
    """Add the convex outline around the picked curves as one sketch undo step (TR229)."""
    from fdcad.core.sketch.hull import HullError, add_hull, outline

    try:
        outline(canvas.edit.sketch, ids)
    except HullError as exc:
        canvas.status_message.emit(str(exc))
        return False
    made: list[str] = []
    canvas.run(lambda: made.extend(add_hull(canvas.edit.sketch, ids)))
    canvas.selection = list(made)
    canvas.status_message.emit(strings.HULL_DONE.format(count=len(made)))
    return True


def toggle_construction(canvas: SketchCanvas) -> None:
    """Switch the selected entities between normal and construction geometry (T2.7)."""
    ids = set(selected_entities(canvas))
    if ids:
        canvas.run(lambda: canvas.edit.toggle_construction(ids))


def dimension_selection(canvas: SketchCanvas) -> None:
    """Start Smart Dimension with up to two selected items already picked."""
    ids = selected_entities(canvas)[:2]
    canvas.set_tool("dimension")
    canvas.dim_picks = list(ids)
    canvas.update()


def select_chain(canvas: SketchCanvas, *eids: str) -> list[str]:
    """Select every curve joined end to end with ``eids`` (T9.8): the item right
    clicked, or every selected item when the menu was opened from the keyboard or
    off the items (audit D11 item 9, D2681)."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from fdcad.core.sketch.chain import chain_of

    sketch = canvas.edit.sketch
    found = {c for eid in eids for c in chain_of(sketch, eid)}
    chain = [i for i in sketch.entities if i in found]
    if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier:
        # Ctrl adds another chain to the selection (TR39).
        canvas.selection = [*canvas.selection, *(c for c in chain if c not in canvas.selection)]
    else:
        canvas.selection = chain
    canvas.selection_changed.emit()
    canvas.update()
    return list(canvas.selection)


def ask_grid(parent: Any, major: float, minor: int) -> tuple[float, int] | None:
    """The part's major grid spacing in mm and minor lines, or None (a seam for tests)."""
    from PySide6.QtWidgets import QInputDialog

    spacing, ok = QInputDialog.getDouble(
        parent, strings.GRID_SPACING, strings.GRID_SPACING_ASK, major, 0.0, 10000.0, 3
    )
    if not ok:
        return None
    count, ok = QInputDialog.getInt(
        parent, strings.GRID_SPACING, strings.GRID_MINOR_ASK, minor, 1, 20
    )
    return (spacing, count) if ok else None


def grid_spacing(window: Any, canvas: SketchCanvas) -> bool:
    """Set the part's sketch grid spacing (TR102, D860), one undo step."""
    from fdcad.ui.commands.document import SetSketchGrid

    tab = window.current
    if tab is None:
        return False
    old = tab.session.document.extra.get("sketch_grid") or {}
    found = ask_grid(canvas, float(old.get("major", 0.0)), int(old.get("minor", 1)))
    if found is None:
        return False
    tab.session.undo.push(SetSketchGrid(tab.session, found[0], found[1], strings.GRID_SPACING))
    canvas.grid_spacing = found[0] if found[0] > 0 else None
    canvas.grid_minor = found[1]
    canvas.update()
    return True


def ask_count(parent: Any, points: bool) -> int | None:
    """The number of pieces (or spaces between points), or None (a seam for tests)."""
    from PySide6.QtWidgets import QInputDialog

    count, ok = QInputDialog.getInt(
        parent,
        strings.SEGMENT,
        strings.SEGMENT_POINTS_ASK if points else strings.SEGMENT_ASK,
        4,
        2,
        100,
    )
    return count if ok else None


def segment_curve(canvas: SketchCanvas, cid: str, points: bool, status: Any = None) -> bool:
    """Split a line or arc into equal pieces, or put equally spaced points on it (TR103)."""
    from fdcad.core.sketch.ops.split import SplitError, segment

    count = ask_count(canvas, points)
    if count is None:
        return False
    say = getattr(status, "setText", None)
    try:
        canvas.run(lambda: segment(canvas.edit.sketch, cid, count, points))
    except SplitError as exc:
        canvas.edit.discard_checkpoint()
        if say is not None:
            say(str(exc))
        return False
    if say is not None:
        say(strings.SEGMENT_DONE.format(n=count))
    return True


def replace_entity(canvas: SketchCanvas, ids: list[str], keep: bool, status: Any = None) -> bool:
    """Replace the first picked curve by the second (TR104, D846), one sketch step."""
    import copy as _copy

    from fdcad.core.sketch.ops.replace_entity import ReplaceError
    from fdcad.core.sketch.ops.replace_entity import replace_entity as swap

    old, new = ids[0], ids[1]
    say = getattr(status, "setText", None)
    try:
        trial = swap(_copy.deepcopy(canvas.edit.sketch), old, new, keep)  # no half change
    except ReplaceError as exc:
        if say is not None:
            say(str(exc))
        return False
    canvas.run(lambda: swap(canvas.edit.sketch, old, new, keep))
    canvas.selection = [old]
    canvas.selection_changed.emit()
    if say is not None:
        note = strings.REPLACE_ENTITY_DONE
        if trial.dropped:
            note += " " + strings.REPLACE_ENTITY_DROPPED.format(which=", ".join(trial.dropped))
        say(note)
    return True


def ask_link_name(canvas: SketchCanvas, start: str) -> str | None:
    """The shared name for linked values, or None when cancelled (a seam for tests)."""
    from PySide6.QtWidgets import QInputDialog

    name, ok = QInputDialog.getText(
        canvas, strings.LINK_VALUES, strings.LINK_NAME_PROMPT, text=start
    )
    return name.strip() if ok and name.strip() else None


def link_values(canvas: SketchCanvas, dids: list[str]) -> bool:
    """Give the picked dimensions one shared name and value (TR193), one undo step."""
    from fdcad.core.sketch.links_values import LinkError, link

    taken = {d.link for d in canvas.edit.sketch.dimensions if d.link}
    n = 1
    while f"Link{n}" in taken:
        n += 1
    name = ask_link_name(canvas, f"Link{n}")
    if name is None:
        return False
    problem: list[str] = []

    def change() -> None:
        try:
            link(canvas.edit.sketch, dids, name)
        except LinkError as exc:
            problem.append(str(exc))

    depth = canvas.edit.undo_depth
    canvas.run(change)
    if problem:
        if canvas.edit.undo_depth > depth:
            canvas.edit.undo()  # nothing changed: drop the empty step
        canvas.status_message.emit(problem[0])
        return False
    canvas.status_message.emit(strings.LINKED.format(count=len(dids), name=name))
    return True


def unlink_values(canvas: SketchCanvas, dids: list[str]) -> int:
    """Take the picked dimensions out of their links; they keep their values."""
    from fdcad.core.sketch.links_values import unlink

    count: list[int] = []
    canvas.run(lambda: count.append(unlink(canvas.edit.sketch, dids)))
    canvas.status_message.emit(strings.UNLINKED.format(count=count[0] if count else 0))
    return count[0] if count else 0


def set_reference(canvas: SketchCanvas, dids: list[str], reference: bool) -> int:
    """Make the dimensions reference ones, or driving at their current sizes, as one
    undo step (TR111). Driving ones that would over define the sketch stay reference.
    Returns how many changed."""
    from fdcad.core.document.model import Param
    from fdcad.core.sketch.solver import measure

    changed: list[str] = []

    def change() -> None:
        for did in dids:
            dim = canvas._dimension(did)
            if dim is None or dim.driving != reference:
                continue
            if reference:
                dim.driving = False
                changed.append(did)
                continue
            value = measure(canvas.edit.sketch, dim)
            if dim.type == "angle":
                dim.param = Param(f"{math.degrees(value):.6g}deg", value)
            else:
                dim.param = Param(f"{value:.6g}mm", value)
            if canvas.edit.set_driving(did, True):
                changed.append(did)

    canvas.run(change)
    message = strings.MADE_REFERENCE if reference else strings.MADE_DRIVING
    canvas.status_message.emit(message.format(count=len(changed)))
    return len(changed)


def shake_sketch(canvas: SketchCanvas) -> list[str]:
    """Shake the sketch on a copy and pick what moved (TR372). The sketch is unchanged."""
    from fdcad.core.sketch.shake import shake

    moved = shake(canvas.edit.sketch)
    canvas.selection = list(moved)
    canvas.selection_changed.emit()
    canvas.update()
    if moved:
        canvas.status_message.emit(strings.SHAKE_MOVED.format(count=len(moved)))
    else:
        canvas.status_message.emit(strings.SHAKE_STILL)
    return moved


def toggle_lock(canvas: SketchCanvas) -> bool:
    """Lock All Points on or off for this sketch (TR372)."""
    canvas.points_locked = not canvas.points_locked
    canvas.status_message.emit(
        strings.POINTS_LOCKED if canvas.points_locked else strings.POINTS_UNLOCKED
    )
    return canvas.points_locked


def _block_items(menu: QMenu, canvas: SketchCanvas, ids: list[str]) -> None:
    """Make Block for loose curves; the block commands for a curve of a copy (TR34)."""
    from fdcad.core.sketch.blocks import block_of

    sk = canvas.edit.sketch
    found = block_of(sk, ids[0]) if ids else None
    if found is None:
        if not any(block_of(sk, i) for i in ids):
            add(menu, "make_block", strings.BLOCK_MAKE, lambda: block_command(canvas, "make", ids))
        return
    block, _index = found
    name = str(block["name"])
    add(
        menu,
        "insert_block",
        strings.BLOCK_INSERT.format(name=name),
        lambda: block_command(canvas, "insert", ids),
    )
    add(menu, "select_block", strings.BLOCK_SELECT, lambda: block_command(canvas, "select", ids))
    add(menu, "update_block", strings.BLOCK_UPDATE, lambda: block_command(canvas, "update", ids))
    add(menu, "explode_block", strings.BLOCK_EXPLODE, lambda: block_command(canvas, "explode", ids))


def block_command(canvas: SketchCanvas, what: str, ids: list[str]) -> bool:
    """Run a block command on the picked curves, one sketch undo step (TR34, D1717)."""
    from fdcad.core.sketch import blocks as bk

    sk = canvas.edit.sketch
    found = bk.block_of(sk, ids[0]) if ids else None
    if what == "select":
        if found is None:
            return False
        block, index = found
        canvas.selection = [e for e in block["copies"][index]["map"].values() if e in sk.entities]
        canvas.selection_changed.emit()
        canvas.update()
        return True
    note = ""

    def change() -> None:
        nonlocal note
        if what == "make":
            block = bk.make_block(canvas.edit.sketch, ids)
            note = strings.BLOCK_MADE.format(name=block["name"])
            return
        assert found is not None
        block, index = found
        if what == "insert":
            ox, oy, turn = bk.copy_frame(canvas.edit.sketch, block, index)
            mapping = bk.insert_copy(canvas.edit.sketch, block, (ox + 10.0, oy - 10.0, turn))
            canvas.selection = [e for e in mapping.values() if e in canvas.edit.sketch.entities]
            note = strings.BLOCK_INSERTED.format(name=block["name"])
        elif what == "update":
            count = bk.update_from_copy(canvas.edit.sketch, block, index)
            note = strings.BLOCK_UPDATED.format(name=block["name"], count=count)
        elif what == "explode":
            bk.explode_copy(canvas.edit.sketch, block, index)
            note = strings.BLOCK_EXPLODED

    canvas.edit.checkpoint()
    try:
        change()
    except bk.BlockError as exc:
        canvas.edit.discard_checkpoint()
        canvas.status_message.emit(str(exc))
        return False
    canvas.changed()
    canvas.status_message.emit(note)
    return True


def toggle_free_drag(canvas: SketchCanvas) -> bool:
    """Drag Without Solving on or off for the open sketch (TR112 item 1, D1716)."""
    canvas.edit.free_drag = not canvas.edit.free_drag
    return canvas.edit.free_drag


def toggle_detach(canvas: SketchCanvas) -> bool:
    """Detach Segment on Drag on or off for the open sketch (TR112 item 3, D1716)."""
    canvas.detach_drag = not canvas.detach_drag
    return canvas.detach_drag


def toggle_reference_mode(canvas: SketchCanvas) -> bool:
    """New dimensions are reference ones while this is on (TR111), every sketch."""
    kind = type(canvas)
    kind.reference_mode = not kind.reference_mode
    canvas.status_message.emit(
        strings.REFERENCE_MODE_ON if kind.reference_mode else strings.REFERENCE_MODE_OFF
    )
    return kind.reference_mode


def toggle_reference(canvas: SketchCanvas, did: str) -> None:
    """Make a dimension a reference (driven) one, or driving again at its current size."""
    from fdcad.core.document.model import Param
    from fdcad.core.sketch.solver import measure

    def change() -> None:
        dim = canvas._dimension(did)
        if dim is None:
            return
        if dim.driving:
            dim.driving = False
            return
        value = measure(canvas.edit.sketch, dim)
        if dim.type == "angle":
            import math

            dim.param = Param(f"{math.degrees(value):.6g}deg", value)
        else:
            dim.param = Param(f"{value:.6g}mm", value)
        dim.driving = True

    canvas.run(change)


def face_axis(face: Any) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
    """Location and direction of a cylindrical or conical face's axis, else None (T14.4.1)."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder
    from OCP.TopoDS import TopoDS

    try:
        surface = BRepAdaptor_Surface(TopoDS.Face(face))
        kind = surface.GetType()
        if kind == GeomAbs_Cylinder:
            ax = surface.Cylinder().Axis()
        elif kind == GeomAbs_Cone:
            ax = surface.Cone().Axis()
        else:
            return None
    except Exception:  # a broken face is simply not round
        return None
    p, d = ax.Location(), ax.Direction()
    return (p.X(), p.Y(), p.Z()), (d.X(), d.Y(), d.Z())


def make_vertex(point: tuple[float, float, float]) -> Any:
    """A vertex at ``point`` (tiny kernel work, D75)."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.gp import gp_Pnt

    return BRepBuilderAPI_MakeVertex(gp_Pnt(*point)).Vertex()


def _cursor_in(tab: DocumentTab) -> QPointF | None:
    """The mouse position in ``tab``'s 3D view, or None when the cursor is outside it."""
    from PySide6.QtGui import QCursor

    view = getattr(tab, "viewport", None)
    if view is None:
        return None
    local = view.mapFromGlobal(QCursor.pos())
    if not view.rect().contains(local):
        return None
    return QPointF(local)


def sketch_normal_to(window: Any, tab: DocumentTab, edge: Any, near: Any = None) -> str | None:
    """Add a plane square to ``edge`` at its end nearer ``near`` and start a sketch on it
    once it is built (TR51, D898). Returns the plane's feature id."""
    from OCP.BRep import BRep_Tool
    from OCP.TopExp import TopExp
    from OCP.TopoDS import TopoDS

    from fdcad.core.document.model import Feature
    from fdcad.core.features.names import default_name
    from fdcad.core.naming.select import reference_for
    from fdcad.ui.commands.document import AddFeature

    report = tab.session.report
    if report is None or report.body is None:
        return None
    body = report.body
    e = TopoDS.Edge(edge)
    ends = [TopExp.FirstVertex_s(e), TopExp.LastVertex_s(e)]

    def gap(v: Any) -> float:
        if near is None:
            return 0.0
        p = BRep_Tool.Pnt_s(v)
        return math.dist((p.X(), p.Y(), p.Z()), tuple(near))

    vertex = min(ends, key=gap)
    edge_ref, vertex_ref = reference_for(body, e), reference_for(body, vertex)
    if edge_ref is None:
        window.status.setText(strings.SKETCH_NORMAL_NO_REF)
        return None
    doc = tab.session.document
    refs: dict[str, Any] = {"first": edge_ref}
    if vertex_ref is not None:
        refs["second"] = vertex_ref
    fid = doc.new_feature_id()
    plane = Feature(
        fid,
        "ref_plane",
        default_name(doc, "ref_plane"),
        params={"method": "normal_to_curve"},
        refs=refs,
    )

    def start(_report: object = None) -> None:
        with contextlib.suppress(RuntimeError, TypeError):
            tab.session.rebuilt.disconnect(start)
        if window.sketch_mode is not None and any(f.id == fid for f in doc.features):
            window.sketch_mode.start(plane_id=fid)

    tab.session.rebuilt.connect(start)
    tab.session.undo.push(AddFeature(tab.session, plane))
    return fid


def _keep_side(canvas: SketchCanvas) -> None:
    """Keep This Side (TR338, D1302): undo the jump and lock the flipped items."""
    if canvas.edit.keep_this_side():
        canvas.changed()
        canvas.status_message.emit(strings.SIDE_KEPT)


def _unlock(canvas: SketchCanvas) -> None:
    """Remove Side Locks (TR338, D1302)."""
    if canvas.edit.remove_side_locks():
        canvas.changed()


def _handle_items(menu: QMenu, canvas: SketchCanvas, pid: str) -> None:
    """Pin Handle or Reset Handle, and Add Handle Line, on a spline point or its handle
    (TR43, D1305)."""
    from fdcad.core.sketch import handles as hd

    sk = canvas.edit.sketch
    if hd.handle_of(sk, pid) is None:
        return
    if hd.is_pinned(sk, pid):
        add(
            menu,
            "reset_handle",
            strings.RESET_HANDLE,
            lambda: canvas.run(lambda: hd.reset_handle(canvas.edit.sketch, pid)),
        )
    else:
        add(
            menu,
            "pin_handle",
            strings.PIN_HANDLE,
            lambda: canvas.run(lambda: hd.pin_handle(canvas.edit.sketch, pid)),
        )
    add(
        menu,
        "handle_line",
        strings.HANDLE_LINE,
        lambda: canvas.run(lambda: hd.handle_line(canvas.edit.sketch, pid)),
    )


def _is_chain(canvas: SketchCanvas, ids: list[str]) -> bool:
    """True when ``ids`` are two or more lines and arcs joined end to end (TR45)."""
    from fdcad.core.sketch.model import Arc, Line
    from fdcad.core.sketch.spline_edit import chain_polyline

    sk = canvas.edit.sketch
    if len(ids) < 2 or not all(isinstance(sk.entities.get(i), Line | Arc) for i in ids):
        return False
    try:
        chain_polyline(sk, ids)
    except ValueError as exc:
        return "closed" in str(exc)  # a closed chain has a length too
    return True


def _path_length(canvas: SketchCanvas, ids: list[str]) -> None:
    """Add a Path Length dimension on the chain ``ids`` at its current length (TR45)."""
    canvas.run(lambda: canvas.edit.add_dimension("path_length", list(ids), None))


def _chamfer(canvas: SketchCanvas, lid: str, mode: str) -> None:
    """Chamfer Dimension: length and angle, or two lengths (TR45, D1307)."""
    from fdcad.ui.sketch_tools.datum_dimensions import chamfer_dimensions

    try:
        canvas.run(lambda: chamfer_dimensions(canvas.edit, lid, mode))
    except ValueError as exc:
        canvas.edit.discard_checkpoint()
        canvas.changed()
        canvas.status_message.emit(str(exc))


def set_limit(canvas: SketchCanvas, did: str, key: str) -> None:
    """Make a dimension exact, a minimum or a maximum (TR342, D1311)."""

    def change() -> None:
        dim = canvas._dimension(did)
        if dim is not None:
            dim.limit = key or None

    canvas.run(change)


def _angle_to_axis(canvas: SketchCanvas, lid: str, axis: str) -> None:
    """An angle dimension from a line to a horizontal or vertical construction line
    through its first end (TR111 item 2, D1312)."""

    def change() -> None:
        from fdcad.core.sketch.model import Line

        edit = canvas.edit
        sk = edit.sketch
        line = sk.entities[lid]
        assert isinstance(line, Line)
        x, y = sk.xy(line.p1)
        reach = max(math.dist(sk.xy(line.p1), sk.xy(line.p2)) / 2, 1.0)
        end = (x + reach, y) if axis == "horizontal" else (x, y + reach)
        ref = sk.add_line(x, y, end[0], end[1], construction=True)
        guide = sk.entities[ref]
        assert isinstance(guide, Line)
        sk.relate("coincident", guide.p1, line.p1)
        sk.relate(axis, ref)
        dim = edit.add_dimension("angle", [ref, lid], None)
        if edit.over_defines(dim.id):
            dim.driving = False

    canvas.run(change)


def _relax(canvas: SketchCanvas, sid: str) -> None:
    """Relax Spline: even handles with the ends fixed (TR115, D1314)."""
    from fdcad.core.sketch.spline_edit import relax

    canvas.run(lambda: relax(canvas.edit.sketch, sid))
