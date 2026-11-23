"""Printer profiles and material densities (PLAN section 8 item 16, DECISIONS D351).

Profiles are application preferences, not part data: the UI stores them as
plain dictionaries made by ``to_dict`` and read back by ``from_dict``.
Lengths are millimetres and angles radians, as everywhere in ``core``.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from typing import Any

#: Printing processes a printer profile can be (TR295 item 2).
PRINT_PROCESSES = ("fdm", "resin", "powder")


@dataclass(frozen=True)
class PrinterProfile:
    """One printer: build volume, nozzle, print limits and the slicer to open."""

    name: str = "Generic printer"
    bed_x: float = 220.0
    bed_y: float = 220.0
    height: float = 250.0
    nozzle: float = 0.4
    overhang_angle: float = math.radians(45.0)
    min_wall: float = 0.8
    fit_tolerance: float = 0.2
    #: Path of the slicer program; empty means the system's default app for 3MF files.
    slicer: str = ""
    #: The printing process (TR295 item 2, D801): ``fdm``, ``resin`` or ``powder``.
    process: str = "fdm"
    #: Layer height, smallest hole the printer makes round, and longest bridge (mm).
    layer_height: float = 0.2
    min_hole: float = 1.0
    max_bridge: float = 10.0
    #: Bed areas the printer cannot print on (TR413, D992): (x0, y0, x1, y1) in mm from
    #: the bed's front left corner, for clips, sensors or a purge area.
    no_zones: tuple[tuple[float, float, float, float], ...] = ()
    #: Height under the print head's gantry for printing parts one at a time; 0 when
    #: not set. Only the last part printed may be taller.
    head_clearance: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Plain values for storing in the preferences."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Any) -> PrinterProfile:
        """Read a stored profile. Missing or bad values fall back to the defaults."""
        base = cls()
        if not isinstance(data, dict):
            return base
        values: dict[str, Any] = {}
        name = data.get("name")
        if isinstance(name, str) and name.strip():
            values["name"] = name.strip()
        slicer = data.get("slicer")
        if isinstance(slicer, str):
            values["slicer"] = slicer
        process = data.get("process")
        if process in PRINT_PROCESSES:
            values["process"] = process
        for key in (
            "bed_x",
            "bed_y",
            "height",
            "nozzle",
            "min_wall",
            "fit_tolerance",
            "layer_height",
            "min_hole",
            "max_bridge",
        ):
            number = _number(data.get(key))
            if number is not None and number > 0:
                values[key] = number
        angle = _number(data.get("overhang_angle"))
        if angle is not None and 0 < angle < math.pi / 2:
            values["overhang_angle"] = angle
        values["no_zones"] = zones_from(data.get("no_zones"))  # TR413
        clearance = _number(data.get("head_clearance"))
        if clearance is not None and clearance >= 0:
            values["head_clearance"] = clearance
        return replace(base, **values)


def zones_from(raw: Any) -> tuple[tuple[float, float, float, float], ...]:
    """Stored no print zones; any that is not four numbers with some area is left out."""
    out: list[tuple[float, float, float, float]] = []
    for item in raw if isinstance(raw, list | tuple) else []:
        if not isinstance(item, list | tuple) or len(item) != 4:
            continue
        numbers = [_number(v) for v in item]
        if any(n is None for n in numbers):
            continue
        x0, y0, x1, y1 = (float(n) for n in numbers)  # type: ignore[arg-type]
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        if x1 - x0 > 0 and y1 - y0 > 0:
            out.append((x0, y0, x1, y1))
    return tuple(out)


def zones_text(zones: tuple[tuple[float, float, float, float], ...]) -> str:
    """Zones as typed text: x0 y0 x1 y1, separated by semicolons."""
    return "; ".join(" ".join(f"{v:g}" for v in zone) for zone in zones)


def parse_zones(text: str) -> tuple[tuple[float, float, float, float], ...]:
    """Typed zones back to numbers. Raises ValueError naming the bad zone."""
    out = []
    for k, part in enumerate(p for p in text.replace(",", " ").split(";") if p.strip()):
        try:
            numbers = [float(v) for v in part.split()]
        except ValueError as exc:
            raise ValueError(
                f"Zone {k + 1} has something that is not a number. Type four numbers: x0 y0 x1 y1."
            ) from exc
        if len(numbers) != 4:
            raise ValueError(f"Zone {k + 1} needs four numbers: x0 y0 x1 y1. Type all four.")
        out.append(numbers)
    return zones_from(out)


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


#: The default profile (PLAN 8 item 16): 220 by 220 by 250 mm, default 3MF app.
GENERIC = PrinterProfile()

#: Typical solid densities in g/cm3 for the material presets (editable in preferences).
DEFAULT_DENSITIES: dict[str, float] = {
    "PLA": 1.24,
    "PETG": 1.27,
    "ABS": 1.04,
    "ASA": 1.07,
    "TPU": 1.21,
    "Resin": 1.15,
}


def densities_from(data: Any) -> dict[str, float]:
    """Stored densities over the defaults; bad or non positive values are ignored."""
    out = dict(DEFAULT_DENSITIES)
    if isinstance(data, dict):
        for key, value in data.items():
            number = _number(value)
            if isinstance(key, str) and key.strip() and number is not None and number > 0:
                out[key.strip()] = number
    return out


def profiles_from(data: Any) -> list[PrinterProfile]:
    """Stored profiles in order, or just the generic one. Names are made unique."""
    found = [PrinterProfile.from_dict(d) for d in data] if isinstance(data, list) else []
    if not found:
        return [GENERIC]
    seen: set[str] = set()
    out = []
    for profile in found:
        name, k = profile.name, 2
        while name in seen:
            name = f"{profile.name} {k}"
            k += 1
        seen.add(name)
        out.append(replace(profile, name=name))
    return out


def manufacturing_values(profile: PrinterProfile) -> dict[str, float | str]:
    """The printer's own limits as Manufacturing Check rule values for its process
    (TR295 item 2, D801): the check starts from the printer in use."""
    return {
        "min_wall": profile.min_wall,
        "nozzle": profile.nozzle,
        "layer_height": profile.layer_height,
        "min_round_hole": profile.min_hole,
        "max_bridge": profile.max_bridge,
    }
