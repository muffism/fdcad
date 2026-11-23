"""Settings by Height in the app and in Open in Slicer (TR384, D1208)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.printing.heights import HEIGHT_CHANGES
from fdcad.ui import strings_print
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.print_tools import heights_tool
from fdcad.ui.print_tools.heights_tool import HeightsDialog
from tests.ui.test_body_display import _open
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def test_add_a_pause_and_a_setting_then_export(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert "print.height_changes" in BY_ID
    tab = _open(qtbot, window)

    def choose(dialog: HeightsDialog) -> bool:
        r = dialog.add_row({"z": 3.0, "kind": "pause", "note": "nuts"})
        assert not dialog.widget(r, 3).isEnabled()
        s = dialog.add_row({"z": 2.0, "kind": "setting", "key": "infill", "value": 50})
        assert dialog.widget(s, 3).isEnabled()
        return True

    monkeypatch.setattr(heights_tool, "run", choose)
    window.commands.actions["print.height_changes"].trigger()
    kept = tab.session.document.print_setup[HEIGHT_CHANGES]
    assert [e["z"] for e in kept] == [2.0, 3.0]
    assert tab.session.undo.undoText() == strings_print.HEIGHTS_UNDO
    target = tmp_path / "paused.3mf"
    window.export("3mf", target)
    qtbot.waitUntil(
        lambda: target.exists() and not window.feedback.running("export"), timeout=30000
    )
    with zipfile.ZipFile(target) as package:
        assert "Metadata/custom_gcode_per_layer.xml" in package.namelist()
    tab.session.undo.undo()
    assert HEIGHT_CHANGES not in tab.session.document.print_setup
