"""One open part: its document, file path, undo stack and background rebuilds.

Kernel work never runs on the UI thread (CLAUDE.md rule 2). A rebuild works on
a snapshot copy of the document, so editing can go on while it runs. A newer
edit cancels the running rebuild and starts a fresh one.
"""

from __future__ import annotations

import contextlib
import copy
import threading
import warnings
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtGui import QUndoStack

from fdcad.core.cache import disk
from fdcad.core.document.model import Document, new_document
from fdcad.core.io import fdef
from fdcad.core.kernel import kernel_job
from fdcad.core.rebuild.engine import RebuildEngine, RebuildReport, document_variables
from fdcad.core.rebuild.values import refresh_values
from fdcad.core.units import UnitSystem
from fdcad.ui.background import start_job
from fdcad.ui.strings import clause
from fdcad.ui.ui_turns import UiTurns, ui_turns


def add_sketch_edges(report: RebuildReport, doc: Document | None = None) -> None:
    """Make the 3D edges of every built sketch, for the viewport (off the UI thread).

    Construction geometry is shown only for sketches with Show Construction in Part
    on (TR339, D1703); their construction curves are also kept for Convert Entities.
    """
    from fdcad.core.sketch.construction_refs import shows_construction
    from fdcad.core.sketch.display import construction_edges, sketch_edges

    datas = {f.id: f.data for f in doc.features} if doc is not None else {}
    for fid, result in report.results.items():
        out = result.sketch
        if out is None:
            continue
        on = shows_construction(datas.get(fid) or {})
        with contextlib.suppress(Exception):  # display only, never break a rebuild
            shape = sketch_edges(out.model, out.plane, construction=on)
            if shape is not None:
                report.sketch_edges[fid] = shape
            if on:
                extra = construction_edges(out.model, out.plane)
                if extra is not None:
                    report.construction_edges[fid] = extra
    with contextlib.suppress(Exception):  # cosmetic threads (P4.2), display only
        from fdcad.core.features.cosmetic_thread import thread_pattern

        marks = [m for r in report.results.values() for m in r.threads]
        report.thread_edges = thread_pattern(marks) if marks else None


class GuardedUndoStack(QUndoStack):
    """The part's undo stack. While ``view_only`` (TR356, D971) every change is refused
    and ``blocked`` is emitted instead, so a part opened for viewing stays as it was."""

    blocked = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.view_only = False
        self._macro_depth = 0

    def push(self, cmd: Any) -> None:
        if self.view_only:
            self.blocked.emit()
            return
        super().push(cmd)

    def beginMacro(self, text: str) -> None:  # noqa: N802
        if self.view_only:
            self._macro_depth += 1
            return
        super().beginMacro(text)

    def endMacro(self) -> None:  # noqa: N802
        if self._macro_depth:
            self._macro_depth -= 1
            return
        super().endMacro()


#: A saved part whose last rebuild took longer than this (seconds) opens without one when
#: no stored results would make it quick (D1106).
SLOW_OPEN_SECONDS = 30.0
#: The name of a new part that has no file yet (D2682 numbers the second and later).
UNTITLED = "Untitled"


def free_untitled(used: set[str]) -> str:
    """The name for a new part: "Untitled", or the first of "Untitled 2", "Untitled 3"
    and so on that is not in ``used`` (casefolded names of the open parts) (D2682)."""
    if UNTITLED.casefold() not in used:
        return UNTITLED
    n = 2
    while f"{UNTITLED} {n}".casefold() in used:
        n += 1
    return f"{UNTITLED} {n}"


class _Signals(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object, int)  # RebuildReport, generation
    cached = Signal(object, int)  # a report from the disk cache, before the rebuild
    kept = Signal(int)  # generation: the shown part was kept and nothing rebuilt (D1106)
    #: The rebuild helper ended while building this feature (id, name, generation).
    lost = Signal(str, str, int)


class _RebuildJob(QRunnable):
    """Rebuilds a document snapshot and meshes the result for display."""

    def __init__(
        self,
        engine: RebuildEngine,
        doc: Document,
        generation: int,
        cancel: threading.Event,
        use_cache: bool = False,
        turns: UiTurns | None = None,
    ) -> None:
        super().__init__()
        self.use_cache = use_cache
        self.turns = turns
        self.engine = engine
        self.doc = doc
        self.generation = generation
        self.cancel = cancel
        self.signals = _Signals()

    def _show_cached(self) -> float | None:
        """Send the cached finished part first, so a saved part appears at once (PLAN 11.2).
        The seconds its last rebuild took, or None when no part was sent."""
        from fdcad.ui.viewport.meshing import mesh_for_display

        key = disk.document_key(self.doc)
        part = disk.load(key)
        if part is None:
            # The solid saved in the part file (D1102): a first open on this computer.
            from fdcad.core.cache.saved_solid import decode

            part = decode(self.doc, key)
        if part is None or part.body is None:
            return None
        report = disk.cached_report(self.doc, part)
        from fdcad.ui.viewport.display_quality import quality_of

        mesh_for_display(part.body.shape, quality_of(self.doc))
        self.signals.cached.emit(report, self.generation)
        from fdcad.core.cache.saved_solid import build_seconds

        seconds = build_seconds(part.states)
        states: Any = part.states
        saved = self.doc.solid
        if not seconds and isinstance(saved, dict) and saved.get("key") == key:
            # A shape cache written before build times were kept: the file's own (D1106).
            states = saved.get("states")
            seconds = build_seconds(states)
        if isinstance(states, dict):  # how long each feature takes, for D2600
            for fid, raw in states.items():
                with contextlib.suppress(AttributeError, TypeError, ValueError):
                    self.expected[str(fid)] = float(raw.get("seconds", 0.0))
        return seconds

    def _progress(self, index: int, total: int, name: str) -> None:
        self.signals.progress.emit(index, total, name)
        if self.turns is not None:
            self.turns.give_way()  # let a busy UI thread finish first (D631)

    def run(self) -> None:
        try:
            go_on = self._prepare()
            outcome = None
            if go_on == "helper":
                outcome = self._in_helper()  # without the kernel lock: no kernel calls
                if outcome.lost_on[0]:
                    # The helper ended while building a feature, as a native fault in
                    # the kernel would: building it here could close FDCAD. The session
                    # holds the rebuild before it and starts again (D1035).
                    report = RebuildReport(results={}, cancelled=True)
                    self.signals.finished.emit(report, self.generation)
                    return
                if outcome.problem and not outcome.lost_on[0] and self.shown_slow:
                    # The helper could not run and the shown part is slow to build: keep
                    # it, as before the helper (D1106).
                    self.signals.kept.emit(self.generation)
                    return
            if go_on != "kept":
                self.outcome = outcome
                self._run()
        finally:
            if self.turns is not None:
                self.turns.end()

    #: Expected build seconds per feature, from the part shown from the cache.
    expected: dict[str, float]
    #: True when the shown part took longer than ``SLOW_OPEN_SECONDS`` to build.
    shown_slow = False
    #: True when the session already has a newer edit waiting (set by the session).
    superseded: Any = staticmethod(lambda: False)
    #: What the helper process came to, for the rebuild after it (``remote.Outcome``).
    outcome: Any = None

    @kernel_job
    def _prepare(self) -> str:
        """Show the cached part, read stored results, and choose where to rebuild:
        "here", "helper" (a separate process, D2600) or "kept" (nothing to do)."""
        from fdcad.core.rebuild import remote

        self.expected = {}
        stored: list[Any] = []
        if self.use_cache:
            shown: float | None = None
            with contextlib.suppress(Exception):  # the cache is optional (FDEF_SPEC 13.5)
                shown = self._show_cached()
            with contextlib.suppress(Exception):
                # Each feature's stored result, so the rebuild below reuses them and
                # builds only the quick features again (D1097).
                from fdcad.core.cache.history import load_history, seed

                stored = load_history(disk.cache_dir(), disk.document_key(self.doc))
                cache = getattr(self.engine, "cache", None)
                if cache is not None and stored:
                    seed(cache, stored)
                    self.engine.history_keys.insert(0, disk.document_key(self.doc))
            self.shown_slow = shown is not None and shown > SLOW_OPEN_SECONDS and not stored
            if self.shown_slow and not remote.enabled():
                # The finished part is shown, and with no stored results the rebuild
                # would build every feature again: 16 minutes for the machine bed, with
                # the window starved of Python's lock throughout, since the kernel holds
                # it for each call (D1106). It is kept; the next change, or Rebuild,
                # builds the part.
                self.signals.kept.emit(self.generation)
                return "kept"
        if stored or not remote.enabled() or self.engine.frozen_results:
            return "here"
        if self.shown_slow:
            return "helper"  # shown at once; every feature is built in the helper
        with contextlib.suppress(Exception):
            if remote.estimate(self.engine, self.doc, self.expected) > remote.REMOTE_SECONDS:
                return "helper"
        return "here"

    def _in_helper(self) -> Any:
        from fdcad.core.rebuild import remote
        from fdcad.ui.viewport.display_quality import quality_of

        engine = self.engine
        quality = None
        with contextlib.suppress(Exception):
            quality = quality_of(self.doc)  # the helper meshes the finished part (TR214)
        outcome = remote.rebuild_remote(
            engine,
            self.doc,
            list(engine.history_keys[:4]),
            progress=self._progress,
            cancelled=self.cancel.is_set,
            quality=quality,
        )
        for key in reversed(outcome.keys):
            if key in engine.history_keys:
                engine.history_keys.remove(key)
            engine.history_keys.insert(0, key)
        del engine.history_keys[8:]
        if outcome.lost_on[0]:
            self.signals.lost.emit(outcome.lost_on[0], outcome.lost_on[1], self.generation)
        return outcome

    @kernel_job
    def _run(self) -> None:
        outcome = self.outcome
        cancelled = self.cancel.is_set
        on_build = self.engine.on_build
        if outcome is not None and outcome.keys:
            with contextlib.suppress(Exception):
                from fdcad.core.cache.history import load_history, seed

                seed(self.engine.cache, load_history(disk.cache_dir(), outcome.keys[0]))
        if outcome is not None and outcome.stopped:
            if self.superseded():
                # A newer edit waits: its rebuild goes on from what the helper wrote.
                report = RebuildReport(results={}, cancelled=True)
                self.signals.finished.emit(report, self.generation)
                return
            # Stopped by the user: show what was built, as a rebuild here would, and
            # stop at the first feature the helper had not built.
            began = threading.Event()

            def note(feature: Any) -> None:
                began.set()
                if on_build is not None:
                    on_build(feature)

            self.engine.on_build = note
            cancelled = began.is_set
        try:
            report = self.engine.rebuild(
                self.doc,
                progress=self._progress,
                cancelled=cancelled,
            )
            if outcome is not None and outcome.stopped:
                report.cancelled = True
            if report.body is not None and not report.cancelled:
                from fdcad.ui.viewport.display_quality import quality_of
                from fdcad.ui.viewport.meshing import mesh_for_display

                quality = quality_of(self.doc)  # TR214
                last = getattr(self.engine, "display_quality", quality)
                mesh_for_display(report.body.shape, quality, coarser=quality < last)
                self.engine.display_quality = quality  # type: ignore[attr-defined]
            if not report.cancelled:
                add_sketch_edges(report, self.doc)
                from fdcad.core.rebuild.change_line import describe

                with contextlib.suppress(Exception):  # the line is a nicety (TR290)
                    report.change = describe(self.doc, report)
                if self.doc.extra.get("checks"):  # TR359: expected values
                    from fdcad.core.checks import evaluate

                    body = report.body
                    report.checks = evaluate(self.doc, body.shape if body is not None else None)
        except Exception as exc:  # never let a rebuild failure reach the UI as a crash
            report = RebuildReport(
                results={}, variable_error=f"Rebuild failed: {clause(exc)}. Undo the last change."
            )
        finally:
            if outcome is not None and outcome.stopped:
                self.engine.on_build = on_build
        self.signals.finished.emit(report, self.generation)


class DocumentSession(QObject):
    """A part open in the app."""

    rebuild_started = Signal()
    rebuild_progress = Signal(int, int, str)
    rebuilt = Signal(object)  # RebuildReport
    changed = Signal()  # title, dirty state or file path changed
    display_changed = Signal()  # a sketch or plane was shown or hidden
    graph_changed = Signal(str)  # a node graph was edited (Phase 7), with its id
    #: Pause Rebuilds changed, or the part went out of date while paused (TR276).
    pause_changed = Signal()
    #: The rebuild helper ended while building a feature (id, name); it is held (D2600).
    helper_lost = Signal(str, str)

    def __init__(
        self,
        document: Document | None = None,
        path: Path | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.document = document or new_document()
        self.path = path
        self.undo = GuardedUndoStack(self)
        self.undo.cleanChanged.connect(self._clean_changed)
        self.engine = RebuildEngine()
        self.engine.on_build = self._note_build
        self.engine.on_done = self._note_done
        self.report: RebuildReport | None = None
        #: The report before the last rebuild, for Before and After (TR289, D2019).
        self.previous_report: RebuildReport | None = None
        self._generation = 0
        self._running: threading.Event | None = None
        self._pending = False
        self._recovered = False
        self._use_cache = False
        self.name: str | None = None  # shown for a part that has no file yet
        #: Shown for a new part with no file and no name: "Untitled", or "Untitled 2" and
        #: so on when other parts already use it, set when the tab opens (D2682).
        self.untitled = UNTITLED
        #: The STEP or mesh file an unsaved part was opened from, so opening it again
        #: switches to this tab (audit C item 18, D741).
        self.opened_from: Path | None = None
        #: The empty part made at start; closed when another opens, if unused (D1033).
        self.auto_blank = False
        #: The crash guard (D1035): the note of the feature being built, and a feature
        #: FDCAD closed on last time, with its data then. Rebuilds stop before it
        #: until it changes, is suppressed or the hold is released.
        from fdcad.ui.main_window.crash_guard import BuildJournal

        self.journal = BuildJournal()
        self.hold_before: str | None = None
        self._hold_data: Any = None
        self.from_cache = False  # True while the shown part comes from the disk cache
        #: The rebuild report whose solid the document carries now (D2611).
        self._solid_report: object | None = None
        #: The shown part is the saved one, not yet rebuilt in this session (D1106).
        self.not_rebuilt = False
        #: Warnings the user chose to keep this session: (feature id, issue code).
        self.dismissed: set[tuple[str, str]] = set()
        self._jobs: set[_RebuildJob] = set()  # kept alive until their signal arrives
        self._pool = QThreadPool.globalInstance()
        #: Pause Rebuilds (TR276, D835): edits are collected until Rebuild.
        self.paused = False
        self.out_of_date = False
        self._pause_index = 0
        #: The checkpoint feature the last rebuild stopped after, or None.
        self.stopped_at: str | None = None
        self._go_on = False

    @property
    def hidden(self) -> set[str]:
        """Sketches hidden on purpose (saved in the file, D114). A copy: change it with
        the ``SetVisibility`` command."""
        from fdcad.core.document.display import hidden_ids

        return hidden_ids(self.document)

    @property
    def shown(self) -> set[str]:
        """Sketches and planes shown on purpose (saved in the file, D114). A copy."""
        from fdcad.core.document.display import shown_ids

        return shown_ids(self.document)

    def _clean_changed(self, _clean: bool) -> None:
        self.changed.emit()

    # Files ------------------------------------------------------------------------

    @classmethod
    def new(cls, units: UnitSystem, parent: QObject | None = None) -> DocumentSession:
        """A session for a new part."""
        return cls(new_document(units), None, parent)

    @classmethod
    def open(cls, path: Path, parent: QObject | None = None) -> DocumentSession:
        """Open a `.fdef` file. Raises FileFormatError or OSError."""
        session = cls(fdef.load(path), Path(path), parent)
        session._use_cache = True
        return session

    def read_linked_equations(self, undoable: bool = True) -> str:
        """Read the linked equations file again (TR25, D749), then the variables read
        from CSV files (TR198, D2102). Returns a status note, or "" when the part has
        neither. ``undoable`` pushes each change as an undo step; without it (while
        opening) the values are put in directly."""
        notes = (self._read_equation_file(undoable), self.read_csv_lookups(undoable))
        return " ".join(n for n in notes if n)

    def read_csv_lookups(self, undoable: bool = True) -> str:
        """Read every variable that comes from a CSV file again (TR198, D2102)."""
        from fdcad.core.equations import csv_lookup
        from fdcad.ui import strings_config as text
        from fdcad.ui.equations.commands import SetEquations

        doc = self.document
        if not csv_lookup.has_lookups(doc):
            return ""
        variables, problems, changed = csv_lookup.refresh(doc, self.path)
        note = text.CSV_LOOKUP_READ.format(count=changed) if changed else ""
        if problems:
            note = (note + " " if note else "") + text.CSV_LOOKUP_FAILED.format(
                count=len(problems), first=problems[0]
            )
        if changed:
            command = SetEquations(self, variables, {}, text.CSV_LOOKUP_UNDO)
            if undoable:
                self.undo.push(command)
            else:
                command.apply()
        return note

    def _read_equation_file(self, undoable: bool) -> str:
        from fdcad.core.equations import text_file
        from fdcad.core.equations.edit import EquationError, apply_rows
        from fdcad.ui import strings_config as text
        from fdcad.ui.equations.commands import SetEquations
        from fdcad.ui.strings import clause

        doc = self.document
        if not doc.equations_file:
            return ""
        name = Path(doc.equations_file).name
        try:
            merged = text_file.read_linked(doc, self.path)
            assert merged is not None
            variables, features = apply_rows(doc, merged.rows)
        except (text_file.EquationFileError, EquationError, OSError) as exc:
            return text.EQ_LINK_FAILED.format(name=name, reason=clause(exc))
        note = (
            text.EQ_LINK_READ.format(count=merged.changed, name=name)
            if merged.changed
            else text.EQ_LINK_SAME.format(name=name)
        )
        if merged.skipped:
            note += text.EQ_IMPORT_SKIPPED.format(
                count=len(merged.skipped), names=", ".join(merged.skipped[:3])
            )
        if not merged.changed:
            return note
        command = SetEquations(self, variables, features, text.EQ_LINK_UNDO_READ)
        if undoable:
            self.undo.push(command)
        else:
            command.apply()
        return note

    def save(self, path: Path | None = None) -> None:
        """Save to ``path`` or the current path. Raises OSError or ValueError."""
        target = Path(path) if path is not None else self.path
        if target is None:
            raise ValueError("Choose where to save the part.")
        self.document.solid = self._solid_to_save()
        fdef.save(self.document, target)
        self.path = target
        self._recovered = False
        self.undo.setClean()
        self.changed.emit()
        # While a rebuild runs the report is for an older document: storing its shape
        # under the new document's key showed the old shape on the next open (audit D3
        # item 19, D744). The next save, or the rebuild's own result, writes it.
        if self.report is not None and not self.report.cancelled and not self.is_rebuilding:
            self._store_cache(self.report)

    def _solid_to_save(self) -> dict[str, Any]:
        """The finished solid to write into the part file (D1102), or nothing while the
        last rebuild is not of this document (running, cancelled, or none yet).

        Encoding is kernel work, so it runs on a worker thread; Save waits for it."""
        report = self.report
        kept = self.document.solid
        key = disk.document_key(self.document)
        if self.from_cache and not self.is_rebuilding and kept.get("key") == key:
            return kept  # shown from this solid and not rebuilt (D1106): keep it
        if kept.get("key") == key and report is not None and report is self._solid_report:
            # Encoded from this same rebuild by the last save: write it again as it is.
            # Encoding again gave other bytes for the same shape (flags the kernel sets
            # on a shape after it is first written), so each save changed the file (D2611).
            return kept
        if report is None or report.cancelled or self.is_rebuilding or self.from_cache:
            return {}
        if report.body is None or self.stopped_at is not None or self.hold_before is not None:
            return {}
        from fdcad.core.cache.saved_solid import encode

        found: list[dict[str, Any]] = []

        def work() -> None:
            with contextlib.suppress(Exception):  # the saved solid is optional
                found.append(encode(key, report.body, dict(report.results)))

        job = threading.Thread(target=work, daemon=True)
        job.start()
        job.join()
        if found:
            self._solid_report = report
        return found[0] if found else {}

    def _store_cache(self, report: RebuildReport) -> None:
        """Write the finished part to the shape cache under the document's key."""
        states = {
            fid: {
                "state": r.state.value,
                "messages": [i.message for i in r.issues],
                "seconds": round(r.seconds, 3),  # D1106: how long a rebuild would take
            }
            for fid, r in report.results.items()
        }
        # The shape cache is written in the background: kernel writes never run on
        # the UI thread (CLAUDE.md section 5 item 2, audit D3 item 2, D723).
        key, body = disk.document_key(self.document), report.body
        results = dict(report.results)  # each feature's result too (D1097)
        self.wait_cache()
        self._cache_job = threading.Thread(
            target=disk.store, args=(key, body, states, results), daemon=True
        )
        self._cache_job.start()

    def wait_cache(self, timeout: float | None = None) -> None:
        """Wait for a shape cache write started by ``save`` (tests, closing)."""
        job = getattr(self, "_cache_job", None)
        if job is not None:
            job.join(timeout)

    @property
    def view_only(self) -> bool:
        """True while the part is open for viewing only (TR356): changes are refused."""
        return bool(getattr(self.undo, "view_only", False))

    @view_only.setter
    def view_only(self, on: bool) -> None:
        self.undo.view_only = on

    @property
    def display_name(self) -> str:
        """The name of a part with no file: its own name, or its Untitled name."""
        return self.name or self.untitled

    @property
    def title(self) -> str:
        """File name, or "Untitled", with an asterisk when there are unsaved changes."""
        name = self.path.stem if self.path else self.display_name
        return f"{name}*" if self.is_dirty else name

    @property
    def is_dirty(self) -> bool:
        """True when there are changes since the last save."""
        if self._recovered:
            return True
        return not self.undo.isClean() or (self.path is None and self.undo.count() > 0)

    def mark_recovered(self) -> None:
        """Mark a part restored from autosave as unsaved until the user saves it."""
        self._recovered = True
        self.changed.emit()

    # Rebuild ----------------------------------------------------------------------

    @property
    def is_rebuilding(self) -> bool:
        """True while a rebuild runs."""
        return self._running is not None

    def request_rebuild(self, force: bool = False) -> None:
        """Start a rebuild, or restart the running one with the latest document. While
        rebuilds are paused, only mark the part out of date, unless ``force``."""
        if self.paused and not force:
            if not self.out_of_date:
                self.out_of_date = True
                self.pause_changed.emit()
            return
        if self._running is not None:
            self._running.set()
            self._pending = True
            return
        # Shown values only: the engine solves again and reports any error, so a
        # damaged value must never stop the rebuild from starting (D634).
        with contextlib.suppress(Exception):
            refresh_values(self.document, document_variables(self.document))
        self._generation += 1
        cancel = threading.Event()
        self._running = cancel
        turns = ui_turns()
        work = copy.deepcopy(self.document)
        self.stopped_at = None if self._go_on else self._checkpoint(work)
        if self.stopped_at is not None:
            work.rollback = self.stopped_at  # stop after the checkpoint (TR276)
        self._go_on = False
        self._apply_hold(work)
        job = _RebuildJob(
            self.engine,
            work,
            self._generation,
            cancel,
            self._use_cache,
            turns,
        )
        self._use_cache = False
        job.superseded = lambda: self._pending
        job.signals.cached.connect(self._cached)
        job.signals.kept.connect(self._kept)
        job.signals.lost.connect(self._lost)
        job.signals.progress.connect(self.rebuild_progress)
        job.signals.finished.connect(self._finished)
        self._jobs.add(job)
        self.rebuild_started.emit()
        turns.begin()
        start_job(self._pool, job)

    # The crash guard (D1035) ------------------------------------------------------

    def _note_build(self, feature: Any) -> None:
        self.journal.begin(self.path, feature.id, feature.name)

    def _note_done(self) -> None:
        self.journal.end()

    def hold(self, fid: str) -> None:
        """Stop rebuilds just before ``fid`` until it changes or the hold is released."""
        from fdcad.core.rebuild.engine import to_json_data_feature

        feature = next((f for f in self.document.features if f.id == fid), None)
        if feature is None:
            return
        self.hold_before = fid
        self._hold_data = to_json_data_feature(feature)

    def release_hold(self) -> None:
        """Let every feature rebuild again."""
        self.hold_before, self._hold_data = None, None

    def _apply_hold(self, work: Document) -> None:
        """On the copy a rebuild works on: stop before the held feature. A held feature
        that was changed, suppressed or deleted since is no longer held."""
        from fdcad.core.rebuild.engine import to_json_data_feature

        fid = self.hold_before
        if fid is None:
            return
        ids = [f.id for f in work.features]
        feature = work.features[ids.index(fid)] if fid in ids else None
        if (
            feature is None
            or feature.suppressed
            or to_json_data_feature(feature) != self._hold_data
        ):
            self.release_hold()
            return
        index = ids.index(fid)
        if index == 0:
            for each in work.features:  # nothing can come before it: build nothing
                each.suppressed = True
            return
        bar = work.rollback
        if bar is None or bar not in ids or ids.index(bar) >= index:
            work.rollback = ids[index - 1]

    # Pause Rebuilds and checkpoints (TR276, D835) -----------------------------------

    @staticmethod
    def _checkpoint(doc: Document) -> str | None:
        """The first checkpoint feature that builds before the rollback bar, or None."""
        for feature in doc.features:
            if feature.data.get("checkpoint") is True and not feature.suppressed:
                if feature is doc.features[-1]:
                    return None  # nothing after it to stop before
                return feature.id
            if doc.rollback == feature.id:
                return None
        return None

    def set_paused(self, on: bool) -> None:
        """Pause Rebuilds on, or off (which rebuilds when the part is out of date)."""
        if on == self.paused:
            return
        self.paused = on
        if on:
            self._pause_index = self.undo.index()
            self.out_of_date = False
        elif self.out_of_date:
            self.out_of_date = False
            self.request_rebuild()
        self.pause_changed.emit()

    def rebuild_paused(self, stay: bool) -> None:
        """Apply the collected edits; with ``stay`` rebuilds stay paused after."""
        if not stay:
            self.set_paused(False)
            if not self.out_of_date:
                self.request_rebuild()
            return
        self._pause_index = self.undo.index()
        self.out_of_date = False
        self.request_rebuild(force=True)
        self.pause_changed.emit()

    def discard_paused(self) -> None:
        """Undo every edit made since the pause (or the last Rebuild and Stay Paused) and
        leave the pause."""
        if not self.paused:
            return
        self.undo.setIndex(min(self._pause_index, self.undo.count()))
        self.out_of_date = False
        self.paused = False
        self.request_rebuild()
        self.pause_changed.emit()

    def continue_rebuild(self) -> None:
        """Rebuild once past every checkpoint."""
        self._go_on = True
        self.request_rebuild(force=True)

    def close(self) -> None:
        """Free what a closed part holds (CLAUDE.md 5A.3, round 10e D633).

        The main window owned every session, so a closed part kept its undo
        history, its last rebuild with every feature's shapes and its tab until
        the app quit. Panels may still hold this session for a moment; they see
        an empty part, and Python frees it once the last of them lets go.
        """
        self.cancel_rebuild()
        self.journal.close()
        self.wait_cache(10.0)  # a shape cache write in progress finishes first
        self.undo.clear()
        self.engine.cache.clear()
        self.report = None
        self.previous_report = None
        signals = (
            self.rebuild_started,
            self.rebuild_progress,
            self.rebuilt,
            self.changed,
            self.display_changed,
            self.graph_changed,
            self.pause_changed,
            self.helper_lost,
        )
        for signal in signals:
            # The window's slots hold the closed tab; nothing listens to a closed part.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                with contextlib.suppress(RuntimeError, TypeError):
                    signal.disconnect()
        self.setParent(None)

    def cancel_rebuild(self) -> None:
        """Stop the running rebuild at the next feature."""
        if self._running is not None:
            self._running.set()
        self._pending = False

    def _cached(self, report: RebuildReport, generation: int) -> None:
        if generation == self._generation and self.report is None:
            self.report = report
            self.from_cache = True
            self.rebuilt.emit(report)

    def _kept(self, generation: int) -> None:
        """The opened part was shown from its saved solid and not rebuilt (D1106)."""
        self._jobs = {j for j in self._jobs if j.generation != generation}
        self._running = None
        if self._pending:
            self._pending = False
            self.request_rebuild()
            return
        if generation == self._generation and self.report is not None:
            self.not_rebuilt = True
            self.rebuilt.emit(self.report)

    def _lost(self, fid: str, name: str, generation: int) -> None:
        """The rebuild helper ended while building ``fid`` (D2600): hold the rebuild
        before it, as the crash guard does after FDCAD closed on one (D1035), and build
        the rest again."""
        if generation != self._generation:
            return
        self.hold(fid)
        self.lost_feature = (fid, name)
        self._pending = True  # _finished starts the held rebuild
        self.helper_lost.emit(fid, name)

    def _finished(self, report: RebuildReport, generation: int) -> None:
        self.from_cache = False
        self.not_rebuilt = False
        self._jobs = {j for j in self._jobs if j.generation != generation}
        self._running = None
        if self._pending:
            self._pending = False
            self.request_rebuild()
            return
        if generation == self._generation:
            if self.report is not None and self.report is not report:
                self.previous_report = self.report
            self.report = report
            if (
                not report.cancelled
                and self.path is not None
                and not self.is_dirty
                and self.stopped_at is None
                and self.hold_before is None
            ):
                # The part is as its file says, so this shape is what the file builds:
                # store it, so opening the file again shows it at once. Only Save
                # stored it, so a part opened and closed unchanged rebuilt in full
                # every time (51 s for a bike frame, D1091).
                self._store_cache(report)
            self.rebuilt.emit(report)

    def wait(self, timeout_ms: int = 30000) -> bool:
        """Block until background work is done (for tests and shutdown)."""
        with ui_turns().hold():  # the UI thread blocks on purpose: rebuilds must not wait
            return bool(self._pool.waitForDone(timeout_ms))
