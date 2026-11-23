"""A section view as file data (TUTORIAL_REVIEW_SPEC_2 TR213, DECISIONS D1604).

A section saved with the part sits in ``appearance["section"]``; a saved view may
carry one under its ``section`` key. Pure Python. Reading never fails: damaged
data gives None, so the part still opens without its section.
"""

from __future__ import annotations

import math
from typing import Any

from fdcad.core.document.model import Document
from fdcad.core.section import AxisSetting, PlaneSetting, Reference, SectionState

KEY = "section"


def _vec(v: tuple[float, float, float]) -> list[float]:
    return [float(c) for c in v]


def _read_vec(raw: Any) -> tuple[float, float, float]:
    if not isinstance(raw, list | tuple) or len(raw) != 3:
        raise ValueError("a section vector must be three numbers")
    x, y, z = (float(c) for c in raw)
    if not all(math.isfinite(c) for c in (x, y, z)):
        raise ValueError("a section vector must be finite")
    return x, y, z


def to_json(state: SectionState) -> dict[str, Any]:
    """One section as file data."""
    planes = []
    for p in state.planes[:3]:
        r = p.reference
        planes.append(
            {
                "origin": _vec(r.origin),
                "normal": _vec(r.normal),
                "x_dir": _vec(r.x_dir),
                "source": p.source,
                "reverse": p.reverse,
                "offset": p.offset,
                "rot_x": p.rot_x,
                "rot_y": p.rot_y,
                "color": p.color,
            }
        )
    out: dict[str, Any] = {
        "planes": planes,
        "show_cap": state.show_cap,
        "cap_color": state.cap_color,
    }
    if state.axis is not None:
        a = state.axis
        out["axis"] = {"point": _vec(a.point), "direction": _vec(a.direction), "angle": a.angle}
    if state.zones:
        out["zones"] = [list(z) for z in state.zones]
    if state.see_through:
        out["see_through"] = list(state.see_through)
        out["see_through_level"] = state.see_through_level
    if state.whole:
        out["whole"] = list(state.whole)
    return out


def from_json(raw: Any) -> SectionState | None:
    """Read a section, or None when it is missing or damaged."""
    if not isinstance(raw, dict):
        return None
    try:
        planes = []
        for p in raw.get("planes", [])[:3]:
            planes.append(
                PlaneSetting(
                    Reference(
                        _read_vec(p["origin"]), _read_vec(p["normal"]), _read_vec(p["x_dir"])
                    ),
                    str(p.get("source", "front")),
                    bool(p.get("reverse", False)),
                    float(p.get("offset", 0.0)),
                    float(p.get("rot_x", 0.0)),
                    float(p.get("rot_y", 0.0)),
                    str(p.get("color", raw.get("cap_color", "#D9822B"))),
                )
            )
        if not planes:
            return None
        axis = None
        if isinstance(raw.get("axis"), dict):
            a = raw["axis"]
            axis = AxisSetting(
                _read_vec(a["point"]), _read_vec(a["direction"]), float(a.get("angle", 0.0))
            )
        zones = [tuple(bool(s) for s in z) for z in raw.get("zones", []) if isinstance(z, list)]
        see = [int(i) for i in raw.get("see_through", []) if isinstance(i, int)]
        whole = [int(i) for i in raw.get("whole", []) if isinstance(i, int) and i >= 0]
        return SectionState(
            planes,
            axis,
            bool(raw.get("show_cap", True)),
            str(raw.get("cap_color", planes[0].color)),
            True,
            zones=zones,
            see_through=see,
            see_through_level=float(raw.get("see_through_level", 0.6)),
            whole=whole,
        )
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def saved(doc: Document) -> SectionState | None:
    """The section saved with the part, or None."""
    return from_json(doc.appearance.get(KEY))


def set_saved(doc: Document, data: dict[str, Any] | None) -> None:
    """Save a section (as file data) with the part, or remove it with None."""
    if data is None:
        doc.appearance.pop(KEY, None)
    else:
        doc.appearance[KEY] = data
