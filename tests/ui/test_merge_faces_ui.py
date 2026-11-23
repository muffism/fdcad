"""Merge Faces and the touching tolerance in the window (TR261, D787)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.body_tools import flow
from fdcad.ui.body_tools.forms import FORMS
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_command_icon_and_forms() -> None:
    from fdcad.ui.icons.audit import audit

    assert BY_ID["feature.merge_faces"].label == "Merge Faces"
    assert BY_ID["feature.merge_faces"].keys == () and audit("feature.merge_faces") == []
    names = {f.name for f in FORMS["merge_faces"].fields()}
    assert {"faces", "tolerance", "angle_tolerance"} <= names
    assert "tolerance" in {f.name for f in FORMS["combine"].fields()}
    assert "tolerance" in {f.name for f in FORMS["split"].fields()}


def test_merge_faces_starts_with_the_picked_faces(qtbot: QtBot, window: MainWindow) -> None:
    tab, ids = _open(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None
    top = report.body.face(f"{ids['plate']}/cap/end")
    window._selection_changed(tab, [top])
    assert flow.start(window, "feature.merge_faces")
    panel = window.panel
    assert panel is not None and panel.feature is not None
    assert panel.feature.type == "merge_faces" and panel.feature.name == "Merge Faces 1"
    edited = panel.current_feature()
    assert edited is not None and len(edited.refs["faces"]) == 1
    assert edited.params["tolerance"].value == 0.001
    panel.reject()


def test_move_face_rules_in_the_panel(qtbot: QtBot, window: MainWindow) -> None:
    """TR263 (D788)."""
    tab, ids = _open(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None
    top = report.body.face(f"{ids['plate']}/cap/end")
    window._selection_changed(tab, [top])
    assert flow.start(window, "feature.move_face")
    panel = window.panel
    assert panel is not None
    widgets = panel.body_form.widgets
    widgets["rule_coplanar"].setChecked(True)
    edited = panel.current_feature()
    assert edited is not None and edited.params["rule_coplanar"] is True
    widgets["suspend_rules"].setChecked(True)
    assert "rule_coplanar" not in {f.name for f in panel.body_form.shown_fields()}
    panel.reject()


def test_move_face_resize_and_measured_size_fields(qtbot: QtBot, window: MainWindow) -> None:
    """TR265 (D789)."""
    tab, ids = _open(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None
    top = report.body.face(f"{ids['plate']}/cap/end")
    window._selection_changed(tab, [top])
    assert flow.start(window, "feature.offset_face")
    panel = window.panel
    assert panel is not None
    form = panel.body_form

    def shown() -> set[str]:
        return {f.name for f in form.shown_fields()}

    assert "distance" in shown() and "set_size" not in shown()
    by = form.widgets["offset_by"]
    by.setCurrentIndex(by.findData("measured"))
    assert {"size_from", "set_size"} <= shown() and "distance" not in shown()
    mode = form.widgets["mode"]
    mode.setCurrentIndex(mode.findData("resize"))
    assert "diameter" in shown() and "set_size" not in shown()
    edited = panel.current_feature()
    assert edited is not None and edited.params["mode"] == "resize"
    assert "set_size" not in edited.params
    panel.reject()
