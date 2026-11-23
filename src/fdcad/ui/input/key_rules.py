"""Default keys against the Windows rules (TR380 item 5, D1003).

1. No Ctrl and Alt together: on many keyboards AltGr is Ctrl+Alt and types letters.
2. No Windows key: Windows keeps it for itself.
3. No Alt and a letter that opens a menu (the underlined menu letters).
4. One key, one command.

Plain text work on key strings such as "Ctrl+Shift+S", no Qt.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping


def menu_letters(labels: Iterable[str]) -> set[str]:
    """The underlined letters of menu titles such as "&File"."""
    out: set[str] = set()
    for label in labels:
        at = label.find("&")
        if 0 <= at < len(label) - 1 and label[at + 1] != "&":
            out.add(label[at + 1].upper())
    return out


def windows_problems(keys: Mapping[str, list[str]], menus: set[str]) -> list[str]:
    """Each broken rule as a sentence. ``keys`` maps a command id to its keys."""
    out: list[str] = []
    owner: dict[str, str] = {}
    for cid, sequences in keys.items():
        for key in sequences:
            parts = [p.strip().upper() for p in key.split("+") if p.strip()]
            mods, last = set(parts[:-1]), parts[-1] if parts else ""
            if "CTRL" in mods and "ALT" in mods:
                out.append(f"{cid}: {key} uses Ctrl and Alt together, which AltGr types.")
            if "META" in mods or "WIN" in mods:
                out.append(f"{cid}: {key} uses the Windows key.")
            if mods == {"ALT"} and last in menus:
                out.append(f"{cid}: {key} opens the menu underlined {last}.")
            seen = owner.setdefault(key.upper(), cid)
            if seen != cid:
                out.append(f"{cid}: {key} is also the key of {seen}.")
    return out
