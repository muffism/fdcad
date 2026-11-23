"""Drop files on the window to open them (TR377, DECISIONS D765).

Dropping a part file (``.fdprt``, ``.fdef``), a STEP or IGES file or a mesh file
anywhere on the main window opens it, the same as File, Open: a part opens in
its own tab (or its tab comes forward when it is open already) and an import
file becomes a new part. The 3D views and the feature tree take drops for their
own drags (D684), so the filter is installed on them too and lets those drags
through. Other files are ignored and the status bar says why.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QMimeData, QObject
from PySide6.QtGui import QDropEvent

from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow

PART_SUFFIXES = (".fdprt", ".fdef")


def openable(path: Path) -> bool:
    """True for a file File, Open accepts."""
    from fdcad.ui.main_window.imports import is_import

    return path.suffix.lower() in PART_SUFFIXES or is_import(path)


def dropped_paths(mime: QMimeData | None) -> list[Path]:
    """The local files in a drop, in the order given."""
    if mime is None or not mime.hasUrls():
        return []
    return [Path(url.toLocalFile()) for url in mime.urls() if url.isLocalFile()]


class FileDrop(QObject):
    """Event filter that opens dropped files."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.window = window

    def watch(self, widget: QObject) -> None:
        """Take file drops on ``widget`` (and let its own drags through)."""
        if hasattr(widget, "setAcceptDrops"):
            widget.setAcceptDrops(True)
        widget.installEventFilter(self)

    def eventFilter(self, _obj: QObject, event: QEvent) -> bool:  # noqa: N802
        """Accept and open files; anything else goes on to the widget."""
        kind = event.type()
        if kind not in (QEvent.Type.DragEnter, QEvent.Type.DragMove, QEvent.Type.Drop):
            return False
        mime = event.mimeData() if hasattr(event, "mimeData") else None
        paths = dropped_paths(mime)
        if not paths:
            return False
        good = [p for p in paths if openable(p)]
        if kind != QEvent.Type.Drop:
            if good:
                event.acceptProposedAction()  # type: ignore[attr-defined]
                return True
            return False
        assert isinstance(event, QDropEvent)
        event.acceptProposedAction()
        self.open(paths)
        return True

    def open(self, paths: list[Path]) -> int:
        """Open every file that can be opened; returns how many were opened."""
        good = [p for p in paths if openable(p)]
        for path in good:
            self.window.open_path(path)
        skipped = len(paths) - len(good)
        if skipped:
            name = next(p.name for p in paths if not openable(p))
            self.window.status.setText(strings.DROP_SKIPPED.format(name=name, count=skipped))
        return len(good)
