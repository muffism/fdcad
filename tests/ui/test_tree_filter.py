"""The tree filter box (TR95, D806)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.tree.feature_tree import FID_ROLE
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def _shown(window: MainWindow) -> list[str]:
    assert window.tree is not None
    return [i.text(0) for i in window.tree.all_items() if not i.isHidden()]


def test_filter_by_name_and_state(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ids = _open(qtbot, window)
    box = window.tree_filter
    everything = _shown(window)
    box.text.setText("front")
    assert _shown(window) == ["Front Plane"]
    box.text.setText("")
    assert _shown(window) == everything
    assert window.tree is not None
    fid = next(
        i.data(0, FID_ROLE)
        for i in window.tree.all_items()
        if isinstance(i.data(0, FID_ROLE), str) and i.data(0, FID_ROLE).startswith("f")
        and tab.session.document.feature(i.data(0, FID_ROLE)).type == "extrude"
    )  # fmt: skip
    tab.session.document.feature(fid).suppressed = True
    box.state.setCurrentIndex(box.state.findData("suppressed"))
    window.tree.refresh()
    names = _shown(window)
    assert tab.session.document.feature(fid).name in names
    assert "Front Plane" not in names
    box.state.setCurrentIndex(box.state.findData("all"))
    assert "Front Plane" in _shown(window)
