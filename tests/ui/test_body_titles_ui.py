"""Rename Body on body rows and the names in 3MF export (TR183, D1201)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from PySide6.QtWidgets import QInputDialog
from pytestqt.qtbot import QtBot

from fdcad.core.body_titles import titles_of
from fdcad.ui import strings
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_display import _body_row, _open
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def test_rename_a_body_label_it_undo_and_export(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tab = _open(qtbot, window)
    session = tab.session
    assert window.tree is not None
    menu = window.tree._body_menu(1)
    action = next(a for a in menu.actions() if a.text() == strings.RENAME_BODY)
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *_a, **_k: ("Lid", True)))
    action.trigger()
    report = session.report
    assert report is not None
    assert titles_of(session.document, report.body)[1] == "Lid"
    assert session.undo.undoText() == strings.RENAME_BODY_UNDO
    qtbot.waitUntil(lambda: _body_row(window, 1).text(0) == "Lid", timeout=10000)
    target = tmp_path / "named.3mf"
    window.export("3mf", target)
    qtbot.waitUntil(
        lambda: target.exists() and not window.feedback.running("export"), timeout=30000
    )
    with zipfile.ZipFile(target) as package:
        assert 'name="Lid"' in package.read("3D/3dmodel.model").decode()
    session.undo.undo()
    assert titles_of(session.document, report.body)[1] is None
