"""Drop files on the window to open them (TR377, D765)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from fdcad.core.io import fdef
from fdcad.ui.main_window.file_drop import dropped_paths, openable
from fdcad.ui.main_window.window import MainWindow
from tests.core.equations.test_equations import _plate
from tests.ui.test_main_window import _folders, window

__all__ = ["_folders", "window"]


def _mime(*paths: Path) -> QMimeData:
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])
    return mime


def _send(widget, mime: QMimeData) -> tuple[bool, bool]:  # type: ignore[no-untyped-def]
    """Drag over then drop on ``widget``: (enter accepted, drop accepted)."""
    action = Qt.DropAction.CopyAction
    enter = QDragEnterEvent(
        QPointF(5, 5).toPoint(),
        action,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(widget, enter)
    drop = QDropEvent(
        QPointF(5, 5), action, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
    )
    QApplication.sendEvent(widget, drop)
    return enter.isAccepted(), drop.isAccepted()


def test_which_files_open() -> None:
    for name in ("a.fdprt", "a.FDEF", "a.step", "a.igs", "a.stl", "a.3mf", "a.obj"):
        assert openable(Path(name)), name
    assert not openable(Path("notes.txt"))
    assert dropped_paths(None) == []
    assert [p.name for p in dropped_paths(_mime(Path("x/a.stl")))] == ["a.stl"]


def test_dropping_a_part_opens_it(qtbot: QtBot, window: MainWindow, tmp_path: Path) -> None:
    part = tmp_path / "plate.fdprt"
    fdef.save(_plate(), part)
    before = window.tabs.count()
    entered, dropped = _send(window, _mime(part))
    assert entered and dropped
    assert window.tabs.count() == before + 1
    assert window.current is not None and window.current.session.path == part
    # Dropped again: its tab comes forward, no second copy.
    _send(window, _mime(part))
    assert window.tabs.count() == before + 1


def test_dropping_other_files_says_why(qtbot: QtBot, window: MainWindow, tmp_path: Path) -> None:
    note = tmp_path / "notes.txt"
    note.write_text("x", encoding="utf-8")
    entered, _dropped = _send(window, _mime(note))
    assert not entered  # the cursor shows that it cannot drop here
    assert window.file_drop.open([note]) == 0
    assert "notes.txt was not opened" in window.status.text()


def test_the_tree_and_the_view_take_file_drops_too(
    qtbot: QtBot, window: MainWindow, tmp_path: Path
) -> None:
    from tests.ui.test_main_window import _open_plate

    tab, _e = _open_plate(qtbot, window)
    part = tmp_path / "other.fdprt"
    fdef.save(_plate(), part)
    assert window.tree is not None
    before = window.tabs.count()
    _send(window.tree.viewport(), _mime(part))
    assert window.tabs.count() == before + 1
    assert tab.viewport.acceptDrops()
