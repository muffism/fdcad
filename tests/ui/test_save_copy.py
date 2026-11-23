"""Save a Copy (TR97, D806)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog
from pytestqt.qtbot import QtBot

from fdcad.core.io import fdef
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_save_a_copy_keeps_the_open_part(
    qtbot: QtBot, window: MainWindow, tmp_path: Path, monkeypatch: object
) -> None:
    assert BY_ID["file.save_copy"].keys == () and BY_ID["file.save_copy_open"].keys == ()
    tab, _ids = _open(qtbot, window)
    session = tab.session
    target = tmp_path / "copy.fdprt"
    monkeypatch.setattr(  # type: ignore[attr-defined]
        QFileDialog, "getSaveFileName", staticmethod(lambda *_a, **_k: (str(target), ""))
    )
    before_path, dirty = session.path, session.is_dirty
    assert window.save_copy()
    assert target.exists()
    assert fdef.load(target).features == session.document.features
    assert session.path == before_path and session.is_dirty == dirty
    tabs = window.tabs.count()
    other = tmp_path / "second.fdprt"
    monkeypatch.setattr(  # type: ignore[attr-defined]
        QFileDialog, "getSaveFileName", staticmethod(lambda *_a, **_k: (str(other), ""))
    )
    assert window.save_copy(open_it=True)
    qtbot.waitUntil(lambda: window.tabs.count() == tabs + 1, timeout=20000)
