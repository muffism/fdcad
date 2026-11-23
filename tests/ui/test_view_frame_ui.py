"""Set the current view as Front or Home, and Reset (TR333, D955)."""

from __future__ import annotations

from typing import Any

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document import view_frame as vf
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def _camera(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> list[tuple[Any, ...]]:
    calls: list[tuple[Any, ...]] = []

    def call(name: str, *args: Any) -> Any:
        calls.append((name, *args))
        if name == "eye_up":
            return (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)  # looking from the right
        return None

    monkeypatch.setattr(window, "_call_view", call)
    return calls


def _close(a: Any, b: Any) -> bool:
    return all(abs(x - y) < 1e-9 for x, y in zip(a, b, strict=True))


def test_set_front_turns_the_standard_views(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    tab, _ids = _open(qtbot, window)
    calls = _camera(window, monkeypatch)
    assert window.view_frame.set_current_as("front")
    extra = tab.session.document.extra
    assert vf.KEY in extra
    calls.clear()
    window.set_view("front")
    assert calls[-1][0] == "look" and _close(calls[-1][1], (1.0, 0.0, 0.0))
    window.set_view("right")  # the right side is now behind the old front
    assert _close(calls[-1][1], (0.0, 0.0, -1.0))
    tab.session.undo.undo()
    assert vf.KEY not in extra
    calls.clear()
    window.set_view("front")
    assert calls[-1] == ("set_view", "front")  # the usual views again


def test_home_and_reset(qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    tab, _ids = _open(qtbot, window)
    calls = _camera(window, monkeypatch)
    monkeypatch.setattr(window.view_frame, "ask_view", lambda: "home")
    assert window.view_frame.set_current_as()
    calls.clear()
    window.commands.actions["view.home"].trigger()
    assert calls[-1][0] == "look" and _close(calls[-1][1], (1.0, 0.0, 0.0))
    assert window.view_frame.reset()
    assert vf.KEY not in tab.session.document.extra
    assert not window.view_frame.reset()  # nothing left to reset
