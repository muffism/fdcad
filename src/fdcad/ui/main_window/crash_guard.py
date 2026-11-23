"""The crash guard (DECISIONS D1035): a part that closed FDCAD once does not do it twice.

The kernel is native code. FDCAD turns every error it reports into a feature error,
but a fault inside it (or a rebuild that never ends, stopped from the Task Manager)
closes the whole program. Before this guard the part that caused it could not be
opened again: opening rebuilt it and FDCAD closed again.

How it works:

1. While a feature is being built, a small note names it: ``<data>/Journal/<id>.json``
   holds the part's file, the feature's id and its name. The note is cleared when the
   rebuild ends and removed when the part closes. Writing it takes a few microseconds.
2. A note left behind by a process that is gone means FDCAD closed while building
   that feature. ``collect`` reads such notes at start.
3. When that part is opened again, ``apply`` puts a hold on the feature: rebuilds
   stop just before it (the document itself is not changed), and a bar in the view
   says so and offers to suppress the feature. Changing the feature, suppressing it
   or Force Rebuild lifts the hold.

Nothing here may ever stop a rebuild: every file error is swallowed.
"""

from __future__ import annotations

import contextlib
import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any

from PySide6.QtCore import QLockFile

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab, MainWindow
    from fdcad.ui.session import DocumentSession

HOLD = (
    "FDCAD closed unexpectedly the last time it rebuilt {name}. The rebuild now stops "
    "before {name}. Change {name} or use Suppress, then use Force Rebuild to build "
    "the rest."
)
#: The rebuild helper process ended while building a feature (D2600).
HELPER_LOST = (
    "The rebuild stopped unexpectedly while building {name}. The rebuild now stops "
    "before {name}. Change {name} or use Suppress, then use Force Rebuild to build "
    "the rest."
)
SUPPRESS = "Suppress {name}"
FOUND = "FDCAD closed unexpectedly last time, while rebuilding {name}."
#: Message bar key; one per feature, so hiding one never hides another.
KEY = "crash_hold:{fid}"


def journal_dir() -> Path:
    """The folder that holds the build notes."""
    from fdcad.ui.main_window.recovery import data_dir

    return data_dir() / "Journal"


@dataclass(frozen=True)
class Suspect:
    """A feature that was being built when FDCAD closed."""

    #: The part's file, or None for a part that was never saved.
    part: str | None
    feature_id: str
    feature_name: str

    def matches(self, path: Path | None, recovered: bool) -> bool:
        """True for the part this note was written for: the same file, or, for a part
        that had no file, any part brought back from an autosave."""
        if self.part is None:
            return path is None and recovered
        if path is None:
            return False
        return os.path.normcase(os.path.abspath(path)) == os.path.normcase(self.part)


def _lock_for(note: Path) -> QLockFile:
    lock = QLockFile(str(note.with_suffix(".lock")))
    lock.setStaleLockTime(0)  # stale only when its process is gone, never by age
    return lock


class BuildJournal:
    """The note of one open part. Made on first use, so parts that never rebuild a
    feature (every result cached) write nothing."""

    def __init__(self, folder: Path | None = None) -> None:
        self.folder = folder
        self.path: Path | None = None
        self._file: IO[str] | None = None
        self._lock: QLockFile | None = None
        self._broken = False

    def _open(self) -> IO[str] | None:
        if self._file is not None or self._broken:
            return self._file
        try:
            folder = self.folder or journal_dir()
            folder.mkdir(parents=True, exist_ok=True)
            self.path = folder / f"{uuid.uuid4().hex}.json"
            self._lock = _lock_for(self.path)
            self._lock.tryLock(0)
            self._file = open(self.path, "w", encoding="utf-8")  # noqa: SIM115  (kept open)
        except OSError:
            self._broken = True
        return self._file

    def begin(self, part: Path | None, feature_id: str, feature_name: str) -> None:
        """Note that this feature is being built now."""
        file = self._open()
        if file is None:
            return
        record = {
            "part": os.path.abspath(part) if part is not None else None,
            "feature": feature_id,
            "name": feature_name,
        }
        with contextlib.suppress(OSError, ValueError):
            file.seek(0)
            file.truncate()
            file.write(json.dumps(record))
            file.flush()  # handed to the system, so it outlives a crash of FDCAD

    def end(self) -> None:
        """The rebuild is over: nothing is being built."""
        if self._file is None:
            return
        with contextlib.suppress(OSError, ValueError):
            self._file.seek(0)
            self._file.truncate()
            self._file.flush()

    def close(self) -> None:
        """The part closed: remove the note."""
        file, self._file = self._file, None
        if file is not None:
            with contextlib.suppress(OSError, ValueError):
                file.close()
        if self._lock is not None:
            self._lock.unlock()
            self._lock = None
        if self.path is not None:
            with contextlib.suppress(OSError):
                self.path.unlink(missing_ok=True)
            self.path = None


def leftovers(folder: Path | None = None) -> list[Suspect]:
    """The notes of processes that are gone, read and removed. Notes of a FDCAD that
    is still running are left alone."""
    found: list[Suspect] = []
    folder = folder or journal_dir()
    try:
        notes = sorted(folder.glob("*.json"))
    except OSError:
        return found
    for note in notes:
        lock = _lock_for(note)
        if not lock.tryLock(0):
            continue  # its FDCAD is running
        try:
            data: Any = None
            with contextlib.suppress(OSError, ValueError):
                text = note.read_text(encoding="utf-8")
                data = json.loads(text) if text.strip() else None
            with contextlib.suppress(OSError):
                note.unlink(missing_ok=True)
        finally:
            lock.unlock()
        with contextlib.suppress(OSError):
            note.with_suffix(".lock").unlink(missing_ok=True)
        if isinstance(data, dict) and isinstance(data.get("feature"), str):
            part = data.get("part")
            found.append(
                Suspect(
                    part if isinstance(part, str) else None,
                    data["feature"],
                    str(data.get("name") or data["feature"]),
                )
            )
    return found


def collect(window: MainWindow) -> list[Suspect]:
    """At start: remember the features FDCAD closed on, and say so once."""
    from fdcad.applog import log

    suspects = leftovers()
    window.crash_suspects = suspects
    for suspect in suspects:
        log.warning(
            "Closed unexpectedly while rebuilding %s (%s) of %s",
            suspect.feature_name,
            suspect.feature_id,
            suspect.part or "an unsaved part",
        )
    if suspects:
        found = FOUND.format(name=suspects[-1].feature_name)
        window.status.setText(found)
        offer_report(window, found)
    return suspects


def offer_report(window: MainWindow, note: str) -> None:
    """A Report Problem button in the status bar, beside the message (D2871). No part
    is open yet at start, so there is no message bar to put it in. It goes once used."""
    from PySide6.QtWidgets import QPushButton

    from fdcad.ui import strings_feedback as text

    button = QPushButton(text.REPORT_PROBLEM)
    button.setObjectName("crash_report")
    button.setToolTip(text.REPORT_PROBLEM_TIP)

    def send() -> None:
        from fdcad.ui.help.report import send_report

        button.hide()
        window.crash_report = None
        send_report(window, note=note, summary=text.REPORT_CLOSED)
        button.deleteLater()

    button.clicked.connect(send)
    window.statusBar().addWidget(button)
    window.crash_report = button


def apply(window: MainWindow, session: DocumentSession, tab: DocumentTab) -> bool:
    """Put a hold on a part's suspect feature, before its first rebuild. True when held."""
    suspects: list[Suspect] = getattr(window, "crash_suspects", [])
    recovered = bool(getattr(session, "_recovered", False))
    for suspect in suspects:
        if not suspect.matches(session.path, recovered):
            continue
        feature = next((f for f in session.document.features if f.id == suspect.feature_id), None)
        if feature is None or feature.suppressed:
            continue
        suspects.remove(suspect)  # used once: the next open of this part is a normal one
        session.hold(feature.id)
        _hold_bar(session, tab, feature.id, HOLD.format(name=feature.name), feature.name)
        return True
    return False


def helper_lost(session: DocumentSession, tab: DocumentTab, fid: str, name: str) -> None:
    """The rebuild helper ended while building ``fid``; the session holds it (D2600)."""
    _hold_bar(session, tab, fid, HELPER_LOST.format(name=name), name)


def _hold_bar(session: DocumentSession, tab: DocumentTab, fid: str, text: str, name: str) -> None:
    def suppress(fid: str = fid) -> None:
        from fdcad.ui.commands.document import SetSuppressed

        if any(f.id == fid for f in session.document.features):
            session.undo.push(SetSuppressed(session, fid, True))
        session.release_hold()
        tab.message_bars.close_message(KEY.format(fid=fid))
        session.request_rebuild()

    bar = tab.message_bars.show_message(
        KEY.format(fid=fid),
        text,
        "warning",
        (SUPPRESS.format(name=name), suppress),
    )
    if bar is not None:
        bar.never_button.hide()  # each crash is its own news: nothing to hide for good
