"""Appearance, Section View and Measure follow the shown part (bug hunt round 10c).

Before, each kept working on the part that was shown when it opened: after a
switch to another part, Appearance coloured the hidden part, the section panel
moved the hidden part's section and Measure kept the old part's picks and units.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Document, new_document
from fdcad.core.sketch.model import Sketch
from fdcad.core.units import UnitSystem
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.session import DocumentSession
from tests.core.features.test_features import add_extrude, add_sketch, rect


@pytest.fixture(autouse=True)
def _folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("FDCAD_DATA_DIR", str(tmp_path / "data"))


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> Iterator[MainWindow]:
    settings = Settings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))
    win = MainWindow(settings)
    win.resize(1200, 800)
    win.show()
    win.finish_setup()
    yield win
    win.appearance_tool.close()
    win.measure_tool.close()
    win.section_tool.turn_off()
    while win.tabs.count():
        tab = win.tabs.widget(0)
        assert isinstance(tab, DocumentTab)
        tab.session.cancel_rebuild()
        tab.session.wait()
        tab.autosaver.discard()
        win.tabs.removeTab(0)
    win.close()
    win.deleteLater()


def _plate(units: UnitSystem = UnitSystem.MM) -> Document:
    doc = new_document(units)
    s = Sketch()
    rect(s, 0, 0, 50, 30)
    sk = add_sketch(doc, s, {"feature": "f2"})
    add_extrude(doc, sk, 10.0)
    return doc


def _open(qtbot: QtBot, win: MainWindow, doc: Document) -> DocumentTab:
    session = DocumentSession(doc, None, win)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = win.add_session(session)
    return tab


def test_appearance_panel_closes_when_another_part_is_shown(
    qtbot: QtBot, window: MainWindow
) -> None:
    first = _open(qtbot, window, _plate())
    window.appearance_tool.open()
    assert window.appearance_tool.panel is not None
    second = _open(qtbot, window, _plate())
    assert window.current is second
    assert window.appearance_tool.panel is None
    assert first.session.document.appearance["part_color"] == "#B4BCC4"


def test_section_panel_closes_and_keeps_the_left_part_section(
    qtbot: QtBot, window: MainWindow
) -> None:
    first = _open(qtbot, window, _plate())
    tool = window.section_tool
    tool.toggle()
    assert tool.panel is not None
    second = _open(qtbot, window, _plate())
    assert window.current is second
    assert tool.panel is None
    assert tool.state_of(first) is not None  # closed as OK: the first part keeps its section
    assert tool.state_of(second) is None
    action = window.commands.actions["view.section"]
    assert not action.isChecked()
    tool.toggle()  # the command now opens a section on the shown part
    assert tool.panel is not None and tool.tab is second


def test_measure_box_follows_the_shown_part(qtbot: QtBot, window: MainWindow) -> None:
    _open(qtbot, window, _plate())
    tool = window.measure_tool
    tool.open()
    box = tool.box
    assert box is not None and box.part_units is UnitSystem.MM
    second = _open(qtbot, window, _plate(UnitSystem.IN))
    assert tool.box is box  # options and history stay
    assert tool.tab is second
    assert box.part_units is UnitSystem.IN


def test_closing_a_part_forgets_its_section(qtbot: QtBot, window: MainWindow) -> None:
    """Sections are kept by id(tab): a closed part's section could come back on a new part."""
    first = _open(qtbot, window, _plate())
    tool = window.section_tool
    tool.toggle()
    tool.accept()
    assert tool.state_of(first) is not None
    key = id(first)
    first.session.undo.clear()
    assert window.close_tab(window.tabs.indexOf(first))
    assert key not in tool.states


def test_appearance_over_the_section_panel_closes_it_as_ok(
    qtbot: QtBot, window: MainWindow
) -> None:
    """Round 10c: closing Appearance also took the section panel out of the left panel,
    while the section tool still thought it was open (its arrow stayed, no OK or Cancel)."""
    tab = _open(qtbot, window, _plate())
    section, appearance = window.section_tool, window.appearance_tool
    section.toggle()
    appearance.open()
    assert section.panel is None and section.state_of(tab) is not None  # closed as OK
    appearance.close()
    section.toggle()  # off, as the checked command says
    assert section.state_of(tab) is None
    section.toggle()
    assert section.panel is not None
    appearance.open()
    section.toggle()  # off while Appearance is on top
    assert section.panel is None and appearance.panel is not None
    section.toggle()
    assert appearance.panel is None
    assert window.properties is not None
    assert window.properties.currentWidget() is section.panel
