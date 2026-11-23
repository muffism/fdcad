"""Feature values typed in the 3D view (TOOL_SPEC T15.2 to T15.4, T15.8, T15.9)."""

from __future__ import annotations

from typing import Any

import pytest
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot

import fdcad.ui.sheet_metal.forms  # noqa: F401  (registers the sheet metal panels)
from fdcad.core.document.model import Feature
from fdcad.core.features.preview import PreviewGeometry
from fdcad.core.naming.select import reference_for
from fdcad.ui.body_tools.flow import new_feature
from fdcad.ui.body_tools.forms import FORMS as BODY_FORMS
from fdcad.ui.main_window.new_feature import phase2_feature
from fdcad.ui.property_panel.forms import FORMS as PANEL_FORMS
from fdcad.ui.property_panel.panel import PropertyPanel
from fdcad.ui.session import DocumentSession
from fdcad.ui.viewport.handles import boxes_overlap, label_box, spread_labels
from fdcad.ui.viewport.preview import FeaturePreview, PreviewData
from fdcad.ui.viewport.value_labels import (
    feature_labels,
    label_text,
    starts_typing,
    value_fields,
)
from tests.core.features.test_features import plate
from tests.core.features.test_fillet import top_edges
from tests.ui.test_property_panel import _session

#: Left out: the helix panel waits for a sketch, the import panels ask for a file.
_SKIPPED = {"helix", "import_mesh", "import_step"}
#: Feature types T15.2 names, each must have at least one label.
_NAMED = (
    "fillet",
    "chamfer",
    "shell",
    "draft",
    "move_face",  # offset face is a Move Face mode
    "hole",
    "rib",
    "dome",
    "wrap",
    "mounting_boss",
    "vent",
    "lip_groove",
    "snap_hook",
    "base_flange",
    "sketched_bend",
)
_TYPES = sorted((set(PANEL_FORMS) | set(BODY_FORMS)) - _SKIPPED)


class LabelView(QWidget):
    """A plain widget with the 3D view's label API (the real view needs a GPU)."""

    handle_dragged = Signal(str, float)
    handle_flipped = Signal(str)
    value_clicked = Signal(str, QPoint)
    value_typed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.labels: list[Any] = []
        self.shown: list[PreviewData] = []

    def show_preview(self, data: PreviewData, _active: str, _label: object) -> None:
        self.shown.append(data)

    def clear_preview(self) -> None:
        self.labels = []

    def show_value_labels(self, labels: list[Any]) -> None:
        self.labels = list(labels)

    def value_label_pos(self, param: str) -> QPoint | None:
        names = [label.param for label in self.labels]
        return QPoint(10, 20 + 30 * names.index(param)) if param in names else None


def _new(doc: Any, ftype: str) -> Feature:
    if ftype in BODY_FORMS:
        return new_feature(doc, ftype, {})
    return Feature(doc.new_feature_id(), ftype, ftype, params={}, refs={})


@pytest.mark.parametrize("ftype", _TYPES)
def test_every_value_of_every_panel_gets_a_label(qtbot: QtBot, ftype: str) -> None:
    doc, _ext = plate()
    session = _session(qtbot, doc)
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    panel.begin(session, _new(doc, ftype), is_new=True)
    fields = value_fields(panel)
    if ftype in _NAMED:
        assert fields, f"{ftype} shows no value to type"
    geometry = PreviewGeometry(None, anchor=(1.0, 2.0, 3.0))
    labels = feature_labels(panel, geometry)
    assert [label.param for label in labels] == list(fields)
    for label in labels:
        assert label.point == (1.0, 2.0, 3.0)
        assert label.text == label_text(fields[label.param])
    panel.reject()


def test_handle_values_keep_their_place_on_the_handle(qtbot: QtBot) -> None:
    doc, ext = plate()
    session = _session(qtbot, doc)
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    panel.begin(session, doc.feature(ext), is_new=False)
    from fdcad.core.features.base import PreviewHandle

    handle = PreviewHandle("depth", (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), 10.0)
    geometry = PreviewGeometry(None, [handle], anchor=(0.0, 0.0, 0.0))
    assert "depth" in value_fields(panel)
    assert [label.param for label in feature_labels(panel, geometry)] == []


def _fillet(qtbot: QtBot) -> tuple[PropertyPanel, FeaturePreview, LabelView]:
    doc, ext = plate()
    session: DocumentSession = _session(qtbot, doc)
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    view = LabelView()
    qtbot.addWidget(view)
    view.show()
    preview = FeaturePreview()
    preview.bind(panel, lambda: view)
    report = session.report
    assert report is not None and report.body is not None
    edge = top_edges(report.body, ext)[0]
    feature = phase2_feature(doc, "fillet", "boss")
    feature.refs["edges"] = [reference_for(report.body, edge)]
    with qtbot.waitSignal(preview.ready, timeout=20000):
        panel.begin(session, feature, is_new=True)
    return panel, preview, view


def test_fillet_label_appears_and_a_typed_value_reaches_panel_and_preview(qtbot: QtBot) -> None:
    panel, preview, view = _fillet(qtbot)
    assert [label.param for label in view.labels] == ["radius"]
    assert view.labels[0].text == "2.00 mm"
    view.value_clicked.emit("radius", QPoint(10, 20))
    editor = preview.editor()
    assert editor.box is not None and editor.box.text() == "2"
    editor.box.edit.setText("3")
    with qtbot.waitSignal(preview.ready, timeout=20000):
        qtbot.keyClick(editor.box.edit, Qt.Key.Key_Return)
    assert editor.box is None
    assert panel.form is not None
    assert panel.form.fields["radius"].edit.text() == "3"
    assert view.labels[0].text == "3.00 mm"
    feature = panel.current_feature()
    assert feature is not None and feature.params["radius"].value == pytest.approx(3.0)


def test_panel_changes_update_the_label_at_once(qtbot: QtBot) -> None:
    panel, _preview, view = _fillet(qtbot)
    assert panel.form is not None
    panel.form.fields["radius"].edit.setText("4")
    assert view.labels[0].text == "4.00 mm"


def test_typing_a_digit_opens_the_box_with_it(qtbot: QtBot) -> None:
    panel, preview, view = _fillet(qtbot)
    view.value_typed.emit("5")
    editor = preview.editor()
    assert editor.box is not None and editor.param == "radius"
    assert editor.box.text() == "5"
    assert not editor.box.edit.hasSelectedText()  # the next digit adds to it
    qtbot.keyClicks(editor.box.edit, ".5")
    qtbot.keyClick(editor.box.edit, Qt.Key.Key_Return)
    assert panel.form is not None and panel.form.fields["radius"].edit.text() == "5.5"


def test_escape_restores_the_value(qtbot: QtBot) -> None:
    panel, preview, view = _fillet(qtbot)
    assert panel.form is not None
    field = panel.form.fields["radius"]
    view.value_clicked.emit("radius", QPoint(10, 20))
    editor = preview.editor()
    assert editor.box is not None
    editor.box.edit.setText("6")
    qtbot.mouseClick(editor.box.rebuild, Qt.MouseButton.LeftButton)  # applied, box open
    assert field.edit.text() == "6"
    qtbot.keyClick(editor.box, Qt.Key.Key_Escape)
    assert editor.box is None
    assert field.edit.text() == "2"


def _hole(qtbot: QtBot) -> tuple[PropertyPanel, FeaturePreview, LabelView]:
    doc, _ext = plate()
    session = _session(qtbot, doc)
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    view = LabelView()
    qtbot.addWidget(view)
    view.show()
    preview = FeaturePreview()
    preview.bind(panel, lambda: view)
    panel.begin(session, phase2_feature(doc, "hole", "boss"), is_new=True)
    return panel, preview, view


def test_tab_and_shift_tab_move_between_the_labels(qtbot: QtBot) -> None:
    panel, preview, view = _hole(qtbot)
    order = preview.value_order()
    assert order[:2] == ["diameter", "depth"]
    view.value_clicked.emit("diameter", QPoint(5, 5))
    editor = preview.editor()
    assert editor.box is not None
    editor.box.edit.setText("7")
    qtbot.keyClick(editor.box.edit, Qt.Key.Key_Tab)
    assert editor.param == "depth"
    assert panel.active_param == "depth"
    assert panel.form is not None and panel.form.fields["diameter"].edit.text() == "7"
    qtbot.keyClick(editor.box.edit, Qt.Key.Key_Backtab)
    assert editor.param == "diameter"
    qtbot.keyClick(editor.box.edit, Qt.Key.Key_Backtab)
    assert editor.param == order[-1]  # round to the last one
    qtbot.keyClick(editor.box, Qt.Key.Key_Escape)
    assert panel.form.fields["diameter"].edit.text() == "5.5"  # Escape puts back the Tab change


def test_a_wrong_value_does_not_move_on(qtbot: QtBot) -> None:
    _panel, preview, view = _hole(qtbot)
    view.value_clicked.emit("diameter", QPoint(5, 5))
    editor = preview.editor()
    assert editor.box is not None
    editor.box.edit.setText("=nonsense +")
    qtbot.keyClick(editor.box.edit, Qt.Key.Key_Tab)
    assert editor.param == "diameter"
    assert editor.box.edit.property("error") is True


def test_typing_opens_the_label_last_used(qtbot: QtBot) -> None:
    _panel, preview, view = _hole(qtbot)
    view.value_clicked.emit("depth", QPoint(5, 5))
    editor = preview.editor()
    assert editor.box is not None
    qtbot.keyClick(editor.box, Qt.Key.Key_Escape)
    view.value_typed.emit("=")
    assert editor.param == "depth" and editor.box is not None
    assert editor.box.text() == "="


def test_closing_the_panel_stops_typing(qtbot: QtBot) -> None:
    panel, preview, view = _hole(qtbot)
    panel.reject()
    view.value_typed.emit("3")
    assert preview._editor is None or preview._editor.box is None


def test_only_digits_minus_dot_and_equals_start_typing() -> None:
    none = Qt.KeyboardModifier.NoModifier
    for ch in "0123456789-.=":
        assert starts_typing(ch, none)
    assert not starts_typing("a", none)
    assert not starts_typing("", none)
    assert not starts_typing("1", Qt.KeyboardModifier.ControlModifier)
    assert not starts_typing("1", Qt.KeyboardModifier.AltModifier)
    assert starts_typing("1", Qt.KeyboardModifier.KeypadModifier)


def test_labels_move_down_until_clear() -> None:
    boxes = [label_box((100.0, 100.0), "2.00 mm", 14.0) for _ in range(3)]
    taken = [label_box((100.0, 100.0), "10.00 mm", 14.0)]
    shifts = spread_labels(boxes, taken)
    assert shifts[0] > 0 and shifts[1] > shifts[0] and shifts[2] > shifts[1]
    placed = [(b[0], b[1] + d, b[2], b[3] + d) for b, d in zip(boxes, shifts, strict=True)]
    for i, a in enumerate(placed):
        assert not boxes_overlap(a, taken[0])
        assert all(not boxes_overlap(a, b) for b in placed[i + 1 :])
    far = label_box((400.0, 400.0), "1", 14.0)
    assert spread_labels([far], taken) == [0.0]
