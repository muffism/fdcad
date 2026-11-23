"""File, Export, Section and Outline (TR300, DECISIONS D1204).

A window asks for the source (the cut at a plane, or the outline seen along an
axis), the plane, the offset, a kerf or tool offset, the scale, and each body's
use (cut, engrave or ignore). Then a DXF or SVG file is chosen and the drawing
is made and written in the background.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QTableWidget,
    QWidget,
)

from fdcad.core.io.section_export import USES, VIEWS, SectionJob
from fdcad.ui import strings_print as text
from fdcad.ui.print_tools import jobs

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow


class SectionExportDialog(QDialog):
    """The options; ``job`` holds the choice after OK."""

    def __init__(self, labels: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("section_export_dialog")
        self.setWindowTitle(text.SECTION_EXPORT_TITLE)
        form = QFormLayout(self)
        self.mode = QComboBox()
        for key, label in text.SECTION_MODES.items():
            self.mode.addItem(label, key)
        self.view = QComboBox()
        for key in VIEWS:
            self.view.addItem(text.SECTION_VIEWS[key], key)
        self.offset = QDoubleSpinBox()
        self.offset.setRange(-100000.0, 100000.0)
        self.offset.setDecimals(3)
        self.offset.setSuffix(" mm")
        self.offset.setToolTip(text.SECTION_OFFSET_TIP)
        self.kerf = QDoubleSpinBox()
        self.kerf.setRange(-50.0, 50.0)
        self.kerf.setDecimals(3)
        self.kerf.setSuffix(" mm")
        self.kerf.setToolTip(text.SECTION_KERF_TIP)
        self.scale = QDoubleSpinBox()
        self.scale.setRange(0.001, 1000.0)
        self.scale.setDecimals(3)
        self.scale.setValue(1.0)
        self.uses = QTableWidget(len(labels), 1)
        self.uses.setObjectName("section_uses")
        self.uses.setHorizontalHeaderLabels([text.SECTION_USE])
        self.uses.setVerticalHeaderLabels(labels)
        for row in range(len(labels)):
            box = QComboBox()
            for key in USES:
                box.addItem(text.SECTION_USES[key], key)
            self.uses.setCellWidget(row, 0, box)
        form.addRow(text.SECTION_SOURCE, self.mode)
        form.addRow(text.SECTION_PLANE, self.view)
        form.addRow(text.SECTION_OFFSET, self.offset)
        form.addRow(text.SECTION_KERF, self.kerf)
        form.addRow(text.SECTION_SCALE, self.scale)
        form.addRow(self.uses)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.mode.currentIndexChanged.connect(lambda _i: self._mode_changed())
        self._mode_changed()

    def _mode_changed(self) -> None:
        self.offset.setEnabled(self.mode.currentData() == "section")

    def set_use(self, row: int, use: str) -> None:
        """Give the body at ``row`` a use (cut, engrave or ignore)."""
        box = self.uses.cellWidget(row, 0)
        assert isinstance(box, QComboBox)
        box.setCurrentIndex(box.findData(use))

    @property
    def job(self) -> SectionJob:
        """The chosen drawing."""
        uses = []
        for row in range(self.uses.rowCount()):
            box = self.uses.cellWidget(row, 0)
            uses.append(str(box.currentData()) if isinstance(box, QComboBox) else "cut")
        return SectionJob(
            str(self.mode.currentData()),
            str(self.view.currentData()),
            self.offset.value(),
            self.kerf.value(),
            self.scale.value(),
            tuple(uses),
        )


def run(dialog: SectionExportDialog) -> bool:
    """Show the dialog and wait; True on OK (a seam for tests, which cannot click it)."""
    return bool(dialog.exec())


def export(window: MainWindow, path: str | None = None) -> jobs.Job | None:
    """Ask for the drawing, then a file (``path`` skips the file dialog), and write it."""
    from fdcad.core.body_titles import labels_of
    from fdcad.core.features.solids import solids

    tab = window.current
    report = tab.session.report if tab is not None else None
    if tab is None or report is None or report.body is None:
        window.status.setText(text.SECTION_NOTHING)
        return None
    bodies = solids(report.body.shape) or [report.body.shape]
    from fdcad.core.body_titles import report_marks

    given = report_marks(report, "body_titles")
    labels = labels_of(tab.session.document, report.body, given) or ["Body 1"]
    dialog = SectionExportDialog(labels[: len(bodies)], window)
    accepted = run(dialog)
    job = dialog.job
    dialog.deleteLater()
    if not accepted:
        return None
    if path is None:
        default = f"{tab.session.title.rstrip('*')} {job.mode}.dxf"
        path, chosen = QFileDialog.getSaveFileName(
            window, text.SECTION_EXPORT_TITLE, default, text.SECTION_FILTER
        )
        if not path:
            return None
        if not path.lower().endswith((".dxf", ".svg")):
            path += ".svg" if "svg" in chosen.lower() else ".dxf"
    from fdcad.core.io.section_export import export_section

    target = path

    def work() -> Any:
        count = export_section(bodies, job, target)
        return text.SECTION_DONE.format(name=Path(target).name, count=count)

    return jobs.start(
        work,
        window.status.setText,
        lambda reason: window.status.setText(text.FLAT_FAILED.format(reason=reason)),
    )
