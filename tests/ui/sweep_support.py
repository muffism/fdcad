"""Shared steps of the app sweep (PLAN Phase 6 bug hunt, docs/BUG_HUNT.md, D490).

The sweep drives the main window on the Qt offscreen platform. Modal dialogs,
message boxes and file pickers are replaced so nothing waits for a person:
dialogs either cancel or accept with their defaults, and every message shown
is recorded so its wording can be checked.
"""

from __future__ import annotations

import difflib
import re
import time
import traceback
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QEvent, QSettings, QThreadPool
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QDialog,
    QFileDialog,
    QInputDialog,
    QMenu,
    QMessageBox,
)

from fdcad.core.io import fdef
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.session import DocumentSession

#: Commands the sweep does not run: they open or close whole parts.
# Close All and Revert to Saved close the part being swept (TR218).
SKIP = frozenset({"file.new", "file.open", "file.close", "file.close_all", "file.revert"})
#: The longest one step may take before it counts as a hang (seconds).
STEP_LIMIT = 30.0
#: Feature ids are never reused, so ``next_id`` may grow on Cancel or Undo (D490).
_NEXT_ID = re.compile(r'"next_id": \d+')
SELECTION_KINDS = ("none", "face", "edge", "vertex", "sketch", "body")


def text_of(tab: DocumentTab) -> str:
    """The part's file text, without the id counter (D490)."""
    return _NEXT_ID.sub('"next_id": 0', fdef.dumps(tab.session.document))


@dataclass
class Dialogs:
    """What the replaced dialogs do, and what they showed."""

    accept: bool = False
    save_path: str = ""
    save_filter: str = ""
    shown: list[str] = field(default_factory=list)


def install_dialogs(monkeypatch: pytest.MonkeyPatch) -> Dialogs:
    """Replace every modal dialog so the sweep never waits for a person."""
    state = Dialogs()

    def exec_(self: QDialog) -> int:
        state.shown.append(f"dialog {type(self).__name__}: {self.windowTitle()}")
        if state.accept:
            self.accept()
            return 1
        self.reject()
        return 0

    def box(kind: str) -> Callable[..., Any]:
        def show(_parent: Any, _title: str, text: str, *_a: Any, **_k: Any) -> Any:
            state.shown.append(f"{kind}: {text}")
            if kind == "question":
                yes = QMessageBox.StandardButton.Yes
                return yes if state.accept else QMessageBox.StandardButton.No
            return QMessageBox.StandardButton.Ok

        return staticmethod(show)

    def box_exec(self: QMessageBox) -> int:
        state.shown.append(f"box: {self.text()}")
        return int(QMessageBox.StandardButton.Cancel.value)

    monkeypatch.setattr(QDialog, "exec", exec_)
    monkeypatch.setattr(QMessageBox, "exec", box_exec)
    for kind in ("question", "warning", "information", "critical"):
        monkeypatch.setattr(QMessageBox, kind, box(kind))
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *_a, **_k: (state.save_path, state.save_filter)),
    )
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *_a, **_k: ("", "")))
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", staticmethod(lambda *_a, **_k: ([], "")))
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *_a, **_k: ""))
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *_a, **_k: ("", False)))
    monkeypatch.setattr(  # Comment... in the tree menu (TR23)
        QInputDialog, "getMultiLineText", staticmethod(lambda *_a, **_k: ("", False))
    )
    monkeypatch.setattr(QInputDialog, "getDouble", staticmethod(lambda *_a, **_k: (0.0, False)))
    monkeypatch.setattr(QInputDialog, "getInt", staticmethod(lambda *_a, **_k: (0, False)))
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *_a, **_k: ("", False)))
    monkeypatch.setattr(QColorDialog, "getColor", staticmethod(lambda *_a, **_k: QColor()))
    monkeypatch.setattr(QMenu, "exec", lambda *_a, **_k: None)
    return state


def make_window(tmp_path: Path) -> MainWindow:
    """A shown main window with its own preferences file."""
    settings = Settings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))
    win = MainWindow(settings)
    win.show()
    win.finish_setup()
    return win


def close_window(win: MainWindow) -> None:
    """Close every part without a save prompt, then the window."""
    while win.tabs.count():
        tab = win.tabs.widget(0)
        if isinstance(tab, DocumentTab):
            tab.session.cancel_rebuild()
            tab.session.wait()
            tab.autosaver.discard()
        win.tabs.removeTab(0)
    win.close()
    win.deleteLater()


def pump(ms: int = 0) -> None:
    """Process events for ``ms`` milliseconds."""
    app = QApplication.instance()
    assert app is not None
    end = time.monotonic() + ms / 1000
    app.processEvents()
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.002)
    # The app's event loop deletes closed panels and dialogs; processEvents alone
    # never does, so without this the sweep kept every one and slowed down (D638).
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)


def idle(tab: DocumentTab, timeout: float = STEP_LIMIT) -> bool:
    """Wait until no rebuild or background job runs. False after ``timeout`` seconds."""
    app = QApplication.instance()
    assert app is not None
    pool = QThreadPool.globalInstance()
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if not tab.session.is_rebuilding and pool.activeThreadCount() == 0:
            app.processEvents()
            if not tab.session.is_rebuilding:
                return True
        time.sleep(0.002)
    return False


def open_part(win: MainWindow, path: Path) -> DocumentTab:
    """Open a sample as an untitled part and wait for its rebuild."""
    session = DocumentSession(fdef.load(path), None, win)
    session.name = path.stem
    tab = win.add_session(session)
    assert idle(tab, 120), f"{path.name}: the first rebuild did not finish"
    return tab


def close_part(win: MainWindow, tab: DocumentTab) -> None:
    """Close a part without a save prompt."""
    settle(win, tab)
    tab.session.cancel_rebuild()
    tab.session.wait()
    tab.autosaver.discard()
    win.tabs.removeTab(win.tabs.indexOf(tab))
    tab.deleteLater()


def close_popups(win: MainWindow) -> None:
    """Close menus, dialogs and tool windows the last step left open."""
    for widget in QApplication.topLevelWidgets():
        if widget is win or not widget.isVisible():
            continue
        if isinstance(widget, QDialog):
            widget.reject()
        else:
            widget.close()


def settle(win: MainWindow, tab: DocumentTab) -> None:
    """Leave any open sketch or panel without keeping it, close pop ups, wait."""
    mode = win.sketch_mode
    if mode is not None and mode.is_open:
        mode.cancel()
    if win.panel is not None and win.panel.is_editing:
        win.panel.reject()
    if mode is not None and mode.picker.active:
        mode.picker.cancel()
    close_popups(win)
    idle(tab)
    # The sweep never returns to the main event loop, which is where Qt deletes
    # widgets closed with deleteLater; do it here as the running app would (D599).
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def finish(win: MainWindow, accept: bool) -> None:
    """Press OK or Cancel on whatever the last step opened."""
    if win.editing == "feature" and win.panel is not None:
        win.panel.accept() if accept else win.panel.reject()
    elif win.editing == "sketch" and win.sketch_mode is not None:
        win.sketch_mode.accept() if accept else win.sketch_mode.cancel()


def shapes_of(tab: DocumentTab) -> dict[str, Any]:
    """One face, edge, vertex and solid of the part, by selection kind."""
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SOLID, TopAbs_VERTEX
    from OCP.TopExp import TopExp_Explorer

    report = tab.session.report
    if report is None or report.body is None:
        return {}
    out: dict[str, Any] = {}
    kinds = (
        ("face", TopAbs_FACE),
        ("edge", TopAbs_EDGE),
        ("vertex", TopAbs_VERTEX),
        ("body", TopAbs_SOLID),
    )
    for name, kind in kinds:
        explorer = TopExp_Explorer(report.body.shape, kind)
        if explorer.More():
            out[name] = explorer.Current()
    return out


def select(win: MainWindow, tab: DocumentTab, kind: str, shapes: dict[str, Any]) -> bool:
    """Select one item of ``kind``. False when the part has none."""
    win._selection_changed(tab, [])
    if kind == "none":
        return True
    if kind == "sketch":
        sketches = [f.id for f in tab.session.document.features if f.type == "sketch"]
        if not sketches or win.tree is None:
            return False
        win.tree.select(sketches[-1])
        return True
    if kind not in shapes:
        return False
    win._selection_changed(tab, [shapes[kind]])
    return True


@dataclass
class Sweep:
    """Runs steps on one part and collects every failure with a short repro."""

    win: MainWindow
    tab: DocumentTab
    dialogs: Dialogs
    failures: list[str] = field(default_factory=list)
    steps: int = 0

    def step(self, label: str, action: Callable[[], object], accept: bool) -> None:
        """Run ``action``, press OK or Cancel, then check undo and redo give back the
        same file text."""
        win, tab = self.win, self.tab
        self.dialogs.accept = accept
        self.steps += 1
        try:
            before = text_of(tab)
            index = tab.session.undo.index()
            start = time.monotonic()
            action()
            pump(5)
            if not idle(tab):
                self.failures.append(f"{label}: still rebuilding after {STEP_LIMIT} s")
            finish(win, accept)
            pump(5)
            if not idle(tab):
                self.failures.append(f"{label}: still rebuilding after OK or Cancel")
            settle(win, tab)
            took = time.monotonic() - start
            if took > STEP_LIMIT:
                self.failures.append(f"{label}: took {took:.1f} s")
            after = text_of(tab)
            done = tab.session.undo.index()
            if done == index and after != before:
                self.failures.append(
                    f"{label}: the part changed with no undo step\n{_diff(before, after)}"
                )
            if done > index:
                self._undo_redo(label, index, done, before, after)
        except Exception as exc:
            tail = "".join(traceback.format_exception(exc)[-3:])
            self.failures.append(f"{label}: {type(exc).__name__}: {exc}\n{tail}")
            settle(win, tab)

    def _undo_redo(self, label: str, index: int, done: int, before: str, after: str) -> None:
        undo, tab = self.tab.session.undo, self.tab
        while undo.index() > index:
            undo.undo()
        idle(tab)
        if text_of(tab) != before:
            self.failures.append(
                f"{label}: Undo does not give back the part\n{_diff(before, text_of(tab))}"
            )
        while undo.index() < done:
            undo.redo()
        idle(tab)
        if text_of(tab) != after:
            self.failures.append(
                f"{label}: Redo does not give back the change\n{_diff(after, text_of(tab))}"
            )
        while undo.index() > index:
            undo.undo()
        idle(tab)


def _diff(a: str, b: str) -> str:
    lines = difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm="", n=0)
    return "\n".join(list(lines)[2:14])


def run_commands(sweep: Sweep, kinds: tuple[str, ...], modes: tuple[bool, ...]) -> None:
    """Every command of the window, with each selection kind, then Cancel and OK."""
    win, tab = sweep.win, sweep.tab
    shapes = shapes_of(tab)
    name = tab.session.title.rstrip("*")
    for cid in sorted(win.commands.actions):
        if cid in SKIP:
            continue
        for kind in kinds:
            for accept in modes:
                settle(win, tab)
                if not select(win, tab, kind, shapes):
                    continue
                label = f"{name}: {cid} with {kind} selected, {'OK' if accept else 'Cancel'}"
                sweep.step(label, lambda c=cid: win.commands.trigger(c), accept)


def menu_items(menu: QMenu, prefix: str = "") -> Iterator[tuple[str, Any]]:
    """Every enabled item of a menu and its submenus, as (path, action)."""
    for action in menu.actions():
        if action.isSeparator():
            continue
        sub = action.menu()
        if isinstance(sub, QMenu):
            yield from menu_items(sub, f"{prefix}{sub.title()}/")
        elif action.isEnabled():
            yield f"{prefix}{action.text()}", action
