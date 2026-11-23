"""Each feature's result on disk beside the finished part (PLAN 11.3 item 2, D1097)."""

from pathlib import Path

import pytest
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

from fdcad.core.cache import history
from fdcad.core.features.base import FeatureResult, FeatureState, Fix, Issue, ThreadMark
from fdcad.core.rebuild.engine import RebuildEngine
from tests.core.features.test_features import _hole, plate


def _volume(shape: object) -> float:
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props, 1e-6)
    return float(props.Mass())


def test_a_part_reopened_reuses_each_stored_feature(tmp_path: Path) -> None:
    # The finished part showed at once from the cache, but every feature was built again
    # behind it (40 s for the bike frame); with the history only quick ones are.
    doc, ext = plate()
    cut = _hole(doc, f"{ext}/cap/end")
    first = RebuildEngine().rebuild(doc)
    assert history.store_history(tmp_path, "part", first.results) >= 2
    stored = history.load_history(tmp_path, "part")
    assert [r.key for r in stored] == [
        r.key for r in first.results.values() if r.key in {s.key for s in stored}
    ]
    engine = RebuildEngine()
    history.seed(engine.cache, stored)
    again = engine.rebuild(doc)
    assert ext in again.reused and cut in again.reused
    assert again.body is not None and first.body is not None
    assert _volume(again.body.shape) == pytest.approx(_volume(first.body.shape), rel=1e-9)
    assert sorted(n for n, _ in again.body.faces) == sorted(n for n, _ in first.body.faces)
    assert again.body.face(f"{ext}/cap/end") is not None  # names still find their faces


def test_steps_share_their_faces_in_the_file(tmp_path: Path) -> None:
    doc, ext = plate()
    for _ in range(4):
        _hole(doc, f"{ext}/cap/end")
    report = RebuildEngine().rebuild(doc)
    history.store_history(tmp_path, "part", report.results)
    one = RebuildEngine().rebuild(plate()[0])
    history.store_history(tmp_path, "one", one.results)
    size = history.history_files(tmp_path, "part")[1].stat().st_size
    single = history.history_files(tmp_path, "one")[1].stat().st_size
    assert size < 4 * single  # five steps of the plate, not five plates


def test_results_of_another_build_are_never_reused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc, _ext = plate()
    history.store_history(tmp_path, "part", RebuildEngine().rebuild(doc).results)
    assert history.load_history(tmp_path, "part")
    monkeypatch.setattr(history, "code_stamp", lambda: "an older FDCAD")
    assert history.load_history(tmp_path, "part") == []


def test_a_damaged_history_is_ignored(tmp_path: Path) -> None:
    doc, _ext = plate()
    history.store_history(tmp_path, "part", RebuildEngine().rebuild(doc).results)
    meta, shapes = history.history_files(tmp_path, "part")
    shapes.write_bytes(b"not a shape")
    assert history.load_history(tmp_path, "part") == []
    meta.write_text("{", encoding="utf-8")
    assert history.load_history(tmp_path, "part") == []
    assert history.load_history(tmp_path, "missing") == []


def test_fixes_and_threads_come_back_as_they_were(tmp_path: Path) -> None:
    doc, _ext = plate()
    report = RebuildEngine().rebuild(doc)
    base = next(r for r in report.results.values() if r.body is not None and r.sketch is None)
    issue = Issue(
        FeatureState.WARNING,
        "Too thin",
        [Fix("Make Thicker", "add_to_param", {"param": "depth", "delta": 0.5})],
        ["f3/side/1"],
        "thin",
    )
    mark = ThreadMark((0, 0, 0), (0, 0, 1), 6.0, 1.0, 10.0, 5.0, True, "M6x1")
    result = FeatureResult(body=base.body, issues=[issue], key="k1", seconds=1.5)
    result.threads = [mark]
    result.extras = {"holes": [(1.0, 2.0, 3.0)], "count": 1, "report": ["One hole"]}
    history.store_history(tmp_path, "part", {"f9": result})
    (back,) = history.load_history(tmp_path, "part")
    assert back.issues == [issue] and back.threads == [mark]
    assert back.key == "k1" and back.seconds == 1.5
    assert back.extras == result.extras  # the hole table reads the centres (tuples)


def test_sketches_planes_and_unwritable_values_are_left_to_the_rebuild(tmp_path: Path) -> None:
    doc, _ext = plate()
    report = RebuildEngine().rebuild(doc)
    solid = next(r for r in report.results.values() if r.body is not None and r.sketch is None)
    odd = FeatureResult(
        body=solid.body,
        issues=[Issue(FeatureState.WARNING, "x", [Fix("Go", "go", {"shape": object()})])],
        key="odd",
    )
    written = history.store_history(tmp_path, "part", {**report.results, "odd": odd})
    keys = {r.key for r in history.load_history(tmp_path, "part")}
    assert len(keys) == written
    assert "odd" not in keys
    for r in report.results.values():
        if r.sketch is not None or r.plane is not None or r.datum is not None:
            assert r.key not in keys


def test_display_extras_with_shapes_and_tuples_are_stored(tmp_path: Path) -> None:
    # D2600: O-ring grooves, contours and measurements carry dicts, tuples and shapes in
    # their extras, so they were built again in the app after every reopen (35 s of the
    # machine bed's 47 s).
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.gp import gp_Pnt
    from OCP.TopoDS import TopoDS_Edge

    doc, _ext = plate()
    report = RebuildEngine().rebuild(doc)
    solid = next(r for r in report.results.values() if r.body is not None and r.sketch is None)
    edge = BRepBuilderAPI_MakeEdge(gp_Pnt(0, 0, 0), gp_Pnt(10, 0, 0)).Edge()
    extras = {
        "oring": {"squeeze": 0.2, "fill": 0.7},
        "label": ("Distance: 10 mm", (1.0, 2.0, 3.0)),
        "reference": edge,
        "curve": edge,
        "levels": [1.0, 2.5],
    }
    result = FeatureResult(body=solid.body, key="k1", extras=extras)
    assert history.store_history(tmp_path, "part", {"f9": result}) == 1
    (back,) = history.load_history(tmp_path, "part")
    assert back.extras["oring"] == extras["oring"]
    assert back.extras["label"] == extras["label"]  # a tuple again, with a tuple inside
    assert back.extras["levels"] == [1.0, 2.5]
    assert isinstance(back.extras["reference"], TopoDS_Edge)
    assert back.extras["reference"].IsSame(back.extras["curve"])
    odd = FeatureResult(body=solid.body, key="k2", extras={"mesh": object()})
    assert history.store_history(tmp_path, "odd", {"f9": odd}) == 0


def test_stored_names_are_made_only_when_asked_for(tmp_path: Path) -> None:
    # D2600: making every result's named faces on load took 7.6 s on the machine bed.
    doc, ext = plate()
    _hole(doc, f"{ext}/cap/end")
    first = RebuildEngine().rebuild(doc)
    history.store_history(tmp_path, "part", first.results)
    stored = history.load_history(tmp_path, "part")
    assert stored and all(isinstance(r.body, history.LazyNamedShape) for r in stored)
    body = stored[-1].body
    assert body is not None and body.__dict__["_faces"] is None  # nothing made yet
    original = first.results[list(first.results)[-1]].body
    assert original is not None
    assert sorted(n for n, _ in body.faces) == sorted(n for n, _ in original.faces)
    assert body.face(f"{ext}/cap/end") is not None
    assert all(r.__dict__.get("_stored_size") for r in stored)  # no sizing on seed
