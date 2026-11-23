"""First time hints in the property panel (TR291 item 1, DECISIONS D2018).

The first time each feature type's panel opens, a one line hint (the command's
tooltip text) shows above the panel's groups with a Show Me link to the guide and
a link that turns hints off. Seen types and the switch are kept in the app
settings.
"""

from __future__ import annotations

from typing import Any

from fdcad.ui import strings_help as text

SEEN_KEY = "help/hints_seen"
OFF_KEY = "help/hints_off"


def _seen(store: Any) -> list[str]:
    raw = store.value(SEEN_KEY, [])
    if isinstance(raw, str):
        return [raw] if raw else []
    return [str(x) for x in raw or []]


def should_show(store: Any, kind: str) -> bool:
    """True when hints are on and this feature type has not shown its hint yet."""
    if str(store.value(OFF_KEY, "false")).lower() == "true":
        return False
    return kind not in _seen(store)


def mark_seen(store: Any, kind: str) -> None:
    """Remember that ``kind`` showed its hint."""
    seen = _seen(store)
    if kind not in seen:
        store.setValue(SEEN_KEY, [*seen, kind])


def turn_off(store: Any) -> None:
    """No more hints."""
    store.setValue(OFF_KEY, "true")


def reset(store: Any) -> None:
    """Hints on again, and every tool shows its hint once more."""
    store.setValue(OFF_KEY, "false")
    store.setValue(SEEN_KEY, [])


def hint_for(kind: str) -> str:
    """The hint line with its links, or "" when the type has no tooltip text."""
    from html import escape

    from fdcad.ui import strings

    line = strings.TOOLTIP_TEXT.get(f"feature.{kind}", "")
    if not line:
        return ""
    return (
        f"{escape(line)} <a href='show'>{text.HINT_SHOW_ME}</a> · "
        f"<a href='off'>{text.HINT_TURN_OFF}</a>"
    )
