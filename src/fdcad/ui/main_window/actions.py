"""Window actions built from the command list, with the user's shortcuts (SHORTCUTS.md)."""

from __future__ import annotations

import sys
from collections.abc import Callable

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMenu, QWidget

from fdcad.ui.input.commands import BY_ID, GestureMap, ShortcutMap, gesture_direction
from fdcad.ui.preferences.settings import Settings

#: How many commands the Recent Commands menu lists.
RECENT_COUNT = 5


class CommandActions:
    """One QAction per command id. Shortcuts come from the defaults plus the user's changes."""

    def __init__(self, owner: QWidget, settings: Settings) -> None:
        self.owner = owner
        self.settings = settings
        self.shortcuts = ShortcutMap(settings.shortcut_overrides, mac=sys.platform == "darwin")
        self.actions: dict[str, QAction] = {}
        self.last: str | None = None
        #: Repeatable commands run lately, newest first (Recent Commands menu, T9.1).
        self.recent: list[str] = []
        self._bar: QMenu | None = None  # the last shortcut bar shown

    def add(
        self,
        cid: str,
        slot: Callable[[], object],
        *,
        checkable: bool = False,
        repeatable: bool = False,
        scope: QWidget | None = None,
    ) -> QAction:
        """Create the action for ``cid``. ``scope`` limits its shortcut to that widget."""
        action = QAction(BY_ID[cid].label, self.owner)
        action.setCheckable(checkable)

        def run(_checked: bool = False) -> None:
            if repeatable:
                self.last = cid
                self.recent = [cid, *[c for c in self.recent if c != cid]][:RECENT_COUNT]
            slot()

        action.triggered.connect(run)
        holder = scope or self.owner
        holder.addAction(action)
        if scope is not None:
            action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.actions[cid] = action
        self._apply(cid)
        return action

    def adopt(self, cid: str, action: QAction) -> QAction:
        """Give an action made elsewhere (undo, redo) the shortcuts of ``cid``."""
        action.setText(BY_ID[cid].label)
        self.actions[cid] = action
        self._apply(cid)
        return action

    def _apply(self, cid: str) -> None:
        self.actions[cid].setShortcuts([QKeySequence(k) for k in self.shortcuts.keys(cid)])

    def reload(self) -> None:
        """Apply shortcuts again after the preferences changed."""
        self.shortcuts = ShortcutMap(self.settings.shortcut_overrides, mac=sys.platform == "darwin")
        for cid in self.actions:
            self._apply(cid)

    def trigger(self, cid: str) -> bool:
        """Run a command by id. Returns False when it does not exist or is disabled."""
        action = self.actions.get(cid)
        if action is None or not action.isEnabled():
            return False
        action.trigger()
        return True

    def trigger_key(self, key: str) -> bool:
        """Run the enabled command whose shortcut is ``key`` (TR354, D2020)."""
        for cid, action in self.actions.items():
            if key in self.shortcuts.keys(cid) and action.isEnabled():
                action.trigger()
                return True
        return False

    def repeat(self) -> bool:
        """Run the last repeatable command again (Enter or Z)."""
        return self.last is not None and self.trigger(self.last)

    def gesture(self, context: str, dx: float, dy: float) -> str | None:
        """Run the command for a mouse gesture. Returns its id, or None."""
        sectors = self.settings.gesture_directions
        mapping = GestureMap(self.settings.gestures, sectors)
        cid = mapping.command(context, gesture_direction(dx, dy, sectors))
        if cid is not None and self.trigger(cid):
            return cid
        return None

    def gesture_labels(self, context: str) -> tuple[dict[str, str], int]:
        """The gesture guide's commands for ``context``: {direction: label} and sectors."""
        sectors = self.settings.gesture_directions
        mapping = GestureMap(self.settings.gestures, sectors)
        labels: dict[str, str] = {}
        for direction in mapping.mapping.get(context, {}):
            cid = mapping.command(context, direction)
            if cid is not None:
                labels[direction] = BY_ID[cid].label
        return labels, sectors

    def shortcut_bar(self, context: str, pos: QPoint) -> QMenu:
        """Show the shortcut bar for a context at ``pos`` (screen pixels), with a search box."""
        from fdcad.ui.input.commands import search_words
        from fdcad.ui.main_window.shortcut_bar import ShortcutBar

        ids = self.settings.shortcut_bar.get(context, [])
        listed = [self.actions[c] for c in ids if c in self.actions]
        overrides = self.settings.search_words
        words = {id(a): search_words(c, overrides) for c, a in self.actions.items()}
        if self._bar is not None:
            self._bar.deleteLater()  # one shortcut bar at a time; old ones stayed (D637)
        menu = ShortcutBar(listed, list(self.actions.values()), self.owner, words)
        self._bar = menu
        if self.owner.isVisible():
            menu.popup(pos)
        return menu
