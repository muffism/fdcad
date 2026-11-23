"""Parting Line panel (TR84, D1415)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_direction_pick_is_stored_as_one_reference(qtbot: QtBot, window: MainWindow) -> None:
    from fdcad.ui.property_panel.forms.parting_line_form import start_parting_line

    tab, _ids = _open(qtbot, window)
    start_parting_line(window, tab)
    form = window.panel.form
    assert form is not None and type(form).__name__ == "PartingLineForm"
    report = tab.session.report
    assert report is not None and report.body is not None
    top = next(n for n, _f in report.body.faces if n.endswith("/cap/end"))
    form.take_shapes(report.body, [report.body.face(top)])
    made = window.panel.current_feature()
    assert made is not None and made.refs["direction"]["name"] == top
    window.panel.reject()


def test_split_faces_tick_is_written(qtbot: QtBot, window: MainWindow) -> None:
    """TR84 (D1811)."""
    from fdcad.ui.property_panel.forms.parting_line_form import start_parting_line

    tab, _ids = _open(qtbot, window)
    start_parting_line(window, tab)
    form = window.panel.form
    assert form is not None and "split_faces" in form.checks
    report = tab.session.report
    assert report is not None and report.body is not None
    top = next(n for n, _f in report.body.faces if n.endswith("/cap/end"))
    form.take_shapes(report.body, [report.body.face(top)])
    form.checks["split_faces"].setChecked(True)
    made = window.panel.current_feature()
    assert made is not None and made.params["split_faces"] is True
    window.panel.reject()
