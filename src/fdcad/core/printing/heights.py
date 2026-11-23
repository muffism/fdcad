"""Settings by height: pauses, colour changes and setting changes at Z heights
(TR384, DECISIONS D1208).

The part keeps a list under ``print_setup.height_changes``; each entry has a
height ``z`` in mm above the print bed and a ``kind``: ``pause`` (for example to
drop in a magnet or a nut), ``colour`` (a filament change), or ``setting`` with
a ``key`` (layer height, infill density or wall count) and a ``value`` that holds
from that height up to the next change of the same key. 3MF export writes them in
the files Bambu Studio, OrcaSlicer and PrusaSlicer read; Cura and plain 3MF have
no place for them. No Qt, no kernel.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

HEIGHT_CHANGES = "height_changes"
KINDS = ("pause", "colour", "setting")
#: Setting keys by height, their limits, and each family's option name.
SETTING_KEYS = ("layer_height", "infill", "walls")
_LIMITS = {"layer_height": (0.01, 2.0), "infill": (0.0, 100.0), "walls": (0.0, 50.0)}
_OPTIONS = {"layer_height": "layer_height", "infill": "fill_density", "walls": "perimeters"}
_BAMBU_OPTIONS = {
    "layer_height": "layer_height",
    "infill": "sparse_infill_density",
    "walls": "wall_loops",
}
#: The most changes kept.
LIMIT = 200


def clean(raw: Any) -> list[dict[str, Any]]:
    """The valid changes sorted by height; damaged entries are left out."""
    if not isinstance(raw, list):
        return []
    out = []
    for entry in raw[:LIMIT]:
        if not isinstance(entry, dict):
            continue
        z, kind = entry.get("z"), entry.get("kind")
        if isinstance(z, bool) or not isinstance(z, int | float) or not 0 < z < 100000:
            continue
        if kind not in KINDS:
            continue
        item: dict[str, Any] = {"z": float(z), "kind": kind}
        if kind == "setting":
            key, value = entry.get("key"), entry.get("value")
            if key not in SETTING_KEYS or isinstance(value, bool):
                continue
            if not isinstance(value, int | float):
                continue
            lo, hi = _LIMITS[key]
            if not lo <= value <= hi:
                continue
            item.update(key=key, value=float(value))
        note = entry.get("note")
        if isinstance(note, str) and note.strip():
            item["note"] = note.strip()[:200]
        out.append(item)
    return sorted(out, key=lambda e: e["z"])


def _value(key: str, value: float) -> str:
    if key == "infill":
        return f"{value:g}%"
    if key == "walls":
        return str(int(value))
    return f"{value:g}"


def ranges(
    changes: Sequence[dict[str, Any]], top: float
) -> list[tuple[float, float, dict[str, str]]]:
    """Height ranges (low, high, key to value) from the setting changes, up to ``top``."""
    keys = {e["z"] for e in changes if e["kind"] == "setting"}
    cuts = sorted(z for z in keys if z < top)
    out = []
    for i, low in enumerate(cuts):
        high = cuts[i + 1] if i + 1 < len(cuts) else top
        active: dict[str, str] = {}
        for e in changes:
            if e["kind"] == "setting" and e["z"] <= low:
                active[e["key"]] = _value(e["key"], e["value"])
        out.append((low, high, active))
    return out


def _gcode_rows(changes: Sequence[dict[str, Any]], attr: str, pause: str) -> str:
    rows = []
    for e in changes:
        if e["kind"] == "pause":
            rows.append(
                f'<{attr}="{e["z"]:g}" type="1" extruder="1" color="" extra="" gcode="{pause}"/>'
            )
        elif e["kind"] == "colour":
            rows.append(
                f'<{attr}="{e["z"]:g}" type="0" extruder="1" color="" extra="" gcode="M600"/>'
            )
    return "".join(rows)


def prusa_files(changes: Sequence[dict[str, Any]], object_id: int, top: float) -> dict[str, str]:
    """PrusaSlicer's pause and colour change file and its layer ranges file."""
    out = {}
    rows = _gcode_rows(changes, "code print_z", "M601")
    if rows:
        out["Metadata/Prusa_Slicer_custom_gcode_per_print_z.xml"] = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            f'<custom_gcodes_per_print_z>{rows}<mode value="SingleExtruder"/>'
            "</custom_gcodes_per_print_z>"
        )
    spans = ranges(changes, top)
    if spans:
        out["Metadata/Prusa_Slicer_layer_config_ranges.xml"] = _ranges_xml(
            spans, object_id, _OPTIONS
        )
    return out


def bambu_files(changes: Sequence[dict[str, Any]], object_id: int, top: float) -> dict[str, str]:
    """Bambu Studio and OrcaSlicer's pause and colour change file and layer ranges."""
    out = {}
    rows = _gcode_rows(changes, "layer top_z", "M400 U1")
    if rows:
        out["Metadata/custom_gcode_per_layer.xml"] = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<custom_gcodes_per_layer><plate><plate_info id="1"/>'
            f'{rows}<mode value="SingleExtruder"/></plate></custom_gcodes_per_layer>'
        )
    spans = ranges(changes, top)
    if spans:
        out["Metadata/layer_config_ranges.xml"] = _ranges_xml(spans, object_id, _BAMBU_OPTIONS)
    return out


def _ranges_xml(
    spans: list[tuple[float, float, dict[str, str]]], object_id: int, names: dict[str, str]
) -> str:
    body = "".join(
        f'<range min_z="{low:g}" max_z="{high:g}">'
        + "".join(f'<option opt_key="{names[k]}">{v}</option>' for k, v in sorted(active.items()))
        + "</range>"
        for low, high, active in spans
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<objects><object id="{object_id}">{body}</object></objects>'
    )
