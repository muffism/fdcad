"""Incremental rebuild: only changed features rebuild (PLAN 11.3 items 1 and 2)."""

import math

import pytest
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

from fdcad.core.cache.memory import ResultCache
from fdcad.core.document.model import Document, Param, Variable
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import sketch_from_data, sketch_to_data
from fdcad.core.units import Kind
from tests.core.features.test_features import _hole, plate


def _volume(engine: RebuildEngine, doc: Document) -> float:
    body = engine.rebuild(doc).body
    assert body is not None
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(body.shape, props)
    return float(props.Mass())


def _part() -> tuple[Document, str, str]:
    doc, ext = plate()
    cut = _hole(doc, f"{ext}/cap/end")
    return doc, ext, cut


def test_second_rebuild_reuses_everything() -> None:
    doc, _, _ = _part()
    engine = RebuildEngine()
    first = engine.rebuild(doc)
    second = engine.rebuild(doc)
    assert len(first.rebuilt) == len(doc.features)
    assert second.rebuilt == [] and len(second.reused) == len(doc.features)


def test_changing_the_hole_keeps_the_plate() -> None:
    doc, ext, cut = _part()
    engine = RebuildEngine()
    engine.rebuild(doc)
    hole_sketch = doc.features[-2]
    sketch = sketch_from_data(hole_sketch.data)
    circle = next(e for e in sketch.entities.values() if hasattr(e, "radius"))
    circle.radius = 8.0  # type: ignore[union-attr]
    hole_sketch.data.update(sketch_to_data(sketch))
    report = engine.rebuild(doc)
    assert report.rebuilt == [hole_sketch.id, cut]
    assert ext in report.reused
    assert _volume(engine, doc) == pytest.approx(25000 - math.pi * 64 * 10, rel=1e-9)


def test_changing_the_depth_rebuilds_downstream_only() -> None:
    doc, ext, cut = _part()
    engine = RebuildEngine()
    engine.rebuild(doc)
    doc.feature(ext).params["depth"] = Param("12", 12.0)
    report = engine.rebuild(doc)
    plate_sketch = doc.features[4].id
    assert plate_sketch in report.reused  # on the Front plane, so not affected
    assert report.rebuilt == [ext, doc.features[-2].id, cut]


def test_variables_drive_values() -> None:
    doc, ext = plate()
    doc.variables.append(Variable("T", Kind.LENGTH, "10", 10.0))
    doc.feature(ext).params["depth"] = Param("=T*2", 0.0)
    engine = RebuildEngine()
    assert _volume(engine, doc) == pytest.approx(50 * 50 * 20, rel=1e-9)
    doc.variables[0].expr = "3"
    report = engine.rebuild(doc)
    assert ext in report.rebuilt
    assert _volume(engine, doc) == pytest.approx(50 * 50 * 6, rel=1e-9)
    assert doc.variables[0].value == 3.0


def test_bad_variable_is_reported() -> None:
    doc, _ = plate()
    doc.variables.append(Variable("A", Kind.LENGTH, "=A+1mm", 0.0))
    report = RebuildEngine().rebuild(doc)
    assert report.variable_error is not None and "Circular" in report.variable_error


def test_progress_and_cancel() -> None:
    doc, _, _ = _part()
    calls: list[tuple[int, int, str]] = []
    RebuildEngine().rebuild(doc, progress=lambda i, n, name: calls.append((i, n, name)))
    assert [c[0] for c in calls] == list(range(len(doc.features)))
    seen: list[int] = []
    report = RebuildEngine().rebuild(
        doc, progress=lambda i, n, name: seen.append(i), cancelled=lambda: len(seen) >= 3
    )
    assert report.cancelled and len(report.results) == 3


def test_suppressed_feature_is_skipped() -> None:
    doc, _ext, cut = _part()
    doc.feature(cut).suppressed = True
    engine = RebuildEngine()
    report = engine.rebuild(doc)
    assert cut not in report.results
    assert _volume(engine, doc) == pytest.approx(25000, rel=1e-9)


def test_rollback_stops_the_rebuild() -> None:
    doc, ext, _cut = _part()
    doc.rollback = ext
    report = RebuildEngine().rebuild(doc)
    assert list(report.results)[-1] == ext


def test_rollback_holds_when_the_feature_above_the_bar_is_suppressed() -> None:
    doc, _ext, cut = _part()
    sketch = doc.features[doc.features.index(doc.feature(cut)) - 1].id
    doc.rollback = sketch  # the bar sits between the hole sketch and the cut
    doc.feature(sketch).suppressed = True
    report = RebuildEngine().rebuild(doc)
    assert cut not in report.results  # still below the bar, so never built


def test_cache_limit_drops_oldest() -> None:
    doc, _, _ = _part()
    cache = ResultCache(limit=60 * 1024)
    RebuildEngine(cache).rebuild(doc)
    assert cache.size <= 60 * 1024 or len(cache) == 1
    assert len(cache) < len(doc.features)


def test_statistics() -> None:
    doc, _, _ = _part()
    report = RebuildEngine().rebuild(doc)
    slow = report.slowest(3)
    assert len(slow) == 3 and slow[0][1] >= slow[-1][1]
    assert report.seconds > 0
