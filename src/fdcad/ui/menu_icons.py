"""Icons for the right click menus (UI review item P4, D2703).

An entry of a right click menu shows the icon its command has in the menu bar,
the command tabs and the context toolbar, so one command has one picture
wherever it is offered. An entry whose command has no icon shows none. A menu
row keeps its icon column either way (``themes.app_style``), so the text of
every row starts on one line.

No icon is drawn for this: every name below is an icon that was already in
``icons/NAMES.md``. The icon of an entry is found in this order:

1. ``KEYS``: the entry's key (``QAction.data()`` in the view and sketch menus).
2. A key that is an icon name itself (``edit.appearance``), a sketch tool
   (``tool.line`` is ``sketch.line``) or a relation (``relation.parallel``).
3. ``LABELS``: an entry worded differently from its command.
4. The entry's label, when exactly one command with an icon has that label
   (Delete, Zoom to Fit, Rebuild).

``apply`` is called where the menus add their own entries, never on rows that
show a user's name (a feature, a saved view), so a part's names cannot pick an
icon by accident.
"""

from __future__ import annotations

from functools import cache

from PySide6.QtGui import QAction

from fdcad.ui import icons
from fdcad.ui.input.commands import COMMANDS

#: Key of a view or sketch menu entry to the icon of its command.
KEYS: dict[str, str] = {
    "zoom_fit": "view.fit",
    "previous_view": "view.previous",
    "normal_to": "view.normal_to",
    "sketch": "sketch.sketch",
    "exit_sketch": "sketch.exit",
    "discard": "sketch.discard",
    "select": "sketch.select",
    "dimension": "sketch.dimension",
    "construction": "sketch.construction",
    "delete": "edit.delete",
    "appearance": "edit.appearance",
    "hide": "context.hide",
    "ok": "corner.ok",
    "cancel": "corner.cancel",
    "reverse": "ui.reverse_direction",
    "fix": "relation.fixed",
    "cut_away": "sketch.cut_away",
}

#: Label of an entry to the icon of its command, where the words differ from the
#: command's own name or the command is offered by the context toolbar only.
LABELS: dict[str, str] = {
    "Edit Feature": "context.edit",
    "Edit Sketch": "context.edit_sketch",
    "Hide": "context.hide",
    "Show": "context.show",
    "Hide Sketch": "context.hide",
    "Show Sketch": "context.show",
    "Hide Body": "context.hide",
    "Show Body": "context.show",
    "Sketch": "sketch.sketch",
    "Edit Material": "tools.material",
}

#: Key prefixes that name an icon family: ``tool.line`` shows ``sketch.line``.
PREFIXES: dict[str, str] = {"tool.": "sketch.", "relation.": "relation.", "style.": "view."}


def _plain(label: str) -> str:
    """A label without its mnemonic mark and trailing dots."""
    return label.replace("&", "").rstrip(".").strip()


@cache
def _listed() -> frozenset[str]:
    return frozenset(icons.listed_names())


@cache
def _by_label() -> dict[str, str]:
    """Label to command id, for labels that exactly one command with an icon has."""
    found: dict[str, list[str]] = {}
    listed = _listed()
    for command in COMMANDS:
        if command.id in listed:
            found.setdefault(command.label, []).append(command.id)
    return {label: ids[0] for label, ids in found.items() if len(ids) == 1}


def icon_name(key: str = "", label: str = "") -> str | None:
    """The icon name for a right click entry with this key and label, or None when
    its command has no icon."""
    listed = _listed()
    if key:
        if key in KEYS:
            return KEYS[key]
        if key in listed and "." in key:
            return key
        for prefix, family in PREFIXES.items():
            name = family + key.removeprefix(prefix)
            if key.startswith(prefix) and name in listed:
                return name
    plain = _plain(label)
    if plain in LABELS:
        return LABELS[plain]
    return _by_label().get(plain)


def apply(action: QAction, key: str = "", label: str | None = None) -> QAction:
    """Give ``action`` the icon of its command, if it has one and shows none yet."""
    if action.icon().isNull():
        name = icon_name(key, action.text() if label is None else label)
        if name is not None:
            action.setIcon(icons.icon(name))
    return action
