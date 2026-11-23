"""Tools, Expected Values (TR359, D889): target results with a tolerance, checked after
every rebuild. The list shows each check's expected and actual value and whether it
passes; the status bar adds how many pass."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.checks import KEY, KINDS, stored
from fdcad.ui import strings
from fdcad.ui.commands.document import DocumentCommand

if TYPE_CHECKING:
    from fdcad.core.rebuild.engine import RebuildReport
    from fdcad.ui.main_window.window import MainWindow
    from fdcad.ui.session import DocumentSession


class SetChecks(DocumentCommand):
    """Replace the part's expected value checks (one undo step; the part rebuilds so
    they are checked at once)."""

    def __init__(self, session: DocumentSession, checks: list[dict[str, Any]]) -> None:
        super().__init__(session, strings.CHECKS_UNDO)
        self.before = copy.deepcopy(session.document.extra.get(KEY))
        self.after = copy.deepcopy(checks) if checks else None

    def _put(self, value: object) -> None:
        if value is None:
            self.session.document.extra.pop(KEY, None)
        else:
            self.session.document.extra[KEY] = copy.deepcopy(value)

    def apply(self) -> None:
        """Store the new checks."""
        self._put(self.after)

    def revert(self) -> None:
        """Put the old checks back."""
        self._put(self.before)


def status_suffix(report: RebuildReport) -> str:
    """ " Checks: 3 of 4 pass." after a rebuild with checks, else ""."""
    checks = getattr(report, "checks", None) or []
    if not checks:
        return ""
    passed = sum(1 for c in checks if c.passed)
    return " " + strings.CHECKS_STATUS.format(passed=passed, count=len(checks))


def _number(text: str) -> float | None:
    try:
        return float(text.strip())
    except ValueError:
        return None


class ExpectedValuesDialog(QDialog):
    """Edit the checks; shows the last rebuild's results beside them."""

    def __init__(self, session: DocumentSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.session = session
        self.setWindowTitle(strings.CHECKS_TITLE)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(list(strings.CHECKS_COLUMNS))
        self.message = QLabel()
        self.message.setWordWrap(True)
        add = QPushButton(strings.CHECKS_ADD)
        add.clicked.connect(lambda: self.add_row({"kind": "volume", "value": 0.0}))
        remove = QPushButton(strings.CHECKS_REMOVE)
        remove.clicked.connect(lambda: self.table.removeRow(self.table.currentRow()))
        current = QPushButton(strings.CHECKS_USE_CURRENT)
        current.setToolTip(strings.CHECKS_USE_CURRENT_TIP)
        current.clicked.connect(self.use_current)
        row = QHBoxLayout()
        for button in (add, remove, current):
            row.addWidget(button)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addLayout(row)
        layout.addWidget(self.message)
        layout.addWidget(buttons)
        results = {c.index: c for c in getattr(session.report, "checks", None) or []}
        for i, entry in enumerate(stored(session.document)):
            self.add_row(entry, results.get(i))

    def add_row(self, entry: dict[str, Any], result: Any = None) -> None:
        """One check row: kind, expected, tolerance, actual and pass or fail."""
        r = self.table.rowCount()
        self.table.insertRow(r)
        kind = QComboBox()
        for key in KINDS:
            kind.addItem(strings.CHECK_KINDS[key], key)
        kind.setCurrentIndex(max(kind.findData(entry.get("kind")), 0))
        kind.setProperty("entry", entry)
        self.table.setCellWidget(r, 0, kind)
        self.table.setItem(r, 1, QTableWidgetItem(f"{float(entry.get('value', 0.0)):g}"))
        self.table.setItem(r, 2, QTableWidgetItem(f"{float(entry.get('tolerance', 0.0)):g}"))
        actual = "" if result is None or result.actual is None else f"{result.actual:.6g}"
        verdict = (
            "" if result is None else (strings.CHECK_PASS if result.passed else strings.CHECK_FAIL)
        )
        for col, text in ((3, actual), (4, verdict)):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, col, item)

    def use_current(self) -> None:
        """Copy each row's actual value into its expected value."""
        for r in range(self.table.rowCount()):
            actual = self.table.item(r, 3)
            if actual is not None and actual.text():
                self.table.setItem(r, 1, QTableWidgetItem(actual.text()))

    def checks(self) -> list[dict[str, Any]] | None:
        """The rows as stored checks, or None with the reason shown."""
        out: list[dict[str, Any]] = []
        for r in range(self.table.rowCount()):
            box = self.table.cellWidget(r, 0)
            assert isinstance(box, QComboBox)
            value_item, tol_item = self.table.item(r, 1), self.table.item(r, 2)
            value = _number(value_item.text() if value_item else "")
            tol = _number(tol_item.text() if tol_item else "0") or 0.0
            if value is None:
                self.message.setText(strings.CHECKS_BAD_ROW.format(row=r + 1))
                return None
            entry: dict[str, Any] = {
                "kind": str(box.currentData()),
                "value": value,
                "tolerance": abs(tol),
            }
            old = box.property("entry")
            if isinstance(old, dict) and entry["kind"] == "measurement":
                for key in ("feature", "key"):
                    if key in old:
                        entry[key] = old[key]
            out.append(entry)
        return out

    def _ok(self) -> None:
        if self.checks() is not None:
            self.accept()


def run(dialog: QDialog) -> bool:
    """Show the dialog; tests replace this."""
    return dialog.exec() == QDialog.DialogCode.Accepted


def open_checks(window: MainWindow) -> bool:
    """Edit the open part's checks. True when they changed."""
    tab = window.current
    if tab is None:
        return False
    dialog = ExpectedValuesDialog(tab.session, window)
    accepted = run(dialog)
    checks = dialog.checks() if accepted else None
    dialog.deleteLater()
    if checks is None or checks == stored(tab.session.document):
        return False
    tab.session.undo.push(SetChecks(tab.session, checks))
    return True
