"""Long rebuilds run in a helper process, so the window stays live (D2600)."""

import sys
from pathlib import Path

import pytest
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.rebuild import remote
from fdcad.ui.commands.document import SetParam
from fdcad.ui.session import DocumentSession
from tests.core.features.test_features import _hole, plate

HELPER = Path(__file__).parents[1] / "core" / "rebuild" / "helper_dies.py"


def _volume(shape: object) -> float:
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props, 1e-6)
    return float(props.Mass())


@pytest.fixture(autouse=True)
def _cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "cache"))


def _done(qtbot: QtBot, session: DocumentSession) -> None:
    qtbot.waitUntil(lambda: not session.is_rebuilding, timeout=60000)


def _watch_app_builds(session: DocumentSession) -> list[str]:
    built: list[str] = []
    session.engine.on_build = lambda feature: built.append(feature.id)
    return built


def test_a_slow_saved_part_rebuilds_in_the_helper_and_shows_every_feature(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # D1106 showed the saved shape and built nothing; the owner wants the part rebuilt.
    from fdcad.ui import session as session_module

    doc, ext = plate()
    hole = _hole(doc, f"{ext}/cap/end")
    first = DocumentSession(doc)
    with qtbot.waitSignal(first.rebuilt, timeout=20000):
        first.request_rebuild()
    path = tmp_path / "plate.fdprt"
    first.save(path)
    first.wait_cache(30.0)
    monkeypatch.setattr(session_module, "SLOW_OPEN_SECONDS", 0.0)  # this plate counts as slow
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "another computer"))
    again = DocumentSession.open(path)
    built = _watch_app_builds(again)
    again.request_rebuild()
    _done(qtbot, again)
    report = again.report
    assert report is not None and not report.cancelled and report.body is not None
    assert not again.not_rebuilt and not again.from_cache  # really rebuilt
    assert ext not in built and hole not in built  # the solids came from the helper
    assert ext in report.reused and hole in report.reused
    assert first.report is not None and first.report.body is not None
    assert _volume(report.body.shape) == pytest.approx(_volume(first.report.body.shape))
    assert again.engine.history_keys  # the next helper goes on from these


def test_a_long_edit_rebuilds_in_the_helper(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    doc, ext = plate()
    hole = _hole(doc, f"{ext}/cap/end")
    session = DocumentSession(doc)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.request_rebuild()
    monkeypatch.setattr(remote, "REMOTE_SECONDS", -1.0)  # every rebuild counts as long
    built = _watch_app_builds(session)
    session.undo.push(SetParam(session, ext, "depth", Param("20", 20.0)))
    _done(qtbot, session)
    report = session.report
    assert report is not None and report.body is not None and not report.cancelled
    assert ext not in built and hole not in built
    assert _volume(report.body.shape) == pytest.approx(50 * 50 * 20 - 3.14159265 * 25 * 20, 1e-6)


def test_stopping_a_helper_rebuild_shows_what_it_built(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc, ext = plate()
    for _ in range(6):
        _hole(doc, f"{ext}/cap/end")
    session = DocumentSession(doc)
    monkeypatch.setattr(remote, "REMOTE_SECONDS", -1.0)
    monkeypatch.setattr(remote, "helper_command", lambda: [sys.executable, str(HELPER), "slow"])
    steps: list[int] = []
    session.rebuild_progress.connect(lambda i, _n, _name: steps.append(i))
    session.request_rebuild()
    qtbot.waitUntil(lambda: len(steps) >= 3, timeout=60000)
    session.cancel_rebuild()
    _done(qtbot, session)
    report = session.report
    assert report is not None and report.cancelled
    assert len(report.results) < len(doc.features)


def test_a_helper_that_dies_holds_the_rebuild_before_that_feature(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A native fault on a feature used to close FDCAD (D1035); now only the helper ends.
    doc, ext = plate()
    hole = _hole(doc, f"{ext}/cap/end")
    session = DocumentSession(doc)
    monkeypatch.setattr(remote, "REMOTE_SECONDS", -1.0)
    monkeypatch.setattr(remote, "helper_command", lambda: [sys.executable, str(HELPER), hole])
    with qtbot.waitSignal(session.helper_lost, timeout=60000) as lost:
        session.request_rebuild()
    assert lost.args[0] == hole
    _done(qtbot, session)
    assert session.hold_before == hole
    report = session.report
    assert report is not None and not report.cancelled
    assert ext in report.results and hole not in report.results
