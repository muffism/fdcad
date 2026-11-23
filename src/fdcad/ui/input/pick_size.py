"""How close the cursor must be to pick (TR313, D917).

One preference scales the 3D view's pick distance and the sketch editor's: Small,
Normal (the old sizes), Large or Extra Large. Kept here as a number the views read
when they measure, set from the preferences at start and on OK.
"""

from __future__ import annotations

#: Choice key to scale; "normal" is 1 (the 3D view 6 pixels, a sketch 10 pixels).
SIZES = {"small": 0.6, "normal": 1.0, "large": 1.5, "extra_large": 2.0}

_scale = 1.0


def scale() -> float:
    """The current pick size scale."""
    return _scale


def set_size(key: str) -> None:
    """Use the scale of ``key`` (unknown keys mean Normal)."""
    global _scale
    _scale = SIZES.get(key, 1.0)
