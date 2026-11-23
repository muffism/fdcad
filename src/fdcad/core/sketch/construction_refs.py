"""Construction geometry of a closed sketch, shown in the part and offered as
references to later sketches and features (TUTORIAL_REVIEW_SPEC_2 TR339, D1703).

The tick is stored in the sketch's data as ``show_construction: true`` and is left
out when off. While it is off, the part shows no construction curves of the sketch.
"""

from __future__ import annotations

from typing import Any

from fdcad.core.sketch.model import Point, Sketch

#: The sketch data key of the tick.
KEY = "show_construction"


def shows_construction(data: dict[str, Any]) -> bool:
    """True when the sketch with ``data`` shows its construction geometry in the part."""
    return data.get(KEY) is True


def set_shows_construction(data: dict[str, Any], on: bool) -> None:
    """Turn the tick on or off in sketch ``data``."""
    if on:
        data[KEY] = True
    else:
        data.pop(KEY, None)


def reference_points(sketch: Sketch, data: dict[str, Any]) -> list[str]:
    """Point ids a later feature may pick from this sketch: its normal points, and its
    construction points too when the tick is on."""
    on = shows_construction(data)
    return [
        eid
        for eid, e in sketch.entities.items()
        if isinstance(e, Point) and (on or not e.construction)
    ]
