"""Esc stops a rebuild or a slow preview (TR126, D814)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox
from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_esc_stops_a_running_rebuild(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    tab, _ids = _open(qtbot, window)
    assert not window.stop_long_work()  # nothing running
    asked: list[str] = []

    def answer(_p: object, _t: str, text: str, *_a: object) -> QMessageBox.StandardButton:
        asked.append(text)
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", answer)
    monkeypatch.setattr(type(tab.session), "is_rebuilding", property(lambda _s: True))
    stopped: list[bool] = []
    monkeypatch.setattr(tab.session, "cancel_rebuild", lambda: stopped.append(True))
    assert window.stop_long_work()
    assert stopped == [True] and "Stop the rebuild" in asked[0]
    assert "stopped" in window.status.text().lower()


def test_esc_stops_a_slow_preview_first(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    import threading

    from fdcad.ui.body_tools import flow

    tab, ids = _open(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None
    window._selection_changed(tab, [report.body.face(f"{ids['boss']}/cap/end")])
    assert flow.start(window, "feature.move_face")
    monkeypatch.setattr(QMessageBox, "question", lambda *_a: QMessageBox.StandardButton.Yes)
    window.preview._cancel = threading.Event()  # as if a preview were being worked out
    assert window.preview.is_running
    assert window.stop_long_work()
    assert not window.preview.is_running and window.editing == "feature"  # panel stays
    assert window.panel is not None
    window.panel.reject()
