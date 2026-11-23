"""STEP import as a base body (PHASE3_SPEC P3.5, DECISIONS D290): embedding, healing
report, colours, naming, later features on top, and save and reopen."""

from __future__ import annotations

from typing import Any

import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

from fdcad.core.document.model import new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.import_step import new_step_import, part_from_step
from fdcad.core.features.solids import compound, solids, volume_of
from fdcad.core.io import fdef
from fdcad.core.io.embedded import decode, encode, new_block_id
from fdcad.core.io.step_import import StepImportError, read_step
from fdcad.core.naming.names import faces_of
from fdcad.core.rebuild.runner import rebuild
from fdcad.samples.step_source import colored_step_bytes


def _box_step(color: str = "#CC2222", top: str | None = "#2244EE") -> bytes:
    box = BRepPrimAPI_MakeBox(40.0, 30.0, 20.0).Shape()
    faces = [(f, top) for f in faces_of(box)[:1]] if top else []
    return colored_step_bytes(box, color, faces)


def test_encode_is_stable_and_round_trips() -> None:
    data = b"ISO-10303-21;" * 100
    assert encode(data) == encode(data)
    assert decode(encode(data)) == data


def test_block_ids_count_up() -> None:
    doc = new_document()
    assert new_block_id(doc) == "b1"
    doc.embedded["b1"] = {}
    doc.embedded["b7"] = {}
    assert new_block_id(doc) == "b8"


def test_read_step_keeps_colours() -> None:
    imported = read_step(_box_step())
    assert len(solids(imported.shape)) == 1
    assert imported.valid
    colors = sorted(c for _f, c in imported.face_colors)
    assert colors == ["#2244EE"] + ["#CC2222"] * 5


def test_open_shells_are_sewn_into_a_solid_and_reported() -> None:
    box = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    loose = compound(faces_of(box))
    imported = read_step(colored_step_bytes(loose, "#22AA44"))
    assert len(solids(imported.shape)) == 1
    assert len(imported.face_colors) == 6
    assert volume_of(imported.shape) == pytest.approx(1000.0, rel=1e-6)
    assert any("Joined 6 open surface pieces into 1 solid" in line for line in imported.report)


def test_open_surface_only_is_an_error() -> None:
    box = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    one_face = faces_of(box)[0]
    with pytest.raises(StepImportError, match="no closed solids"):
        read_step(colored_step_bytes(one_face))


def test_not_a_step_file() -> None:
    with pytest.raises(StepImportError, match="not a STEP file"):
        read_step(b"hello")


def test_part_from_step_builds_with_names_and_colours() -> None:
    doc = part_from_step("box.step", _box_step())
    feature = doc.features[-1]
    assert feature.type == "import_step" and feature.name == "Imported 1"
    assert doc.embedded["b1"]["type"] == "step"
    assert doc.embedded["b1"]["filename"] == "box.step"
    results = rebuild(doc)
    res = results[feature.id]
    assert res.state is FeatureState.OK
    assert res.body is not None
    assert volume_of(res.body.shape) == pytest.approx(40 * 30 * 20, rel=1e-9)
    names = [n for n, _f in res.body.faces]
    assert names == [f"{feature.id}/face/{k}" for k in range(1, 7)]
    colors = res.extras["face_colors"]
    assert sorted(colors.values()) == ["#2244EE"] + ["#CC2222"] * 5


def _cut_on_top(doc: Any) -> str:
    """A through all hole of radius 5 from a sketch on the imported top face."""
    from fdcad.core.sketch.model import Sketch
    from fdcad.samples.builder import face_ref, to_local
    from tests.core.features.test_features import add_extrude, add_sketch

    ref, plane = face_ref(doc, (0.0, 0.0, 1.0))
    u, v = to_local(plane, (20.0, 15.0, 20.0))
    sketch = Sketch()
    sketch.add_circle(u, v, 5.0)
    sid = add_sketch(doc, sketch, ref)
    return add_extrude(doc, sid, 1.0, operation="cut", end_condition="through_all", reverse=True)


def test_features_on_top_of_an_import_and_reopen(tmp_path: Any) -> None:
    doc = part_from_step("box.step", _box_step(top=None))
    cut = _cut_on_top(doc)
    results = rebuild(doc)
    assert results[cut].state is FeatureState.OK, results[cut].issues
    body = results[cut].body
    assert body is not None
    import math

    expected = 40 * 30 * 20 - math.pi * 25 * 20
    assert volume_of(body.shape) == pytest.approx(expected, rel=1e-6)
    path = tmp_path / "imported.fdef"
    fdef.save(doc, path)
    again = fdef.load(path)
    assert again.embedded == doc.embedded
    results2 = rebuild(again)
    body2 = results2[cut].body
    assert body2 is not None
    assert volume_of(body2.shape) == pytest.approx(expected, rel=1e-9)


def test_insert_into_a_part_keeps_a_separate_body_unless_merged() -> None:
    doc = part_from_step("box.step", _box_step(top=None))
    cyl = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(20, 15, 20), gp_Dir(0, 0, 1)), 5.0, 10.0).Shape()
    bid, block, feature = new_step_import(doc, "pin.step", colored_step_bytes(cyl))
    assert bid == "b2"
    doc.embedded[bid] = block
    doc.features.append(feature)
    res = rebuild(doc)[feature.id]
    assert res.body is not None and len(solids(res.body.shape)) == 2
    feature.params["merge"] = True
    res = rebuild(doc)[feature.id]
    assert res.body is not None and len(solids(res.body.shape)) == 1


def test_missing_block_is_a_feature_error() -> None:
    doc = part_from_step("box.step", _box_step())
    doc.embedded.clear()
    res = rebuild(doc)[doc.features[-1].id]
    assert res.state is FeatureState.ERROR
    assert "missing" in res.issues[0].message


def test_damaged_block_is_a_feature_error() -> None:
    doc = part_from_step("box.step", _box_step())
    doc.embedded["b1"]["data"] = "not base64!"
    res = rebuild(doc)[doc.features[-1].id]
    assert res.state is FeatureState.ERROR
    assert "damaged" in res.issues[0].message


def test_old_files_without_imports_still_save_the_same() -> None:
    doc = new_document()
    text = fdef.dumps(doc)
    assert '"embedded": {}' in text
    assert fdef.dumps(fdef.loads(text)) == text


def test_names_survive_a_later_feature_change() -> None:
    doc = part_from_step("box.step", _box_step())
    source = doc.features[-1].id
    cut = _cut_on_top(doc)
    first = rebuild(doc)[cut].body
    assert first is not None
    hole = doc.feature(cut)
    hole.params["reverse"] = True
    names_before = sorted(n for n, _f in first.faces if n.startswith(source))
    second = rebuild(doc)[cut].body
    assert second is not None
    assert sorted(n for n, _f in second.faces if n.startswith(source)) == names_before


def test_curves_and_points_outside_solids_are_reported() -> None:
    """Audit D item 6 (D722): a solid plus a free edge gave an empty report."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeVertex

    box = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
    edge = BRepBuilderAPI_MakeEdge(gp_Pnt(20, 0, 0), gp_Pnt(30, 0, 0)).Edge()
    point = BRepBuilderAPI_MakeVertex(gp_Pnt(50, 0, 0)).Vertex()
    imported = read_step(colored_step_bytes(compound([box, edge, point]), "#888888"))
    note = " ".join(imported.report)
    assert "1 curve" in note and "1 point" in note and "not part of a solid" in note
    plain = read_step(colored_step_bytes(box, "#888888"))
    assert not any("not part of a solid" in r for r in plain.report)
