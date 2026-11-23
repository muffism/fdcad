"""View > Show Types (TR215, D819)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_ticks_per_type_and_hide_all(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ids = _open(qtbot, window)
    session = tab.session
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.document.features.append(
            Feature("f90", "ref_axis", "Axis 1", params={"kind": "two_points"}, refs={})
        )
        session.request_rebuild()
    window.type_actions["planes"].setChecked(False)
    assert "planes" in tab.hidden_types and tab.visible_plane_ids() == []
    window.type_actions["planes"].setChecked(True)
    assert "planes" not in tab.hidden_types
    window.show_sketches_action.setChecked(True)
    window.hide_all_types()
    assert all(not a.isChecked() for a in window.type_actions.values())
    assert not window.show_sketches_action.isChecked()
    window.hide_all_types()  # back as it was
    assert all(a.isChecked() for a in window.type_actions.values())
    assert window.show_sketches_action.isChecked()
