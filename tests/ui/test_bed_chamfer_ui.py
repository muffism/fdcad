"""Bed Edge Chamfer command (TR177, D779)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.print_tools import bed_chamfer_tool
from tests.ui.test_main_window import _folders, _open_plate, window

__all__ = ["_folders", "window"]


def test_command_and_icon() -> None:
    from fdcad.ui.icons.audit import audit

    assert BY_ID["print.bed_chamfer"].label == "Bed Edge Chamfer"
    assert BY_ID["print.bed_chamfer"].keys == () and audit("print.bed_chamfer") == []


def test_needs_a_bed_face_then_adds_one_chamfer(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fdcad.ui.commands.print_setup import SetPrintSetup

    tab, ext = _open_plate(qtbot, window)
    monkeypatch.setattr(bed_chamfer_tool, "ask_size", lambda _w, _s: 0.3)
    assert not bed_chamfer_tool.bed_chamfer(window)
    assert "No face is on the bed" in window.status.text()
    bottom = {"kind": "face", "name": f"{ext}/cap/start"}
    tab.session.undo.push(SetPrintSetup(tab.session, bottom, "Lay flat"))
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert bed_chamfer_tool.bed_chamfer(window)
    made = tab.session.document.features[-1]
    assert made.type == "chamfer" and made.refs["faces"] == [bottom]
    assert made.params["distance"].value == pytest.approx(0.3)
    assert tab.session.report is not None
    assert tab.session.report.results[made.id].state.value != "error"
