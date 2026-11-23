"""A session builds from the numbers its file keeps (IDEAS 49, DECISIONS D2626).

A part file keeps numbers to twelve significant digits. A session used to build
from the full numbers it had in memory, so a kernel result that hangs on the last
digits could come out differently when the part was opened again (D1049, D1052,
D1053). Every feature is now built from the rounded copy that would be saved.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from OCP.BRep import BRep_Tool
from OCP.TopAbs import TopAbs_VERTEX
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Shape

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features.base import BuildContext, FeatureResult
from fdcad.core.features.extrude import Extrude
from fdcad.core.io import fdef
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, rect

#: Beyond the twelve significant digits a file keeps.
SLIVER = 10.0000000000003


def _part() -> tuple[Document, str]:
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, SLIVER, 5)
    sketch = add_sketch(doc, s, {"feature": "f2"})
    return doc, add_extrude(doc, sketch, 4.0)


def _corners(shape: TopoDS_Shape) -> list[tuple[float, float, float]]:
    out = []
    explorer = TopExp_Explorer(shape, TopAbs_VERTEX)
    while explorer.More():
        p = BRep_Tool.Pnt_s(TopoDS.Vertex(explorer.Current()))
        out.append((p.X(), p.Y(), p.Z()))
        explorer.Next()
    return sorted(out)


def test_a_session_builds_what_its_file_builds(tmp_path: Path) -> None:
    doc, fid = _part()
    built = body(RebuildEngine().rebuild(doc).results, fid)
    path = tmp_path / "part.fdprt"
    fdef.save(doc, path)
    opened = body(RebuildEngine().rebuild(fdef.load(path)).results, fid)
    assert _corners(built.shape) == _corners(opened.shape)  # exactly, to the last digit
    assert max(x for x, _y, _z in _corners(built.shape)) == 10.0


def test_a_feature_is_given_the_rounded_numbers(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[Feature] = []
    real = Extrude.execute

    def spy(self: Extrude, feature: Feature, ctx: BuildContext) -> FeatureResult:
        seen.append(feature)
        seen.extend(f for f in ctx.document.features if f.type == "sketch")
        return real(self, feature, ctx)

    monkeypatch.setattr(Extrude, "execute", spy)
    doc, fid = _part()
    doc.feature(fid).params["width"] = [SLIVER, 2.0]  # a number no formula sets again
    doc.feature(fid).params["depth"] = Param("10/3", 10 / 3)
    RebuildEngine().rebuild(doc)
    extrude, sketch = seen
    assert extrude.params["width"] == [10.0, 2.0]
    # A typed value is worked out from its text again on open, so it keeps every digit.
    depth = extrude.params["depth"]
    assert isinstance(depth, Param) and depth.value == 10 / 3 and depth.expr == "10/3"
    assert extrude is not doc.feature(fid)
    assert SLIVER not in _numbers(sketch.data)
    # The document itself keeps its own numbers: only the build sees rounded ones.
    assert SLIVER in _numbers(doc.feature(sketch.id).data)


def test_a_value_solved_only_after_a_measure_keeps_its_digits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D2673: a formula that fails on the 0 a measured value has before its first
    rebuild (a part just opened) is solved again after the measure, and is worked
    out from its text then too. It was rounded, so a part just opened built from
    other numbers than the same part rebuilt later in the session."""
    from tests.core.features.test_features import plate

    seen: list[float] = []
    real = Extrude.execute

    def spy(self: Extrude, feature: Feature, ctx: BuildContext) -> FeatureResult:
        depth = feature.params["depth"]
        assert isinstance(depth, Param)
        seen.append(depth.value)
        return real(self, feature, ctx)

    monkeypatch.setattr(Extrude, "execute", spy)
    doc, _plate = plate()  # 50 mm long
    box = doc.new_feature_id()
    doc.features.append(Feature(box, "bounding_box", "Bounding Box 1"))
    s = Sketch()
    rect(s, 0, 0, 10, 10)
    sketch = add_sketch(doc, s, {"feature": "f2"})
    fid = add_extrude(doc, sketch, 1.0)
    # 1000 / 50 / 3 mm: no twelve digit number; a division by zero before the measure.
    doc.feature(fid).params["depth"] = Param(f'=1000mm / "length@{box}" / 3', 0.0)
    assert body(RebuildEngine().rebuild(doc).results, fid)
    assert seen[-1] == 1000 / 50 / 3  # every digit, as a later rebuild solves it
    seen.clear()
    assert body(RebuildEngine().rebuild(doc).results, fid)  # the measure is known now
    assert seen[-1] == 1000 / 50 / 3


def _numbers(value: object) -> set[float]:
    if isinstance(value, float):
        return {value}
    if isinstance(value, dict):
        return set().union(*(_numbers(v) for v in value.values())) if value else set()
    if isinstance(value, list | tuple):
        return set().union(*(_numbers(v) for v in value)) if value else set()
    return set()


@pytest.mark.parametrize("why", ["suppressed", "below the rollback bar"])
def test_a_value_the_file_cannot_keep_in_a_feature_that_does_not_build(why: str) -> None:
    """D2670: the copy of the part holds every feature, and a nan in one that never
    builds made every rebuild of the part raise "Cannot save the value nan"."""
    doc, first = _part()
    s = Sketch()
    rect(s, 0, 0, 3, 3)
    second = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 2.0)
    doc.feature(second).data["kept"] = float("nan")
    if why == "suppressed":
        doc.feature(second).suppressed = True
    else:
        doc.rollback = first
    report = RebuildEngine().rebuild(doc)
    assert body(report.results, first).shape is not None
    assert second not in report.results
