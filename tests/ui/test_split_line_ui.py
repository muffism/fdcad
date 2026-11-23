"""Split Line panel (TR60, D1414)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_intersection_method_writes_faces_and_plane(qtbot: QtBot, window: MainWindow) -> None:
    from fdcad.ui.property_panel.forms.split_line_form import start_split_line

    tab, _ids = _open(qtbot, window)
    start_split_line(window, tab)
    form = window.panel.form
    assert form is not None and type(form).__name__ == "SplitLineForm"
    form.choice_boxes["method"].setCurrentIndex(
        form.choice_boxes["method"].findData("intersection")
    )
    report = tab.session.report
    assert report is not None and report.body is not None
    names = [n for n, _f in report.body.faces]
    form.take_shapes(report.body, [report.body.face(names[0])])
    form._activate("plane")
    form.take_shapes(report.body, [report.body.face(names[1])])
    made = window.panel.current_feature()
    assert made is not None and made.params["method"] == "intersection"
    assert [r["name"] for r in made.refs["faces"]] == [names[0]]
    assert made.refs["plane"][0]["name"] == names[1]
    window.panel.reject()


def test_silhouette_method_writes_the_direction(qtbot: QtBot, window: MainWindow) -> None:
    """TR60 (D1810): Silhouette shows the pull pick, Intersection the body pick."""
    from fdcad.ui.property_panel.forms.split_line_form import start_split_line

    tab, _ids = _open(qtbot, window)
    start_split_line(window, tab)
    form = window.panel.form
    assert form is not None
    method = form.choice_boxes["method"]
    method.setCurrentIndex(method.findData("silhouette"))
    report = tab.session.report
    assert report is not None and report.body is not None
    names = [n for n, _f in report.body.faces]
    form.take_shapes(report.body, [report.body.face(names[0])])
    form._activate("direction")
    form.take_shapes(report.body, [report.body.face(names[1])])
    made = window.panel.current_feature()
    assert made is not None and made.params["method"] == "silhouette"
    assert made.refs["direction"][0]["name"] == names[1]
    assert "sketch" not in made.refs and "plane" not in made.refs
    method.setCurrentIndex(method.findData("intersection"))
    form._activate("tool_body")
    form.take_shapes(report.body, [report.body.face(names[2])])
    made = window.panel.current_feature()
    assert made is not None and made.refs["tool_body"][0]["name"] == names[2]
    window.panel.reject()
