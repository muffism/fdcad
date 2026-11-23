"""Display States dialog (TR88, D1608): save, apply, delete and link body displays."""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fdcad.core import display_states as ds
from fdcad.core.document.model import Document
from fdcad.ui.commands.document import DocumentCommand

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab, MainWindow

TITLE = "Display States"
SAVE = "Save Current..."
APPLY = "Apply"
DELETE = "Delete"
LINK = "Link to Active Configuration"
UNLINK = "Unlink Active Configuration"
CLOSE = "Close"
SAVE_PROMPT = "Name of the display state:"
NONE_YET = "No display states yet. Use Save Current to keep the bodies' display."
LINKED = "Configuration {config} shows {state}."
NOT_LINKED = "Configuration {config} has no display state."
NO_PART = "Display States needs an open part. Open or create a part first."


class SetAppearance(DocumentCommand):
    """Replace the part's appearance block: one undo step, no rebuild."""

    def __init__(self, session: Any, change: Callable[[Document], object], text: str) -> None:
        super().__init__(session, text)
        self.before = copy.deepcopy(session.document.appearance)
        work = copy.deepcopy(session.document)
        change(work)
        self.after = copy.deepcopy(work.appearance)

    @property
    def changes_anything(self) -> bool:
        """False when the change left the appearance as it was."""
        return bool(self.before != self.after)

    def apply(self) -> None:
        """Store the new appearance."""
        self.session.document.appearance = copy.deepcopy(self.after)

    def revert(self) -> None:
        """Store the old appearance."""
        self.session.document.appearance = copy.deepcopy(self.before)

    def redo(self) -> None:
        """Draw the part again."""
        self.apply()
        self.session.display_changed.emit()

    def undo(self) -> None:
        """Draw the part again as before."""
        self.revert()
        self.session.display_changed.emit()


def push(session: Any, change: Callable[[Document], object], text: str) -> bool:
    """Make an appearance change as one undo step. False when nothing changed."""
    command = SetAppearance(session, change, text)
    if not command.changes_anything:
        return False
    session.undo.push(command)
    return True


def _active_configuration(doc: Document) -> str | None:
    from fdcad.core import configurations as configs

    return configs.active_name(doc) if doc.configurations else None


class DisplayStatesDialog(QDialog):
    """The list of display states with Save Current, Apply, Delete and Link."""

    def __init__(self, window: MainWindow, tab: DocumentTab, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        self.main, self.tab = window, tab
        #: Asks for a name: (title, prompt, start) to (text, ok). Tests replace it.
        self.ask_name: Callable[[str, str, str], tuple[str, bool]] = self._ask
        layout = QHBoxLayout(self)
        left = QVBoxLayout()
        self.list = QListWidget()
        left.addWidget(self.list, 1)
        self.message = QLabel()
        self.message.setWordWrap(True)
        left.addWidget(self.message)
        layout.addLayout(left, 1)
        side = QVBoxLayout()
        self.buttons: dict[str, QPushButton] = {}
        for label, slot in (
            (SAVE, self.save),
            (APPLY, self.apply_selected),
            (DELETE, self.delete_selected),
            (LINK, self.link_selected),
            (UNLINK, self.unlink),
            (CLOSE, self.accept),
        ):
            button = QPushButton(label)
            button.clicked.connect(lambda _c=False, s=slot: s())
            side.addWidget(button)
            self.buttons[label] = button
        side.addStretch(1)
        layout.addLayout(side)
        self.refresh()

    def _ask(self, title: str, prompt: str, text: str) -> tuple[str, bool]:
        answer, ok = QInputDialog.getText(self, title, prompt, text=text)
        return str(answer), bool(ok)

    @property
    def doc(self) -> Document:
        """The part's document."""
        return self.tab.session.document

    def refresh(self) -> None:
        """List the states and say what the active configuration shows."""
        keep = self.selected()
        self.list.clear()
        for name in ds.names(self.doc):
            self.list.addItem(name)
            if name == keep:
                self.list.setCurrentRow(self.list.count() - 1)
        config = _active_configuration(self.doc)
        has = bool(ds.names(self.doc))
        for label in (APPLY, DELETE, LINK):
            self.buttons[label].setEnabled(has)
        self.buttons[LINK].setEnabled(has and config is not None)
        linked = ds.linked(self.doc, config) if config is not None else None
        self.buttons[UNLINK].setEnabled(linked is not None)
        if not has:
            self.message.setText(NONE_YET)
        elif config is not None:
            text = LINKED.format(config=config, state=linked) if linked else None
            self.message.setText(text or NOT_LINKED.format(config=config))
        else:
            self.message.clear()

    def selected(self) -> str | None:
        """The selected state's name."""
        item = self.list.currentItem() if hasattr(self, "list") else None
        return item.text() if item is not None else None

    def save(self, name: str | None = None) -> bool:
        """Save the bodies' display now under a name (asked when None)."""
        if name is None:
            n = len(ds.names(self.doc)) + 1
            text, ok = self.ask_name(TITLE, SAVE_PROMPT, f"State {n}")
            if not ok:
                return False
            name = text
        try:
            clean = ds.check_name(self.doc, name, keep=" ".join(name.split()))
        except ds.DisplayStateError as exc:
            self.message.setText(str(exc))
            return False
        done = push(self.tab.session, lambda d: ds.save(d, clean), f"Save Display State {clean}")
        self.refresh()
        return done

    def apply_selected(self) -> bool:
        """Show the selected state."""
        name = self.selected()
        if name is None:
            return False
        done = push(self.tab.session, lambda d: ds.apply(d, name), f"Apply Display State {name}")
        self.refresh()
        return done

    def delete_selected(self) -> bool:
        """Delete the selected state and its links."""
        name = self.selected()
        if name is None:
            return False
        done = push(self.tab.session, lambda d: ds.delete(d, name), f"Delete Display State {name}")
        self.refresh()
        return done

    def link_selected(self) -> bool:
        """Link the active configuration to the selected state."""
        name = self.selected()
        config = _active_configuration(self.doc)
        if name is None or config is None:
            return False
        done = push(
            self.tab.session, lambda d: ds.link(d, config, name), f"Link Display State {name}"
        )
        self.refresh()
        return done

    def unlink(self) -> bool:
        """Unlink the active configuration."""
        config = _active_configuration(self.doc)
        if config is None:
            return False
        done = push(self.tab.session, lambda d: ds.link(d, config, None), "Unlink Display State")
        self.refresh()
        return done


def run(window: MainWindow) -> bool:
    """View > Display States for the active part."""
    tab = window.current
    if tab is None:
        window.status.setText(NO_PART)
        return False
    dialog = DisplayStatesDialog(window, tab, window)
    try:
        dialog.exec()
    finally:
        dialog.deleteLater()
    return True


def after_configuration(session: Any, configuration: str) -> bool:
    """Show the state linked to a configuration that just became active (one more undo
    step). False when it has none."""
    if ds.linked(session.document, configuration) is None:
        return False
    return push(
        session,
        lambda d: ds.apply_linked(d, configuration),
        f"Display State of {configuration}",
    )
