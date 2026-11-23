"""Select Through Faces (TR64 item 4, D1800): pick an edge hidden behind faces.

While a Fillet or Chamfer panel has Select Through Faces ticked, a click in the
view takes the nearest edge under the cursor even when a face lies in front of
it. The view lists everything under the cursor nearest first; this module picks
the first edge of that list.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def first_edge(shapes: Iterable[Any]) -> Any | None:
    """The first edge in ``shapes`` (nearest first), or None when there is none."""
    from OCP.TopAbs import TopAbs_EDGE

    for shape in shapes:
        if shape is not None and not shape.IsNull() and shape.ShapeType() == TopAbs_EDGE:
            return shape
    return None


def view_of(widget: Any) -> Any | None:
    """The 3D view that ``widget`` (a property panel) works with, or None (also when
    the panel or window is already deleted)."""
    from shiboken6 import isValid

    if widget is None or not isValid(widget):
        return None
    win = widget.window()
    tabs = getattr(win, "tabs", None)
    tab = tabs.currentWidget() if tabs is not None else None
    view = getattr(tab, "viewport", None)
    return view if hasattr(view, "pick_through") else None


def set_pick_through(widget: Any, on: bool) -> bool:
    """Turn Select Through Faces on or off in the view of ``widget``; True when set."""
    view = view_of(widget)
    if view is None:
        return False
    view.pick_through = on
    return True
