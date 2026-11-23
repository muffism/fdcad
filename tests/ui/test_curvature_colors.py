"""Curvature colours on faces with a scale and readout (TR199 item 1, D2503)."""

from __future__ import annotations

from typing import Any

from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from pytestqt.qtbot import QtBot

from fdcad.core.units import UnitSystem
from fdcad.ui.command_tabs.tabs import EVALUATE_GROUPS
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.curvature_colors import NOTHING_UNDER, unit_text
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_main_window import _folders, _open_plate, window

__all__ = ["_folders", "window"]


def test_command_icon_and_tab() -> None:
    from fdcad.ui.icons.audit import audit

    command = BY_ID["evaluate.curvature_colors"]
    assert command.label == "Curvature Colors" and command.group == "Evaluate"
    assert audit("evaluate.curvature_colors") == []
    listed = [
        c for _g, big, small in EVALUATE_GROUPS for c in [*big, *(x for s in small for x in s)]
    ]
    assert "evaluate.curvature_colors" in listed


def test_unit_text() -> None:
    assert unit_text("largest", 0.25, UnitSystem.MM) == "0.25 1/mm"
    assert unit_text("gaussian", 1.0, UnitSystem.IN) == "645.2 1/in²"


def test_toggle_paints_faces_and_reads_the_cursor(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ext = _open_plate(qtbot, window)
    colors = window.curvature_colors
    assert window.commands.trigger("evaluate.curvature_colors")
    assert colors.on and colors.panel.isVisible()
    qtbot.waitUntil(lambda: colors.result is not None, timeout=10000)
    painted = getattr(tab.viewport, "painted_faces", [])
    assert painted and len(painted) == len(colors.result)
    assert colors.low.text().endswith("1/mm")
    # The readout: a cylinder face under the cursor.
    cyl = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 4.0, 10.0).Shape()
    explorer = TopExp_Explorer(cyl, TopAbs_FACE)
    face: Any = explorer.Current()
    tab.viewport.shape_under_cursor = lambda: face  # type: ignore[method-assign]
    colors.cursor_moved((4.0, 0.0, 5.0))
    assert "radius 4" in colors.readout.text()
    tab.viewport.shape_under_cursor = lambda: None  # type: ignore[method-assign]
    colors.cursor_moved(None)
    assert colors.readout.text() == NOTHING_UNDER
    assert window.commands.trigger("evaluate.curvature_colors")
    assert not colors.on and getattr(tab.viewport, "painted_faces", None) == []
