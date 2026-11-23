"""Long rebuilds in a helper process, so the window never waits on the kernel (D2600).

The kernel holds Python's lock for the whole of each call, so a rebuild on a worker
thread starved the window: on the machine bed (768 features) it stopped responding for
the whole 16 minute rebuild, and Cancel could not be clicked (IDEAS 68).

A rebuild that would take long runs in a second FDCAD process instead. It builds the
document and writes each feature's result to the history cache (``cache/history.py``,
D1097), the same files a reopened part reads. The app then reads those results back and
runs its own rebuild, which only builds sketches, planes and other quick features again.
While the helper works, the app process makes no kernel calls, so the window stays live.

A stopped helper writes the results it has so far, so the next rebuild goes on from
them: an edit made while a long rebuild runs does not start it again from nothing.

The two processes talk over a local pipe with a random key that only they know (the
standard library's ``multiprocessing.connection``). Nothing here imports Qt.
"""

from __future__ import annotations

import contextlib
import os
import secrets
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from multiprocessing.connection import Client, Listener
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fdcad.core.document.model import Document
    from fdcad.core.rebuild.engine import RebuildEngine

#: A rebuild expected to take longer than this (seconds) runs in the helper process.
REMOTE_SECONDS = 8.0
#: The argument that starts a packaged FDCAD as a helper (``packaging/launcher.py``).
WORKER_FLAG = "--rebuild-helper"
#: Environment variables that carry the pipe address and key to the helper.
_ADDRESS_ENV, _KEY_ENV = "FDCAD_HELPER_ADDRESS", "FDCAD_HELPER_KEY"
#: How long a stopped helper may take to write what it has (seconds), and how long the
#: helper has to start and answer.
_STOP_WAIT, _START_WAIT = 60.0, 120.0
#: Set to "0" to keep every rebuild in the app process (tests, troubleshooting).
DISABLE_ENV = "FDCAD_REBUILD_HELPER"
#: The last helper's own output, in the cache folder.
LOG_NAME = "rebuild-helper.log"


def enabled() -> bool:
    """False when the helper is turned off with ``FDCAD_REBUILD_HELPER=0``."""
    return os.environ.get(DISABLE_ENV, "1") != "0"


def estimate(engine: RebuildEngine, doc: Document, expected: dict[str, float]) -> float:
    """Seconds a rebuild of ``doc`` with ``engine`` would take: the build times of every
    feature from the first one that changed since the engine last built it.

    ``engine.built`` holds each feature's data and seconds from the last rebuild;
    ``expected`` gives seconds for features it has not built (from the saved part).
    """
    from fdcad.core.rebuild.engine import to_json_data_feature

    total, changed = 0.0, False
    for feature in doc.features:
        if feature.suppressed:
            continue
        seen = engine.built.get(feature.id)
        if not changed and seen is not None and seen[0] == to_json_data_feature(feature):
            continue
        changed = True
        total += seen[1] if seen is not None else expected.get(feature.id, 0.0)
        if doc.rollback == feature.id:
            break
    return total


@dataclass
class Outcome:
    """What a helper rebuild came to."""

    #: True when every feature was built and the results were written.
    done: bool = False
    #: True when it was stopped on request (it wrote what it had).
    stopped: bool = False
    #: History keys the helper wrote, newest first: read these back.
    keys: list[str] = field(default_factory=list)
    #: The feature it was building when it ended without a word (a native fault), or "".
    lost_on: tuple[str, str] = ("", "")
    #: Why it could not run, for the log; empty when it ran.
    problem: str = ""


def helper_command() -> list[str]:
    """The command that starts a helper: the packaged app with ``WORKER_FLAG``, or
    this Python running this module."""
    if getattr(sys, "frozen", False):
        return [sys.executable, WORKER_FLAG]
    return [sys.executable, "-m", "fdcad.core.rebuild.remote"]


def _address() -> str:
    token = secrets.token_hex(8)
    if sys.platform == "win32":
        return rf"\\.\pipe\fdcad-rebuild-{os.getpid()}-{token}"
    return str(Path(tempfile.gettempdir()) / f"fdcad-rebuild-{os.getpid()}-{token}")


def _family() -> str:
    return "AF_PIPE" if sys.platform == "win32" else "AF_UNIX"


def _start(address: str, key: bytes) -> subprocess.Popen[bytes]:
    env = dict(os.environ)
    env[_ADDRESS_ENV], env[_KEY_ENV] = address, key.hex()
    env["PYINSTALLER_SUPPRESS_SPLASH_SCREEN"] = "1"  # no boot picture for a helper
    flags = 0
    if sys.platform == "win32":
        # Below normal: the window keeps first call on the processor while it builds.
        flags = subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS
    from fdcad.core.cache import disk

    log: Any = subprocess.DEVNULL
    with contextlib.suppress(OSError):  # what went wrong in the last helper, for support
        disk.cache_dir().mkdir(parents=True, exist_ok=True)
        log = open(disk.cache_dir() / LOG_NAME, "wb")  # noqa: SIM115 - closed below
    try:
        return subprocess.Popen(  # our own program, no shell
            helper_command(),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            creationflags=flags,
        )
    finally:
        if log is not subprocess.DEVNULL:
            log.close()


def _connect(
    address: str, key: bytes, proc: subprocess.Popen[bytes], cancelled: Callable[[], bool]
) -> Any:
    """Connect to the helper once its pipe is open; None if it died or took too long."""
    deadline = time.monotonic() + _START_WAIT
    while time.monotonic() < deadline:
        if proc.poll() is not None or cancelled():
            return None
        try:
            return Client(address, family=_family(), authkey=key)
        except (FileNotFoundError, ConnectionRefusedError, OSError):
            time.sleep(0.05)
    return None


def _end(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is None:
        with contextlib.suppress(OSError):
            proc.kill()
    with contextlib.suppress(Exception):
        proc.wait(5)


def rebuild_remote(
    engine: RebuildEngine,
    doc: Document,
    seeds: list[str],
    progress: Callable[[int, int, str], None] | None = None,
    cancelled: Callable[[], bool] = lambda: False,
    on_build: Callable[[str, str], None] | None = None,
    quality: int | None = None,
) -> Outcome:
    """Build ``doc`` in a helper process, starting from the stored results under the
    history keys ``seeds``. Blocks until it ends; never makes kernel calls itself, so
    the caller should not hold the kernel lock. ``on_build`` gets each feature's id and
    name as the helper starts it, for the crash guard (D1035). With ``quality`` the
    helper also meshes the finished part for display at that quality; the mesh is
    stored with it, so the app does not spend seconds meshing it again."""
    from fdcad.core.cache import disk

    key = secrets.token_bytes(32)
    address = _address()
    try:
        proc = _start(address, key)
    except OSError as exc:
        return Outcome(problem=f"helper did not start: {exc}")
    building = ("", "")
    try:
        conn = _connect(address, key, proc, cancelled)
        if conn is None:
            stopped = cancelled()
            return Outcome(stopped=stopped, problem="" if stopped else "helper did not answer")
        with conn:
            options = {
                "full_sketches_only": engine.full_sketches_only,
                "simplify_threads": engine.simplify_threads,
                "real_once": engine.real_once,
                "quality": quality,
            }
            conn.send({"doc": doc, "seeds": seeds, "cache": str(disk.cache_dir()), **options})
            asked_stop = 0.0
            while True:
                if cancelled() and not asked_stop:
                    with contextlib.suppress(OSError):
                        conn.send("stop")
                    asked_stop = time.monotonic()
                if asked_stop and time.monotonic() - asked_stop > _STOP_WAIT:
                    return Outcome(stopped=True)
                try:
                    if not conn.poll(0.1):
                        if proc.poll() is not None:
                            raise EOFError
                        continue
                    message = conn.recv()
                except (EOFError, OSError):
                    if asked_stop:
                        return Outcome(stopped=True)
                    return Outcome(lost_on=building, problem="helper ended without a result")
                kind = message[0]
                if kind == "progress" and progress is not None:
                    progress(message[1], message[2], message[3])
                elif kind == "build":
                    building = (message[1], message[2])
                    if on_build is not None and message[1]:
                        with contextlib.suppress(Exception):
                            on_build(message[1], message[2])
                elif kind == "done":
                    if message[1]:
                        engine.real_once = False  # the helper used it up
                    return Outcome(done=True, keys=list(message[2]))
                elif kind == "stopped":
                    return Outcome(stopped=True, keys=list(message[1]))
                elif kind == "failed":
                    return Outcome(problem=str(message[1]))
    finally:
        _end(proc)


# The helper's side ----------------------------------------------------------------


def _serve(address: str, key: bytes) -> int:
    from fdcad.core.cache import disk
    from fdcad.core.cache.history import load_history, seed, store_history
    from fdcad.core.rebuild.engine import RebuildEngine

    with Listener(address, family=_family(), authkey=key) as listener:  # noqa: SIM117 - accept needs the listener
        with listener.accept() as conn:
            job: dict[str, Any] = conn.recv()
            doc = job["doc"]
            folder = Path(job["cache"])
            os.environ["FDCAD_CACHE_DIR"] = str(folder)  # write where the app reads
            engine = RebuildEngine()
            engine.full_sketches_only = bool(job.get("full_sketches_only"))
            engine.simplify_threads = bool(job.get("simplify_threads"))
            engine.real_once = bool(job.get("real_once"))
            used_real = engine.real_once
            for seed_key in reversed(job.get("seeds", [])):  # oldest first, newest wins
                with contextlib.suppress(Exception):
                    seed(engine.cache, load_history(folder, seed_key))
            stop = [False]

            def cancelled() -> bool:
                if not stop[0]:
                    with contextlib.suppress(EOFError, OSError):
                        while conn.poll():
                            if conn.recv() == "stop":
                                stop[0] = True
                return stop[0]

            engine.on_build = lambda f: conn.send(("build", f.id, f.name))
            try:
                report = engine.rebuild(
                    doc,
                    progress=lambda i, n, name: conn.send(("progress", i, n, name)),
                    cancelled=cancelled,
                )
            except Exception as exc:  # the app falls back to its own rebuild
                conn.send(("failed", f"{type(exc).__name__}: {exc}"))
                return 1
            conn.send(("build", "", ""))  # built: an end from here is no feature's fault
            doc_key = disk.document_key(doc)
            if report.cancelled:
                partial = f"{doc_key}.partial"
                written = 0
                with contextlib.suppress(Exception):
                    written = store_history(folder, partial, report.results)
                conn.send(("stopped", [partial] if written else []))
                return 0
            states = {
                fid: {
                    "state": r.state.value,
                    "messages": [i.message for i in r.issues],
                    "seconds": round(r.seconds, 3),
                }
                for fid, r in report.results.items()
            }
            quality = job.get("quality")
            if report.body is not None and isinstance(quality, int):
                from fdcad.core.display_mesh import mesh_for_display

                with contextlib.suppress(Exception):  # the app meshes it if this fails
                    mesh_for_display(report.body.shape, quality)
            disk.store(doc_key, report.body, states, report.results)
            conn.send(("done", used_real, [doc_key]))
    return 0


def main() -> int:
    """Run as a helper: build the document the app sends, then exit."""
    address, key = os.environ.get(_ADDRESS_ENV), os.environ.get(_KEY_ENV)
    if not address or not key:
        return 2
    os.environ.pop(_KEY_ENV, None)
    import faulthandler

    if sys.stderr is not None:
        faulthandler.enable()  # a native fault names its place in the helper's log
    return _serve(address, bytes.fromhex(key))


if __name__ == "__main__":
    raise SystemExit(main())
