"""Identical bodies grouped in the feature tree (TR308, D958)."""

from __future__ import annotations

from PySide6.QtWidgets import QTreeWidgetItem
from pytestqt.qtbot import QtBot

from fdcad.ui import strings
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.features.test_multibody import two_blocks
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def _bodies_folder(window: MainWindow) -> QTreeWidgetItem:
    tree = window.tree
    for i in range(tree.topLevelItemCount()):
        item = tree.topLevelItem(i)
        if item.text(0).startswith("Solid Bodies"):
            return item
    raise AssertionError("no Solid Bodies folder")


def test_two_same_blocks_share_a_folder(qtbot: QtBot, window: MainWindow) -> None:
    doc, _first, _second, _body = two_blocks(gap=5.0)  # apart, the same size
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    assert session.report is not None and session.report.body_groups == [[0, 1]]
    folder = _bodies_folder(window)
    assert folder.childCount() == 1
    group = folder.child(0)
    assert group.text(0) == strings.IDENTICAL_BODIES.format(count=2)
    assert group.childCount() == 2
