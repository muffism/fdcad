"""The crash guard (D1035): a part that closed FDCAD once does not do it twice."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from pytestqt.qtbot import QtBot

from fdcad.core.io import fdef
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.ui.main_window import crash_guard
from fdcad.ui.main_window.crash_guard import BuildJournal, Suspect, leftovers
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.session import DocumentSession
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]

SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "bracket.fdprt"

_DIE_WHILE_BUILDING = """
import os, sys
from pathlib import Path
from fdcad.ui.main_window.crash_guard import BuildJournal
journal = BuildJournal(Path(sys.argv[1]))
journal.begin(Path(sys.argv[2]), "f7", "Fillet 3")
if sys.argv[3] == "finished":
    journal.end()
os._exit(3)  # no clean up, like a fault in the kernel
"""


def _die(folder: Path, part: Path, how: str) -> None:
    done = subprocess.run(
        [sys.executable, "-c", _DIE_WHILE_BUILDING, str(folder), str(part), how],
        check=False,
        timeout=120,
    )
    assert done.returncode == 3


def test_note_is_written_cleared_and_removed(tmp_path: Path) -> None:
    journal = BuildJournal(tmp_path)
    assert list(tmp_path.iterdir()) == []  # nothing until a feature is built
    journal.begin(tmp_path / "a.fdprt", "f3", "Fillet 3")
    assert journal.path is not None and '"Fillet 3"' in journal.path.read_text("utf-8")
    assert leftovers(tmp_path) == []  # its FDCAD (this test) is still running
    journal.end()
    assert journal.path.read_text("utf-8") == ""
    note = journal.path
    journal.close()
    assert not note.exists()


def test_a_process_that_dies_while_building_leaves_a_suspect(tmp_path: Path) -> None:
    part = tmp_path / "bracket.fdprt"
    _die(tmp_path / "notes", part, "building")
    found = leftovers(tmp_path / "notes")
    assert found == [Suspect(str(part.resolve()), "f7", "Fillet 3")]
    assert found[0].matches(part, recovered=False)
    assert not found[0].matches(tmp_path / "other.fdprt", recovered=False)
    assert list((tmp_path / "notes").glob("*.json")) == []  # read once, then removed
    assert leftovers(tmp_path / "notes") == []


def test_a_process_that_dies_between_rebuilds_leaves_none(tmp_path: Path) -> None:
    _die(tmp_path / "notes", tmp_path / "bracket.fdprt", "finished")
    assert leftovers(tmp_path / "notes") == []


def test_unsaved_part_suspect_matches_only_recovered_parts() -> None:
    suspect = Suspect(None, "f2", "Extrude 1")
    assert suspect.matches(None, recovered=True)
    assert not suspect.matches(None, recovered=False)
    assert not suspect.matches(Path("a.fdprt"), recovered=True)


def test_engine_tells_before_building_and_when_done() -> None:
    doc = fdef.load(SAMPLE)
    engine = RebuildEngine()
    built: list[str] = []
    done: list[int] = []
    engine.on_build = lambda feature: built.append(feature.id)
    engine.on_done = lambda: done.append(1)
    report = engine.rebuild(doc)
    assert built == report.rebuilt and built  # each built feature, in order
    engine.on_build = lambda feature: 1 / 0  # a broken note never stops a rebuild
    assert engine.rebuild(doc).reused  # all cached now: nothing is built
    assert len(done) == 2


def _solid_features(session: DocumentSession) -> list[str]:
    return [
        f.id for f in session.document.features if f.type in ("extrude", "extruded_cut", "hole")
    ]


def test_hold_stops_before_the_feature_until_it_changes(qtbot: QtBot) -> None:
    session = DocumentSession.open(SAMPLE)
    ids = [f.id for f in session.document.features]
    held = _solid_features(session)[-1]
    session.hold(held)
    with qtbot.waitSignal(session.rebuilt, timeout=60000):
        session.request_rebuild()
    assert session.report is not None
    assert held not in session.report.results
    assert all(fid not in session.report.results for fid in ids[ids.index(held) :])
    assert ids[ids.index(held) - 1] in session.report.results
    assert session.document.rollback is None  # the part itself is not changed
    # Changing the feature lifts the hold: the user did what the message asked.
    session.document.feature(held).name += " changed"
    with qtbot.waitSignal(session.rebuilt, timeout=60000):
        session.request_rebuild()
    assert session.hold_before is None
    assert held in session.report.results
    session.close()


def test_opening_a_suspect_part_holds_it_and_offers_to_suppress(
    qtbot: QtBot, window: MainWindow
) -> None:
    doc = fdef.load(SAMPLE)
    feature = next(f for f in reversed(doc.features) if f.type in ("extrude", "extruded_cut"))
    window.crash_suspects = [Suspect(str(SAMPLE.resolve()), feature.id, feature.name)]
    window.open_path(SAMPLE)
    tab = window.current
    assert isinstance(tab, DocumentTab)
    assert tab.session.hold_before == feature.id
    assert window.crash_suspects == []  # used once
    key = crash_guard.KEY.format(fid=feature.id)
    bar = tab.message_bars.bars[key]
    assert feature.name in bar.label.text()
    assert bar.action_button is not None and feature.name in bar.action_button.text()
    tab.session.wait()
    qtbot.wait(50)
    bar.action_button.click()
    assert tab.session.document.feature(feature.id).suppressed
    assert tab.session.hold_before is None
    assert key not in tab.message_bars.bars
    tab.session.undo.undo()  # one undo step brings the feature back
    assert not tab.session.document.feature(feature.id).suppressed
    tab.session.wait()


def test_force_rebuild_lifts_the_hold(qtbot: QtBot, window: MainWindow) -> None:
    window.open_path(SAMPLE)
    tab = window.current
    assert isinstance(tab, DocumentTab)
    tab.session.wait()
    tab.session.hold(_solid_features(tab.session)[-1])
    window.force_rebuild()
    assert tab.session.hold_before is None
    tab.session.wait()


def test_native_faults_are_written_to_a_file(tmp_path: Path) -> None:
    import faulthandler

    from fdcad import applog

    was_on = faulthandler.is_enabled()
    try:
        applog._watch_native_faults(tmp_path)
        assert faulthandler.is_enabled()
        assert "started" in (tmp_path / "crash.log").read_text("utf-8")
    finally:
        faulthandler.disable()
        if applog._fault_file is not None:
            applog._fault_file.close()
            applog._fault_file = None
        if was_on:
            faulthandler.enable()
