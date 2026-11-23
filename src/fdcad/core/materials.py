"""Part material (TR78, DECISIONS D803).

A part may have a material: a name, a density in g/cm3, and optionally a colour
and, for sheet metal, the smallest inside bend radius as a multiple of the
thickness. It is saved in the part (``Document.material``), so the part keeps
its density on any computer. The library offered is FDCAD's own general
values (not any supplier's tables) plus the materials the user adds in the
preferences. Mass Properties and Print Estimate start from the part's material;
the sheet metal check warns about bends tighter than the material allows. No Qt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fdcad.core.document.model import Document

#: One g/cm3 in lb/in3, for showing imperial densities.
LB_PER_IN3 = 0.0361273


@dataclass(frozen=True)
class Material:
    """A material: density in g/cm3; ``colour`` "#RRGGBB" or ""; ``min_bend`` the smallest
    inside bend radius over the sheet thickness, 0 when not known."""

    name: str
    density: float
    colour: str = ""
    min_bend: float = 0.0

    def to_data(self) -> dict[str, Any]:
        """The form saved in the part: only what is set."""
        out: dict[str, Any] = {"name": self.name, "density": self.density}
        if self.colour:
            out["colour"] = self.colour
        if self.min_bend > 0:
            out["min_bend"] = self.min_bend
        return out


#: FDCAD's general starting values. Densities in g/cm3; bends as radius over thickness.
LIBRARY: tuple[Material, ...] = (
    Material("PLA", 1.24, "#E8E4D8"),
    Material("PETG", 1.27, "#D8E6EE"),
    Material("ABS", 1.04, "#EDEAE0"),
    Material("ASA", 1.07, "#E6E6E0"),
    Material("TPU", 1.21, "#3A3A3A"),
    Material("Resin", 1.15, "#C8C0B0"),
    Material("Acrylic", 1.19, "#E0F0F4"),
    Material("Plywood", 0.60, "#C9A26B"),
    Material("Aluminium", 2.70, "#C4C8CC", 1.0),
    Material("Mild steel", 7.85, "#8C9096", 1.0),
    Material("Stainless steel", 8.00, "#A8ACB0", 1.5),
    Material("Copper", 8.96, "#B87333", 0.5),
    Material("Brass", 8.50, "#C9A43A", 1.0),
)


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out and abs(out) != float("inf") else None


def from_data(raw: Any) -> Material | None:
    """A saved material, or None when there is none or it is damaged."""
    if not isinstance(raw, dict):
        return None
    name = raw.get("name")
    density = _number(raw.get("density"))
    if not isinstance(name, str) or not name.strip() or density is None or density <= 0:
        return None
    colour = raw.get("colour", "")
    if not (isinstance(colour, str) and (colour == "" or _is_colour(colour))):
        colour = ""
    bend = _number(raw.get("min_bend", 0.0)) or 0.0
    return Material(name.strip(), density, colour, max(bend, 0.0))


def _is_colour(text: str) -> bool:
    if len(text) != 7 or not text.startswith("#"):
        return False
    try:
        int(text[1:], 16)
    except ValueError:
        return False
    return True


def part_material(doc: Document) -> Material | None:
    """The part's material, or None."""
    return from_data(doc.material)


def library(user: dict[str, float] | None = None) -> list[Material]:
    """The materials offered: FDCAD's, with the user's densities over them and the user's
    own materials after them (the densities in Preferences, Printing)."""
    out = {m.name: m for m in LIBRARY}
    for name, density in (user or {}).items():
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(density, (int, float)) or density <= 0:
            continue
        base = out.get(name.strip())
        if base is None:
            out[name.strip()] = Material(name.strip(), float(density))
        else:
            out[base.name] = Material(base.name, float(density), base.colour, base.min_bend)
    return list(out.values())


def density_text(density: float) -> str:
    """A density in both systems, for labels: "1.24 g/cm3 (0.0448 lb/in3)"."""
    return f"{density:g} g/cm3 ({density * LB_PER_IN3:.4g} lb/in3)"


def min_bend_of(name: str) -> float:
    """The library's smallest bend ratio for a material name, 0 when not known."""
    for material in LIBRARY:
        if material.name == name:
            return material.min_bend
    return 0.0
