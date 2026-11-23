"""Autosave to a recovery folder and recovery after a crash (PLAN Phase 1).

Each open part with unsaved changes is written to ``<data>/Recovery/<id>.fdprt``
with a small ``.json`` beside it naming the original file. A clean exit deletes
them, so files found at startup mean FDCAD did not close normally.

While FDCAD runs, each autosave is held by a ``<id>.lock`` lock file, so a
second FDCAD started meanwhile leaves the first one's autosaves alone (bug hunt
F10). The lock of a process that crashed is stale and is taken over.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QLockFile

from fdcad.core.document.model import Document
from fdcad.core.io import fdef
from fdcad.core.io.migrations import FileFormatError


def data_dir() -> Path:
    """FDCAD's data folder: ``FDCAD_DATA_DIR`` if set, else the platform location."""
    override = os.environ.get("FDCAD_DATA_DIR")
    if override:
        return Path(override)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "FDCAD"
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(base) / "FDCAD"


def recovery_dir() -> Path:
    """Folder that holds autosaved parts."""
    return data_dir() / "Recovery"


@dataclass
class Recovered:
    """An autosaved part found at startup."""

    document: Document
    original: Path | None
    files: tuple[Path, Path]
    #: The original file changed after the autosave, so the copy opens unnamed (D724).
    original_newer: bool = False


class Autosaver:
    """Writes autosave copies for one part."""

    def __init__(self) -> None:
        self.id = uuid.uuid4().hex
        folder = recovery_dir()
        self.fdef_path = folder / f"{self.id}{fdef.PART_SUFFIX}"
        self.meta_path = folder / f"{self.id}.json"
        self.lock = _lock_for(self.fdef_path)
        #: Why the last autosave failed, or empty.
        self.error = ""

    def save(self, document: Document, original: Path | None, wait: bool = True) -> None:
        """Write the autosave copy. Errors never interrupt work; the last one is kept in
        ``error`` so the window can say so once (audit D3 item 10, D724).

        The text is made here; with ``wait`` False the file is written in a background
        thread, so a large part does not stall the window."""
        try:
            text = fdef.dumps(document)
        except (TypeError, ValueError) as exc:
            self.error = str(exc)
            return
        meta = json.dumps({"original": str(original) if original else None})
        self.join()
        if not self.lock.isLocked():
            with contextlib.suppress(OSError):
                self.fdef_path.parent.mkdir(parents=True, exist_ok=True)
            self.lock.tryLock(0)
        if wait:
            self._write(text, meta)
            return
        self._job = threading.Thread(target=self._write, args=(text, meta), daemon=True)
        self._job.start()

    def _write(self, text: str, meta: str) -> None:
        try:
            self.fdef_path.parent.mkdir(parents=True, exist_ok=True)
            fdef.save_text(text, self.fdef_path)
            self.meta_path.write_text(meta, encoding="utf-8")
            self.error = ""
        except (OSError, ValueError) as exc:
            self.error = getattr(exc, "strerror", None) or str(exc)

    def join(self) -> None:
        """Wait for a background write to finish."""
        job = getattr(self, "_job", None)
        if job is not None:
            job.join(30.0)

    def discard(self) -> None:
        """Delete the autosave copy (after a save or a clean close)."""
        self.join()
        for path in (self.fdef_path, self.meta_path):
            path.unlink(missing_ok=True)
        if self.lock.isLocked():
            self.lock.unlock()


def _lock_for(part: Path) -> QLockFile:
    lock = QLockFile(str(part.with_suffix(".lock")))
    lock.setStaleLockTime(0)  # stale only when its process is gone, never by age
    return lock


def _in_use(part: Path) -> bool:
    """True when another running FDCAD holds the autosave ``part``."""
    lock = _lock_for(part)
    if lock.tryLock(0):
        lock.unlock()  # no owner, or a crashed one: free to recover
        return False
    info = lock.getLockInfo()  # (pid, host name, app name)
    pid = info[0] if isinstance(info, tuple) and info else None
    return pid != os.getpid()  # this process's own autosave is recoverable (tests)


def find_recoverable() -> list[Recovered]:
    """Autosaved parts left behind by a crash. Damaged files are skipped."""
    folder = recovery_dir()
    found: list[Recovered] = []
    if not folder.exists():
        return found
    parts = (p for p in folder.iterdir() if fdef.is_part_file(p))  # older builds wrote .fdef
    for path in sorted(parts):
        if _in_use(path):
            continue
        meta_path = path.with_suffix(".json")
        try:
            doc = fdef.load(path)
            meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        except (OSError, ValueError, RecursionError, FileFormatError):
            # Unreadable: set aside so it is not tried at every start, but kept for
            # someone who wants to look at it (audit D3 item 9, D724).
            with contextlib.suppress(OSError):
                path.rename(path.with_name(path.name + ".damaged"))
            continue
        if not isinstance(meta, dict):
            meta = {}  # a damaged note must not stop the start up scan (D709)
        original = Path(meta["original"]) if meta.get("original") else None
        newer = False
        try:
            # Saved again after the autosave: Save must not overwrite the newer file.
            newer = original is not None and original.stat().st_mtime > path.stat().st_mtime
        except OSError:
            newer = False
        found.append(Recovered(doc, None if newer else original, (path, meta_path), newer))
    return found


def discard_all(items: list[Recovered]) -> None:
    """Delete recovered files once they are open again or declined."""
    for item in items:
        for path in item.files:
            path.unlink(missing_ok=True)
