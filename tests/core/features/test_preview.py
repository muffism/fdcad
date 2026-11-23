"""Live preview geometry, merge result and default feature names (W6.4, W6.2, W6.6)."""

import copy

import pytest

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features.base import FeatureState, PreviewHandle
from fdcad.core.features.names import default_name
from fdcad.core.features.preview import body_before, build_preview
from fdcad.core.features.solids import solids
from fdcad.core.rebuild.engine import RebuildEngine, RebuildReport
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, bounds, plate, rect, volume


def rebuild(doc: Document) -> RebuildReport:
    return RebuildEngine().rebuild(doc)


def test_preview_of_new_extrude_is_its_own_solid() -> None:
    doc, ext = plate(10.0)
    report = rebuild(doc)
    feature = copy.deepcopy(doc.feature(ext))
    doc.features.pop()  # a new feature is not in the document yet
    feature.params["depth"] = Param("25", 25.0)
    geo = build_preview(doc, feature, report.results)
    assert geo.error is None and geo.shape is not None
    assert volume(geo.shape) == pytest.approx(50 * 50 * 25)
    [handle] = geo.handles
    assert handle.param == "depth" and handle.value == 25.0
    assert handle.tip == pytest.approx((25.0, 25.0, 25.0))


def test_preview_of_cut_shows_the_tool_not_the_part() -> None:
    doc, _ext = plate(10.0)
    s = Sketch()
    rect(s, 10, 10, 20, 20)
    sk = add_sketch(doc, s, {"feature": "f2"})
    report = rebuild(doc)
    cut = Feature(
        "new",
        "extrude",
        "Cut 1",
        params={"operation": "cut", "end_condition": "through_all", "depth": Param("1", 1.0)},
        refs={"sketch": {"feature": sk}},
    )
    geo = build_preview(doc, cut, report.results)
    assert geo.shape is not None
    assert bounds(geo.shape)[:2] == pytest.approx((10, 10))
    assert geo.handles == []  # through all has no depth to drag
    assert body_before(doc, cut, report.results) is report.results[sk].body


def test_mid_plane_and_two_direction_handles() -> None:
    doc, ext = plate(10.0, end_condition="mid_plane")
    report = rebuild(doc)
    geo = build_preview(doc, doc.feature(ext), report.results)
    [h] = geo.handles
    assert h.scale == 2.0 and h.tip[2] == pytest.approx(5.0)
    assert h.value_at(7.0) == pytest.approx(14.0)
    doc2, ext2 = plate(10.0, end_condition="two_directions", depth2=4.0)
    geo2 = build_preview(doc2, doc2.feature(ext2), rebuild(doc2).results)
    assert [h.param for h in geo2.handles] == ["depth", "depth2"]
    assert geo2.handles[1].tip[2] == pytest.approx(-4.0)


def test_preview_errors_come_back_as_messages() -> None:
    doc, ext = plate(10.0)
    report = rebuild(doc)
    feature = copy.deepcopy(doc.feature(ext))
    feature.params["depth"] = Param("0", 0.0)
    geo = build_preview(doc, feature, report.results)
    assert geo.shape is None and geo.error and "greater than zero" in geo.error
    missing = copy.deepcopy(feature)
    missing.refs["sketch"] = {"feature": "nope"}
    assert build_preview(doc, missing, {}).error


def test_handle_tip_follows_value() -> None:
    h = PreviewHandle("depth", (0, 0, 0), (1, 0, 0), 8.0)
    assert h.tip == (8.0, 0.0, 0.0)


def test_merge_off_keeps_a_separate_body() -> None:
    doc, _ext = plate(10.0)
    s = Sketch()
    rect(s, 100, 0, 120, 20)
    sk = add_sketch(doc, s, {"feature": "f2"})
    second = add_extrude(doc, sk, 5.0, merge=False)
    report = rebuild(doc)
    assert report.results[second].state is FeatureState.OK
    assert report.body is not None and len(solids(report.body.shape)) == 2
    s2 = Sketch()
    rect(s2, 40, 0, 60, 20)  # overlapping: merged into one body by default
    sk2 = add_sketch(doc, s2, {"feature": "f2"})
    add_extrude(doc, sk2, 5.0)
    report = rebuild(doc)
    assert report.body is not None and len(solids(report.body.shape)) == 2


def test_default_names() -> None:
    doc = new_document()
    assert default_name(doc, "extrude", "boss") == "Extrude 1"
    assert default_name(doc, "extrude", "cut") == "Cut 1"
    assert default_name(doc, "revolve", "boss") == "Revolve 1"
    assert default_name(doc, "revolve", "cut") == "Revolve Cut 1"
    doc.features.append(Feature("a", "extrude", "Extrude 1"))
    doc.features.append(Feature("b", "extrude", "Extrude 3"))
    assert default_name(doc, "extrude") == "Extrude 4"
    assert default_name(doc, "extrude", "cut") == "Cut 1"


def test_opening_a_sample_keeps_its_stored_names() -> None:
    """Names are data: the default name scheme never renames a saved feature."""
    from pathlib import Path

    from fdcad.core.io import fdef

    path = Path(__file__).parents[3] / "samples" / "bracket.fdprt"
    stored = [f["name"] for f in __import__("json").loads(path.read_text())["features"]]
    doc = fdef.load(path)
    assert [f.name for f in doc.features] == stored
