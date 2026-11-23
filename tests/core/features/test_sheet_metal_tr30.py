"""Sheet metal small options (TR30, D696): cut linked to thickness, edge flange offset,
miter flange propagate."""

from __future__ import annotations

import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.modify import tangent_chain
from fdcad.core.io import fdef
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import Sketch, sketch_to_data
from fdcad.samples.make import SAMPLE_DIR, measure


def _bracket() -> Document:
    return fdef.loads((SAMPLE_DIR / "sheet_metal_bracket.fdprt").read_text(encoding="utf-8"))


def _volume(doc: Document) -> float:
    report = RebuildEngine().rebuild(doc)
    assert report.body is not None
    return float(measure(report.body.shape)["volume"])


def _hole_cut(doc: Document, link: bool, reverse: bool) -> str:
    sk = Sketch()
    sk.add_circle(20, 20, 3)
    sketch = Feature(
        doc.new_feature_id(),
        "sketch",
        "Hole Sketch",
        refs={"plane": {"feature": "f2"}},
        data=sketch_to_data(sk),
    )
    params = {
        "operation": "cut",
        "end_condition": "blind",
        "depth": Param("0.5", 0.5),
        "reverse": reverse,
    }
    if link:
        params["link_thickness"] = True
    cut = Feature(
        doc.new_feature_id(),
        "extrude",
        "Cut 1",
        params=params,
        refs={"sketch": {"feature": sketch.id}},
    )
    doc.features[-1:-1] = [sketch, cut]  # before the flat pattern
    return cut.id


def test_cut_linked_to_thickness_cuts_through_the_sheet() -> None:
    base = _volume(_bracket())
    for reverse in (False, True):
        linked, through = _bracket(), _bracket()
        _hole_cut(linked, True, reverse)
        fid = _hole_cut(through, False, reverse)
        through.feature(fid).params["end_condition"] = "through_all"
        # The typed 0.5 is not used: the cut goes through the 2 mm sheet.
        assert base - _volume(linked) == pytest.approx(base - _volume(through), abs=1e-6)


def test_link_follows_a_changed_thickness() -> None:
    doc = _bracket()
    _hole_cut(doc, True, False)
    first = _volume(_bracket()) - _volume(doc)
    doc = _bracket()
    doc.feature("f5").params["thickness"] = Param("3", 3.0)
    base3 = _volume(doc)
    _hole_cut(doc, True, False)
    again = base3 - _volume(doc)
    if first > 1:  # this direction cuts the sheet
        assert again == pytest.approx(first * 1.5, rel=1e-3)


def test_link_needs_sheet_metal() -> None:
    doc = fdef.loads((SAMPLE_DIR / "bracket.fdprt").read_text(encoding="utf-8"))
    cut = doc.feature("f8")
    cut.params["link_thickness"] = True
    cut.params["end_condition"] = "blind"
    result = RebuildEngine().rebuild(doc).results["f8"]
    assert result.state is FeatureState.ERROR
    assert "sheet metal" in " ".join(i.message for i in result.issues)


def _flange_box(doc: Document) -> list[float]:
    report = RebuildEngine().rebuild(doc)
    assert report.results["f8"].state is not FeatureState.ERROR
    assert report.body is not None
    return [float(v) for v in measure(report.body.shape)["bbox"]]


def test_edge_flange_offset_moves_the_flange_in() -> None:
    inside = _flange_box(_bracket())
    doc = _bracket()
    flange = doc.feature("f8")
    flange.params["position"] = "offset"
    flange.params["offset_distance"] = Param("5", 5.0)
    flange.params["offset_rule"] = "material_inside"
    moved = _flange_box(doc)
    changed = [abs(a - b) for a, b in zip(inside, moved, strict=True)]
    assert max(changed) == pytest.approx(5.0, abs=1e-6)
    zero = _bracket()
    zero.feature("f8").params.update({"position": "offset", "offset_distance": Param("0", 0.0)})
    assert _flange_box(zero) == pytest.approx(inside)


def test_propagate_walks_straight_edges_only() -> None:
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    box = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
    edge = TopoDS.Edge(TopExp_Explorer(box, TopAbs_EDGE).Current())
    # A box has no smooth joins: the edge stays alone.
    assert len(tangent_chain(box, [edge], straight_only=True)) == 1
