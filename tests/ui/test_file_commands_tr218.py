"""Save All, Close All, Revert to Saved and the parts from last time (TR218, D961)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Variable
from fdcad.core.units import Kind
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def _saved(qtbot: QtBot, window: MainWindow, path: Path):  # type: ignore[no-untyped-def]
    tab, _ids = _open(qtbot, window)
    assert window._save_to(tab, path)
    return tab


def _dirty(tab) -> None:  # type: ignore[no-untyped-def]
    from fdcad.ui.commands.document import SetVariables

    variables = [*tab.session.document.variables, Variable("Extra", Kind.LENGTH, "1mm", 1.0)]
    tab.session.undo.push(SetVariables(tab.session, variables))
    assert tab.session.is_dirty


def test_save_all_and_backups(qtbot: QtBot, window: MainWindow, tmp_path: Path) -> None:
    window.settings.backup_count = 2
    tab = _saved(qtbot, window, tmp_path / "a.fdprt")
    _dirty(tab)
    assert window.save_all() == 1
    assert not tab.session.is_dirty
    assert (tmp_path / "Backups" / "a.backup1.fdprt").is_file()  # the first save's file
    assert window.save_all() == 0


def test_revert_to_saved(
    qtbot: QtBot, window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tab = _saved(qtbot, window, tmp_path / "b.fdprt")
    _dirty(tab)
    monkeypatch.setattr(window, "confirm_revert", lambda _name: True)
    assert window.revert_to_saved()
    current = window.current
    assert current is not None and current is not tab
    assert all(v.name != "Extra" for v in current.session.document.variables)
    assert not current.session.is_dirty


def test_close_all_asks_then_closes(
    qtbot: QtBot, window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tab = _saved(qtbot, window, tmp_path / "c.fdprt")
    _dirty(tab)
    monkeypatch.setattr(window, "_ask_unsaved", lambda _i: QMessageBox.StandardButton.Cancel)
    assert not window.close_all()
    assert window.tabs.count() >= 1
    monkeypatch.setattr(window, "_ask_unsaved", lambda _i: QMessageBox.StandardButton.Discard)
    assert window.close_all()
    assert window.tabs.count() == 0


def test_last_session_is_kept_on_quit(qtbot: QtBot, window: MainWindow, tmp_path: Path) -> None:
    _saved(qtbot, window, tmp_path / "d.fdprt")
    window.close()
    assert window.settings.last_session == [str(tmp_path / "d.fdprt")]
