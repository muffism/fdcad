"""Saved camera views of a part (TUTORIAL_REVIEW_SPEC TR14.2, DECISIONS D690).

A saved view is a name and a camera: target point, view direction (eye to
target), up vector, eye distance and view scale. They are kept in the part file
under ``views`` (FDEF_SPEC 2 item 14), in the order they were saved. Pure
Python: the UI turns a camera into these numbers and back.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

Vec3 = tuple[float, float, float]
#: Longest view name.
MAX_NAME = 60


class SavedViewError(ValueError):
    """A saved view is damaged or a name cannot be used; the message says why."""


@dataclass(frozen=True)
class SavedView:
    """One named camera."""

    name: str
    center: Vec3
    direction: Vec3
    up: Vec3
    distance: float
    scale: float


def _vec(raw: Any, what: str) -> Vec3:
    if not isinstance(raw, list | tuple) or len(raw) != 3:
        raise SavedViewError(f"a saved view's {what} must be three numbers")
    try:
        x, y, z = (float(v) for v in raw)
    except (TypeError, ValueError) as exc:
        raise SavedViewError(f"a saved view's {what} must be three numbers") from exc
    if not all(math.isfinite(v) for v in (x, y, z)):
        raise SavedViewError(f"a saved view's {what} must be three numbers")
    return x, y, z


def _number(raw: Any, what: str) -> float:
    if isinstance(raw, bool) or not isinstance(raw, int | float) or not math.isfinite(raw):
        raise SavedViewError(f"a saved view's {what} must be a number")
    if raw <= 0:
        raise SavedViewError(f"a saved view's {what} must be above zero")
    return float(raw)


def view_from_json(raw: Any) -> SavedView:
    """Read one saved view. Raises SavedViewError when it is damaged."""
    if not isinstance(raw, dict) or not isinstance(raw.get("name"), str):
        raise SavedViewError("a saved view has no name")
    direction = _vec(raw.get("direction"), "direction")
    up = _vec(raw.get("up"), "up vector")
    if math.hypot(*direction) < 1e-9 or math.hypot(*up) < 1e-9:
        raise SavedViewError("a saved view's direction and up vector must not be zero")
    return SavedView(
        raw["name"],
        _vec(raw.get("center"), "center"),
        direction,
        up,
        _number(raw.get("distance"), "distance"),
        _number(raw.get("scale"), "scale"),
    )


def view_to_json(view: SavedView) -> dict[str, Any]:
    """One saved view as file data."""
    return {
        "name": view.name,
        "center": list(view.center),
        "direction": list(view.direction),
        "up": list(view.up),
        "distance": view.distance,
        "scale": view.scale,
    }


def names(views: list[dict[str, Any]]) -> list[str]:
    """The saved views' names, in order."""
    return [str(v.get("name", "")) for v in views]


def name_problem(views: list[dict[str, Any]], name: str, keep: str | None = None) -> str:
    """Why ``name`` cannot be used for a saved view, or "". ``keep`` is the view
    being renamed (it may keep its own name)."""
    clean = name.strip()
    if not clean:
        return "Type a name for the view."
    if len(clean) > MAX_NAME:
        return f"Use a name of {MAX_NAME} characters or less."
    taken = {n.casefold() for n in names(views) if n != keep}
    if clean.casefold() in taken:
        return f"A saved view is already called {clean}. Choose another name."
    return ""


def usable_names(views: list[dict[str, Any]], notes: list[str]) -> list[dict[str, Any]]:
    """The views read from a file, each with a name ``name_problem`` accepts: an
    empty, too long or repeated name (ignoring case) is changed, and each change adds
    a sentence to ``notes`` (audit D5 item 4, D2679)."""
    from fdcad.core.document.names import usable_name

    out: list[dict[str, Any]] = []
    taken: set[str] = set()
    for v in views:
        old = str(v.get("name", ""))
        new = usable_name(old, taken, MAX_NAME, "View")
        taken.add(new.casefold())
        if not old.strip():
            notes.append(f'A saved view with no name is now called "{new}".')
        elif new != old.strip():
            why = (
                f"names are at most {MAX_NAME} characters"
                if len(old.strip()) > MAX_NAME
                else "another saved view has that name"
            )
            notes.append(f'The saved view "{old.strip()}" is now called "{new}": {why}.')
        out.append({**v, "name": new} if new != old else v)
    return out


def save_view(views: list[dict[str, Any]], view: SavedView) -> list[dict[str, Any]]:
    """The views with ``view`` added, or replacing the one with its name (Update)."""
    data = view_to_json(view)
    out = [dict(v) for v in views]
    for i, v in enumerate(out):
        if v.get("name") == view.name:
            out[i] = data
            return out
    return [*out, data]


def rename_view(views: list[dict[str, Any]], old: str, new: str) -> list[dict[str, Any]]:
    """The views with ``old`` renamed to ``new``. Raises SavedViewError for a bad name."""
    problem = name_problem(views, new, keep=old)
    if problem:
        raise SavedViewError(problem)
    return [{**v, "name": new.strip()} if v.get("name") == old else dict(v) for v in views]


def delete_view(views: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    """The views without ``name``."""
    return [dict(v) for v in views if v.get("name") != name]


def find(views: list[dict[str, Any]], name: str) -> SavedView | None:
    """The saved view called ``name``, or None."""
    for v in views:
        if v.get("name") == name:
            return view_from_json(v)
    return None
