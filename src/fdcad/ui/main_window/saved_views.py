"""Save View and the saved views of a part (TUTORIAL_REVIEW_SPEC TR14.2, D690).

Save View keeps the current camera under a name in the part file. Saved views
are listed after the standard views (View menu, the view toolbar's views list
and the right click View Orientation menu). Manage Saved Views renames,
updates and deletes them. Each change is one undo step.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QListWidget,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.document import saved_views as sv

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab, MainWindow

SAVE_TITLE = "Save View"
SAVE_PROMPT = "Name of the view:"
SAVED = "Saved the view {name}."
NO_VIEW = "Save View needs an open part with a 3D view."
RENAME_TITLE = "Rename View"
MANAGE_TITLE = "Saved Views"
MANAGE = "Manage Saved Views..."
NONE_SAVED = "No saved views"
GO = "Go To"
UPDATE = "Update"
RENAME = "Rename"
DELETE = "Delete"
CLOSE = "Close"
UPDATED = "Updated the view {name} to the current camera."


def _pose_view(name: str, pose: Any) -> sv.SavedView:
    return sv.SavedView(name, pose.center, pose.direction, pose.up, pose.distance, pose.scale)


class SavedViews:
    """Save View, Go To, and the manage dialog for one window."""

    def __init__(self, window: MainWindow) -> None:
        self.window = window
        #: Asks for a name: (title, prompt, start text) to (text, ok). Tests replace it.
        self.ask_name: Callable[[str, str, str], tuple[str, bool]] = self._ask

    def _ask(self, title: str, prompt: str, text: str) -> tuple[str, bool]:
        answer, ok = QInputDialog.getText(self.window, title, prompt, text=text)
        return str(answer), bool(ok)

    # Helpers -------------------------------------------------------------------------

    def _tab(self) -> DocumentTab | None:
        return self.window.current

    def views(self) -> list[dict[str, Any]]:
        """The active part's saved views."""
        tab = self._tab()
        return tab.session.document.views if tab is not None else []

    def _push(self, views: list[dict[str, Any]], text: str) -> None:
        from fdcad.ui.commands.document import SetSavedViews

        tab = self._tab()
        if tab is not None:
            tab.session.undo.push(SetSavedViews(tab.session, views, text))

    def _pose(self) -> Any:
        tab = self._tab()
        get = getattr(getattr(tab, "viewport", None), "camera_pose", None)
        return get() if get is not None else None

    def _next_name(self) -> str:
        used = {n.casefold() for n in sv.names(self.views())}
        n = 1
        while f"view {n}" in used:
            n += 1
        return f"View {n}"

    # Commands ------------------------------------------------------------------------

    def save(self, name: str | None = None) -> bool:
        """Save the current camera under a name (asked when None)."""
        pose = self._pose()
        if pose is None:
            self.window.status.setText(NO_VIEW)
            return False
        if name is None:
            text, ok = self.ask_name(SAVE_TITLE, SAVE_PROMPT, self._next_name())
            if not ok:
                return False
            name = text
        problem = sv.name_problem(self.views(), name)
        if problem:
            self.window.status.setText(problem)
            return False
        name = name.strip()
        views = self._with_section(sv.save_view(self.views(), _pose_view(name, pose)), name)
        self._push(views, f"Save View {name}")
        self.window.status.setText(SAVED.format(name=name))
        return True

    def go(self, name: str) -> bool:
        """Turn the camera to a saved view."""
        from fdcad.ui.viewport.views import CameraPose

        view = sv.find(self.views(), name)
        tab = self._tab()
        restore = getattr(getattr(tab, "viewport", None), "restore_pose", None)
        if view is None or restore is None:
            return False
        restore(CameraPose(view.center, view.direction, view.up, view.distance, view.scale))
        self._show_section(name)
        return True

    def _with_section(self, views: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
        """Keep the section that is on in the saved view ``name`` (TR213, D1604)."""
        from fdcad.core.section_store import KEY, to_json

        tool = getattr(self.window, "section_tool", None)
        tab = self._tab()
        state = tool.state_of(tab) if tool is not None and tab is not None else None
        if state is None:
            return views
        return [{**v, KEY: to_json(state)} if v.get("name") == name else v for v in views]

    def _show_section(self, name: str) -> None:
        """Going to a saved view that kept a section shows that section."""
        from fdcad.core.section_store import KEY, from_json

        tool = getattr(self.window, "section_tool", None)
        tab = self._tab()
        if tool is None or tab is None:
            return
        raw = next((v.get(KEY) for v in self.views() if v.get("name") == name), None)
        state = from_json(raw)
        if state is not None:
            tool.show_state(tab, state)

    def update(self, name: str) -> bool:
        """Store the current camera in an existing saved view."""
        pose = self._pose()
        if pose is None or name not in sv.names(self.views()):
            return False
        views = self._with_section(sv.save_view(self.views(), _pose_view(name, pose)), name)
        self._push(views, f"Update View {name}")
        self.window.status.setText(UPDATED.format(name=name))
        return True

    def rename(self, old: str, new: str | None = None) -> bool:
        """Rename a saved view (asks for the name when None)."""
        if new is None:
            text, ok = self.ask_name(RENAME_TITLE, SAVE_PROMPT, old)
            if not ok:
                return False
            new = text
        try:
            views = sv.rename_view(self.views(), old, new)
        except sv.SavedViewError as exc:
            self.window.status.setText(str(exc))
            return False
        self._push(views, f"Rename View {old}")
        return True

    def delete(self, name: str) -> bool:
        """Delete a saved view."""
        if name not in sv.names(self.views()):
            return False
        self._push(sv.delete_view(self.views(), name), f"Delete View {name}")
        return True

    # Menus ---------------------------------------------------------------------------

    def fill(self, menu: QMenu, manage: bool = True) -> None:
        """Add the saved views to a menu, after a separator (and Manage when asked)."""
        names = sv.names(self.views())
        if not names and not manage:
            return
        menu.addSeparator()
        for name in names:
            action = menu.addAction(name)
            action.setObjectName(f"saved_view:{name}")
            action.triggered.connect(partial(self.go, name))
        if not names:
            menu.addAction(NONE_SAVED).setEnabled(False)
        if manage:
            menu.addAction(MANAGE).triggered.connect(self.manage)

    def manage(self) -> None:
        """The Saved Views dialog."""
        dialog = ManageDialog(self, self.window)
        dialog.exec()
        dialog.deleteLater()  # closed dialogs stayed alive (D637, audit D8 item 2)


class ManageDialog(QDialog):
    """List of saved views with Go To, Update, Rename and Delete."""

    def __init__(self, views: SavedViews, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(MANAGE_TITLE)
        self.views = views
        layout = QHBoxLayout(self)
        self.list = QListWidget()
        layout.addWidget(self.list, 1)
        side = QVBoxLayout()
        self.buttons: dict[str, QPushButton] = {}
        for label, slot in (
            (GO, views.go),
            (UPDATE, views.update),
            (RENAME, views.rename),
            (DELETE, views.delete),
        ):
            button = QPushButton(label)
            button.clicked.connect(partial(self._run, slot))
            side.addWidget(button)
            self.buttons[label] = button
        side.addStretch(1)
        close = QPushButton(CLOSE)
        close.clicked.connect(self.accept)
        side.addWidget(close)
        layout.addLayout(side)
        self.list.itemDoubleClicked.connect(lambda item: views.go(item.text()))
        self.list.currentRowChanged.connect(lambda _r: self._enable())
        self.refill()

    def refill(self) -> None:
        """Show the current list, keeping the selection where it can."""
        current = self.list.currentItem().text() if self.list.currentItem() else None
        self.list.clear()
        names = sv.names(self.views.views())
        self.list.addItems(names)
        if current in names:
            self.list.setCurrentRow(names.index(current))
        elif names:
            self.list.setCurrentRow(0)
        self._enable()

    def _enable(self) -> None:
        on = self.list.currentItem() is not None
        for button in self.buttons.values():
            button.setEnabled(on)

    def _run(self, slot: Any) -> None:
        item = self.list.currentItem()
        if item is not None:
            slot(item.text())
            self.refill()
