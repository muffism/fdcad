"""The Sheet Metal Rules window (TR332, DECISIONS D1111).

Lists the named rules of the shared rule library file. Save Current saves the part's
Sheet Metal values as a rule, Delete removes one, Library File picks another shared
file, and Apply copies the picked rule into the part's Sheet Metal folder (one undo
step, done by ``flow.sheet_rules`` after the window closes).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.document.model import Feature
from fdcad.core.features.sheetmetal.rules import RuleError, load_rules, rule_of, save_rules
from fdcad.ui import strings_sheetmetal as text


class SheetRulesDialog(QDialog):
    """Pick, save and delete named sheet metal rules."""

    def __init__(self, path: str, folder: Feature, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sheet_rules_dialog")
        self.setWindowTitle(text.RULES_TITLE)
        self.path = path
        self.folder = folder
        self.rules: dict[str, dict[str, Any]] = {}
        self.chosen: str | None = None
        layout = QVBoxLayout(self)
        self.file_label = QLabel("")
        self.file_label.setWordWrap(True)
        layout.addWidget(self.file_label)
        self.list = QListWidget()
        self.list.setObjectName("sheet_rules_list")
        layout.addWidget(self.list)
        self.info = QLabel("")
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        row = QHBoxLayout()
        buttons = (
            (text.RULES_APPLY, self.apply_picked),
            (text.RULES_SAVE, self.save_current),
            (text.RULES_DELETE, self.delete_picked),
            (text.RULES_LIBRARY, self.choose_library),
            (text.RULES_CLOSE, self.reject),
        )
        for label, slot in buttons:
            button = QPushButton(label)
            button.clicked.connect(slot)
            row.addWidget(button)
        layout.addLayout(row)
        self.reload()

    def reload(self) -> None:
        """Read the library file again and list its rules."""
        self.file_label.setText(text.RULES_FILE.format(name=Path(self.path).name))
        try:
            self.rules = load_rules(self.path)
        except RuleError as exc:
            self.rules = {}
            self.info.setText(str(exc))
        self.list.clear()
        current = self.folder.params.get("rule_name")
        for name in sorted(self.rules):
            self.list.addItem(name)
            if name == current:
                self.list.setCurrentRow(self.list.count() - 1)

    def picked(self) -> str | None:
        """The rule picked in the list."""
        item = self.list.currentItem()
        return item.text() if item is not None else None

    def apply_picked(self) -> None:
        """Close the window and apply the picked rule."""
        name = self.picked()
        if name is None:
            self.info.setText(text.RULES_PICK)
            return
        self.chosen = name
        self.accept()

    def save_current(self, name: str | None = None) -> bool:
        """Save the part's Sheet Metal values as a rule (asks for the name)."""
        if not isinstance(name, str):
            name, ok = QInputDialog.getText(self, text.RULES_SAVE, text.RULES_NAME)
            if not ok:
                return False
        name = name.strip()
        if not name:
            self.info.setText(text.RULES_NO_NAME)
            return False
        rules = dict(self.rules)
        rules[name] = rule_of(self.folder)
        return self._write(rules)

    def delete_picked(self) -> bool:
        """Delete the picked rule from the library."""
        name = self.picked()
        if name is None:
            self.info.setText(text.RULES_PICK)
            return False
        rules = {k: v for k, v in self.rules.items() if k != name}
        return self._write(rules)

    def choose_library(self) -> None:
        """Pick another shared library file."""
        path, _ = QFileDialog.getSaveFileName(
            self, text.RULES_LIBRARY, self.path, text.RULES_FILTER
        )
        if path:
            self.path = path
            self.reload()

    def _write(self, rules: dict[str, dict[str, Any]]) -> bool:
        try:
            save_rules(self.path, rules)
        except RuleError as exc:
            self.info.setText(str(exc))
            return False
        self.reload()
        return True
