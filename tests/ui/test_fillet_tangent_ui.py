"""Tangent Propagation tick on the Fillet and Chamfer panels (TR131, D1400)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_fillet_tick_writes_only_when_off(qtbot: QtBot, window: MainWindow) -> None:
    _open(qtbot, window)
    window.commands.actions["feature.fillet"].trigger()
    form = window.panel.form
    assert form is not None and hasattr(form, "propagate")
    assert form.propagate.isChecked()
    form.items.add({"kind": "edge", "name": "edge(a|b)"})
    made = window.panel.current_feature()
    assert made is not None and "tangent_propagation" not in made.params
    form.propagate.setChecked(False)
    made = window.panel.current_feature()
    assert made is not None and made.params["tangent_propagation"] is False
    window.panel.reject()


def test_chamfer_tick_shows_for_symmetric_distance(qtbot: QtBot, window: MainWindow) -> None:
    _open(qtbot, window)
    window.commands.actions["feature.chamfer"].trigger()
    form = window.panel.form
    assert form is not None and hasattr(form, "propagate")
    form.items.add({"kind": "edge", "name": "edge(a|b)"})
    form.propagate.setChecked(False)
    made = window.panel.current_feature()
    assert made is not None and made.params["tangent_propagation"] is False
    form.method.setCurrentIndex(form.method.findData("asymmetric"))
    assert not form.propagate.isVisibleTo(form.propagate.parentWidget())
    made = window.panel.current_feature()
    assert made is not None and "tangent_propagation" not in made.params
    window.panel.reject()


def test_fillet_method_and_profile_are_written(qtbot: QtBot, window: MainWindow) -> None:
    """TR62 (D1402): Method and Profile, with the second distance and the conic shape."""
    _open(qtbot, window)
    window.commands.actions["feature.fillet"].trigger()
    form = window.panel.form
    assert form is not None and hasattr(form, "method")
    form.items.add({"kind": "edge", "name": "edge(a|b)"})
    made = window.panel.current_feature()
    assert made is not None
    assert not {"method", "profile", "distance2", "rho"} & set(made.params)
    form.method.setCurrentIndex(form.method.findData("asymmetric"))
    form.profile.setCurrentIndex(form.profile.findData("conic"))
    assert form.fields["distance2"].isVisibleTo(form.fields["distance2"].window())
    made = window.panel.current_feature()
    assert made is not None
    assert made.params["method"] == "asymmetric" and made.params["profile"] == "conic"
    assert made.params["distance2"].value == 4.0 and made.params["rho"].value == 0.5
    window.panel.reject()


def test_variable_points_add_move_and_delete(qtbot: QtBot, window: MainWindow) -> None:
    """TR133 (D1403): positions in percent, Add Point in the widest gap, Delete Point."""
    _open(qtbot, window)
    window.commands.actions["feature.fillet"].trigger()
    form = window.panel.form
    assert form is not None and hasattr(form, "add_point")
    form.kind.setCurrentIndex(form.kind.findData("variable"))
    form.items.add({"kind": "edge", "name": "edge(a|b)"})
    form.add_point.click()
    assert form.controls.value() == 1
    assert form.fields["vp_1"].edit.text() == "50"
    form.fields["vp_1"].edit.setText("20")
    form.add_point.click()
    assert form.fields["vp_2"].edit.text() == "60"
    form.fields["vr_1_2"].edit.setText("3")
    made = window.panel.current_feature()
    assert made is not None and made.params["vp_1"].value == 20.0
    form.delete_control_point(1)
    assert form.controls.value() == 1
    assert form.fields["vp_1"].edit.text() == "60"
    assert form.fields["vr_1_1"].edit.text() == "3"
    made = window.panel.current_feature()
    assert made is not None and "vp_2" not in made.params
    window.panel.reject()


def test_limits_group_writes_keep_edges_and_plane(qtbot: QtBot, window: MainWindow) -> None:
    """TR271 (D1407): Edges to Keep and the limiting plane."""
    _open(qtbot, window)
    window.commands.actions["feature.fillet"].trigger()
    form = window.panel.form
    assert form is not None and hasattr(form, "limits")
    form.items.add({"kind": "edge", "name": "edge(a|b)"})
    made = window.panel.current_feature()
    assert made is not None and "keep_edges" not in made.refs
    form.limits.keep.add({"kind": "edge", "name": "edge(c|d)"})
    form.limits.plane.add({"kind": "face", "name": "f9/cap/end"})
    form.limits.flip.setChecked(True)
    made = window.panel.current_feature()
    assert made is not None
    assert made.refs["keep_edges"] == [{"kind": "edge", "name": "edge(c|d)"}]
    assert made.refs["limit_plane"]["name"] == "f9/cap/end"
    assert made.params["limit_flip"] is True
    window.panel.reject()


def test_rules_row_adds_rules_with_radius_and_exclusions(qtbot: QtBot, window: MainWindow) -> None:
    """TR320 (D1408): Add Rule, Own radius and exclusions."""
    from fdcad.ui import strings

    _open(qtbot, window)
    window.commands.actions["feature.fillet"].trigger()
    form = window.panel.form
    assert form is not None and hasattr(form, "rules")
    form.assistant_scope.setCurrentIndex(0)  # Whole Part
    assert form.rules.add_rule() == strings.RULE_NEEDS_FEATURE
    form.rules.kind.setCurrentIndex(form.rules.kind.findText("Edges Parallel to Z"))
    form.rules.own.setChecked(True)
    form.rules.radius.edit.setText("3")
    assert form.rules.add_rule() is None
    form.items.list.setCurrentRow(0)
    item = form.items.list.currentItem()
    data = dict(item.data(256), exclude=["edge(a|b)"])
    item.setData(256, data)
    made = window.panel.current_feature()
    assert made is not None
    (rule,) = made.refs["auto_edges"]
    assert rule["rule"] == "parallel" and rule["axis"] == "z" and rule["exclude"] == ["edge(a|b)"]
    assert made.params[rule["radius"]].value == 3.0
    window.panel.reject()


def test_face_fillet_hold_line_is_written(qtbot: QtBot, window: MainWindow) -> None:
    """TR29 (D1409): Method Hold Line with its edges."""
    from fdcad.ui import strings

    _open(qtbot, window)
    window.commands.actions["feature.fillet"].trigger()
    form = window.panel.form
    assert form is not None and hasattr(form, "face_method")
    form.kind.setCurrentIndex(form.kind.findData("face"))
    form.face_sets.lists["faces1"].add({"kind": "face", "name": "f9/cap/end"})
    form.face_sets.lists["faces2"].add({"kind": "face", "name": "f9/side/e5"})
    form.face_method.setCurrentIndex(form.face_method.findData("hold_line"))
    assert form.hold_box.isVisibleTo(form.hold_box.window())
    assert form.apply(form.feature) == strings.HOLD_NEEDED
    form.hold_lines.add({"kind": "edge", "name": "edge(a|b)"})
    made = window.panel.current_feature()
    assert made is not None and made.params["method"] == "hold_line"
    assert made.refs["hold_lines"] == [{"kind": "edge", "name": "edge(a|b)"}]
    window.panel.reject()


def test_chamfer_corner_choice_is_written(qtbot: QtBot, window: MainWindow) -> None:
    """TR321 (D1812): Corners Mitre is written; Patch is the default and not written."""
    _open(qtbot, window)
    window.commands.actions["feature.chamfer"].trigger()
    form = window.panel.form
    assert form is not None and hasattr(form, "corner")
    form.items.add({"kind": "edge", "name": "edge(a|b)"})
    made = window.panel.current_feature()
    assert made is not None and "corner" not in made.params
    form.corner.setCurrentIndex(form.corner.findData("mitre"))
    made = window.panel.current_feature()
    assert made is not None and made.params["corner"] == "mitre"
    form.corner.setCurrentIndex(form.corner.findData("blend"))  # TR321 (D2304)
    made = window.panel.current_feature()
    assert made is not None and made.params["corner"] == "blend"
    window.panel.reject()
