"""Long rebuilds in a helper process, so the window never waits on the kernel (D2600)."""

import sys
import threading
from pathlib import Path

import pytest
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

from fdcad.core.cache import disk
from fdcad.core.cache.history import load_history, seed
from fdcad.core.document.model import Param
from fdcad.core.rebuild import remote
from fdcad.core.rebuild.engine import RebuildEngine
from tests.core.features.test_features import _hole, plate

HERE = Path(__file__).parent


def _volume(shape: object) -> float:
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props, 1e-6)
    return float(props.Mass())


@pytest.fixture
def cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path))
    return tmp_path


def test_the_helper_builds_the_part_and_the_app_reuses_every_solid(cache: Path) -> None:
    doc, ext = plate()
    cut = _hole(doc, f"{ext}/cap/end")
    here = RebuildEngine().rebuild(doc)
    engine = RebuildEngine()
    steps: list[int] = []
    out = remote.rebuild_remote(engine, doc, [], progress=lambda i, _n, _name: steps.append(i))
    assert out.done and not out.problem, out
    assert out.keys == [disk.document_key(doc)]
    assert steps and steps[0] == 0  # progress came across
    seed(engine.cache, load_history(cache, out.keys[0]))
    after = engine.rebuild(doc)
    assert ext in after.reused and cut in after.reused  # no solid was built in the app
    assert after.body is not None and here.body is not None
    assert _volume(after.body.shape) == pytest.approx(_volume(here.body.shape), rel=1e-9)
    assert sorted(n for n, _ in after.body.faces) == sorted(n for n, _ in here.body.faces)
    assert disk.load(out.keys[0]) is not None  # the finished part is cached too


def test_a_helper_goes_on_from_the_results_it_is_given(cache: Path) -> None:
    doc, ext = plate()
    first = _hole(doc, f"{ext}/cap/end")
    out = remote.rebuild_remote(RebuildEngine(), doc, [])
    assert out.done
    second = _hole(doc, f"{ext}/cap/end")
    engine = RebuildEngine()
    built: list[str] = []
    again = remote.rebuild_remote(
        engine, doc, out.keys, on_build=lambda fid, _name: built.append(fid)
    )
    assert again.done
    assert second in built and first not in built and ext not in built


def test_a_stopped_helper_writes_what_it_has(cache: Path) -> None:
    doc, ext = plate()
    for _ in range(6):
        _hole(doc, f"{ext}/cap/end")
    stop = threading.Event()
    out = remote.rebuild_remote(
        RebuildEngine(), doc, [], on_build=lambda _fid, name: stop.set(), cancelled=stop.is_set
    )
    assert out.stopped and not out.done
    if out.keys:  # it had built something by the time it read the stop
        assert out.keys[0].endswith(".partial")
        assert load_history(cache, out.keys[0])


def test_a_helper_that_dies_names_the_feature_it_was_building(
    cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A native fault in the kernel ends the process with no word; building that feature
    # in the app could close FDCAD, so the app must know which one it was.
    doc, ext = plate()
    cut = _hole(doc, f"{ext}/cap/end")
    script = HERE / "helper_dies.py"
    monkeypatch.setattr(remote, "helper_command", lambda: [sys.executable, str(script), cut])
    out = remote.rebuild_remote(RebuildEngine(), doc, [])
    assert not out.done and out.lost_on[0] == cut


def test_the_estimate_counts_from_the_first_changed_feature() -> None:
    doc, ext = plate()
    a = _hole(doc, f"{ext}/cap/end")
    b = _hole(doc, f"{ext}/cap/end")
    engine = RebuildEngine()
    engine.rebuild(doc)
    engine.built = {fid: (data, 10.0) for fid, (data, _s) in engine.built.items()}
    assert remote.estimate(engine, doc, {}) == 0.0  # nothing changed
    doc.feature(a).params["depth"] = Param("2", 2.0)  # an edit to the first hole
    # That hole, the second hole's sketch and the second hole.
    assert remote.estimate(engine, doc, {}) == 30.0
    assert b in engine.built
    fresh = RebuildEngine()  # nothing built yet: the saved times count
    expected = {f.id: 1.0 for f in doc.features}
    assert remote.estimate(fresh, doc, expected) == float(len(doc.features))


def test_the_helper_can_be_turned_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(remote.DISABLE_ENV, "0")
    assert not remote.enabled()
    monkeypatch.delenv(remote.DISABLE_ENV)
    assert remote.enabled()
