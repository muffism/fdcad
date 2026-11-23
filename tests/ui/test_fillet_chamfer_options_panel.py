"""Panels for the round 9t fillet and chamfer options: face and full round fillets, the
fillet assistant (D518, D519) and offset face and face to face chamfers (D520)."""

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.features.base import Fix
from fdcad.core.features.modify import edges_of
from fdcad.core.naming.names import NamedShape
from fdcad.ui.main_window.new_feature import phase2_feature
from fdcad.ui.property_panel.forms.base import REMEMBERED
from fdcad.ui.property_panel.forms.chamfer_form import ChamferForm
from fdcad.ui.property_panel.forms.fillet_form import FilletForm
from fdcad.ui.property_panel.panel import PropertyPanel
from fdcad.ui.session import DocumentSession
from tests.core.features.test_fillet_faces import rib_part
from tests.ui.test_property_panel import _session


@pytest.fixture
def panel(qtbot: QtBot) -> PropertyPanel:
    REMEMBERED.clear()
    widget = PropertyPanel()
    qtbot.addWidget(widget)
    return widget


def _open(qtbot: QtBot, panel: PropertyPanel, ftype: str) -> tuple[DocumentSession, str, str]:
    doc, ext, rib = rib_part()
    session = _session(qtbot, doc)
    panel.begin(session, phase2_feature(doc, ftype, "boss"), is_new=True)
    return session, ext, rib


def _body(session: DocumentSession) -> NamedShape:
    report = session.report
    assert report is not None and report.body is not None
    return report.body


def _face(b: NamedShape, name: str):  # type: ignore[no-untyped-def]
    face = b.face(name)
    assert face is not None, name
    return face


# Fillet ------------------------------------------------------------------------------


def test_full_round_shows_three_sets_and_hides_the_radius(
    qtbot: QtBot, panel: PropertyPanel
) -> None:
    session, _ext, rib = _open(qtbot, panel, "fillet")
    form = panel.form
    assert isinstance(form, FilletForm)
    assert panel.groups["face_sets"].isHidden()
    form.kind.setCurrentIndex(form.kind.findData("full_round"))
    assert not panel.groups["face_sets"].isHidden()
    assert panel.groups["items"].isHidden()
    assert panel.groups["parameters"].isHidden()
    assert not form.face_sets.lists["centre"].isHidden()
    assert form.face_sets.labels["faces1"].text() == "Side Face Set 1"
    b = _body(session)
    assert panel.current_feature() is None  # nothing picked yet
    # One click per set: the target moves on after each pick.
    for name in (f"{rib}/side/e8", f"{rib}/cap/end", f"{rib}/side/e6"):
        assert form.take_shapes(b, [_face(b, name)]) is None
    result = panel.current_feature()
    assert result is not None
    assert result.params["fillet_type"] == "full_round"
    assert result.refs["faces1"][0]["name"] == f"{rib}/side/e8"
    assert result.refs["centre"][0]["name"] == f"{rib}/cap/end"
    assert result.refs["faces2"][0]["name"] == f"{rib}/side/e6"
    assert "edges" not in result.refs and "radius_1" not in result.params


def test_face_fillet_two_sets_and_radius(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, ext, rib = _open(qtbot, panel, "fillet")
    form = panel.form
    assert isinstance(form, FilletForm)
    form.kind.setCurrentIndex(form.kind.findData("face"))
    assert form.face_sets.lists["centre"].isHidden()
    assert not panel.groups["parameters"].isHidden()
    assert form.multiple.isHidden()
    b = _body(session)
    form.take_shapes(b, [_face(b, f"{rib}/side/e6")])
    assert panel.current_feature() is None  # set 2 is still empty
    form.take_shapes(b, [_face(b, f"{ext}/cap/end#2")])
    form.fields["radius"].edit.setText("1.5")
    result = panel.current_feature()
    assert result is not None
    assert result.params["fillet_type"] == "face"
    assert result.params["radius"] == Param("1.5", 1.5)
    assert "centre" not in result.refs
    assert set(result.refs) >= {"faces1", "faces2"}
    # Back to constant: the face sets are not written.
    form.kind.setCurrentIndex(form.kind.findData("constant"))
    form.take_shapes(b, edges_of(_face(b, f"{rib}/cap/end"))[:1])
    again = panel.current_feature()
    assert again is not None
    assert "faces1" not in again.refs and "edges" in again.refs


def test_assistant_buttons_add_convexity_items(qtbot: QtBot, panel: PropertyPanel) -> None:
    _s, _ext, rib = _open(qtbot, panel, "fillet")
    form = panel.form
    assert isinstance(form, FilletForm)
    # The assistant sits in the Add Edges group, on the More tab (D2790).
    concave = form.add_group.findChild(object, "assistant_concave")
    convex = form.add_group.findChild(object, "assistant_convex")
    assert concave is not None and convex is not None
    concave.click()
    concave.click()  # no repeat
    form.assistant_scope.setCurrentIndex(form.assistant_scope.findData(rib))
    convex.click()
    assert [form.items.list.item(i).text() for i in range(form.items.list.count())] == [
        "Concave edges of the part",
        f"Convex edges of {panel.session.document.feature(rib).name}",  # type: ignore[union-attr]
    ]
    result = panel.current_feature()
    assert result is not None
    assert result.refs["auto_edges"] == [
        {"convexity": "concave"},
        {"convexity": "convex", "feature": rib},
    ]
    assert "edges" not in result.refs


def test_partial_edges_group(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, _ext, rib = _open(qtbot, panel, "fillet")
    form = panel.form
    assert isinstance(form, FilletForm)
    group = panel.groups["partial"]
    assert not group.isHidden()
    b = _body(session)
    form.take_shapes(b, edges_of(_face(b, f"{rib}/cap/end"))[:1])
    plain = panel.current_feature()
    assert plain is not None
    assert not {"partial", "start_distance", "start_percent"} & set(plain.params)
    group.set_checked(True)
    assert not form.fields["start_distance"].parentWidget().isHidden()
    assert form.fields["start_percent"].parentWidget().isHidden()
    form.partial_kind.setCurrentIndex(form.partial_kind.findData("percent"))
    assert form.fields["start_distance"].parentWidget().isHidden()
    form.fields["end_percent"].edit.setText("60")
    form.partial_flip.setChecked(True)
    result = panel.current_feature()
    assert result is not None
    assert result.params["partial"] == "percent"
    assert result.params["start_percent"] == Param("25", 25.0)
    assert result.params["end_percent"] == Param("60", 60.0)
    assert result.params["partial_flip"] is True
    assert "start_distance" not in result.params
    # Only Constant Size has partial edges.
    form.kind.setCurrentIndex(form.kind.findData("variable"))
    assert group.isHidden()
    variable = panel.current_feature()
    assert variable is not None and "partial" not in variable.params


# Chamfer -----------------------------------------------------------------------------


def test_offset_face_uses_the_method_and_flip(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, ext, _rib = _open(qtbot, panel, "chamfer")
    form = panel.form
    assert isinstance(form, ChamferForm)
    form.kind.setCurrentIndex(form.kind.findData("offset_face"))
    assert not form.method.isHidden() and not form.flip.isHidden()
    assert panel.groups["face_sets"].isHidden()
    b = _body(session)
    form.take_shapes(b, edges_of(_face(b, f"{ext}/cap/start"))[:1])
    form.method.setCurrentIndex(form.method.findData("asymmetric"))
    assert not form.fields["distance2"].parentWidget().isHidden()
    form.fields["distance2"].edit.setText("2")
    result = panel.current_feature()
    assert result is not None
    assert result.params["chamfer_type"] == "offset_face"
    assert result.params["method"] == "asymmetric"
    assert result.params["distance2"] == Param("2", 2.0)
    # Width is only for face to face.
    form.method.setCurrentIndex(form.method.findData("width"))
    form._update()
    assert form.method.currentData() == "symmetric"


def test_face_to_face_sets_and_width(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, ext, _rib = _open(qtbot, panel, "chamfer")
    form = panel.form
    assert isinstance(form, ChamferForm)
    form.kind.setCurrentIndex(form.kind.findData("face_face"))
    assert not panel.groups["face_sets"].isHidden()
    assert panel.groups["items"].isHidden()
    assert form.flip.isHidden()
    assert form.fields["width"].parentWidget().isHidden()
    form.method.setCurrentIndex(form.method.findData("width"))
    assert not form.fields["width"].parentWidget().isHidden()
    assert form.fields["distance"].parentWidget().isHidden()
    b = _body(session)
    form.take_shapes(b, [_face(b, f"{ext}/cap/start")])
    form.take_shapes(b, [_face(b, f"{ext}/side/e6")])
    form.fields["width"].edit.setText("1.5")
    result = panel.current_feature()
    assert result is not None
    assert result.params["chamfer_type"] == "face_face"
    assert result.params["method"] == "width"
    assert result.params["width"] == Param("1.5", 1.5)
    assert result.refs["faces1"][0]["name"] == f"{ext}/cap/start"
    assert result.refs["faces2"][0]["name"] == f"{ext}/side/e6"
    assert "edges" not in result.refs and "flip" not in result.params
    form.apply_fix(Fix("Reduce the width to 1 mm", "set_param", {"param": "width", "value": 1.0}))
    assert form.fields["width"].edit.text() == "1"


def test_face_to_face_needs_both_sets(qtbot: QtBot, panel: PropertyPanel) -> None:
    session, ext, _rib = _open(qtbot, panel, "chamfer")
    form = panel.form
    assert isinstance(form, ChamferForm)
    form.kind.setCurrentIndex(form.kind.findData("face_face"))
    b = _body(session)
    form.take_shapes(b, [_face(b, f"{ext}/cap/start")])
    assert panel.current_feature() is None
    assert "Face Set 2" in panel.message.text()
