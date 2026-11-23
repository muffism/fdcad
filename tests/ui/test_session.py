"""Document session: background rebuild, undo and redo, save and open."""

from collections.abc import Callable
from pathlib import Path

import pytest
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param, Variable
from fdcad.core.units import Kind, UnitSystem
from fdcad.ui.commands.document import (
    AddFeature,
    DeleteFeature,
    RenameFeature,
    SetParam,
    SetRollback,
    SetSuppressed,
    SetVariables,
)
from fdcad.ui.session import DocumentSession
from tests.core.features.test_features import plate


@pytest.fixture(autouse=True)
def _cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "cache"))


def _session(qtbot: QtBot) -> tuple[DocumentSession, str]:
    doc, ext = plate()
    session = DocumentSession(doc)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.request_rebuild()
    return session, ext


def _rebuilt(qtbot: QtBot, session: DocumentSession, action: Callable[[], object]) -> None:
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        action()


def test_rebuild_runs_in_background(qtbot: QtBot) -> None:
    session, ext = _session(qtbot)
    assert session.report is not None
    assert session.report.results[ext].body is not None
    assert not session.is_rebuilding


def test_set_param_undo_redo(qtbot: QtBot) -> None:
    session, ext = _session(qtbot)
    original = session.document.feature(ext).params["depth"]
    depth = Param("20", 20.0)
    _rebuilt(qtbot, session, lambda: session.undo.push(SetParam(session, ext, "depth", depth)))
    assert session.document.feature(ext).params["depth"] == depth
    assert session.report is not None and ext in session.report.rebuilt
    _rebuilt(qtbot, session, session.undo.undo)
    assert session.document.feature(ext).params["depth"] == original
    _rebuilt(qtbot, session, session.undo.redo)
    assert session.document.feature(ext).params["depth"] == depth


def test_delete_add_rename_suppress_rollback(qtbot: QtBot) -> None:
    session, ext = _session(qtbot)
    doc = session.document
    count = len(doc.features)
    _rebuilt(qtbot, session, lambda: session.undo.push(DeleteFeature(session, ext)))
    assert len(doc.features) == count - 1
    _rebuilt(qtbot, session, session.undo.undo)
    assert doc.features[-1].id == ext
    _rebuilt(qtbot, session, lambda: session.undo.push(RenameFeature(session, ext, "Base")))
    assert doc.feature(ext).name == "Base"
    _rebuilt(qtbot, session, lambda: session.undo.push(SetSuppressed(session, ext, True)))
    assert session.report is not None and ext not in session.report.results
    _rebuilt(qtbot, session, lambda: session.undo.push(SetRollback(session, "f4")))
    assert doc.rollback == "f4"
    for _ in range(3):
        _rebuilt(qtbot, session, session.undo.undo)
    assert doc.feature(ext).name == "Extrude f6"
    assert not doc.feature(ext).suppressed and doc.rollback is None
    again = doc.feature(ext)
    _rebuilt(qtbot, session, lambda: session.undo.push(AddFeature(session, again, 4)))
    assert doc.features[4].id == ext and len(doc.features) == count + 1


def test_variables_command(qtbot: QtBot) -> None:
    session, ext = _session(qtbot)
    session.document.feature(ext).params["depth"] = Param("=T", 10.0)
    new = [Variable("T", Kind.LENGTH, "15", 15.0)]
    _rebuilt(qtbot, session, lambda: session.undo.push(SetVariables(session, new)))
    assert session.document.feature(ext).params["depth"] == Param("=T", 15.0)


def test_title_dirty_save_and_open(qtbot: QtBot, tmp_path: Path) -> None:
    session, ext = _session(qtbot)
    assert session.title == "Untitled"
    _rebuilt(qtbot, session, lambda: session.undo.push(RenameFeature(session, ext, "Base")))
    assert session.is_dirty and session.title == "Untitled*"
    path = tmp_path / "plate.fdef"
    session.save(path)
    assert session.title == "plate" and not session.is_dirty
    reopened = DocumentSession.open(path)
    assert reopened.document == session.document


def test_new_session_units() -> None:
    session = DocumentSession.new(UnitSystem.IN)
    assert session.document.units is UnitSystem.IN
    assert len(session.document.features) == 4


def test_newer_edit_restarts_rebuild(qtbot: QtBot) -> None:
    session, ext = _session(qtbot)
    session.undo.push(SetParam(session, ext, "depth", Param("30", 30.0)))
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        session.undo.push(SetParam(session, ext, "depth", Param("40", 40.0)))
    report = session.report
    assert report is not None and report.body is not None
    box = Bnd_Box()
    BRepBndLib.Add_s(report.body.shape, box)
    assert box.CornerMax().Z() == pytest.approx(40, abs=1e-3)


def test_a_damaged_value_never_stops_the_rebuild(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Opening a part with a damaged value raised in the quick value refresh, after
    # the tab was added, so the part never rebuilt and no message showed (D634).
    from fdcad.ui import session as session_module

    def broken(*_args: object, **_kwargs: object) -> None:
        raise TypeError("damaged value")

    monkeypatch.setattr(session_module, "refresh_values", broken)
    session = DocumentSession.new(UnitSystem.MM)
    with qtbot.waitSignal(session.rebuilt, timeout=30000):
        session.request_rebuild()
    assert session.report is not None


def test_added_flat_pattern_goes_above_the_rollback_bar(qtbot: QtBot) -> None:
    """Audit D11 item 4, E item 10.1 (D719): it went below the bar, greyed and unbuilt."""
    from fdcad.ui.sheet_metal.flow import add_flat_pattern

    session, ext = _session(qtbot)
    doc = session.document
    _rebuilt(qtbot, session, lambda: session.undo.push(SetRollback(session, "f4")))
    flat = add_flat_pattern(session)
    ids = [f.id for f in doc.features]
    assert ids.index(flat.id) < ids.index(ext)  # above the rolled back extrude
    assert doc.rollback == flat.id  # the bar moved below the new feature


def test_save_writes_the_shape_cache_off_the_ui_thread(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Audit D3 item 2 (D723): kernel writes for the cache ran on the UI thread."""
    import threading

    from fdcad.core.cache import disk

    threads: list[str] = []
    real = disk.store
    monkeypatch.setattr(
        disk, "store", lambda *a: (threads.append(threading.current_thread().name), real(*a))
    )
    session, _ext = _session(qtbot)
    session.save(tmp_path / "part.fdprt")
    session.wait_cache(30.0)
    assert threads and threads[0] != threading.main_thread().name


def test_opening_a_part_stores_its_shape_for_the_next_open(qtbot: QtBot, tmp_path: Path) -> None:
    """D1091: only Save wrote the shape cache, so a part opened and closed without
    changes rebuilt in full on every open (51 s for the bike frame)."""
    from fdcad.core.cache import disk
    from fdcad.core.io import fdef

    doc, _ext = plate()
    path = tmp_path / "plate.fdprt"
    fdef.save(doc, path)
    session = DocumentSession.open(path)
    _rebuilt(qtbot, session, session.request_rebuild)
    qtbot.waitUntil(lambda: not session.is_rebuilding, timeout=20000)
    session.wait_cache(30.0)
    part = disk.load(disk.document_key(fdef.load(path)))
    assert part is not None and part.body is not None


def test_reopening_a_part_reuses_each_features_stored_result(qtbot: QtBot, tmp_path: Path) -> None:
    """D1097: the rebuild behind a part shown from the cache built every feature again
    (40 s for the bike frame); now it reuses the results stored beside the part."""
    from fdcad.core.io import fdef
    from tests.core.features.test_features import _hole

    doc, ext = plate()
    cut = _hole(doc, f"{ext}/cap/end")
    path = tmp_path / "plate.fdprt"
    fdef.save(doc, path)
    first = DocumentSession.open(path)
    _rebuilt(qtbot, first, first.request_rebuild)
    qtbot.waitUntil(lambda: not first.is_rebuilding, timeout=20000)
    first.wait_cache(30.0)
    again = DocumentSession.open(path)  # a new engine with an empty memory cache
    again.request_rebuild()
    qtbot.waitUntil(
        lambda: again.report is not None and not again.from_cache and not again.is_rebuilding,
        timeout=20000,
    )
    report = again.report
    assert report is not None and ext in report.reused and cut in report.reused


def test_a_saved_part_shows_from_its_own_file_on_another_computer(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D1102 (owner's choice): the first open of a part on a computer with no local cache
    built every feature before showing anything; the solid saved in the file shows it."""
    from tests.core.features.test_features import _hole

    doc, ext = plate()
    _hole(doc, f"{ext}/cap/end")
    session = DocumentSession(doc)
    _rebuilt(qtbot, session, session.request_rebuild)
    path = tmp_path / "plate.fdprt"
    session.save(path)
    session.wait_cache(30.0)
    assert '"solid"' in path.read_text(encoding="utf-8")
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "another computer"))
    again = DocumentSession.open(path)
    first: list[bool] = []
    again.rebuilt.connect(lambda _r: first.append(again.from_cache))
    again.request_rebuild()
    qtbot.waitUntil(lambda: bool(first), timeout=20000)
    assert first[0] is True  # shown from the file before the rebuild ended
    qtbot.waitUntil(lambda: not again.is_rebuilding, timeout=20000)
    assert again.not_rebuilt is False  # a quick part is still rebuilt (D1106)


def test_a_slow_saved_part_opens_without_a_rebuild(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D1106: the machine bed shown from its file then rebuilt every feature for 16
    minutes, and the kernel held Python's lock so the window froze. A saved part whose
    rebuild took long opens as saved; a change rebuilds it. Since D2600 this is what
    happens only when the rebuild helper is turned off."""
    from fdcad.core.rebuild import remote
    from fdcad.ui import session as session_module
    from tests.core.features.test_features import _hole

    monkeypatch.setenv(remote.DISABLE_ENV, "0")
    doc, ext = plate()
    hole = _hole(doc, f"{ext}/cap/end")
    session = DocumentSession(doc)
    _rebuilt(qtbot, session, session.request_rebuild)
    path = tmp_path / "plate.fdprt"
    session.save(path)
    session.wait_cache(30.0)
    assert '"seconds"' in path.read_text(encoding="utf-8")
    monkeypatch.setattr(session_module, "SLOW_OPEN_SECONDS", 0.0)  # this plate counts as slow
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "another computer"))
    again = DocumentSession.open(path)
    built: list[object] = []
    real = again.engine.rebuild
    monkeypatch.setattr(
        again.engine, "rebuild", lambda *a, **k: (built.append(1), real(*a, **k))[1]
    )
    _rebuilt(qtbot, again, again.request_rebuild)
    qtbot.waitUntil(lambda: not again.is_rebuilding, timeout=20000)
    assert built == [] and again.not_rebuilt and again.from_cache
    report = again.report
    assert report is not None and report.body is not None
    again.save(path)  # saving it unchanged keeps the solid it was opened from
    assert '"solid"' in path.read_text(encoding="utf-8")
    _rebuilt(qtbot, again, lambda: again.undo.push(SetSuppressed(again, hole, True)))
    qtbot.waitUntil(lambda: not again.is_rebuilding, timeout=20000)
    assert built and not again.not_rebuilt and not again.from_cache


def test_an_old_shape_cache_without_times_uses_the_times_in_the_file(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D1106: a shape cache written before build times were kept is read first; the
    times saved in the file still decide that the slow part opens without a rebuild."""
    from fdcad.core.cache import disk
    from fdcad.core.rebuild import remote
    from fdcad.ui import session as session_module
    from tests.core.features.test_features import _hole

    monkeypatch.setenv(remote.DISABLE_ENV, "0")
    doc, ext = plate()
    _hole(doc, f"{ext}/cap/end")
    session = DocumentSession(doc)
    _rebuilt(qtbot, session, session.request_rebuild)
    path = tmp_path / "plate.fdprt"
    session.save(path)
    session.wait_cache(30.0)
    report = session.report
    assert report is not None and report.body is not None
    old = disk.CachedPart(report.body, {fid: {"state": "ok"} for fid in report.results})
    monkeypatch.setattr(disk, "load", lambda _key: old)
    monkeypatch.setattr(session_module, "SLOW_OPEN_SECONDS", 0.0)
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "no history here"))
    again = DocumentSession.open(path)
    _rebuilt(qtbot, again, again.request_rebuild)
    qtbot.waitUntil(lambda: not again.is_rebuilding, timeout=20000)
    assert again.not_rebuilt


def test_a_changed_part_stores_no_shape_until_saved(qtbot: QtBot, tmp_path: Path) -> None:
    """D1091: a part with unsaved changes no longer matches its file, so its shape is
    not stored under the file's key."""
    from fdcad.core.cache import disk
    from fdcad.core.io import fdef

    doc, _ext = plate()
    path = tmp_path / "plate.fdprt"
    fdef.save(doc, path)
    session = DocumentSession.open(path)
    _rebuilt(qtbot, session, session.request_rebuild)
    qtbot.waitUntil(lambda: not session.is_rebuilding, timeout=20000)
    session.wait_cache(30.0)
    for f in disk.cache_dir().glob("*"):
        f.unlink()
    _rebuilt(qtbot, session, lambda: session.undo.push(SetSuppressed(session, _ext, True)))
    qtbot.waitUntil(lambda: not session.is_rebuilding, timeout=20000)
    session.wait_cache(30.0)
    assert list(disk.cache_dir().glob("*.json")) == []


def test_save_during_a_rebuild_leaves_the_cache_alone(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Audit D3 item 19 (D744): saving during a rebuild stored the old shape under the new
    document's key."""
    import threading

    from fdcad.core.cache import disk

    stored: list[object] = []
    session, _ext = _session(qtbot)
    monkeypatch.setattr(disk, "store", lambda *a: stored.append(a))
    session._running = threading.Event()  # a rebuild is running
    session.save(tmp_path / "part.fdprt")
    session.wait_cache(5.0)
    session._running = None
    assert stored == []


def test_deleting_a_graphs_position_keeps_the_graph_in_place(qtbot: QtBot) -> None:
    """Audit D3 item 6 (D735): the graph moved to the end of the tree, and Delete did not
    mention graphs that use the feature."""
    from fdcad.core.document.dependencies import graphs_using
    from fdcad.core.graph.model import Graph, Node
    from fdcad.ui.commands.document import DeleteFeature

    session, ext = _session(qtbot)
    doc = session.document
    before = doc.features[[f.id for f in doc.features].index(ext) - 1].id
    ref = Node("n1", "model_curve", {"source": {"feature": ext}})
    doc.graphs.append(Graph("g1", "Graph 1", position=ext, nodes=[ref]))
    assert graphs_using(doc, ext) == ["Graph 1"]
    _rebuilt(qtbot, session, lambda: session.undo.push(DeleteFeature(session, ext)))
    assert doc.graphs[0].position == before
    _rebuilt(qtbot, session, session.undo.undo)
    assert doc.graphs[0].position == ext


def test_saving_again_writes_the_same_solid(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # D2611: each save encoded the solid again, and the same shape came out as other
    # bytes, so a part saved twice with no change differed (the Save As sweep test).
    from fdcad.core.cache import saved_solid

    encoded: list[str] = []
    real = saved_solid.encode

    def counted(key, body, results):  # type: ignore[no-untyped-def]
        encoded.append(key)
        return real(key, body, results)

    monkeypatch.setattr(saved_solid, "encode", counted)
    session, ext = _session(qtbot)
    path = tmp_path / "plate.fdprt"
    session.save(path)
    first = path.read_bytes()
    session.save(path)
    assert len(encoded) == 1 and path.read_bytes() == first
    _rebuilt(
        qtbot,
        session,
        lambda: session.undo.push(SetParam(session, ext, "depth", Param("30", 30.0))),
    )
    session.save(path)
    assert len(encoded) == 2  # a new rebuild is encoded again
