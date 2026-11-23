"""Custom command tabs and a simple mode (TR222, DECISIONS D2508).

- Right click a command button for Add to My Commands (or Remove from My
  Commands) and Hide Button. My Commands is the user's own tab: large buttons with
  text, in the order added, eight to a group. It shows while it has a command.
- The tab bar menu gets Show Hidden Buttons and Simple Mode.
- Simple mode shows only the Features, Sketch, Evaluate and My Commands tabs, and
  on them only the commands most parts need. Turning it off shows everything the
  user had before; it never changes the user's own hidden tabs or buttons.

All of it is settings, never part data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMenu, QWidget

from fdcad.ui.command_tabs.ribbon import RibbonGroup, RibbonPanel

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow

TAB_NAME = "custom"
TAB_TITLE = "My Commands"
GROUP_TITLE = "My Commands"
#: Large buttons per group, so a group stays well under 900 px wide (round 14 rule 4).
PER_GROUP = 8
ADD = "Add to My Commands"
REMOVE = "Remove from My Commands"
HIDE = "Hide Button"
SHOW_HIDDEN = "Show Hidden Buttons"
SIMPLE_MODE = "Simple Mode"
SIMPLE_ON = "Simple mode on: fewer tabs and buttons. Use the tab menu to turn it off."
SIMPLE_OFF = "Simple mode off: every tab and button is back."
#: The tabs simple mode keeps.
SIMPLE_TABS = ("features", "sketch", "evaluate", TAB_NAME)
#: The commands simple mode keeps on those tabs (sketch tools are all kept).
SIMPLE_COMMANDS = frozenset(
    {
        "sketch.sketch",
        "feature.extrude",
        "feature.revolve",
        "feature.extruded_cut",
        "feature.hole",
        "feature.revolved_cut",
        "feature.fillet",
        "feature.chamfer",
        "feature.linear_pattern",
        "feature.circular_pattern",
        "feature.mirror",
        "feature.shell",
        "feature.ref_plane",
        "evaluate.measure",
        "evaluate.mass_properties",
        "view.section",
        "edit.rebuild",
    }
)


def custom_groups(commands: list[str]) -> list[tuple[str, list[Any], list[Any]]]:
    """My Commands as groups of large buttons, at most ``PER_GROUP`` each."""
    out: list[tuple[str, list[Any], list[Any]]] = []
    for start in range(0, len(commands), PER_GROUP):
        out.append((GROUP_TITLE, list(commands[start : start + PER_GROUP]), []))
    return out


def shown(cid: str, tab: str, hidden: set[str], simple: bool) -> bool:
    """Whether the button of ``cid`` on tab ``tab`` shows."""
    if cid in hidden and tab != TAB_NAME:
        return False
    if simple and tab not in ("sketch", TAB_NAME):
        return cid in SIMPLE_COMMANDS
    return True


class TabCustomizer:
    """Keeps My Commands, hidden buttons and simple mode on one window's command tabs."""

    def __init__(self, window: MainWindow) -> None:
        self.window = window
        self.tabs = window.command_tabs
        self.settings = window.settings
        self.panel: RibbonPanel | None = None
        self._ids = {id(a): cid for cid, a in window.commands.actions.items()}
        old_menu = self.tabs.tab_menu

        def tab_menu() -> QMenu:
            menu = old_menu()
            self.add_tab_items(menu)
            return menu

        self.tabs.tab_menu = tab_menu  # type: ignore[method-assign]
        old_show_all = self.tabs.show_all

        def show_all() -> None:
            old_show_all()
            self.apply()  # simple mode still hides its tabs

        self.tabs.show_all = show_all  # type: ignore[method-assign]
        self.tabs.set_tab_shown = self.set_tab_shown  # type: ignore[method-assign]
        self.rebuild_custom()
        self.apply()

    # Buttons ---------------------------------------------------------------------------

    def command_of(self, button: Any) -> str:
        """The command id a button runs (a dropdown: its first tool)."""
        actions = getattr(button, "group_actions", None) or [button.defaultAction()]
        return self._ids.get(id(actions[0]), "")

    def _panel_name(self, panel: QWidget) -> str:
        return panel.objectName().removesuffix("_tab")

    def _hook(self, panel: RibbonPanel) -> None:
        for button in panel.buttons():
            if button.property("custom_menu"):
                continue
            button.setProperty("custom_menu", True)
            button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            button.customContextMenuRequested.connect(
                lambda pos, b=button: self.button_menu(b).popup(b.mapToGlobal(pos))
            )

    def button_menu(self, button: Any) -> QMenu:
        """The right click menu of a command button."""
        cid = self.command_of(button)
        menu = QMenu(button)
        menu.setObjectName("command_button_menu")
        if cid in self.settings.custom_commands:
            menu.addAction(REMOVE, lambda: self.remove_custom(cid))
        else:
            menu.addAction(ADD, lambda: self.add_custom(cid))
        panel = button.window() and self._panel_of(button)
        if panel is not None and self._panel_name(panel) != TAB_NAME:
            menu.addAction(HIDE, lambda: self.hide_button(cid))
        return menu

    def _panel_of(self, widget: QWidget) -> QWidget | None:
        parent = widget.parentWidget()
        while parent is not None and not isinstance(parent, RibbonPanel):
            parent = parent.parentWidget()
        return parent

    # My Commands -----------------------------------------------------------------------

    def add_custom(self, cid: str) -> None:
        """Put a command on My Commands."""
        found = self.settings.custom_commands
        if cid and cid not in found:
            self.settings.custom_commands = [*found, cid]
            self.rebuild_custom()
            self.apply()

    def remove_custom(self, cid: str) -> None:
        """Take a command off My Commands."""
        self.settings.custom_commands = [c for c in self.settings.custom_commands if c != cid]
        self.rebuild_custom()
        self.apply()

    def rebuild_custom(self) -> None:
        """Make the My Commands tab again from the settings; no commands, no tab."""
        from fdcad.ui.command_tabs.tabs import build_panel

        tabs = self.tabs
        index = tabs.index_of(TAB_NAME)
        current = tabs.currentWidget()
        if index >= 0:
            old = tabs.widget(index)
            tabs.removeTab(index)
            if old is not None:
                old.deleteLater()
        self.panel = None
        commands = [c for c in self.settings.custom_commands if c in self.window.commands.actions]
        if not commands:
            return
        panel = build_panel(TAB_NAME, custom_groups(commands), self.window.commands.actions)
        at = index if index >= 0 else tabs.count()
        tabs.insertTab(at, panel, TAB_TITLE)
        self.panel = panel
        if current is not None and tabs.indexOf(current) >= 0:
            tabs.setCurrentWidget(current)

    # Hidden buttons and simple mode ------------------------------------------------------

    def hide_button(self, cid: str) -> None:
        """Hide a command's button on the built in tabs."""
        if cid and cid not in self.settings.hidden_buttons:
            self.settings.hidden_buttons = [*self.settings.hidden_buttons, cid]
            self.apply()

    def show_hidden(self) -> None:
        """Show every hidden button again."""
        self.settings.hidden_buttons = []
        self.apply()

    def set_simple(self, on: bool) -> None:
        """Turn simple mode on or off."""
        self.settings.simple_mode = on
        self.apply()
        self.window.status.setText(SIMPLE_ON if on else SIMPLE_OFF)

    def apply(self) -> None:
        """Show and hide tabs, buttons and empty groups for the current settings."""
        hidden = set(self.settings.hidden_buttons)
        simple = self.settings.simple_mode
        user_hidden = set(self.settings.hidden_command_tabs)
        tabs = self.tabs
        for i in range(tabs.count()):
            panel = tabs.widget(i)
            if not isinstance(panel, RibbonPanel):
                continue
            name = self._panel_name(panel)
            self._hook(panel)
            buttons = panel.buttons()
            for button in buttons:
                button.setVisible(shown(self.command_of(button), name, hidden, simple))
            for group in panel.findChildren(RibbonGroup):  # a group with no button hides
                mine = [b for b in buttons if group.isAncestorOf(b)]
                group.setVisible(any(not b.isHidden() for b in mine) or not mine)
            visible = name not in user_hidden and (not simple or name in SIMPLE_TABS)
            tabs.setTabVisible(i, visible)
        if not any(tabs.isTabVisible(i) for i in range(tabs.count())) and tabs.count():
            tabs.setTabVisible(0, True)

    def set_tab_shown(self, index: int, shown: bool) -> None:
        """A tab's tick box on the tab bar menu: remember the user's choice by name, so
        tabs that simple mode hides are never saved as hidden by the user."""
        widget = self.tabs.widget(index)
        if widget is None:
            return
        name = self._panel_name(widget)
        hidden = [n for n in self.settings.hidden_command_tabs if n != name]
        if not shown:
            visible = [i for i in range(self.tabs.count()) if self.tabs.isTabVisible(i)]
            if visible == [index]:
                return  # the last visible tab always stays
            hidden.append(name)
        self.settings.hidden_command_tabs = hidden
        self.apply()

    def add_tab_items(self, menu: QMenu) -> None:
        """Show Hidden Buttons and Simple Mode on the tab bar menu."""
        menu.addSeparator()
        show = menu.addAction(SHOW_HIDDEN, self.show_hidden)
        show.setEnabled(bool(self.settings.hidden_buttons))
        simple = menu.addAction(SIMPLE_MODE)
        simple.setObjectName("simple_mode")
        simple.setCheckable(True)
        simple.setChecked(self.settings.simple_mode)
        simple.toggled.connect(self.set_simple)


def install(window: MainWindow) -> TabCustomizer:
    """Add My Commands, hidden buttons and simple mode to the window's command tabs."""
    customizer = TabCustomizer(window)
    window.tab_customizer = customizer
    return customizer
