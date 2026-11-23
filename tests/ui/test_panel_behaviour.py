"""Property panel behaviour: Pin, remembered folding, pick box menus (TR206, D861)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.property_panel.groups import Group
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_folded_group_stays_folded(qtbot: QtBot) -> None:
    Group.folded.discard("Trial")
    g = Group("Trial", "tip")
    qtbot.addWidget(g)
    g.arrow.click()
    assert not g.is_expanded() and "Trial" in Group.folded
    again = Group("Trial", "tip")
    qtbot.addWidget(again)
    assert not again.is_expanded()
    again.arrow.click()
    assert "Trial" not in Group.folded


def test_pin_starts_the_command_again(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ids = _open(qtbot, window)
    window.commands.actions["feature.offset_body"].trigger()  # a command, so it can repeat
    panel = window.panel
    assert panel is not None
    panel.pin_button.setChecked(True)
    count = len(tab.session.document.features)
    with qtbot.waitSignal(panel.again, timeout=5000):
        panel.accept()
    qtbot.waitUntil(lambda: panel.is_editing, timeout=5000)
    assert len(tab.session.document.features) == count + 1
    assert panel.feature is not None and panel.feature.type == "offset_body"
    form = panel.body_form
    assert form is not None
    box = form.widgets["bodies"]
    box.clear_all()
    panel.pin_button.setChecked(False)
    panel.reject()


def test_shift_enter_starts_the_command_again(qtbot: QtBot, window: MainWindow) -> None:
    """TR314 (D954): Shift and Enter accepts and opens the same tool again."""
    from PySide6.QtCore import Qt

    tab, _ids = _open(qtbot, window)
    window.commands.actions["feature.offset_body"].trigger()
    panel = window.panel
    assert panel is not None and not panel.pin_button.isChecked()
    count = len(tab.session.document.features)
    with qtbot.waitSignal(panel.again, timeout=5000):
        qtbot.keyClick(panel, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    qtbot.waitUntil(lambda: panel.is_editing, timeout=5000)
    assert len(tab.session.document.features) == count + 1
    panel.reject()


def test_title_red_while_incomplete(qtbot: QtBot, window: MainWindow) -> None:
    """TR314: the title shows the error colour while the preview cannot be built."""
    from types import SimpleNamespace

    _open(qtbot, window)
    window.commands.actions["feature.offset_body"].trigger()
    panel = window.panel
    assert panel is not None
    panel.preview_checked(SimpleNamespace(shape=None, problems=[], checks=[]))
    assert panel.incomplete and "color" in panel.title.styleSheet()
    panel.preview_checked(SimpleNamespace(shape=object(), problems=[], checks=[]))
    assert not panel.incomplete and panel.title.styleSheet() == ""
    panel.reject()
