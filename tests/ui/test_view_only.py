"""Open a part for viewing only, then Edit (TR356, D971)."""

from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Variable
from fdcad.core.units import Kind
from fdcad.ui.commands.document import SetVariables
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def _push_variable(tab) -> None:  # type: ignore[no-untyped-def]
    variables = [*tab.session.document.variables, Variable("Extra", Kind.LENGTH, "1mm", 1.0)]
    tab.session.undo.push(SetVariables(tab.session, variables))


def test_view_only_refuses_changes_until_edit(
    qtbot: QtBot, window: MainWindow, tmp_path: Path
) -> None:
    first, _ids = _open(qtbot, window)
    path = tmp_path / "view.fdprt"
    assert window._save_to(first, path)
    window.close_tab(window.tabs.indexOf(first), ask=False)
    with qtbot.waitSignal(window.tabs.currentChanged, timeout=20000, raising=False):
        assert window.open_view_only(path)
    tab = window.current
    assert tab is not None and tab.session.view_only
    assert "view only" in window.tabs.tabText(window.tabs.indexOf(tab))
    bar = tab.message_bars.bars["view_only"]
    _push_variable(tab)
    assert all(v.name != "Extra" for v in tab.session.document.variables)
    assert not tab.session.is_dirty
    assert "viewing only" in window.status.text()
    assert bar.action_button is not None
    bar.action_button.click()
    assert not tab.session.view_only and "view_only" not in tab.message_bars.bars
    _push_variable(tab)
    assert any(v.name == "Extra" for v in tab.session.document.variables)
