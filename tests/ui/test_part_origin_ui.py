"""Move Part Origin from the tree menu (TR343, D2419)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QInputDialog
from pytestqt.qtbot import QtBot

from fdcad.ui import strings
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.features.test_features import plate
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_move_origin_to_the_box_centre_and_back(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc, _ext = plate()
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    tree = window.tree
    assert tree is not None
    item = tree.item_for("f1")
    assert item is not None
    menu = tree._context_menu(session, item)
    assert menu is not None and strings.MOVE_PART_ORIGIN in [a.text() for a in menu.actions()]
    box = strings.PART_ORIGIN_CHOICES["box"]
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *_a, **_k: (box, True)))
    assert tree.ask_part_origin()
    origin = session.document.feature("f1")
    assert (origin.params["ox"].value, origin.params["oy"].value, origin.params["oz"].value) == (
        pytest.approx(25.0),
        pytest.approx(25.0),
        pytest.approx(5.0),
    )
    assert tree.move_part_origin("reset")
    assert "ox" not in session.document.feature("f1").params
    session.undo.undo()
    assert "ox" in session.document.feature("f1").params
    assert not tree.move_part_origin("selection")  # nothing selected
