"""The design table editor (PHASE4_SPEC P4.10 item 3, D392).

A built in table: rows are configurations, columns are values. OK applies the
table as one undoable command (new rows add configurations, deleted rows
delete them); Cancel changes nothing. CSV import fills the table, CSV export
writes it. The table is stored inside the `.fdef` file.
"""

from __future__ import annotations

import copy
import csv
import io
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fdcad.core import configurations as configs
from fdcad.core import design_table as dt
from fdcad.core.configurations import ConfigurationError
from fdcad.core.document.model import Param
from fdcad.ui import strings_config as text
from fdcad.ui.equations.commands import DocumentChange
from fdcad.ui.strings import clause

if TYPE_CHECKING:
    from fdcad.core.document.model import Document
    from fdcad.ui.session import DocumentSession

#: The configuration a name cell showed when the editor opened (None for new rows).
_ORIGINAL_ROLE = Qt.ItemDataRole.UserRole


def column_choices(session: DocumentSession) -> list[str]:
    """Every path a column can show: variables, feature values and suppression."""
    from fdcad.core.properties import rows

    doc = session.document
    out = [f"{configs.VAR_PREFIX}{v.name}" for v in doc.variables]
    # TR90 item 1 (D2100): description, part colour and custom properties.
    out += [dt.DESCRIPTION, dt.THEME, configs.PART_COLOR]
    out += [f"{dt.PROP_PREFIX}{row.name}" for row in rows(doc)]
    builtin = {"f1", "f2", "f3", "f4"}
    for feature in doc.features:
        if feature.id in builtin:
            continue
        out.append(f"{feature.id}.{configs.SUPPRESSED}")
        out.extend(f"{feature.id}.{name}" for name in feature.params)
        if feature.type == "sketch":
            dims = [
                d["id"]
                for d in feature.data.get("dimensions", [])
                if isinstance(d, dict) and isinstance(d.get("id"), str)
            ]
            out.extend(f"{feature.id}.{did}" for did in dims)
            # TR197 (D2101): the sketch's plane and whether each dimension drives.
            if isinstance(feature.refs.get(configs.PLANE), dict):
                out.append(f"{feature.id}.{configs.PLANE}")
            out.extend(f"{feature.id}.{did}{configs.DRIVING}" for did in dims)
    return out


def _by_formula(doc: Any, path: str) -> bool:
    """True when a feature value or dimension is set by a formula (an equation)."""
    head, _, tail = path.partition(".")
    feature = next((f for f in doc.features if f.id == head), None)
    if feature is None:
        return False
    value = feature.params.get(tail)
    if isinstance(value, Param):
        return value.expr.strip().startswith("=")
    for dim in feature.data.get("dimensions", []):
        if isinstance(dim, dict) and dim.get("id") == tail:
            expr = dim.get("expr") or (dim.get("param") or {}).get("expr", "")
            return isinstance(expr, str) and expr.strip().startswith("=")
    return False


class DesignTableDialog(QDialog):
    """Edits the part's design table."""

    def __init__(self, session: DocumentSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("design_table_dialog")
        self.setWindowTitle(text.TABLE_TITLE)
        self.session = session
        self.table = QTableWidget()
        self.table.setObjectName("design_table")
        help_text = QLabel(text.TABLE_HELP)
        help_text.setWordWrap(True)
        self.message = QLabel()
        self.message.setObjectName("design_table_message")
        self.message.setWordWrap(True)
        grid = QGridLayout()
        actions = (
            ("add_row", text.TABLE_ADD_ROW, lambda: self.add_row()),
            ("delete_row", text.TABLE_DELETE_ROW, self.delete_row),
            ("add_column", text.TABLE_ADD_COLUMN, lambda: self.ask_column()),
            ("add_values", text.TABLE_ADD_VALUES, lambda: self.ask_columns()),  # TR90
            ("delete_column", text.TABLE_DELETE_COLUMN, self.delete_column),
            ("import", text.TABLE_IMPORT, lambda: self.import_csv()),
            ("export", text.TABLE_EXPORT, lambda: self.export_csv()),
            ("copy", text.TABLE_COPY, lambda: self.copy_table()),  # TR304
            ("paste", text.TABLE_PASTE, lambda: self.paste_table()),
            ("remove", text.TABLE_REMOVE, self.remove_table),
            ("rules", text.TABLE_RULES, lambda: self.edit_rules()),  # TR331
            ("apply_rules", text.TABLE_APPLY_RULES, lambda: self.apply_rules()),
            ("try", text.TABLE_TRY, lambda: self.try_row()),
        )
        for i, (key, label, slot) in enumerate(actions):
            button = QPushButton(label)
            button.setObjectName(f"table_{key}")
            button.clicked.connect(slot)
            grid.addWidget(button, i // 4, i % 4)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        #: Sum, average, smallest, largest and count of the current column (TR198).
        self.summary = QLabel()
        self.summary.setObjectName("design_table_summary")
        self.summary.setWordWrap(True)
        self.table.currentCellChanged.connect(lambda *_a: self.update_summary())
        self.table.cellChanged.connect(lambda *_a: self.update_summary())
        layout = QVBoxLayout(self)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.summary)
        layout.addWidget(help_text)
        layout.addLayout(grid)
        layout.addWidget(self.message)
        layout.addWidget(buttons)
        self.resize(720, 420)
        doc = session.document
        stored = dt.stored(doc)
        work = copy.deepcopy(doc)
        self.show_table(dt.from_configurations(work, stored.columns if stored else []))
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item is not None:
                item.setData(_ORIGINAL_ROLE, item.text())

    def update_summary(self) -> str:
        """Show the numbers of the current column (TR198, D966). Returns the text."""
        from fdcad.core.table_summary import column_summary
        from fdcad.ui.property_panel.panel import format_value

        column = self.table.currentColumn() - 1  # column 0 holds the names
        found = None
        if column >= 0:
            try:
                found = column_summary(self.session.document, self.current(), column)
            except Exception:  # a table being typed may not read yet
                found = None
        if found is None:
            self.summary.setText(text.TABLE_SUMMARY_NONE)
            return self.summary.text()
        units = self.session.document.units

        def shown(value: float) -> str:
            return format_value(value, found.kind, units)

        header = self.table.horizontalHeaderItem(column + 1)
        self.summary.setText(
            text.TABLE_SUMMARY.format(
                column=header.text() if header is not None else "",
                count=found.count,
                total=shown(found.total),
                average=shown(found.average),
                smallest=shown(found.smallest),
                largest=shown(found.largest),
            )
        )
        return self.summary.text()

    # Table contents -------------------------------------------------------------------

    def show_table(self, table: dt.Table) -> None:
        """Fill the editor from ``table``. Rows keep the configuration they started as."""
        originals = {}
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            original = item.data(_ORIGINAL_ROLE) if item is not None else None
            if item is not None and isinstance(original, str):
                originals[item.text().strip()] = original
        self.table.clear()
        self.table.setColumnCount(len(table.columns) + 1)
        self.table.setHorizontalHeaderLabels([text.TABLE_CONFIG_HEADER, *table.columns])
        # A named value shows its name (TR32); the path stays in the header's data.
        for c, path in enumerate(table.columns, start=1):
            header = self.table.horizontalHeaderItem(c)
            if header is not None:
                header.setData(Qt.ItemDataRole.UserRole, path)
                header.setText(column_title(self.session.document, path))
                header.setToolTip(path)
        self.table.setRowCount(len(table.rows))
        for r, (name, values) in enumerate(table.rows):
            name_item = QTableWidgetItem(name)
            name_item.setData(_ORIGINAL_ROLE, originals.get(name.strip()))
            self.table.setItem(r, 0, name_item)
            for c, value in enumerate(values):
                self.table.setItem(r, c + 1, QTableWidgetItem(value))

    def columns(self) -> list[str]:
        """The column paths, in order."""
        out = []
        for c in range(1, self.table.columnCount()):
            item = self.table.horizontalHeaderItem(c)
            path = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
            out.append(path if isinstance(path, str) else (item.text() if item is not None else ""))
        return out

    def current(self) -> dt.Table:
        """The table as edited."""
        rows = []
        for r in range(self.table.rowCount()):
            cells = []
            for c in range(self.table.columnCount()):
                item = self.table.item(r, c)
                cells.append(item.text().strip() if item is not None else "")
            rows.append((cells[0], cells[1:]))
        return dt.Table(self.columns(), rows)

    def set_cell(self, row: int, column: str | int, value: str) -> None:
        """Type ``value`` into a cell (column by path or by index, 0 is the name)."""
        index = column if isinstance(column, int) else self.columns().index(column) + 1
        self.table.setItem(row, index, QTableWidgetItem(value))

    def add_row(self, name: str | None = None) -> int:
        """Add a configuration row; its cells start empty (values kept as they are)."""
        r = self.table.rowCount()
        existing = {row[0] for row in self.current().rows}
        if name is None:
            n = r + 1
            while text.CONFIG_NEW_NAME.format(n=n) in existing:
                n += 1
            name = text.CONFIG_NEW_NAME.format(n=n)
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(name))
        return r

    def delete_row(self) -> None:
        """Delete the selected row (its configuration is deleted on OK)."""
        r = self.table.currentRow()
        if r >= 0 and self.table.rowCount() > 1:
            self.table.removeRow(r)

    def add_column(self, path: str) -> bool:
        """Add a column for ``path`` with each configuration's current value."""
        if not dt.column_exists(self.session.document, path):
            self.message.setText(
                text.TABLE_NOT_APPLIED.format(
                    message=f'"{path}" is not a value. Pick a value from the list.'
                )
            )
            return False
        table = self.current()
        if path in table.columns:
            return False
        work = copy.deepcopy(self.session.document)
        values = dict(dt.from_configurations(work, [path]).rows)
        table.columns.append(path)
        table.rows = [(name, [*vals, values.get(name, [""])[0]]) for name, vals in table.rows]
        self.show_table(table)
        return True

    def ask_column(self) -> None:
        """Ask which value to add as a column."""
        choices = [c for c in column_choices(self.session) if c not in self.columns()]
        path, ok = QInputDialog.getItem(
            self, text.TABLE_TITLE, text.TABLE_COLUMN_PROMPT, choices, 0, True
        )
        if ok and path:
            self.add_column(path.strip())

    def add_columns(self, paths: list[str]) -> int:
        """Add a column for each path not shown yet (TR90, D969). Returns how many."""
        added = sum(1 for path in paths if self.add_column(path))
        self.message.setText(text.TABLE_VALUES_ADDED.format(count=added))
        return added

    def pick_columns(self, choices: list[str]) -> list[str] | None:
        """Tick the values to add; variables and values set by a formula start ticked
        (a seam for tests). None when cancelled."""
        from PySide6.QtWidgets import QDialogButtonBox, QListWidget, QListWidgetItem

        dialog = QDialog(self)
        dialog.setWindowTitle(text.TABLE_ADD_VALUES)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(text.TABLE_VALUES_PROMPT))
        items = QListWidget()
        items.setObjectName("table_value_choices")
        doc = self.session.document
        for path in choices:
            item = QListWidgetItem(column_title(doc, path))
            item.setToolTip(path)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            ticked = path.startswith(configs.VAR_PREFIX) or _by_formula(doc, path)
            item.setCheckState(Qt.CheckState.Checked if ticked else Qt.CheckState.Unchecked)
            items.addItem(item)
        layout.addWidget(items)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        try:
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return None
            return [
                str(items.item(i).data(Qt.ItemDataRole.UserRole))
                for i in range(items.count())
                if items.item(i).checkState() == Qt.CheckState.Checked
            ]
        finally:
            dialog.deleteLater()

    def ask_columns(self) -> int:
        """Add Values: pick several values at once and add a column for each."""
        choices = [c for c in column_choices(self.session) if c not in self.columns()]
        picked = self.pick_columns(choices)
        return self.add_columns(picked) if picked else 0

    def delete_column(self) -> None:
        """Delete the selected column (the configuration name column stays)."""
        c = self.table.currentColumn()
        if c > 0:
            self.table.removeColumn(c)

    # CSV ------------------------------------------------------------------------------

    def import_csv(self, path: str | Path | None = None) -> bool:
        """Fill the table from a CSV file."""
        if path is None:
            chosen, _f = QFileDialog.getOpenFileName(
                self, text.TABLE_IMPORT, "", text.TABLE_CSV_FILTER
            )
            if not chosen:
                return False
            path = chosen
        try:
            table = dt.from_csv(Path(path).read_text(encoding="utf-8-sig"))
        except dt.DesignTableError as exc:
            self.message.setText(text.TABLE_NOT_APPLIED.format(message=exc))
            return False
        except (OSError, UnicodeDecodeError) as exc:
            self.message.setText(text.TABLE_CSV_UNREADABLE.format(reason=clause(exc)))
            return False
        self.show_table(table)
        self.message.clear()
        return True

    def export_csv(self, path: str | Path | None = None) -> bool:
        """Write the table to a CSV file."""
        if path is None:
            chosen, _f = QFileDialog.getSaveFileName(
                self, text.TABLE_EXPORT, "", text.TABLE_CSV_FILTER
            )
            if not chosen:
                return False
            path = chosen
        try:
            # With a byte order mark, so spreadsheet programs read names in any script
            # (audit D3 item 11, D724); import already accepts one.
            Path(path).write_text(dt.to_csv(self.current()), encoding="utf-8-sig", newline="")
        except OSError as exc:
            self.message.setText(text.TABLE_EXPORT_FAILED.format(reason=clause(exc)))
            return False
        self.message.setText(text.TABLE_EXPORTED.format(path=path))
        return True

    # Clipboard (TR304, D930) ---------------------------------------------------------------

    def copy_table(self) -> str:
        """Put the table on the clipboard as tab separated text, which spreadsheets
        and another part's Design Table both paste. Returns the text."""
        from PySide6.QtWidgets import QApplication

        rows = list(csv.reader(io.StringIO(dt.to_csv(self.current()))))
        buffer = io.StringIO()
        csv.writer(buffer, delimiter="\t", lineterminator="\n").writerows(rows)
        board = QApplication.clipboard()
        if board is not None:
            board.setText(buffer.getvalue())
        self.message.setText(text.TABLE_COPIED)
        return buffer.getvalue()

    def paste_table(self, pasted: str | None = None) -> bool:
        """Fill the table from the clipboard: tab separated (from a spreadsheet or a
        copied table) or comma separated text. Nothing changes until OK."""
        from PySide6.QtWidgets import QApplication

        if pasted is None:
            board = QApplication.clipboard()
            pasted = board.text() if board is not None else ""
        if not pasted.strip():
            self.message.setText(text.TABLE_PASTE_EMPTY)
            return False
        first = pasted.splitlines()[0]
        if "\t" in first:
            rows = list(csv.reader(io.StringIO(pasted), delimiter="\t"))
            buffer = io.StringIO()
            csv.writer(buffer, lineterminator="\n").writerows(rows)
            pasted = buffer.getvalue()
        try:
            table = dt.from_csv(pasted)
        except dt.DesignTableError as exc:
            self.message.setText(text.TABLE_NOT_APPLIED.format(message=exc))
            return False
        self.show_table(table)
        self.message.setText(text.TABLE_PASTED)
        return True

    # Rules, themes and trial values (TR331, D2103) ------------------------------------------

    def run_dialog(self, dialog: QDialog) -> bool:
        """Show a dialog and wait (tests replace this)."""
        return dialog.exec() == QDialog.DialogCode.Accepted

    def edit_rules(self) -> bool:
        """Open Rules and Themes. True when they were stored."""
        from fdcad.ui.equations.rules_dialog import RulesDialog

        dialog = RulesDialog(self.session, self)
        try:
            return self.run_dialog(dialog)
        finally:
            dialog.deleteLater()

    def apply_rules(self) -> int:
        """Run the rules in every configuration now (one undo step). Returns how many
        values changed."""
        count = 0

        def change(d: Document) -> None:
            nonlocal count
            count = dt.run_rules(d)

        try:
            command = DocumentChange(self.session, text.TABLE_UNDO_RULES, change)
        except dt.DesignTableError as exc:
            self.message.setText(text.TABLE_NOT_APPLIED.format(message=exc))
            return 0
        if command.changes_anything:
            self.session.undo.push(command)
            work = copy.deepcopy(self.session.document)
            stored = dt.stored(work)
            self.show_table(
                dt.from_configurations(work, stored.columns if stored else self.columns())
            )
        self.message.setText(text.TABLE_RULES_APPLIED.format(count=count))
        return count

    def try_row(self) -> Any:
        """Build the current row's values on a copy, rules run, and show it in a small
        window without adding a configuration. Returns the window, or None."""
        from fdcad.core import config_rules
        from fdcad.ui.equations.config_preview import ConfigPreview

        r = max(self.table.currentRow(), 0)
        table = self.current()
        if not table.rows:
            self.message.setText(text.TABLE_TRY_EMPTY)
            return None
        try:
            work = config_rules.trial(self.session.document, table.columns, table.rows[r][1])
        except config_rules.RuleError as exc:
            self.message.setText(text.TABLE_NOT_APPLIED.format(message=exc))
            return None
        window = ConfigPreview(self.session, configs.active_name(work), self, doc=work)
        window.setWindowTitle(text.TABLE_TRY_TITLE.format(name=table.rows[r][0]))
        window.show()
        self.trials = [*getattr(self, "trials", [])[-3:], window]
        self.message.setText(text.TABLE_TRY_STARTED.format(name=table.rows[r][0]))
        return window

    # Apply ----------------------------------------------------------------------------

    def renames(self) -> dict[str, str]:
        """Configurations whose name was changed in the table: old name to new name."""
        doc_names = set(configs.names(self.session.document))
        out = {}
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            original = item.data(_ORIGINAL_ROLE) if item is not None else None
            if item is None or not isinstance(original, str) or original not in doc_names:
                continue
            new = " ".join(item.text().split())
            if new and new != original:
                out[original] = new
        return out

    def remove_table(self) -> None:
        """Remove the stored table (one undo step); configurations keep their values."""
        session = self.session
        command = DocumentChange(session, text.TABLE_UNDO_REMOVE, dt.remove)
        if command.changes_anything:
            session.undo.push(command)
        super().accept()

    def accept(self) -> None:
        """Apply the table as one undoable command, or say what is wrong."""
        table = self.current()
        session = self.session
        renames = self.renames()
        from fdcad.core import configurations as configs

        kept = {name for name, _values in table.rows} | set(renames.values())
        gone = [n for n in configs.names(session.document) if n not in kept and n not in renames]
        if gone:
            # Configurations missing from the table are deleted: say which first.
            answer = QMessageBox.question(
                self, text.TABLE_TITLE, text.TABLE_DELETES.format(names=", ".join(gone))
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        def change(d: Document) -> None:
            rename_all(d, renames)
            dt.apply(d, table, delete_missing=True)

        try:
            command = DocumentChange(session, text.TABLE_UNDO, change)
        except (dt.DesignTableError, ConfigurationError) as exc:
            self.message.setText(text.TABLE_NOT_APPLIED.format(message=exc))
            return
        if command.changes_anything:
            session.undo.push(command)
        super().accept()


def rename_all(doc: Document, renames: dict[str, str]) -> None:
    """Rename configurations together, so names may be swapped. Raises ConfigurationError."""
    temporary = {}
    for i, old in enumerate(renames):
        name = f"renaming {i}"
        while name in configs.names(doc):
            name += " again"
        configs.rename(doc, old, name)
        temporary[name] = renames[old]
    for name, new in temporary.items():
        configs.rename(doc, name, new)


def column_title(doc: object, path: str) -> str:
    """The header text of a column: ``f6.thickness`` shows as ``wall`` when the value
    has a name (TR32), else the path itself."""
    from fdcad.core.equations.value_names import value_name

    if path == dt.DESCRIPTION:
        return text.TABLE_DESCRIPTION_HEADER
    if path == dt.THEME:
        return text.TABLE_THEME_HEADER
    if path == configs.PART_COLOR:
        return text.TABLE_COLOR_HEADER
    if path.startswith(dt.PROP_PREFIX):
        return text.TABLE_PROPERTY_HEADER.format(name=path[len(dt.PROP_PREFIX) :])
    head, _, tail = path.partition(".")
    features = getattr(doc, "features", [])
    feature = next((f for f in features if f.id == head), None)
    if feature is None or not tail:
        return path
    name = value_name(feature, tail)
    return f"{name} ({feature.name})" if name != tail else path
