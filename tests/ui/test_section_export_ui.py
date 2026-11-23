"""Export Section and Outline from the File menu (TR300, D1204)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.print_tools import section_export
from fdcad.ui.print_tools.section_export import SectionExportDialog
from tests.ui.test_body_display import _open
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def test_outline_of_two_bodies_with_an_engraved_one(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert "file.export_section" in BY_ID
    _open(qtbot, window)

    def choose(dialog: SectionExportDialog) -> bool:
        assert dialog.uses.rowCount() == 2
        dialog.mode.setCurrentIndex(dialog.mode.findData("outline"))
        assert not dialog.offset.isEnabled()
        dialog.set_use(1, "engrave")
        return True

    monkeypatch.setattr(section_export, "run", choose)
    target = tmp_path / "plates.svg"
    job = section_export.export(window, str(target))
    assert job is not None
    qtbot.waitUntil(lambda: "ENGRAVE layers" in window.status.text(), timeout=30000)
    text = target.read_text()
    assert 'id="CUT"' in text and 'id="ENGRAVE"' in text
