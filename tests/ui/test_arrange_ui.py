"""Suggest Orientation and Arrange on Bed (TR301, D1210)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.features.solids import solids
from fdcad.ui import strings_print
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.print_tools.arrange_tool import arrange_bodies, suggest_orientation
from tests.ui.test_body_display import _open
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def test_suggest_lays_the_best_face_flat(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    assert suggest_orientation(window) is not None
    qtbot.waitUntil(lambda: "down_face" in (tab.session.document.print_setup or {}), timeout=30000)


def test_arrange_adds_moves_in_one_undo_step(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    session = tab.session
    before = len(session.document.features)
    assert arrange_bodies(window, 8.0) is not None
    # The status line may already show the rebuild, so wait for the features.
    qtbot.waitUntil(lambda: len(session.document.features) > before, timeout=30000)
    added = [f for f in session.document.features[before:] if f.type == "move_copy_body"]
    assert added
    assert session.undo.undoText() == strings_print.ARRANGE_UNDO
    qtbot.waitUntil(lambda: session.report is not None and not session.is_rebuilding, timeout=30000)
    report = session.report
    assert report is not None and report.body is not None
    assert len(solids(report.body.shape)) == 2
    session.undo.undo()
    assert len(session.document.features) == before
