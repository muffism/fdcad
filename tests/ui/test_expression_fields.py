"""Expressions in feature panel fields (TOOL_SPEC T14.6)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Document, Variable
from fdcad.core.units import Kind
from fdcad.core.units.variables import requested_variable, valid_name
from fdcad.ui.property_panel.panel import PropertyPanel
from fdcad.ui.session import DocumentSession
from tests.core.features.test_features import plate


def _session(qtbot: QtBot, doc: Document) -> DocumentSession:
    session = DocumentSession(doc)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.request_rebuild()
    return session


@pytest.fixture
def panel(qtbot: QtBot) -> PropertyPanel:
    widget = PropertyPanel()
    qtbot.addWidget(widget)
    widget.show()
    return widget


def test_request_parser() -> None:
    assert requested_variable('="Depth"') == "Depth"
    assert requested_variable('  = " Wall_2 " ') == "Wall_2"
    assert requested_variable("=Depth") is None
    assert requested_variable("10") is None
    assert valid_name("Wall_2") and not valid_name("2Wall") and not valid_name("a b")


def test_every_field_says_it_takes_expressions_and_toggles(
    qtbot: QtBot, panel: PropertyPanel
) -> None:
    doc, ext = plate()
    doc.variables.append(Variable("Width", Kind.LENGTH, "40", 40.0))
    session = _session(qtbot, doc)
    panel.begin(session, doc.feature(ext), is_new=False)
    for field in panel.values.values():
        assert "expression" in field.toolTip()
    depth = panel.values["depth"]
    tools = depth.tools
    assert tools.button.isHidden()  # a plain value has nothing to switch
    depth.edit.setText("=Width/2")
    assert not tools.button.isHidden()
    tools.button.click()
    assert tools.showing_result and tools.result.text().startswith("20.00")
    assert tools.result.isReadOnly()
    assert depth.edit.text() == "=Width/2"  # the stored expression is unchanged
    param = depth.param()
    assert param is not None and param.expr == "=Width/2" and param.value == pytest.approx(20.0)
    tools.button.click()
    assert not tools.showing_result
    depth.edit.setText("12")
    assert tools.button.isHidden()


def test_typing_a_quoted_new_name_makes_a_variable(
    qtbot: QtBot, panel: PropertyPanel, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc, ext = plate()
    session = _session(qtbot, doc)
    panel.begin(session, doc.feature(ext), is_new=False)
    depth = panel.values["depth"]
    depth.edit.setText("15")
    asked: list[str] = []

    def no(_parent: object, _title: str, text: str) -> QMessageBox.StandardButton:
        asked.append(text)
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", no)
    depth.edit.setText('="Depth"')
    assert "Enter" in depth.info.text()
    qtbot.keyClick(depth.edit, Qt.Key.Key_Return)
    assert asked and "Depth" in asked[0] and "15" in asked[0]
    assert depth.edit.text() == "15" and doc.variables == []
    assert panel.is_editing  # Enter did not accept the panel

    monkeypatch.setattr(QMessageBox, "question", lambda *_a: QMessageBox.StandardButton.Yes)
    depth.edit.setText('="Depth"')
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        qtbot.keyClick(depth.edit, Qt.Key.Key_Return)
    assert depth.edit.text() == "=Depth"
    assert [(v.name, v.expr, v.value) for v in doc.variables] == [("Depth", "15", 15.0)]
    param = depth.param()
    assert param is not None and param.value == pytest.approx(15.0)
    # One undo step removes it again.
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.undo.undo()
    assert doc.variables == []
    # A name already in use just links to it; a bad name is refused.
    doc.variables.append(Variable("Wall", Kind.LENGTH, "3", 3.0))
    depth.variables["Wall"] = (Kind.LENGTH, 3.0)
    assert depth.tools.try_new_variable('="Wall"')
    assert depth.edit.text() == "=Wall"
    assert depth.tools.try_new_variable('="2x"')
    assert "cannot be a variable name" in depth.info.text()
    assert not depth.tools.try_new_variable("12")


def test_value_box_text_can_make_a_variable(
    qtbot: QtBot, panel: PropertyPanel, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc, ext = plate()
    session = _session(qtbot, doc)
    panel.begin(session, doc.feature(ext), is_new=False)
    monkeypatch.setattr(QMessageBox, "question", lambda *_a: QMessageBox.StandardButton.Yes)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        assert panel.set_text("depth", '="Thick"') is None  # the handle value box path
    assert panel.values["depth"].edit.text() == "=Thick"
    assert [v.name for v in doc.variables] == ["Thick"]
