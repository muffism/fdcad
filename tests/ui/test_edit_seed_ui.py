"""Edit Seed on a pattern copy's face (TR142 item 2, D1016)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF
from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.context_menu import keys
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_context_menus import _extruded
from tests.ui.test_workflow import _folders, face_with_normal, window

__all__ = ["_folders", "window"]


def test_edit_seed_opens_the_original(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fdcad.ui.main_window import context_menu as cm

    tab, _sid, fid = _extruded(qtbot, window)
    face = face_with_normal(tab, (0.0, 0.0, 1.0))
    menu = window.context_menus.build_view_menu(tab, [face], pos=QPointF(5, 5))
    assert "edit_seed" not in keys(menu)  # not a pattern copy
    monkeypatch.setattr(cm.ContextMenus, "seed_of", staticmethod(lambda _t, _s: fid))
    opened: list[str] = []
    monkeypatch.setattr(window, "edit_feature", opened.append)
    menu = window.context_menus.build_view_menu(tab, [face], pos=QPointF(5, 5))
    assert "edit_seed" in keys(menu)
    next(a for a in menu.actions() if a.data() == "edit_seed").trigger()
    assert opened == [fid]


def test_copy_values_starts_the_copy_entry(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TR59 item 3 (D1900): right click a copy, Copy Values, and type the values."""
    from fdcad.core.document.model import Param
    from fdcad.ui.main_window import context_menu as cm

    tab, _sid, fid = _extruded(qtbot, window)
    from tests.core.features.phase3_parts import add_feature

    pid = add_feature(
        tab.session.document,
        "linear_pattern",
        {"spacing1": Param("12", 12.0), "count1": Param("3", 3.0)},
        {"direction1": {"feature": "f4"}, "features": [{"feature": fid}]},
    )
    face = face_with_normal(tab, (0.0, 0.0, 1.0))
    monkeypatch.setattr(cm.ContextMenus, "seed_of", staticmethod(lambda _t, _s: fid))
    monkeypatch.setattr(cm.ContextMenus, "instance_of", staticmethod(lambda _t, _s: (pid, (3, 1))))
    menu = window.context_menus.build_view_menu(tab, [face], pos=QPointF(5, 5))
    next(a for a in menu.actions() if a.data() == "copy_values").trigger()
    panel = window.panel
    assert panel is not None and panel.feature is not None and panel.feature.id == pid
    assert panel.body_form.widgets["instance_values"].text() == "3: "
    panel.reject()
