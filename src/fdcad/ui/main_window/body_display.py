"""Isolate, hide and show bodies, show the hovered body, show all hidden (P3.4 item 6, D410).

Keys (SHORTCUTS.md 3): I isolates, H hides or shows the selected bodies,
Shift+Tab shows the hidden body under the cursor, Ctrl+Shift+Tab shows every
hidden body. Hiding is saved in the part and goes on the undo list; isolating
is a view state of the open part, like the section view.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from fdcad.core.body_visibility import (
    bodies_of,
    first_hit,
    hidden_indices,
    hidden_names,
    marks_for,
    see_through_names,
    without_bodies,
)
from fdcad.core.kernel import kernel_job
from fdcad.ui import strings_phase3 as text
from fdcad.ui.commands.document import SetHiddenBodies, SetSeeThroughBodies

if TYPE_CHECKING:
    from fdcad.core.naming.names import NamedShape
    from fdcad.ui.main_window.window import DocumentTab, MainWindow

Vec3 = tuple[float, float, float]


class _Signals(QObject):
    done = Signal(object)


class HoverJob(QRunnable):
    """Finds the hidden body under the cursor off the UI thread (CLAUDE.md rule 2)."""

    def __init__(self, body: NamedShape, indices: list[int], ray: tuple[Vec3, Vec3]) -> None:
        super().__init__()
        self.body, self.indices, self.ray = body, indices, ray
        self.signals = _Signals()

    @kernel_job
    def run(self) -> None:
        """Intersect the ray with the hidden bodies; never raise (CLAUDE.md rule 7)."""
        try:
            hit = first_hit(self.body, self.indices, *self.ray)
        except Exception:
            hit = None
        self.signals.done.emit(hit)


class HistoryJob(QRunnable):
    """Finds the features that made one body off the UI thread (TR153, D972)."""

    def __init__(self, doc: Any, body: NamedShape, index: int) -> None:
        super().__init__()
        self.doc, self.body, self.index = doc, body, index
        self.signals = _Signals()

    @kernel_job
    def run(self) -> None:
        """Read the body's faces; never raise (CLAUDE.md rule 7)."""
        from fdcad.core.body_history import body_history

        try:
            found: list[str] | None = body_history(self.doc, self.body, self.index)
        except Exception:
            found = None
        self.signals.done.emit(found)


class BodyDisplay(QObject):
    """The body visibility commands of the main window."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.window = window
        self._jobs: set[Any] = set()

    # What is picked -----------------------------------------------------------------

    @staticmethod
    def _body(tab: DocumentTab) -> NamedShape | None:
        report = tab.session.report
        return report.body if report is not None else None

    def selected(self, tab: DocumentTab) -> list[int]:
        """Bodies of the faces, edges or vertices picked in the view, else the tree's body row."""
        body = self._body(tab)
        picks = bodies_of(body.shape if body is not None else None, tab.selection)
        if picks:
            return picks
        tree = self.window.tree
        index = tree.selected_body() if tree is not None else None
        return [index] if index is not None else []

    # Hide and show --------------------------------------------------------------------

    def hide_or_show(self) -> bool:
        """H: hide the selected bodies, or show them when all are hidden. False with none."""
        tab = self.window.current
        if tab is None:
            return False
        indices = self.selected(tab)
        if not indices:
            return False
        hidden = set(hidden_indices(self._body(tab), hidden_names(tab.session.document)))
        self.set_hidden(tab, indices, not set(indices) <= hidden)
        return True

    def set_hidden(self, tab: DocumentTab, indices: list[int], hide: bool) -> None:
        """Hide or show the bodies at ``indices`` as one undoable step."""
        body = self._body(tab)
        current = hidden_names(tab.session.document)
        after = (
            current | marks_for(body, indices) if hide else without_bodies(current, body, indices)
        )
        if after == current:
            return
        if len(indices) == 1:
            label = text.HIDE_ONE_UNDO if hide else text.SHOW_ONE_UNDO
            words = label.format(index=indices[0] + 1)
        else:
            label = text.HIDE_BODIES_UNDO if hide else text.SHOW_BODIES_UNDO
            words = label.format(count=len(indices))
        tab.session.undo.push(SetHiddenBodies(tab.session, after, words))
        count = len(hidden_indices(body, after))
        if hide:
            message = (
                text.BODY_HIDDEN.format(index=indices[0] + 1)
                if len(indices) == 1
                else text.BODIES_HIDDEN.format(count=count)
            )
            self.window.status.setText(message)

    def set_locked(self, tab: DocumentTab, indices: list[int], on: bool) -> None:
        """Lock or unlock the bodies at ``indices`` as one undoable step (TR269)."""
        from fdcad.core.body_visibility import locked_names
        from fdcad.ui.commands.document import SetLockedBodies

        body = self._body(tab)
        current = locked_names(tab.session.document)
        after = current | marks_for(body, indices) if on else without_bodies(current, body, indices)
        if after == current:
            return
        label = text.LOCK_ONE_UNDO if on else text.UNLOCK_ONE_UNDO
        tab.session.undo.push(
            SetLockedBodies(tab.session, after, label.format(index=indices[0] + 1))
        )
        if on:
            self.window.status.setText(text.BODY_LOCKED.format(index=indices[0] + 1))

    def set_see_through(self, tab: DocumentTab, indices: list[int], on: bool) -> None:
        """Make the bodies at ``indices`` see through, or solid, as one undoable step."""
        body = self._body(tab)
        current = see_through_names(tab.session.document)
        after = current | marks_for(body, indices) if on else without_bodies(current, body, indices)
        if after == current:
            return
        label = text.SEE_THROUGH_ONE_UNDO if on else text.SOLID_ONE_UNDO
        tab.session.undo.push(
            SetSeeThroughBodies(tab.session, after, label.format(index=indices[0] + 1))
        )

    def show_all(self) -> None:
        """Ctrl+Shift+Tab: show every hidden body and leave isolate."""
        tab = self.window.current
        if tab is None:
            return
        was_isolated = tab.isolated is not None
        tab.isolated = None
        count = len(hidden_indices(self._body(tab), hidden_names(tab.session.document)))
        if hidden_names(tab.session.document):
            tab.session.undo.push(SetHiddenBodies(tab.session, set(), text.SHOW_ALL_UNDO))
        elif was_isolated:
            tab.session.display_changed.emit()
        if count == 1:
            message = text.BODY_SHOWN
        else:
            message = text.BODIES_SHOWN.format(count=count) if count else text.NO_HIDDEN_BODIES
        self.window.status.setText(message)

    def from_tree(self, action: str, index: int) -> None:
        """A command from the Solid Bodies folder menu."""
        tab = self.window.current
        if tab is None:
            return
        if action == "folder_move" or action.startswith("folder:"):  # TR153 (D2106)
            from fdcad.ui.main_window import body_folders_ui

            if action == "folder_move":
                body_folders_ui.move_to_folder(self, tab, [index])
            else:
                _f, op, name = action.split(":", 2)
                body_folders_ui.folder_action(self, tab, op, name)
            return
        if action == "rename":  # TR183 (D1201)
            self.rename(tab, index)
        elif action == "settings":  # TR383 (D1207)
            self.print_settings(tab, index)
        elif action.startswith("role:"):
            self.set_role(tab, [index], action.partition(":")[2])
        elif action == "show_all":
            self.show_all()
        elif action == "transform":
            from fdcad.ui.body_tools import flow

            flow.start(self.window, "feature.transform_handles", body_index=index)
        elif action == "isolate":
            self._isolate(tab, [index])
        elif action == "history":
            self.history(tab, index)
        elif action in ("see_through", "solid"):
            self.set_see_through(tab, [index], action == "see_through")
        elif action in ("lock", "unlock"):
            self.set_locked(tab, [index], action == "lock")
        elif action.startswith("display:"):  # TR216
            from fdcad.ui.main_window.body_modes_ui import set_mode

            set_mode(tab, index, mode=action.partition(":")[2])
        elif action == "transparency":
            from fdcad.ui.main_window.body_modes_ui import ask_transparency

            ask_transparency(self.window, tab, index)
        else:
            self.set_hidden(tab, [index], action == "hide")

    def rename(self, tab: DocumentTab, index: int, title: str | None = None) -> None:
        """Give a body a lasting name of its own (TR183, D1201); empty takes it off."""
        from PySide6.QtWidgets import QInputDialog

        from fdcad.core.body_titles import BODY_TITLES, titles_of, with_title
        from fdcad.ui import strings
        from fdcad.ui.commands.print_setup import SetPrintSetupKey

        named = self._body(tab)
        if title is None:
            from fdcad.core.body_titles import report_marks

            given = report_marks(tab.session.report, "body_titles")
            titles = titles_of(tab.session.document, named, given)
            now = titles[index] if 0 <= index < len(titles) else None
            title, ok = QInputDialog.getText(
                self.window, strings.RENAME_BODY_TITLE, strings.RENAME_BODY_LABEL, text=now or ""
            )
            if not ok:
                return
        value = with_title(tab.session.document, named, index, title)
        tab.session.undo.push(
            SetPrintSetupKey(tab.session, BODY_TITLES, value, strings.RENAME_BODY_UNDO)
        )

    def print_settings(self, tab: DocumentTab, index: int) -> None:
        """Set a body's slicer settings (TR383, D1207), as one undo step."""
        from fdcad.core.body_titles import labels_of, report_marks
        from fdcad.core.printing.body_settings import BODY_SETTINGS, settings_of, with_settings
        from fdcad.ui import strings_print
        from fdcad.ui.commands.print_setup import SetPrintSetupKey
        from fdcad.ui.main_window import body_settings_dialog

        named = self._body(tab)
        doc = tab.session.document
        current = settings_of(doc, named)
        labels = labels_of(doc, named, report_marks(tab.session.report, "body_titles"))
        if not 0 <= index < len(labels):
            return
        dialog = body_settings_dialog.BodySettingsDialog(labels[index], current[index], self.window)
        accepted = body_settings_dialog.run(dialog)
        values = dialog.values
        dialog.deleteLater()
        if not accepted or values == current[index]:
            return
        value = with_settings(doc, named, index, values)
        tab.session.undo.push(
            SetPrintSetupKey(tab.session, BODY_SETTINGS, value, strings_print.BODY_SETTINGS_UNDO)
        )

    def set_role(self, tab: DocumentTab, indices: list[int], role: str) -> None:
        """Give bodies a print role (TR382), as one undo step."""
        from fdcad.core.body_titles import report_marks
        from fdcad.core.printing.body_roles import with_roles
        from fdcad.ui.commands.print_setup import SetBodyRoles

        given = report_marks(tab.session.report, "body_roles")  # TR386 (D1205)
        roles = with_roles(tab.session.document, self._body(tab), indices, role, given)
        tab.session.undo.push(SetBodyRoles(tab.session, roles, text.PRINT_ROLE_UNDO))

    # Isolate --------------------------------------------------------------------------

    def isolate(self) -> None:
        """I: show only the selected bodies; press again to show the others."""
        tab = self.window.current
        if tab is None:
            return
        if tab.isolated is not None:
            tab.isolated = None
            self.window.status.setText(text.ISOLATE_OFF)
            tab.session.display_changed.emit()
            return
        hidden = hidden_indices(self._body(tab), hidden_names(tab.session.document))
        # A hidden body is not drawn while isolated, so isolating it would empty the view.
        indices = [i for i in self.selected(tab) if i not in hidden]
        if not indices:
            self.window.status.setText(text.ISOLATE_NOTHING)
            return
        self._isolate(tab, indices)

    def _isolate(self, tab: DocumentTab, indices: list[int]) -> None:
        tab.isolated = marks_for(self._body(tab), indices)
        settings = getattr(self.window, "settings", None)
        tab.isolate_look = settings.isolate_others if settings is not None else "hidden"
        self.window.status.setText(text.ISOLATING)
        tab.session.display_changed.emit()

    # Show the hovered body ----------------------------------------------------------

    def show_hovered(self, ray: tuple[Vec3, Vec3] | None = None) -> None:
        """Shift+Tab: show the hidden body under the cursor (found in a kernel job)."""
        tab = self.window.current
        if tab is None:
            return
        body = self._body(tab)
        hidden = hidden_indices(body, hidden_names(tab.session.document))
        if body is None or not hidden:
            self.window.status.setText(text.NO_HIDDEN_BODIES)
            return
        if ray is None:
            ray = self._cursor_ray(tab)
        if ray is None:
            self.window.status.setText(text.HOVER_NO_VIEW)
            return
        job = HoverJob(body, hidden, ray)
        self._jobs.add(job)
        job.signals.done.connect(lambda hit, j=job, t=tab: self._hovered(t, j, hit))
        QThreadPool.globalInstance().start(job)

    @staticmethod
    def _cursor_ray(tab: DocumentTab) -> tuple[Vec3, Vec3] | None:
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QCursor

        view: Any = tab.viewport
        ray_at = getattr(view, "ray_at", None)
        if ray_at is None:
            return None
        pos = view.mapFromGlobal(QCursor.pos())
        if not view.rect().contains(pos):
            return None
        result: tuple[Vec3, Vec3] | None = ray_at(QPointF(pos))
        return result

    def _hovered(self, tab: DocumentTab, job: HoverJob, hit: int | None) -> None:
        self._jobs.discard(job)
        if hit is None:
            self.window.status.setText(text.HOVER_NOTHING)
            return
        self.set_hidden(tab, [hit], hide=False)
        self.window.status.setText(text.HOVER_SHOWN.format(index=hit + 1))

    def history(self, tab: DocumentTab, index: int) -> None:
        """Show Feature History for one body (TR153): worked out off the UI thread."""
        import copy

        body = self._body(tab)
        if body is None:
            self.window.status.setText(text.HOVER_NOTHING)
            return
        job = HistoryJob(copy.deepcopy(tab.session.document), body, index)
        self._jobs.add(job)
        job.signals.done.connect(
            lambda found, j=job, t=tab: self._history_found(t, j, index, found)
        )
        QThreadPool.globalInstance().start(job)

    def _history_found(
        self, tab: DocumentTab, job: Any, index: int, found: list[str] | None
    ) -> None:
        from fdcad.ui import strings

        self._jobs.discard(job)
        if not found:
            self.window.status.setText(strings.BODY_HISTORY_NONE.format(index=index + 1))
            return
        self.show_history(tab, index, found)

    def show_history(self, tab: DocumentTab, index: int, fids: list[str]) -> Any:
        """A list of the features, in tree order; picking one selects it in the tree."""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QDialog, QLabel, QListWidget, QListWidgetItem, QVBoxLayout

        from fdcad.ui import strings

        doc = tab.session.document
        dialog = QDialog(self.window)
        dialog.setObjectName("body_history")
        dialog.setWindowTitle(strings.BODY_HISTORY_TITLE.format(index=index + 1))
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(strings.BODY_HISTORY_HELP))
        items = QListWidget()
        items.setObjectName("body_history_list")
        for fid in fids:
            if any(f.id == fid for f in doc.features):
                item = QListWidgetItem(doc.feature(fid).name)
                item.setData(Qt.ItemDataRole.UserRole, fid)
                items.addItem(item)
        layout.addWidget(items)

        def pick(item: QListWidgetItem) -> None:
            tree = self.window.tree
            if tree is None:
                return
            row = tree.item_for(str(item.data(Qt.ItemDataRole.UserRole)))
            if row is not None:
                tree.scrollToItem(row)
                tree.setCurrentItem(row)

        items.itemClicked.connect(pick)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.show()  # not modal: the tree and the view stay usable
        return dialog

    def wait(self, timeout_ms: int = 20000) -> bool:
        """Wait for running jobs (tests)."""
        return QThreadPool.globalInstance().waitForDone(timeout_ms)
