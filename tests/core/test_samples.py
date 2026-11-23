"""Sample parts: golden results, file round trips, STEP and naming stability (PLAN 10)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureState
from fdcad.core.io import fdef
from fdcad.core.io.export import export_step
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import sketch_from_data
from fdcad.core.sketch.solver import SketchStatus, solve
from fdcad.samples.make import GOLDEN, SAMPLE_DIR, measure
from fdcad.samples.parts import SAMPLES

NAMES = sorted(SAMPLES)
GOLDEN_DATA = json.loads(GOLDEN.read_text(encoding="utf-8"))


def _volume(shape: object) -> float:
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    return float(props.Mass())


def _same(a: object, b: object) -> bool:
    """Equal JSON, with floats equal to 9 significant digits.

    Face snapshots come from the kernel, whose last digits differ a little
    between Windows and macOS.
    """
    if isinstance(a, float) or isinstance(b, float):
        return (
            isinstance(a, int | float)
            and isinstance(b, int | float)
            and math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
        )
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b, strict=True))
    return a == b


@pytest.mark.parametrize("name", NAMES)
def test_saved_sample_matches_its_builder(name: str) -> None:
    saved = json.loads((SAMPLE_DIR / f"{name}.fdprt").read_text(encoding="utf-8"))
    built = json.loads(fdef.dumps(SAMPLES[name]()))
    assert _same(saved, built), "run: uv run python -m fdcad.samples.make"


@pytest.mark.parametrize("name", NAMES)
def test_sample_rebuilds_to_golden_results(name: str) -> None:
    doc = fdef.load(SAMPLE_DIR / f"{name}.fdprt")
    report = RebuildEngine().rebuild(doc)
    bad = {f: r.state for f, r in report.results.items() if r.state is not FeatureState.OK}
    assert bad == {}
    assert report.body is not None
    assert report.body_count == GOLDEN_DATA[name].get("bodies", 1)
    got, want = measure(report.body.shape), GOLDEN_DATA[name]
    # Deformed samples state their own tolerance (PLAN 10 item 8, D394).
    assert got["volume"] == pytest.approx(want["volume"], rel=want.get("volume_rel", 1e-6))
    assert (got["faces"], got["edges"]) == (want["faces"], want["edges"])
    assert got["bbox"] == pytest.approx(want["bbox"], abs=want.get("bbox_abs", 1e-4))


@pytest.mark.parametrize("name", NAMES)
def test_sample_sketches_are_fully_defined(name: str) -> None:
    doc = fdef.load(SAMPLE_DIR / f"{name}.fdprt")
    for feature in doc.features:
        if feature.type == "sketch":
            assert solve(sketch_from_data(feature.data)).status is SketchStatus.FULL, feature.name


@pytest.mark.parametrize("name", NAMES)
def test_sample_round_trip_and_step(name: str, tmp_path: Path) -> None:
    doc = fdef.load(SAMPLE_DIR / f"{name}.fdprt")
    assert fdef.dumps(fdef.loads(fdef.dumps(doc))) == fdef.dumps(doc)
    report = RebuildEngine().rebuild(doc)
    assert report.body is not None
    path = tmp_path / f"{name}.step"
    export_step(report.body.shape, path)
    reader = STEPControl_Reader()
    assert reader.ReadFile(str(path)) == IFSelect_RetDone
    reader.TransferRoots()
    want = GOLDEN_DATA[name]
    assert _volume(reader.OneShape()) == pytest.approx(
        want["volume"], rel=want.get("volume_rel", 1e-6)
    )


def test_plate_follows_its_variables() -> None:
    """Editing an upstream value moves the holes with it (owner review step 4)."""
    doc = fdef.load(SAMPLE_DIR / "plate_with_holes.fdprt")
    width = next(v for v in doc.variables if v.name == "Width")
    width.expr, width.value = "140mm", 140.0
    report = RebuildEngine().rebuild(doc)
    assert all(r.state is FeatureState.OK for r in report.results.values())
    assert report.body is not None
    got = measure(report.body.shape)
    holes = 4 * math.pi * 16 * 10 + math.pi * 100 * 10
    assert got["volume"] == pytest.approx(140 * 60 * 10 - holes, rel=1e-9)
    assert got["bbox"][3] == pytest.approx(140.0)
    assert got["faces"] == GOLDEN_DATA["plate_with_holes"]["faces"]


def test_shaft_step_length_edit() -> None:
    doc = fdef.load(SAMPLE_DIR / "turned_shaft.fdprt")
    profile = next(f for f in doc.features if f.name == "Shaft Profile")
    first = profile.data["dimensions"][0]
    first["param"] = Param("150", 150.0)  # overall length, was 120
    report = RebuildEngine().rebuild(doc)
    assert all(r.state is FeatureState.OK for r in report.results.values())
    assert report.body is not None
    assert measure(report.body.shape)["bbox"][3] == pytest.approx(150.0)
