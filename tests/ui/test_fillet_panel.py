"""Fillet panel (PHASE2_SPEC P2.4): picks, radii, variable rows, preview modes, the pre
check box with its fix buttons, the command and the tree icon."""

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.features.base import Fix
from fdcad.core.features.modify import edges_of
from fdcad.core.features.preview import PreviewGeometry
from fdcad.ui.main_window.new_feature import phase2_feature
from fdcad.ui.property_panel.forms.base import REMEMBERED
from fdcad.ui.property_panel.forms.fillet_form import FilletForm
from fdcad.ui.property_panel.panel import PropertyPanel
from fdcad.ui.session import DocumentSession
from tests.core.features.test_features import plate
from tests.ui.test_property_panel import _session


@pytest.fixture
def panel(qtbot: QtBot) -> PropertyPanel:
    widget = PropertyPanel()
    qtbot.addWidget(widget)
    return widget


def _open(qtbot: QtBot, panel: PropertyPanel) -> tuple[DocumentSession, str]:
    REMEMBERED.clear()
    doc, ext = plate()
    session = _session(qtbot, doc)
    feature = phase2_feature(doc, "fillet", "boss")
    panel.begin(session, feature, is_new=True)
    return session, ext


def _top_edges(session: DocumentSession, ext: str) -> list:
    report = session.report
    assert report is not None and report.body is not None
    face = report.body.face(f"{ext}/cap/end")
    assert face is not None
    return edges_of(face)


def test_new_fillet_opens_with_its_groups(qtbot: QtBot, panel: PropertyPanel) -> None:
    _open(qtbot, panel)
    assert isinstance(panel.form, FilletForm)
    assert panel.title.text() == "Fillet 1"
    assert {"fillet_type", "items", "parameters", "variable"} <= set(panel.groups)
    assert panel.groups["variable"].isHidden()
    assert panel.current_feature() is None  # nothing picked yet
    assert "Pick edges" in panel.message.text()


def test_picked_edges_are_written_as_references(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, ext = _open(qtbot, panel)
    report = session.report
    assert report is not None and report.body is not None
    edges = _top_edges(session, ext)
    assert panel.form.take_shapes(report.body, edges[:2]) is None
    assert panel.form.take_shapes(report.body, edges[:1]) is None  # no repeats
    result = panel.current_feature()
    assert result is not None
    assert len(result.refs["edges"]) == 2
    assert result.params["radius"] == Param("2", 2.0)
    assert result.params["fillet_type"] == "constant"


def test_faces_and_features_are_items_too(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, ext = _open(qtbot, panel)
    report = session.report
    assert report is not None and report.body is not None
    top = report.body.face(f"{ext}/cap/end")
    panel.form.take_shapes(report.body, [top])
    panel.form.items.add({"feature": ext})
    result = panel.current_feature()
    assert result is not None
    assert result.refs["faces"][0]["name"] == f"{ext}/cap/end"
    assert result.refs["features"] == [{"feature": ext}]
    assert "edges" not in result.refs


def test_multiple_radius_adds_a_field_per_edge(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, ext = _open(qtbot, panel)
    report = session.report
    assert report is not None and report.body is not None
    panel.form.take_shapes(report.body, _top_edges(session, ext)[:2])
    panel.form.multiple.setChecked(True)
    assert {"radius_1", "radius_2"} <= set(panel.form.fields)
    panel.form.fields["radius_2"].edit.setText("3")
    result = panel.current_feature()
    assert result is not None
    assert result.params["multiple_radius"] is True
    assert result.params["radius_2"] == Param("3", 3.0)


def test_variable_rows_set_all_and_control_points(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, ext = _open(qtbot, panel)
    report = session.report
    assert report is not None and report.body is not None
    panel.form.take_shapes(report.body, _top_edges(session, ext)[:1])
    form = panel.form
    form.kind.setCurrentIndex(form.kind.findData("variable"))
    assert not panel.groups["variable"].isHidden()
    form.controls.setValue(2)
    assert {"vr_1_start", "vr_1_1", "vr_1_2", "vr_1_end"} <= set(form.fields)
    form.fields["radius"].edit.setText("1.5")
    form.set_all()
    form.transition.setCurrentIndex(form.transition.findData("straight"))
    result = panel.current_feature()
    assert result is not None
    assert result.params["fillet_type"] == "variable"
    assert result.params["control_points"] == 2
    assert result.params["transition"] == "straight"
    assert result.params["vr_1_end"] == Param("1.5", 1.5)


def test_preview_modes(qtbot: QtBot, panel: PropertyPanel) -> None:
    """Full previews the result, Partial only its outline, None nothing (D585)."""
    from fdcad.core.features.preview import build_preview
    from fdcad.ui.viewport.preview import outline_only

    session, ext = _open(qtbot, panel)
    report = session.report
    assert report is not None and report.body is not None
    panel.form.take_shapes(report.body, _top_edges(session, ext)[:3])
    feature = panel.current_feature()
    assert feature is not None
    form = panel.form
    form.mode.setCurrentIndex(form.mode.findData("none"))
    assert form.for_preview(feature) is None
    form.mode.setCurrentIndex(form.mode.findData("partial"))
    outline = form.for_preview(feature)
    assert outline is not None and len(outline.refs["edges"]) == 3  # every item
    assert outline.data["preview_outline"] is True
    assert "preview_outline" not in feature.data  # the edited feature is untouched
    geometry = build_preview(session.document, outline, report.results)
    assert geometry.replaces_part and len(geometry.accent) == 3
    outline_only(geometry)
    assert geometry.outline and not geometry.replaces_part and geometry.shape is not None
    form.mode.setCurrentIndex(form.mode.findData("full"))
    full = form.for_preview(feature)
    assert full is not None and "preview_outline" not in full.data


def test_pre_check_shows_failed_edges_and_fix_buttons(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, ext = _open(qtbot, panel)
    report = session.report
    assert report is not None and report.body is not None
    edges = _top_edges(session, ext)
    panel.form.take_shapes(report.body, edges[:2])
    names = panel.form.items.names()
    fixes = [
        Fix(
            "Fillet the rest (skip 1 edge)", "skip_items", {"items": [names[0]], "keys": ["edges"]}
        ),
        Fix("Reduce the radius to 4.5 mm", "set_param", {"param": "radius", "value": 4.5}),
    ]
    panel.preview_checked(
        PreviewGeometry(
            None, error="Fillet 1 failed on 1 of 2 edges", failed=[names[0]], fixes=fixes
        )
    )
    check = panel.form.check
    assert not check.isHidden()
    assert check.buttons.count() == 2
    check.buttons.itemAt(1).widget().click()
    assert panel.form.fields["radius"].edit.text() == "4.5"
    check.buttons.itemAt(0).widget().click()
    assert panel.form.items.names() == [names[1]]
    panel.preview_checked(PreviewGeometry(None))
    assert check.isHidden()


def test_settings_are_remembered_for_the_next_fillet(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, ext = _open(qtbot, panel)
    report = session.report
    assert report is not None and report.body is not None
    panel.form.take_shapes(report.body, _top_edges(session, ext)[:1])
    panel.form.fields["radius"].edit.setText("1.25")
    panel.accept()
    assert REMEMBERED["fillet"]["radius"] == Param("1.25", 1.25)
    again = phase2_feature(session.document, "fillet", "boss")
    assert again.params["radius"] == Param("1.25", 1.25)
    assert again.name == "Fillet 2"
    REMEMBERED.clear()


def test_fillet_command_and_tree_icon_exist() -> None:
    from fdcad.core.document.model import Feature
    from fdcad.ui.command_tabs.tabs import FEATURE_GROUPS
    from fdcad.ui.input.commands import BY_ID
    from fdcad.ui.tree.row_icons import icon_name

    assert BY_ID["feature.fillet"].keys == ("Shift+F",)
    flat = str(FEATURE_GROUPS)
    assert "feature.fillet" in flat
    assert icon_name(Feature("f9", "fillet", "Fillet 1")) == "feature.fillet"


def test_check_box_wraps_long_text_and_keeps_panel_width(qtbot: QtBot) -> None:
    from fdcad.ui.property_panel.forms.base import CheckBox

    box = CheckBox()
    qtbot.addWidget(box)
    box.resize(240, 300)
    box.show_result(
        "Fillet 1 failed: edge(f6/cap/end|f8/side/e13) (largest radius 0.0234 mm).",
        [("Fillet the rest and skip four edges that are too short", lambda: None)],
    )
    box.show()
    assert "​" in box.label.text()
    button = box.buttons.itemAt(0).widget()
    assert box.minimumSizeHint().width() < 240
    assert button.toolTip().startswith("Fillet the rest and skip four")
    assert button.fontMetrics().horizontalAdvance(button.text()) <= button.width()
