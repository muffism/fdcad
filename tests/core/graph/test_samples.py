"""Sample graphs (PLAN Phase 7): saved files match their builders, rebuilds match the
golden results on every run, files round trip and STEP export keeps the volume."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader

from fdcad.core.features.base import FeatureState
from fdcad.core.graph import geometry as geo
from fdcad.core.graph.engine import Evaluator
from fdcad.core.io import fdef
from fdcad.core.io.export import export_step
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.samples.graphs import GOLDEN, GRAPH_SAMPLES, SAMPLE_DIR
from fdcad.samples.make import measure

NAMES = sorted(GRAPH_SAMPLES)
GOLDEN_DATA = json.loads(GOLDEN.read_text(encoding="utf-8"))


def _check(name: str, data: dict[str, object]) -> None:
    gold = GOLDEN_DATA[name]
    assert data["volume"] == pytest.approx(gold["volume"], rel=1e-6)
    assert data["faces"] == gold["faces"] and data["edges"] == gold["edges"]
    assert data["bbox"] == pytest.approx(gold["bbox"], abs=1e-4)


@pytest.mark.parametrize("name", NAMES)
def test_saved_file_matches_its_builder(name: str) -> None:
    text = (SAMPLE_DIR / f"{name}.fdprt").read_text(encoding="utf-8")
    built = GRAPH_SAMPLES[name]()
    assert json.loads(fdef.dumps(built))["graphs"] == json.loads(text)["graphs"]
    assert json.loads(text)["schema"] == 2


@pytest.mark.parametrize("name", NAMES)
def test_sample_rebuilds_to_golden_results_every_time(name: str) -> None:
    for _ in range(2):  # fresh engines and evaluators: random nodes are seeded
        doc = fdef.load(SAMPLE_DIR / f"{name}.fdprt")
        from fdcad.core.graph.engine import SHARED

        SHARED.clear()
        report = RebuildEngine().rebuild(doc)
        assert all(r.state is not FeatureState.ERROR for r in report.results.values()), name
        assert report.body is not None
        _check(name, measure(report.body.shape))
        assert report.body_count == GOLDEN_DATA[name]["bodies"]


@pytest.mark.parametrize("name", NAMES)
def test_sample_round_trips_and_exports(name: str, tmp_path: Path) -> None:
    doc = fdef.load(SAMPLE_DIR / f"{name}.fdprt")
    assert fdef.dumps(fdef.loads(fdef.dumps(doc))) == fdef.dumps(doc)
    report = RebuildEngine().rebuild(doc)
    assert report.body is not None
    path = tmp_path / f"{name}.step"
    export_step(report.body.shape, path)
    reader = STEPControl_Reader()
    assert reader.ReadFile(str(path)) == IFSelect_RetDone
    reader.TransferRoots()
    # Ball jointed lattices lose a few parts in 100000 through STEP (DECISIONS D379).
    tolerance = 1e-4 if name == "lattice_block" else 1e-6
    assert geo.volume(reader.OneShape()) == pytest.approx(
        GOLDEN_DATA[name]["volume"], rel=tolerance
    )


def test_slider_bracket_follows_its_sliders() -> None:
    doc = fdef.load(SAMPLE_DIR / "slider_bracket.fdprt")
    graph = doc.graphs[0]
    width = next(n for n in graph.nodes if n.params.get("max") == 60)
    from fdcad.core.document.model import Param

    width.params["value"] = Param("30", 30.0)
    report = RebuildEngine().rebuild(doc)
    assert report.body is not None
    assert geo.volume(report.body.shape) == pytest.approx(856 * 30)
    assert doc.variables[0].expr == "60mm"


def test_attractor_holes_grow_with_distance() -> None:
    doc = fdef.load(SAMPLE_DIR / "attractor_plate.fdprt")
    graph = doc.graphs[0]
    report = RebuildEngine().rebuild(doc)
    from fdcad.core.graph.drive import make_env

    env = make_env(doc, graph, report.results, {})
    result = Evaluator().evaluate(graph, env)
    field = next(n.id for n in graph.nodes if n.type == "attractor")
    values = result.value(field, "values")
    distances = result.value(field, "distances")
    order = sorted(range(len(values)), key=lambda i: distances[i])
    assert values[order[0]] < values[order[-1]]
    assert min(values) >= 1 and max(values) <= 4
