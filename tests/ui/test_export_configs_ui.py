"""File, Export, Export Configurations (TR196, D827)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core import configurations as configs
from fdcad.ui.main_window import export_configs as ec
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_export_two_configurations_in_the_background(
    qtbot: QtBot, window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tab, _ids = _open(qtbot, window)
    configs.add(tab.session.document, "Second")

    def accept(dialog: ec.ExportConfigsDialog) -> bool:
        dialog.folder.setText(str(tmp_path))
        dialog.kind.setCurrentIndex(dialog.kind.findData("stl"))
        return True

    monkeypatch.setattr(ec, "run", accept)
    job = ec.export_configurations(window)
    assert job is not None
    with qtbot.waitSignal(job.signals.done, timeout=60000) as done:
        pass
    assert "2 configurations exported" in done.args[0]
    # Files only: the data folder is here too, with the crash guard's notes (D1035).
    made = sorted(p.suffix for p in tmp_path.iterdir() if p.is_file())
    assert made == [".stl", ".stl", ".txt"]
    assert configs.active_name(tab.session.document) == "Default"
