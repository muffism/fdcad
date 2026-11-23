"""Default keys follow the Windows rules (TR380 item 5, D1003)."""

from __future__ import annotations

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication

from fdcad.ui import strings
from fdcad.ui.input.commands import COMMANDS, ShortcutMap
from fdcad.ui.input.key_rules import menu_letters, windows_problems

_MENUS = [
    strings.MENU_FILE,
    strings.MENU_EDIT,
    strings.MENU_VIEW,
    strings.MENU_INSERT,
    strings.MENU_TOOLS,
    strings.MENU_HELP,
]


def _defaults(mac: bool) -> dict[str, list[str]]:
    shortcuts = ShortcutMap({}, mac=mac)
    return {c.id: list(shortcuts.keys(c.id)) for c in COMMANDS}


def test_the_rules_catch_each_case() -> None:
    letters = menu_letters(["&File", "&Edit", "Save && Close"])
    assert letters == {"F", "E"}
    found = windows_problems(
        {"a": ["Ctrl+Alt+S"], "b": ["Meta+D"], "c": ["Alt+F"], "d": ["Ctrl+S"], "e": ["Ctrl+S"]},
        letters,
    )
    assert len(found) == 4
    assert windows_problems({"a": ["Alt+C", "Ctrl+Shift+S"]}, letters) == []


def test_default_keys_break_no_windows_rule() -> None:
    assert windows_problems(_defaults(mac=False), menu_letters(_MENUS)) == []


def test_quit_and_force_rebuild_never_share_a_key(qapp: QApplication) -> None:
    quit_keys = {k.toString() for k in QKeySequence.keyBindings(QKeySequence.StandardKey.Quit)}
    for mac in (False, True):
        rebuild = set(ShortcutMap({}, mac=mac).keys("edit.force_rebuild"))
        assert not rebuild & quit_keys
