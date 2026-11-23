"""App event filters do nothing off the GUI thread (IDEAS 48, D2659).

When FDCAD is ended from outside (Git Bash's ``kill``), the exit runs on a thread of
its own and Qt still hands that thread a few events whose C++ objects are gone. The
key position filter's first look at one, ``event.type()``, was an access violation
in ``crash.log``. Each filter on the whole app now returns before it touches the
event when called off the GUI thread.
"""

from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent

from fdcad.app import _FileOpenFilter
from fdcad.ui.gui_thread import off_gui_thread
from fdcad.ui.input.key_position import KeyPositionFilter

ROOT = Path(__file__).resolve().parents[2]


class _GoneEvent:
    """Stands for an event whose C++ object is gone: any use of it fails."""

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"the filter used the event ({name})")

    @property  # type: ignore[misc]
    def __class__(self) -> Any:  # isinstance asks for it: that is a use too
        raise AssertionError("the filter asked what kind of event it is")


def _off_thread(call: Any) -> list[object]:
    out: list[object] = []

    def run() -> None:
        try:
            out.append(call())
        except BaseException as exc:  # reported to the test below
            out.append(exc)

    worker = threading.Thread(target=run)
    worker.start()
    worker.join(10)
    return out


def test_off_gui_thread_is_false_here_and_true_elsewhere() -> None:
    assert not off_gui_thread()
    assert _off_thread(off_gui_thread) == [True]


def test_the_key_position_filter_leaves_events_alone_off_the_gui_thread() -> None:
    ran: list[str] = []
    keys = KeyPositionFilter(lambda letter: ran.append(letter) or True, lambda: None)
    assert _off_thread(lambda: keys.eventFilter(QObject(), _GoneEvent())) == [False]  # type: ignore[arg-type]
    # On the GUI thread it still reads events (tests/ui/test_key_position.py has the rest).
    press = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_L, Qt.KeyboardModifier.NoModifier, "l")
    assert keys.eventFilter(QObject(), press) is False  # a Latin letter: Qt's own shortcut
    assert ran == []


def test_the_file_open_filter_leaves_events_alone_off_the_gui_thread() -> None:
    opened: list[Path] = []
    files = _FileOpenFilter(opened.append)
    assert _off_thread(lambda: files.eventFilter(QObject(), _GoneEvent())) == [False]  # type: ignore[arg-type]
    assert files.eventFilter(QObject(), QEvent(QEvent.Type.KeyPress)) is False


def test_every_filter_on_the_whole_app_has_the_guard() -> None:
    # A new filter on the app must ask off_gui_thread first too.
    installed = []
    for path in (ROOT / "src" / "fdcad").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        installed += re.findall(r"\b(?:app|qApp|instance\(\))\.installEventFilter\((\w+)", text)
    assert sorted(installed) == ["file_filter", "keys"]
    for module, cls in (
        ("app.py", "_FileOpenFilter"),
        ("ui/input/key_position.py", "KeyPositionFilter"),
    ):
        text = (ROOT / "src" / "fdcad" / module).read_text(encoding="utf-8")
        body = text.split(f"class {cls}", 1)[1].split("def eventFilter", 1)[1]
        first = next(ln.strip() for ln in body.splitlines()[1:] if ln.strip())
        assert first == "if off_gui_thread():", (cls, first)
