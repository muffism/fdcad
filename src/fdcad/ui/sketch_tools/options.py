"""Sketch preferences an open sketch follows (TOOL_SPEC T11, T1.2.8, T1.3.3).

Pure data, no Qt. ``Settings.sketch_options`` stores them; the main window
hands a copy to every sketch canvas, also to one that is already open.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OverDefine(Enum):
    """What happens when a new dimension would over define the sketch (T11.5)."""

    ASK = "ask"
    REFERENCE = "reference"


@dataclass(frozen=True)
class SketchOptions:
    """The Sketch page of the preferences. Every switch is on except the grid, value
    input, keep proportions, the two exit switches and midpoint picks."""

    normal_to_on_open: bool = True
    show_centres: bool = True
    end_point_dots: bool = True
    snapping: bool = True
    model_snaps: bool = True
    auto_relations: bool = True
    #: Kinds of automatic relation (TR231, D1309): each can be turned off on its own.
    auto_horizontal: bool = True
    auto_vertical: bool = True
    auto_parallel: bool = True
    auto_perpendicular: bool = True
    auto_tangent: bool = True
    auto_equal: bool = True
    auto_midpoint: bool = True
    auto_coincident: bool = True
    show_grid: bool = False
    #: Open the size box at the cursor as soon as a shape starts (T11.6, D513).
    value_input: bool = False
    #: The first dimension of an unsized sketch scales the whole sketch (TR119, D938).
    keep_proportions: bool = False
    #: Dragging holds the geometry of dimensions changed since the sketch opened in
    #: place (TR238, D1706). Off by default.
    lock_changed_dimensions: bool = False
    #: Dragging dimensioned geometry gives its driving dimensions the new sizes
    #: (TR112 item 2, D1716). Off by default: TOOL_SPEC T2 keeps dimensions.
    drag_changes_dimensions: bool = False
    #: Leaving a sketch (TR120, D941): double click on empty space, or Esc with no tool
    #: and nothing picked, exits the sketch. Both off by default.
    double_click_exit: bool = False
    escape_exit: bool = False
    #: Smart Dimension picks (TR418, D953): end points and centres where their snap
    #: shows (on, as before), and midpoints of lines, arcs and part edges (off, since a
    #: click on a line's middle picks the line for its length).
    dimension_ends: bool = True
    dimension_middles: bool = False
    dimension_centres: bool = True
    over_define: OverDefine = OverDefine.ASK
    #: Snap to Grid (TR102, D860): "off", "shown" (while the grid shows) or "always".
    grid_snap: str = "off"
    #: Steps while Alt is held during drawing: length in mm and angle in degrees.
    length_step: float = 1.0
    angle_step: float = 15.0
    #: The grid (TR238, D1014): "square" lines, or "polar" rings round the origin at
    #: the grid spacing with spokes every ``polar_angle`` degrees.
    grid_kind: str = "square"
    polar_angle: float = 15.0


#: Kinds of automatic relation with their own switch (TR231, D1309).
AUTO_KINDS = (
    "horizontal",
    "vertical",
    "parallel",
    "perpendicular",
    "tangent",
    "equal",
    "midpoint",
    "coincident",
)

#: Keys of the boolean options, in the order the preferences page lists them.
SWITCHES = (
    "normal_to_on_open",
    "show_centres",
    "end_point_dots",
    "snapping",
    "model_snaps",
    "auto_relations",
    *(f"auto_{kind}" for kind in AUTO_KINDS),
    "show_grid",
    "value_input",
    "keep_proportions",
    "lock_changed_dimensions",
    "drag_changes_dimensions",
    "double_click_exit",
    "escape_exit",
    "dimension_ends",
    "dimension_middles",
    "dimension_centres",
)
