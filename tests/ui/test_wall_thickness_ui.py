"""Wall Thickness Analysis in the app (PLAN Phase 4, DECISIONS D414)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.printing.profiles import PrinterProfile
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.preferences import print_settings
from fdcad.ui.print_tools.wall_thickness import FULL_COLOR
from tests.ui.test_phase2_flow import _folders, plate_tab, window

__all__ = ["_folders", "window"]


def test_command_and_tab(window: MainWindow) -> None:
    assert BY_ID["evaluate.wall_thickness"].group == "Evaluate"
    assert "evaluate.wall_thickness" in window.commands.actions
    assert window.commands.actions["evaluate.wall_thickness"].isCheckable()


def test_thin_plate_is_coloured_against_the_profile_minimum(
    qtbot: QtBot, window: MainWindow
) -> None:
    tab, _ext = plate_tab(qtbot, window)
    report = tab.session.report
    assert report is not None and report.body is not None
    action = window.commands.actions["evaluate.wall_thickness"]
    action.trigger()  # the default profile's 0.8 mm minimum: nothing is thin
    qtbot.waitUntil(lambda: "No wall is thinner than 0.8 mm" in window.status.text(), timeout=20000)
    assert tab.viewport.painted_faces == []  # type: ignore[attr-defined]
    # A profile whose minimum wall is thicker than the plate marks its two large faces.
    print_settings.set_profiles(window.settings, [PrinterProfile("Thick", min_wall=50.0)], "Thick")
    window.wall_thickness.refresh()  # type: ignore[attr-defined]
    qtbot.waitUntil(lambda: "Walls thinner than 50 mm" in window.status.text(), timeout=20000)
    painted = tab.viewport.painted_faces  # type: ignore[attr-defined]
    assert painted and all(c == FULL_COLOR for _f, c in painted)
    assert "Thinnest wall found:" in window.status.text()
    assert tab.session.undo.count() == 0  # display only
    action.trigger()  # off: the colours go
    assert tab.viewport.painted_faces == []  # type: ignore[attr-defined]


def test_typed_target_and_hover_reading(qtbot: QtBot, window: MainWindow) -> None:
    """TR87 item 2 (D1808): a typed target replaces the profile minimum, and the wall under
    the cursor is read into the status bar."""
    tab, _ext = plate_tab(qtbot, window)
    print_settings.set_wall_target(window.settings, 40.0)
    assert print_settings.wall_target(window.settings) == 40.0
    action = window.commands.actions["evaluate.wall_thickness"]
    action.trigger()
    qtbot.waitUntil(lambda: "Walls thinner than 40 mm" in window.status.text(), timeout=20000)
    report = tab.session.report
    assert report is not None and report.body is not None
    window.wall_thickness.hover(tab, (25.0, 25.0, 10.0))  # type: ignore[attr-defined]
    qtbot.waitUntil(lambda: "Wall here: 10.00 mm" in window.status.text(), timeout=20000)
    action.trigger()
    print_settings.set_wall_target(window.settings, 0.0)


def test_target_field_on_the_printing_page(window: MainWindow) -> None:
    from fdcad.ui.preferences.printing_page import PrintingPage

    page = PrintingPage(window.settings)
    page.wall_target_box.setValue(2.5)
    page.apply(window.settings)
    assert print_settings.wall_target(window.settings) == 2.5
    print_settings.set_wall_target(window.settings, 0.0)
