"""Push Pull panel (TR267, D1413)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_next_parallel_face_sets_target_and_distance(qtbot: QtBot, window: MainWindow) -> None:
    from fdcad.ui.property_panel.forms.push_pull_form import start_push_pull

    tab, ids = _open(qtbot, window)
    start_push_pull(window, tab)
    form = window.panel.form
    assert form is not None and type(form).__name__ == "PushPullForm"
    report = tab.session.report
    assert report is not None and report.body is not None
    top = next(n for n, _f in report.body.faces if n.endswith("/cap/end"))
    form.take_shapes(report.body, [report.body.face(top)])
    assert form.next_parallel() is None
    made = window.panel.current_feature()
    assert made is not None
    assert [r["name"] for r in made.refs["faces"]] == [top]
    assert len(made.refs["to_face"]) == 1
    assert made.params["distance"].value != 5.0
    window.panel.reject()
    assert ids
