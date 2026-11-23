"""Named display states (TUTORIAL_REVIEW_SPEC_2 TR88, DECISIONS D1608).

A display state is a name and a copy of the part's body display: which bodies are
hidden, their colours, which are see through, and each body's display mode and
transparency (TR216). They live in ``appearance.display_states``:

    {"states": [{"name": "...", "values": {<appearance key>: <value>}}],
     "links": {<configuration name>: <state name>}}

A configuration linked to a state applies it when it becomes active. Pure Python.
"""

from __future__ import annotations

import copy
from typing import Any

from fdcad.core.document.model import Document

KEY = "display_states"
#: The appearance keys a display state holds.
STATE_KEYS = ("hidden_bodies", "see_through_bodies", "bodies", "body_display")
MAX_NAME = 60


class DisplayStateError(ValueError):
    """A display state name cannot be used; the message says what to do."""


def _block(doc: Document) -> dict[str, Any]:
    raw = doc.appearance.get(KEY)
    if not isinstance(raw, dict):
        return {"states": [], "links": {}}
    states = [
        s
        for s in raw.get("states", [])
        if isinstance(s, dict)
        and isinstance(s.get("name"), str)
        and isinstance(s.get("values"), dict)
    ]
    links = {
        k: v
        for k, v in (raw.get("links") or {}).items()
        if isinstance(k, str) and isinstance(v, str)
    }
    return {"states": states, "links": links}


def _store(doc: Document, block: dict[str, Any]) -> None:
    if block["states"] or block["links"]:
        doc.appearance[KEY] = block
    else:
        doc.appearance.pop(KEY, None)


def names(doc: Document) -> list[str]:
    """The display states' names, in order."""
    return [s["name"] for s in _block(doc)["states"]]


def capture(doc: Document) -> dict[str, Any]:
    """The part's body display now, as the values of a state."""
    return {k: copy.deepcopy(doc.appearance[k]) for k in STATE_KEYS if k in doc.appearance}


def check_name(doc: Document, name: str, keep: str | None = None) -> str:
    """A cleaned up name. Raises DisplayStateError when it cannot be used."""
    clean = " ".join(name.split())
    if not clean:
        raise DisplayStateError("Type a name for the display state.")
    if len(clean) > MAX_NAME:
        raise DisplayStateError(f"Use a name of {MAX_NAME} characters or less.")
    if clean != keep and clean.casefold() in {n.casefold() for n in names(doc)}:
        raise DisplayStateError(f"A display state is already called {clean}. Choose another name.")
    return clean


def save(doc: Document, name: str) -> str:
    """Save the body display now under ``name`` (replacing a state of that name)."""
    block = _block(doc)
    clean = " ".join(name.split())
    values = capture(doc)
    for state in block["states"]:
        if state["name"] == clean:
            state["values"] = values
            _store(doc, block)
            return clean
    clean = check_name(doc, name)
    block["states"].append({"name": clean, "values": values})
    _store(doc, block)
    return clean


def apply(doc: Document, name: str) -> bool:
    """Show state ``name``: its keys replace the body display. False when unknown."""
    state = next((s for s in _block(doc)["states"] if s["name"] == name), None)
    if state is None:
        return False
    for key in STATE_KEYS:
        if key in state["values"]:
            doc.appearance[key] = copy.deepcopy(state["values"][key])
        else:
            doc.appearance.pop(key, None)
    return True


def delete(doc: Document, name: str) -> None:
    """Remove state ``name`` and the links to it."""
    block = _block(doc)
    block["states"] = [s for s in block["states"] if s["name"] != name]
    block["links"] = {c: s for c, s in block["links"].items() if s != name}
    _store(doc, block)


def link(doc: Document, configuration: str, state: str | None) -> None:
    """Link a configuration to a state, or unlink it with None."""
    block = _block(doc)
    if state is None:
        block["links"].pop(configuration, None)
    elif state in names(doc):
        block["links"][configuration] = state
    _store(doc, block)


def linked(doc: Document, configuration: str) -> str | None:
    """The state linked to a configuration, or None."""
    found = _block(doc)["links"].get(configuration)
    return found if isinstance(found, str) else None


def apply_linked(doc: Document, configuration: str) -> bool:
    """Apply the state linked to ``configuration``, if any."""
    state = linked(doc, configuration)
    return apply(doc, state) if state is not None else False
