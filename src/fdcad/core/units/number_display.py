"""How shown numbers look (TR350, D949).

Display only: values in fields, files and formulas never change. A style has

- a rounding rule for the last shown place: half away from zero, half to even, or
  truncate (toward zero);
- a decimal separator, a point or a comma (the UI turns "follow the system" into
  one of these);
- for inch values, an optional fraction display to a chosen denominator (2 to 64),
  such as 1 3/4. A value that does not land on that denominator closely enough
  keeps its decimals, so a fraction never hides a difference.

The app sets the style once at start and after Preferences; tests set and reset it.
No Qt.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, InvalidOperation

ROUNDING = ("half_away", "half_even", "truncate")
SEPARATORS = (".", ",")
DENOMINATORS = (0, 2, 4, 8, 16, 32, 64)  # 0: fractions off

_MODES = {"half_away": ROUND_HALF_UP, "half_even": ROUND_HALF_EVEN, "truncate": ROUND_DOWN}


@dataclass(frozen=True)
class NumberStyle:
    """One way of showing numbers."""

    rounding: str = "half_away"
    separator: str = "."
    fraction: int = 0  # inch fraction denominator; 0 shows decimals

    def clean(self) -> NumberStyle:
        """The same style with any unknown value put back to its default."""
        return NumberStyle(
            self.rounding if self.rounding in ROUNDING else "half_away",
            self.separator if self.separator in SEPARATORS else ".",
            self.fraction if self.fraction in DENOMINATORS else 0,
        )


_style = NumberStyle()


def set_style(style: NumberStyle | None) -> None:
    """Use ``style`` for every shown number from now on (None: the default)."""
    global _style
    _style = (style or NumberStyle()).clean()


def style() -> NumberStyle:
    """The style in use."""
    return _style


def fixed(value: float, places: int, use: NumberStyle | None = None) -> str:
    """``value`` with ``places`` decimals, rounded and separated as the style says."""
    s = use or _style
    places = max(0, int(places))
    if not math.isfinite(value):
        return f"{value}"
    try:
        exact = Decimal(repr(float(value)))  # the number as typed, not its binary tail
        text = f"{exact.quantize(Decimal(1).scaleb(-places), rounding=_MODES[s.rounding]):f}"
    except (InvalidOperation, KeyError):
        text = f"{value:.{places}f}"
    if text.startswith("-") and set(text[1:]) <= set("0."):
        text = text[1:]  # no minus sign on a shown zero
    return text.replace(".", s.separator) if s.separator != "." else text


def fraction_text(inches: float, denominator: int, places: int = 3) -> str | None:
    """``inches`` as a whole number and a reduced fraction (1 3/4), or None when the
    value is not within half of the last shown decimal place of a 1/``denominator``
    step, so the fraction would hide a difference."""
    if denominator not in DENOMINATORS or denominator == 0 or not math.isfinite(inches):
        return None
    steps = round(abs(inches) * denominator)
    if abs(abs(inches) * denominator - steps) / denominator > 0.5 * 10 ** (-places):
        return None
    whole, rest = divmod(steps, denominator)
    top, bottom = rest, denominator
    while top and top % 2 == 0 and bottom % 2 == 0:
        top, bottom = top // 2, bottom // 2
    sign = "-" if inches < 0 and steps else ""
    if top == 0:
        return f"{sign}{whole}"
    if whole == 0:
        return f"{sign}{top}/{bottom}"
    return f"{sign}{whole} {top}/{bottom}"


def length(value: float, places: int, inch: bool, use: NumberStyle | None = None) -> str:
    """A shown length already in the shown unit: a fraction for inches when the style
    asks for one and it fits, else ``fixed``."""
    s = use or _style
    if inch and s.fraction:
        text = fraction_text(value, s.fraction, places)
        if text is not None:
            return text
    return fixed(value, places, s)
