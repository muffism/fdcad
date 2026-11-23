"""The Variables tab agrees with the equations manager (bug hunt, v1.0)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core import configurations as configs
from fdcad.core.document.model import Document, Param, Variable
from fdcad.core.units import Kind
from fdcad.ui.equations.commands import DocumentChange
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.property_panel.variables import VariablesPanel
from fdcad.ui.session import DocumentSession
from tests.core.equations.test_equations import _plate
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def _open(qtbot: QtBot, window: MainWindow, doc: Document) -> DocumentTab:  # noqa: F811
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = window.add_session(session)
    return tab


def _tab(window: MainWindow) -> VariablesPanel:  # noqa: F811
    assert window.variables is not None
    return window.variables


def test_edits_keep_comments_and_feature_value_formulas(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    doc = _plate()
    doc.variables[0].comment = "plate width"
    doc.variables.append(Variable("Deep", Kind.LENGTH, '="depth@Extrude 1" * 2', 20.0, "twice"))
    tab = _open(qtbot, window, doc)
    panel = _tab(window)
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        panel.table.item(0, 2).setText("70")
    assert panel.message.text() == ""
    variables = tab.session.document.variables
    assert [(v.name, v.expr, v.value, v.comment) for v in variables] == [
        ("Width", "70", 70.0, "plate width"),
        ("Deep", '="depth@Extrude 1" * 2', 20.0, "twice"),
    ]


def test_renamed_and_removed_variables_take_their_configured_values(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    doc = _plate()
    doc.variables.append(Variable("Spare", Kind.LENGTH, "5", 5.0))
    tab = _open(qtbot, window, doc)
    session = tab.session
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.undo.push(DocumentChange(session, "add", lambda d: configs.add(d, "Long")))
    for name, value in (("Width", 80.0), ("Spare", 7.0)):
        path, param = f"var.{name}", Param(f"{value:g}", value)
        session.undo.push(
            DocumentChange(
                session, "w", lambda d, p=path, v=param: configs.set_scoped(d, p, v, "this")
            )
        )
    panel = _tab(window)
    panel.refresh()
    panel.table.item(0, 0).setText("W")
    panel.table.setCurrentCell(1, 0)
    panel.remove_row()
    doc = session.document
    assert configs.configured_paths(doc) == ["var.W"]
    assert [v.name for v in doc.variables] == ["W"]
    session.undo.undo()  # the removal
    assert configs.configured_paths(session.document) == ["var.Spare", "var.W"]
