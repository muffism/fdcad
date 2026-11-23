"""More screw heads, thread series and drill names for the Hole Tool (TR253, D786).

Compiled from the published standards (CLAUDE.md 7.6), nominal maximum values:

- Counterbore heads, metric: socket head (ISO 4762, in ``hole_data``), button head
  (ISO 7380-1), low head socket (DIN 7984), pan head (ISO 7045), cheese head
  (ISO 1207), and a washer seat: a socket head on a plain washer (ISO 7089).
- Counterbore heads, inch: socket head (ASME B18.3, in ``hole_data``), button head
  and low head socket (ASME B18.3), pan head and fillister (cheese) head (ASME
  B18.6.3), and a washer seat on a type A plain washer, narrow (ASME B18.21.1).
- Countersunk heads: the socket form (ISO 10642, 90 degrees; ASME B18.3, 82
  degrees, in ``hole_data``) and the cross recessed form (ISO 7046-1, 90 degrees,
  theoretical head diameter). Inch has one form.
- Metric fine pitches (ISO 261, 262) and the larger coarse sizes M30 to M48 (ISO
  261, 273, 4762, 4032). Their countersunk head is about twice the diameter (ISO
  10642 stops at M20).
- Inch fine (UNF) and extra fine (UNEF) series and the smallest gauge sizes from
  ASME B1.1, with the 75 percent thread tap drills.
- Drill names: number drills #1 to #80, letter drills A to Z and fractional drills
  in 1/64 inch steps up to 2 inches, shown beside a diameter that matches one.

Every length is in millimetres.
"""

from __future__ import annotations

INCH = 25.4

#: Counterbore head forms, with the socket head first (the hole's default).
CBORE_HEADS = ("socket", "button", "low_head", "pan", "cheese", "washer")
#: Countersunk head forms; ``recessed`` is metric only.
CSK_HEADS = ("flat", "recessed")


def base_of(name: str) -> str:
    """The nominal size of a thread name: "M10x1.25" gives "M10", "#10-32" gives "#10"."""
    if name.startswith("M"):
        return name.split("x")[0]
    return name.split("-")[0]


def _mm(rows: dict[str, tuple[float, float]]) -> dict[str, tuple[float, float]]:
    return rows


def _inch(rows: dict[str, tuple[float, float]]) -> dict[str, tuple[float, float]]:
    return {k: (a * INCH, b * INCH) for k, (a, b) in rows.items()}


#: Head diameter and height of each head form, by nominal size.
HEADS: dict[str, dict[str, tuple[float, float]]] = {
    "button": {
        **_mm(
            {
                "M3": (5.7, 1.65),
                "M4": (7.6, 2.2),
                "M5": (9.5, 2.75),
                "M6": (10.5, 3.3),
                "M8": (14.0, 4.4),
                "M10": (17.5, 5.5),
                "M12": (21.0, 6.6),
                "M16": (28.0, 8.8),
            }
        ),
        **_inch(
            {
                "#0": (0.114, 0.032),
                "#1": (0.139, 0.039),
                "#2": (0.164, 0.046),
                "#3": (0.188, 0.052),
                "#4": (0.213, 0.059),
                "#5": (0.238, 0.066),
                "#6": (0.262, 0.073),
                "#8": (0.312, 0.087),
                "#10": (0.361, 0.101),
                "1/4": (0.437, 0.132),
                "5/16": (0.547, 0.166),
                "3/8": (0.656, 0.199),
                "1/2": (0.875, 0.265),
                "5/8": (1.000, 0.331),
            }
        ),
    },
    "low_head": {
        **_mm(
            {
                "M3": (5.5, 2.0),
                "M4": (7.0, 2.8),
                "M5": (8.5, 3.5),
                "M6": (10.0, 4.0),
                "M8": (13.0, 5.0),
                "M10": (16.0, 6.0),
                "M12": (18.0, 7.0),
                "M14": (21.0, 8.0),
                "M16": (24.0, 9.0),
                "M20": (30.0, 11.0),
                "M24": (36.0, 13.0),
            }
        ),
        **_inch(
            {
                "#8": (0.270, 0.106),
                "#10": (0.312, 0.118),
                "1/4": (0.375, 0.157),
                "5/16": (0.469, 0.197),
                "3/8": (0.562, 0.236),
                "1/2": (0.750, 0.315),
                "5/8": (0.938, 0.394),
            }
        ),
    },
    "pan": {
        **_mm(
            {
                "M1.6": (3.2, 1.3),
                "M2": (4.0, 1.6),
                "M2.5": (5.0, 2.1),
                "M3": (5.6, 2.4),
                "M4": (8.0, 3.1),
                "M5": (9.5, 3.7),
                "M6": (12.0, 4.6),
                "M8": (16.0, 6.0),
                "M10": (20.0, 7.5),
            }
        ),
        **_inch(
            {
                "#2": (0.167, 0.053),
                "#4": (0.219, 0.068),
                "#6": (0.270, 0.082),
                "#8": (0.322, 0.096),
                "#10": (0.373, 0.110),
                "#12": (0.425, 0.125),
                "1/4": (0.492, 0.144),
                "5/16": (0.615, 0.178),
                "3/8": (0.740, 0.212),
            }
        ),
    },
    "cheese": {
        **_mm(
            {
                "M1.6": (3.0, 1.1),
                "M2": (3.8, 1.4),
                "M2.5": (4.5, 1.8),
                "M3": (5.5, 2.0),
                "M4": (7.0, 2.6),
                "M5": (8.5, 3.3),
                "M6": (10.0, 3.9),
                "M8": (13.0, 5.0),
                "M10": (16.0, 6.0),
            }
        ),
        **_inch(
            {
                "#2": (0.140, 0.083),
                "#4": (0.183, 0.104),
                "#6": (0.226, 0.125),
                "#8": (0.270, 0.146),
                "#10": (0.313, 0.168),
                "#12": (0.357, 0.188),
                "1/4": (0.414, 0.216),
                "5/16": (0.518, 0.267),
                "3/8": (0.622, 0.318),
            }
        ),
    },
}

#: Plain washers: outside diameter and thickness, by nominal size.
WASHERS: dict[str, tuple[float, float]] = {
    **_mm(
        {
            "M1.6": (4.0, 0.3),
            "M2": (5.0, 0.3),
            "M2.5": (6.0, 0.5),
            "M3": (7.0, 0.5),
            "M4": (9.0, 0.8),
            "M5": (10.0, 1.0),
            "M6": (12.0, 1.6),
            "M8": (16.0, 1.6),
            "M10": (20.0, 2.0),
            "M12": (24.0, 2.5),
            "M14": (28.0, 2.5),
            "M16": (30.0, 3.0),
            "M20": (37.0, 3.0),
            "M24": (44.0, 4.0),
            "M30": (56.0, 4.0),
            "M36": (66.0, 5.0),
        }
    ),
    **_inch(
        {
            "#2": (0.250, 0.022),
            "#4": (0.312, 0.035),
            "#6": (0.375, 0.049),
            "#8": (0.375, 0.049),
            "#10": (0.406, 0.049),
            "#12": (0.438, 0.065),
            "1/4": (0.625, 0.065),
            "5/16": (0.688, 0.065),
            "3/8": (0.812, 0.065),
            "7/16": (0.922, 0.065),
            "1/2": (1.062, 0.095),
            "5/8": (1.312, 0.095),
            "3/4": (1.469, 0.134),
            "1": (2.000, 0.134),
        }
    ),
}

#: Cross recessed countersunk heads (ISO 7046-1): theoretical head diameter.
RECESSED_CSK: dict[str, float] = {
    "M1.6": 3.6,
    "M2": 4.4,
    "M2.5": 5.5,
    "M3": 6.3,
    "M3.5": 8.2,
    "M4": 9.4,
    "M5": 10.4,
    "M6": 12.6,
    "M8": 17.3,
    "M10": 20.0,
}


def head(form: str, name: str) -> tuple[float, float] | None:
    """Head diameter and height of a counterbore head ``form`` for size ``name``, or None
    when the standard has no such head (the socket head lives in ``hole_data``)."""
    return HEADS.get(form, {}).get(base_of(name))


def washer(name: str) -> tuple[float, float] | None:
    """Plain washer outside diameter and thickness for size ``name``, or None."""
    return WASHERS.get(base_of(name))


def recessed_csk(name: str) -> float | None:
    """Cross recessed countersunk head diameter for a metric size, or None."""
    return RECESSED_CSK.get(base_of(name))


# Drill names ---------------------------------------------------------------------------

_NUMBER = (
    0.2280, 0.2210, 0.2130, 0.2090, 0.2055, 0.2040, 0.2010, 0.1990, 0.1960, 0.1935,
    0.1910, 0.1890, 0.1850, 0.1820, 0.1800, 0.1770, 0.1730, 0.1695, 0.1660, 0.1610,
    0.1590, 0.1570, 0.1540, 0.1520, 0.1495, 0.1470, 0.1440, 0.1405, 0.1360, 0.1285,
    0.1200, 0.1160, 0.1130, 0.1110, 0.1100, 0.1065, 0.1040, 0.1015, 0.0995, 0.0980,
    0.0960, 0.0935, 0.0890, 0.0860, 0.0820, 0.0810, 0.0785, 0.0760, 0.0730, 0.0700,
    0.0670, 0.0635, 0.0595, 0.0550, 0.0520, 0.0465, 0.0430, 0.0420, 0.0410, 0.0400,
    0.0390, 0.0380, 0.0370, 0.0360, 0.0350, 0.0330, 0.0320, 0.0310, 0.0292, 0.0280,
    0.0260, 0.0250, 0.0240, 0.0225, 0.0210, 0.0200, 0.0180, 0.0160, 0.0145, 0.0135,
)  # fmt: skip
_LETTER = (
    0.234, 0.238, 0.242, 0.246, 0.250, 0.257, 0.261, 0.266, 0.272, 0.277, 0.281, 0.290,
    0.295, 0.302, 0.316, 0.323, 0.332, 0.339, 0.348, 0.358, 0.368, 0.377, 0.386, 0.397,
    0.404, 0.413,
)  # fmt: skip


def _fraction(n: int) -> str:
    from math import gcd

    g = gcd(n, 64)
    whole, rest = divmod(n // g, 64 // g)
    if rest == 0:
        return str(whole)
    frac = f"{rest}/{64 // g}"
    return f"{whole} {frac}" if whole else frac


#: Every named inch drill: (diameter in inches, name).
DRILLS: tuple[tuple[float, str], ...] = (
    *((d, f"#{k}") for k, d in enumerate(_NUMBER, start=1)),
    *((d, chr(ord("A") + k)) for k, d in enumerate(_LETTER)),
    *((n / 64, _fraction(n)) for n in range(1, 129)),
)

#: How close a diameter must be to a drill to take its name, in inches.
DRILL_TOLERANCE = 0.0003


def drill_names(diameter_mm: float) -> list[str]:
    """The inch drill names of ``diameter_mm`` (a letter drill can also be a fraction,
    for example E is 1/4), or an empty list."""
    inches = diameter_mm / INCH
    return [name for d, name in DRILLS if abs(d - inches) <= DRILL_TOLERANCE]
