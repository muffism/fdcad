"""Partial Edges by Reference on the Fillet and Chamfer panels (TR64 item 5, D1401)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.ui import strings
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


@pytest.mark.parametrize("command", ["feature.fillet", "feature.chamfer"])
def test_reference_ends_are_written(qtbot: QtBot, window: MainWindow, command: str) -> None:
    _open(qtbot, window)
    window.commands.actions[command].trigger()
    form = window.panel.form
    assert form is not None and hasattr(form, "partial_ends")
    form.partial_group.set_checked(True)
    form.partial_kind.setCurrentIndex(form.partial_kind.findData("reference"))
    assert form.partial_ends.isVisibleTo(form.partial_ends.parentWidget())
    form.items.add({"kind": "edge", "name": "edge(a|b)"})
    assert window.panel.current_feature() is None or "partial_ends" not in (
        window.panel.current_feature().refs  # type: ignore[union-attr]
    )
    feature = form.feature
    assert form.apply(feature) == strings.PARTIAL_ENDS_NEEDED
    form.partial_ends.picks.add({"kind": "vertex", "name": "vertex(a|b|c)"})
    form.partial_ends.picks.add({"kind": "vertex", "name": "vertex(a|b|d)"})
    made = window.panel.current_feature()
    assert made is not None and made.params["partial"] == "reference"
    assert [r["name"] for r in made.refs["partial_ends"]] == ["vertex(a|b|c)", "vertex(a|b|d)"]
    form.partial_group.set_checked(False)
    made = window.panel.current_feature()
    assert made is not None and "partial_ends" not in made.refs
    window.panel.reject()
