"""Give the icon set its Datum look (DECISIONS D1034). Run once; safe to run again.

    uv run python tools/icon_duotone.py

Two changes to the SVG files in ``src/fdcad/ui/icons``:

1. **Body tint.** Every closed outline (a rectangle, circle, ellipse, polygon or a
   path whose every part closes) that had no fill gets a light fill in its own line
   colour, so parts, faces and pages read as solid shapes and not as wire. Dashed
   and half strength outlines stay empty: they stand for hidden or reference lines.
2. **Cut colour.** Tools that take material away draw their active part in ``#CUT``
   instead of ``#ACCENT``, so adding and removing never look alike.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

ICONS = Path(__file__).resolve().parents[1] / "src" / "fdcad" / "ui" / "icons"
#: Fill strength of a body in the line colour, and of an active shape.
BODY_TINT = "0.12"
ACTIVE_TINT = "0.2"
#: Shapes smaller than this (width and height) are marks, not bodies.
SMALL = 3.5
#: Tools that take material away.
CUT = frozenset(
    {
        "feature.extruded_cut",
        "feature.revolved_cut",
        "feature.swept_cut",
        "feature.lofted_cut",
        "feature.section_cut",
        "feature.hole",
        "feature.polygon_holes",
        "feature.drain_holes",
        "feature.perforation",
        "feature.vent",
        "feature.lightening_pockets",
        "feature.corner_relief",
        "feature.sheet_corner_relief",
        "feature.break_corner",
        "feature.shaft_shape",
        "feature.ring_groove",
        "feature.oring_groove",
        "feature.snap_groove",
        "feature.delete_body",
        "feature.delete_face",
        "feature.rip",
        "sketch.trim",
        "sketch.cut_away",
    }
)
_ELEMENT = re.compile(r"<(rect|circle|ellipse|polygon|path)\b[^>]*?/>")
_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)")


def _closed(tag: str, attrs: dict[str, str]) -> bool:
    if tag in ("rect", "polygon"):
        return True
    if tag == "circle":
        return float(attrs.get("r", "0")) * 2 >= SMALL
    if tag == "ellipse":
        return min(float(attrs.get("rx", "0")), float(attrs.get("ry", "0"))) * 2 >= SMALL / 2
    parts = [p for p in re.split(r"(?=[Mm])", attrs.get("d", "")) if p.strip()]
    if not parts or not all(p.strip()[-1] in "Zz" for p in parts):
        return False
    numbers = [float(n) for n in _NUMBER.findall(attrs.get("d", ""))]
    return len(numbers) >= 4  # even a box written with H and V has five


def _tint(match: re.Match[str]) -> str:
    text = match.group(0)
    node = ET.fromstring(text)
    attrs = node.attrib
    if "fill" in attrs or attrs.get("stroke") == "none":
        return text
    if "stroke-dasharray" in attrs or "stroke-opacity" in attrs or "opacity" in attrs:
        return text
    if not _closed(match.group(1), attrs):
        return text
    colour = attrs.get("stroke", "currentColor")
    strength = BODY_TINT if colour == "currentColor" else ACTIVE_TINT
    return f'{text[:-2].rstrip()} fill="{colour}" fill-opacity="{strength}"/>'


_GEOMETRY = ("d", "x", "y", "width", "height", "cx", "cy", "r", "rx", "ry", "points", "transform")


def _geometry(attrs: dict[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple((k, attrs[k]) for k in _GEOMETRY if k in attrs)


def restyle(name: str, text: str) -> str:
    """The icon's SVG text in the Datum look."""
    # An outline that already has the same shape filled under it is left alone.
    filled = set()
    for found in _ELEMENT.finditer(text):
        attrs = ET.fromstring(found.group(0)).attrib
        if attrs.get("fill", "none") != "none":
            filled.add(_geometry(attrs))

    def tint(match: re.Match[str]) -> str:
        if _geometry(ET.fromstring(match.group(0)).attrib) in filled:
            return match.group(0)
        return _tint(match)

    text = _ELEMENT.sub(tint, text)
    if name in CUT:
        text = text.replace("#ACCENT", "#CUT")
    return text


def main() -> int:
    """Rewrite every icon that changes; print how many did."""
    changed = 0
    for path in sorted(ICONS.glob("*.svg")):
        old = path.read_text(encoding="utf-8")
        new = restyle(path.stem, old)
        if new != old:
            path.write_text(new, encoding="utf-8", newline="\n")
            changed += 1
    print(f"{changed} icons changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
