"""Checks for the last open points of the UI review of 2026-11-19 (D2840 to D2844).

P11, the pressed fill, is checked in ``test_theme_contrast.py``, beside the pairs it
measures. The sweep of ``test_panel_widths.py`` looks for bare field names and empty
rows in every panel. The tests here pin the cases that were seen: Split's label,
the notes of the Hole Tool, Draft and Shell, and the two sets of fields of Fillet's
Variable Radii, and its rows of radii for every edge.
"""

from __future__ import annotations

from typing import Any

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication, QFormLayout, QLabel, QVBoxLayout, QWidget
from pytestqt.qtbot import QtBot

from fdcad.core.features.modify import edges_of
from fdcad.ui import strings_phase3 as text
from fdcad.ui.body_tools import flow
from fdcad.ui.body_tools.forms import FORMS
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.property_panel.groups import Group, Note, show_if_filled
from tests.ui.panel_checks import blank_rows, is_raw, raw_labels
from tests.ui.test_main_window import _open_plate
from tests.ui.test_ui_polish_controls import styled  # noqa: F401  (fixture)
from tests.ui.test_workflow import _folders, window  # noqa: F401  (fixtures)

# D2841: labels, not field names ---------------------------------------------------------


def test_the_check_knows_a_field_name_from_a_label() -> None:
    for name in ("keep", "angle2", "rotate_by", "exclude", "pin"):
        assert is_raw(name), name
    for label in ("Keep", "Trim tools", "Angle", "X", "mm", "Cut", "Body 1", "2", "", "(none)"):
        assert not is_raw(label), label


def test_every_field_of_every_form_has_a_label_and_every_choice_a_name() -> None:
    """A field with no entry in ``LABELS`` showed its own name: "keep" in Split, "exclude"
    in Intersect, "angle2" in Circular Pattern, "form" in Hinge. A choice with no entry
    in ``CHOICES`` did the same: "pin" in Hinge, "axis" in Move Face."""
    import fdcad.ui.sheet_metal.forms  # noqa: F401  (adds its forms and their text)

    missing: list[str] = []
    for ftype, form in FORMS.items():
        for spec in form.fields():
            if spec.name not in text.LABELS:
                missing.append(f"{ftype}: label of {spec.name}")
            missing += [
                f"{ftype}: choice {choice} of {spec.name}"
                for choice in spec.choices
                if choice not in text.CHOICES
            ]
    assert not missing, missing


def test_split_names_its_list_of_bodies(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    _open_plate(qtbot, window)
    assert flow.start(window, "feature.split")
    qtbot.wait(50)
    panel = window.panel
    assert panel is not None and panel.is_editing
    form: Any = panel.body_form
    results = form.widgets["keep"]
    group = next(g for g in panel.groups_box.findChildren(Group) if g.isAncestorOf(results))
    label = group.form.labelForField(results)
    assert isinstance(label, QLabel)
    assert label.text() == "Keep"
    assert "bodies that stay" in results.toolTip()
    assert raw_labels(panel.groups_box) == []
    # It is no wider than the words of the group above, so it sits in their column and
    # the list starts where their fields start. "Bodies to keep" pushed the list 29 px
    # to the right of them.
    others = [
        g.form.labelForField(form.widgets[name])
        for name in ("tools", "bodies", "tolerance")
        for g in panel.groups_box.findChildren(Group)
        if g.isAncestorOf(form.widgets[name])
    ]
    assert len(others) == 3
    widest = max(other.fontMetrics().horizontalAdvance(other.text()) for other in others)
    assert label.fontMetrics().horizontalAdvance(label.text()) <= widest
    panel.cancel()


# D2842: no empty rows -------------------------------------------------------------------


def _hosted(qtbot: QtBot, group: Group) -> QWidget:
    """``group`` at the top of a column 240 px wide, as a panel holds its groups."""
    host = QWidget()
    qtbot.addWidget(host)
    column = QVBoxLayout(host)
    column.addWidget(group)
    column.addStretch(1)
    host.resize(240, 300)
    host.show()
    qtbot.wait(20)
    return host


def test_a_note_with_no_words_takes_no_row(qtbot: QtBot) -> None:
    group = Group("Options", "")
    note = Note()
    group.form.addRow(QLabel("Fit"))
    group.form.addRow(note)
    host = _hosted(qtbot, group)
    assert note.isHidden()
    assert blank_rows(host) == []
    note.setText("Fit H7 from the table.")
    qtbot.wait(20)
    assert not note.isHidden() and note.wordWrap()
    assert blank_rows(host) == []
    note.setText("")
    assert note.isHidden()
    # A plain label with no words is what the check is there to find.
    group.form.addRow(QLabel(""))
    qtbot.wait(20)
    found = blank_rows(host)
    assert len(found) == 1 and found[0].startswith("Options: ") and "at the end" in found[0]


def test_a_note_made_with_words_shows_once_it_is_in_a_panel(qtbot: QtBot) -> None:
    """A note is made before it is put in a group. Words given then must not open it
    as a window of its own, and must show once it has a place."""
    first, later = Note("Words from the start."), Note()
    later.setText("Words before it has a place.")
    assert not first.isVisible() and not later.isVisible()
    group = Group("Options", "")
    group.form.addRow(first)
    group.form.addRow(later)
    host = _hosted(qtbot, group)
    assert first.isVisible() and later.isVisible()
    assert blank_rows(host) == []


def test_a_holder_of_rows_takes_no_row_while_it_has_none(qtbot: QtBot) -> None:
    group = Group("Multi Thickness", "")
    holder = QWidget()
    rows = QFormLayout(holder)
    rows.setContentsMargins(0, 0, 0, 0)
    group.form.addRow(QLabel("Faces"))
    group.form.addRow(holder)
    host = _hosted(qtbot, group)
    assert blank_rows(host) == ["Multi Thickness: 8 px empty at the end"]
    show_if_filled(holder)
    qtbot.wait(20)
    assert holder.isHidden() and blank_rows(host) == []
    rows.addRow(QLabel("Face 1"), QLabel("2 mm"))
    show_if_filled(holder)
    qtbot.wait(20)
    assert not holder.isHidden() and blank_rows(host) == []


@pytest.mark.parametrize("kind", ["hole", "draft", "shell"])
def test_the_notes_of_a_panel_take_no_row_until_they_say_something(
    kind: str,
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """The Hole Tool's fit note, Draft's note under Add Faces Needing Draft and Shell's
    answer under Check Walls were labels with no words, each a blank line with a gap."""
    _open_plate(qtbot, window)
    window.insert_feature(kind, "boss")
    qtbot.wait(50)
    panel = window.panel
    assert panel is not None and panel.is_editing
    tabs = panel.page_tabs
    for key in tabs.keys if tabs is not None else [""]:
        if tabs is not None:
            tabs.show_tab(key)
        for group in panel.groups_box.findChildren(Group):
            if not group.isHidden():
                group.set_checked(True)
                group.set_expanded(True)
        qtbot.wait(50)
        assert blank_rows(panel.groups_box) == [], key
    form: Any = panel.form
    note = {"hole": "fit_note", "draft": "assist_note", "shell": "check_result"}[kind]
    label = getattr(form, note)
    assert isinstance(label, Note) and label.isHidden()
    label.setText("Words to read.")
    assert not label.isHidden()
    panel.cancel()


# D2843: Fillet's Variable Radii ---------------------------------------------------------


def _lefts(panel: QWidget, form: Any) -> dict[str, int]:
    """Where each field of the control points and of the radii starts, in the panel."""
    return {
        name: field.mapTo(panel, QPoint(0, 0)).x()
        for name, field in form.fields.items()
        if name.startswith(("vp_", "vr_"))
    }


def _word_widths(*forms: QFormLayout) -> set[int]:
    found = set()
    for layout in forms:
        for row in range(layout.rowCount()):
            item = layout.itemAt(row, QFormLayout.ItemRole.LabelRole)
            assert item is not None
            found.add(item.widget().width())
    return found


def _variable_fillet(qtbot: QtBot, win: MainWindow, edges: int) -> Any:
    """A new fillet of ``edges`` edges of the plate, set to Variable Size."""
    tab, _ext = _open_plate(qtbot, win)
    win.insert_feature("fillet", "boss")
    qtbot.wait(50)
    panel = win.panel
    assert panel is not None and panel.is_editing
    form: Any = panel.form
    report = tab.session.report
    assert report is not None and report.body is not None
    assert form.take_shapes(report.body, edges_of(report.body.shape)[:edges]) is None
    form.kind.setCurrentIndex(form.kind.findData("variable"))
    return form


def test_fillet_variable_radii_fields_start_at_one_x(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """ "Point 1 at (%)" and "Edge 1 point 1" are rows of two forms, each with a column
    for its own words, so their fields started 8 px apart."""
    form = _variable_fillet(qtbot, window, 2)
    panel = window.panel
    assert panel is not None
    form.controls.setValue(2)
    # Wide enough for every field to sit beside its word, whatever the font.
    window.resizeDocks([window.left_dock], [640], Qt.Orientation.Horizontal)
    qtbot.wait(100)
    lefts = _lefts(panel, form)
    assert {"vp_1", "vp_2", "vr_1_start", "vr_1_1", "vr_2_end"} <= set(lefts)
    assert len(set(lefts.values())) == 1, lefts
    assert len(_word_widths(form.positions_form, form.radii_form)) == 1
    # The column follows the rows: one point less, and with no point at all.
    for points in (1, 0):
        form.controls.setValue(points)
        qtbot.wait(100)
        lefts = _lefts(panel, form)
        assert ("vp_1" in lefts) == (points == 1)
        assert "vr_2_end" in lefts and len(set(lefts.values())) == 1, (points, lefts)
        assert blank_rows(panel.groups_box) == [], points
    panel.cancel()


def test_fillet_variable_radii_fields_start_at_one_x_in_the_narrow_panel(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """At the default width of the left panel too, where a field may sit under its
    word: then every field of both sets does."""
    form = _variable_fillet(qtbot, window, 2)
    panel = window.panel
    assert panel is not None
    form.controls.setValue(1)
    qtbot.wait(100)
    assert window.left_dock.width() == window.default_left_width()
    lefts = _lefts(panel, form)
    assert len(lefts) == 7 and len(set(lefts.values())) == 1, lefts
    panel.cancel()


# D2844: a row of radii for every edge ---------------------------------------------------


def test_fillet_variable_radii_has_rows_for_every_edge(
    styled: QApplication,  # noqa: F811
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """The rows of radii were counted by the control points, not by the edges: three
    edges with one control point showed the radii of Edge 1 only, and with no control
    point no radius at all."""
    form = _variable_fillet(qtbot, window, 3)
    panel = window.panel
    assert panel is not None

    def radii() -> list[str]:
        return sorted(name for name in form.fields if name.startswith("vr_"))

    assert form.controls.value() == 0
    assert radii() == [f"vr_{k}_{end}" for k in (1, 2, 3) for end in ("end", "start")]
    form.controls.setValue(1)
    qtbot.wait(50)
    assert radii() == [f"vr_{k}_{at}" for k in (1, 2, 3) for at in ("1", "end", "start")]
    assert sorted(name for name in form.fields if name.startswith("vp_")) == ["vp_1"]
    form.controls.setValue(4)
    qtbot.wait(50)
    assert len(radii()) == 3 * 6
    feature = panel.current_feature()
    assert feature is not None
    assert {"vr_1_start", "vr_2_3", "vr_3_end"} <= set(feature.params)
    panel.cancel()
