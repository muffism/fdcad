"""Overhang Analysis in the app (PLAN Phase 2, DECISIONS D354)."""

from __future__ import annotations

import math

from pytestqt.qtbot import QtBot

from fdcad.core.printing.profiles import PrinterProfile
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.preferences import print_settings
from fdcad.ui.print_tools.overhang import FULL_COLOR
from tests.ui.test_phase2_flow import _folders, plate_tab, window
from tests.ui.test_print_orientation_ui import _side_face

__all__ = ["_folders", "window"]


def test_flat_plate_has_no_overhang(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ext = plate_tab(qtbot, window)
    action = window.commands.actions["evaluate.overhang"]
    action.trigger()
    qtbot.waitUntil(lambda: "No face overhangs more than 45" in window.status.text(), timeout=20000)
    assert tab.viewport.painted_faces == []  # type: ignore[attr-defined]


def test_upside_down_build_paints_the_overhang_and_turns_off(
    qtbot: QtBot, window: MainWindow
) -> None:
    from fdcad.ui.commands.print_setup import SetPrintSetup

    tab, ext = plate_tab(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None
    window.commands.actions["evaluate.overhang"].trigger()
    qtbot.waitUntil(lambda: "No face overhangs" in window.status.text(), timeout=20000)
    # Lay the side face flat: the plate stands up, its faces are walls: still nothing.
    tab.selection = [_side_face(tab)]
    window.commands.actions["print.lay_flat"].trigger()
    qtbot.waitUntil(lambda: "No face overhangs" in window.status.text(), timeout=20000)
    # Lay the top face on the bed: even a steep 10 degree limit finds nothing.
    from fdcad.core.naming.select import reference_for

    top = report.body.face(f"{ext}/cap/end")
    assert top is not None
    ref = reference_for(report.body, top)
    tab.session.undo.push(SetPrintSetup(tab.session, ref, "Set"))
    qtbot.waitUntil(lambda: "No face overhangs" in window.status.text(), timeout=20000)
    print_settings.set_profiles(
        window.settings, [PrinterProfile("Steep", overhang_angle=math.radians(10))], "Steep"
    )
    window.overhang_analysis.refresh()
    qtbot.waitUntil(lambda: "No face overhangs more than 10" in window.status.text(), timeout=20000)
    window.commands.actions["evaluate.overhang"].trigger()
    assert tab.viewport.painted_faces == []  # type: ignore[attr-defined]


def test_overhang_colours_a_bridge(qtbot: QtBot, window: MainWindow) -> None:
    """A part with a ceiling over a gap gets one red face."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt

    from fdcad.core.naming.names import NamedShape

    tab, _ext = plate_tab(qtbot, window)
    block = BRepPrimAPI_MakeBox(30, 10, 20).Shape()
    tunnel = BRepPrimAPI_MakeBox(gp_Pnt(10, -1, -1), 10, 12, 11).Shape()
    report = tab.session.report
    assert report is not None
    last = list(report.results.values())[-1]
    last.body = NamedShape(BRepAlgoAPI_Cut(block, tunnel).Shape())
    window.commands.actions["evaluate.overhang"].trigger()
    qtbot.waitUntil(
        lambda: "above 45 degrees: 1 face (red), 0 faces in part" in window.status.text(),
        timeout=20000,
    )
    painted = tab.viewport.painted_faces  # type: ignore[attr-defined]
    assert [c for _f, c in painted] == [FULL_COLOR]
