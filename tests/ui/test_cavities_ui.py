"""Enclosed Cavities window (TR284, D772)."""

from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from fdcad.core.io.export import export_step
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import MainWindow
from tests.core.test_cavities import _box, _hollow_cube
from tests.ui.test_main_window import _folders, window

__all__ = ["_folders", "window"]


def test_command_and_icon() -> None:
    from fdcad.ui.icons.audit import audit

    assert BY_ID["evaluate.cavities"].label == "Enclosed Cavities"
    assert BY_ID["evaluate.cavities"].keys == () and audit("evaluate.cavities") == []


def test_find_and_drain(qtbot: QtBot, window: MainWindow, tmp_path: Path) -> None:
    step = tmp_path / "hollow.step"
    export_step(_hollow_cube(), step)
    session = window.import_flow.open_file(step)
    assert session is not None
    qtbot.waitUntil(lambda: session.report is not None, timeout=20000)
    tool = window.cavities
    assert window.commands.trigger("evaluate.cavities")
    qtbot.waitUntil(lambda: tool.voids is not None, timeout=20000)
    assert tool.found.count() == 1 and "1000 mm^3" in tool.found.item(0).text()
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        assert tool.add_drain()
    assert session.document.features[-1].type == "hole"
    tool.search()
    qtbot.waitUntil(lambda: tool.voids is not None, timeout=20000)
    assert tool.voids == [] and "No closed voids" in tool.summary.text()
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.undo.undo()  # one undo step takes the drain hole away
    assert session.document.features[-1].type != "hole"


def test_cup_volume(qtbot: QtBot, window: MainWindow, tmp_path: Path) -> None:
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut

    from fdcad.core.naming.names import faces_of

    cup = BRepAlgoAPI_Cut(_box(0, 0, 0, 20, 20, 20), _box(5, 5, 5, 15, 25, 15)).Shape()  # open +Y
    step = tmp_path / "cup.step"
    export_step(cup, step)
    session = window.import_flow.open_file(step)
    assert session is not None
    qtbot.waitUntil(lambda: session.report is not None, timeout=20000)
    tool = window.cavities
    window.commands.trigger("evaluate.cavities")
    tab = window.current
    assert tab is not None and session.report is not None and session.report.body is not None
    assert not tool.measure_cup()  # nothing picked
    assert "Pick the inside faces" in tool.summary.text()
    tab.selection = faces_of(session.report.body.shape)
    assert tool.measure_cup()
    qtbot.waitUntil(lambda: tool.cup is not None, timeout=20000)
    assert abs(tool.cup - 10 * 15 * 10) < 1e-3  # the inside holds 10 x 15 x 10 below the top
