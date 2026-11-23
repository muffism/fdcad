"""File, Export, Batch Export (TR368, D904): values for chosen variables, every
combination rebuilt and exported in the background. The open part does not change."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow


class BatchExportDialog(QDialog):
    """A row per variable (tick by giving it values), the file kind, the name template
    and the folder."""

    def __init__(self, names: list[str], folder: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(strings.BATCH_TITLE)
        self.table = QTableWidget(len(names), 2)
        self.table.setHorizontalHeaderLabels(list(strings.BATCH_COLUMNS))
        for i, name in enumerate(names):
            item = QTableWidgetItem(name)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 0, item)
            self.table.setItem(i, 1, QTableWidgetItem(""))
        self.kind = QComboBox()
        for key, label in strings.EXPORT_CONFIGS_KINDS.items():
            self.kind.addItem(label, key)
        self.template = QLineEdit()
        self.template.setPlaceholderText(strings.BATCH_TEMPLATE_HINT)
        self.folder = QLineEdit(folder)
        browse = QPushButton(strings.EXPORT_CONFIGS_BROWSE)
        browse.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.addWidget(self.folder, 1)
        row.addWidget(browse)
        self.message = QLabel(strings.BATCH_NOTE)
        self.message.setWordWrap(True)
        form = QFormLayout()
        form.addRow(strings.EXPORT_CONFIGS_KIND, self.kind)
        form.addRow(strings.BATCH_TEMPLATE, self.template)
        form.addRow(strings.EXPORT_CONFIGS_FOLDER, row)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addLayout(form)
        layout.addWidget(self.message)
        layout.addWidget(buttons)

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, strings.EXPORT_CONFIGS_FOLDER, self.folder.text()
        )
        if chosen:
            self.folder.setText(chosen)

    def plan(self) -> tuple[list[dict[str, str]], str] | None:
        """The combinations and the name template, or None with the reason shown."""
        from fdcad.core.io.export_variants import (
            BatchError,
            combinations,
            default_template,
            parse_values,
        )

        values: dict[str, list[str]] = {}
        try:
            for i in range(self.table.rowCount()):
                name_item, text_item = self.table.item(i, 0), self.table.item(i, 1)
                text = text_item.text().strip() if text_item is not None else ""
                if name_item is not None and text:
                    values[name_item.text()] = parse_values(text)
            if not values:
                self.message.setText(strings.BATCH_NO_VALUES)
                return None
            combos = combinations(values)
        except BatchError as exc:
            self.message.setText(str(exc))
            return None
        template = self.template.text().strip() or default_template(list(values))
        return combos, template

    def _ok(self) -> None:
        if self.plan() is not None and self.folder.text().strip():
            self.accept()


def run(dialog: QDialog) -> bool:
    """Show the dialog; tests replace this."""
    return dialog.exec() == QDialog.DialogCode.Accepted


def batch_export(window: MainWindow) -> Any:
    """Ask, then export every combination in the background. Returns the job or None."""
    import copy

    from PySide6.QtCore import QThreadPool

    from fdcad.core.io.export_variants import BatchError, export_variants
    from fdcad.ui.main_window.window import _Job

    tab = window.current
    if tab is None:
        return None
    session = tab.session
    if session.is_rebuilding:
        window.status.setText(strings.EXPORT_WAIT)
        return None
    names = [v.name for v in session.document.variables]
    if not names:
        window.status.setText(strings.BATCH_NO_VARIABLES)
        return None
    base = (session.path.stem if session.path is not None else session.name) or "Part"
    start = str(session.path.parent) if session.path is not None else str(Path.home())
    dialog = BatchExportDialog(names, start, window)
    accepted = run(dialog)
    plan = dialog.plan() if accepted else None
    kind, folder = str(dialog.kind.currentData()), dialog.folder.text()
    dialog.deleteLater()
    if plan is None or not folder.strip():
        return None
    combos, template = plan
    doc = copy.deepcopy(session.document)

    def work() -> str:
        try:
            found = export_variants(doc, combos, folder, kind, base, template)
        except BatchError as exc:
            return str(exc)
        failed = [o.name for o in found if not o.ok]
        if failed:
            return strings.BATCH_SOME.format(done=len(found) - len(failed), failed=len(failed))
        return strings.BATCH_DONE.format(n=len(found), folder=Path(folder).name)

    job = _Job(work)
    window.feedback.begin("export")
    job.signals.done.connect(window._export_finished)
    QThreadPool.globalInstance().start(job)
    return job
