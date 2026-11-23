"""Shortcut, gesture and shortcut bar editors for the preferences dialog (PLAN 8 item 16)."""

from __future__ import annotations

import sys

from PySide6.QtCore import QKeyCombination, Qt, Signal
from PySide6.QtGui import QGuiApplication, QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fdcad.ui import strings, strings_extra
from fdcad.ui.input.commands import (
    BY_ID,
    COMMANDS,
    DIRECTIONS_4,
    DIRECTIONS_8,
    ShortcutMap,
    key_text,
    search_words,
)
from fdcad.ui.preferences.settings import Settings

_CONTEXTS = {"part": strings.CONTEXT_PART, "sketch": strings.CONTEXT_SKETCH}


class KeyCapture(QLineEdit):
    """Takes one key press with its modifiers (T14.7.4).

    The key comes from the key code and the Ctrl, Shift, Alt and Meta modifiers
    only, never from the typed text, so Caps Lock never acts as Shift and letters
    always show in upper case.
    """

    keySequenceChanged = Signal(QKeySequence)  # noqa: N815  (same name as QKeySequenceEdit)

    _MODIFIER_KEYS = (
        Qt.Key.Key_Control,
        Qt.Key.Key_Shift,
        Qt.Key.Key_Alt,
        Qt.Key.Key_Meta,
        Qt.Key.Key_CapsLock,
        Qt.Key.Key_AltGr,
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("key_capture")
        self.setReadOnly(True)
        self.setPlaceholderText(strings_extra.PRESS_A_KEY)
        self._sequence = QKeySequence()

    def keySequence(self) -> QKeySequence:  # noqa: N802
        """The captured key."""
        return self._sequence

    def setKeySequence(self, sequence: QKeySequence) -> None:  # noqa: N802
        """Show a key as if it was pressed."""
        self._sequence = sequence
        self.setText(key_text(sequence.toString(QKeySequence.SequenceFormat.NativeText)))
        self.keySequenceChanged.emit(sequence)

    def clear(self) -> None:
        """Forget the captured key."""
        self._sequence = QKeySequence()
        super().clear()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Capture the key; modifier keys alone and Caps Lock are ignored."""
        key = event.key()
        if key in self._MODIFIER_KEYS or key == Qt.Key.Key_unknown:
            event.accept()
            return
        mods = event.modifiers() & (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.ShiftModifier
            | Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.MetaModifier
        )
        self.setKeySequence(QKeySequence(QKeyCombination(mods, Qt.Key(key))))
        event.accept()


class ShortcutEditor(QWidget):
    """Commands with category, shortcuts and search words (T14.7).

    A search box and a category list narrow the table. Assigning a key in use
    asks first and then moves it. Remove Shortcut, Reset to Defaults (shortcuts
    only, or everything) and Copy List sit below.
    """

    #: The user chose Reset to Defaults for everything: gestures and the bar too.
    reset_everything = Signal()

    COLUMNS = 4  # category, command, shortcut, search words

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.map = ShortcutMap(dict(settings.shortcut_overrides), mac=sys.platform == "darwin")
        self.words: dict[str, str] = dict(settings.search_words)
        self.search = QLineEdit()
        self.search.setPlaceholderText(strings.SEARCH_COMMANDS)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _t: self._filter())
        self.category = QComboBox()
        self.category.setObjectName("shortcut_category")
        self.category.addItem(strings_extra.CATEGORY_ALL, "")
        for group in dict.fromkeys(c.group for c in COMMANDS):
            self.category.addItem(strings_extra.CATEGORY_NAMES.get(group, group), group)
        self.category.currentIndexChanged.connect(lambda _i: self._filter())
        self.table = QTableWidget(0, self.COLUMNS)
        self.table.setHorizontalHeaderLabels(strings_extra.SHORTCUT_COLUMNS)
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.EditKeyPressed
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.currentCellChanged.connect(lambda *_: self._row_changed())
        self.table.itemChanged.connect(self._item_changed)
        self.keys = KeyCapture()
        self.keys.keySequenceChanged.connect(self._check)
        self.warning = QLabel()
        self.warning.setWordWrap(True)
        self.assign = QPushButton(strings.ASSIGN)
        self.assign.clicked.connect(lambda: self.assign_current())
        self.clear = QPushButton(strings_extra.REMOVE_SHORTCUT)
        self.clear.clicked.connect(self.clear_current)
        self.reset = QPushButton(strings_extra.RESET_DEFAULTS)
        self.reset.clicked.connect(lambda: self.ask_reset())
        self.copy = QPushButton(strings_extra.COPY_LIST)
        self.copy.clicked.connect(self.copy_list)
        top = QHBoxLayout()
        top.addWidget(self.search, 1)
        top.addWidget(self.category)
        row = QHBoxLayout()
        row.addWidget(self.keys, 1)
        row.addWidget(self.assign)
        row.addWidget(self.clear)
        row.addWidget(self.reset)
        row.addWidget(self.copy)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.table, 1)
        layout.addLayout(row)
        layout.addWidget(self.warning)
        self._filling = False
        self._fill()

    def _fill(self) -> None:
        self._filling = True
        self.table.setRowCount(len(COMMANDS))
        for i, cmd in enumerate(COMMANDS):
            group = QTableWidgetItem(strings_extra.CATEGORY_NAMES.get(cmd.group, cmd.group))
            group.setData(Qt.ItemDataRole.UserRole, cmd.group)
            name = QTableWidgetItem(cmd.label)
            name.setData(Qt.ItemDataRole.UserRole, cmd.id)
            keys = QTableWidgetItem(self._text(cmd.id))
            words = QTableWidgetItem(search_words(cmd.id, self.words))
            for item in (group, name, keys):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            for col, item in enumerate((group, name, keys, words)):
                self.table.setItem(i, col, item)
        self.table.resizeColumnsToContents()
        self._filling = False

    def _text(self, cid: str) -> str:
        return ", ".join(
            key_text(QKeySequence(k).toString(QKeySequence.SequenceFormat.NativeText))
            for k in self.map.keys(cid)
        )

    def _refresh_keys(self) -> None:
        self._filling = True
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 1)
            cell = self.table.item(i, 2)
            words = self.table.item(i, 3)
            if item is not None and cell is not None:
                cid = str(item.data(Qt.ItemDataRole.UserRole))
                cell.setText(self._text(cid))
                if words is not None:
                    words.setText(search_words(cid, self.words))
        self._filling = False

    def _item_changed(self, item: QTableWidgetItem) -> None:
        """Typing in the search words column stores the words (T14.7.2)."""
        if self._filling or item.column() != 3:
            return
        name = self.table.item(item.row(), 1)
        if name is None:
            return
        cid = str(name.data(Qt.ItemDataRole.UserRole))
        self.set_words(cid, item.text())

    def set_words(self, cid: str, words: str) -> None:
        """Give a command its search words (the defaults again when they match)."""
        clean = " ".join(words.split())
        if clean == search_words(cid):
            self.words.pop(cid, None)
        else:
            self.words[cid] = clean
        self._refresh_keys()

    def _filter(self) -> None:
        needle = self.search.text().strip().lower()
        group = str(self.category.currentData() or "")
        for i in range(self.table.rowCount()):
            cells = [self.table.item(i, c) for c in range(self.COLUMNS)]
            hay = " ".join(c.text() for c in cells if c is not None).lower()
            row_group = cells[0].data(Qt.ItemDataRole.UserRole) if cells[0] is not None else ""
            hidden = (bool(needle) and needle not in hay) or (bool(group) and row_group != group)
            self.table.setRowHidden(i, hidden)

    def visible_ids(self) -> list[str]:
        """Command ids of the rows the search and category leave shown."""
        out = []
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 1)
            if item is not None and not self.table.isRowHidden(i):
                out.append(str(item.data(Qt.ItemDataRole.UserRole)))
        return out

    def current(self) -> str | None:
        """Id of the selected command."""
        item = self.table.item(self.table.currentRow(), 1)
        return str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else None

    def select(self, cid: str) -> None:
        """Select a command's row."""
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 1)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == cid:
                self.table.setCurrentCell(i, 1)

    def _row_changed(self) -> None:
        self.keys.clear()
        self.warning.setText("")

    def _key_text(self) -> str:
        return self.keys.keySequence().toString(QKeySequence.SequenceFormat.PortableText)

    def _check(self, *_args: object) -> None:
        key, cid = self._key_text(), self.current()
        owners = [o for o in self.map.owners(key) if o != cid] if key else []
        if owners:
            names = ", ".join(BY_ID[o].label for o in owners)
            self.warning.setText(strings.SHORTCUT_IN_USE.format(key=key_text(key), names=names))
        else:
            self.warning.setText("")

    def assign_current(self, key: str | None = None) -> dict[str, str]:
        """Give the selected command the typed key (added to its shortcuts).

        A key in use asks first; Yes moves it from the other command (T14.7.3).
        Returns the commands that lost it, or nothing when the user said No.
        """
        cid = self.current()
        key = key if isinstance(key, str) else self._key_text()
        if cid is None or not key:
            return {}
        owners = [o for o in self.map.owners(key) if o != cid]
        if owners:
            names = ", ".join(BY_ID[o].label for o in owners)
            answer = QMessageBox.question(
                self,
                strings_extra.KEY_IN_USE_TITLE,
                strings_extra.KEY_IN_USE.format(
                    key=key_text(key), names=names, command=BY_ID[cid].label
                ),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return {}
        lost = self.map.set(cid, [*self.map.keys(cid), key])
        self._refresh_keys()
        if lost:
            names = ", ".join(BY_ID[o].label for o in lost)
            self.warning.setText(strings.SHORTCUT_MOVED.format(key=key_text(key), names=names))
        return lost

    def clear_current(self) -> None:
        """Remove Shortcut: the selected command keeps no key."""
        cid = self.current()
        if cid is not None:
            self.map.set(cid, [])
            self._refresh_keys()

    def ask_reset(self) -> str | None:
        """Reset to Defaults: asks for shortcuts only or everything. Returns the choice."""
        box = QMessageBox(self)
        box.setWindowTitle(strings_extra.RESET_DEFAULTS)
        box.setText(strings_extra.RESET_QUESTION)
        only = box.addButton(strings_extra.RESET_SHORTCUTS_ONLY, QMessageBox.ButtonRole.AcceptRole)
        every = box.addButton(
            strings_extra.RESET_EVERYTHING, QMessageBox.ButtonRole.DestructiveRole
        )
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        clicked = box.clickedButton()
        choice = "shortcuts" if clicked is only else "everything" if clicked is every else None
        box.deleteLater()  # closed boxes stayed alive (D637)
        if choice is not None:
            self.reset_to_defaults(choice)
        return choice

    def reset_to_defaults(self, scope: str = "shortcuts") -> None:
        """Back to SHORTCUTS.md; with ``"everything"`` also search words, gestures and the bar."""
        self.map.reset()
        if scope == "everything":
            self.words = {}
            self.reset_everything.emit()
        self._refresh_keys()

    def reset_all(self) -> None:
        """Back to the default shortcuts (kept for older callers)."""
        self.reset_to_defaults("shortcuts")

    def list_text(self) -> str:
        """The command list as plain text: category, command and shortcut per line."""
        lines = []
        for cmd in COMMANDS:
            category = strings_extra.CATEGORY_NAMES.get(cmd.group, cmd.group)
            lines.append(f"{category}\t{cmd.label}\t{self._text(cmd.id)}")
        return "\n".join(lines) + "\n"

    def copy_list(self) -> str:
        """Copy List: put the plain text list on the clipboard (T14.7.5)."""
        text = self.list_text()
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
        return text

    def apply(self, settings: Settings) -> None:
        """Store the changes."""
        settings.shortcut_overrides = dict(self.map.overrides)
        settings.search_words = dict(self.words)


class GestureEditor(QWidget):
    """Command for each gesture direction, per context."""

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.mapping = settings.gestures
        self.sectors = QComboBox()
        self.sectors.addItem(strings.FOUR_DIRECTIONS, 4)
        self.sectors.addItem(strings.EIGHT_DIRECTIONS, 8)
        self.sectors.setCurrentIndex(self.sectors.findData(settings.gesture_directions))
        self.sectors.currentIndexChanged.connect(lambda _i: self._build())
        self.hint = QLabel(strings.GESTURE_HINT)
        self.hint.setWordWrap(True)
        self.boxes: dict[tuple[str, str], QComboBox] = {}
        self.area = QWidget()
        self.area_layout = QHBoxLayout(self.area)
        layout = QVBoxLayout(self)
        top = QFormLayout()
        top.addRow(strings.DIRECTIONS, self.sectors)
        layout.addLayout(top)
        layout.addWidget(self.hint)
        layout.addWidget(self.area, 1)
        self._build()

    def _build(self) -> None:
        self._store()
        while self.area_layout.count():
            item = self.area_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        self.boxes = {}
        directions = DIRECTIONS_8 if self.sectors.currentData() == 8 else DIRECTIONS_4
        for context, title in _CONTEXTS.items():
            group = QGroupBox(title)
            form = QFormLayout(group)
            for direction in directions:
                box = QComboBox()
                # As wide as its card allows, not as its longest command (D2699): the
                # two cards were wider than the window, which cut the second one off.
                # The list that drops down keeps the width of the longest command.
                box.setSizeAdjustPolicy(
                    QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
                )
                box.setMinimumContentsLength(12)
                box.addItem(strings.NO_COMMAND, "")
                for cmd in COMMANDS:
                    box.addItem(f"{cmd.group}: {cmd.label}", cmd.id)
                box.view().setMinimumWidth(box.view().sizeHintForColumn(0) + 24)
                current = self.mapping.get(context, {}).get(direction, "")
                box.setCurrentIndex(max(box.findData(current), 0))
                form.addRow(strings.DIRECTION_NAMES[direction], box)
                self.boxes[(context, direction)] = box
            self.area_layout.addWidget(group)

    def _store(self) -> None:
        for (context, direction), box in self.boxes.items():
            cid = str(box.currentData() or "")
            m = self.mapping.setdefault(context, {})
            if cid:
                m[direction] = cid
            else:
                m.pop(direction, None)

    def reset(self) -> None:
        """Back to the default gestures (Reset to Defaults, everything)."""
        from fdcad.ui.input.commands import DEFAULT_GESTURES

        self.boxes = {}
        self.mapping = {k: dict(v) for k, v in DEFAULT_GESTURES.items()}
        self._build()

    def apply(self, settings: Settings) -> None:
        """Store the changes."""
        self._store()
        settings.gestures = self.mapping
        settings.gesture_directions = int(self.sectors.currentData())


class ShortcutBarEditor(QWidget):
    """Which commands the shortcut bar shows, per context."""

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        bar = settings.shortcut_bar
        self.lists: dict[str, QListWidget] = {}
        layout = QHBoxLayout(self)
        for context, title in _CONTEXTS.items():
            group = QGroupBox(title)
            inner = QVBoxLayout(group)
            items = QListWidget()
            chosen = bar.get(context, [])
            order = [*chosen, *[c.id for c in COMMANDS if c.id not in chosen]]
            for cid in order:
                cmd = BY_ID.get(cid)
                if cmd is None:
                    continue
                item = QListWidgetItem(f"{cmd.label} ({cmd.group})")
                item.setData(Qt.ItemDataRole.UserRole, cid)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.CheckState.Checked if cid in chosen else Qt.CheckState.Unchecked
                )
                items.addItem(item)
            inner.addWidget(items)
            layout.addWidget(group)
            self.lists[context] = items

    def reset(self) -> None:
        """Back to the default shortcut bar commands (Reset to Defaults, everything)."""
        from fdcad.ui.input.commands import DEFAULT_BAR

        for context, items in self.lists.items():
            chosen = DEFAULT_BAR.get(context, [])
            for i in range(items.count()):
                item = items.item(i)
                if item is not None:
                    cid = str(item.data(Qt.ItemDataRole.UserRole))
                    state = Qt.CheckState.Checked if cid in chosen else Qt.CheckState.Unchecked
                    item.setCheckState(state)

    def chosen(self, context: str) -> list[str]:
        """Checked commands of a context, in list order."""
        items = self.lists[context]
        out = []
        for i in range(items.count()):
            item = items.item(i)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                out.append(str(item.data(Qt.ItemDataRole.UserRole)))
        return out

    def apply(self, settings: Settings) -> None:
        """Store the changes."""
        settings.shortcut_bar = {context: self.chosen(context) for context in self.lists}
