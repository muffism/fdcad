"""Copy Values to Others and Edit by Rule (TR160, D957)."""

from __future__ import annotations

from typing import Any

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.tree import copy_values as copy_ui
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_copy_values_from_the_tree(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    tab, ids = _open(qtbot, window)
    doc = tab.session.document
    plate, boss = ids["plate"], ids["boss"]
    assert boss in copy_ui.others_of_kind(doc, plate)
    monkeypatch.setattr(copy_ui, "ask_targets", lambda _d, _s, _p: [boss])
    assert window.tree.copy_values(plate) == 1
    depth = doc.feature(boss).params["depth"]
    assert isinstance(depth, Param) and depth.value == pytest.approx(10.0)
    tab.session.undo.undo()
    depth = doc.feature(boss).params["depth"]
    assert isinstance(depth, Param) and depth.value == pytest.approx(6.0)


def test_copy_values_dialog_starts_unticked(qtbot: QtBot, window: MainWindow) -> None:
    tab, ids = _open(qtbot, window)
    dialog = copy_ui.CopyValuesDialog(tab.session.document, ids["plate"], window)
    qtbot.addWidget(dialog)
    assert dialog.items.count() == 2 and dialog.chosen() == []


def test_edit_by_rule_dialog_and_command(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    tab, ids = _open(qtbot, window)
    doc = tab.session.document
    dialog = copy_ui.EditByRuleDialog(tab.session, window)
    qtbot.addWidget(dialog)
    dialog.ftype.setCurrentIndex(dialog.ftype.findData("extrude"))
    dialog.param.setCurrentIndex(dialog.param.findData("depth"))
    dialog.test.setCurrentIndex(dialog.test.findData("<"))
    dialog.limit.setText("8")
    assert set(dialog.matches()) == {ids["hole"], ids["boss"]}
    assert dialog.found.count() == 2
    dialog.new_value.setText("5mm")
    value = dialog.value()
    assert value is not None and value.value == pytest.approx(5.0)
    found: list[Any] = [[ids["boss"]], "depth", Param("4mm", 4.0)]
    monkeypatch.setattr(copy_ui, "ask_rule", lambda _s, _p: tuple(found))
    window.commands.actions["edit.edit_by_rule"].trigger()
    depth = doc.feature(ids["boss"]).params["depth"]
    assert isinstance(depth, Param) and depth.value == pytest.approx(4.0)
