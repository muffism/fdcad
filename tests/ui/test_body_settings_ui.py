"""Print Settings on a body row and in Export 3MF (TR383, D1207)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.printing.body_settings import settings_of
from fdcad.ui import strings_print
from fdcad.ui.main_window import body_settings_dialog
from fdcad.ui.main_window.body_settings_dialog import BodySettingsDialog
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_display import _open
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def test_set_settings_export_and_undo(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tab = _open(qtbot, window)
    session = tab.session

    def choose(dialog: BodySettingsDialog) -> bool:
        assert not dialog.walls.isEnabled()
        dialog.ticks["walls"].setChecked(True)
        dialog.walls.setValue(5)
        dialog.ticks["supports"].setChecked(True)
        dialog.supports.setCurrentIndex(1)
        return True

    monkeypatch.setattr(body_settings_dialog, "run", choose)
    window.body_display.from_tree("settings", 1)
    report = session.report
    assert report is not None
    assert settings_of(session.document, report.body)[1] == {"walls": 5, "supports": False}
    assert session.undo.undoText() == strings_print.BODY_SETTINGS_UNDO
    target = tmp_path / "tuned.3mf"
    window.export("3mf", target)
    qtbot.waitUntil(
        lambda: target.exists() and not window.feedback.running("export"), timeout=30000
    )
    with zipfile.ZipFile(target) as package:
        config = package.read("Metadata/model_settings.config").decode()
    assert 'key="wall_loops" value="5"' in config
    session.undo.undo()
    assert settings_of(session.document, report.body)[1] == {}
