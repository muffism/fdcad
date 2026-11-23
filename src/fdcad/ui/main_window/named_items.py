"""Named faces and edges (TR152, D2105): Name This Item from the right click menu of
a face or edge, and Tools, Named Items: the list of names, which picks each item in
the 3D view, with Rename and Remove."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fdcad.core import named_items
from fdcad.ui import strings_config as text

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab, MainWindow
    from fdcad.ui.session import DocumentSession


def ask_name(parent: QWidget, current: str) -> str | None:
    """Ask for a name (tests replace this). None when cancelled."""
    typed, ok = QInputDialog.getText(parent, text.NAMED_TITLE, text.NAMED_PROMPT, text=current)
    return typed if ok else None


def name_item(window: MainWindow, tab: DocumentTab, shape: Any) -> str | None:
    """Give the face or edge ``shape`` a name (one undo step). Returns the name."""
    from fdcad.core.naming.select import reference_for

    session = tab.session
    report = session.report
    if report is None or report.body is None:
        return None
    ref = reference_for(report.body, shape)
    if ref is None or ref.get("kind") not in named_items.KINDS:
        window.status.setText(text.NAMED_NO_REF)
        return None
    typed = ask_name(window, named_items.name_of(session.document, ref) or "")
    if typed is None:
        return None
    return _apply(window, session, lambda d: named_items.add(d, typed, ref))


def _apply(window: MainWindow, session: DocumentSession, change: Any) -> str | None:
    """Run ``change`` on a copy and store the tree block it leaves as one undo step."""
    import copy

    from fdcad.ui.commands.document import SetTreeInfo

    work = copy.deepcopy(session.document)
    try:
        out = change(work)
    except named_items.ItemNameError as exc:
        window.status.setText(str(exc))
        return None
    if work.tree != session.document.tree:
        session.undo.push(SetTreeInfo(session, work.tree, text.NAMED_UNDO))
        rebuild = getattr(session, "request_rebuild", None)
        if rebuild is not None:
            rebuild()  # measure the named items for property formulas
    if isinstance(out, str):
        window.status.setText(text.NAMED_SET.format(name=out))
        return out
    return ""


class NamedItemsDialog(QDialog):
    """The list of named faces and edges, and the named bodies."""

    def __init__(self, window: MainWindow, parent: QWidget | None = None) -> None:
        super().__init__(parent or window)
        self.setObjectName("named_items_dialog")
        self.setWindowTitle(text.NAMED_LIST_TITLE)
        self.window_ = window
        self.list = QListWidget()
        self.list.setObjectName("named_items_list")
        self.list.currentItemChanged.connect(lambda item, _old: self.show_item(item))
        self.message = QLabel()
        self.message.setWordWrap(True)
        rename = QPushButton(text.NAMED_RENAME)
        rename.clicked.connect(lambda: self.rename_current())
        remove = QPushButton(text.NAMED_REMOVE)
        remove.clicked.connect(lambda: self.remove_current())
        row = QHBoxLayout()
        row.addWidget(rename)
        row.addWidget(remove)
        row.addStretch(1)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(text.NAMED_HELP))
        layout.addWidget(self.list, 1)
        layout.addWidget(self.message)
        layout.addLayout(row)
        self.resize(320, 360)
        self.refresh()

    @property
    def tab(self) -> DocumentTab | None:
        """The part shown."""
        return self.window_.current

    def refresh(self) -> None:
        """Fill the list from the part."""
        self.list.clear()
        tab = self.tab
        if tab is None:
            return
        doc = tab.session.document
        for item in named_items.items(doc):
            row = QListWidgetItem(text.NAMED_ROW.format(name=item["name"], kind=item["kind"]))
            row.setData(Qt.ItemDataRole.UserRole, item["name"])
            self.list.addItem(row)
        from fdcad.core.body_titles import stored

        for title in stored(doc).values():
            row = QListWidgetItem(text.NAMED_ROW.format(name=title, kind="body"))
            self.list.addItem(row)
        if self.list.count() == 0:
            self.message.setText(text.NAMED_EMPTY)

    def show_item(self, row: QListWidgetItem | None) -> Any:
        """Pick the item in the 3D view. Returns the shape, or None."""
        tab = self.tab
        name = row.data(Qt.ItemDataRole.UserRole) if row is not None else None
        if tab is None or not isinstance(name, str):
            return None
        item = named_items.find(tab.session.document, name)
        report = tab.session.report
        if item is None or report is None or report.body is None:
            return None
        try:
            shape = named_items.resolve(report.body, item)
        except Exception as exc:  # a name that no longer resolves
            self.message.setText(text.NAMED_LOST.format(name=name, reason=exc))
            return None
        tab.selection = [shape]
        pick = getattr(tab.viewport, "select_shapes", None)
        if pick is not None:
            pick([shape])
        self.message.clear()
        return shape

    def _current_name(self) -> str | None:
        row = self.list.currentItem()
        name = row.data(Qt.ItemDataRole.UserRole) if row is not None else None
        return name if isinstance(name, str) else None

    def rename_current(self) -> bool:
        """Rename the chosen item."""
        name, tab = self._current_name(), self.tab
        if name is None or tab is None:
            self.message.setText(text.NAMED_PICK)
            return False
        typed = ask_name(self, name)
        if typed is None:
            return False
        done = _apply(self.window_, tab.session, lambda d: named_items.rename(d, name, typed))
        self.refresh()
        return bool(done)

    def remove_current(self) -> bool:
        """Take the name off the chosen item."""
        name, tab = self._current_name(), self.tab
        if name is None or tab is None:
            self.message.setText(text.NAMED_PICK)
            return False
        _apply(self.window_, tab.session, lambda d: named_items.remove(d, name))
        self.refresh()
        return True


def open_list(window: MainWindow) -> NamedItemsDialog | None:
    """Tools, Named Items: show the list (not modal)."""
    if window.current is None:
        return None
    dialog = NamedItemsDialog(window)
    window.named_items_dialog = dialog  # type: ignore[attr-defined]
    dialog.show()
    return dialog
