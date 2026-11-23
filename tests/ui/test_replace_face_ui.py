"""Replace Face panel and view menu (TR130, D1412)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_panel_takes_faces_then_target(qtbot: QtBot, window: MainWindow) -> None:
    tab, ids = _open(qtbot, window)
    from fdcad.ui.property_panel.forms.replace_face_form import start_replace

    start_replace(window, tab)
    form = window.panel.form
    assert form is not None and type(form).__name__ == "ReplaceFaceForm"
    report = tab.session.report
    assert report is not None and report.body is not None
    names = [n for n, _f in report.body.faces]
    first = report.body.face(names[0])
    second = report.body.face(names[1])
    form.take_shapes(report.body, [first])
    form.take_shapes(report.body, [second])
    made = window.panel.current_feature()
    assert made is not None
    assert [r["name"] for r in made.refs["faces"]] == [names[0]]
    assert [r["name"] for r in made.refs["target"]] == [names[1]]
    window.panel.reject()
    assert ids
