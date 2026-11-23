"""File, Mirror Part (TR73, D899): save the opposite hand of the open part as a new
part file and open it. The mirroring runs in the background (CLAUDE.md rule 2)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QFileDialog

from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow


def ask_path(window: MainWindow, suggested: str) -> str:
    """Where to save the new part; tests replace this."""
    path, _ = QFileDialog.getSaveFileName(
        window, strings.MIRROR_PART_TITLE, suggested, strings.FILTER_FDEF
    )
    return path


def mirror_part(window: MainWindow) -> bool:
    """Ask where, then build, save and open the mirrored part. True when started."""
    from fdcad.core.io import fdef
    from fdcad.core.mirror_part import mirrored_document
    from fdcad.ui.print_tools import jobs

    tab = window.current
    report = tab.session.report if tab is not None else None
    if tab is None or report is None or report.body is None:
        window.status.setText(strings.MIRROR_PART_EMPTY)
        return False
    name = tab.session.title.rstrip("*") or "Part"
    path = ask_path(window, f"{name} mirrored.fdprt")
    if not path:
        return False
    shape, units = report.body.shape, tab.session.document.units

    def work() -> Any:
        doc = mirrored_document(shape, units, name)
        fdef.save(doc, path)
        return path

    def done(saved: Any) -> None:
        window.status.setText(strings.MIRROR_PART_DONE.format(path=saved))
        window.open_path(Path(str(saved)))

    def failed(message: str) -> None:
        window.status.setText(strings.MIRROR_PART_FAILED.format(reason=message))

    window.status.setText(strings.MIRROR_PART_WORKING)
    jobs.start(work, done, failed)
    return True
