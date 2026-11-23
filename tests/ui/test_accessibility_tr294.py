"""Describe Part and Large Controls (TR294 items 2 and 3, D2017)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox, QToolButton
from pytestqt.qtbot import QtBot

from fdcad.ui import accessibility
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_describe_part_lists_bodies_size_and_features(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    tab, _ids = _open(qtbot, window)
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: shown.append(a[2]))
    text = accessibility.show_description(window)
    assert shown == [text]
    assert "Bodies: 1." in text and "millimetres" in text
    names = [f.name for f in tab.session.document.features if f.type not in ("origin", "plane")]
    assert all(name in text for name in names)


def test_large_controls_grow_buttons_and_back(qtbot: QtBot, window: MainWindow) -> None:
    buttons = [b for b in window.findChildren(QToolButton) if getattr(b, "role", "") == "large"]
    assert buttons
    before = buttons[0].iconSize().width()
    accessibility.apply_large_controls(window, True)
    assert buttons[0].iconSize().width() == round(before * 1.5)
    accessibility.apply_large_controls(window, False)
    assert buttons[0].iconSize().width() == before
