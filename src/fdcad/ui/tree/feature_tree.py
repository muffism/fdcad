"""Feature tree with rollback bar and actions (PLAN section 8 items 2 and 12).

Every action goes through an undoable command (CLAUDE.md rule 3).
"""

from __future__ import annotations

import sys
from typing import Any

from PySide6.QtCore import QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QDragMoveEvent, QDropEvent, QKeyEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QInputDialog,
    QMenu,
    QMessageBox,
    QTreeWidget,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
    QWidget,
)

from fdcad.core.document import dependencies, rollback
from fdcad.core.document.model import RIGHT_PLANE_ID, Feature
from fdcad.core.document.names import rename_problem
from fdcad.core.features.base import FeatureResult, FeatureState
from fdcad.core.sketch.solver import SketchStatus
from fdcad.ui import strings
from fdcad.ui import strings_extra as text
from fdcad.ui.commands.document import (
    DeleteFeature,
    MoveFeature,
    RenameFeature,
    ReplaceFeature,
    SetRollback,
    SetSuppressed,
    SetVisibility,
)
from fdcad.ui.main_window import visibility
from fdcad.ui.session import DocumentSession
from fdcad.ui.themes.theme import chrome, palette
from fdcad.ui.tree import problems
from fdcad.ui.tree.row_icons import ROW_ICON_SIZE, icon_name, row_icon

FID_ROLE = Qt.ItemDataRole.UserRole
ROLLBACK_MARK = "__rollback__"
PART_MARK = "__part__"
#: Body rows hold their index in the Solid Bodies order; the folder holds -1 (D410).
BODY_ROLE = Qt.ItemDataRole.UserRole + 7
#: Item data role holding a folder row's name (TR23).
FOLDER_ROLE = Qt.ItemDataRole.UserRole + 41
#: Item data role holding a feature row's comment (TR23).
COMMENT_ROLE = Qt.ItemDataRole.UserRole + 42
#: Item data role holding a body folder row's name (TR153, D2106).
BODY_FOLDER_ROLE = Qt.ItemDataRole.UserRole + 43
_BUILT_IN = {"f1", "f2", "f3", RIGHT_PLANE_ID}


def display_order(features: list[Feature]) -> list[Feature]:
    """Rows in tree order: the default planes, Origin, then the rest in document order."""
    planes = [f for f in features if f.id in _BUILT_IN and f.type == "plane"]
    others = [f for f in features if f.id in _BUILT_IN and f.type != "plane"]
    rest = [f for f in features if f.id not in _BUILT_IN]
    return [*planes, *others, *rest]


#: Tree prefixes for sketches that are not fully defined (T1.4.3).
UNDER_PREFIX = "(-) "
OVER_PREFIX = "(+) "


def sketch_prefix(result: FeatureResult | None) -> str:
    """ "(-) " for an under defined sketch, "(+) " for an over defined one, else ""."""
    out = result.sketch if result is not None else None
    if out is None:
        return ""
    if out.solve.status is SketchStatus.UNDER:
        return UNDER_PREFIX
    if out.solve.status is SketchStatus.OVER:
        return OVER_PREFIX
    return ""


def strip_prefix(text: str) -> str:
    """A row's text without its sketch state prefix."""
    for prefix in (UNDER_PREFIX, OVER_PREFIX):
        if text.startswith(prefix):
            return text[len(prefix) :]
    return text


def children_of(features: list[Feature], fid: str) -> list[Feature]:
    """Features that reference ``fid`` (parent and child view, delete warning)."""
    return [f for f in features if f.id != fid and fid in dependencies.referenced_ids(f.refs)]


#: "No previous rollback position yet" (None means the end of the tree).
_NOWHERE = object()


def strings_built_in() -> str:
    """Reason given when a row cannot be moved at all."""
    return "The origin and default planes cannot move. Drag a feature instead."


def own_sketch(features: list[Feature], fid: str) -> str | None:
    """The sketch only ``fid`` uses, or None (shared sketches are always kept, T5.3.5)."""
    feature = next((f for f in features if f.id == fid), None)
    if feature is None or feature.type == "sketch":
        return None
    sid = visibility.sketch_of(feature)
    if sid is None or not any(f.id == sid for f in features):
        return None
    users = [f for f in features if f.id != sid and visibility.sketch_of(f) == sid]
    return sid if [u.id for u in users] == [fid] else None


class FeatureTree(QTreeWidget):
    """The list of features of the active part."""

    edit_requested = Signal(str)  # feature id
    library_requested = Signal(str)  # feature id: Save as Library Feature (TR72)
    sketch_requested = Signal(str)  # plane feature id
    edit_plane_requested = Signal(str)  # sketch feature id (T14.2)
    replace_requested = Signal(str)  # import feature id: Replace From File (TR11)
    heal_requested = Signal(str)  # STEP or IGES import feature id: Heal (TR31)
    pick_requested = Signal(str)  # STEP or IGES import feature id: Pick Bodies (TR302)
    repair_requested = Signal(str)  # a feature with problems: Repair Lost References (TR125)
    material_requested = Signal()  # the Material row (TR78)
    refreshed = Signal()  # the rows were made again (the filter box, TR95)
    visibility_changed = Signal()  # a sketch was shown or hidden
    normal_to_requested = Signal(str)  # plane, sketch or feature id (T9.5)
    #: A body command from the Solid Bodies folder: "hide", "show", "isolate" or
    #: "show_all", with the body index (-1 for the folder) (D410).
    body_requested = Signal(str, int)
    #: Appearance for a solid feature id, or "" for the part (owner request: colours easy to find).
    appearance_requested = Signal(str)
    #: Why a drag or a rename was refused, for the status bar.
    message_shown = Signal(str)
    #: A Section Planes row (TR213, D2501): "pick", "edit" or "off", with the plane index.
    section_requested = Signal(str, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("feature_tree")
        self.setHeaderHidden(True)
        self.setRootIsDecorated(True)  # a feature expands to show its sketch (L4, W5.3)
        self.setIconSize(QSize(ROW_ICON_SIZE, ROW_ICON_SIZE))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)
        self.itemDoubleClicked.connect(self._double_clicked)
        self.itemChanged.connect(self._renamed)
        # A double click edits the feature, so it must not also open the name editor;
        # Rename in the menu and the platform edit key (F2) still rename.
        self.setEditTriggers(QAbstractItemView.EditTrigger.EditKeyPressed)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.session: DocumentSession | None = None
        self._filling = False
        self.message = ""
        #: Flat tree view (Ctrl+T): every feature on its own row, no nesting.
        self.flat = False
        #: Select the rollback bar row after the next refresh (arrow keys keep it).
        self._bar_wanted = False
        self._refresh_queued = False
        self.setDropIndicatorShown(True)
        # Ctrl and Shift click pick several rows, for Add to New Folder (TR23).
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        #: Folders the user closed (view state, kept while FDCAD runs).
        self.closed_folders: set[str] = set()
        #: Window actions offered on the part row's menu (Show All Dimensions, TR32).
        self.part_actions: list[QAction] = []
        self.itemCollapsed.connect(self._folder_toggled)
        self.itemExpanded.connect(self._folder_toggled)
        self.itemClicked.connect(self._clicked)
        #: Parent and child arrows for the hovered or picked feature (TR96, D942). Off
        #: by default; the part row's menu turns them on. A view state.
        self.relation_arrows = False
        self._arrow_hover: str | None = None
        self.setMouseTracking(True)
        self.itemEntered.connect(self._hover_arrows)
        #: Names of the section planes shown in the Section Planes folder (TR213).
        self.section_planes: list[str] = []

    # Parent and child arrows (TR96 item 1) --------------------------------------------

    def set_relation_arrows(self, on: bool) -> None:
        """Draw arrows to the parents and children of the hovered or picked feature."""
        self.relation_arrows = on
        self.viewport().update()

    def _hover_arrows(self, item: QTreeWidgetItem, _column: int) -> None:
        if not self.relation_arrows:
            return
        fid = item.data(0, FID_ROLE)
        self._arrow_hover = fid if isinstance(fid, str) else None
        self.viewport().update()

    def leaveEvent(self, event: Any) -> None:  # noqa: N802
        """The arrows go back to the picked feature when the mouse leaves."""
        if self._arrow_hover is not None:
            self._arrow_hover = None
            self.viewport().update()
        super().leaveEvent(event)

    def arrow_rows(
        self,
    ) -> tuple[QTreeWidgetItem, list[QTreeWidgetItem], list[QTreeWidgetItem]] | None:
        """The feature's row, then the rows its parents and children show in. A row
        inside a closed folder or feature is shown by that closed row."""
        session = self.session
        if session is None or not self.relation_arrows:
            return None
        fid = self._arrow_hover
        item = self.currentItem()
        if fid is None and item is not None:
            current = item.data(0, FID_ROLE)
            fid = current if isinstance(current, str) else None
        if fid is None or not self._exists(fid):
            return None
        source = self.item_for(fid)
        if source is None:
            return None
        doc = session.document

        def rows(found: list[Feature]) -> list[QTreeWidgetItem]:
            out: list[QTreeWidgetItem] = []
            for feature in found:
                item = self.item_for(feature.id)
                if item is None:
                    continue
                shown = _shown_row(item)
                if shown is not source and shown not in out:
                    out.append(shown)
            return out

        return (
            _shown_row(source),
            rows(dependencies.parents_of(doc, fid)),
            rows(dependencies.children_of(doc, fid)),
        )

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        """The rows, then the parent and child arrows over them (TR96)."""
        super().paintEvent(event)
        found = self.arrow_rows() if self.relation_arrows else None
        if found is None:
            return
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QPainter, QPen, QPolygonF

        source, parents, children = found
        colours = palette()
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        start = self.visualItemRect(source)
        for n, (targets, colour) in enumerate(
            ((parents, colours.accent), (children, colours.selection))
        ):
            pen = QPen(QColor(colour))
            pen.setWidthF(1.5)
            painter.setPen(pen)
            painter.setBrush(QColor(colour))
            for i, target in enumerate(targets):
                rect = self.visualItemRect(target)
                if rect.isNull():
                    continue
                x = 3.0 + 4.0 * n + 8.0 * i  # parents on the left, children beside them
                y0, y1 = start.center().y(), rect.center().y()
                tip = QPointF(rect.left() + 2.0, y1)
                path = [QPointF(start.left() + 2.0, y0), QPointF(x, y0), QPointF(x, y1), tip]
                painter.drawPolyline(QPolygonF(path))
                head = QPolygonF(
                    [tip, QPointF(tip.x() - 5.0, y1 - 3.0), QPointF(tip.x() - 5.0, y1 + 3.0)]
                )
                painter.drawPolygon(head)
        painter.end()

    def set_session(self, session: DocumentSession | None) -> None:
        """Show ``session``'s features, or nothing."""
        if self.session is not None:
            self.session.rebuilt.disconnect(self.refresh)
            self.session.undo.indexChanged.disconnect(self._refresh_soon)
        self.session = session
        if session is not None:
            session.rebuilt.connect(self.refresh)
            # Rows follow every change at once, not only when the rebuild ends, so a
            # row of a deleted or undone feature never lingers while the part rebuilds.
            session.undo.indexChanged.connect(self._refresh_soon)
        self.refresh()

    def _refresh_soon(self, *_args: object) -> None:
        """Refill the rows on the next turn of the event loop (never inside a row's
        own signal, such as the rename that changed the document)."""
        if not self._refresh_queued:
            self._refresh_queued = True
            QTimer.singleShot(0, self, self._queued_refresh)

    def _queued_refresh(self) -> None:
        self._refresh_queued = False
        self.refresh()

    def _exists(self, fid: object) -> bool:
        """True when ``fid`` is a feature of the open part (rows can be a step behind)."""
        session = self.session
        return session is not None and any(f.id == fid for f in session.document.features)

    def set_flat(self, flat: bool) -> None:
        """Show features in one flat list, or nest sketches under their features again."""
        self.flat = flat
        self.setRootIsDecorated(not flat)
        self.refresh()

    def selected_id(self) -> str | None:
        """Id of the selected feature, or None (the part name and the rollback bar
        are rows but not features)."""
        item = self.currentItem()
        fid = item.data(0, FID_ROLE) if item is not None else None
        return fid if isinstance(fid, str) and fid not in (ROLLBACK_MARK, PART_MARK) else None

    def select(self, fid: str) -> None:
        """Select feature ``fid``, now or after the next refresh adds it."""
        # Remember the id only while its row is missing: once selected, a later
        # click on another row must win over it at the next refresh.
        self._wanted: str | None = fid
        for item in self.all_items():
            if item.data(0, FID_ROLE) == fid:
                self.setCurrentItem(item)
                self._wanted = None
                break

    def all_items(self) -> list[QTreeWidgetItem]:
        """Every row, nested ones included, top to bottom."""
        out: list[QTreeWidgetItem] = []
        it = QTreeWidgetItemIterator(self)
        while it.value() is not None:
            out.append(it.value())
            it += 1
        return out

    def selected_body(self) -> int | None:
        """Index of the selected body row in the Solid Bodies folder, or None."""
        item = self.currentItem()
        index = item.data(0, BODY_ROLE) if item is not None else None
        return index if isinstance(index, int) and index >= 0 else None

    def hidden_bodies(self) -> set[int]:
        """Indices of the bodies hidden on purpose (D410)."""
        from fdcad.core.body_visibility import hidden_indices, hidden_names

        session = self.session
        report = session.report if session is not None else None
        if session is None or report is None:
            return set()
        names = hidden_names(session.document)
        return set(hidden_indices(report.body, names)) if names else set()

    def see_through_bodies(self) -> set[int]:
        """Indices of the bodies drawn see through on their own (TR21)."""
        from fdcad.core.body_visibility import hidden_indices, see_through_names

        session = self.session
        report = session.report if session is not None else None
        if session is None or report is None:
            return set()
        names = see_through_names(session.document)
        return set(hidden_indices(report.body, names)) if names else set()

    def locked_bodies(self) -> set[int]:
        """Indices of the locked bodies (TR269)."""
        from fdcad.core.body_visibility import hidden_indices, locked_names

        session = self.session
        report = session.report if session is not None else None
        if session is None or report is None:
            return set()
        names = locked_names(session.document)
        return set(hidden_indices(report.body, names)) if names else set()

    def _body_menu(self, index: int) -> QMenu:
        """Menu of the Solid Bodies folder (index -1) or of one body row (D410)."""
        from fdcad.ui import strings_phase3 as text3

        menu = QMenu(self)
        if index >= 0:
            hidden = index in self.hidden_bodies()
            self._add(
                menu,
                text3.SHOW_BODY if hidden else text3.HIDE_BODY,
                lambda: self.body_requested.emit("show" if hidden else "hide", index),
            )
            if not hidden:
                clear = index in self.see_through_bodies()  # TR21
                self._add(
                    menu,
                    text3.SOLID_BODY if clear else text3.SEE_THROUGH_BODY,
                    lambda: self.body_requested.emit("solid" if clear else "see_through", index),
                )
                self._add(menu, text3.ISOLATE, lambda: self.body_requested.emit("isolate", index))
                locked = index in self.locked_bodies()  # TR269
                self._add(
                    menu,
                    text3.UNLOCK_BODY if locked else text3.LOCK_BODY,
                    lambda: self.body_requested.emit("unlock" if locked else "lock", index),
                )
                if not locked:
                    self._add(
                        menu,
                        text3.TRANSFORM_HANDLES,
                        lambda: self.body_requested.emit("transform", index),
                    )
            self._add(  # TR183 (D1201)
                menu, strings.RENAME_BODY, lambda: self.body_requested.emit("rename", index)
            )
            if not hidden:
                self._display_menu(menu, index)  # TR216
            self._role_menu(menu, index)
            from fdcad.ui import strings_print as text_print

            self._add(  # TR383 (D1207)
                menu,
                text_print.BODY_SETTINGS,
                lambda: self.body_requested.emit("settings", index),
            )
            self._add(  # TR153 (D972)
                menu, strings.BODY_HISTORY, lambda: self.body_requested.emit("history", index)
            )
            from fdcad.ui import strings_config as text_config

            self._add(  # TR153 (D2106)
                menu,
                text_config.BODY_FOLDER_MOVE,
                lambda: self.body_requested.emit("folder_move", index),
            )
        self._add(menu, text3.SHOW_ALL_BODIES, lambda: self.body_requested.emit("show_all", -1))
        return menu

    def _body_folder_menu(self, folder: str) -> QMenu:
        """Menu of a body folder row (TR153, D2106): commands for all its bodies."""
        from fdcad.ui import strings_config as text_config

        menu = QMenu(self)
        for op, label in text_config.BODY_FOLDER_ACTIONS.items():
            self._add(
                menu, label, lambda op=op: self.body_requested.emit(f"folder:{op}:{folder}", -1)
            )
        return menu

    def _display_menu(self, menu: QMenu, index: int) -> None:
        """Display Mode and Transparency of one body (TR216, D1606)."""
        from fdcad.core.body_modes import body_modes
        from fdcad.ui.main_window import body_modes_ui as bm

        session = self.session
        report = session.report if session is not None else None
        modes = body_modes(session.document, report.body) if session and report else []
        current = modes[index][0] if 0 <= index < len(modes) else ""
        sub = menu.addMenu(bm.DISPLAY_MODE)
        sub.menuAction().setObjectName("body_display_mode")
        for mode, label in bm.MODE_LABELS.items():
            action = sub.addAction(label)
            action.setCheckable(True)
            action.setChecked(mode == current)
            action.triggered.connect(
                lambda _c=False, m=mode: self.body_requested.emit(f"display:{m}", index)
            )
        self._add(menu, bm.TRANSPARENCY, lambda: self.body_requested.emit("transparency", index))

    def _role_menu(self, menu: QMenu, index: int) -> None:
        """Print Role: Part, Modifier, Negative Volume, Support Enforcer or Blocker (TR382)."""
        from fdcad.core.printing.body_roles import ROLES
        from fdcad.ui import strings_phase3 as text3

        roles = self.body_roles()
        current = roles[index] if 0 <= index < len(roles) else "part"
        sub = menu.addMenu(text3.PRINT_ROLE)
        sub.setToolTipsVisible(True)
        sub.menuAction().setObjectName("print_role")
        for role in ROLES:
            action = sub.addAction(text3.PRINT_ROLES[role])
            action.setCheckable(True)
            action.setChecked(role == current)
            action.setToolTip(text3.PRINT_ROLE_TIP)
            action.triggered.connect(
                lambda _c=False, r=role: self.body_requested.emit(f"role:{r}", index)
            )

    def body_roles(self) -> list[str]:
        """The print role of every body (TR382)."""
        from fdcad.core.printing.body_roles import roles_of

        session = self.session
        report = session.report if session is not None else None
        if session is None or report is None:
            return []
        from fdcad.core.body_titles import report_marks

        return roles_of(session.document, report.body, report_marks(report, "body_roles"))

    @property
    def filling(self) -> bool:
        """True while ``refresh`` rebuilds the rows (row changes are not the user's)."""
        return self._filling

    def item_for(self, fid: str) -> QTreeWidgetItem | None:
        """The row of feature ``fid``, or None."""
        return next((i for i in self.all_items() if i.data(0, FID_ROLE) == fid), None)

    def refresh(self, *_args: object) -> None:
        """Rebuild the rows from the document and the last rebuild report."""
        self._filling = True
        selected = getattr(self, "_wanted", None) or self.selected_id()
        current = self.currentItem()
        on_bar = current is not None and current.data(0, FID_ROLE) == ROLLBACK_MARK
        keep_bar = self._bar_wanted or (on_bar and selected is None)
        self._wanted = None
        self.clear()
        session = self.session
        if session is None:
            self._filling = False
            self.refreshed.emit()  # no rows is news too: the filter shows its empty state
            return
        doc = session.document
        report = session.report
        colors = palette()
        # Part name, Solid Bodies folder, the planes, Origin, then features (L4).
        part = QTreeWidgetItem([session.title.rstrip("*")])
        part.setFlags(Qt.ItemFlag.ItemIsEnabled)
        part.setData(0, FID_ROLE, PART_MARK)
        worst = problems.worst_state(report) if report is not None else None
        part_mark = {"error": colors.state_error, "warning": colors.state_warning}.get(worst or "")
        part.setIcon(0, row_icon("tree.part", part_mark, mark=worst or "error"))
        if part_mark is not None:
            part.setToolTip(0, text.PART_PROBLEMS_TIP)
        self.addTopLevelItem(part)
        count = report.body_count if report is not None else 0
        folder = QTreeWidgetItem([strings.BODIES.format(count=count)])
        folder.setFlags(Qt.ItemFlag.ItemIsEnabled)
        folder.setData(0, BODY_ROLE, -1)
        folder.setIcon(0, row_icon("tree.solid_bodies"))
        if count > 1:
            folder.setForeground(0, QBrush(QColor(colors.state_warning)))
        hidden_bodies = self.hidden_bodies()
        roles = self.body_roles() if count > 1 else []
        # Identical bodies sit in a folder of their own with a count (TR308, D958).
        group_of: dict[int, int] = {}
        groups = [
            g for g in getattr(report, "body_groups", None) or [] if all(0 <= i < count for i in g)
        ]
        for k, group in enumerate(groups):
            for i in group:
                group_of[i] = k
        subs: dict[int, QTreeWidgetItem] = {}
        from fdcad.core.body_folders import folders_of

        own_folder = folders_of(doc, report.body if report is not None else None)
        user_rows: dict[str, QTreeWidgetItem] = {}

        def holder(i: int) -> QTreeWidgetItem:
            # A folder of the user's comes first (TR153, D2106), made at its first body.
            name = own_folder[i] if i < len(own_folder) else None
            if name:
                if name not in user_rows:
                    row = QTreeWidgetItem([name])
                    row.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    row.setData(0, BODY_FOLDER_ROLE, name)
                    row.setIcon(0, row_icon("tree.folder"))
                    folder.addChild(row)
                    user_rows[name] = row
                return user_rows[name]
            # The row a body goes under: its group's folder, made at its first body.
            k = group_of.get(i)
            if k is None:
                return folder
            if k not in subs:
                sub = QTreeWidgetItem([strings.IDENTICAL_BODIES.format(count=len(groups[k]))])
                sub.setFlags(Qt.ItemFlag.ItemIsEnabled)
                sub.setData(0, BODY_ROLE, -1)
                sub.setIcon(0, row_icon("tree.solid_bodies"))
                sub.setToolTip(0, strings.IDENTICAL_BODIES_TIP)
                folder.addChild(sub)
                subs[k] = sub
            return subs[k]

        from fdcad.core.body_titles import stored, titles_of

        body = report.body if report is not None else None
        from fdcad.core.body_titles import report_marks

        given = report_marks(report, "body_titles")  # TR386 (D1205)
        titles = titles_of(doc, body, given) if stored(doc) or given else []  # TR183
        for i in range(count):
            own = titles[i] if i < len(titles) else None
            label = own or strings.BODY.format(index=i + 1)
            if i < len(roles) and roles[i] != "part":  # TR382
                from fdcad.ui import strings_phase3 as text3

                label = text3.BODY_WITH_ROLE.format(body=label, role=text3.PRINT_ROLES[roles[i]])
            child = QTreeWidgetItem([label])
            child.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            child.setData(0, BODY_ROLE, i)
            if i in hidden_bodies:  # hidden bodies look like suppressed rows (D410)
                child.setIcon(0, row_icon("tree.body", faded=True))
                child.setForeground(0, QBrush(QColor(chrome().muted)))
            else:
                child.setIcon(0, row_icon("tree.body"))
            holder(i).addChild(child)
        self.addTopLevelItem(folder)
        # Colours in use (P2.11 item 1), under the bodies (L4 keeps them second).
        from fdcad.ui.appearance.tree_rows import appearance_row

        self.addTopLevelItem(appearance_row(doc))
        self.addTopLevelItem(_material_row(doc))  # TR78 (D803)
        from fdcad.ui.equations.tree_rows import equations_row

        equations = equations_row(doc)  # global variables (P4.10 item 1)
        if equations is not None:
            self.addTopLevelItem(equations)
        from fdcad.ui.section.tree_rows import section_folder

        sections = section_folder(self.section_planes)  # TR213 (D2501)
        if sections is not None:
            self.addTopLevelItem(sections)
            sections.setExpanded(True)
        state_color = {
            FeatureState.WARNING: colors.state_warning,
            FeatureState.ERROR: colors.state_error,
        }
        rolled_back = False
        # A sketch used by a feature sits under that feature (W5.3), unless the
        # rollback bar lies between them.
        ids = [f.id for f in doc.features]
        place = rollback.current(doc)
        cut = ids.index(place) + 1 if place is not None else len(ids)
        # A bar at the default planes sits below all built in rows (T14.5.1).
        built_in_rows = [f.id for f in display_order(doc.features) if f.id in _BUILT_IN]
        bar_after = built_in_rows[-1] if place in _BUILT_IN and built_in_rows else place
        warned_parents = problems.warned_parents(doc, report) if report is not None else set()
        users = {
            sid: uid
            for sid, uid in visibility.sketch_users(doc).items()
            if sid in ids[:cut] and uid in ids[:cut] and ids.index(sid) < ids.index(uid)
        }
        if self.flat:
            users = {}
        nested: dict[str, list[QTreeWidgetItem]] = {}
        from fdcad.core.document import tree_info

        top_ids = [f.id for f in display_order(doc.features) if f.id not in users]
        folder_of = tree_info.runs(doc.tree, top_ids)
        from fdcad.core.document.freeze import frozen as frozen_ids
        from fdcad.core.document.freeze import place as freeze_at

        freeze_place = None if self.flat else freeze_at(doc)
        frozen_set = set(frozen_ids(doc))
        open_folder: QTreeWidgetItem | None = None
        for feature in display_order(doc.features):
            result = report.results.get(feature.id) if report else None
            prefix = sketch_prefix(result) if feature.type == "sketch" else ""
            item = QTreeWidgetItem([prefix + feature.name])
            item.setData(0, FID_ROLE, feature.id)
            item.setToolTip(0, feature.name)  # long names are cut off in a narrow tree (D594)
            name = icon_name(feature)
            if feature.id in _BUILT_IN:
                item.setIcon(0, row_icon(name))  # never a state mark, never grey
            elif feature.suppressed or rolled_back:
                item.setIcon(0, row_icon(name, faded=True))
                item.setForeground(0, QBrush(QColor(chrome().muted)))
            else:
                state = state_color.get(result.state) if result is not None else None
                if state is None and feature.id in warned_parents:
                    # A parent of a feature with a warning gets a smaller mark (T14.5.3).
                    item.setIcon(
                        0, row_icon(name, colors.state_warning, small=True, mark="warning")
                    )
                else:
                    kind = "warning" if result and result.state is FeatureState.WARNING else "error"
                    item.setIcon(0, row_icon(name, state, mark=kind))
                if state is not None:
                    item.setForeground(0, QBrush(QColor(state)))  # red or warning text
                if result is not None and result.issues:
                    messages = [feature.name, *(i.message for i in result.issues)]
                    item.setToolTip(0, "\n".join(messages))
            if feature.id in frozen_set:  # TR98 (D2507): frozen rows say so
                from fdcad.ui.tree import freeze_bar

                tip = item.toolTip(0)
                item.setToolTip(0, f"{tip}\n{freeze_bar.ROW_TIP}" if tip else freeze_bar.ROW_TIP)
            note = tree_info.comment(doc.tree, feature.id)
            if note:  # a comment: a small mark, and the text on hover (TR23)
                item.setData(0, COMMENT_ROLE, note)
                faded = (feature.suppressed or rolled_back) and feature.id not in _BUILT_IN
                if result is None or result.state is FeatureState.OK or faded:
                    item.setIcon(0, row_icon(name, faded=faded, commented=True))
                item.setToolTip(0, f"{item.toolTip(0)}\n{note}" if item.toolTip(0) else note)
            if feature.id not in _BUILT_IN or feature.type == "plane":
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)  # planes too (T9.5)
            shared = visibility.shared_sketch(doc, feature)
            if shared is not None:
                item.addChild(_link_row(shared))  # a shared sketch (T5.3.5)
            if feature.id in users:
                nested.setdefault(users[feature.id], []).append(item)
            elif feature.id in folder_of:
                # A folder row holds its run of neighbouring features (TR23).
                name_ = folder_of[feature.id]
                if open_folder is None or open_folder.data(0, FOLDER_ROLE) != name_:
                    open_folder = self._folder_row(name_)
                    self.addTopLevelItem(open_folder)
                    open_folder.setExpanded(name_ not in self.closed_folders)
                open_folder.addChild(item)
                item.addChildren(nested.pop(feature.id, []))
            else:
                open_folder = None
                self.addTopLevelItem(item)
                item.addChildren(nested.pop(feature.id, []))
            if feature.id == selected:
                self.setCurrentItem(item)
            if doc.graphs:  # node graphs sit below the feature at their position (Phase 7)
                from fdcad.ui.node_editor.tree_rows import graph_rows

                found = report.graphs if report is not None else None
                for row in graph_rows(doc, feature.id, rolled_back, found):
                    self.addTopLevelItem(row)
                    open_folder = None
            if feature.id == freeze_place:  # TR98 (D2507)
                from fdcad.ui.tree import freeze_bar

                self.addTopLevelItem(freeze_bar.row(colors.selection))
                open_folder = None
            if bar_after == feature.id:
                bar = QTreeWidgetItem([strings.ROLLBACK_BAR])
                bar.setData(0, FID_ROLE, ROLLBACK_MARK)
                bar.setForeground(0, QBrush(QColor(colors.state_warning)))
                # Selectable and draggable: arrows or a drag move it (T14.5.1).
                bar.setFlags(
                    Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsDragEnabled
                )
                self.addTopLevelItem(bar)
                open_folder = None
                if keep_bar:
                    self.setCurrentItem(bar)
                rolled_back = True
        self._bar_wanted = False
        self._filling = False
        self.refreshed.emit()

    # Actions ------------------------------------------------------------------------

    # Folders and comments (TR23) -----------------------------------------------------

    def _folder_row(self, name: str) -> QTreeWidgetItem:
        row = QTreeWidgetItem([name])
        row.setData(0, FOLDER_ROLE, name)
        row.setIcon(0, row_icon("tree.folder"))
        row.setFlags(
            Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
        )
        return row

    def _folder_toggled(self, item: QTreeWidgetItem) -> None:
        name = item.data(0, FOLDER_ROLE)
        if isinstance(name, str) and not self._filling:
            if item.isExpanded():
                self.closed_folders.discard(name)
            else:
                self.closed_folders.add(name)

    def _set_tree(self, tree: dict[str, Any], text_: str) -> None:
        from fdcad.ui.commands.document import SetTreeInfo

        if self.session is not None:
            self.session.undo.push(SetTreeInfo(self.session, tree, text_))
            self.refresh()

    def top_level_features(self) -> list[str]:
        """Feature ids of the top level rows, folder members included, top to bottom."""
        out: list[str] = []
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if item is None:
                continue
            rows: list[QTreeWidgetItem | None] = [item]
            if isinstance(item.data(0, FOLDER_ROLE), str):
                rows = [item.child(j) for j in range(item.childCount())]
            for row in rows:
                if row is None:
                    continue
                fid = row.data(0, FID_ROLE)
                if isinstance(fid, str) and fid not in (ROLLBACK_MARK, PART_MARK):
                    out.append(fid)
        return out

    def selected_features(self) -> list[str]:
        """Ids of the selected feature rows."""
        out = []
        for item in self.selectedItems():
            fid = item.data(0, FID_ROLE)
            if isinstance(fid, str) and fid not in (ROLLBACK_MARK, PART_MARK):
                out.append(fid)
        return out

    def add_to_new_folder(self, fids: list[str] | None = None) -> bool:
        """Put neighbouring features (the selection) in a new folder."""
        from fdcad.core.document import tree_info

        if self.session is None:
            return False
        members = [f for f in (fids or self.selected_features()) if f not in _BUILT_IN]
        tree = self.session.document.tree
        try:
            new = tree_info.add_folder(
                tree, tree_info.next_name(tree), members, self.top_level_features()
            )
        except tree_info.TreeInfoError as exc:
            self.message = str(exc)
            self.message_shown.emit(self.message)
            return False
        self._set_tree(new, text.ADD_FOLDER)
        return True

    def rename_folder(self, old: str, new: str) -> bool:
        """Rename a folder."""
        from fdcad.core.document import tree_info

        if self.session is None:
            return False
        try:
            tree = tree_info.rename_folder(self.session.document.tree, old, new)
        except tree_info.TreeInfoError as exc:
            self.message = str(exc)
            self.message_shown.emit(self.message)
            return False
        if new.strip() != old:
            self.closed_folders = {new.strip() if n == old else n for n in self.closed_folders}
            self._set_tree(tree, text.RENAME_FOLDER)
        return True

    def remove_folder(self, name: str) -> None:
        """Remove a folder; its features stay where they are."""
        from fdcad.core.document import tree_info

        if self.session is not None:
            self._set_tree(
                tree_info.remove_folder(self.session.document.tree, name), text.REMOVE_FOLDER
            )

    def set_comment(self, fid: str, note: str | None = None) -> bool:
        """Set a feature's comment (asks for it when ``note`` is None)."""
        from fdcad.core.document import tree_info

        if self.session is None:
            return False
        tree = self.session.document.tree
        if note is None:
            from PySide6.QtWidgets import QInputDialog

            note, ok = QInputDialog.getMultiLineText(
                self, text.COMMENT_TITLE, text.COMMENT_PROMPT, tree_info.comment(tree, fid)
            )
            if not ok:
                return False
        try:
            new = tree_info.set_comment(tree, fid, note)
        except tree_info.TreeInfoError as exc:
            self.message = str(exc)
            self.message_shown.emit(self.message)
            return False
        if new != tree:
            self._set_tree(new, text.EDIT_COMMENT)
        return True

    def _folder_menu(self, name: str, item: QTreeWidgetItem) -> QMenu:
        menu = QMenu(self)
        self._add(menu, strings.RENAME, lambda: self.editItem(item, 0))
        self._add(menu, text.REMOVE_FOLDER, lambda: self.remove_folder(name))
        return menu

    def set_section_planes(self, names: list[str]) -> None:
        """Show these section planes in the Section Planes folder; [] removes it."""
        if names != self.section_planes:
            self.section_planes = list(names)
            self.refresh()

    def _double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        from fdcad.ui.section.tree_rows import SECTION_ROLE

        plane = item.data(0, SECTION_ROLE)
        if isinstance(plane, int):
            self.section_requested.emit("edit", max(plane, 0))
            return
        fid = item.data(0, FID_ROLE)
        if isinstance(fid, str) and fid not in _BUILT_IN and self._exists(fid):
            self.edit_requested.emit(fid)

    def _renamed(self, item: QTreeWidgetItem, _column: int) -> None:
        if self._filling or self.session is None:
            return
        folder = item.data(0, FOLDER_ROLE)
        if isinstance(folder, str):
            if not self.rename_folder(folder, item.text(0)):
                self.refresh()
            return
        fid = item.data(0, FID_ROLE)
        name = strip_prefix(item.text(0)).strip()
        if not isinstance(fid, str) or fid == ROLLBACK_MARK:
            return
        if not self._exists(fid):
            self.refresh()
            return
        doc = self.session.document
        if not name or name == doc.feature(fid).name:
            self.refresh()
            return
        problem = rename_problem(doc, fid, name)
        if problem is not None:
            self.message = problem
            self.refresh()  # put the old name back
            QMessageBox.warning(self, strings.RENAME, problem)
            return
        self.session.undo.push(RenameFeature(self.session, fid, name))

    def _menu(self, pos: QPoint) -> None:
        session = self.session
        item = self.itemAt(pos)
        if session is None:
            return
        menu = self._context_menu(session, item) if item is not None else self.empty_menu()
        if menu is None:
            return
        menu.exec(self.viewport().mapToGlobal(pos))

    @staticmethod
    def toggle_checkpoint(session: DocumentSession, fid: str) -> None:
        """Mark a feature as a checkpoint, or clear the mark (TR276, D835)."""
        import copy

        from fdcad.ui.commands.document import ReplaceFeature

        edited = copy.deepcopy(session.document.feature(fid))
        if edited.data.get("checkpoint") is True:
            edited.data.pop("checkpoint", None)
        else:
            edited.data["checkpoint"] = True
        session.undo.push(ReplaceFeature(session, edited, strings.CHECKPOINT_UNDO))

    def _context_menu(self, session: DocumentSession, item: QTreeWidgetItem) -> QMenu | None:
        """Build the menu for ``item`` without executing it (tests use this)."""
        from fdcad.ui.appearance.entries import LABEL_ROLE, TARGETS_ROLE, entry_menu, row_targets

        targets = row_targets(item.data(0, TARGETS_ROLE))
        if targets:  # a colour row under Appearances (D584)
            return entry_menu(self, session, targets, str(item.data(0, LABEL_ROLE) or ""))
        from fdcad.ui.section.tree_rows import SECTION_ROLE

        plane = item.data(0, SECTION_ROLE)
        if isinstance(plane, int):  # TR213 (D2501)
            return self._section_menu(plane)
        body_folder = item.data(0, BODY_FOLDER_ROLE)
        if isinstance(body_folder, str):  # TR153 (D2106)
            return self._body_folder_menu(body_folder)
        body = item.data(0, BODY_ROLE)
        if isinstance(body, int):
            return self._body_menu(body)
        folder = item.data(0, FOLDER_ROLE)
        if isinstance(folder, str):
            return self._folder_menu(folder, item)
        fid = item.data(0, FID_ROLE)
        menu = QMenu(self)
        if fid == MATERIAL_MARK:  # TR78
            self._add(menu, strings.MATERIAL_EDIT, self.material_requested.emit)
            return menu
        if fid == ROLLBACK_MARK:
            self._roll_items(menu)
            return menu
        from fdcad.ui.tree import freeze_bar

        if fid == freeze_bar.MARK:  # TR98 (D2507)
            return freeze_bar.bar_menu(menu, session)
        if fid == PART_MARK:
            self._add(menu, _appearance_label(), lambda: self.appearance_requested.emit(""))
            for action in self.part_actions:
                menu.addAction(action)
            arrows = menu.addAction(strings.RELATION_ARROWS)  # TR96 (D942)
            arrows.setObjectName("relation_arrows")
            arrows.setCheckable(True)
            arrows.setChecked(self.relation_arrows)
            arrows.toggled.connect(self.set_relation_arrows)
            return menu
        if not isinstance(fid, str) or not self._exists(fid):
            return None
        feature = session.document.feature(fid)
        editable = fid not in _BUILT_IN
        if editable:
            sketch_id = visibility.sketch_of(feature)
            if sketch_id is not None:
                self._add(menu, strings.EDIT_SKETCH, lambda: self.edit_requested.emit(sketch_id))
            label = strings.EDIT_SKETCH if feature.type == "sketch" else strings.EDIT_FEATURE
            self._add(menu, label, lambda: self.edit_requested.emit(fid))
            if feature.type in ("ref_plane", "ref_axis", "ref_point", "coord_system"):
                # Reference geometry (P2.10): sketch on a plane, hide or show (D251).
                if feature.type == "ref_plane":
                    self._add(menu, strings.SKETCH, lambda: self.sketch_requested.emit(fid))
                datum_shown = fid not in session.hidden
                self._add(
                    menu,
                    strings.HIDE if datum_shown else strings.SHOW,
                    lambda: self.set_sketch_visible(fid, not datum_shown),
                )
            if feature.type == "sketch":
                self._add(
                    menu, strings.EDIT_SKETCH_PLANE, lambda: self.edit_plane_requested.emit(fid)
                )
                shown = self._sketch_shown(session, fid)
                self._add(
                    menu,
                    strings.HIDE if shown else strings.SHOW,
                    lambda: self.set_sketch_visible(fid, not shown),
                )
                self._add(menu, strings.SKETCH_COLOR, lambda: self.pick_sketch_color(fid))
                from fdcad.core.sketch.construction_refs import shows_construction

                cons = self._add(  # TR339 (D1703)
                    menu,
                    strings.SHOW_CONSTRUCTION_IN_PART,
                    lambda: self.set_show_construction(fid, not shows_construction(feature.data)),
                )
                cons.setCheckable(True)
                cons.setChecked(shows_construction(feature.data))
                from fdcad.core.appearance import sketch_color

                if sketch_color(session.document.appearance, fid):
                    self._add(
                        menu, strings.SKETCH_COLOR_CLEAR, lambda: self.pick_sketch_color(fid, "")
                    )
            elif sketch_id is not None and any(
                f.id == sketch_id for f in session.document.features
            ):
                sketch_shown = self._sketch_shown(session, sketch_id)
                self._add(
                    menu,
                    text.HIDE_SKETCH if sketch_shown else text.SHOW_SKETCH,
                    lambda: self.set_sketch_visible(sketch_id, not sketch_shown),
                )
            if _makes_solid(feature):
                self._add(menu, _appearance_label(), lambda: self.appearance_requested.emit(fid))
            self._add(menu, strings.RENAME, lambda: self.rename(fid))
            from fdcad.core.features.switch_op import THIN_TYPES, can_switch

            if can_switch(feature):  # TR387: keep the sketch and ends, change the operation
                from fdcad.core.features.switch_op import switched_operation, switched_thin
                from fdcad.ui.commands.document import ReplaceFeature

                cut = feature.params.get("operation", "boss") == "cut"
                self._add(
                    menu,
                    strings.SWITCH_TO_BOSS if cut else strings.SWITCH_TO_CUT,
                    lambda: session.undo.push(
                        ReplaceFeature(session, switched_operation(session.document, feature))
                    ),
                )
                if feature.type in THIN_TYPES:
                    thin = isinstance(feature.params.get("thin_type"), str)
                    self._add(
                        menu,
                        strings.SWITCH_FROM_THIN if thin else strings.SWITCH_TO_THIN,
                        lambda: session.undo.push(ReplaceFeature(session, switched_thin(feature))),
                    )
            from fdcad.ui.main_window import move_to_body_ui

            if move_to_body_ui.offered(session, fid):  # TR155 (D2107)
                from fdcad.ui.strings_config import MOVE_BODY

                self._add(menu, MOVE_BODY, lambda: move_to_body_ui.move_feature(self, session, fid))
            from fdcad.core.features.import_replace import can_replace

            if can_replace(feature):  # TR11
                from fdcad.ui import strings_import

                self._add(menu, strings_import.REPLACE, lambda: self.replace_requested.emit(fid))
                if feature.type == "import_step":
                    self._add(menu, strings_import.HEAL, lambda: self.heal_requested.emit(fid))
                    self._add(  # TR302 (D1203)
                        menu,
                        strings_import.PICK_BODIES,
                        lambda: self.pick_requested.emit(fid),
                    )
            if _has_problem(session, fid):  # TR125
                self._add(menu, strings.REPAIR_FEATURE, lambda: self.repair_requested.emit(fid))
            self._add(menu, text.COMMENT, lambda: self.set_comment(fid))  # TR23
            if feature.type == "sketch" or visibility.sketch_of(feature) is not None:
                from fdcad.ui.strings_config import LIBRARY_SAVE

                self._add(  # TR72 (D2115)
                    menu, LIBRARY_SAVE, lambda: self.library_requested.emit(fid)
                )
            self._add(menu, text.ADD_FOLDER, lambda: self.add_to_new_folder())
            label = strings.UNSUPPRESS if feature.suppressed else strings.SUPPRESS
            self._add(
                menu,
                label,
                lambda: session.undo.push(SetSuppressed(session, fid, not feature.suppressed)),
            )
            from fdcad.ui.equations.scope import add_suppress_items

            add_suppress_items(menu, session, feature)  # per configuration (P4.10)
            if feature.type == "shell" and feature.refs.get("skipped_faces"):  # TR278 (D1406)
                self._add(menu, strings.RESET_SKIPPED, lambda: self.reset_skipped(fid))
            if feature.type in ("fillet", "draft"):  # TR132 (D1404)
                from fdcad.ui.tree import change_fillets as cf

                if feature.type == "fillet":
                    self._add(
                        menu, strings.CHANGE_FILLETS, lambda: cf.FilletsDialog(session, self).exec()
                    )
                else:
                    self._add(
                        menu, strings.CHANGE_DRAFTS, lambda: cf.DraftsDialog(session, self).exec()
                    )
            if feature.type in ("fillet", "chamfer"):  # TR134 (D994)
                from fdcad.core.fillet_chamfer import can_swap

                if can_swap(feature):
                    label = (
                        strings.SWAP_TO_CHAMFER
                        if feature.type == "fillet"
                        else strings.SWAP_TO_FILLET
                    )
                    self._add(menu, label, lambda: self.swap_kind(fid))
            from fdcad.core.features.pattern_explode import can_explode

            if can_explode(feature):  # TR270 (D1902): one feature per copy
                self._add(menu, strings.EXPLODE_PATTERN, lambda: self.explode_pattern(fid))
            from fdcad.core.features.linked_copy import linked

            if linked(feature):  # TR154 (D2417)
                self._add(menu, strings.BREAK_BODY_LINK, lambda: self.break_body_link(fid))
            if feature.type == "insert_part" and feature.params.get("link", True) is not False:
                self._add(menu, strings.BREAK_BODY_LINK, lambda: self.break_part_link(fid))
            if feature.type == "loft":  # TR136 item 3 (D2404)
                self._add(menu, strings.ADD_LOFT_SECTION, lambda: self.ask_loft_section(fid))
            from fdcad.core.features.follow_pattern import FOLLOW_TYPES, follow_target

            if feature.type not in (*FOLLOW_TYPES, "follow_pattern") and follow_target(
                session.document, fid
            ):  # TR399 (D1904): repeat this feature at every copy of the pattern it is on
                self._add(menu, strings.ADD_TO_PATTERN, lambda: self.add_to_pattern(fid))
            if feature.type == "sketch":  # TR122 (D986): merge into a sketch on the same plane
                from fdcad.ui.tree import merge_sketch

                if merge_sketch.same_plane_sketches(session, fid):
                    self._add(menu, strings.MERGE_SKETCH, lambda: self.merge_sketch(fid))
            if feature.type == "sketch":  # TR49
                from fdcad.ui.tree import derived_sketch as ds

                if feature.refs.get("derived_from"):
                    self._add(
                        menu, strings.DERIVED_PLACE, lambda: ds.edit_placement(session, fid, self)
                    )
                    self._add(menu, strings.DERIVED_BREAK, lambda: ds.break_link(session, fid))
                else:
                    self._add(
                        menu, strings.DERIVED_TITLE, lambda: ds.make_derived(session, fid, self)
                    )
            from fdcad.ui.tree.replace_dialog import replace_everywhere

            self._add(  # TR277
                menu,
                strings.REPLACE_EVERYWHERE,
                lambda: replace_everywhere(
                    session, fid, False, self, getattr(self.window(), "status", None)
                ),
            )
            checkpoint = self._add(  # TR276: stop every rebuild after this feature
                menu, strings.CHECKPOINT_SET, lambda: self.toggle_checkpoint(session, fid)
            )
            checkpoint.setCheckable(True)
            checkpoint.setChecked(feature.data.get("checkpoint") is True)
            from fdcad.core.features.base import keeps_separate_body

            if keeps_separate_body(feature):  # undo "Keep separate body" (D527)
                from fdcad.ui.commands.document import SetKeepSeparateBody

                self._add(
                    menu,
                    strings.WARN_SEPARATE_BODIES,
                    lambda: session.undo.push(SetKeepSeparateBody(session, fid, False)),
                )
        elif feature.type == "plane":
            self._add(menu, strings.SKETCH, lambda: self.sketch_requested.emit(fid))
            self._add(menu, text.NORMAL_TO, lambda: self.normal_to_requested.emit(fid))
            plane_shown = fid in session.shown
            self._add(
                menu,
                strings.HIDE if plane_shown else strings.SHOW,
                lambda: self.set_sketch_visible(fid, not plane_shown),
            )
            self._add(menu, strings.RENAME, lambda: self.rename(fid))
        if fid not in _BUILT_IN:
            self._add(menu, strings.ROLLBACK_HERE, lambda: self._rollback(fid))
        if editable and fid not in _BUILT_IN:  # TR293 (D2209): reorder without a drag
            self._add(menu, strings.TREE_MOVE_UP, lambda: self.step_feature(fid, -1))
            self._add(menu, strings.TREE_MOVE_DOWN, lambda: self.step_feature(fid, 1))
        self._roll_items(menu)
        if editable and fid not in _BUILT_IN:
            freeze_bar.feature_items(menu, session, fid)  # TR98 (D2507)
        self._recent_items(menu)  # TR221
        self._add(menu, strings.PARENTS_CHILDREN, lambda: self.show_relatives(fid))
        if feature.type == "origin":  # TR343 (D2419)
            self._add(menu, strings.MOVE_PART_ORIGIN, lambda: self.ask_part_origin())
        from fdcad.ui.tree import copy_values as copy_ui

        if editable and fid not in _BUILT_IN and copy_ui.others_of_kind(session.document, fid):
            self._add(menu, strings.COPY_VALUES, lambda: self.copy_values(fid))  # TR160
        if editable:
            menu.addSeparator()
            self._add(menu, strings.DELETE, lambda: self.delete(fid))
        return menu

    def empty_menu(self) -> QMenu | None:
        """Right click on empty tree space: the roll items that apply (T14.5.1)."""
        menu = QMenu(self)
        self._roll_items(menu)
        self._recent_items(menu)  # TR221
        return menu if not menu.isEmpty() else None

    def _recent_items(self, menu: QMenu) -> None:
        """A Recently Edited submenu: the features OK last applied, newest first; a
        pick opens the feature for editing (TR221, D963)."""
        session = self.session
        if session is None:
            return
        doc = session.document
        known = {f.id: f for f in doc.features}
        recent = [fid for fid in getattr(session, "recent_edits", []) if fid in known]
        if not recent:
            return
        sub = menu.addMenu(strings.RECENTLY_EDITED)
        sub.setObjectName("recently_edited")
        for fid in recent:
            action = sub.addAction(known[fid].name)
            action.triggered.connect(lambda _c=False, f=fid: self.edit_requested.emit(f))

    def _roll_items(self, menu: QMenu) -> None:
        """Roll Forward, Roll to Previous and Roll to End, where they apply."""
        session = self.session
        if session is None:
            return
        doc = session.document
        if rollback.current(doc) is not None:
            self._add(menu, text.ROLL_FORWARD, self.roll_forward)
        previous = getattr(session, "rollback_previous", _NOWHERE)
        if previous is not _NOWHERE and previous != rollback.current(doc):
            self._add(menu, text.ROLL_PREVIOUS, self.roll_previous)
        if rollback.current(doc) is not None:
            self._add(menu, text.ROLL_END, self.roll_end)

    def roll_forward(self) -> None:
        """Move the bar one feature down."""
        if self.session is not None:
            self._rollback(rollback.stepped(self.session.document, 1))

    def roll_back_one(self) -> None:
        """Move the bar one feature up."""
        if self.session is not None:
            self._rollback(rollback.stepped(self.session.document, -1))

    def roll_previous(self) -> None:
        """Move the bar back to where it was before its last move."""
        previous = getattr(self.session, "rollback_previous", _NOWHERE)
        if previous is None or isinstance(previous, str):  # set by _rollback
            self._rollback(previous)

    def roll_end(self) -> None:
        """Move the bar to the end of the tree."""
        self._rollback(None)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """With the rollback bar selected, Up and Down move it one feature (T14.5.1).
        On a Mac the main Delete key (Backspace to Qt) deletes the selected feature, as
        forward delete does (SHORTCUTS.md 1.7, audit C item 3, D732)."""
        item = self.currentItem()
        if event.key() == Qt.Key.Key_Backspace and sys.platform == "darwin":
            fid = self.selected_id()
            if fid is not None:
                self.delete(fid)
                event.accept()
                return
        on_bar = item is not None and item.data(0, FID_ROLE) == ROLLBACK_MARK
        if on_bar and event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            doc = self.session.document if self.session is not None else None
            step = -1 if event.key() == Qt.Key.Key_Up else 1
            # Only a bar that moves asks for the bar row again (not at either end).
            self._bar_wanted = doc is not None and rollback.stepped(doc, step) != rollback.current(
                doc
            )
            if event.key() == Qt.Key.Key_Up:
                self.roll_back_one()
            else:
                self.roll_forward()
            event.accept()
            return
        super().keyPressEvent(event)

    def _section_menu(self, plane: int) -> QMenu:
        """Menu of the Section Planes folder or one of its planes (TR213, D2501)."""
        from fdcad.ui.section import tree_rows

        menu = QMenu(self)
        index = max(plane, 0)
        self._add(menu, tree_rows.EDIT, lambda: self.section_requested.emit("edit", index))
        self._add(menu, tree_rows.TURN_OFF, lambda: self.section_requested.emit("off", index))
        return menu

    def _clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        """A marked feature shows its problem box; the part name lists every problem."""
        from fdcad.ui.section.tree_rows import SECTION_ROLE

        plane = item.data(0, SECTION_ROLE)
        if isinstance(plane, int) and plane >= 0:
            self.section_requested.emit("pick", plane)
            return
        fid = item.data(0, FID_ROLE)
        session = self.session
        if session is None or session.report is None or not isinstance(fid, str):
            return
        if fid == PART_MARK:
            if problems.worst_state(session.report) is not None:
                self.show_problem_list()
            return
        if fid == ROLLBACK_MARK or not self._exists(fid):
            return
        found = [p for p in problems.all_problems(session.document, session.report) if p.fid == fid]
        if found:
            self.show_problem_box(fid)

    def show_problem_box(self, fid: str) -> problems.ProblemBox | None:
        """The small box beside a marked feature's row (T14.5.3)."""
        session = self.session
        item = self.item_for(fid)
        if session is None or session.report is None or item is None:
            return None
        found = [p for p in problems.all_problems(session.document, session.report) if p.fid == fid]
        if not found:
            return None
        feature = session.document.feature(fid)
        sketch_id = visibility.sketch_of(feature) if feature.type != "sketch" else None
        if sketch_id is not None and not any(f.id == sketch_id for f in session.document.features):
            sketch_id = None
        box = problems.ProblemBox(fid, found, sketch_id, self)
        box.edit_feature.connect(self.edit_requested.emit)
        box.edit_sketch.connect(self.edit_requested.emit)
        rect = self.visualItemRect(item)
        self.problem_box = box
        if self.isVisible():
            box.open_at(self.viewport().mapToGlobal(rect.topRight() + QPoint(8, 0)))
        return box

    def show_problem_list(self) -> problems.ProblemList | None:
        """Every error and warning of the part, from the part name row (T14.5.3)."""
        session = self.session
        if session is None or session.report is None:
            return None
        popup = problems.ProblemList(problems.all_problems(session.document, session.report), self)
        popup.chosen.connect(self._select_from_list)
        self.problem_list = popup
        if self.isVisible():
            top = self.topLevelItem(0)
            rect = self.visualItemRect(top) if top is not None else self.rect()
            popup.open_at(self.viewport().mapToGlobal(rect.bottomLeft()))
        return popup

    def _select_from_list(self, fid: str) -> None:
        item = self.item_for(fid)
        if item is not None:
            self.setCurrentItem(item)
            self.scrollToItem(item)

    @staticmethod
    def _sketch_shown(session: DocumentSession, fid: str) -> bool:
        built = session.report.results if session.report is not None else {fid: None}
        return fid in visibility.visible_sketches(
            session.document, built, session.hidden, session.shown
        )

    def set_sketch_visible(self, fid: str, visible: bool) -> None:
        """Show or hide a sketch or plane in the 3D view, as one undoable command."""
        session = self.session
        if session is not None:
            session.undo.push(SetVisibility(session, fid, visible))
            self.visibility_changed.emit()

    def set_visible(self, fid: str, visible: bool) -> None:
        """Show or hide a sketch or plane. Same as ``set_sketch_visible``."""
        self.set_sketch_visible(fid, visible)

    def rename(self, fid: str) -> None:
        """Start typing a new name for a feature or plane row."""
        item = self.item_for(fid)  # the sketch's own row, not a shared sketch link row
        if item is not None:
            self.scrollToItem(item)  # opens a folded feature that holds the sketch
            self.setCurrentItem(item)
            self.editItem(item, 0)

    def relatives_text(self, fid: str) -> str:
        """Parents and children of a feature, as text for the parent and child view."""
        assert self.session is not None
        doc = self.session.document
        parents = ", ".join(f.name for f in dependencies.parents_of(doc, fid)) or strings.NONE
        children = ", ".join(f.name for f in dependencies.children_of(doc, fid)) or strings.NONE
        return strings.RELATIVES.format(
            name=doc.feature(fid).name, parents=parents, children=children
        )

    def show_relatives(self, fid: str) -> None:
        """Show which features a feature uses and which use it, as two lists to walk
        through (TR96 item 2, D942)."""
        if self.session is None:
            return
        from fdcad.ui.tree.relatives_dialog import RelativesDialog

        dialog = RelativesDialog(self.session.document, fid, self)
        dialog.exec()
        dialog.deleteLater()

    def _min_index(self) -> int:
        """Lowest index a feature may be dropped at (just above the built-ins)."""
        ids = [f.id for f in self.session.document.features] if self.session is not None else []
        built_in = [i for i, fid in enumerate(ids) if fid in _BUILT_IN]
        return (max(built_in) + 1) if built_in else 0

    def step_feature(self, fid: str, step: int) -> bool:
        """Move Up (-1) or Move Down (+1) one place, as a drop there would (TR293)."""
        if self.session is None:
            return False
        ids = [f.id for f in self.session.document.features]
        if fid not in ids:
            return False
        index = ids.index(fid) + step
        if index < self._min_index() or index >= len(ids):
            return False
        return self.move_feature(fid, index)

    def move_feature(self, fid: str, index: int) -> bool:
        """Move a feature to ``index`` when no reference breaks. Returns True when moved."""
        session = self.session
        if session is None or fid in _BUILT_IN:
            return False
        index = max(index, self._min_index())
        problem = dependencies.move_problem(session.document, fid, index)
        if problem is not None:
            self.message = problem
            self.message_shown.emit(problem)
            self.refresh()
            return False
        current = [f.id for f in session.document.features].index(fid)
        if current != index:
            session.undo.push(MoveFeature(session, fid, index))
        self.message = ""
        return True

    def drop_index(self, fid: str, target: QTreeWidgetItem | None, above: bool) -> int | None:
        """Position ``fid`` would take when dropped on ``target``, or None for no move."""
        if self.session is None:
            return None
        ids = [f.id for f in self.session.document.features]
        if target is None:
            return len(ids) - 1
        tid = target.data(0, FID_ROLE)
        if not isinstance(tid, str) or tid not in ids:
            return None
        index = ids.index(tid)
        old = ids.index(fid) if fid in ids else len(ids)
        if old < index and above:
            index -= 1  # moving down onto the upper half lands just above the target
        elif old > index and not above:
            index += 1  # moving up onto the lower half lands just below the target
        return max(index, self._min_index())

    def drop_problem(self, fid: str, target: QTreeWidgetItem | None, above: bool) -> str | None:
        """Why dropping ``fid`` there is not allowed, or None (parents before children)."""
        if self.session is None or fid in _BUILT_IN:
            return strings_built_in()
        index = self.drop_index(fid, target, above)
        if index is None:
            return text.DROP_ON_FEATURE
        return dependencies.move_problem(self.session.document, fid, index)

    def _drop_above(self, event: Any) -> bool:
        return self.dropIndicatorPosition() == QAbstractItemView.DropIndicatorPosition.AboveItem

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802
        """Show where a feature will land, and a not allowed cursor where it cannot (T14.5.2)."""
        super().dragMoveEvent(event)
        item = self.currentItem()
        fid = item.data(0, FID_ROLE) if item is not None else None
        target = self.itemAt(event.position().toPoint())
        if fid == ROLLBACK_MARK:
            event.acceptProposedAction()
            return
        if not isinstance(fid, str):
            event.ignore()
            return
        problem = self.drop_problem(fid, target, self._drop_above(event))
        self.message = problem or ""
        if problem is None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        """Reorder by drag and drop, through an undoable command; or move the bar."""
        item = self.currentItem()
        fid = item.data(0, FID_ROLE) if item is not None else None
        target = self.itemAt(event.position().toPoint())
        above = self._drop_above(event)
        event.ignore()  # the tree is rebuilt from the document, never moved by Qt
        if self.session is None:
            return
        if fid == ROLLBACK_MARK:
            self.drop_bar(target, above)
            return
        if not isinstance(fid, str) or fid in _BUILT_IN:
            return
        index = self.drop_index(fid, target, above)
        if index is not None:
            self.move_feature(fid, index)
        else:
            self.message = text.DROP_ON_FEATURE
            self.message_shown.emit(self.message)

    def drop_bar(self, target: QTreeWidgetItem | None, above: bool) -> None:
        """Move the rollback bar to a row it was dragged onto (T14.5.1)."""
        if self.session is None:
            return
        doc = self.session.document
        tid = target.data(0, FID_ROLE) if target is not None else None
        if target is None:
            self._rollback(None)
        elif isinstance(tid, str) and tid not in (ROLLBACK_MARK, PART_MARK):
            self._rollback(rollback.dropped(doc, tid, above))

    def find_feature(self, text: str | None = None) -> bool:
        """Select the next feature whose name contains ``text`` (asks when it is None)."""
        if text is None:
            text, ok = QInputDialog.getText(self, strings.FIND_TITLE, strings.FIND_PROMPT)
            if not ok:
                return False
        needle = text.strip().lower()
        if not needle:
            return False
        items = self.all_items()
        count = len(items)
        current = self.currentItem()
        start = items.index(current) if current in items else -1
        for step in range(1, count + 1):
            item = items[(start + step) % count]
            if needle in item.text(0).lower():
                self.setCurrentItem(item)
                self.scrollToItem(item)
                return True
        return False

    def delete_selected(self) -> None:
        """Delete the selected feature (Delete key), or remove a selected colour (D584)."""
        from fdcad.ui.appearance.entries import LABEL_ROLE, TARGETS_ROLE, row_targets, set_color

        item = self.currentItem()
        targets = row_targets(item.data(0, TARGETS_ROLE)) if item is not None else []
        if targets and item is not None and item.isSelected() and self.session is not None:
            set_color(self.session, targets, None, str(item.data(0, LABEL_ROLE) or ""))
            return
        folder = item.data(0, FOLDER_ROLE) if item is not None else None
        if isinstance(folder, str) and item is not None and item.isSelected():
            self.remove_folder(folder)  # Delete on a folder row keeps its features (TR23)
            return
        fid = self.selected_id()
        if fid is not None:
            self.delete(fid)

    @staticmethod
    def _add(menu: QMenu, text: str, slot: Any) -> QAction:
        """Add a menu entry, with the icon of its command when it has one (D2703)."""
        from fdcad.ui import menu_icons

        action = menu.addAction(text)
        action.triggered.connect(slot)
        return menu_icons.apply(action)

    def set_show_construction(self, fid: str, on: bool) -> bool:
        """Turn Show Construction in Part on or off for sketch ``fid`` (TR339, D1703).
        One undo step; the rebuild redraws the sketch."""
        import copy

        from fdcad.core.sketch.construction_refs import set_shows_construction
        from fdcad.ui.commands.document import ReplaceFeature

        session = self.session
        if session is None:
            return False
        try:
            feature = session.document.feature(fid)
        except KeyError:
            return False
        edited = copy.deepcopy(feature)
        set_shows_construction(edited.data, on)
        if edited.data == feature.data:
            return False
        session.undo.push(ReplaceFeature(session, edited, strings.SHOW_CONSTRUCTION_IN_PART))
        return True

    def pick_sketch_color(self, fid: str, color: str | None = None) -> bool:
        """Give sketch ``fid`` its own colour in the 3D view, or the usual one back
        (TR233, D928). Without ``color`` a colour dialog asks. One undo step."""
        from fdcad.core.appearance import Target, sketch_color
        from fdcad.ui.appearance.commands import SetAppearance

        session = self.session
        if session is None:
            return False
        if color is None:
            from PySide6.QtWidgets import QColorDialog

            start = sketch_color(session.document.appearance, fid)
            chosen = QColorDialog.getColor(
                QColor(start or palette().sketch_under), self, strings.SKETCH_COLOR
            )
            if not chosen.isValid():
                return False
            color = chosen.name().upper()
        value = None if color == "" else color
        session.undo.push(
            SetAppearance(session, [Target("sketch", fid)], value, strings.SKETCH_COLOR)
        )
        return True

    def _rollback(self, fid: str | None) -> None:
        session = self.session
        if session is None or fid == rollback.current(session.document):
            return
        # Remember where the bar was, for Roll to Previous (view state, not saved).
        session.rollback_previous = rollback.current(session.document)  # type: ignore[attr-defined]
        session.undo.push(SetRollback(session, fid))

    def reset_skipped(self, fid: str) -> None:
        """Reset Skipped Faces: the shell treats every face again (TR278, D1406)."""
        import copy

        session = self.session
        if session is None:
            return
        edited = copy.deepcopy(session.document.feature(fid))
        edited.refs.pop("skipped_faces", None)
        session.undo.push(ReplaceFeature(session, edited, strings.RESET_SKIPPED))

    def swap_kind(self, fid: str) -> bool:
        """Change a fillet to a chamfer or a chamfer to a fillet, one undo step (TR134)."""
        from fdcad.core.fillet_chamfer import SwapError, swapped

        session = self.session
        if session is None:
            return False
        doc = session.document
        old = doc.feature(fid)
        bar = getattr(self.window(), "statusBar", None)

        def report(message: str) -> None:
            if callable(bar):
                bar().showMessage(message)

        try:
            new = swapped(old)
        except SwapError as exc:
            report(str(exc))
            return False
        session.undo.push(
            ReplaceFeature(session, new, strings.SWAP_KIND_UNDO.format(name=old.name))
        )
        note = strings.SWAP_KIND_CHILDREN if dependencies.children_of(doc, fid) else ""
        report(" ".join(t for t in (strings.SWAP_KIND_DONE.format(name=new.name), note) if t))
        return True

    def explode_pattern(self, fid: str) -> bool:
        """Turn a pattern into one feature per copy, one undo step (TR270, D1902)."""
        from fdcad.core.features.base import FeatureError
        from fdcad.core.features.pattern_explode import explode
        from fdcad.ui.commands.document import AddFeature

        session = self.session
        if session is None or session.report is None:
            return False
        doc = session.document
        bar = getattr(self.window(), "statusBar", None)
        try:
            made = explode(doc, fid, session.report.results)
        except FeatureError as exc:
            if callable(bar):
                bar().showMessage(str(exc))
            return False
        index = next(i for i, f in enumerate(doc.features) if f.id == fid)
        session.undo.beginMacro(strings.EXPLODE_PATTERN_UNDO.format(name=doc.feature(fid).name))
        session.undo.push(ReplaceFeature(session, made[0]))
        for n, feature in enumerate(made[1:], start=1):
            session.undo.push(AddFeature(session, feature, index + n))
        session.undo.endMacro()
        return True

    def ask_part_origin(self) -> bool:
        """Ask where the part origin goes, then move it (TR343, D2419)."""
        choices = list(strings.PART_ORIGIN_CHOICES.values())
        picked, ok = QInputDialog.getItem(
            self, strings.MOVE_PART_ORIGIN, strings.PART_ORIGIN_PROMPT, choices, 0, False
        )
        if not ok:
            return False
        key = next(k for k, v in strings.PART_ORIGIN_CHOICES.items() if v == picked)
        return self.move_part_origin(key)

    def move_part_origin(self, how: str) -> bool:
        """Move the part origin and its main planes to the bodies' box centre ("box"),
        their centre of volume ("mass"), the selected vertex or face ("selection") or back
        ("reset"), in one undo step. The origin keeps its turns."""
        import copy

        from fdcad.core.document.model import Param
        from fdcad.core.features.reference import ORIGIN_KEYS

        session = self.session
        if session is None:
            return False
        doc = session.document
        origin = next((f for f in doc.features if f.type == "origin"), None)
        if origin is None:
            return False
        point = self._origin_point(how)
        bar = getattr(self.window(), "statusBar", None)
        if point is None:
            if callable(bar):
                bar().showMessage(strings.PART_ORIGIN_NOTHING)
            return False
        edited = copy.deepcopy(origin)
        if how == "reset":
            for key in ORIGIN_KEYS:
                edited.params.pop(key, None)
        else:
            for key, v in zip(("ox", "oy", "oz"), point, strict=True):
                edited.params[key] = Param(f"{v:.6g}", v)
        session.undo.push(ReplaceFeature(session, edited, strings.MOVE_PART_ORIGIN))
        return True

    def _origin_point(self, how: str) -> tuple[float, float, float] | None:
        """Where ``how`` puts the origin, from the last rebuild, or None."""
        session = self.session
        report = session.report if session is not None else None
        if how == "reset":
            return (0.0, 0.0, 0.0)
        if report is None or report.body is None:
            return None
        shape = report.body.shape
        if how == "selection":
            window = self.window()
            tab = getattr(window, "current", None)
            picked = list(getattr(tab, "selection", []) or [])
            if not picked:
                return None
            shape = picked[0]
        from OCP.TopAbs import TopAbs_VERTEX

        if shape.ShapeType() == TopAbs_VERTEX:
            from OCP.BRep import BRep_Tool
            from OCP.TopoDS import TopoDS

            p = BRep_Tool.Pnt_s(TopoDS.Vertex(shape))
            return p.X(), p.Y(), p.Z()
        if how == "mass":  # the centre of volume (centroid gives a face its area centre)
            from OCP.BRepGProp import BRepGProp
            from OCP.GProp import GProp_GProps

            props = GProp_GProps()
            BRepGProp.VolumeProperties_s(shape, props)
            c = props.CentreOfMass()
            return c.X(), c.Y(), c.Z()
        from fdcad.core.features.preview_anchor import box_centre

        return box_centre(shape)

    def break_part_link(self, fid: str) -> bool:
        """Keep an inserted part's bodies in this part and stop reading its file (TR71,
        D2420). The STEP block stays in the part after an undo; it is only data."""
        from fdcad.core.features.base import FeatureError
        from fdcad.core.features.insert_part import break_link

        session = self.session
        if session is None:
            return False
        try:
            made, block_id, block = break_link(session.document, fid)
        except FeatureError as exc:
            bar = getattr(self.window(), "statusBar", None)
            if callable(bar):
                bar().showMessage(str(exc))
            return False
        session.document.embedded[block_id] = block
        session.undo.push(ReplaceFeature(session, made, strings.BREAK_BODY_LINK))
        return True

    def break_body_link(self, fid: str) -> bool:
        """Make a linked body copy independent, in one undo step (TR154, D2417): the
        features take the order they are built in, and the copy's link is turned off."""
        from fdcad.core.features.base import FeatureError
        from fdcad.core.features.linked_copy import break_link
        from fdcad.ui.commands.document import MoveFeature

        session = self.session
        if session is None:
            return False
        doc = session.document
        try:
            order = break_link(doc, fid)
        except FeatureError as exc:
            bar = getattr(self.window(), "statusBar", None)
            if callable(bar):
                bar().showMessage(str(exc))
            return False
        session.undo.beginMacro(strings.BREAK_BODY_LINK_UNDO.format(name=doc.feature(fid).name))
        for index, feature in enumerate(order):
            current = next(i for i, f in enumerate(doc.features) if f.id == feature.id)
            if current != index:
                session.undo.push(MoveFeature(session, feature.id, index))
        session.undo.push(ReplaceFeature(session, next(f for f in order if f.id == fid)))
        session.undo.endMacro()
        return True

    def ask_loft_section(self, fid: str) -> bool:
        """Ask where the new loft section goes, then add it (TR136 item 3, D2404)."""
        count = (
            len(self.session.document.feature(fid).refs.get("profiles") or [])
            if (self.session is not None)
            else 0
        )
        value, ok = QInputDialog.getDouble(
            self,
            strings.ADD_LOFT_SECTION,
            strings.LOFT_SECTION_PROMPT,
            1.5,
            1.01,
            max(count - 0.01, 1.01),
            2,
        )
        return bool(ok) and self.add_loft_section(fid, value)

    def add_loft_section(self, fid: str, position: float) -> bool:
        """Add a plane and a section sketch to the loft at ``position`` (1.5 is halfway
        between profiles 1 and 2) in one undo step, then open the sketch to edit it."""
        import copy

        from fdcad.core.features.base import FeatureError
        from fdcad.core.features.loft_section import add_loft_section, insert_section
        from fdcad.ui.commands.document import AddFeature

        session = self.session
        if session is None or session.report is None:
            return False
        doc = session.document
        bar = getattr(self.window(), "statusBar", None)
        try:
            plane, sketch = add_loft_section(doc, fid, position, dict(session.report.results))
        except FeatureError as exc:
            if callable(bar):
                bar().showMessage(str(exc))
            return False
        changed = copy.deepcopy(doc)
        insert_section(changed, fid, position, copy.deepcopy(plane), copy.deepcopy(sketch))
        index = next(i for i, f in enumerate(doc.features) if f.id == fid)
        session.undo.beginMacro(strings.LOFT_SECTION_UNDO.format(name=doc.feature(fid).name))
        session.undo.push(AddFeature(session, plane, index))
        session.undo.push(AddFeature(session, sketch, index + 1))
        session.undo.push(ReplaceFeature(session, changed.feature(fid)))
        session.undo.endMacro()
        edit = getattr(self.window(), "edit_feature", None)
        if callable(edit):
            edit(sketch.id)
        return True

    def add_to_pattern(self, fid: str) -> bool:
        """Repeat a feature at every copy of the pattern it was built on, as a Follow
        Pattern just below it (TR399, D1904). One undo step."""
        from fdcad.core.document.model import Feature
        from fdcad.core.features import REGISTRY
        from fdcad.core.features.follow_pattern import follow_target
        from fdcad.ui.body_tools.flow import default_name
        from fdcad.ui.commands.document import AddFeature

        session = self.session
        if session is None:
            return False
        doc = session.document
        target = follow_target(doc, fid)
        if target is None:
            return False
        seed = doc.feature(fid)
        ftype = REGISTRY.get(seed.type)
        solid = seed.params.get("operation") in ("boss", "cut") or (
            ftype is not None and ftype.pattern_operation is not None
        )
        made = Feature(
            doc.new_feature_id(),
            "follow_pattern",
            default_name(doc, "follow_pattern"),
            params={} if solid else {"geometry": True},  # a chamfer copies its faces
            refs={"pattern": {"feature": target[0]}, "features": [{"feature": fid}]},
            data={"on": list(target[1])},
        )
        index = next(i for i, f in enumerate(doc.features) if f.id == fid)
        session.undo.push(AddFeature(session, made, index + 1))
        return True

    def merge_sketch(self, fid: str) -> bool:
        """Merge this sketch into another on the same plane (TR122)."""
        from fdcad.ui.tree import merge_sketch

        if self.session is None:
            return False
        bar = getattr(self.window(), "statusBar", None)

        def report(message: str) -> None:
            if callable(bar):
                bar().showMessage(message)

        return merge_sketch.merge_into(self.session, fid, self, report)

    def copy_values(self, fid: str) -> int:
        """Copy this feature's values to other features of its kind (TR160)."""
        from fdcad.ui.tree import copy_values as copy_ui

        if self.session is None:
            return 0
        window = self.window()
        bar = getattr(window, "statusBar", None)

        def report(message: str) -> None:
            if callable(bar):
                bar().showMessage(message)

        return copy_ui.copy_values_to_others(self.session, fid, self, report)

    def delete(self, fid: str) -> None:
        """Delete a feature, warning first when other features use it.

        A feature whose sketch no other feature uses asks whether to delete the
        sketch too (T9.10); both go as one undo step.
        """
        session = self.session
        if session is None or fid in _BUILT_IN:
            return
        doc = session.document
        if fid in rollback.rolled_back(doc):
            self.delete_rolled_back(fid)
            return
        sketch_id = own_sketch(doc.features, fid)
        from fdcad.core.document.dependencies import graphs_using
        from fdcad.ui.tree import delete_dialog

        graphs = graphs_using(doc, fid)
        # Everything that uses the feature, directly or through another (TR201, D807).
        items = [f for f in rollback.dependents(doc, fid) if f.id != sketch_id]
        from fdcad.core.equations.orphans import only_used_by

        # Variables only these features use (TR91, D940), offered unticked.
        orphans = only_used_by(doc, [fid, *(f.id for f in items)])
        also: list[str] = []
        drop_vars: list[str] = []
        if items or graphs or orphans:
            chosen = delete_dialog.ask(doc.feature(fid).name, items, graphs, self, orphans)
            if chosen is None:
                return
            if chosen == delete_dialog.REPLACE:
                from fdcad.ui.tree.replace_dialog import replace_everywhere

                status = getattr(self.window(), "status", None)
                replace_everywhere(session, fid, True, self, status)
                return
            drop_vars = [c[len(delete_dialog.VARIABLE) :] for c in chosen if c.startswith("var:")]
            also = [c for c in chosen if not c.startswith(delete_dialog.VARIABLE)]
        with_sketch = False
        if sketch_id is not None:
            choice = self.ask_keep_sketch(doc.feature(fid).name, doc.feature(sketch_id).name)
            if choice is None:
                return
            with_sketch = not choice
        if not with_sketch and not also and not drop_vars:
            session.undo.push(DeleteFeature(session, fid))
            return
        doomed = [fid, *also, *([sketch_id] if with_sketch and sketch_id else [])]
        order = [f.id for f in doc.features]
        session.undo.beginMacro(f"Delete {doc.feature(fid).name}")
        for gone in sorted(set(doomed), key=order.index, reverse=True):
            session.undo.push(DeleteFeature(session, gone))
        if drop_vars:
            session.undo.push(_drop_variables(session, drop_vars))
        session.undo.endMacro()

    def delete_rolled_back(self, fid: str) -> bool:
        """Delete a rolled back feature with everything that uses it, after a confirm
        that lists them (T14.5.1). One undo step. Returns True when deleted."""
        session = self.session
        if session is None:
            return False
        doc = session.document
        extra = rollback.dependents(doc, fid)
        if extra:
            names = ", ".join(f.name for f in extra)
            answer = QMessageBox.question(
                self,
                strings.DELETE,
                text.DELETE_DEPENDENTS.format(name=doc.feature(fid).name, names=names),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,  # the safe button (U8.5)
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False
        order = [f.id for f in doc.features]
        doomed = sorted([fid, *[f.id for f in extra]], key=order.index, reverse=True)
        session.undo.beginMacro(f"Delete {doc.feature(fid).name}")
        for gone in doomed:
            session.undo.push(DeleteFeature(session, gone))
        session.undo.endMacro()
        return True

    def ask_keep_sketch(self, name: str, sketch: str) -> bool | None:
        """True keeps the sketch, False deletes it too, None cancels (T9.10)."""
        box = QMessageBox(self)
        box.setWindowTitle(text.DELETE_TITLE)
        box.setText(text.DELETE_KEEP_SKETCH.format(name=name, sketch=sketch))
        also = box.addButton(text.DELETE_ALSO_SKETCH, QMessageBox.ButtonRole.DestructiveRole)
        keep = box.addButton(text.DELETE_KEEP, QMessageBox.ButtonRole.AcceptRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(keep)
        box.exec()
        clicked = box.clickedButton()
        box.deleteLater()  # closed boxes stayed alive (D637)
        if clicked is keep:
            return True
        if clicked is also:
            return False
        return None


def _drop_variables(session: Any, names: list[str]) -> Any:
    """One undo step that deletes global variables, with their configuration overrides
    and design table columns (TR91, D940)."""
    from fdcad.core import configurations as configs
    from fdcad.ui.equations.commands import DocumentChange

    gone = set(names)

    def change(d: Any) -> None:
        d.variables = [v for v in d.variables if v.name not in gone]
        configs.follow_variables(d, dict.fromkeys(gone))

    return DocumentChange(session, strings.DELETE_VARIABLES_UNDO, change)


def _shown_row(item: QTreeWidgetItem) -> QTreeWidgetItem:
    """The row ``item`` shows in: itself, or its highest closed parent row."""
    row, parent = item, item.parent()
    while parent is not None:
        if not parent.isExpanded():
            row = parent
        parent = parent.parent()
    return row


def _link_row(sketch: Feature) -> QTreeWidgetItem:
    """A row with the link icon for a sketch that an earlier feature already uses (T5.3.5)."""
    row = QTreeWidgetItem([strings.REGION_SHARED_SKETCH.format(sketch=sketch.name)])
    row.setData(0, FID_ROLE, sketch.id)
    row.setIcon(0, row_icon("tree.link"))
    row.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    return row


def _appearance_label() -> str:
    from fdcad.ui.input.commands import BY_ID

    return BY_ID["edit.appearance"].label


def _makes_solid(feature: Feature) -> bool:
    """True for features that make or change solid faces, which can carry a colour."""
    from fdcad.core.features import REGISTRY

    ftype = REGISTRY.get(feature.type)
    return ftype is not None and bool(ftype.makes_solid)


def _has_problem(session: DocumentSession, fid: str) -> bool:
    """True when the feature's last build reported an error or a warning (TR125)."""
    report = session.report
    result = report.results.get(fid) if report is not None else None
    return result is not None and bool(result.issues)


#: The Material row's mark in FID_ROLE (TR78).
MATERIAL_MARK = "__material__"


def _material_row(doc: Any) -> QTreeWidgetItem:
    """The part's material, with its density in both systems (TR78, D803)."""
    from fdcad.core.materials import density_text, part_material
    from fdcad.ui.icons import icon

    found = part_material(doc)
    label = strings.MATERIAL_ROW.format(name=found.name) if found else strings.MATERIAL_ROW_NONE
    row = QTreeWidgetItem([label])
    row.setFlags(Qt.ItemFlag.ItemIsEnabled)
    row.setData(0, FID_ROLE, MATERIAL_MARK)
    row.setIcon(0, icon("tools.material"))
    tip = strings.MATERIAL_ROW_TIP
    if found is not None:
        tip = f"{density_text(found.density)}\n{tip}"
    row.setToolTip(0, tip)
    return row
