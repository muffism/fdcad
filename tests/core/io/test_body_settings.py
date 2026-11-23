"""Per body print settings in 3MF (TR383, D1207)."""

from __future__ import annotations

import zipfile
from pathlib import Path

from fdcad.core.io.export import MeshSettings, export_3mf
from fdcad.core.printing import body_settings as bs
from fdcad.core.rebuild.runner import rebuild
from tests.core.io.test_3mf_conformance import _check, _two_boxes

VALUES = {
    "layer_height": 0.12,
    "walls": 4,
    "infill": 35,
    "pattern": "gyroid",
    "supports": False,
    "extruder": 2,
}


def _texts(path: Path) -> str:
    with zipfile.ZipFile(path) as zf:
        return "".join(
            zf.read(n).decode() for n in zf.namelist() if n.endswith((".model", ".config"))
        )


def test_clean_keeps_known_values_in_range() -> None:
    raw = {**VALUES, "walls": 2.5, "infill": 150, "pattern": "stars", "x": 1, "supports": "yes"}
    assert bs.clean(raw) == {"layer_height": 0.12, "extruder": 2}
    assert bs.clean(None) == {}
    assert bs.clean({"walls": True}) == {}


def test_each_family_gets_its_keys(tmp_path: Path) -> None:
    out = tmp_path / "b.3mf"
    export_3mf(_two_boxes(), out, body_settings=[{}, VALUES])
    text = _texts(out)
    for key in (
        'key="wall_loops" value="4"',
        'key="sparse_infill_density" value="35%"',
        'key="sparse_infill_pattern" value="gyroid"',
        'key="enable_support" value="0"',
        'key="layer_height" value="0.12"',
        'key="extruder" value="2"',
    ):
        assert key in text
    assert 'name="cura:wall_line_count" preserve="true">4<' in text
    assert 'name="cura:extruder_nr" preserve="true">1<' in text
    _check(out)
    prusa = tmp_path / "p.3mf"
    export_3mf(_two_boxes(), prusa, settings=MeshSettings(slicer="prusa"), body_settings=[VALUES])
    text = _texts(prusa)
    assert 'key="perimeters" value="4"' in text and 'key="fill_density" value="35%"' in text
    assert 'key="support_material" value="0"' in text
    plain = tmp_path / "x.3mf"
    export_3mf(_two_boxes(), plain, settings=MeshSettings(slicer="plain"), body_settings=[VALUES])
    assert "wall" not in _texts(plain) and "perimeters" not in _texts(plain)


def test_settings_follow_the_body() -> None:
    from fdcad.core.sketch.model import Sketch
    from tests.core.features.test_features import add_extrude, add_sketch, plate, rect

    doc, _ext = plate()
    s = Sketch()
    rect(s, 70, 0, 80, 10)
    add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 5.0)
    named = list(rebuild(doc).values())[-1].body
    doc.print_setup[bs.BODY_SETTINGS] = bs.with_settings(doc, named, 1, {"walls": 5})
    again = list(rebuild(doc).values())[-1].body
    assert bs.settings_of(doc, again) == [{}, {"walls": 5}]
    doc.print_setup[bs.BODY_SETTINGS] = bs.with_settings(doc, again, 1, {})
    assert doc.print_setup[bs.BODY_SETTINGS] == {}
