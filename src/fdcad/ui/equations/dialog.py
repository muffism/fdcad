"""The equations manager (PHASE4_SPEC P4.10 item 1, PLAN Phase 4, DECISIONS D390).

Three sections: global variables, feature values (suppression formulas) and
equations (feature values set by a formula). Typing a name in an "Add" row
puts quotes round it and moves to the value cell with ``=`` filled in. Each
row shows a mark for valid text, what it evaluates to and a comment. Values
are solved on every change by the core equations engine (pure Python, so it
runs on the UI thread without kernel work). OK applies everything as one
undoable command; Cancel changes nothing.
"""

from __future__ import annotations

import contextlib
import copy
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fdcad.core import configurations as configs
from fdcad.core.equations import text_file
from fdcad.core.equations.edit import (
    EquationError,
    Row,
    RowResult,
    apply_rows,
    preview,
    quote,
    rows_for,
    unquote,
)
from fdcad.core.units import Kind
from fdcad.core.units.expressions import FUNCTION_NAMES
from fdcad.ui import strings_config as text
from fdcad.ui.equations.commands import SetEquations
from fdcad.ui.strings import clause
from fdcad.ui.themes.theme import chrome, palette

if TYPE_CHECKING:
    from fdcad.ui.session import DocumentSession

NAME, VALUE, MARK, RESULT, COMMENT = range(5)
_SECTION_ROLE = Qt.ItemDataRole.UserRole
_PLACEHOLDER_ROLE = Qt.ItemDataRole.UserRole + 1
_KIND_ROLE = Qt.ItemDataRole.UserRole + 2
#: The name a variable row had when the manager opened (None for new rows).
_ORIGINAL_ROLE = Qt.ItemDataRole.UserRole + 3
#: An equation kept but not used (TR194, D830).
_DISABLED_ROLE = Qt.ItemDataRole.UserRole + 4


def _format(result: RowResult, section: str, session: DocumentSession) -> str:
    from fdcad.ui.property_panel.panel import format_value

    if result.value is None:
        return ""
    if section == "feature":
        return text.EQ_SUPPRESSED if result.value != 0 else text.EQ_UNSUPPRESSED
    return format_value(result.value, result.kind, session.document.units)


class EquationsDialog(QDialog):
    """Edits the part's equations. Opened from Tools, Equations or the tree folder."""

    def __init__(self, session: DocumentSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("equations_dialog")
        self.setWindowTitle(text.EQUATIONS_TITLE)
        self.session = session
        self.tree = QTreeWidget()
        self.tree.setObjectName("equations_tree")
        self.tree.setColumnCount(len(text.EQ_HEADERS))
        self.tree.setHeaderLabels(text.EQ_HEADERS)
        self.tree.setColumnWidth(NAME, 170)
        self.tree.setColumnWidth(VALUE, 220)
        self.tree.setColumnWidth(MARK, 24)
        self.tree.setColumnWidth(RESULT, 110)
        # Comfort (TR194, D830): several rows at once, typing ahead in the value cell.
        from PySide6.QtWidgets import QAbstractItemView

        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        from fdcad.ui.equations.comfort import FormulaDelegate

        self.delegate = FormulaDelegate(self.names, self.tree)
        self.tree.setItemDelegateForColumn(VALUE, self.delegate)
        self.filter = QLineEdit()
        self.filter.setObjectName("equations_filter")
        self.filter.setPlaceholderText(text.EQ_FILTER)
        self.filter.setClearButtonEnabled(True)
        self.filter.setMinimumWidth(160)  # its hint text is never cut off
        self.filter.textChanged.connect(self.apply_filter)
        self.message = QLabel()
        self.message.setObjectName("equations_message")
        self.message.setWordWrap(True)
        help_text = QLabel(text.EQ_HELP.format(functions=", ".join(FUNCTION_NAMES)))
        help_text.setWordWrap(True)
        delete = QPushButton(text.EQ_DELETE)
        delete.setObjectName("equations_delete")
        delete.clicked.connect(self.delete_row)
        # The text file (TR25): export, import and a linked file.
        self.link = session.document.equations_file
        self.link_label = QLabel()
        self.link_label.setObjectName("equations_link")
        file_buttons = []
        for name, label, tip, slot in (
            ("equations_export", text.EQ_EXPORT, text.EQ_EXPORT_TIP, self.export_file),
            ("equations_import", text.EQ_IMPORT, text.EQ_IMPORT_TIP, self.import_file),
            ("equations_link_file", text.EQ_LINK, text.EQ_LINK_TIP, self.link_file),
            ("equations_unlink", text.EQ_UNLINK, text.EQ_UNLINK_TIP, self.unlink),
        ):
            button = QPushButton(label)
            button.setObjectName(name)
            button.setToolTip(tip)
            button.clicked.connect(lambda _c=False, s=slot: s())
            file_buttons.append(button)
        self.unlink_button = file_buttons[-1]
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        comfort = []
        slots: tuple[tuple[str, str, str, Callable[..., object]], ...] = (
            ("equations_disable", text.EQ_DISABLE, text.EQ_DISABLE_TIP, self.toggle_disabled),
            ("equations_sort", text.EQ_SORT, text.EQ_SORT_TIP, self.sort_rows),
            ("equations_replace", text.EQ_REPLACE, text.EQ_REPLACE_TIP, self.replace_reference),
            ("equations_allowed", text.EQ_ALLOWED, text.EQ_ALLOWED_TIP, self.edit_allowed),
            ("equations_csv", text.CSV_LOOKUP, text.CSV_LOOKUP_TIP, self.edit_lookup),  # TR198
            ("equations_type", text.VAR_TYPE, text.VAR_TYPE_TIP, self.edit_type),  # TR417
            ("equations_group", text.VAR_GROUP, text.VAR_GROUP_TIP, self.edit_group),
        )
        for name, label, tip, handler in slots:
            button = QPushButton(label)
            button.setObjectName(name)
            button.setToolTip(tip)
            button.clicked.connect(lambda _c=False, s=handler: s())
            comfort.append(button)
        top = QHBoxLayout()
        top.addWidget(self.filter, 1)
        for button in comfort:
            top.addWidget(button)
        row = QHBoxLayout()
        row.addWidget(delete)
        for button in file_buttons:
            row.addWidget(button)
        row.addStretch(1)
        row.addWidget(buttons)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.tree, 1)
        layout.addWidget(help_text)
        layout.addWidget(self.link_label)
        layout.addWidget(self.message)
        layout.addLayout(row)
        self.resize(960, 520)  # wide enough for the filter box beside the buttons (D1034)
        self.sections: dict[str, QTreeWidgetItem] = {}
        self._filling = False
        self._last_cell: tuple[QTreeWidgetItem, int] | None = None
        self.tree.itemChanged.connect(self._changed)
        self.tree.currentItemChanged.connect(self._current_changed)
        self.tree.itemDoubleClicked.connect(self._double_clicked)
        self.load()
        self._show_link()

    # Rows -------------------------------------------------------------------------

    def load(self, rows: list[Row] | None = None) -> None:
        """Fill the sections from the part, or from ``rows`` (an imported file)."""
        originals = {
            str(item.data(0, _ORIGINAL_ROLE))
            for item in (self.items() if rows is not None else [])
            if isinstance(item.data(0, _ORIGINAL_ROLE), str)
        }
        self._filling = True
        self.tree.clear()
        self.sections = {}
        for section, title in text.EQ_SECTIONS.items():
            head = QTreeWidgetItem([title])
            head.setFlags(Qt.ItemFlag.ItemIsEnabled)
            head.setData(0, _SECTION_ROLE, section)
            font = head.font(0)
            font.setBold(True)
            head.setFont(0, font)
            self.tree.addTopLevelItem(head)
            self.sections[section] = head
        from_part = rows is None
        listed = rows_for(self.session.document) if rows is None else rows
        # Variables of one group stay together, ungrouped ones first (TR417, D2104).
        groups = self._groups()
        order = {n: i for i, n in enumerate(dict.fromkeys(g for g in groups.values() if g))}
        listed = sorted(
            listed,
            key=lambda r: (
                r.section != "variable",
                order.get(groups.get(r.name, ""), -1) if r.section == "variable" else 0,
            ),
        )
        for r in listed:
            item = self._add_row(r.section, r)
            group = groups.get(r.name, "") if r.section == "variable" else ""
            if group:
                item.setToolTip(NAME, text.VAR_GROUP_SHOWN.format(group=group))
            if r.section == "variable" and (from_part or r.name in originals):
                item.setData(0, _ORIGINAL_ROLE, r.name)
        for section in self.sections:
            self._add_placeholder(section)
        self.tree.expandAll()
        self._filling = False
        self.evaluate()

    def _add_row(self, section: str, row: Row) -> QTreeWidgetItem:
        item = QTreeWidgetItem([quote(row.name), row.expr, "", "", row.comment])
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        item.setData(0, _SECTION_ROLE, section)
        self._show_disabled(item, row.disabled)
        if row.kind is not None:
            item.setData(0, _KIND_ROLE, row.kind.value)
        head = self.sections[section]
        index = head.childCount()
        last = head.child(index - 1) if index else None
        if last is not None and last.data(0, _PLACEHOLDER_ROLE):
            index -= 1
        head.insertChild(index, item)
        return item

    def _add_placeholder(self, section: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([text.EQ_ADD[section]])
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        item.setData(0, _SECTION_ROLE, section)
        item.setData(0, _PLACEHOLDER_ROLE, True)
        item.setForeground(0, QBrush(QColor(chrome().muted)))
        self.sections[section].addChild(item)
        return item

    def items(self) -> list[QTreeWidgetItem]:
        """Every real row, in section order (placeholders left out)."""
        out = []
        for head in self.sections.values():
            for i in range(head.childCount()):
                child = head.child(i)
                if child is not None and not child.data(0, _PLACEHOLDER_ROLE):
                    out.append(child)
        return out

    def rows(self) -> list[Row]:
        """The rows as typed."""
        out = []
        for item in self.items():
            raw_kind = item.data(0, _KIND_ROLE)
            out.append(
                Row(
                    str(item.data(0, _SECTION_ROLE)),
                    unquote(item.text(NAME)),
                    item.text(VALUE).strip(),
                    item.text(COMMENT).strip(),
                    Kind(raw_kind) if isinstance(raw_kind, str) else None,
                    item.data(0, _DISABLED_ROLE) is True,
                )
            )
        return out

    def add(self, section: str, name: str, expr: str = "=", comment: str = "") -> QTreeWidgetItem:
        """Add a row (also used by tests and picks)."""
        self._filling = True
        item = self._add_row(section, Row(section, name, expr, comment))
        self._filling = False
        self.evaluate()
        return item

    def delete_row(self) -> None:
        """Delete the selected rows (or the current one)."""
        chosen = self._chosen()
        if not chosen:
            return
        for item in chosen:
            parent = item.parent()
            if parent is not None:
                parent.removeChild(item)
        self._last_cell = None
        self.evaluate()

    # Comfort (TR194, D830) ----------------------------------------------------------

    def _chosen(self) -> list[QTreeWidgetItem]:
        """The selected real rows, or the current one."""
        picked = [i for i in self.tree.selectedItems() if i in self.items()]
        current = self.tree.currentItem()
        if not picked and current is not None and current in self.items():
            picked = [current]
        return picked

    def names(self) -> list[str]:
        """Every name a formula can use, and the functions, for typing ahead."""
        from fdcad.core.equations import solve

        try:
            found = sorted(solve(self.session.document).namespace)
        except Exception:  # a broken part still offers the functions
            found = []
        return [quote(n) for n in found] + [f"{f}(" for f in FUNCTION_NAMES]

    def _show_disabled(self, item: QTreeWidgetItem, disabled: bool) -> None:
        item.setData(0, _DISABLED_ROLE, disabled)
        font = item.font(VALUE)
        font.setItalic(disabled)
        for col in (NAME, VALUE):
            item.setFont(col, font)
            item.setForeground(col, QBrush(QColor(chrome().muted)) if disabled else QBrush())

    def toggle_disabled(self) -> None:
        """Disable the selected equations, or enable them when all are disabled."""
        rows = [i for i in self._chosen() if i.data(0, _SECTION_ROLE) == "equation"]
        if not rows:
            self.message.setText(text.EQ_DISABLE_PICK)
            return
        disable = not all(i.data(0, _DISABLED_ROLE) is True for i in rows)
        self._filling = True
        for item in rows:
            self._show_disabled(item, disable)
        self._filling = False
        self.evaluate()

    def sort_rows(self) -> None:
        """Sort each section's rows by name; the Add row stays last."""
        self._filling = True
        for head in self.sections.values():
            rows = [head.child(i) for i in range(head.childCount())]
            real = [r for r in rows if r is not None and not r.data(0, _PLACEHOLDER_ROLE)]
            rest = [r for r in rows if r is not None and r.data(0, _PLACEHOLDER_ROLE)]
            head.takeChildren()
            for r in sorted(real, key=lambda i: unquote(i.text(NAME)).lower()) + rest:
                head.addChild(r)
        self._filling = False

    def apply_filter(self, typed: str = "") -> None:
        """Show only rows whose name, value or comment hold the typed text."""
        needle = typed.strip().lower()
        for item in self.items():
            hay = " ".join(item.text(c) for c in (NAME, VALUE, COMMENT)).lower()
            hay += " " + item.toolTip(NAME).lower()  # the group (TR417)
            item.setHidden(bool(needle) and needle not in hay)

    def replace_reference(self, chosen: str | None = None) -> bool:
        """Replace a name the current row uses that no longer exists with another name."""
        from PySide6.QtWidgets import QInputDialog

        from fdcad.core.units.expressions import references

        item = self.tree.currentItem()
        if item is None or item not in self.items():
            self.message.setText(text.EQ_REPLACE_PICK)
            return False
        known = {unquote(n) for n in self.names()}
        used = [unquote(item.text(NAME))] if item.data(0, _SECTION_ROLE) == "equation" else []
        with contextlib.suppress(Exception):  # text that does not parse names nothing
            used += list(references(item.text(VALUE)))
        lost = next((n for n in used if n and n not in known), None)
        if lost is None:
            self.message.setText(text.EQ_REPLACE_NONE)
            return False
        if chosen is None:
            options = sorted(known)
            chosen, ok = QInputDialog.getItem(
                self, text.EQ_REPLACE, text.EQ_REPLACE_ASK.format(name=lost), options, 0, False
            )
            if not ok or not chosen:
                return False
        self._filling = True
        if unquote(item.text(NAME)) == lost:
            item.setText(NAME, quote(chosen))
        item.setText(VALUE, item.text(VALUE).replace(quote(lost), quote(chosen)))
        self._filling = False
        self.message.setText(text.EQ_REPLACED.format(old=lost, new=chosen))
        self.evaluate()
        return True

    # Editing ----------------------------------------------------------------------

    def _changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._filling:
            return
        section = item.data(0, _SECTION_ROLE)
        if item.parent() is None or not isinstance(section, str):
            return
        self._filling = True
        try:
            if item.data(0, _PLACEHOLDER_ROLE):
                typed = unquote(item.text(NAME)) if column == NAME else ""
                if not typed or typed == text.EQ_ADD[section]:
                    item.setText(NAME, text.EQ_ADD[section])
                    return
                # A name in an Add row: quote it, make the row real and move to the value.
                item.setData(0, _PLACEHOLDER_ROLE, False)
                item.setForeground(0, QBrush())
                item.setText(NAME, quote(typed))
                item.setText(VALUE, "=")
                self._add_placeholder(section)
                QTimer.singleShot(0, lambda: self._edit_value(item))
            elif column == NAME:
                item.setText(NAME, quote(item.text(NAME)))
            if column in (NAME, VALUE):
                self._last_cell = (item, column)
        finally:
            self._filling = False
        self.evaluate()

    def _edit_value(self, item: QTreeWidgetItem) -> None:
        self.tree.setCurrentItem(item, VALUE)
        self.tree.editItem(item, VALUE)
        self._last_cell = (item, VALUE)
        editor = QApplication.focusWidget()
        if isinstance(editor, QLineEdit):
            editor.end(False)

    def _current_changed(self, item: QTreeWidgetItem | None, _old: object) -> None:
        if item is not None and item.parent() is not None:
            column = self.tree.currentColumn()
            self._last_cell = (item, VALUE if column != NAME else NAME)

    def _double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        if column in (MARK, RESULT):
            self.tree.editItem(item, VALUE)

    def insert_name(self, name: str) -> bool:
        """Put a picked name (a dimension double clicked in the view) into the cell."""
        quoted = quote(name)
        editor = QApplication.focusWidget()
        if isinstance(editor, QLineEdit) and self.tree.isAncestorOf(editor):
            editor.insert(quoted)
            self.message.setText(text.EQ_PICKED.format(name=unquote(name)))
            return True
        if self._last_cell is None:
            target = self.sections["equation"].child(self.sections["equation"].childCount() - 1)
            if target is None:
                return False
            target.setText(NAME, quoted)  # starts a new equation for the picked value
            return True
        item, column = self._last_cell
        try:
            current = item.text(column)
        except RuntimeError:  # the row was deleted
            self._last_cell = None
            return False
        if column == NAME:
            item.setText(NAME, quoted)
        else:
            base = current if current.strip() else "="
            item.setText(VALUE, base + quoted)
        self.message.setText(text.EQ_PICKED.format(name=unquote(name)))
        return True

    # Text file (TR25) -------------------------------------------------------------

    def _show_link(self) -> None:
        name = Path(self.link).name if self.link else ""
        self.link_label.setText(text.EQ_LINKED.format(name=name) if name else text.EQ_LINK_NONE)
        self.link_label.setToolTip(self.link)
        self.unlink_button.setEnabled(bool(self.link))

    def _choose(self, title: str, save: bool) -> str:
        if save:
            chosen, _f = QFileDialog.getSaveFileName(self, title, "", text.EQ_FILE_FILTER)
            if chosen and not Path(chosen).suffix:
                chosen += text_file.SUFFIX
        else:
            chosen, _f = QFileDialog.getOpenFileName(self, title, "", text.EQ_FILE_FILTER)
        return chosen

    def export_file(self, path: str | Path | None = None) -> bool:
        """Save the rows as they are in the manager to a text file."""
        target = path or self._choose(text.EQ_EXPORT_TITLE, save=True)
        if not target:
            return False
        try:
            Path(target).write_text(text_file.to_text(self.rows()), encoding="utf-8")
        except OSError as exc:
            self.message.setText(text.EQ_EXPORT_FAILED.format(reason=clause(exc)))
            return False
        self.message.setText(text.EQ_EXPORTED.format(name=Path(target).name))
        return True

    def import_file(self, path: str | Path | None = None) -> bool:
        """Put the rows of a text file into the manager; OK applies them."""
        source = path or self._choose(text.EQ_IMPORT_TITLE, save=False)
        if not source:
            return False
        name = Path(source).name
        try:
            incoming = text_file.read_file(Path(source))
        except (text_file.EquationFileError, OSError) as exc:
            self.message.setText(text.EQ_FILE_UNREADABLE.format(name=name, reason=clause(exc)))
            return False
        merged = text_file.merge(self.session.document, self.rows(), incoming)
        self.load(merged.rows)
        note = text.EQ_IMPORTED.format(count=merged.changed, name=name)
        if merged.skipped:
            note += text.EQ_IMPORT_SKIPPED.format(
                count=len(merged.skipped), names=", ".join(merged.skipped[:3])
            )
        self.message.setText(note)
        return True

    def link_file(self, path: str | Path | None = None) -> bool:
        """Link a text file: read it now, and again on open and on Rebuild."""
        source = path or self._choose(text.EQ_LINK_TITLE, save=False)
        if not source or not self.import_file(source):
            return False
        self.link = str(Path(source).resolve())
        self._show_link()
        return True

    def unlink(self) -> None:
        """Stop reading the linked file; the values stay."""
        self.link = ""
        self._show_link()

    # Values -----------------------------------------------------------------------

    def evaluate(self) -> list[RowResult]:
        """Solve the rows and show marks, values and errors."""
        items = self.items()
        results = preview(self.session.document, self.rows())
        self._filling = True
        try:
            first_error = ""
            for item, result in zip(items, results, strict=True):
                section = str(item.data(0, _SECTION_ROLE))
                if item.data(0, _DISABLED_ROLE) is True:
                    item.setText(MARK, "")
                    item.setText(RESULT, text.EQ_DISABLED)
                    continue
                good = result.ok
                item.setText(MARK, text.EQ_OK_MARK if good else text.EQ_BAD_MARK)
                item.setForeground(
                    MARK, QBrush(QColor(palette().state_ok if good else palette().state_error))
                )
                item.setText(RESULT, _format(result, section, self.session) if good else "")
                tip = result.error or ""
                for col in (VALUE, MARK, RESULT):
                    item.setToolTip(col, tip)
                if not good and not first_error:
                    first_error = f"{item.text(NAME)}: {result.error}"
            self.message.setText(first_error)
        finally:
            self._filling = False
        return results

    def ask_allowed(self, name: str, current: str) -> str | None:
        """The allowed values typed for ``name``; tests replace this."""
        from PySide6.QtWidgets import QInputDialog

        typed, ok = QInputDialog.getText(
            self, text.EQ_ALLOWED, text.EQ_ALLOWED_PROMPT.format(name=name), text=current
        )
        return typed if ok else None

    def edit_allowed(self, name: str | None = None) -> bool:
        """Set the allowed values of the chosen variable (TR274, D906): a list such as
        "10, 20, 30" or a range such as "5..50"; empty allows any value."""
        from fdcad.core.equations.allowed_text import format_allowed, parse_allowed
        from fdcad.core.units import ExpressionError

        if name is None:
            item = self.tree.currentItem()
            if item is None or item.data(0, _SECTION_ROLE) != "variable":
                self.message.setText(text.EQ_ALLOWED_PICK)
                return False
            name = unquote(item.text(NAME))
        if not hasattr(self, "allowed"):
            self.allowed: dict[str, dict[str, Any] | None] = {}
        doc = self.session.document
        var = next((v for v in doc.variables if v.name == name), None)
        kind = var.kind if var is not None else None
        before = self.allowed.get(name, var.allowed if var is not None else None)
        typed = self.ask_allowed(name, format_allowed(before, kind, doc.units))
        if typed is None:
            return False
        try:
            self.allowed[name] = parse_allowed(typed, kind, doc.units)
        except (ValueError, ExpressionError) as exc:
            self.message.setText(str(exc))
            return False
        self.message.setText(text.EQ_ALLOWED_SET.format(name=name))
        return True

    def ask_lookup(self, name: str, before: dict[str, str] | None) -> dict[str, str] | None:
        """Ask for the CSV file, row and column (a seam for tests). An empty file name
        stops reading from a file; None when cancelled."""
        from PySide6.QtWidgets import QFileDialog, QInputDialog

        start = (before or {}).get("file", "")
        path, _f = QFileDialog.getOpenFileName(
            self, text.CSV_LOOKUP_TITLE.format(name=name), start, text.CSV_LOOKUP_FILTER
        )
        if not path:
            return None
        row, ok = QInputDialog.getText(
            self, text.CSV_LOOKUP, text.CSV_LOOKUP_ROW, text=(before or {}).get("row", "")
        )
        if not ok:
            return None
        column, ok = QInputDialog.getText(
            self, text.CSV_LOOKUP, text.CSV_LOOKUP_COLUMN, text=(before or {}).get("column", "")
        )
        if not ok:
            return None
        return {"file": path, "row": row.strip(), "column": column.strip()}

    def edit_lookup(self, name: str | None = None) -> bool:
        """Read the chosen variable from a CSV table by row label or number and column
        (TR198, D2102): the value is read now, and again on open and on Rebuild."""
        from fdcad.core.equations import csv_lookup

        item = self.tree.currentItem()
        if name is None:
            if item is None or item.data(0, _SECTION_ROLE) != "variable":
                self.message.setText(text.EQ_ALLOWED_PICK)
                return False
            name = unquote(item.text(NAME))
        else:
            item = next(
                (
                    i
                    for i in self.items()
                    if i.data(0, _SECTION_ROLE) == "variable" and unquote(i.text(NAME)) == name
                ),
                None,
            )
        doc = self.session.document
        var = next((v for v in doc.variables if v.name == name), None)
        if var is None or item is None:
            self.message.setText(text.CSV_LOOKUP_NEW)
            return False
        if not hasattr(self, "lookups"):
            self.lookups: dict[str, dict[str, str] | None] = {}
        before = self.lookups.get(name, csv_lookup.lookup_of(var))
        chosen = self.ask_lookup(name, before)
        if chosen is None:
            return False
        if not chosen["file"]:
            self.lookups[name] = None
            self.message.setText(text.CSV_LOOKUP_STOPPED.format(name=name))
            return True
        try:
            read = csv_lookup.read_value(var, chosen, self.session.path, doc)
        except (csv_lookup.CsvLookupError, OSError, UnicodeDecodeError) as exc:
            self.message.setText(text.CSV_LOOKUP_BAD.format(name=name, reason=exc))
            return False
        self.lookups[name] = chosen
        item.setText(VALUE, read.expr)
        self.message.setText(text.CSV_LOOKUP_SET.format(name=name, value=read.expr))
        return True

    # Types and groups (TR417, D2104) -------------------------------------------------

    def _groups(self) -> dict[str, str]:
        """Variable name to group: the part's, with this dialog's changes."""
        out = {v.name: v.group for v in self.session.document.variables}
        out.update(getattr(self, "groups", {}))
        return out

    def _chosen_variables(self) -> list[str]:
        return [
            unquote(i.text(NAME)) for i in self._chosen() if i.data(0, _SECTION_ROLE) == "variable"
        ]

    def ask_type(self, names: list[str], current: str) -> str | None:
        """Ask for the type (a seam for tests): "", "text" or "yes_no"; None to cancel."""
        from PySide6.QtWidgets import QInputDialog

        labels = list(text.VAR_TYPES.values())
        start = labels.index(text.VAR_TYPES.get(current, labels[0]))
        picked, ok = QInputDialog.getItem(
            self, text.VAR_TYPE, text.VAR_TYPE_PROMPT.format(names=", ".join(names)), labels,
            start, False,
        )  # fmt: skip
        if not ok:
            return None
        return next(k for k, v in text.VAR_TYPES.items() if v == picked)

    def edit_type(self, names: list[str] | None = None) -> bool:
        """Make the chosen variables numbers, text or yes or no."""
        names = names or self._chosen_variables()
        if not names:
            self.message.setText(text.VAR_PICK)
            return False
        if not hasattr(self, "types"):
            self.types: dict[str, str] = {}
        doc = self.session.document
        old = next((v for v in doc.variables if v.name == names[0]), None)
        picked = self.ask_type(names, self.types.get(names[0], old.type if old else ""))
        if picked is None:
            return False
        for name in names:
            self.types[name] = picked
        self.message.setText(text.VAR_TYPE_SET.format(type=text.VAR_TYPES[picked]))
        return True

    def ask_group(self, names: list[str], current: str) -> str | None:
        """Ask for the group name (a seam for tests); empty for none, None to cancel."""
        from PySide6.QtWidgets import QInputDialog

        typed, ok = QInputDialog.getText(
            self, text.VAR_GROUP, text.VAR_GROUP_PROMPT.format(names=", ".join(names)),
            text=current,
        )  # fmt: skip
        return " ".join(typed.split()) if ok else None

    def edit_group(self, names: list[str] | None = None) -> bool:
        """Put the chosen variables in a group (empty takes them out); the list keeps a
        group's variables together."""
        names = names or self._chosen_variables()
        if not names:
            self.message.setText(text.VAR_PICK)
            return False
        if not hasattr(self, "groups"):
            self.groups: dict[str, str] = {}
        typed = self.ask_group(names, self._groups().get(names[0], ""))
        if typed is None:
            return False
        rows = self.rows()
        for name in names:
            self.groups[name] = typed
        self.load(rows)
        self.message.setText(text.VAR_GROUP_SET.format(group=typed or text.VAR_NO_GROUP))
        return True

    def accept(self) -> None:
        """Apply the rows as one undoable step, or say what is wrong."""
        try:
            variables, features = apply_rows(self.session.document, self.rows(), strict=True)
        except EquationError as exc:
            self.message.setText(text.EQ_NOT_APPLIED.format(message=exc))
            return
        for var in variables:  # TR274: allowed values chosen in this dialog
            if var.name in getattr(self, "allowed", {}):
                var.allowed = self.allowed[var.name]
            if var.name in getattr(self, "lookups", {}):  # TR198 (D2102)
                var.lookup = self.lookups[var.name]
            if var.name in getattr(self, "types", {}):  # TR417 (D2104)
                var.type = self.types[var.name]
            if var.name in getattr(self, "groups", {}):
                var.group = self.groups[var.name]
        doc = self.session.document
        configurations = self._followed_configurations()
        changed_vars = variables != doc.variables
        link_changed = self.link != doc.equations_file
        if changed_vars or features or configurations is not None or link_changed:
            self.session.undo.push(
                SetEquations(
                    self.session, variables, features, text.EQ_UNDO, configurations, self.link
                )
            )
        super().accept()

    def _followed_configurations(self) -> dict[str, Any] | None:
        """The configurations block with renamed variables' overrides moved and deleted
        variables' overrides dropped, or None when no configured variable changed."""
        doc = self.session.document
        now: dict[str, str] = {}
        for item in self.items():
            original = item.data(0, _ORIGINAL_ROLE)
            if item.data(0, _SECTION_ROLE) == "variable" and isinstance(original, str):
                now[original] = unquote(item.text(NAME))
        work = copy.copy(doc)
        work.configurations = copy.deepcopy(doc.configurations)
        configs.follow_variables(work, {v.name: now.get(v.name) for v in doc.variables})
        return work.configurations if work.configurations != doc.configurations else None
