"""Bodies a cut or boss acts on (TR33, D697)."""

from __future__ import annotations

import pytest
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import solids
from fdcad.core.io import fdef
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import Sketch, sketch_to_data
from fdcad.samples.make import SAMPLE_DIR, measure


def _split() -> Document:
    return fdef.loads((SAMPLE_DIR / "multibody_split_part.fdprt").read_text(encoding="utf-8"))


def _volumes(doc: Document) -> list[float]:
    report = RebuildEngine().rebuild(doc)
    assert report.body is not None
    return sorted(float(measure(s)["volume"]) for s in solids(report.body.shape))


def _body_ref(doc: Document, index: int) -> dict[str, object]:
    report = RebuildEngine().rebuild(doc)
    assert report.body is not None
    solid = solids(report.body.shape)[index]
    face = TopExp_Explorer(solid, TopAbs_FACE).Current()
    ref = reference_for(report.body, face)
    assert ref is not None
    return ref


def _cut_across(doc: Document, scope: str, bodies: list[dict[str, object]]) -> str:
    """A rectangle across the split plane, cut through all from the Front Plane."""
    sk = Sketch()
    pts = [(-40, -5), (40, -5), (40, 5), (-40, 5)]
    for i in range(4):
        sk.add_line(*pts[i], *pts[(i + 1) % 4])
    sketch = Feature(
        doc.new_feature_id(),
        "sketch",
        "Slot Sketch",
        refs={"plane": {"feature": "f2"}},
        data=sketch_to_data(sk),
    )
    params: dict[str, object] = {
        "operation": "cut",
        "end_condition": "through_all_both",
        "depth": Param("1", 1.0),
        "reverse": False,
    }
    refs: dict[str, object] = {"sketch": {"feature": sketch.id}}
    if scope == "selected":
        params["bodies_scope"] = "selected"
        refs["bodies"] = bodies
    cut = Feature(doc.new_feature_id(), "extrude", "Cut 1", params=params, refs=refs)  # type: ignore[arg-type]
    doc.features += [sketch, cut]
    return cut.id


def test_selected_bodies_cut_only_the_picked_one() -> None:
    before = _volumes(_split())
    assert len(before) == 2
    every = _split()
    _cut_across(every, "all", [])
    all_cut = _volumes(every)
    doc = _split()
    ref = _body_ref(doc, 0)
    fid = _cut_across(doc, "selected", [ref])
    report = RebuildEngine().rebuild(doc)
    assert report.results[fid].state is not FeatureState.ERROR
    one_cut = _volumes(doc)
    # One body is as before, the other as with All bodies.
    kept = [v for v in one_cut if any(abs(v - b) < 1e-6 for b in before)]
    cut = [v for v in one_cut if any(abs(v - c) < 1e-6 for c in all_cut)]
    assert len(kept) == 1 and len(cut) == 1 and kept != cut
    assert sum(one_cut) > sum(all_cut) + 1


def test_selected_with_no_picks_is_an_error() -> None:
    doc = _split()
    fid = _cut_across(doc, "selected", [])
    result = RebuildEngine().rebuild(doc).results[fid]
    assert result.state is FeatureState.ERROR


def test_all_bodies_is_the_old_behaviour() -> None:
    a, b = _split(), _split()
    _cut_across(a, "all", [])
    _cut_across(b, "all", [])
    b.features[-1].params.pop("bodies_scope", None)
    assert _volumes(a) == pytest.approx(_volumes(b))


def test_selected_bodies_hole_drills_only_the_picked_body() -> None:
    """Audit D6 item 2 (D736): only an extruded cut had a Selected bodies test."""
    from fdcad.core.features.solids import volume_of

    doc = _split()
    ref = _body_ref(doc, 0)
    sk = Sketch()
    for x in (-30, -10, 10, 30):
        sk.add_point(x, 20)
    above = Feature(  # 40 mm above the Front plane: holes drill down into both bodies
        doc.new_feature_id(),
        "ref_plane",
        "Plane 1",
        params={"method": "offset", "distance": Param("40", 40.0)},
        refs={"first": {"feature": "f2"}},
    )
    doc.features.append(above)
    sketch = Feature(
        doc.new_feature_id(),
        "sketch",
        "Hole Points",
        refs={"plane": {"feature": above.id}},
        data=sketch_to_data(sk),
    )
    params: dict[str, object] = {
        "hole_type": "simple",
        "end_condition": "through_all",
        "diameter": Param("3", 3.0),
        "bodies_scope": "selected",
    }
    hole = Feature(
        doc.new_feature_id(),
        "hole",
        "Hole 1",
        params=params,  # type: ignore[arg-type]
        refs={"sketch": {"feature": sketch.id}, "bodies": [ref]},
    )
    before = _volumes(_split())
    doc.features += [sketch, hole]
    report = RebuildEngine().rebuild(doc)
    assert report.results[hole.id].state is not FeatureState.ERROR, [
        i.message for i in report.results[hole.id].issues
    ]
    after = sorted(volume_of(s) for s in solids(report.body.shape))  # type: ignore[union-attr]
    unchanged = [v for v in after if any(abs(v - b) < 1e-6 for b in before)]
    assert len(unchanged) == 1  # the other body has no holes


def test_warnings_about_picked_bodies_reach_the_feature(monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit D8 item 3 (D746): the Bodies box dropped warnings such as a body found by
    its position."""
    from fdcad.core.features import bodies
    from fdcad.core.features.base import Issue

    real = bodies.body_indices

    def warned(*args: object, **kwargs: object) -> tuple[list[int], list[Issue]]:
        indices, issues = real(*args, **kwargs)  # type: ignore[arg-type]
        return indices, [*issues, Issue(FeatureState.WARNING, "found by position", code="moved")]

    monkeypatch.setattr(bodies, "body_indices", warned)
    doc = _split()
    fid = _cut_across(doc, "selected", [_body_ref(doc, 0)])
    codes = [i.code for i in RebuildEngine().rebuild(doc).results[fid].issues]
    assert "moved" in codes
