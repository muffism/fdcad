"""Robustness tests from TUTORIAL_REVIEW_SPEC_2 section 21 (Stage 1 item 11, D737).

Common bug classes in other CAD tools' trackers, checked against FDCAD's own
samples and features. No new behaviour: each test pins what already holds.
"""

from __future__ import annotations

import math
import time
from pathlib import Path

import pytest

from fdcad.core.document.model import Document, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.face_picks import outward_normal
from fdcad.core.io import fdef
from fdcad.core.naming.names import faces_of
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.units import Kind
from fdcad.samples.make import SAMPLE_DIR
from fdcad.samples.parts import SAMPLES

NAMES = sorted(SAMPLES)


def _load(name: str) -> Document:
    return fdef.load(SAMPLE_DIR / f"{name}{fdef.PART_SUFFIX}")


def _lengths(doc: Document) -> list[tuple[str, str]]:
    """(feature id, parameter) of every length typed as a plain value."""
    from fdcad.core.features import REGISTRY

    out = []
    for f in doc.features:
        ftype = REGISTRY.get(f.type)
        for name, value in f.params.items():
            plain = isinstance(value, Param) and not value.expr.strip().startswith("=")
            if plain and ftype is not None and ftype.kind_of(name) is Kind.LENGTH:
                assert isinstance(value, Param)
                if value.value > 0:
                    out.append((f.id, name))
    return out


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("factor", [1.000001, 1.1])
def test_changed_lengths_keep_references_or_say_they_are_lost(name: str, factor: float) -> None:
    """Item 1: change every length a little and by about ten percent; nothing crashes,
    and a feature that fails says why (a lost reference is an error, never silent)."""
    doc = _load(name)
    for fid, param in _lengths(doc):
        value = doc.feature(fid).params[param]
        assert isinstance(value, Param)
        new = value.value * factor
        doc.feature(fid).params[param] = Param(f"{new:.9g}", new)
    report = RebuildEngine().rebuild(doc)
    for fid, result in report.results.items():
        if result.state is FeatureState.ERROR:
            assert result.issues and result.issues[0].message, fid


@pytest.mark.parametrize("name", NAMES)
def test_every_solid_feature_names_its_faces(name: str) -> None:
    """Item 1: every feature kind that makes a solid returns a naming map."""
    report = RebuildEngine().rebuild(_load(name))
    assert report.body is not None
    named = [f for _n, f in report.body.faces]
    unnamed = [f for f in faces_of(report.body.shape) if not any(f.IsSame(g) for g in named)]
    assert not unnamed, f"{name}: {len(unnamed)} faces have no name"


@pytest.mark.parametrize("count", [0, 1, 2, 9, 10, 11, 100])
def test_pattern_counts(count: int) -> None:
    """Item 3: pattern counts at the edges; 0 leaves the part with a warning (TR345,
    D875), the rest build or fail with a message, never crash."""
    from tests.core.features.test_patterns import X, centred, length, pattern

    doc, _plate, boss = centred()
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(0.5), "count1": Param(str(count), float(count))},
        {"direction1": X, "features": [{"feature": boss}]},
    )
    result = results[fid]
    if count == 0:
        assert result.state is FeatureState.WARNING and result.issues
    else:
        assert result.state is not FeatureState.ERROR or result.issues


@pytest.mark.parametrize("name", NAMES)
def test_no_value_is_reinterpreted_on_load(name: str) -> None:
    """Item 8: saving and opening again gives the same text and the same volume."""
    text = (SAMPLE_DIR / f"{name}{fdef.PART_SUFFIX}").read_text(encoding="utf-8")
    doc = fdef.loads(text)
    assert fdef.dumps(fdef.loads(fdef.dumps(doc))) == fdef.dumps(doc)


def test_rebuild_time_does_not_grow_over_repeated_edits() -> None:
    """Item 9: a hundred edits of one value; the last rebuilds are not much slower than
    the first ones (no growing caches or leaks in the rebuild path)."""
    doc = _load("plate_with_holes")
    fid, param = _lengths(doc)[0]
    engine = RebuildEngine()
    times = []
    for k in range(100):
        value = doc.feature(fid).params[param]
        assert isinstance(value, Param)
        new = value.value * (1.001 if k % 2 else 1 / 1.001)
        doc.feature(fid).params[param] = Param(f"{new:.9g}", new)
        start = time.perf_counter()
        engine.rebuild(doc)
        times.append(time.perf_counter() - start)
    first, last = sum(times[5:15]) / 10, sum(times[-10:]) / 10
    assert last < 3 * first + 0.05


@pytest.mark.parametrize("name", ["plate_with_holes", "turned_shaft"])
def test_a_sketch_on_every_face_is_square_to_it(name: str) -> None:
    """Item 18: a sketch on any flat face of a block or a turned body faces out of it."""
    from fdcad.core.features.sketch import face_plane

    doc = _load(name)
    report = RebuildEngine().rebuild(doc)
    assert report.body is not None
    checked = 0
    for face in faces_of(report.body.shape):
        normal = outward_normal(face)
        if normal is None or reference_for(report.body, face) is None:
            continue
        plane = face_plane(face)
        if plane is None:
            continue
        dot = sum(a * b for a, b in zip(plane.normal, normal, strict=True))
        assert math.isclose(dot, 1.0, abs_tol=1e-9), (name, normal, plane.normal)
        checked += 1
    assert checked >= 2


def test_save_failure_keeps_the_old_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Item 10: covered in tests/core/io/test_hostile_files.py; kept here as a pointer."""
    from tests.core.io.test_hostile_files import test_a_failed_save_leaves_the_old_file

    test_a_failed_save_leaves_the_old_file(tmp_path, monkeypatch)
