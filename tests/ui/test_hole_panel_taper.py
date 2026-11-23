"""Hole Tool panel: Taper and Depth Includes Point (TR144 item 3, D1505)."""

from pytestqt.qtbot import QtBot

from fdcad.ui.property_panel.panel import PropertyPanel
from tests.ui.test_hole_panel import _open, panel, temp_prefs  # noqa: F401


def test_taper_and_point_in_depth_are_written(qtbot: QtBot, panel: PropertyPanel) -> None:  # noqa: F811
    session, ext, form = _open(qtbot, panel)
    assert form.shown("taper") and not form.shown("taper_angle")
    form.checks["taper"].setChecked(True)
    assert form.shown("taper_angle")
    assert not form.shown("point_in_depth")
    bottom = form.choice_boxes["bottom"]
    bottom.setCurrentIndex(bottom.findData("drill_point"))
    assert form.shown("point_in_depth")
    form.checks["point_in_depth"].setChecked(True)
    report = session.report
    assert report is not None and report.body is not None
    form.tabs.setCurrentIndex(1)
    form.take_point(report.body, [report.body.face(f"{ext}/cap/end")], (5.0, 5.0, 10.0))
    feature = panel.current_feature()
    assert feature is not None
    assert feature.params["taper"] is True and "taper_angle" in feature.params
    assert feature.params["point_in_depth"] is True


def test_pipe_tapped_lists_pipe_sizes(qtbot: QtBot, panel: PropertyPanel) -> None:  # noqa: F811
    """TR145 (D1511)."""
    _session, _ext, form = _open(qtbot, panel)
    box = form.choice_boxes["hole_type"]
    box.setCurrentIndex(box.findData("pipe_tapped"))
    standard = form.choice_boxes["standard"]
    standard.setCurrentIndex(standard.findData("ansi"))
    sizes = form.choice_boxes["size"]
    assert sizes.findData("1/2 NPT") >= 0
    sizes.setCurrentIndex(sizes.findData("1/2 NPT"))
    assert form.shown("thread_depth") and not form.shown("modeled_thread")
    assert float(form.fields["pitch"].edit.text()) > 0


def test_counterdrill_shows_the_head_and_its_angle(qtbot: QtBot, panel: PropertyPanel) -> None:  # noqa: F811
    """TR144 item 2 (D1506)."""
    session, ext, form = _open(qtbot, panel)
    box = form.choice_boxes["hole_type"]
    box.setCurrentIndex(box.findData("counterdrill"))
    assert form.shown("cbore_diameter") and form.shown("cdrill_angle")
    assert form.fields["cbore_diameter"].edit.text() != ""
    report = session.report
    assert report is not None and report.body is not None
    form.tabs.setCurrentIndex(1)
    form.take_point(report.body, [report.body.face(f"{ext}/cap/end")], (5.0, 5.0, 10.0))
    feature = panel.current_feature()
    assert feature is not None and feature.params["hole_type"] == "counterdrill"
    assert "cdrill_angle" in feature.params and "cbore_depth" in feature.params
