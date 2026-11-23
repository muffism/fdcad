"""Mac Redo key (TR375, D767)."""

from __future__ import annotations

from collections import Counter

from fdcad.ui.input.commands import COMMANDS, ShortcutMap, normalize


def test_mac_redo_takes_the_standard_key() -> None:
    mac = ShortcutMap(mac=True)
    assert mac.keys("edit.redo") == ["Ctrl+Shift+Z", "Ctrl+Y"]  # Command+Shift+Z first
    assert mac.keys("view.previous") == ["Meta+Shift+Z"]  # Control+Shift+Z on a Mac
    assert mac.owners("Ctrl+Shift+Z") == ["edit.redo"]


def test_windows_and_linux_keys_stay() -> None:
    pc = ShortcutMap(mac=False)
    assert pc.keys("edit.redo") == ["Ctrl+Y"]
    assert pc.keys("view.previous") == ["Ctrl+Shift+Z"]


def test_no_default_key_is_shared_on_a_mac() -> None:
    mac = ShortcutMap(mac=True)
    used = Counter(normalize(k) for c in COMMANDS for k in mac.default(c.id))
    assert [k for k, n in used.items() if n > 1] == []
