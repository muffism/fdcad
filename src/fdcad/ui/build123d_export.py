"""File, Export, build123d Script (PLAN Phase 5, D342). The work runs on the thread pool."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QFileDialog

from fdcad.ui import strings_sheetmetal as text
from fdcad.ui.sheet_metal.flow import _ExportJob
from fdcad.ui.strings import clause

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow


def export_build123d(window: MainWindow, path: str | None = None) -> _ExportJob | None:
    """Ask for a file name and write the part's build123d script in the background."""
    tab = window.current
    if tab is None:
        return None
    title = tab.session.title.rstrip("*") or "Part"
    if path is None:
        path, _ = QFileDialog.getSaveFileName(
            window, text.EXPORT_BUILD123D, f"{title}.py", text.FILTER_PYTHON
        )
        if not path:
            return None
    doc = copy.deepcopy(tab.session.document)
    target = path

    def work() -> str:
        from fdcad.core.io.build123d import script_for

        try:
            script = script_for(doc, title)
            Path(target).write_text(script, encoding="utf-8", newline="\n")
        except OSError as exc:
            return text.BUILD123D_FAILED.format(error=clause(exc))
        return text.BUILD123D_DONE.format(name=Path(target).name)

    job = _ExportJob(work)
    job.signals.done.connect(window.status.setText)
    QThreadPool.globalInstance().start(job)
    return job
