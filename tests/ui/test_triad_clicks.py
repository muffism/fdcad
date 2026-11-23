"""Corner triad clicks and the orientation popup (TR210, D1600, D1601)."""

from __future__ import annotations

import math
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from pytestqt.qtbot import QtBot

from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window import orientation_popup
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.viewport.triad import CENTRE_PX, LENGTH_PX, axis_at, triad_view

FRONT = ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0))
ISO = ((1.0, 1.0, 1.0), (0.0, 1.0, 0.0))


def _close(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    return all(math.isclose(x, y, abs_tol=1e-6) for x, y in zip(a, b, strict=True))


def test_front_view_arrows_are_picked_along_their_length() -> None:
    h = 400.0
    cx, cy = CENTRE_PX[0], h - CENTRE_PX[1]
    assert axis_at(cx + LENGTH_PX * 0.8, cy, h, *FRONT) == "x"
    assert axis_at(cx, cy - LENGTH_PX * 0.8, h, *FRONT) == "y"
    assert axis_at(cx + 1, cy + 1, h, *FRONT) == "z"  # Z points at the screen
    assert axis_at(cx + 200, cy, h, *FRONT) is None
    assert axis_at(cx + 20, cy - 20, h, *FRONT) is None  # between the arrows


def test_iso_view_x_goes_right_and_down_z_left_and_down() -> None:
    h = 300.0
    cx, cy = CENTRE_PX[0], h - CENTRE_PX[1]
    assert axis_at(cx + 15, cy + 8.5, h, *ISO) == "x"
    assert axis_at(cx - 15, cy + 8.5, h, *ISO) == "z"
    assert axis_at(cx, cy - 18, h, *ISO) == "y"


def test_click_looks_along_then_from_the_other_side() -> None:
    eye, up = triad_view("x", *ISO)
    assert _close(eye, (1.0, 0.0, 0.0)) and _close(up, (0.0, 1.0, 0.0))
    eye2, _ = triad_view("x", eye, up)
    assert _close(eye2, (-1.0, 0.0, 0.0))


def test_shift_click_turns_a_quarter_about_the_axis() -> None:
    eye, up = triad_view("y", *FRONT, quarter=True)
    assert _close(eye, (1.0, 0.0, 0.0)) and _close(up, (0.0, 1.0, 0.0))
    eye, up = triad_view("z", *FRONT, quarter=True)
    assert _close(eye, (0.0, 0.0, 1.0)) and _close(up, (-1.0, 0.0, 0.0))


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
        tab = win.tabs.widget(0)
        assert isinstance(tab, DocumentTab)
        tab.session.cancel_rebuild()
        tab.session.wait()
        tab.autosaver.discard()
        win.tabs.removeTab(0)
    win.close()
    win.deleteLater()


def test_orientation_popup_lists_views_layouts_and_new_view(window: MainWindow) -> None:
    assert BY_ID["view.orientation"].keys == ()  # the owner chooses the key
    assert "view.orientation" in window.commands.actions
    calls: list[str] = []
    window.set_view = calls.append  # type: ignore[method-assign]
    menu = orientation_popup.build(window)
    data = [a.data() for a in menu.actions() if not a.isSeparator()]
    assert data[:3] == ["view.front", "view.back", "view.left"]
    assert "view.split_four" in data and data[-1] == "view.save_view"
    next(a for a in menu.actions() if a.data() == "view.top").trigger()
    assert calls == ["top"]
