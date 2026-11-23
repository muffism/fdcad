"""Temporary Axes toggle (TR17, D693)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_main_window import _folders, _open_plate, window

__all__ = ["_folders", "window"]


class _View:
    def __init__(self) -> None:
        self.calls: list[bool] = []

    def set_temporary_axes(self, on: bool) -> int:
        self.calls.append(on)
        return 0


def test_command_and_icon() -> None:
    from fdcad.ui.icons.audit import audit

    assert BY_ID["view.temporary_axes"].label == "Temporary Axes"
    assert audit("view.temporary_axes") == []


def test_toggle_reaches_every_open_part(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ext = _open_plate(qtbot, window)
    view = _View()
    tab.viewport = view  # type: ignore[assignment]
    action = window.commands.actions["view.temporary_axes"]
    assert action.isCheckable() and not action.isChecked()
    assert window.commands.trigger("view.temporary_axes")
    assert view.calls == [True]
    assert window.commands.trigger("view.temporary_axes")
    assert view.calls == [True, False]
