"""Draft Analysis in the app (PHASE2_SPEC P2.7 item 4, DECISIONS D522)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.print_tools.draft_analysis import COLORS
from tests.ui.test_phase2_flow import _folders, plate_tab, window
from tests.ui.test_print_orientation_ui import _side_face

__all__ = ["_folders", "window"]


def _painted(tab: object) -> list[str]:
    return sorted(c for _f, c in tab.viewport.painted_faces)  # type: ignore[attr-defined]


def test_command_is_a_checkable_evaluate_tool(window: MainWindow) -> None:
    assert BY_ID["evaluate.draft_analysis"].group == "Evaluate"
    assert window.commands.actions["evaluate.draft_analysis"].isCheckable()


def test_top_plane_by_default_then_front_plane_reverse_and_off(
    qtbot: QtBot, window: MainWindow
) -> None:
    tab, _ext = plate_tab(qtbot, window)
    analysis = window.draft_analysis
    window.commands.actions["evaluate.draft_analysis"].trigger()
    assert analysis.panel.isVisible()
    qtbot.waitUntil(lambda: "Draft from Top Plane" in window.status.text(), timeout=20000)
    # The plate lies on the Front plane: pulled along the Top plane normal, four faces need draft.
    assert "4 faces need draft" in window.status.text()
    assert _painted(tab).count(COLORS["needs"]) == 4
    assert "Needs draft: 4 faces" in analysis.legend["needs"].text()
    front = analysis.direction.findText("Front Plane")
    analysis.direction.setCurrentIndex(front)
    qtbot.waitUntil(lambda: "Draft from Front Plane" in window.status.text(), timeout=20000)
    assert "1 face positive, 1 face negative, 4 faces need draft" in window.status.text()
    analysis.angle.setValue(5.0)
    qtbot.waitUntil(lambda: "at 5 degrees" in window.status.text(), timeout=20000)
    window.commands.actions["evaluate.draft_analysis"].trigger()
    assert tab.viewport.painted_faces == []  # type: ignore[attr-defined]
    assert not analysis.panel.isVisible()


def test_selected_side_face_as_direction(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ext = plate_tab(qtbot, window)
    analysis = window.draft_analysis
    window.commands.actions["evaluate.draft_analysis"].trigger()
    qtbot.waitUntil(lambda: "Draft from" in window.status.text(), timeout=20000)
    tab.selection = []
    analysis.take_selected_face()
    assert "Select one flat face" in window.status.text()
    tab.selection = [_side_face(tab)]
    analysis.take_selected_face()
    qtbot.waitUntil(lambda: "Draft from Selected face" in window.status.text(), timeout=20000)
    assert "1 face positive, 1 face negative, 4 faces need draft" in window.status.text()
    analysis.reverse.setChecked(True)
    qtbot.waitUntil(lambda: "Draft from Selected face" in window.status.text(), timeout=20000)
    window.commands.actions["evaluate.draft_analysis"].trigger()
