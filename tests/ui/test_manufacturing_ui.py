"""Manufacturing Check window (TR295, TR296, D790)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window import manufacturing_tool
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.property_panel.narrow import words_of
from fdcad.ui.session import DocumentSession
from tests.core.features.test_corner_relief import _pocket
from tests.core.features.test_hole import add_hole, on_top
from tests.ui.test_main_window import _folders, window

__all__ = ["_folders", "window"]


def test_command_and_icon() -> None:
    from fdcad.ui.icons.audit import audit

    assert BY_ID["evaluate.manufacturing"].label == "Manufacturing Check"
    assert BY_ID["evaluate.manufacturing"].keys == () and audit("evaluate.manufacturing") == []


def _run(qtbot: QtBot, window: MainWindow, doc: object) -> manufacturing_tool.ManufacturingTool:
    session = DocumentSession(doc, None, window)  # type: ignore[arg-type]
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    tool = window.manufacturing
    assert window.commands.trigger("evaluate.manufacturing")
    assert tool.check()
    qtbot.waitUntil(lambda: tool.findings is not None, timeout=20000)
    return tool


def test_a_sharp_corner_gets_a_corner_relief(qtbot: QtBot, window: MainWindow) -> None:
    doc, _cut = _pocket()
    tool = _run(qtbot, window, doc)
    assert tool.findings is not None
    row = next(i for i, f in enumerate(tool.findings) if f.kind == "sharp_corner")
    tool.found.setCurrentRow(row)
    assert tool.fix_button.isEnabled() and words_of(tool.fix_button) == "Add Corner Relief"
    tab = window.current
    assert tab is not None
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert tool.apply_fix()
    made = tab.session.document.features[-1]
    assert made.type == "corner_relief" and len(made.refs["edges"]) == 1
    assert tab.session.report is not None
    assert tab.session.report.results[made.id].state.value != "error"


def test_snap_a_hole_to_stock_and_profiles_round_trip(
    qtbot: QtBot, window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(doc, sk, face=top, diameter=5.25, depth=6.0)
    tool = _run(qtbot, window, doc)
    assert tool.findings is not None
    row = next(i for i, f in enumerate(tool.findings) if f.kind == "drill_size")
    tool.found.setCurrentRow(row)
    assert words_of(tool.fix_button) == "Snap to Stock Size"
    tab = window.current
    assert tab is not None
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert tool.apply_fix()
    assert tab.session.document.feature(fid).params["diameter"].value == pytest.approx(5.2)
    # Edit a rule, save, change it, load it back.
    target = tmp_path / "shop.fdmfg"
    monkeypatch.setattr(manufacturing_tool, "ask_save_path", lambda _w: str(target))
    monkeypatch.setattr(manufacturing_tool, "ask_open_path", lambda _w: str(target))
    tool.rules.item(0, 1).setText("4")
    assert tool.profiles["milling"]["tool_diameter"] == 4.0
    assert tool.save() and target.exists()
    tool.rules.item(0, 1).setText("8")
    assert tool.load() and tool.profiles["milling"]["tool_diameter"] == 4.0
    tool.rules.item(0, 1).setText("-1")
    assert "number of 0 or more" in tool.summary.text()
    # Every process is checked now (TR298, TR299, D805).
    tool.process.setCurrentIndex(tool.process.findData("moulding"))
    assert tool.check()


def test_the_printer_in_use_seeds_its_process(window: MainWindow) -> None:
    """The active printer's process starts from that printer's limits (TR295 item 2, D801)."""
    from dataclasses import replace

    from fdcad.core.printing.profiles import PrinterProfile
    from fdcad.ui.main_window.manufacturing_tool import ManufacturingTool
    from fdcad.ui.preferences import print_settings

    resin = replace(PrinterProfile(), name="Resin box", process="resin", min_wall=0.4)
    print_settings.set_profiles(window.settings, [resin], 0)
    tool = ManufacturingTool(window)
    assert tool.profiles["resin"]["min_wall"] == 0.4
    assert tool.profiles["fdm"]["min_wall"] == 0.8
    assert PrinterProfile.from_dict(resin.to_dict()).process == "resin"
    assert PrinterProfile.from_dict({"process": "laser"}).process == "fdm"
