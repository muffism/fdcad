"""Expected value checks in the window (TR359, D889)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.ui.main_window import expected_values as ev
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_configurations_ui import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_checks_are_kept_and_shown_after_a_rebuild(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    tab = _open(qtbot, window)

    def fill(dialog: ev.ExpectedValuesDialog) -> bool:
        dialog.add_row({"kind": "faces", "value": 6, "tolerance": 0})
        dialog.add_row({"kind": "size_x", "value": 999, "tolerance": 0.1})
        return True

    monkeypatch.setattr(ev, "run", fill)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert ev.open_checks(window)
    assert len(tab.session.document.extra["checks"]) == 2
    assert "Checks: 1 of 2 pass." in window.status.text()
    dialog = ev.ExpectedValuesDialog(tab.session)
    qtbot.addWidget(dialog)
    assert dialog.table.item(0, 4).text() == "Pass" and dialog.table.item(1, 4).text() == "Fail"
    dialog.use_current()
    assert dialog.checks()[1]["value"] == pytest.approx(  # type: ignore[index]
        float(dialog.table.item(1, 3).text())
    )
    tab.session.undo.undo()
    assert "checks" not in tab.session.document.extra
