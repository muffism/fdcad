"""Pause Rebuilds and checkpoints (TR276, D835)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.ui.commands.document import SetParam
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def _depth(tab, fid):  # type: ignore[no-untyped-def]
    return tab.session.document.feature(fid).params["depth"].value


def test_pause_collects_edits_then_rebuild_or_discard(qtbot: QtBot, window: MainWindow) -> None:
    tab, ids = _open(qtbot, window)
    session = tab.session
    boss = ids["boss"]
    built = session.report
    window.pause_action.trigger()
    assert session.paused and window.pause_action.isChecked()
    session.undo.push(SetParam(session, boss, "depth", Param("7", 7.0)))
    assert session.out_of_date and session.report is built  # nothing rebuilt
    assert "Out of date" in window.status.text()
    session.discard_paused()
    assert not session.paused and _depth(tab, boss) != 7.0
    qtbot.waitUntil(lambda: not session.is_rebuilding, timeout=20000)
    session.set_paused(True)
    session.undo.push(SetParam(session, boss, "depth", Param("8", 8.0)))
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.rebuild_paused(stay=True)
    assert session.paused and not session.out_of_date
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.rebuild()  # Rebuild leaves the pause
    assert not session.paused


def test_a_checkpoint_stops_the_rebuild_until_continue(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ids = _open(qtbot, window)
    session = tab.session
    first = next(f for f in session.document.features if f.type == "extrude")
    assert first is not session.document.features[-1]
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.tree.toggle_checkpoint(session, first.id)
    assert session.stopped_at == first.id
    qtbot.waitUntil(lambda: "checkpoint" in window.status.text(), timeout=5000)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.continue_rebuild()
    assert session.stopped_at is None
