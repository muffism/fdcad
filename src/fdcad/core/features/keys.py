"""Standard key sizes for keyseats and keyways (TUTORIAL_REVIEW_SPEC_2 TR248, DECISIONS D871).

Compiled from the published standards:

- ``metric``: parallel keys (ISO/R 773, DIN 6885 form A): by shaft diameter, the key
  width and the keyseat depth in the shaft (t1) and the keyway depth in the hub (t2).
- ``inch``: square keys (ANSI B17.1): by shaft diameter, the key width; the key is as
  tall as it is wide, half in the shaft and half in the hub.
- ``woodruff``: half moon keys (ANSI B17.2): width, key diameter and height of each
  key. FDCAD picks the widest key no wider than a quarter of the shaft, then the
  largest key diameter no larger than the shaft. The shaft seat is the key's circle
  sunk so the key stands half its width proud; the hub keyway is half the width deep.

``rule`` keeps FDCAD's own rule from D841: D / 4 wide and D / 8 deep. All values in mm.
No Qt.
"""

from __future__ import annotations

from dataclasses import dataclass

INCH = 25.4
STANDARDS = ("rule", "metric", "inch", "woodruff")

#: Metric parallel keys: (shaft over, shaft up to, width, shaft depth t1, hub depth t2).
METRIC: tuple[tuple[float, float, float, float, float], ...] = (
    (6, 8, 2, 1.2, 1.0),
    (8, 10, 3, 1.8, 1.4),
    (10, 12, 4, 2.5, 1.8),
    (12, 17, 5, 3.0, 2.3),
    (17, 22, 6, 3.5, 2.8),
    (22, 30, 8, 4.0, 3.3),
    (30, 38, 10, 5.0, 3.3),
    (38, 44, 12, 5.0, 3.3),
    (44, 50, 14, 5.5, 3.8),
    (50, 58, 16, 6.0, 4.3),
    (58, 65, 18, 7.0, 4.4),
    (65, 75, 20, 7.5, 4.9),
    (75, 85, 22, 9.0, 5.4),
    (85, 95, 25, 9.0, 5.4),
    (95, 110, 28, 10.0, 6.4),
    (110, 130, 32, 11.0, 7.4),
)
#: Inch square keys: (shaft over, shaft up to, key width), in inches.
INCH_SQUARE: tuple[tuple[float, float, float], ...] = (
    (5 / 16, 7 / 16, 3 / 32),
    (7 / 16, 9 / 16, 1 / 8),
    (9 / 16, 7 / 8, 3 / 16),
    (7 / 8, 5 / 4, 1 / 4),
    (5 / 4, 11 / 8, 5 / 16),
    (11 / 8, 7 / 4, 3 / 8),
    (7 / 4, 9 / 4, 1 / 2),
    (9 / 4, 11 / 4, 5 / 8),
    (11 / 4, 13 / 4, 3 / 4),
    (13 / 4, 15 / 4, 7 / 8),
    (15 / 4, 9 / 2, 1.0),
)
#: Half moon keys: name to (width, key diameter, height), in inches.
WOODRUFF: dict[str, tuple[float, float, float]] = {
    "204": (1 / 16, 1 / 2, 0.203),
    "304": (3 / 32, 1 / 2, 0.203),
    "305": (3 / 32, 5 / 8, 0.250),
    "404": (1 / 8, 1 / 2, 0.203),
    "405": (1 / 8, 5 / 8, 0.250),
    "406": (1 / 8, 3 / 4, 0.313),
    "505": (5 / 32, 5 / 8, 0.250),
    "506": (5 / 32, 3 / 4, 0.313),
    "507": (5 / 32, 7 / 8, 0.375),
    "606": (3 / 16, 3 / 4, 0.313),
    "607": (3 / 16, 7 / 8, 0.375),
    "608": (3 / 16, 1.0, 0.438),
    "807": (1 / 4, 7 / 8, 0.375),
    "808": (1 / 4, 1.0, 0.438),
    "809": (1 / 4, 9 / 8, 0.484),
}


class KeySizeError(ValueError):
    """No standard key fits the diameter; the message says what to do."""


@dataclass(frozen=True)
class Key:
    """A key's slot sizes in mm. ``seat_diameter`` is set for a half moon key."""

    name: str
    width: float
    shaft_depth: float
    hub_depth: float
    seat_diameter: float = 0.0


def key_for(standard: str, diameter: float) -> Key:
    """The key for a shaft (or bore) of ``diameter`` mm under ``standard``."""
    if standard == "rule":
        return Key("D/4", diameter / 4, diameter / 8, diameter / 8)
    if standard == "metric":
        for low, high, width, t1, t2 in METRIC:
            if low < diameter <= high + 1e-9:
                return Key(f"{width:g} mm", float(width), t1, t2)
        raise KeySizeError(
            f"No metric parallel key fits a {diameter:.4g} mm shaft (6 to 130 mm). "
            "Choose the FDCAD rule instead."
        )
    inches = diameter / INCH
    if standard == "inch":
        for low, high, width in INCH_SQUARE:
            if low < inches <= high + 1e-9:
                w = width * INCH
                return Key(f"{width:g} in square", w, w / 2, w / 2)
        raise KeySizeError(
            f"No inch square key fits a {diameter:.4g} mm shaft (5/16 to 4 1/2 in). "
            "Choose the FDCAD rule instead."
        )
    if standard == "woodruff":
        fits = [
            (w, d, name)
            for name, (w, d, _h) in WOODRUFF.items()
            if w <= inches / 4 + 1e-9 and d <= inches + 1e-9
        ]
        if not fits:
            raise KeySizeError(
                f"No half moon key fits a {diameter:.4g} mm shaft (1/4 in or more). "
                "Choose the FDCAD rule instead."
            )
        widest = max(w for w, _d, _n in fits)
        w, d, name = max((f for f in fits if f[0] == widest), key=lambda f: f[1])
        height = WOODRUFF[name][2]
        width = w * INCH
        return Key(name, width, (height - w / 2) * INCH, width / 2, d * INCH)
    raise KeySizeError(f"Unknown key standard '{standard}'. Choose one in the panel.")
