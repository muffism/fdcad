"""Custom command tabs and a simple mode (TR222, D2508)."""

from __future__ import annotations

from fdcad.ui.command_tabs.custom import (
    ADD,
    HIDE,
    PER_GROUP,
    REMOVE,
    SIMPLE_COMMANDS,
    TAB_NAME,
    custom_groups,
    shown,
)
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_main_window import _folders, window

__all__ = ["_folders", "window"]


def _button(window: MainWindow, tab: str, cid: str):  # type: ignore[no-untyped-def]
    tabs = window.command_tabs
    panel = tabs.widget(tabs.index_of(tab))
    customizer = window.tab_customizer
    return next(b for b in panel.buttons() if customizer.command_of(b) == cid)


def test_rules() -> None:
    groups = custom_groups([f"c{i}" for i in range(PER_GROUP + 2)])
    assert [len(big) for _t, big, _s in groups] == [PER_GROUP, 2]
    assert shown("feature.wrap", "features", set(), False)
    assert not shown("feature.wrap", "features", {"feature.wrap"}, False)
    assert shown("feature.wrap", TAB_NAME, {"feature.wrap"}, False)  # my own tab keeps it
    assert not shown("feature.wrap", "features", set(), True)
    assert shown("feature.extrude", "features", set(), True)
    assert shown("sketch.line", "sketch", set(), True)
    assert "feature.extrude" in SIMPLE_COMMANDS


def test_my_commands_tab(window: MainWindow) -> None:
    tabs = window.command_tabs
    assert tabs.index_of(TAB_NAME) == -1  # no commands, no tab
    button = _button(window, "features", "feature.extrude")
    menu = window.tab_customizer.button_menu(button)
    assert [a.text() for a in menu.actions()] == [ADD, HIDE]
    menu.actions()[0].trigger()
    assert window.settings.custom_commands == ["feature.extrude"]
    index = tabs.index_of(TAB_NAME)
    assert index >= 0 and tabs.isTabVisible(index)
    mine = _button(window, TAB_NAME, "feature.extrude")
    assert mine.toolButtonStyle() is not None
    menu = window.tab_customizer.button_menu(mine)
    assert [a.text() for a in menu.actions()] == [REMOVE]  # no Hide on my own tab
    menu.actions()[0].trigger()
    assert tabs.index_of(TAB_NAME) == -1 and window.settings.custom_commands == []


def test_hide_button_and_show_hidden(window: MainWindow) -> None:
    customizer = window.tab_customizer
    button = _button(window, "features", "feature.extrude")
    customizer.hide_button("feature.extrude")
    assert button.isHidden() and window.settings.hidden_buttons == ["feature.extrude"]
    menu = window.command_tabs.tab_menu()
    show = next(a for a in menu.actions() if a.text() == "Show Hidden Buttons")
    assert show.isEnabled()
    show.trigger()
    assert not button.isHidden() and window.settings.hidden_buttons == []


def test_simple_mode_hides_tabs_and_buttons_and_comes_back(window: MainWindow) -> None:
    tabs = window.command_tabs
    assert window.settings.simple_mode is False  # off by default
    wrap = _button(window, "features", "feature.extrude")
    menu = tabs.tab_menu()
    simple = next(a for a in menu.actions() if a.objectName() == "simple_mode")
    simple.setChecked(True)
    assert window.settings.simple_mode
    assert not tabs.isTabVisible(tabs.index_of("print"))
    assert tabs.isTabVisible(tabs.index_of("features"))
    assert not wrap.isHidden()
    rib = _button(window, "features", "feature.rib")
    assert rib.isHidden()
    # A tab ticked off in simple mode is the user's choice; simple mode's own hiding is not.
    tabs.set_tab_shown(tabs.index_of("evaluate"), False)
    assert window.settings.hidden_command_tabs == ["evaluate"]
    window.tab_customizer.set_simple(False)
    assert tabs.isTabVisible(tabs.index_of("print")) and not rib.isHidden()
    assert not tabs.isTabVisible(tabs.index_of("evaluate"))
    tabs.show_all()
    assert tabs.isTabVisible(tabs.index_of("evaluate"))
