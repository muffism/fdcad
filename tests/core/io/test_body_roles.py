"""Body roles for printing in 3MF (TR382, D796)."""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree

from fdcad.core.io.export import MeshSettings, export_3mf
from fdcad.core.printing import body_roles as br
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import add_extrude, add_sketch, plate, rect
from tests.core.io.test_3mf_conformance import _check, _two_boxes

CORE = "{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}"


def _model(package: zipfile.ZipFile) -> ElementTree.Element:
    return ElementTree.fromstring(package.read("3D/3dmodel.model"))


def test_default_form_writes_model_settings_and_cura_marks(tmp_path: Path) -> None:
    out = tmp_path / "roles.3mf"
    export_3mf(_two_boxes(), out, name="Plate", roles=[br.PART, br.NEGATIVE])
    package = _check(out)  # still valid 3MF with the Cura metadata
    model = _model(package)
    objects = model.findall(f"{CORE}resources/{CORE}object")
    assembly = objects[-1]
    item = model.find(f"{CORE}build/{CORE}item")
    assert item is not None and item.get("objectid") == assembly.get("id")
    parts = [c.get("objectid") for c in assembly.iter(f"{CORE}component")]
    config = ElementTree.fromstring(package.read("Metadata/model_settings.config"))
    obj = config.find("object")
    assert obj is not None and obj.get("id") == assembly.get("id")
    assert [(p.get("id"), p.get("subtype")) for p in obj.findall("part")] == [
        (parts[0], "normal_part"),
        (parts[1], "negative_part"),
    ]
    cura = [m.get("name") for m in objects[1].iter(f"{CORE}metadata")]
    assert cura == ["cura:anti_overhang_mesh"]
    assert list(objects[0].iter(f"{CORE}metadata")) == []
    assert "PrusaSlicer" not in package.read("3D/3dmodel.model").decode()
    assert "Metadata/Slic3r_PE_model.config" not in package.namelist()


def test_prusa_form_writes_one_object_with_triangle_ranges(tmp_path: Path) -> None:
    out = tmp_path / "prusa.3mf"
    settings = MeshSettings(slicer="prusa")
    export_3mf(_two_boxes(), out, name="Plate", settings=settings, roles=[br.PART, br.MODIFIER])
    package = _check(out)
    model = _model(package)
    objects = model.findall(f"{CORE}resources/{CORE}object")
    assert len(objects) == 1
    triangles = len(list(objects[0].iter(f"{CORE}triangle")))
    config = ElementTree.fromstring(package.read("Metadata/Slic3r_PE_model.config"))
    obj = config.find("object")
    assert obj is not None and obj.get("id") == objects[0].get("id")
    assert obj.get("instances_count") == "1"
    ranges = [(int(v.get("firstid", -1)), int(v.get("lastid", -1))) for v in obj.findall("volume")]
    assert ranges[0][0] == 0 and ranges[-1][1] == triangles - 1
    assert ranges[1][0] == ranges[0][1] + 1  # no gaps, no overlaps
    kinds = [
        m.get("value") for v in obj.findall("volume") for m in v if m.get("key") == "volume_type"
    ]
    assert kinds == ["ModelPart", "ParameterModifier"]
    assert all(m.get("type") in ("object", "volume") for m in obj.iter("metadata"))
    assert "Metadata/model_settings.config" not in package.namelist()


def test_no_roles_no_settings_files(tmp_path: Path) -> None:
    for slicer in br.SLICER_FORMS:
        out = tmp_path / f"{slicer}.3mf"
        export_3mf(_two_boxes(), out, settings=MeshSettings(slicer=slicer), roles=[br.PART] * 2)
        names = _check(out).namelist()
        assert not any(n.endswith(".config") for n in names)


def test_roles_follow_the_body_through_rebuilds() -> None:
    from fdcad.core.sketch.model import Sketch

    doc, _ext = plate()
    s = Sketch()
    rect(s, 70, 0, 80, 10)
    add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 5.0)
    named = list(rebuild(doc).values())[-1].body
    assert br.roles_of(doc, named) == [br.PART, br.PART]
    doc.print_setup[br.BODY_ROLES] = br.with_roles(doc, named, [1], br.BLOCKER)
    assert br.roles_of(doc, named) == [br.PART, br.BLOCKER]
    again = list(rebuild(doc).values())[-1].body
    assert br.roles_of(doc, again) == [br.PART, br.BLOCKER]
    doc.print_setup[br.BODY_ROLES] = br.with_roles(doc, again, [1], br.PART)
    assert doc.print_setup[br.BODY_ROLES] == {}
    doc.print_setup[br.BODY_ROLES] = {"x": "wrong", 3: "part"}
    assert br.roles_of(doc, again) == [br.PART, br.PART]


def test_status_line() -> None:
    assert br.status_line(br.SLICER_DEFAULT, [br.PART]) == ""
    line = br.status_line(br.SLICER_DEFAULT, [br.PART, br.NEGATIVE])
    assert "Bambu Studio, OrcaSlicer: all roles kept" in line and "not cut" in line
    assert "not cut" not in br.status_line(br.SLICER_DEFAULT, [br.PART, br.MODIFIER])
    assert br.status_line(br.SLICER_PRUSA, [br.ENFORCER]).startswith("PrusaSlicer: all roles")


def test_old_mesh_settings_load_with_the_default_form() -> None:
    assert MeshSettings.from_data({"deviation": 0.02}).slicer == "default"
    assert MeshSettings.from_data({"slicer": "nope"}) == MeshSettings()


def test_targets_cura_only_and_plain(tmp_path: Path) -> None:
    """TR385 (D1206): Cura alone writes its marks only; plain writes no slicer data."""
    cura = tmp_path / "cura.3mf"
    export_3mf(
        _two_boxes(), cura, settings=MeshSettings(slicer="cura"), roles=[br.PART, br.MODIFIER]
    )
    with zipfile.ZipFile(cura) as package:
        assert not any(n.endswith(".config") for n in package.namelist())
        assert "cura:infill_mesh" in package.read("3D/3dmodel.model").decode()
    plain = tmp_path / "plain.3mf"
    export_3mf(
        _two_boxes(), plain, settings=MeshSettings(slicer="plain"), roles=[br.PART, br.MODIFIER]
    )
    names = _check(plain).namelist()
    assert not any(n.endswith(".config") for n in names)
    with zipfile.ZipFile(plain) as package:
        assert "cura" not in package.read("3D/3dmodel.model").decode()
    assert "not written" in br.status_line(br.SLICER_PLAIN, [br.MODIFIER])
    assert set(br.TARGET_SUPPORT) == set(br.SLICER_TARGETS)
    assert MeshSettings.from_data({"slicer": "plain"}).slicer == "plain"
