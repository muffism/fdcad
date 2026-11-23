"""Remove History turns the part into one plain body (TR158, D983)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.features.solids import volume_of
from fdcad.ui.main_window import remove_history
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_remove_history_keeps_the_shape(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    tab, _ids = _open(qtbot, window)
    session = tab.session
    assert session.report is not None and session.report.body is not None
    before = volume_of(session.report.body.shape)
    count = len(session.document.features)
    monkeypatch.setattr(remove_history, "confirm", lambda _w, _n: True)
    with qtbot.waitSignal(session.rebuilt, timeout=30000):
        assert window.remove_history.run()
    types = [f.type for f in session.document.features[4:]]
    assert types == ["import_step"]
    report = session.report
    assert report is not None and report.body is not None
    assert volume_of(report.body.shape) == pytest.approx(before, rel=1e-6)
    with qtbot.waitSignal(session.rebuilt, timeout=30000):
        session.undo.undo()
    assert len(session.document.features) == count


def test_nothing_to_keep_says_so(qtbot: QtBot, window: MainWindow) -> None:
    from fdcad.ui.session import DocumentSession

    session = DocumentSession.new(window.settings.default_units, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000, raising=False):
        window.add_session(session)
    assert not window.remove_history.run()
    assert "Build the part first" in window.status.text()
