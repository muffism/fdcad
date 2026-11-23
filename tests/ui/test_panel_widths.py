"""No tool's panel makes the left panel wider than it is by default (D2791).

Every command of the window is started with nothing selected, then with a face, an
edge and a sketch selected. Whatever it opens in the left panel, with every group
opened, must fit the default width, and the left panel must keep that width. The
quick test does this once per command; the slow one also goes through every choice
of every drop down of each panel, since a choice can show rows that were hidden.

The same sweep looks at two more things in every panel it opens (D2841, D2842,
``panel_checks.py``): no label is the bare name of a field, and no group has an
empty row. The sweep runs once and each test reads what it found.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QComboBox, QTableView, QWidget
from pytestqt.qtbot import QtBot

from fdcad.samples.make import SAMPLE_DIR
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.preferences.settings import Theme
from fdcad.ui.property_panel.elide import is_cut, shown_text
from fdcad.ui.property_panel.groups import Group
from fdcad.ui.themes import app_style, theme
from tests.ui.panel_checks import blank_rows, raw_labels
from tests.ui.sweep_support import (
    SKIP,
    Dialogs,
    close_window,
    install_dialogs,
    make_window,
    open_part,
    pump,
    select,
    settle,
    shapes_of,
)

PART = SAMPLE_DIR / "enclosure.fdprt"
KINDS = ("none", "face", "edge", "sketch")
#: The dialogs record of the window fixture now in use (one entry).
_SHOWN: list[Dialogs] = []
#: Commands that show a dialog and nothing in the left panel. They are left out (D2811):
#: the app sweep opens every dialog, and on the Mac a Preferences dialog that this sweep
#: opened and deleted after other tests had run ended the test process now and then (a
#: fault inside PySide while the dialog's list items are destroyed, as in D639).
DIALOGS = frozenset(
    {
        "file.export_configs",
        "select.in_volume",
        "select.sets",
        "tools.expected_values",
        "tools.hole_table",
        "tools.material",
        "tools.part_notes",
        "tools.properties",
        "tools.slice",
        "tree.remove_history",
        "ui.preferences",
        "view.describe_part",
        "view.display_quality",
        "view.display_states",
    }
)
#: A drop down with more entries than this is a list of things in the part (bodies,
#: sketches, favourites), not a choice that changes the rows of the panel.
MOST_CHOICES = 12


@pytest.fixture(autouse=True)
def _folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("FDCAD_DATA_DIR", str(tmp_path / "data"))


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[MainWindow]:
    """A window in FDCAD's own style, as the app shows it, with no dialog that waits.
    What the replaced dialogs showed is kept in ``_SHOWN``."""
    _SHOWN.clear()
    _SHOWN.append(install_dialogs(monkeypatch))
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    font = app.font()
    theme.apply_theme(app, Theme.LIGHT)  # sizes differ without FDCAD's style sheet
    win = make_window(tmp_path)
    win.resize(1440, 900)
    yield win
    close_window(win)
    app_style._uninstall()
    app.setStyleSheet("")
    app.setPalette(app.style().standardPalette())
    app.setFont(font)
    theme._forced = None


def _open_groups(win: MainWindow) -> None:
    """Open every group of whatever shows in the left panel, and tick its tick box."""
    assert win.properties is not None
    for group in win.properties.findChildren(Group):
        if not group.isHidden() and group.isEnabled():
            if group.check is not None and not group.is_checked():
                group.set_checked(True)
            group.set_expanded(True)


def _pages(win: MainWindow) -> Iterator[str]:
    """Show each tab of a panel with tabs in turn (D2790); one page for the others."""
    tabs = getattr(win.panel, "page_tabs", None) if win.panel is not None else None
    if tabs is None or win.editing != "feature":
        yield ""
        return
    for index, key in enumerate(tabs.keys):
        if tabs.bar.isTabVisible(index):
            tabs.show_tab(key)
            yield f", tab {tabs.bar.tabText(index)}"
    tabs.show_tab(tabs.keys[0])


def _too_wide(win: MainWindow, default: int) -> str:
    """Why what shows now breaks the rule, or an empty text."""
    _open_groups(win)
    pump(20)
    fits = win.fit_panels()
    need = win.panel_width_needed()
    width = win.left_dock.width()
    if width > default:
        return f"the left panel is {width} px wide"
    if not fits or need > default:
        return f"needs {need} px; widest: {_widest(win)}"
    cut = _cut_short(win)
    if cut:
        return f"the drop down entry {cut!r} is cut short without an ellipsis"
    table = _scrolls_sideways(win)
    if table:
        return f"the table {table!r} has a sideways scroll bar"
    return ""


def _scrolls_sideways(win: MainWindow) -> str:
    """The name of a table on show whose columns are wider than it is (D2804)."""
    assert win.properties is not None
    shown = win.properties.currentWidget()
    for table in shown.findChildren(QTableView) if shown is not None else []:
        if table.isVisibleTo(shown) and table.horizontalScrollBar().maximum() > 0:
            return table.objectName() or type(table).__name__
    return ""


def _cut_short(win: MainWindow) -> str:
    """The entry of a drop down on show that is cut in the middle of a letter (D2800):
    one with no room for its entry must end it with an ellipsis."""
    assert win.properties is not None
    shown = win.properties.currentWidget()
    for box in shown.findChildren(QComboBox) if shown is not None else []:
        if box.isVisibleTo(shown) and is_cut(box) and not box.property("elides_entry"):
            return shown_text(box)
    return ""


def _widest(win: MainWindow) -> str:
    """The three widest controls on show, to say where to look."""
    assert win.properties is not None
    shown = win.properties.currentWidget()
    found: list[tuple[int, str]] = []
    for child in shown.findChildren(QWidget) if shown is not None else []:
        if not child.isVisibleTo(shown) or child.findChildren(QWidget):
            continue
        width = max(child.minimumSizeHint().width(), child.minimumWidth())
        text = getattr(child, "text", None)
        words = text() if callable(text) else ""
        if isinstance(child, QComboBox):
            words = child.currentText() or child.placeholderText()
        found.append((width, f"{type(child).__name__} {str(words)[:30]!r} {width} px"))
    return "; ".join(name for _w, name in sorted(found, reverse=True)[:3])


def _choices(win: MainWindow) -> list[QComboBox]:
    assert win.properties is not None
    shown = win.properties.currentWidget()
    boxes = shown.findChildren(QComboBox) if shown is not None else []
    return [
        box
        for box in boxes
        if box.isVisibleTo(shown)
        and box.isEnabled()
        and 1 < box.count() <= MOST_CHOICES
        and not box.isEditable()
        and box.objectName() not in ("favourite_names", "favourite_default")
    ]


@dataclass
class Found:
    """What one sweep found, by kind of fault. Each entry names the command."""

    wide: list[str] = field(default_factory=list)
    raw: list[str] = field(default_factory=list)
    blank: list[str] = field(default_factory=list)

    def look(self, win: MainWindow, where: str) -> None:
        """Note the bare names and the empty rows of what shows now, each once per
        command and tab."""
        shown = win.properties.currentWidget() if win.properties is not None else None
        if shown is None:
            return
        for kept, new in ((self.raw, raw_labels(shown)), (self.blank, blank_rows(shown))):
            for text in new:
                if f"{where}: {text}" not in kept:
                    kept.append(f"{where}: {text}")


#: What the quick sweep (False) and the slow one (True) found, once each has run.
_FOUND: dict[bool, Found] = {}


def _found(win: MainWindow, deep: bool) -> Found:
    """The findings of the sweep, which runs the first time they are asked for."""
    if deep not in _FOUND:
        tab = open_part(win, PART)
        assert win.left_dock.width() == win.default_left_width()
        _FOUND[deep] = _sweep(win, tab, KINDS, deep)
    return _FOUND[deep]


def _sweep(win: MainWindow, tab: DocumentTab, kinds: tuple[str, ...], deep: bool) -> Found:
    dialogs = _SHOWN[0]
    default = win.default_left_width()
    shapes = shapes_of(tab)
    found = Found()
    wide = found.wide
    seen = 0
    # A dialog command that is not in ``DIALOGS`` yet is started once, not once per
    # selection, and the test then asks for it to be added there.
    only_dialog: set[str] = set()
    for cid in sorted(win.commands.actions):
        if cid in SKIP or cid in DIALOGS:
            continue
        for kind in kinds:
            settle(win, tab)
            if win.left_dock.width() != default:
                # A command such as Full Screen resized the window: start again.
                win.resizeDocks([win.left_dock], [default], Qt.Orientation.Horizontal)
                pump(10)
            if cid in only_dialog or not select(win, tab, kind, shapes):
                continue
            shown = len(dialogs.shown)
            try:
                win.commands.trigger(cid)
            except Exception:  # what a command does is the app sweep's business
                continue
            pump(30)
            if not win.editing and win.properties.currentWidget() is win.panel:
                if len(dialogs.shown) > shown:
                    only_dialog.add(cid)
                continue  # it opened nothing in the left panel
            seen += 1
            for page in _pages(win):
                why = _too_wide(win, default)
                if why:
                    wide.append(f"{cid} with {kind} selected{page}: {why}")
                found.look(win, f"{cid}{page}")
                if not deep:
                    continue
                for box in _choices(win):
                    start = box.currentIndex()
                    for index in range(box.count()):
                        try:
                            box.setCurrentIndex(index)
                        except Exception:
                            break
                        pump(10)
                        why = _too_wide(win, default)
                        if why:
                            text = box.itemText(index)
                            wide.append(f"{cid} with {kind} selected{page}, {text!r}: {why}")
                        found.look(win, f"{cid}{page}")
                    box.setCurrentIndex(start)
                    pump(10)
    settle(win, tab)
    assert not only_dialog, f"add to DIALOGS in this file: {sorted(only_dialog)}"
    assert seen > 40, f"only {seen} panels opened: the sweep is not reaching the tools"
    return found


def _report(wide: list[str], default: int) -> None:
    listed = "\n".join(wide[:60])
    assert not wide, f"{len(wide)} panels need more than the default {default} px:\n{listed}"


def _none(found: list[str], what: str) -> None:
    listed = "\n".join(found[:60])
    assert not found, f"{len(found)} {what}:\n{listed}"


def test_no_panel_is_wider_than_the_default(window: MainWindow) -> None:
    _report(_found(window, deep=False).wide, window.default_left_width())


def test_no_panel_shows_the_bare_name_of_a_field(window: MainWindow) -> None:
    """D2841: Split showed "keep" in front of its list of bodies."""
    _none(_found(window, deep=False).raw, "labels are bare names of fields")


def test_no_group_of_a_panel_has_an_empty_row(window: MainWindow) -> None:
    """D2842: a note with no words took a row in the Hole Tool and in Draft."""
    _none(_found(window, deep=False).blank, "groups have an empty row")


@pytest.mark.slow
def test_no_choice_of_any_panel_is_wider_than_the_default(window: MainWindow) -> None:
    _report(_found(window, deep=True).wide, window.default_left_width())


@pytest.mark.slow
def test_no_choice_of_any_panel_shows_the_bare_name_of_a_field(window: MainWindow) -> None:
    _none(_found(window, deep=True).raw, "labels are bare names of fields")


@pytest.mark.slow
def test_no_choice_of_any_panel_has_an_empty_row(window: MainWindow) -> None:
    _none(_found(window, deep=True).blank, "groups have an empty row")
