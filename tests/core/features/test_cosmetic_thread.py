"""Cosmetic threads (PHASE4_SPEC P4.2): metadata on shafts and holes, the display
pattern and the STEP file description."""

import math
from pathlib import Path
from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.cosmetic_thread import step_notes, thread_pattern
from fdcad.core.features.hole import defaults_for
from fdcad.core.io.export import export_step
from fdcad.core.io.step_notes import add_notes, read_notes
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Circle, Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, messages, volume
from tests.core.features.test_hole import add_hole, on_top


def shaft(radius: float = 5.0, length: float = 30.0) -> tuple[Document, str, str]:
    doc = new_document()
    s = Sketch()
    c = s.add_point(0, 0)
    eid = s.new_id()
    s.entities[eid] = Circle(eid, c, radius)
    sk = add_sketch(doc, s, {"feature": "f2"})
    return doc, add_extrude(doc, sk, length), eid


def end_edge_ref(doc: Document, ext: str, eid: str) -> dict[str, Any]:
    b = body(rebuild(doc), ext)
    edge = b.edge(f"edge({ext}/cap/end|{ext}/side/{eid})")
    assert edge is not None
    ref = reference_for(b, edge)
    assert ref is not None
    return ref


def add_thread(doc: Document, edge: dict[str, Any], **params: Any) -> str:
    fid = doc.new_feature_id()
    values: dict[str, Any] = {
        "diameter": Param("10", 10.0),
        "pitch": Param("1.5", 1.5),
        "end_condition": "blind",
        "length": Param("12", 12.0),
        "size": "M10",
    }
    values.update(params)
    doc.features.append(
        Feature(fid, "cosmetic_thread", "Thread", params=values, refs={"edge": [edge]})
    )
    return fid


def test_shaft_thread_is_metadata_only() -> None:
    doc, ext, eid = shaft()
    fid = add_thread(doc, end_edge_ref(doc, ext, eid))
    results = rebuild(doc)
    res = results[fid]
    assert res.state is FeatureState.OK
    assert volume(body(results, fid).shape) == pytest.approx(math.pi * 25 * 30, rel=1e-9)
    (mark,) = res.threads
    assert not mark.internal and mark.length == 12.0 and mark.surface == pytest.approx(10.0)
    assert mark.origin[2] == pytest.approx(30.0) and mark.direction[2] == pytest.approx(-1.0)
    assert mark.label == "M10x1.5"
    pattern = thread_pattern(res.threads)
    assert pattern is not None


def test_full_length_and_reverse() -> None:
    doc, ext, eid = shaft()
    fid = add_thread(doc, end_edge_ref(doc, ext, eid), end_condition="full")
    assert rebuild(doc)[fid].threads[0].length == pytest.approx(30.0)


def test_thread_needs_a_round_edge() -> None:
    from tests.core.features.test_features import plate

    doc, ext = plate()
    b = body(rebuild(doc), ext)
    edge = b.edge(f"edge({ext}/cap/end|{ext}/side/e5)")
    assert edge is not None
    ref = reference_for(b, edge)
    assert ref is not None
    fid = add_thread(doc, ref)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "round edge" in messages(res)


def test_tapped_hole_cosmetic_thread() -> None:
    doc, _ext, sk, top = on_top([(10, 10), (40, 40)])
    values = defaults_for("tapped", "iso", "M6")
    assert values["thread_diameter"] == 6.0
    fid = add_hole(doc, sk, "tapped", top, **{**values, "cosmetic_thread": True})
    marks = rebuild(doc)[fid].threads
    assert len(marks) == 2 and all(m.internal for m in marks)
    # The table's thread is 12 mm deep; the plate is 10 mm thick, and the mark ends
    # with the material (D1050). It read 12: the mark ran 2 mm out of the plate.
    assert marks[0].diameter == 6.0 and marks[0].length == pytest.approx(10.0)
    assert marks[0].surface == pytest.approx(5.0)
    doc.feature(fid).params["cosmetic_thread"] = False
    assert rebuild(doc)[fid].threads == []


def test_a_thread_mark_in_thick_material_keeps_its_depth() -> None:
    """D1050: only the material limits a mark. In a 30 mm plate the 12 mm thread is whole."""
    from tests.core.features.test_features import plate
    from tests.core.features.test_hole import face_ref, points_sketch

    doc, ext = plate(30.0)
    top = face_ref(doc, ext, "cap/end")
    sk = points_sketch(doc, top, [(25, 25)])
    values = defaults_for("tapped", "iso", "M6")
    fid = add_hole(doc, sk, "tapped", top, **{**values, "cosmetic_thread": True})
    marks = rebuild(doc)[fid].threads
    assert len(marks) == 1 and marks[0].length == pytest.approx(12.0)


def test_step_description_holds_the_threads(tmp_path: Path) -> None:
    doc, ext, eid = shaft()
    fid = add_thread(doc, end_edge_ref(doc, ext, eid))
    results = rebuild(doc)
    notes = step_notes(results[fid].threads)
    assert notes[0].startswith("Cosmetic thread M10x1.5 external")
    path = tmp_path / "shaft.step"
    export_step(body(results, fid).shape, path, notes=notes)
    text = path.read_text(encoding="latin-1")
    assert notes[0] in read_notes(text)
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader

    reader = STEPControl_Reader()
    assert reader.ReadFile(str(path)) == IFSelect_RetDone
    reader.TransferRoots()
    assert volume(reader.OneShape()) == pytest.approx(math.pi * 25 * 30, rel=1e-6)


def test_add_notes_quotes() -> None:
    text = "HEADER;\nFILE_DESCRIPTION(('Open CASCADE Model'),'2;1');\n"
    out = add_notes(text, ["It's M5"])
    assert read_notes(out) == ["Open CASCADE Model", "It's M5"]


def test_a_thread_longer_than_its_face_is_shown_as_long_as_the_face() -> None:
    """D2647 (bug hunt round 10b O9): a 50 mm thread on a 30 mm shaft was stored,
    drawn and written to STEP 50 mm long, with no message."""
    doc, ext, eid = shaft(radius=5.0, length=30.0)
    fid = add_thread(doc, end_edge_ref(doc, ext, eid), length=Param("50", 50.0))
    result = rebuild(doc)[fid]
    assert result.state is FeatureState.WARNING
    assert [i.code for i in result.issues] == ["thread_too_long"]
    assert result.threads[0].length == pytest.approx(30.0)
    assert doc.feature(fid).params["length"] == Param("50", 50.0)  # the typed value stays
    doc.feature(fid).params["length"] = Param("12", 12.0)
    result = rebuild(doc)[fid]
    assert result.state is FeatureState.OK and result.threads[0].length == 12.0
