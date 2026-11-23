"""Interference Check window (TR150, D771)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.features.test_multibody import two_blocks
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def _open(qtbot: QtBot, window: MainWindow, gap: float):  # type: ignore[no-untyped-def]  # noqa: F811
    doc, _a, _b, _body = two_blocks(gap=gap)
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = window.add_session(session)
    return tab


def test_command_and_icon() -> None:
    from fdcad.ui.icons.audit import audit

    assert BY_ID["evaluate.interference"].label == "Interference Check"
    assert BY_ID["evaluate.interference"].keys == ()
    assert audit("evaluate.interference") == []


def test_a_small_gap_is_listed_and_shown(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window, gap=0.2)
    tool = window.interference
    assert window.commands.trigger("evaluate.interference")
    assert tool.bodies.count() == 2
    assert tool.check()
    qtbot.waitUntil(lambda: tool.results is not None, timeout=20000)
    assert tool.found.count() == 1 and "gap 0.2 mm" in tool.found.item(0).text()
    assert len(tab.viewport.print_layers["interference"]) == 1  # type: ignore[attr-defined]
    tool.ignore_pair()
    assert tool.found.count() == 0
    tool.results = None
    tool.check()
    qtbot.waitUntil(lambda: tool.results is not None, timeout=20000)
    assert tool.results == [] and "No bodies" in tool.summary.text()  # ignored now
    window.commands.trigger("evaluate.interference")
    assert tab.viewport.print_layers["interference"] == []  # type: ignore[attr-defined]
    assert not tab.session.is_dirty


def test_far_apart_and_excluded(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    from PySide6.QtCore import Qt

    _open(qtbot, window, gap=10.0)
    tool = window.interference
    window.commands.trigger("evaluate.interference")
    tool.check()
    qtbot.waitUntil(lambda: tool.results is not None, timeout=20000)
    assert tool.results == []
    tool.bodies.item(1).setCheckState(Qt.CheckState.Unchecked)
    assert tool._excluded() == [1]
