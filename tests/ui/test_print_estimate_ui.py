"""Print Estimate in the Evaluate tab (PLAN Phase 2, DECISIONS D355)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.preferences import print_settings
from fdcad.ui.print_tools.estimate import PrintEstimate, volume_text
from fdcad.ui.strings_print import ESTIMATE_NOTE, ESTIMATE_NOTHING
from tests.ui.test_phase2_flow import _folders, plate_tab, window

__all__ = ["_folders", "window"]

PLATE = 50 * 50 * 10  # mm3, the test plate


def test_estimate_shows_volume_and_weight_labelled_as_solid(
    qtbot: QtBot, window: MainWindow
) -> None:
    plate_tab(qtbot, window)
    window.commands.actions["evaluate.print_estimate"].trigger()
    tool = window.print_estimate
    assert isinstance(tool, PrintEstimate) and tool.panel.isVisible()
    qtbot.waitUntil(lambda: tool.volume_label.text() == "25.00 cm³", timeout=20000)
    assert tool.material_box.currentText() == "PLA"
    assert tool.weight_label.text() == f"{PLATE / 1000 * 1.24:.1f} g"
    assert tool.bodies_label.text() == "1"
    labels = [w.text() for w in tool.panel.findChildren(type(tool.volume_label))]
    assert ESTIMATE_NOTE in labels
    names = [tool.material_box.itemText(i) for i in range(tool.material_box.count())]
    assert names[:6] == ["PLA", "PETG", "ABS", "ASA", "TPU", "Resin"]


def test_material_and_density_edits(qtbot: QtBot, window: MainWindow) -> None:
    plate_tab(qtbot, window)
    tool = window.print_estimate
    tool.open()
    qtbot.waitUntil(lambda: tool.result is not None, timeout=20000)
    tool.material_box.setCurrentText("ABS")
    assert tool.density_box.value() == pytest.approx(1.04)
    assert tool.weight_label.text() == f"{PLATE / 1000 * 1.04:.1f} g"
    tool.density_box.setValue(2.0)
    assert tool.weight_label.text() == "50.0 g"
    assert print_settings.densities(window.settings)["ABS"] == 2.0  # the preset was edited
    assert print_settings.last_material(window.settings) == "ABS"


def test_estimate_follows_a_rebuild_and_needs_a_part(qtbot: QtBot, window: MainWindow) -> None:
    tool = window.print_estimate
    tool.open()
    assert tool.volume_label.text() == ESTIMATE_NOTHING
    tab, _ext = plate_tab(qtbot, window)
    tool.refresh()
    qtbot.waitUntil(lambda: tool.volume_label.text() == "25.00 cm³", timeout=20000)
    extrude = next(f for f in tab.session.document.features if f.type == "extrude")
    from fdcad.core.document.model import Param
    from fdcad.ui.commands.document import SetParam

    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.push(SetParam(tab.session, extrude.id, "depth", Param("20", 20.0)))
    qtbot.waitUntil(lambda: tool.volume_label.text() == "50.00 cm³", timeout=20000)


def test_volume_text_units() -> None:
    assert volume_text(1000.0, "mm") == "1.00 cm³"
    assert volume_text(25.4**3, "in") == "1.000 in³"


def test_estimate_follows_the_shown_part(qtbot: QtBot, window: MainWindow) -> None:
    """Round 10c: after a switch to another part the window kept the first part's volume."""
    first, ext = plate_tab(qtbot, window)
    from fdcad.core.document.model import Param
    from fdcad.ui.commands.document import SetParam

    with qtbot.waitSignal(first.session.rebuilt, timeout=20000):
        first.session.undo.push(SetParam(first.session, ext, "depth", Param("20", 20.0)))
    tool = window.print_estimate
    tool.open()
    qtbot.waitUntil(lambda: tool.volume_label.text() == "50.00 cm³", timeout=20000)
    plate_tab(qtbot, window)  # a second part, shown at once
    qtbot.waitUntil(lambda: tool.volume_label.text() == "25.00 cm³", timeout=20000)
    window.tabs.setCurrentWidget(first)
    qtbot.waitUntil(lambda: tool.volume_label.text() == "50.00 cm³", timeout=20000)
