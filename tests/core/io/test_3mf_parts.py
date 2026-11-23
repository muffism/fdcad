"""Read slicer 3MF files as named parts with roles (TR386, D1205)."""

from __future__ import annotations

import io
import time
import zipfile
from pathlib import Path

import numpy as np
import pytest

from fdcad.core.io import mesh_import
from fdcad.core.io.export import MeshSettings, export_3mf
from fdcad.core.io.mesh_import import MeshImportError, read_3mf_parts
from fdcad.core.printing import body_roles as br
from tests.core.io.test_3mf_conformance import _two_boxes


@pytest.mark.parametrize("slicer", br.SLICER_FORMS)
def test_fdcad_files_read_back_with_names_and_roles(tmp_path: Path, slicer: str) -> None:
    out = tmp_path / f"{slicer}.3mf"
    export_3mf(
        _two_boxes(),
        out,
        name="Box",
        settings=MeshSettings(slicer=slicer),
        roles=[br.PART, br.NEGATIVE],
        titles=["Shell & lid", None],
    )
    parts = read_3mf_parts(out.read_bytes())
    assert [p.name for p in parts] == ["Shell & lid", "Box body 2"]
    assert [p.role for p in parts] == [br.PART, br.NEGATIVE]
    assert parts[0].mesh.triangle_count == 12 and parts[1].mesh.triangle_count == 12
    sizes = sorted(float(np.ptp(p.mesh.vertices, axis=0).max()) for p in parts)
    assert sizes == pytest.approx([5.0, 30.0])


def test_plain_objects_use_their_names_and_cura_marks(tmp_path: Path) -> None:
    out = tmp_path / "cura.3mf"
    export_3mf(_two_boxes(), out, name="Box", roles=[br.PART, br.MODIFIER])
    data = out.read_bytes()
    buffer = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as src, zipfile.ZipFile(buffer, "w") as dst:
        for name in src.namelist():
            if not name.endswith(".config"):  # Cura reads only the model
                dst.writestr(name, src.read(name))
    parts = read_3mf_parts(buffer.getvalue())
    assert [p.role for p in parts] == [br.PART, br.MODIFIER]
    assert parts[0].name == "Box body 1"


def _package(model: str, configs: dict[str, bytes] | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("3D/3dmodel.model", model)
        for name, text in (configs or {}).items():
            zf.writestr(name, text)
    return buffer.getvalue()


_TRI = (
    '<model unit="millimeter"><resources><object id="1" name="a"><mesh><vertices>'
    '<vertex x="0" y="0" z="0"/><vertex x="1" y="0" z="0"/><vertex x="0" y="1" z="0"/>'
    '<vertex x="0" y="0" z="1"/></vertices><triangles><triangle v1="0" v2="1" v3="2"/>'
    '<triangle v1="0" v2="1" v3="3"/></triangles></mesh></object></resources>'
    '<build><item objectid="1"/></build></model>'
)


def test_damaged_settings_are_left_out() -> None:
    bad = {
        "Metadata/model_settings.config": b'<config><object id="1"><part subtype="x">'
        b'<metadata key="name" value="&#xFFFF;&bogus;"/></part><part id="1" subtype="??">'
        b"<metadata/></part></object></config>",
        "Metadata/Slic3r_PE_model.config": b'<config><object id="1"><volume firstid="5" '
        b'lastid="2"/><volume firstid="0" lastid="99"></volume></object></config>',
    }
    parts = read_3mf_parts(_package(_TRI, bad))
    assert len(parts) == 1 and parts[0].mesh.triangle_count == 2
    assert parts[0].role == "part"


def test_huge_settings_are_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mesh_import, "MAX_3MF_CONFIG", 10)
    config = b'<config><object id="1"><part id="1" subtype="negative_part"/></object></config>'
    parts = read_3mf_parts(_package(_TRI, {"Metadata/model_settings.config": config}))
    assert parts[0].role == "part" and parts[0].name == "a"


def test_hostile_settings_read_fast() -> None:
    config = b"<config>" + b'<object id="1"><part id="1" ' * 20000 + b"</config>"
    start = time.perf_counter()
    read_3mf_parts(_package(_TRI, {"Metadata/model_settings.config": config}))
    assert time.perf_counter() - start < 2.0


def test_not_a_package() -> None:
    with pytest.raises(MeshImportError, match="Export"):
        read_3mf_parts(b"PK\x03\x04 broken")
