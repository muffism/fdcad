"""TOOL_SPEC T16 item 4: the Hole Tool panel offers Up to Next and Up to Vertex."""

from pytestqt.qtbot import QtBot

from fdcad.ui.property_panel.forms.hole_form import HoleForm
from fdcad.ui.property_panel.panel import PropertyPanel
from tests.ui.test_hole_panel import _open, panel, temp_prefs  # noqa: F401


def _choose(form: HoleForm, end: str) -> None:
    box = form.choice_boxes["end_condition"]
    box.setCurrentIndex(box.findData(end))


def test_list_order(qtbot: QtBot, panel: PropertyPanel) -> None:  # noqa: F811
    _s, _ext, form = _open(qtbot, panel)
    box = form.choice_boxes["end_condition"]
    order = [box.itemData(i) for i in range(box.count())]
    assert order == ["blind", "through_all", "up_to_next", "up_to_vertex", "up_to_face"]


def test_up_to_next_needs_no_pick_and_hides_depth(qtbot: QtBot, panel: PropertyPanel) -> None:  # noqa: F811
    session, ext, form = _open(qtbot, panel)
    _choose(form, "up_to_next")
    assert not form.shown("depth") and not form.shown("up_to") and not form.shown("up_to_vertex")
    assert form.shown("bottom")
    report = session.report
    assert report is not None and report.body is not None
    form.tabs.setCurrentIndex(1)
    form.take_point(report.body, [report.body.face(f"{ext}/cap/end")], (5.0, 5.0, 10.0))
    feature = panel.current_feature()
    assert feature is not None and feature.params["end_condition"] == "up_to_next"
    assert "depth" not in feature.params and "up_to" not in feature.refs


def test_up_to_vertex_takes_a_vertex(qtbot: QtBot, panel: PropertyPanel) -> None:  # noqa: F811
    from OCP.TopAbs import TopAbs_VERTEX
    from OCP.TopExp import TopExp_Explorer

    session, ext, form = _open(qtbot, panel)
    _choose(form, "up_to_vertex")
    assert form.shown("up_to_vertex") and not form.shown("up_to") and not form.shown("depth")
    report = session.report
    assert report is not None and report.body is not None
    form.tabs.setCurrentIndex(1)
    form.take_point(report.body, [report.body.face(f"{ext}/cap/end")], (5.0, 5.0, 10.0))
    assert panel.current_feature() is None  # no vertex yet
    form.tabs.setCurrentIndex(0)
    explorer = TopExp_Explorer(report.body.shape, TopAbs_VERTEX)
    form.take_shapes(report.body, [explorer.Current()])
    feature = panel.current_feature()
    assert feature is not None
    assert feature.refs["up_to_vertex"][0]["kind"] == "vertex"
    assert "up_to" not in feature.refs
