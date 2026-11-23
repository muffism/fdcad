"""Layer Fit Check from the Evaluate tools (TR187 item 1, D1209)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox
from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.print_tools.layer_fit_tool import layer_fit
from tests.ui.test_body_display import _open
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def test_check_runs_and_says_what_it_found(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "information", lambda _w, _t, body: shown.append(body))
    _open(qtbot, window)
    assert "evaluate.layer_fit" in window.commands.actions
    assert layer_fit(window) is not None
    qtbot.waitUntil(lambda: window.status.text().startswith("Layer fit"), timeout=30000)
