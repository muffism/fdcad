"""Speed and memory budgets of PLAN 11.2, as tests (PLAN 10 item 12).

Each limit has a 50 percent margin for slower CI runners. Viewport frame rate
(budget 6) needs a GPU and is checked by hand in each owner review.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.io import fdef
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.samples.graphs import SAMPLE_DIR as GRAPH_SAMPLE_DIR
from fdcad.samples.make import SAMPLE_DIR
from fdcad.samples.parts import SAMPLES
from fdcad.sysinfo import process_memory

MARGIN = 1.5
GRAPH_SAMPLES = sorted(p.stem for p in GRAPH_SAMPLE_DIR.glob("*.fdprt"))
MB = 1024 * 1024


@pytest.fixture(autouse=True)
def _folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("FDCAD_DATA_DIR", str(tmp_path / "data"))


def _startup(tmp_path: Path) -> dict[str, float]:
    report = tmp_path / "startup.json"
    env = dict(os.environ)
    env["FDCAD_STARTUP_REPORT"] = str(report)
    env["QT_QPA_PLATFORM"] = "offscreen"
    subprocess.run(
        [sys.executable, "-m", "fdcad.app"], env=env, timeout=120, check=True, cwd=tmp_path
    )
    data: dict[str, float] = json.loads(report.read_text(encoding="utf-8"))
    return data


def test_startup_and_empty_part_memory(tmp_path: Path) -> None:
    """Budgets 1 and 7: window in 2 s, ready in 5 s, under 400 MB with an empty part."""
    data = _startup(tmp_path)
    assert data["visible"] < 2.0 * MARGIN
    assert data["ready"] < 5.0 * MARGIN
    if sys.platform.startswith("linux") or sys.platform == "darwin":
        # Resident memory counts mapped library files: about 245 MB of them on Linux
        # (D491) and about 210 MB on Apple Silicon (D2711). Count what the app
        # allocates itself; on macOS that is the figure Activity Monitor shows.
        assert 0 < data["private"] < 400 * MB
    elif data["memory"]:
        assert data["memory"] < 400 * MB


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_full_rebuild_of_each_sample(name: str) -> None:
    """Budget 4: a full rebuild of each sample part in under 2 s."""
    doc = fdef.load(SAMPLE_DIR / f"{name}.fdprt")
    start = time.perf_counter()
    report = RebuildEngine().rebuild(doc)
    assert report.body is not None
    assert time.perf_counter() - start < 2.0 * MARGIN


@pytest.mark.parametrize("name", GRAPH_SAMPLES)
def test_full_rebuild_of_each_graph_sample(name: str) -> None:
    """Budget 4 for the node editor samples (Phase 6 performance pass, D432)."""
    doc = fdef.load(GRAPH_SAMPLE_DIR / f"{name}.fdprt")
    start = time.perf_counter()
    report = RebuildEngine().rebuild(doc)
    assert report.body is not None
    assert time.perf_counter() - start < 2.0 * MARGIN


def test_edit_near_the_end_of_200_features() -> None:
    """Budget 3: change one dimension near the end of a 200 feature tree in under 0.5 s."""
    doc = fdef.load(SAMPLE_DIR / "generated_200.fdprt")
    engine = RebuildEngine()
    engine.rebuild(doc)
    sketch = doc.features[-4]  # the second last hole sketch
    assert sketch.type == "sketch"
    diameter = next(d for d in sketch.data["dimensions"] if d["type"] == "diameter")
    diameter["param"] = Param("5", 5.0)
    start = time.perf_counter()
    report = engine.rebuild(doc)
    elapsed = time.perf_counter() - start
    assert len(report.rebuilt) <= 4  # the sketch, its cut, and what follows
    assert elapsed < 0.5 * MARGIN


def test_open_with_valid_cache(qtbot: QtBot, tmp_path: Path) -> None:
    """Budget 2: a saved part with a valid cache appears in under 2 s."""
    from fdcad.ui.session import DocumentSession

    path = tmp_path / "part.fdef"
    first = DocumentSession(fdef.load(SAMPLE_DIR / "generated_200.fdprt"))
    with qtbot.waitSignal(first.rebuilt, timeout=60000):
        first.request_rebuild()
    first.save(path)  # also fills the disk cache, in the background (D723)
    first.wait_cache(60.0)
    start = time.perf_counter()
    session = DocumentSession.open(path)
    with qtbot.waitSignal(session.rebuilt, timeout=60000):
        session.request_rebuild()
    elapsed = time.perf_counter() - start
    assert session.from_cache and session.report is not None
    assert session.report.body is not None
    assert elapsed < 2.0 * MARGIN
    session.wait(60000)


def test_200_feature_part_memory() -> None:
    """Budget 7: under 1.5 GB with the 200 feature part open."""
    code = (
        "from fdcad.core.io import fdef\n"
        "from fdcad.core.rebuild.engine import RebuildEngine\n"
        "from fdcad.samples.make import SAMPLE_DIR\n"
        "from fdcad.sysinfo import process_memory\n"
        "from fdcad.ui.viewport.meshing import mesh_for_display\n"
        "r = RebuildEngine().rebuild(fdef.load(SAMPLE_DIR / 'generated_200.fdprt'))\n"
        "mesh_for_display(r.body.shape)\n"
        "print(process_memory())\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=120, check=True
    )
    memory = int(out.stdout.strip().splitlines()[-1])
    if memory:
        assert memory < 1536 * MB


def test_no_leak_when_parts_open_and_close(qtbot: QtBot) -> None:
    """Budget 8: opening, rebuilding and closing a sample 50 times grows memory under 50 MB."""
    from fdcad.ui.session import DocumentSession

    if not process_memory():
        pytest.skip("process memory cannot be read here")

    def cycle() -> None:
        session = DocumentSession(fdef.load(SAMPLE_DIR / "plate_with_holes.fdprt"))
        with qtbot.waitSignal(session.rebuilt, timeout=20000):
            session.request_rebuild()
        session.wait()
        session.engine.cache.clear()
        session.deleteLater()

    for _ in range(5):  # warm up imports and caches
        cycle()
    qtbot.wait(50)
    before = process_memory()
    for _ in range(50):
        cycle()
    qtbot.wait(50)
    assert process_memory() - before < 50 * MB


#: Each PLAN 11.2 budget and the tests that check it (Phase 6 performance pass, D432).
#: Budget 6 (viewport frame rate) needs a GPU and is checked by hand in owner reviews.
BUDGET_TESTS = {
    1: ["tests/perf/test_budgets.py::test_startup_and_empty_part_memory"],
    2: ["tests/perf/test_budgets.py::test_open_with_valid_cache"],
    3: ["tests/perf/test_budgets.py::test_edit_near_the_end_of_200_features"],
    4: [
        "tests/perf/test_budgets.py::test_full_rebuild_of_each_sample",
        "tests/perf/test_budgets.py::test_full_rebuild_of_each_graph_sample",
    ],
    5: ["tests/core/sketch/test_sketch_speed.py::test_drag_keeps_up_with_200_entities"],
    7: [
        "tests/perf/test_budgets.py::test_startup_and_empty_part_memory",
        "tests/perf/test_budgets.py::test_200_feature_part_memory",
    ],
    8: ["tests/perf/test_budgets.py::test_no_leak_when_parts_open_and_close"],
}


def test_every_budget_has_a_test() -> None:
    root = Path(__file__).resolve().parents[2]
    assert sorted(BUDGET_TESTS) == [1, 2, 3, 4, 5, 7, 8]
    for tests in BUDGET_TESTS.values():
        for test in tests:
            path, name = test.split("::")
            assert f"def {name}(" in (root / path).read_text(encoding="utf-8"), test
