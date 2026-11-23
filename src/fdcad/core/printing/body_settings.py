"""Per body print settings (TR383, DECISIONS D1207).

A body can carry a small table of slicer settings: layer height, wall count,
infill density and pattern, supports on or off, and the extruder. Each is
optional. They are kept in the part's print setup under ``body_settings``, a
face name of the body (its mark, as for print roles, D796) to the values, and
3MF export writes them in the keys each slicer family reads. FDCAD never also
changes the geometry for them. No Qt and no kernel calls beyond small topology
queries.
"""

from __future__ import annotations

from typing import Any

from fdcad.core.document.model import Document
from fdcad.core.naming.names import NamedShape

BODY_SETTINGS = "body_settings"
#: Infill patterns every target reads, and each family's name for them.
PATTERNS = ("grid", "gyroid", "cubic", "lines", "honeycomb")
_BAMBU_PATTERN = {"lines": "line"}
_PRUSA_PATTERN = {"lines": "line"}
_CURA_PATTERN = {"honeycomb": "triangles"}  # Cura has no honeycomb: the nearest
#: Limits of each value.
LIMITS = {"layer_height": (0.01, 2.0), "walls": (0, 50), "infill": (0, 100), "extruder": (1, 16)}


def clean(raw: Any) -> dict[str, Any]:
    """Only the settings that are known and in range."""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Any] = {}
    for key, kind in (
        ("layer_height", float),
        ("walls", int),
        ("infill", float),
        ("extruder", int),
    ):
        value = raw.get(key)
        if isinstance(value, bool) or not isinstance(value, int | float):
            continue
        lo, hi = LIMITS[key]
        if lo <= value <= hi and (kind is float or float(value).is_integer()):
            out[key] = kind(value)
    if raw.get("pattern") in PATTERNS:
        out["pattern"] = raw["pattern"]
    if isinstance(raw.get("supports"), bool):
        out["supports"] = raw["supports"]
    return out


def stored(doc: Document) -> dict[str, dict[str, Any]]:
    """The saved marks and settings; anything damaged is left out."""
    raw = (doc.print_setup or {}).get(BODY_SETTINGS)
    if not isinstance(raw, dict):
        return {}
    out = {}
    for k, v in raw.items():
        values = clean(v)
        if isinstance(k, str) and values:
            out[k] = values
    return out


def settings_of(doc: Document, named: NamedShape | None) -> list[dict[str, Any]]:
    """The settings of every body of ``named`` in Solid Bodies order ({} for none)."""
    from fdcad.core.body_visibility import body_names

    marks = stored(doc)
    if not marks:
        return [{} for _ in body_names(named)]
    return [
        next((marks[n] for n in sorted(names) if n in marks), {}) for names in body_names(named)
    ]


def with_settings(
    doc: Document, named: NamedShape | None, index: int, values: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """The ``body_settings`` value after giving the body at ``index`` ``values``
    (empty takes its settings off)."""
    from fdcad.core.body_visibility import body_names, mark_of

    all_names = body_names(named)
    out = dict(stored(doc))
    if not 0 <= index < len(all_names):
        return out
    for name in all_names[index]:
        out.pop(name, None)
    mark = mark_of(all_names[index])
    kept = clean(values)
    if mark is not None and kept:
        out[mark] = kept
    return out


def _percent(value: float) -> str:
    return f"{value:g}%"


def bambu_keys(values: dict[str, Any]) -> list[tuple[str, str]]:
    """Bambu Studio and OrcaSlicer part settings keys and values."""
    out = []
    if "layer_height" in values:
        out.append(("layer_height", f"{values['layer_height']:g}"))
    if "walls" in values:
        out.append(("wall_loops", str(values["walls"])))
    if "infill" in values:
        out.append(("sparse_infill_density", _percent(values["infill"])))
    if "pattern" in values:
        out.append(
            ("sparse_infill_pattern", _BAMBU_PATTERN.get(values["pattern"], values["pattern"]))
        )
    if "supports" in values:
        out.append(("enable_support", "1" if values["supports"] else "0"))
    if "extruder" in values:
        out.append(("extruder", str(values["extruder"])))
    return out


def prusa_keys(values: dict[str, Any]) -> list[tuple[str, str]]:
    """PrusaSlicer volume settings keys and values."""
    out = []
    if "layer_height" in values:
        out.append(("layer_height", f"{values['layer_height']:g}"))
    if "walls" in values:
        out.append(("perimeters", str(values["walls"])))
    if "infill" in values:
        out.append(("fill_density", _percent(values["infill"])))
    if "pattern" in values:
        out.append(("fill_pattern", _PRUSA_PATTERN.get(values["pattern"], values["pattern"])))
    if "supports" in values:
        out.append(("support_material", "1" if values["supports"] else "0"))
    if "extruder" in values:
        out.append(("extruder", str(values["extruder"])))
    return out


def cura_keys(values: dict[str, Any]) -> list[tuple[str, str]]:
    """Cura per model settings (``cura:`` metadata). Cura has no layer height per model."""
    out = []
    if "walls" in values:
        out.append(("cura:wall_line_count", str(values["walls"])))
    if "infill" in values:
        out.append(("cura:infill_sparse_density", f"{values['infill']:g}"))
    if "pattern" in values:
        out.append(("cura:infill_pattern", _CURA_PATTERN.get(values["pattern"], values["pattern"])))
    if "supports" in values:
        out.append(("cura:support_enable", "True" if values["supports"] else "False"))
    if "extruder" in values:
        out.append(("cura:extruder_nr", str(values["extruder"] - 1)))  # Cura counts from 0
    return out
