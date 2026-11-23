"""Rules and Themes of the design table (TR331, D2103).

Two tables: rules (on, if, test, value, then, choices), run top to bottom, and themes
(theme, value, typed text). OK stores both as one undoable step.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from fdcad.core import config_rules
from fdcad.ui import strings_config as text
from fdcad.ui.equations.commands import DocumentChange

if TYPE_CHECKING:
    from fdcad.core.document.model import Document
    from fdcad.ui.session import DocumentSession

#: Rule table columns.
ON, IF, TEST, VALUE, THEN, CHOICES = range(6)


class RulesDialog(QDialog):
    """Edits the part's configuration rules and themes."""

    def __init__(self, session: DocumentSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from fdcad.ui.equations.table_dialog import column_choices, column_title

        self.setObjectName("config_rules_dialog")
        self.setWindowTitle(text.RULES_TITLE)
        self.session = session
        doc = session.document
        self.paths = [p for p in column_choices(session) if not p.startswith(("config.", "prop."))]
        self.titles = {p: column_title(doc, p) for p in self.paths}
        self.rules = QTableWidget(0, 6)
        self.rules.setObjectName("config_rules")
        self.rules.setHorizontalHeaderLabels(text.RULES_HEADERS)
        self.themes = QTableWidget(0, 3)
        self.themes.setObjectName("config_themes")
        self.themes.setHorizontalHeaderLabels(text.THEMES_HEADERS)
        tabs = QTabWidget()
        tabs.addTab(self._page(self.rules, text.RULES_HELP, "rule"), text.RULES_TAB)
        tabs.addTab(self._page(self.themes, text.THEMES_HELP, "theme"), text.THEMES_TAB)
        self.message = QLabel()
        self.message.setObjectName("config_rules_message")
        self.message.setWordWrap(True)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(tabs, 1)
        layout.addWidget(self.message)
        layout.addWidget(buttons)
        self.resize(760, 420)
        for rule in config_rules.rules(doc):
            self.add_rule(rule)
        for name, values in config_rules.themes(doc).items():
            for path, typed in values.items():
                self.add_theme_value(name, path, typed)

    def _page(self, table: QTableWidget, help_text: str, kind: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        note = QLabel(help_text)
        note.setWordWrap(True)
        layout.addWidget(table, 1)
        layout.addWidget(note)
        grid = QGridLayout()
        add = self.add_rule if kind == "rule" else self.add_theme_value
        actions: list[tuple[str, str, Any]] = [
            ("add", text.RULES_ADD if kind == "rule" else text.THEMES_ADD, lambda: add()),
            ("delete", text.RULES_DELETE, lambda: table.removeRow(table.currentRow())),
        ]
        if kind == "rule":
            actions += [
                ("up", text.RULES_UP, lambda: self.move_rule(-1)),
                ("down", text.RULES_DOWN, lambda: self.move_rule(1)),
            ]
        for i, (key, label, slot) in enumerate(actions):
            button = QPushButton(label)
            button.setObjectName(f"{kind}_{key}")
            button.clicked.connect(lambda _c=False, slot=slot: slot())
            grid.addWidget(button, 0, i)
        layout.addLayout(grid)
        return page

    def _path_box(self, path: str) -> QComboBox:
        box = QComboBox()
        for p in self.paths:
            box.addItem(self.titles[p], p)
        index = box.findData(path)
        box.setCurrentIndex(max(index, 0))
        return box

    # Rules ------------------------------------------------------------------------------

    def add_rule(self, rule: dict[str, Any] | None = None) -> int:
        """Add a rule row (empty, or showing ``rule``). Returns its row."""
        rule = rule or {}
        r = self.rules.rowCount()
        self.rules.insertRow(r)
        on = QTableWidgetItem()
        on.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        on.setCheckState(Qt.CheckState.Unchecked if rule.get("off") else Qt.CheckState.Checked)
        self.rules.setItem(r, ON, on)
        self.rules.setCellWidget(r, IF, self._path_box(str(rule.get("if", ""))))
        test = QComboBox()
        test.addItems(list(config_rules.TESTS))
        test.setCurrentText(str(rule.get("test", ">")))
        self.rules.setCellWidget(r, TEST, test)
        self.rules.setItem(r, VALUE, QTableWidgetItem(str(rule.get("value", ""))))
        self.rules.setCellWidget(r, THEN, self._path_box(str(rule.get("then", ""))))
        choices = ", ".join(str(c) for c in rule.get("choices", []))
        self.rules.setItem(r, CHOICES, QTableWidgetItem(choices))
        return r

    def set_rule_cell(self, row: int, column: int, value: str) -> None:
        """Type or pick a value in a rule cell (a seam for tests)."""
        widget = self.rules.cellWidget(row, column)
        if isinstance(widget, QComboBox):
            index = widget.findData(value)
            if index >= 0:
                widget.setCurrentIndex(index)
            else:
                widget.setCurrentText(value)
        elif column == ON:
            item = self.rules.item(row, ON)
            if item is not None:
                on = value.lower() in ("1", "true", "yes", "on")
                item.setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
        else:
            self.rules.setItem(row, column, QTableWidgetItem(value))

    def move_rule(self, step: int) -> None:
        """Move the current rule up or down (rules run top to bottom)."""
        r = self.rules.currentRow()
        target = r + step
        if r < 0 or not 0 <= target < self.rules.rowCount():
            return
        all_rules = self.edited_rules()
        all_rules[r], all_rules[target] = all_rules[target], all_rules[r]
        self.rules.setRowCount(0)
        for rule in all_rules:
            self.add_rule(rule)
        self.rules.setCurrentCell(target, VALUE)

    def edited_rules(self) -> list[dict[str, Any]]:
        """The rules as edited, in order."""
        out = []
        for r in range(self.rules.rowCount()):
            if_box, test_box, then_box = (self.rules.cellWidget(r, c) for c in (IF, TEST, THEN))
            on, value, choices = (self.rules.item(r, c) for c in (ON, VALUE, CHOICES))
            rule: dict[str, Any] = {
                "if": if_box.currentData() if isinstance(if_box, QComboBox) else "",
                "test": test_box.currentText() if isinstance(test_box, QComboBox) else ">",
                "value": value.text().strip() if value is not None else "",
                "then": then_box.currentData() if isinstance(then_box, QComboBox) else "",
                "choices": [
                    c.strip() for c in (choices.text() if choices else "").split(",") if c.strip()
                ],
            }
            if on is not None and on.checkState() != Qt.CheckState.Checked:
                rule["off"] = True
            out.append(rule)
        return out

    # Themes -----------------------------------------------------------------------------

    def add_theme_value(self, name: str = "", path: str = "", typed: str = "") -> int:
        """Add a theme row: the theme's name, a value it sets and the typed text."""
        r = self.themes.rowCount()
        self.themes.insertRow(r)
        self.themes.setItem(r, 0, QTableWidgetItem(name))
        self.themes.setCellWidget(r, 1, self._path_box(path))
        self.themes.setItem(r, 2, QTableWidgetItem(typed))
        return r

    def edited_themes(self) -> dict[str, dict[str, str]]:
        """The themes as edited: name to values."""
        out: dict[str, dict[str, str]] = {}
        for r in range(self.themes.rowCount()):
            name_item, typed_item = self.themes.item(r, 0), self.themes.item(r, 2)
            box = self.themes.cellWidget(r, 1)
            name = name_item.text().strip() if name_item is not None else ""
            typed = typed_item.text().strip() if typed_item is not None else ""
            if not typed and not name:
                continue
            path = box.currentData() if isinstance(box, QComboBox) else ""
            out.setdefault(name, {})[str(path)] = typed
        return out

    def accept(self) -> None:
        """Store the rules and themes as one undoable step, or say what is wrong."""
        rules, themes = self.edited_rules(), self.edited_themes()

        def change(d: Document) -> None:
            config_rules.set_rules(d, rules)
            config_rules.set_themes(d, themes)

        try:
            command = DocumentChange(self.session, text.RULES_UNDO, change)
        except config_rules.RuleError as exc:
            self.message.setText(str(exc))
            return
        if command.changes_anything:
            self.session.undo.push(command)
        super().accept()
