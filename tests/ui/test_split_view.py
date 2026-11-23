"""Split View (TR16, D699). The panes need a GPU; the test platform checks the rules."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.viewport.split import cells, start_views
from tests.ui.test_main_window import _folders, _open_plate, window

__all__ = ["_folders", "window"]


def test_layouts() -> None:
    assert cells("one") == [(0, 0)]
    assert cells("side") == [(0, 0), (0, 1)]
    assert cells("stacked") == [(0, 0), (1, 0)]
    assert len(set(cells("four"))) == 4
    assert start_views("four") == ["front", "top", "right", "iso"]
    for name in ("one", "side", "stacked", "four"):
        assert cells(name)[0] == (0, 0)  # the main view never moves
        assert len(start_views(name)) == len(cells(name))


def test_commands_and_icons() -> None:
    from fdcad.ui.icons.audit import audit

    for name in ("one", "side", "stacked", "four"):
        cid = f"view.split_{name}"
        assert cid in BY_ID and BY_ID[cid].keys == ()
        assert audit(cid) == []


def test_without_a_3d_view_it_says_so(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ext = _open_plate(qtbot, window)
    if hasattr(tab.viewport, "_viewer"):
        return  # a real 3D view: checked by hand
    window.set_split("four")
    assert tab.split == "one" and not tab.panes
    assert "3D view" in window.status.text()
    assert window.commands.actions["view.split_one"].isChecked()


class _Pane:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def set_view(self, name: str) -> None:
        self.calls.append(name)


def test_the_active_pane_takes_view_commands(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ext = _open_plate(qtbot, window)
    pane = _Pane()
    tab.active_pane = pane
    window.set_view("top")
    assert pane.calls == ["top"]
    tab.active_pane = None
    window.set_view("front")
    assert pane.calls == ["top"]
