"""Purge Unused and Delete Below Rollback Bar (TR159, D956)."""

from __future__ import annotations

from typing import Any

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Variable
from fdcad.core.units import Kind
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.tree import purge as purge_ui
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_purge_unused_variable(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    tab, _ids = _open(qtbot, window)
    doc = tab.session.document
    doc.variables.append(Variable("Spare", Kind.LENGTH, "1mm", 1.0))
    seen: list[Any] = []

    def ask(_session: Any, found: Any, _parent: Any) -> Any:
        seen.append(found)
        return [], ["Spare"]

    monkeypatch.setattr(purge_ui, "ask", ask)
    window.commands.actions["tree.purge_unused"].trigger()
    assert seen and "Spare" in seen[0].variables
    assert all(v.name != "Spare" for v in doc.variables)
    tab.session.undo.undo()
    assert any(v.name == "Spare" for v in doc.variables)


def test_purge_dialog_lists_and_ticks(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ids = _open(qtbot, window)
    doc = tab.session.document
    doc.variables.append(Variable("Spare", Kind.LENGTH, "1mm", 1.0))
    from fdcad.core.document.purge import find_unused

    dialog = purge_ui.PurgeDialog(tab.session, find_unused(doc), window)
    qtbot.addWidget(dialog)
    assert dialog.items.count() >= 1
    _features, variables = dialog.chosen()
    assert "Spare" in variables  # every item starts ticked


def test_delete_below_the_bar(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    tab, _ids = _open(qtbot, window)
    doc = tab.session.document
    count = len(doc.features)
    monkeypatch.setattr(purge_ui, "confirm_below_bar", lambda _p, _names: True)
    window.commands.actions["tree.delete_below_bar"].trigger()  # nothing below: a message
    assert len(doc.features) == count
    window.tree.roll_back_one()
    window.commands.actions["tree.delete_below_bar"].trigger()
    assert len(doc.features) == count - 1
    tab.session.undo.undo()
    assert len(doc.features) == count
