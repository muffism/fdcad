"""Before and After window (TR289, D2019)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.ui.compare_tool import LAYER, show_changes
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_rows_after_a_change_and_the_faint_shape(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ids = _open(qtbot, window)
    session = tab.session
    first = next(f for f in session.document.features if f.type == "extrude")
    depth = first.params["depth"]
    assert isinstance(depth, Param)
    first.params["depth"] = Param("x", depth.value + 2.0)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.request_rebuild()
    dialog = show_changes(window)
    assert dialog is not None and dialog.table.rowCount() >= 1
    dialog.table.selectRow(0)
    assert tab.viewport.print_layers.get(LAYER)
    dialog.reject()
    assert not tab.viewport.print_layers.get(LAYER)
