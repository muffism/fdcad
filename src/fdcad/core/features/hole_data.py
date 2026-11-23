"""Standard sizes for the Hole Tool (PHASE4_SPEC P4.1, CLAUDE.md 7.6, DECISIONS D310).

Compiled from the published standards, never from another product's tables:

- ISO metric coarse threads: nominal diameter and pitch from ISO 261 and ISO 262.
  Tap drill is the usual rule of nominal diameter minus pitch.
- ISO metric clearance holes: fine, medium and coarse series of ISO 273, shown as
  Close, Normal and Loose.
- Metric heads and nuts: socket head cap screws (ISO 4762: head diameter, head
  height equal to the nominal size), countersunk socket screws (ISO 10642, 90
  degree head, theoretical head diameter) and hex nuts (ISO 4032: width across
  flats and height).
- ANSI inch threads: Unified coarse (UNC) and two common fine (UNF) sizes from
  ANSI B1.1, with the 75 percent thread tap drills. Clearance close and normal
  fits are common close and free fit drill sizes, which are smaller than the
  ASME B18.2.8 clearance holes for most sizes (audit D13 item 1, D728); loose adds
  1/32 inch to the normal fit.
- Inch heads and nuts: socket head cap screws and 82 degree flat head screws
  (ASME B18.3) and hex nuts (ASME B18.2.2).

Every length here is in millimetres. Heat set insert sizes are typical published
values and the user can change them (an editable table in the preferences).
"""

from __future__ import annotations

from dataclasses import dataclass

INCH = 25.4

#: Hole types (FDEF_SPEC 5.3.21).
HOLE_TYPES = (
    "simple",
    "counterbore",
    "countersink",
    "tapped",
    "heat_set_insert",
    "nut_trap",
    "nut_slot",
    "self_tapping",  # TR255 (D840)
    "magnet",  # TR179 (D869)
    "dowel",  # TR252 (D872)
    "bearing",  # TR251 (D873)
    "counterdrill",  # TR144 (D1506)
    "pipe_tapped",  # TR145 (D1511)
    "custom",  # TR144 (D1912): a stack of elements
)
STANDARDS = ("iso", "ansi", "user")  # "user": sizes from the user's file (TR144, D1914)
PURPOSES = ("drill", "tap_drill", "clearance")
FITS = ("close", "normal", "loose")
#: Printing fit presets (PLAN Phase 4): none, clearance, slip and press.
PRINT_FITS = ("none", "clearance", "slip", "press")


@dataclass(frozen=True)
class ScrewSize:
    """One screw size of a standard. Lengths in mm."""

    name: str
    diameter: float
    pitch: float
    tap_drill: float
    clearance: tuple[float, float, float]  # close, normal, loose
    head_diameter: float  # socket head cap screw
    head_height: float
    csk_diameter: float  # countersunk head, theoretical sharp diameter
    nut_flats: float  # hex nut width across flats
    nut_height: float
    thread_class: str = ""  # a user size's thread class, such as 6g (TR327, D1920)


def _m(
    name: str,
    d: float,
    p: float,
    clr: tuple[float, float, float],
    dk: float,
    csk: float,
    s: float,
    m: float,
) -> ScrewSize:
    return ScrewSize(name, d, p, round(d - p, 3), clr, dk, d, csk, s, m)


#: ISO metric coarse sizes (ISO 261, 262, 273, 4762, 10642, 4032).
ISO: tuple[ScrewSize, ...] = (
    _m("M1.6", 1.6, 0.35, (1.7, 1.8, 2.0), 3.0, 3.0, 3.2, 1.3),
    _m("M2", 2.0, 0.4, (2.2, 2.4, 2.6), 3.8, 3.8, 4.0, 1.6),
    _m("M2.5", 2.5, 0.45, (2.7, 2.9, 3.1), 4.5, 4.7, 5.0, 2.0),
    _m("M3", 3.0, 0.5, (3.2, 3.4, 3.6), 5.5, 6.72, 5.5, 2.4),
    _m("M4", 4.0, 0.7, (4.3, 4.5, 4.8), 7.0, 8.96, 7.0, 3.2),
    _m("M5", 5.0, 0.8, (5.3, 5.5, 5.8), 8.5, 11.2, 8.0, 4.7),
    _m("M6", 6.0, 1.0, (6.4, 6.6, 7.0), 10.0, 13.44, 10.0, 5.2),
    _m("M8", 8.0, 1.25, (8.4, 9.0, 10.0), 13.0, 17.92, 13.0, 6.8),
    _m("M10", 10.0, 1.5, (10.5, 11.0, 12.0), 16.0, 22.4, 16.0, 8.4),
    _m("M12", 12.0, 1.75, (13.0, 13.5, 14.5), 18.0, 26.88, 18.0, 10.8),
    _m("M14", 14.0, 2.0, (15.0, 15.5, 16.5), 21.0, 30.8, 21.0, 12.8),
    _m("M16", 16.0, 2.0, (17.0, 17.5, 18.5), 24.0, 33.6, 24.0, 14.8),
    _m("M20", 20.0, 2.5, (21.0, 22.0, 24.0), 30.0, 40.32, 30.0, 18.0),
    _m("M24", 24.0, 3.0, (25.0, 26.0, 28.0), 36.0, 48.0, 36.0, 21.5),
    # TR253 (D786): larger coarse sizes; the countersunk head is about twice the size.
    _m("M30", 30.0, 3.5, (31.0, 33.0, 35.0), 45.0, 60.0, 46.0, 25.6),
    _m("M36", 36.0, 4.0, (37.0, 39.0, 42.0), 54.0, 72.0, 55.0, 31.0),
    _m("M42", 42.0, 4.5, (43.0, 45.0, 48.0), 63.0, 84.0, 65.0, 34.0),
    _m("M48", 48.0, 5.0, (50.0, 52.0, 56.0), 72.0, 96.0, 75.0, 38.0),
)

#: ISO metric fine pitches (ISO 261, 262; TR253, D786): (size, pitch).
FINE_PITCHES: tuple[tuple[str, float], ...] = (
    ("M3", 0.35),
    ("M4", 0.5),
    ("M5", 0.5),
    ("M6", 0.75),
    ("M8", 1.0),
    ("M10", 1.25),
    ("M10", 1.0),
    ("M12", 1.5),
    ("M12", 1.25),
    ("M14", 1.5),
    ("M16", 1.5),
    ("M20", 1.5),
    ("M24", 2.0),
    ("M30", 2.0),
    ("M36", 3.0),
)


def _fine(coarse: tuple[ScrewSize, ...]) -> tuple[ScrewSize, ...]:
    """The fine pitch sizes: the coarse size's holes, heads and nuts, a finer thread."""
    by_name = {s.name: s for s in coarse}
    out = []
    for name, pitch in FINE_PITCHES:
        c = by_name[name]
        out.append(
            ScrewSize(
                f"{name}x{pitch:g}",
                c.diameter,
                pitch,
                round(c.diameter - pitch, 3),
                c.clearance,
                c.head_diameter,
                c.head_height,
                c.csk_diameter,
                c.nut_flats,
                c.nut_height,
            )
        )
    return tuple(out)


def _ordered(rows: tuple[ScrewSize, ...]) -> tuple[ScrewSize, ...]:
    """By diameter, then coarsest thread first."""
    return tuple(sorted(rows, key=lambda s: (s.diameter, -s.pitch)))


ISO = _ordered(ISO + _fine(ISO))


def _u(
    name: str,
    d: float,
    tpi: float,
    tap: float,
    close: float,
    normal: float,
    dk: float,
    k: float,
    csk: float,
    s: float,
    m: float,
) -> ScrewSize:
    """An inch size; every value in inches except threads per inch."""
    loose = normal + 1 / 32
    return ScrewSize(
        name,
        d * INCH,
        INCH / tpi,
        tap * INCH,
        (close * INCH, normal * INCH, loose * INCH),
        dk * INCH,
        k * INCH,
        csk * INCH,
        s * INCH,
        m * INCH,
    )


#: ANSI inch sizes (ANSI B1.1, B18.3, B18.2.2; clearance holes are drill sizes, D728).
ANSI: tuple[ScrewSize, ...] = (
    _u("#2-56", 0.086, 56, 0.070, 0.089, 0.096, 0.140, 0.086, 0.172, 3 / 16, 1 / 16),
    _u("#4-40", 0.112, 40, 0.089, 0.116, 0.1285, 0.183, 0.112, 0.225, 1 / 4, 3 / 32),
    _u("#6-32", 0.138, 32, 0.1065, 0.144, 0.1495, 0.226, 0.138, 0.279, 5 / 16, 7 / 64),
    _u("#8-32", 0.164, 32, 0.136, 0.1695, 0.177, 0.270, 0.164, 0.332, 11 / 32, 1 / 8),
    _u("#10-24", 0.190, 24, 0.1495, 0.196, 0.201, 0.312, 0.190, 0.385, 3 / 8, 1 / 8),
    _u("#10-32", 0.190, 32, 0.159, 0.196, 0.201, 0.312, 0.190, 0.385, 3 / 8, 1 / 8),
    _u("#12-24", 0.216, 24, 0.177, 0.221, 0.228, 0.343, 0.216, 0.438, 7 / 16, 5 / 32),
    _u("1/4-20", 0.250, 20, 0.201, 0.257, 0.266, 0.375, 0.250, 0.507, 7 / 16, 7 / 32),
    _u("1/4-28", 0.250, 28, 0.213, 0.257, 0.266, 0.375, 0.250, 0.507, 7 / 16, 7 / 32),
    _u("5/16-18", 0.3125, 18, 0.257, 0.323, 0.332, 0.469, 0.3125, 0.635, 1 / 2, 17 / 64),
    _u("3/8-16", 0.375, 16, 0.3125, 0.386, 0.397, 0.5625, 0.375, 0.762, 9 / 16, 21 / 64),
    _u("7/16-14", 0.4375, 14, 0.368, 0.4531, 0.4687, 0.656, 0.4375, 0.812, 11 / 16, 3 / 8),
    _u("1/2-13", 0.500, 13, 0.4219, 0.5156, 0.5312, 0.750, 0.500, 0.875, 3 / 4, 7 / 16),
    _u("5/8-11", 0.625, 11, 0.5312, 0.6406, 0.6562, 0.9375, 0.625, 1.125, 15 / 16, 35 / 64),
    _u("3/4-10", 0.750, 10, 0.6562, 0.7656, 0.7812, 1.125, 0.750, 1.375, 9 / 8, 41 / 64),
    _u("1-8", 1.000, 8, 0.875, 1.0156, 1.0312, 1.500, 1.000, 1.875, 3 / 2, 55 / 64),
    # TR253 (D786): the smallest gauge sizes, and the rest of the fine (UNF) and extra
    # fine (UNEF) series. Holes, heads and nuts follow the coarse size of each diameter.
    _u("#0-80", 0.060, 80, 0.0469, 0.0635, 0.067, 0.096, 0.060, 0.119, 5 / 32, 3 / 64),
    _u("#1-64", 0.073, 64, 0.0595, 0.076, 0.081, 0.118, 0.073, 0.146, 5 / 32, 3 / 64),
    _u("#1-72", 0.073, 72, 0.0595, 0.076, 0.081, 0.118, 0.073, 0.146, 5 / 32, 3 / 64),
    _u("#2-64", 0.086, 64, 0.070, 0.089, 0.096, 0.140, 0.086, 0.172, 3 / 16, 1 / 16),
    _u("#3-48", 0.099, 48, 0.0785, 0.104, 0.110, 0.161, 0.099, 0.199, 3 / 16, 1 / 16),
    _u("#3-56", 0.099, 56, 0.082, 0.104, 0.110, 0.161, 0.099, 0.199, 3 / 16, 1 / 16),
    _u("#4-48", 0.112, 48, 0.0935, 0.116, 0.1285, 0.183, 0.112, 0.225, 1 / 4, 3 / 32),
    _u("#5-40", 0.125, 40, 0.1015, 0.1285, 0.136, 0.205, 0.125, 0.252, 1 / 4, 3 / 32),
    _u("#5-44", 0.125, 44, 0.104, 0.1285, 0.136, 0.205, 0.125, 0.252, 1 / 4, 3 / 32),
    _u("#6-40", 0.138, 40, 0.113, 0.144, 0.1495, 0.226, 0.138, 0.279, 5 / 16, 7 / 64),
    _u("#8-36", 0.164, 36, 0.136, 0.1695, 0.177, 0.270, 0.164, 0.332, 11 / 32, 1 / 8),
    _u("#12-28", 0.216, 28, 0.182, 0.221, 0.228, 0.343, 0.216, 0.438, 7 / 16, 5 / 32),
    _u("#12-32", 0.216, 32, 0.185, 0.221, 0.228, 0.343, 0.216, 0.438, 7 / 16, 5 / 32),
    _u("1/4-32", 0.250, 32, 0.2188, 0.257, 0.266, 0.375, 0.250, 0.507, 7 / 16, 7 / 32),
    _u("5/16-24", 0.3125, 24, 0.272, 0.323, 0.332, 0.469, 0.3125, 0.635, 1 / 2, 17 / 64),
    _u("5/16-32", 0.3125, 32, 0.2812, 0.323, 0.332, 0.469, 0.3125, 0.635, 1 / 2, 17 / 64),
    _u("3/8-24", 0.375, 24, 0.332, 0.386, 0.397, 0.5625, 0.375, 0.762, 9 / 16, 21 / 64),
    _u("3/8-32", 0.375, 32, 0.3438, 0.386, 0.397, 0.5625, 0.375, 0.762, 9 / 16, 21 / 64),
    _u("7/16-20", 0.4375, 20, 0.3906, 0.4531, 0.4687, 0.656, 0.4375, 0.812, 11 / 16, 3 / 8),
    _u("7/16-28", 0.4375, 28, 0.4062, 0.4531, 0.4687, 0.656, 0.4375, 0.812, 11 / 16, 3 / 8),
    _u("1/2-20", 0.500, 20, 0.4531, 0.5156, 0.5312, 0.750, 0.500, 0.875, 3 / 4, 7 / 16),
    _u("1/2-28", 0.500, 28, 0.4688, 0.5156, 0.5312, 0.750, 0.500, 0.875, 3 / 4, 7 / 16),
    _u("5/8-18", 0.625, 18, 0.5781, 0.6406, 0.6562, 0.9375, 0.625, 1.125, 15 / 16, 35 / 64),
    _u("5/8-24", 0.625, 24, 0.5781, 0.6406, 0.6562, 0.9375, 0.625, 1.125, 15 / 16, 35 / 64),
    _u("3/4-16", 0.750, 16, 0.6875, 0.7656, 0.7812, 1.125, 0.750, 1.375, 9 / 8, 41 / 64),
    _u("3/4-20", 0.750, 20, 0.7031, 0.7656, 0.7812, 1.125, 0.750, 1.375, 9 / 8, 41 / 64),
    _u("1-12", 1.000, 12, 0.9219, 1.0156, 1.0312, 1.500, 1.000, 1.875, 3 / 2, 55 / 64),
    _u("1-20", 1.000, 20, 0.9531, 1.0156, 1.0312, 1.500, 1.000, 1.875, 3 / 2, 55 / 64),
)
ANSI = _ordered(ANSI)

#: Countersink head angle of each standard, in degrees.
CSK_ANGLE = {"iso": 90.0, "ansi": 82.0, "user": 90.0}


#: The user's own sizes (TR144 item 4, D1914), set by the app from its preferences.
USER_SIZES: list[ScrewSize] = []

#: The columns of a user size file; only name and diameter are needed.
USER_COLUMNS = (
    "name",
    "diameter",
    "pitch",
    "tap_drill",
    "clearance_close",
    "clearance_normal",
    "clearance_loose",
    "head_diameter",
    "head_height",
    "csk_diameter",
    "nut_flats",
    "nut_height",
    "class",  # TR327 (D1920): the thread class Thread and Cosmetic Thread take
)


def parse_user_sizes(text: str) -> list[ScrewSize]:
    """Rows of a user size file (TR144 item 4, D1914): comma separated values with a
    header row naming the columns of ``USER_COLUMNS`` (name and diameter needed, in
    mm). Missing values follow common proportions of the diameter. Raises ValueError
    naming the row that is wrong. Reading the file never runs code."""
    import csv
    import io

    reader = csv.DictReader(io.StringIO(text))
    fields = [f.strip().lower() for f in reader.fieldnames or []]
    if "name" not in fields or "diameter" not in fields:
        raise ValueError("The file needs a header row with name and diameter columns.")
    out: list[ScrewSize] = []
    for number, raw in enumerate(reader, start=2):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        try:
            d = float(row["diameter"])
            values = {key: float(row[key]) if row.get(key) else None for key in USER_COLUMNS[2:-1]}
        except ValueError:
            raise ValueError(f"Row {number} has a value that is not a number.") from None
        name = row.get("name", "")
        if not name or d <= 0:
            raise ValueError(f"Row {number} needs a name and a diameter above 0.")

        def get(key: str, default: float, found: dict[str, float | None] = values) -> float:
            value = found.get(key)
            return default if value is None else value

        out.append(
            ScrewSize(
                name,
                d,
                get("pitch", 0.0),
                get("tap_drill", round(d * 0.8, 3)),
                (
                    get("clearance_close", round(d * 1.05, 3)),
                    get("clearance_normal", round(d * 1.1, 3)),
                    get("clearance_loose", round(d * 1.2, 3)),
                ),
                get("head_diameter", round(d * 1.6, 3)),
                get("head_height", d),
                get("csk_diameter", round(d * 2.0, 3)),
                get("nut_flats", round(d * 1.6, 3)),
                get("nut_height", round(d * 0.8, 3)),
                row.get("class", ""),
            )
        )
    if not out:
        raise ValueError("The file has no sizes. Add a row under the header.")
    return out


def sizes(standard: str) -> tuple[ScrewSize, ...]:
    """Every size of ``standard`` (``"iso"``, ``"ansi"`` or ``"user"``, D1914)."""
    if standard == "user":
        return tuple(USER_SIZES)
    return ANSI if standard == "ansi" else ISO


def size_names(standard: str) -> list[str]:
    """Names of the sizes of ``standard``, smallest first."""
    return [s.name for s in sizes(standard)]


def find(standard: str, name: str) -> ScrewSize | None:
    """The size called ``name`` in ``standard``, or None."""
    for s in sizes(standard):
        if s.name == name:
            return s
    return None


def counterbore(size: ScrewSize, form: str = "socket") -> tuple[float, float] | None:
    """Counterbore diameter and depth for a head ``form`` (DECISIONS D310, D786), or None
    when that head has no size in the standard.

    Diameter: head diameter plus 1 mm below M12 and plus 2 mm from M12 (1/16 and
    1/8 inch for inch sizes), so the head clears its bore. Depth: head height. A
    washer seat is a socket head on a plain washer: the washer's diameter plus the
    same clearance, and the head height plus the washer thickness.
    """
    from fdcad.core.features import hole_heads

    inch = not size.name.startswith("M")
    small = size.diameter < 12.0
    extra = (1 / 16 if small else 1 / 8) * INCH if inch else (1.0 if small else 2.0)
    if form == "washer":
        found = hole_heads.washer(size.name)
        if found is None:
            return None
        return round(found[0] + extra, 4), round(size.head_height + found[1], 4)
    if form != "socket":
        head = hole_heads.head(form, size.name)
        if head is None:
            return None
        return round(head[0] + extra, 4), round(head[1], 4)
    return round(size.head_diameter + extra, 4), round(size.head_height, 4)


@dataclass(frozen=True)
class InsertSize:
    """A heat set insert: thread size, hole diameter and hole depth (mm)."""

    name: str
    diameter: float
    depth: float


#: Typical published heat set insert hole sizes (editable in the preferences, D310).
INSERTS: tuple[InsertSize, ...] = (
    InsertSize("M2", 3.2, 4.0),
    InsertSize("M2.5", 3.6, 5.0),
    InsertSize("M3", 4.0, 5.7),
    InsertSize("M4", 5.6, 8.1),
    InsertSize("M5", 6.4, 9.5),
    InsertSize("M6", 8.0, 12.7),
    InsertSize("M8", 9.7, 12.7),
    InsertSize("#4-40", 0.161 * INCH, 0.250 * INCH),
    InsertSize("#6-32", 0.199 * INCH, 0.300 * INCH),
    InsertSize("#8-32", 0.228 * INCH, 0.300 * INCH),
    InsertSize("#10-32", 0.250 * INCH, 0.375 * INCH),
    InsertSize("1/4-20", 0.354 * INCH, 0.500 * INCH),
)


#: Holes for screws that form their own thread in plastic (TR255, D840), by FDCAD's own
#: rule rather than a standard: the hole is 0.8 of the screw's size, 2.5 sizes deep, so
#: the thread bites into the wall. The entry bevel opens to the screw's size. Editable
#: in the Hole Tool like the insert table.
SELF_TAPPING: tuple[InsertSize, ...] = tuple(
    InsertSize(name, round(0.8 * d, 4), round(2.5 * d, 4))
    for name, d in (
        ("M2", 2.0),
        ("M2.5", 2.5),
        ("M3", 3.0),
        ("M3.5", 3.5),
        ("M4", 4.0),
        ("M5", 5.0),
        ("M6", 6.0),
        ("#2", 0.086 * INCH),
        ("#4", 0.112 * INCH),
        ("#6", 0.138 * INCH),
        ("#8", 0.164 * INCH),
        ("#10", 0.190 * INCH),
    )
)
#: The entry bevel's diameter over the hole's: back to the screw's own size.
SELF_TAP_BEVEL = 1.25


def self_tap_table(rows: list[dict[str, object]] | None = None) -> list[InsertSize]:
    """The self tapping table: the user's valid rows when given, else FDCAD's rule."""
    if not rows:
        return list(SELF_TAPPING)
    found = insert_table(rows)
    return found if found != list(INSERTS) else list(SELF_TAPPING)


def bad_insert_rows(rows: list[dict[str, object]]) -> list[int]:
    """Row numbers (from 1) of insert rows that are not a name, a diameter and a depth
    above zero. Such rows are left out of the table (audit A item 19, D739)."""
    bad = []
    for number, row in enumerate(rows, start=1):
        try:
            ok = bool(str(row["name"]).strip())
            ok = ok and float(str(row["diameter"])) > 0 and float(str(row["depth"])) > 0
        except (KeyError, ValueError):
            ok = False
        if not ok:
            bad.append(number)
    return bad


def insert_table(rows: list[dict[str, object]] | None = None) -> list[InsertSize]:
    """The insert table: the user's rows when given and valid, else the defaults."""
    if not rows:
        return list(INSERTS)
    out: list[InsertSize] = []
    for row in rows:
        try:
            name = str(row["name"])
            diameter = float(str(row["diameter"]))
            depth = float(str(row["depth"]))
        except (KeyError, ValueError):
            continue
        if name and diameter > 0 and depth > 0:
            out.append(InsertSize(name, diameter, depth))
    return out or list(INSERTS)


def fit_offset(fit: str, tolerance: float) -> float:
    """How much a printing fit preset adds to a hole diameter (DECISIONS D311).

    ``tolerance`` is the printer profile's fit tolerance: the gap per side a
    printed part needs to slide freely. Clearance adds two gaps, Slip one, Press
    none (the hole is printed at its nominal size, so it grips).
    """
    return {"clearance": 2.0 * tolerance, "slip": tolerance}.get(fit, 0.0)


#: Default printer fit tolerance in mm when no profile sets one (DECISIONS D311).
DEFAULT_FIT_TOLERANCE = 0.2


#: Common neodymium magnet sizes (TR179, D869): name to (diameter or width, length (0 for
#: round), thickness) in mm, the nominal sizes sellers list.
MAGNETS: dict[str, tuple[float, float, float]] = {
    "Round 3 x 2": (3.0, 0.0, 2.0),
    "Round 5 x 2": (5.0, 0.0, 2.0),
    "Round 6 x 2": (6.0, 0.0, 2.0),
    "Round 6 x 3": (6.0, 0.0, 3.0),
    "Round 8 x 2": (8.0, 0.0, 2.0),
    "Round 8 x 3": (8.0, 0.0, 3.0),
    "Round 10 x 2": (10.0, 0.0, 2.0),
    "Round 10 x 3": (10.0, 0.0, 3.0),
    "Round 10 x 5": (10.0, 0.0, 5.0),
    "Round 12 x 3": (12.0, 0.0, 3.0),
    "Round 15 x 3": (15.0, 0.0, 3.0),
    "Round 20 x 3": (20.0, 0.0, 3.0),
    "Block 10 x 5 x 2": (5.0, 10.0, 2.0),
    "Block 10 x 5 x 3": (5.0, 10.0, 3.0),
    "Block 15 x 10 x 3": (10.0, 15.0, 3.0),
    "Block 20 x 10 x 2": (10.0, 20.0, 2.0),
    "Block 20 x 10 x 3": (10.0, 20.0, 3.0),
    "Block 20 x 10 x 5": (10.0, 20.0, 5.0),
    "Block 30 x 10 x 3": (10.0, 30.0, 3.0),
}


#: Dowel pin diameters (TR252, D872): metric parallel pins (ISO 2338, ISO 8734) and inch
#: dowel pins, by name, in mm. Pins are made a little over size, so a hole at the
#: nominal size is a press fit; a slip fit hole is DOWEL_SLIP larger.
DOWELS: dict[str, dict[str, float]] = {
    "iso": {
        f"{d:g} mm": d for d in (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 16.0)
    },
    "ansi": {
        name: inches * INCH
        for name, inches in (
            ("1/16 in", 1 / 16),
            ("3/32 in", 3 / 32),
            ("1/8 in", 1 / 8),
            ("5/32 in", 5 / 32),
            ("3/16 in", 3 / 16),
            ("1/4 in", 1 / 4),
            ("5/16 in", 5 / 16),
            ("3/8 in", 3 / 8),
            ("1/2 in", 1 / 2),
            ("5/8 in", 5 / 8),
            ("3/4 in", 3 / 4),
        )
    },
}
DOWEL_SLIP = 0.02
DOWEL_FITS = ("press", "slip")


def dowel_names(standard: str) -> list[str]:
    """Dowel sizes of ``standard`` (iso or ansi), smallest first."""
    return list(DOWELS.get(standard, DOWELS["iso"]))


def dowel_size(standard: str, name: str) -> float | None:
    """The nominal diameter of dowel ``name``, or None."""
    for table in (DOWELS.get(standard, {}), *DOWELS.values()):
        if name in table:
            return table[name]
    return None


#: Common deep groove ball bearings (TR251, D873): designation to (bore, outside
#: diameter, width) in mm, the boundary dimensions of ISO 15.
BEARINGS: dict[str, tuple[float, float, float]] = {
    "623": (3.0, 10.0, 4.0),
    "624": (4.0, 13.0, 5.0),
    "625": (5.0, 16.0, 5.0),
    "626": (6.0, 19.0, 6.0),
    "627": (7.0, 22.0, 7.0),
    "608": (8.0, 22.0, 7.0),
    "609": (9.0, 24.0, 7.0),
    "693": (3.0, 8.0, 3.0),
    "695": (5.0, 13.0, 4.0),
    "696": (6.0, 15.0, 5.0),
    "697": (7.0, 17.0, 5.0),
    "688": (8.0, 16.0, 5.0),
    "698": (8.0, 19.0, 6.0),
    "6800": (10.0, 19.0, 5.0),
    "6900": (10.0, 22.0, 6.0),
    "6000": (10.0, 26.0, 8.0),
    "6001": (12.0, 28.0, 8.0),
    "6002": (15.0, 32.0, 9.0),
    "6003": (17.0, 35.0, 10.0),
    "6004": (20.0, 42.0, 12.0),
    "6200": (10.0, 30.0, 9.0),
    "6201": (12.0, 32.0, 10.0),
    "6202": (15.0, 35.0, 11.0),
    "6203": (17.0, 40.0, 12.0),
    "6204": (20.0, 47.0, 14.0),
}


def bearing_groove(bore: float) -> tuple[float, float]:
    """(width, radius) of the ring groove for an internal retaining ring in a bore of
    ``bore`` mm: FDCAD's rule close to the published ring tables (groove about 4.5 %
    over the bore, width by ring thickness band)."""
    width = 1.1 if bore <= 25 else 1.3 if bore <= 38 else 1.6 if bore <= 55 else 1.85
    return width, bore * 1.045 / 2


# Tapered pipe threads (TR145, D1511) -------------------------------------------------

#: The taper of every pipe thread here: 1 in 16 on the diameter.
PIPE_TAPER = 1.0 / 16.0


@dataclass(frozen=True)
class PipeSize:
    """One tapered pipe thread size, in mm: the major diameter at the gauge plane, the
    pitch, the length of thread in the hole and the drill it is tapped from."""

    name: str
    major: float
    pitch: float
    length: float
    drill: float


def _npt(name: str, tpi: float, od: float, drill: float) -> PipeSize:
    """NPT, ASME B1.20.1: the outside diameter, threads per inch and the effective thread
    length L2 = (0.80 D + 6.8) p, all in inches; the drill is the usual tap drill."""
    p = 1.0 / tpi
    return PipeSize(name, od * INCH, p * INCH, round((0.80 * od + 6.8) * p * INCH, 3), drill * INCH)


#: NPT sizes (ANSI standard): outside diameter and threads per inch from ASME B1.20.1.
NPT = (
    _npt("1/16 NPT", 27, 0.3125, 0.242),
    _npt("1/8 NPT", 27, 0.405, 0.339),
    _npt("1/4 NPT", 18, 0.540, 0.4375),
    _npt("3/8 NPT", 18, 0.675, 0.578),
    _npt("1/2 NPT", 14, 0.840, 0.719),
    _npt("3/4 NPT", 14, 1.050, 0.922),
    _npt("1 NPT", 11.5, 1.315, 1.156),
    _npt("1-1/4 NPT", 11.5, 1.660, 1.500),
    _npt("1-1/2 NPT", 11.5, 1.900, 1.734),
    _npt("2 NPT", 11.5, 2.375, 2.219),
)
#: R (BSPT) sizes (ISO standard), ISO 7-1: the major diameter at the gauge plane, the
#: threads per inch, and the gauge length as the thread length; the usual tap drill.
RP = tuple(
    PipeSize(name, major, INCH / tpi, gauge, drill)
    for name, major, tpi, gauge, drill in (
        ("Rc 1/8", 9.728, 28, 4.0, 8.4),
        ("Rc 1/4", 13.157, 19, 6.0, 11.2),
        ("Rc 3/8", 16.662, 19, 6.4, 14.75),
        ("Rc 1/2", 20.955, 14, 8.2, 18.25),
        ("Rc 3/4", 26.441, 14, 9.5, 23.75),
        ("Rc 1", 33.249, 11, 10.4, 30.0),
        ("Rc 1-1/4", 41.910, 11, 12.7, 38.5),
        ("Rc 1-1/2", 47.803, 11, 12.7, 44.5),
        ("Rc 2", 59.614, 11, 15.9, 56.0),
    )
)


def pipe_sizes(standard: str) -> tuple[PipeSize, ...]:
    """The tapered pipe sizes of a standard: NPT for ANSI, Rc for ISO."""
    return NPT if standard == "ansi" else RP
