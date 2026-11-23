"""Shortcut, gesture and shortcut bar maps."""

from __future__ import annotations

from fdcad.ui.input.commands import (
    BY_ID,
    COMMANDS,
    DEFAULT_BAR,
    DEFAULT_GESTURES,
    GestureMap,
    ShortcutMap,
    gesture_direction,
    normalize,
)


def test_defaults_follow_shortcuts_md() -> None:
    m = ShortcutMap()
    assert m.keys("view.normal_to") == ["Ctrl+8", "N"]
    assert m.keys("sketch.line") == ["L"]
    assert m.keys("edit.redo") == ["Ctrl+Y"]
    assert m.keys("edit.force_rebuild") == ["Ctrl+Q"]


def test_mac_keeps_control_where_cmd_is_reserved() -> None:
    m = ShortcutMap(mac=True)
    assert m.keys("edit.force_rebuild") == ["Meta+Q"]
    assert "Ctrl+Meta+F" in m.keys("ui.fullscreen")
    reserved = {"ctrl+q", "ctrl+h", "ctrl+m", "ctrl+space", "ctrl+tab", "ctrl+shift+tab"}
    for c in COMMANDS:
        assert not {normalize(k) for k in m.keys(c.id)} & reserved, c.id


def test_no_default_conflicts() -> None:
    for mac in (False, True):
        m = ShortcutMap(mac=mac)
        seen: dict[str, str] = {}
        for c in COMMANDS:
            for k in m.keys(c.id):
                assert normalize(k) not in seen, (k, c.id, seen.get(normalize(k)))
                seen[normalize(k)] = c.id


def test_setting_a_used_key_moves_it() -> None:
    m = ShortcutMap()
    lost = m.set("view.wireframe", ["L"])
    assert lost == {"sketch.line": "L"}
    assert m.keys("sketch.line") == []
    assert m.owners("l") == ["view.wireframe"]
    m.set("view.wireframe", ["Shift+W"])
    assert "view.wireframe" not in m.overrides  # back to its default
    m.reset()
    assert m.keys("sketch.line") == ["L"]


def test_gesture_directions() -> None:
    assert gesture_direction(5, 5) is None
    assert gesture_direction(0, -80) == "up"
    assert gesture_direction(-80, 3) == "left"
    assert gesture_direction(60, 60, sectors=8) == "down_right"
    g = GestureMap()
    assert g.command("part", "up") == "view.top"
    assert g.command("sketch", "left") == "sketch.line"
    assert g.command("sketch", None) is None


def test_defaults_name_real_commands() -> None:
    for context in DEFAULT_GESTURES.values():
        assert all(cid in BY_ID for cid in context.values())
    for items in DEFAULT_BAR.values():
        assert all(cid in BY_ID for cid in items)
