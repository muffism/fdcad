"""Rebuild statistics panel: time per feature, slowest first, and memory use (PLAN 11.5)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fdcad.sysinfo import process_memory
from fdcad.ui import strings
from fdcad.ui.session import DocumentSession


class RebuildStats(QDialog):
    """Shows the last rebuild of a part. Updates after every rebuild while open."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(strings.STATS_TITLE)
        self.session: DocumentSession | None = None
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(strings.STATS_COLUMNS)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        layout = QVBoxLayout(self)
        layout.addWidget(self.summary)
        layout.addWidget(self.table, 1)
        layout.addWidget(buttons)
        self.resize(520, 480)

    def set_session(self, session: DocumentSession | None) -> None:
        """Follow ``session``."""
        if self.session is not None:
            self.session.rebuilt.disconnect(self.refresh)
        self.session = session
        if session is not None:
            session.rebuilt.connect(self.refresh)
        self.refresh()

    def refresh(self, *_args: object) -> None:
        """Fill the table from the last rebuild."""
        report = self.session.report if self.session is not None else None
        memory = process_memory() / (1024 * 1024)
        if report is None:
            self.table.setRowCount(0)
            self.summary.setText(strings.STATS_NONE.format(memory=memory))
            return
        doc = self.session.document if self.session is not None else None
        names = {f.id: f.name for f in doc.features} if doc else {}
        rows = sorted(report.results.items(), key=lambda kv: kv[1].seconds, reverse=True)
        self.table.setRowCount(len(rows))
        rebuilt = set(report.rebuilt)
        for i, (fid, result) in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(names.get(fid, fid)))
            self.table.setItem(i, 1, QTableWidgetItem(f"{result.seconds * 1000:.1f}"))
            how = strings.STATS_REBUILT if fid in rebuilt else strings.STATS_REUSED
            self.table.setItem(i, 2, QTableWidgetItem(how))
        self.table.resizeColumnsToContents()
        self.summary.setText(
            strings.STATS_SUMMARY.format(
                seconds=report.seconds,
                rebuilt=len(report.rebuilt),
                reused=len(report.reused),
                memory=memory,
            )
        )
