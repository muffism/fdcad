"""A closed part's 3D view is freed at once, in a set order (IDEAS 83 F1, D2780).

Left to the garbage collector, the kernel freed a closed part's drawing context
after its window was gone, and a part still open could stop drawing
("wglMakeCurrent() has failed"). The first tests check the order on the offscreen
platform. The last one opens and closes parts on the real screen; it runs only
when asked, like the pixel test of the view polish.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.session import DocumentSession


@pytest.fixture
def viewport(qapp: QApplication) -> Iterator[object]:
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        pytest.skip("the 3D viewer needs a display on Linux")
    from fdcad.ui.viewport.widget import ViewportWidget

    view = ViewportWidget()
    yield view
    view.deleteLater()


def _with_kernel_view(view: object) -> object:
    """Give ``view`` a kernel view and a shown box, as a real screen would."""
    from OCP.AIS import AIS_Shape
    from OCP.Aspect import Aspect_NeutralWindow
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

    v: object = view
    v._view = v._viewer.CreateView()  # type: ignore[attr-defined]
    v._window = Aspect_NeutralWindow()  # type: ignore[attr-defined]
    part = AIS_Shape(BRepPrimAPI_MakeBox(1.0, 1.0, 1.0).Shape())
    v._context.Display(part, False)  # type: ignore[attr-defined]
    v._part = part  # type: ignore[attr-defined]
    return part


def test_release_frees_items_then_the_view_then_the_window(viewport: object) -> None:
    v: object = viewport
    part = _with_kernel_view(v)
    steps = v.release()  # type: ignore[attr-defined]
    assert steps == ["shown items", "kernel view", "window handle"]
    assert not v._context.IsDisplayed(part)  # type: ignore[attr-defined]
    assert v._viewer.DefinedViews().Size() == 0  # type: ignore[attr-defined]
    assert v._view is None and v._window is None  # type: ignore[attr-defined]
    assert v.released  # type: ignore[attr-defined]


def test_release_runs_once_and_the_view_never_starts_again(viewport: object) -> None:
    from PySide6.QtGui import QShowEvent

    v: object = viewport
    _with_kernel_view(v)
    v.release()  # type: ignore[attr-defined]
    assert v.release() == []  # type: ignore[attr-defined]
    v.showEvent(QShowEvent())  # type: ignore[attr-defined]
    assert v._view is None and v._window is None  # type: ignore[attr-defined]


def test_release_without_a_kernel_view_does_nothing(viewport: object) -> None:
    assert viewport.release() == []  # type: ignore[attr-defined]


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[MainWindow]:
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("FDCAD_DATA_DIR", str(tmp_path / "data"))
    settings = Settings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))
    win = MainWindow(settings)
    win.show()
    win.finish_setup()
    yield win
    while win.tabs.count():
        win.close_tab(0, ask=False)
    win.close()


def test_closing_a_tab_frees_its_views_before_the_tab_is_deleted(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    from shiboken6 import isValid

    seen: list[tuple[str, bool]] = []
    real = DocumentTab.release_views

    def release(tab: DocumentTab) -> None:
        seen.append(("release", isValid(tab) and window.tabs.indexOf(tab) == -1))
        real(tab)

    monkeypatch.setattr(DocumentTab, "release_views", release)
    tab = window.add_session(DocumentSession.new(window.settings.default_units, window))
    tab.destroyed.connect(lambda *_a: seen.append(("deleted", True)))
    assert window.close_tab(window.tabs.indexOf(tab), ask=False)
    QApplication.sendPostedEvents(None, 0)
    from PySide6.QtCore import QEvent

    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    # Freed once, out of the tab bar but still alive, and before the tab is deleted.
    assert seen[0] == ("release", True)
    assert ("deleted", True) in seen[1:]


def test_release_views_closes_the_panes_first(window: MainWindow) -> None:
    tab = window.add_session(DocumentSession.new(window.settings.default_units, window))
    order: list[str] = []

    class Pane:
        def close_view(self) -> None:
            order.append("pane")

    class View:
        def release(self) -> list[str]:
            order.append("main")
            return []

    real_panes, real_view = tab.panes, tab.viewport
    tab.panes, tab.viewport = [Pane(), Pane()], View()
    try:
        tab.release_views()
    finally:
        tab.panes, tab.viewport = real_panes, real_view
    assert order == ["pane", "pane", "main"]


# Opening and closing parts on a real screen -------------------------------------------


@pytest.mark.skipif(
    os.environ.get("FDCAD_VIEW_PIXELS") != "1" or sys.platform.startswith("linux"),
    reason="opens real 3D views: set FDCAD_VIEW_PIXELS=1 on a screen",
)
def test_views_keep_drawing_while_parts_open_and_close() -> None:
    """One part stays open while others open and close quickly: every view draws, and
    the kernel reports no drawing error, not even while the collector runs."""
    probe = Path(__file__).with_name("view_release_probe.py")
    env = {k: v for k, v in os.environ.items() if k != "QT_QPA_PLATFORM"}
    done = subprocess.run(
        [sys.executable, str(probe), "18"], capture_output=True, text=True, env=env, timeout=900
    )
    lines = [line for line in done.stdout.splitlines() if line.startswith("{")]
    assert lines, done.stdout[-4000:] + done.stderr[-4000:]
    seen = json.loads(lines[-1])
    assert seen["checks"] >= 36, seen
    assert seen["failed"] == [], seen
    assert seen["kernel_errors"] == 0, seen
