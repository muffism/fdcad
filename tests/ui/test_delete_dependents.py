"""Delete with a list of dependents (TR201, D807)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from fdcad.core.document.rollback import dependents
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.tree import delete_dialog
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_delete_all_some_or_none(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    tab, ids = _open(qtbot, window)
    session, tree = tab.session, window.tree
    assert tree is not None
    plate = ids["plate"]
    users = [f.id for f in dependents(session.document, plate)]
    assert users  # the boss and hole stand on the plate
    seen: list[list[str]] = []

    def answer(_name: str, items: list, _graphs: list, *_rest: object) -> list[str] | None:
        seen.append([f.id for f in items])
        return None

    monkeypatch.setattr(delete_dialog, "ask", answer)
    monkeypatch.setattr(tree, "ask_keep_sketch", lambda *_a: True)
    tree.delete(plate)
    assert plate in [f.id for f in session.document.features]  # cancelled
    assert seen and set(users) <= set(seen[0]) | {f.id for f in session.document.features}
    monkeypatch.setattr(delete_dialog, "ask", lambda *_a: list(seen[0]))
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tree.delete(plate)
    left = [f.id for f in session.document.features]
    assert plate not in left and not set(seen[0]) & set(left)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.undo.undo()  # one step brings all of them back
    assert plate in [f.id for f in session.document.features]
    assert set(seen[0]) <= {f.id for f in session.document.features}
    monkeypatch.setattr(delete_dialog, "ask", lambda *_a: [])
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tree.delete(plate)
    assert set(seen[0]) <= {f.id for f in session.document.features}  # kept


def test_the_dialog_ticks_everything_first(qtbot: QtBot) -> None:
    from fdcad.core.document.model import Feature

    dialog = delete_dialog.DeleteDialog(
        "Extrude 1", [Feature("f7", "sketch", "Sketch 2"), Feature("f8", "extrude", "Boss")], []
    )
    qtbot.addWidget(dialog)
    assert dialog.chosen() == ["f7", "f8"]
    dialog._tick(False)
    assert dialog.chosen() == []


def test_delete_in_the_view_offers_feature_or_face(qtbot: QtBot, window: MainWindow) -> None:
    tab, ids = _open(qtbot, window)
    assert window.delete_in_view() is None  # nothing picked
    report = tab.session.report
    assert report is not None and report.body is not None
    top = report.body.face(f"{ids['boss']}/cap/end")
    window._selection_changed(tab, [top])
    menu = window.delete_in_view()
    assert menu is not None
    texts = [a.text() for a in menu.actions()]
    assert texts[0].startswith("Delete Feature (") and texts[1] == "Delete Face (1 picked)"
    menu.close()


def test_variables_only_it_used_are_offered_unticked(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TR91 (D940): the delete list offers the variables only the feature used."""
    from fdcad.core.document.model import Param, Variable
    from fdcad.core.units import Kind

    tab, ids = _open(qtbot, window)
    session, tree = tab.session, window.tree
    assert tree is not None
    doc = session.document
    doc.variables.append(Variable("BossHeight", Kind.LENGTH, "6mm", 6.0))
    doc.variables.append(Variable("Shared", Kind.LENGTH, "10mm", 10.0))
    doc.feature(ids["boss"]).params["depth"] = Param("=BossHeight", 6.0)
    doc.feature(ids["plate"]).params["depth"] = Param("=Shared", 10.0)
    offered: list[list[str]] = []

    def answer(_n: str, _items: list, _g: list, _p: object, variables: list[str]) -> list[str]:
        offered.append(list(variables))
        return [delete_dialog.VARIABLE + v for v in variables]

    monkeypatch.setattr(delete_dialog, "ask", answer)
    monkeypatch.setattr(tree, "ask_keep_sketch", lambda *_a: True)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tree.delete(ids["boss"])
    assert offered == [["BossHeight"]]
    assert [v.name for v in doc.variables] == ["Shared"]
    assert ids["boss"] not in [f.id for f in doc.features]
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.undo.undo()  # one step brings the feature and the variable back
    assert [v.name for v in session.document.variables] == ["BossHeight", "Shared"]
    assert ids["boss"] in [f.id for f in session.document.features]


def test_variables_start_unticked(qtbot: QtBot) -> None:
    dialog = delete_dialog.DeleteDialog("Boss", [], [], None, ["BossHeight"])
    qtbot.addWidget(dialog)
    assert dialog.chosen() == [] and dialog.chosen_variables() == []
    dialog.variables.item(0).setCheckState(Qt.CheckState.Checked)
    assert dialog.chosen_variables() == ["BossHeight"]
