"""Pauses, colour changes and settings by height in 3MF (TR384, D1208)."""

from __future__ import annotations

import zipfile
from pathlib import Path

from fdcad.core.io.export import MeshSettings, export_3mf
from fdcad.core.printing import heights as hz
from tests.core.io.test_3mf_conformance import _check, _two_boxes

CHANGES = [
    {"z": 12.0, "kind": "setting", "key": "infill", "value": 40},
    {"z": 5.0, "kind": "pause", "note": "magnets"},
    {"z": 20.0, "kind": "colour"},
    {"z": 12.0, "kind": "setting", "key": "layer_height", "value": 0.1},
    {"z": 25.0, "kind": "setting", "key": "infill", "value": 10},
]


def test_clean_sorts_and_drops_damaged_entries() -> None:
    raw = [
        *CHANGES,
        {"z": -1, "kind": "pause"},
        {"z": 3, "kind": "jump"},
        "x",
        {"z": 4, "kind": "setting", "key": "walls", "value": 99},
        {"z": True, "kind": "pause"},
    ]
    out = hz.clean(raw)
    assert [e["z"] for e in out] == [5.0, 12.0, 12.0, 20.0, 25.0]
    assert out[0]["note"] == "magnets"
    assert hz.clean("nope") == []


def test_ranges_hold_until_the_next_change() -> None:
    spans = hz.ranges(hz.clean(CHANGES), 30.0)
    assert spans == [
        (12.0, 25.0, {"infill": "40%", "layer_height": "0.1"}),
        (25.0, 30.0, {"infill": "10%", "layer_height": "0.1"}),
    ]


def _files(path: Path) -> dict[str, str]:
    with zipfile.ZipFile(path) as zf:
        return {n: zf.read(n).decode() for n in zf.namelist() if n.startswith("Metadata/")}


def test_each_family_gets_its_files(tmp_path: Path) -> None:
    out = tmp_path / "b.3mf"
    export_3mf(_two_boxes(), out, heights=CHANGES)
    files = _files(out)
    gcode = files["Metadata/custom_gcode_per_layer.xml"]
    assert 'top_z="5" type="1"' in gcode and 'gcode="M400 U1"' in gcode
    assert 'top_z="20" type="0"' in gcode
    ranges = files["Metadata/layer_config_ranges.xml"]
    assert (
        '<range min_z="12" max_z="25">' in ranges
        and 'opt_key="sparse_infill_density">40%' in ranges
    )
    assert 'max_z="30"' in ranges  # up to the top of the part
    _check(out)
    prusa = tmp_path / "p.3mf"
    export_3mf(_two_boxes(), prusa, settings=MeshSettings(slicer="prusa"), heights=CHANGES)
    files = _files(prusa)
    assert 'print_z="5" type="1"' in files["Metadata/Prusa_Slicer_custom_gcode_per_print_z.xml"]
    assert 'opt_key="fill_density">40%' in files["Metadata/Prusa_Slicer_layer_config_ranges.xml"]
    for target in ("cura", "plain"):
        other = tmp_path / f"{target}.3mf"
        export_3mf(_two_boxes(), other, settings=MeshSettings(slicer=target), heights=CHANGES)
        assert not any("gcode" in n or "ranges" in n for n in _files(other))
