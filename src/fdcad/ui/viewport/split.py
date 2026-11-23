"""Split View layouts (TUTORIAL_REVIEW_SPEC TR16, D699). Pure Python, no Qt.

A layout places the main view and its extra panes in a grid and says which
standard view each extra pane starts with. The main view is always the first
cell (top left), so it is never moved between windows.
"""

from __future__ import annotations

#: Layout name to the grid cell (row, column) of each view, main view first.
LAYOUTS: dict[str, list[tuple[int, int]]] = {
    "one": [(0, 0)],
    "side": [(0, 0), (0, 1)],
    "stacked": [(0, 0), (1, 0)],
    "four": [(0, 0), (0, 1), (1, 0), (1, 1)],
}
#: The standard view of each view when a layout starts (None: the main view keeps its
#: camera). Four views start as Front, Top, Right and Isometric (TR16.1).
START_VIEWS: dict[str, list[str | None]] = {
    "one": [None],
    "side": [None, "iso"],
    "stacked": [None, "iso"],
    "four": ["front", "top", "right", "iso"],
}


def cells(layout: str) -> list[tuple[int, int]]:
    """Grid cells of a layout. Raises KeyError for an unknown layout."""
    return LAYOUTS[layout]


def start_views(layout: str) -> list[str | None]:
    """The standard view each view of the layout starts with."""
    return START_VIEWS[layout]
