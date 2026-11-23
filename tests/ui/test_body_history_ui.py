"""Show Feature History for a body (TR153 item 2, D972)."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog
from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.features.test_multibody import two_blocks
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_history_of_one_body_lists_its_features(qtbot: QtBot, window: MainWindow) -> None:
    doc, first, second, _body = two_blocks(gap=5.0)
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    shown: list[list[str]] = []
    real = window.body_display.show_history
    window.body_display.show_history = lambda t, i, f: (shown.append(f), real(t, i, f))[1]  # type: ignore[method-assign]
    window.tree.body_requested.emit("history", 0)
    qtbot.waitUntil(lambda: bool(shown), timeout=20000)
    ids = set(shown[0])
    assert (first in ids) != (second in ids)  # one block's features only
    dialogs = window.findChildren(QDialog, "body_history")
    assert dialogs
    dialogs[0].close()
