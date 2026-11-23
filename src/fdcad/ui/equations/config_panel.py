"""Configurations tab: create, rename, switch and delete configurations (P4.10 item 2).

Every change is one undoable command (``DocumentChange``) and the part
rebuilds on the worker thread. Double click a configuration to show it; edit
its name in place to rename it.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fdcad.core import configurations as configs
from fdcad.ui import strings_config as text
from fdcad.ui.equations.commands import DocumentChange

if TYPE_CHECKING:
    from collections.abc import Callable

    from fdcad.core.document.model import Document
    from fdcad.ui.session import DocumentSession

_NAME_ROLE = Qt.ItemDataRole.UserRole


class ConfigurationsPanel(QWidget):
    """Lists the part's configurations, with the active one in bold."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("configurations_panel")
        self.session: DocumentSession | None = None
        self.list = QListWidget()
        self.list.setObjectName("configurations_list")
        self.list.itemDoubleClicked.connect(self._double_clicked)
        self.list.itemChanged.connect(self._renamed)
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.message = QLabel()
        self.message.setObjectName("configurations_message")
        self.message.setWordWrap(True)
        self.buttons: dict[str, QPushButton] = {}
        grid = QGridLayout()
        for i, (key, label, slot) in enumerate(
            (
                ("add", text.CONFIG_ADD, self.add),
                ("add_linked", text.CONFIG_ADD_LINKED, self.add_linked),  # TR195
                ("show", text.CONFIG_ACTIVATE, self.activate_selected),
                ("rename", text.CONFIG_RENAME, self.rename_selected),
                ("delete", text.CONFIG_DELETE, self.delete_selected),
                ("table", text.CONFIG_TABLE, self.open_table),
                ("preview", text.CONFIG_PREVIEW, self.preview_selected),  # TR197
                ("colours", text.CONFIG_COLOURS_BUTTON, self.toggle_colours),
            )
        ):
            button = QPushButton(label)
            button.setObjectName(f"config_{key}")
            if key == "colours":
                button.setToolTip(text.CONFIG_COLOURS_TIP)
            button.clicked.connect(lambda _c=False, slot=slot: slot())
            self.buttons[key] = button
            grid.addWidget(button, i // 2, i % 2)
        layout = QVBoxLayout(self)
        layout.addWidget(self.list, 1)
        layout.addWidget(self.info)
        layout.addLayout(grid)
        layout.addWidget(self.message)
        self._filling = False
        self.table_opener: Callable[[], object] | None = None

    def set_session(self, session: DocumentSession | None) -> None:
        """Show ``session``'s configurations."""
        if self.session is not None:
            with contextlib.suppress(RuntimeError, TypeError):
                self.session.undo.indexChanged.disconnect(self.refresh)
        self.session = session
        if session is not None:
            session.undo.indexChanged.connect(self.refresh)
        self.refresh()

    @property
    def doc(self) -> Document | None:
        """The shown part."""
        return self.session.document if self.session is not None else None

    def refresh(self, *_args: object) -> None:
        """Fill the list from the document."""
        self._filling = True
        self.list.clear()
        doc = self.doc
        if doc is not None:
            active = configs.active_name(doc)
            for item in configs.items(doc):
                name = str(item["name"])
                label = text.CONFIG_ACTIVE.format(name=name) if name == active else name
                parent = item.get("parent")
                if isinstance(parent, str):  # TR195: linked, and how many own values
                    label += " " + text.CONFIG_LINKED.format(
                        parent=parent, n=len(configs.own_paths(doc, name))
                    )
                row = QListWidgetItem(label)
                row.setData(_NAME_ROLE, name)
                if item.get("description"):  # TR90 item 1 (D2100)
                    row.setToolTip(str(item["description"]))
                row.setFlags(row.flags() | Qt.ItemFlag.ItemIsEditable)
                if name == active:
                    font = row.font()
                    font.setBold(True)
                    row.setFont(font)
                    self.list.setCurrentItem(row)
                self.list.addItem(row)
            self.info.setText(text.CONFIG_OVERRIDES.format(count=len(configs.kept_paths(doc))))
        self._filling = False

    def selected(self) -> str | None:
        """The selected configuration's name."""
        item = self.list.currentItem()
        name = item.data(_NAME_ROLE) if item is not None else None
        return name if isinstance(name, str) else None

    def _push(self, label: str, change: Callable[[Document], object]) -> bool:
        session = self.session
        if session is None:
            return False
        try:

            def run(d: Document) -> None:
                change(d)

            command = DocumentChange(session, label, run)
        except configs.ConfigurationError as exc:
            self.message.setText(str(exc))
            return False
        self.message.clear()
        if command.changes_anything:
            session.undo.push(command)
        self.refresh()
        return True

    def add(self, name: str | None = None) -> str | None:
        """Add a configuration with the active values and show it."""
        doc = self.doc
        if doc is None:
            return None
        if not name:
            n = len(configs.names(doc)) + 1
            while text.CONFIG_NEW_NAME.format(n=n) in configs.names(doc):
                n += 1
            name = text.CONFIG_NEW_NAME.format(n=n)
        clean = name

        def change(d: Document) -> None:
            nonlocal clean
            clean = configs.add(d, name)
            configs.activate(d, clean)

        if not self._push(text.CONFIG_UNDO_ADD.format(name=name), change):
            return None
        return clean

    def add_linked(self, name: str | None = None) -> str | None:
        """Add a configuration linked to the active one (TR195) and show it."""
        doc = self.doc
        if doc is None:
            return None
        if not name:
            n = len(configs.names(doc)) + 1
            while text.CONFIG_NEW_NAME.format(n=n) in configs.names(doc):
                n += 1
            name = text.CONFIG_NEW_NAME.format(n=n)
        clean = name

        def change(d: Document) -> None:
            nonlocal clean
            clean = configs.add_linked(d, name)
            configs.activate(d, clean)

        if not self._push(text.CONFIG_UNDO_ADD.format(name=name), change):
            return None
        return clean

    def activate(self, name: str) -> bool:
        """Show configuration ``name`` (one undo step; the part rebuilds)."""
        doc = self.doc
        if doc is None or name == configs.active_name(doc):
            return False
        from fdcad.core import display_states

        session = self.session
        linked = session is not None and display_states.linked(doc, name) is not None
        label = text.CONFIG_UNDO_SWITCH.format(name=name)
        if linked:  # TR88: the configuration's display state comes in the same step
            session.undo.beginMacro(label)  # type: ignore[union-attr]
        try:
            done = self._push(label, lambda d: configs.activate(d, name))
            if done and linked:
                from fdcad.ui.main_window.display_states_ui import after_configuration

                after_configuration(session, name)
        finally:
            if linked:
                session.undo.endMacro()  # type: ignore[union-attr]
        return done

    def activate_selected(self) -> None:
        """Show the selected configuration."""
        name = self.selected()
        if name is not None:
            self.activate(name)

    def rename(self, old: str, new: str) -> bool:
        """Rename a configuration."""
        return self._push(
            text.CONFIG_UNDO_RENAME.format(name=old), lambda d: configs.rename(d, old, new)
        )

    def rename_selected(self) -> None:
        """Start editing the selected name in place."""
        item = self.list.currentItem()
        if item is not None:
            self._filling = True
            item.setText(str(item.data(_NAME_ROLE)))
            self._filling = False
            self.list.editItem(item)

    def delete(self, name: str) -> bool:
        """Delete a configuration."""
        return self._push(
            text.CONFIG_UNDO_DELETE.format(name=name), lambda d: configs.delete(d, name)
        )

    def delete_selected(self) -> None:
        """Delete the selected configuration."""
        name = self.selected()
        if name is not None:
            self.delete(name)

    def preview_selected(self) -> Any:
        """Show the selected configuration in a small window without making it active
        (TR197, D2101). Returns the window, or None."""
        from fdcad.ui.equations.config_preview import ConfigPreview

        name = self.selected()
        if self.session is None or name is None:
            self.message.setText(text.CONFIG_PREVIEW_PICK)
            return None
        window = ConfigPreview(self.session, name, self)
        window.show()
        self.previews = [*getattr(self, "previews", [])[-3:], window]
        return window

    def toggle_colours(self) -> bool:
        """Turn Colours by Configuration on or off (TR197, D2101). Returns the new state."""
        from fdcad.core import config_preview

        doc = self.doc
        if doc is None:
            return False
        on = not config_preview.colours_vary(doc)
        if self._push(text.CONFIG_UNDO_COLOURS, lambda d: config_preview.set_colours_vary(d, on)):
            self.message.setText(text.CONFIG_COLOURS_ON if on else text.CONFIG_COLOURS_OFF)
        return on

    def open_table(self) -> None:
        """Open the design table editor."""
        if self.table_opener is not None:
            self.table_opener()

    def _double_clicked(self, item: QListWidgetItem) -> None:
        name = item.data(_NAME_ROLE)
        if isinstance(name, str):
            self.activate(name)

    def _renamed(self, item: QListWidgetItem) -> None:
        if self._filling:
            return
        old = item.data(_NAME_ROLE)
        new = item.text().strip()
        if not isinstance(old, str) or new in (old, text.CONFIG_ACTIVE.format(name=old)):
            self.message.clear()  # an earlier refusal no longer applies
            self.refresh()
            return
        if not self.rename(old, new):
            self.refresh()
