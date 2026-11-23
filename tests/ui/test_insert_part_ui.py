"""Insert Part: the command and Break Link (TR71, D2420)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QFileDialog
from pytestqt.qtbot import QtBot

from fdcad.core.io import fdef
from fdcad.ui import strings
from fdcad.ui.body_tools import flow
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.features.test_features import plate
from tests.core.features.test_insert_part import _insert
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_command_asks_for_the_file(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source, _ext = plate()
    path = tmp_path / "plate.fdprt"
    fdef.save(source, path)
    _open(qtbot, window)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *_a, **_k: ("", "")))
    assert not flow.start(window, "feature.insert_part")  # cancelled
    picked = (str(path), "")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *_a, **_k: picked))
    assert flow.start(window, "feature.insert_part")
    panel = window.panel
    assert panel is not None and panel.feature is not None
    assert panel.feature.params["part_file"] == str(path)
    panel.reject()


def test_break_link_from_the_tree(qtbot: QtBot, window: MainWindow, tmp_path: Path) -> None:
    source, _ext = plate()
    path = tmp_path / "plate.fdprt"
    fdef.save(source, path)
    doc, fid = _insert(path)
    session = DocumentSession(doc, None, window)  # type: ignore[arg-type]
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    tree = window.tree
    assert tree is not None
    item = tree.item_for(fid)
    assert item is not None
    menu = tree._context_menu(session, item)
    assert menu is not None and strings.BREAK_BODY_LINK in [a.text() for a in menu.actions()]
    assert tree.break_part_link(fid)
    feature = session.document.feature(fid)
    assert feature.params["link"] is False and feature.refs["embedded"]["embedded"] in (
        session.document.embedded
    )
