"""Chamfer panel Partial Edges (TR64 item 5, D1012)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_partial_group_writes_its_range(qtbot: QtBot, window: MainWindow) -> None:
    _open(qtbot, window)
    window.commands.actions["feature.chamfer"].trigger()
    form = window.panel.form
    assert form is not None and hasattr(form, "partial_group")
    assert form.partial_group.isVisibleTo(form.partial_group.parentWidget())
    form.partial_group.set_checked(True)
    form.items.add({"kind": "edge", "name": "edge(a|b)"})
    made = window.panel.current_feature()
    assert made is not None and made.params["partial"] == "distance"
    assert made.params["end_distance"].value == 10.0
    form.method.setCurrentIndex(form.method.findData("asymmetric"))
    assert not form.partial_group.isVisibleTo(form.partial_group.parentWidget())
    made = window.panel.current_feature()
    assert made is not None and "partial" not in made.params
    window.panel.reject()
