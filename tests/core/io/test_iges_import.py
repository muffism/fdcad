"""IGES import with joining into a solid, and the gap a heal closes (TR31, D760)."""

from __future__ import annotations

from pathlib import Path

import pytest
from OCP.BRep import BRep_Builder
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt, gp_Trsf, gp_Vec
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS_Compound

from fdcad.core.features.solids import solids, volume_of
from fdcad.core.io.iges_import import IgesImportError, read_iges
from fdcad.core.naming.names import faces_of


def _iges(tmp_path: Path, faces: list) -> bytes:  # type: ignore[type-arg]
    """IGES bytes holding ``faces`` as loose surfaces (as most IGES files are)."""
    from OCP.IGESControl import IGESControl_Writer

    compound = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(compound)
    for face in faces:
        builder.Add(compound, face)
    writer = IGESControl_Writer("MM", 0)
    writer.AddShape(compound)
    writer.ComputeModel()
    path = tmp_path / "part.igs"
    assert writer.Write(str(path))
    return path.read_bytes()


def _box_faces() -> list:  # type: ignore[type-arg]
    return faces_of(BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 20.0, 10.0, 5.0).Shape())


def test_loose_surfaces_that_close_a_volume_become_a_solid(tmp_path: Path) -> None:
    imported = read_iges(_iges(tmp_path, _box_faces()), "Imported 1")
    assert len(solids(imported.shape)) == 1
    assert volume_of(imported.shape) == pytest.approx(1000.0, rel=1e-6)
    assert any("Joined 6 open surface pieces into 1 solid" in line for line in imported.report)


def test_a_missing_face_is_reported_with_where_the_gap_is(tmp_path: Path) -> None:
    data = _iges(tmp_path, _box_faces()[:-1])
    with pytest.raises(IgesImportError) as caught:
        read_iges(data, "Imported 1")
    message = str(caught.value)
    assert message.startswith("Imported 1: the surfaces do not close a volume")
    assert "1 gap" in message and "near (" in message
    assert "Heal" in message  # what to do next


def test_a_small_gap_closes_with_a_larger_heal_tolerance(tmp_path: Path) -> None:
    faces = _box_faces()
    move = gp_Trsf()
    move.SetTranslation(gp_Vec(0.0, 0.0, 0.05))  # the top face sits 0.05 mm too high
    top = max(faces, key=_centre_z)
    faces = [f.Moved(TopLoc_Location(move)) if f.IsSame(top) else f for f in faces]
    data = _iges(tmp_path, faces)
    with pytest.raises(IgesImportError, match="gap"):
        read_iges(data, "Imported 1")
    healed = read_iges(data, "Imported 1", gap=0.1)
    assert len(solids(healed.shape)) == 1
    assert volume_of(healed.shape) == pytest.approx(1000.0, rel=2e-2)


def _centre_z(face) -> float:  # type: ignore[no-untyped-def]
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, props)
    return props.CentreOfMass().Z()


def test_not_an_iges_file() -> None:
    with pytest.raises(IgesImportError, match="not an IGES file"):
        read_iges(b"hello", "Imported 1")


def test_a_part_opened_from_iges_rebuilds_to_the_solid(tmp_path: Path) -> None:
    from fdcad.core.features.base import FeatureState
    from fdcad.core.features.import_step import is_iges, part_from_step
    from fdcad.core.io import fdef
    from fdcad.core.rebuild.engine import RebuildEngine

    doc = part_from_step("part.IGS", _iges(tmp_path, _box_faces()))
    feature = doc.features[-1]
    assert feature.type == "import_step" and is_iges(doc, feature)
    report = RebuildEngine().rebuild(fdef.loads(fdef.dumps(doc)))  # the format is saved
    assert report.results[feature.id].state is not FeatureState.ERROR
    assert report.body is not None and volume_of(report.body.shape) == pytest.approx(1000.0)


def test_heal_gap_on_the_feature(tmp_path: Path) -> None:
    from fdcad.core.document.model import Param
    from fdcad.core.features.base import FeatureState
    from fdcad.core.features.import_step import part_from_step
    from fdcad.core.rebuild.engine import RebuildEngine

    faces = _box_faces()
    move = gp_Trsf()
    move.SetTranslation(gp_Vec(0.0, 0.0, 0.05))
    top = max(faces, key=_centre_z)
    faces = [f.Moved(TopLoc_Location(move)) if f.IsSame(top) else f for f in faces]
    doc = part_from_step("open.igs", _iges(tmp_path, faces))
    feature = doc.features[-1]
    result = RebuildEngine().rebuild(doc).results[feature.id]
    assert result.state is FeatureState.ERROR and "Heal" in result.issues[0].message
    feature.params["heal_gap"] = Param("0.1", 0.1)
    report = RebuildEngine().rebuild(doc)
    assert report.results[feature.id].state is not FeatureState.ERROR
    assert "Healed with a gap of 0.1 mm." in report.results[feature.id].extras["report"]


def test_replace_a_step_import_with_an_iges_file(tmp_path: Path) -> None:
    from fdcad.core.document.model import Feature
    from fdcad.core.features.import_replace import new_source

    feature = Feature("f5", "import_step", "Imported 1", refs={"source": {"embedded": "b1"}})
    from fdcad.core.document.model import new_document

    _bid, block = new_source(new_document(), feature, "new.iges", b"data")
    assert block["type"] == "step" and block["format"] == "iges"
