"""Select Bodies by Size (TR70, D894)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.body_sizes import sizes
from fdcad.core.features.solids import solids
from fdcad.ui.main_window.bodies_by_size import BodiesBySizeDialog
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.test_body_sizes import _part
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_delete_the_small_bodies_in_one_step(qtbot: QtBot, window: MainWindow) -> None:
    doc, _fid = _part()
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = window.add_session(session)
    report = tab.session.report
    assert report is not None and report.body is not None
    dialog = BodiesBySizeDialog(window)
    qtbot.addWidget(dialog)
    dialog.set_bodies(sizes(report.body))
    dialog.slider.setValue(10)
    assert "2 of 3 bodies" in dialog.count.text()
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert dialog.act("delete")
    after = tab.session.report
    assert after is not None and after.body is not None
    assert len(solids(after.body.shape)) == 1
    assert tab.session.document.features[-1].type == "delete_body"
