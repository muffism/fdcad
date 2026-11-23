"""File, Export, Export Configurations (TR196, D827).

A dialog with a tick per configuration, the file kind and a folder. The files
are written in the background from copies of the part, so the open part and
its active configuration do not change.
"""

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
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow


class ExportConfigsDialog(QDialog):
    """Choose configurations, a file kind and a folder."""

    def __init__(self, names: list[str], folder: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(strings.EXPORT_CONFIGS_TITLE)
        self.list = QListWidget()
        for name in names:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.list.addItem(item)
        self.kind = QComboBox()
        for key, label in strings.EXPORT_CONFIGS_KINDS.items():
            self.kind.addItem(label, key)
        self.folder = QLineEdit(folder)
        browse = QPushButton(strings.EXPORT_CONFIGS_BROWSE)
        browse.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.addWidget(self.folder, 1)
        row.addWidget(browse)
        form = QFormLayout()
        form.addRow(strings.EXPORT_CONFIGS_KIND, self.kind)
        form.addRow(strings.EXPORT_CONFIGS_FOLDER, row)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.list)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, strings.EXPORT_CONFIGS_FOLDER, self.folder.text()
        )
        if chosen:
            self.folder.setText(chosen)

    def chosen(self) -> list[str]:
        """The ticked configuration names, in order."""
        return [
            self.list.item(i).text()
            for i in range(self.list.count())
            if self.list.item(i).checkState() == Qt.CheckState.Checked
        ]


def run(dialog: QDialog) -> bool:
    """Show the dialog; tests replace this."""
    return dialog.exec() == QDialog.DialogCode.Accepted


def export_configurations(window: MainWindow) -> Any:
    """Ask, then write one file per ticked configuration in the background. Returns the
    job, or None when nothing was started."""
    from PySide6.QtCore import QThreadPool

    from fdcad.core import configurations as configs
    from fdcad.core.io.export_configs import export_configurations as write
    from fdcad.ui.main_window.window import _Job

    tab = window.current
    if tab is None:
        return None
    session = tab.session
    if session.is_rebuilding:
        window.status.setText(strings.EXPORT_WAIT)
        return None
    configs.sync_active(session.document)
    base = (session.path.stem if session.path is not None else session.name) or "Part"
    start = str(session.path.parent) if session.path is not None else str(Path.home())
    dialog = ExportConfigsDialog(configs.names(session.document), start, window)
    accepted = run(dialog)
    names, kind, folder = dialog.chosen(), str(dialog.kind.currentData()), dialog.folder.text()
    dialog.deleteLater()
    if not accepted:
        return None
    if not names or not folder.strip():
        window.status.setText(strings.EXPORT_CONFIGS_NONE)
        return None
    import copy

    doc = copy.deepcopy(session.document)  # the background work never touches the open part

    def work() -> str:
        found = write(doc, names, folder, kind, base)
        failed = [o.name for o in found if not o.ok]
        if failed:
            return strings.EXPORT_CONFIGS_SOME.format(
                done=len(found) - len(failed), failed=", ".join(failed)
            )
        return strings.EXPORT_CONFIGS_DONE.format(n=len(found), folder=Path(folder).name)

    job = _Job(work)
    window.feedback.begin("export")
    job.signals.done.connect(window._export_finished)
    QThreadPool.globalInstance().start(job)
    return job
