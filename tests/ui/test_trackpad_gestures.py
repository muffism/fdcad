"""Trackpad rotate, smart zoom and swipe (TR380 item 1, D1612)."""

from __future__ import annotations

import sys

import pytest
from PySide6.QtWidgets import QApplication

from fdcad.ui.viewport.keynav import swipe_back


def test_swipe_directions() -> None:
    assert swipe_back(180.0) and swipe_back(135.0) and swipe_back(-180.0)
    assert not swipe_back(0.0) and not swipe_back(45.0) and not swipe_back(300.0)


def test_next_view_without_a_view(qapp: QApplication) -> None:
    if sys.platform.startswith("linux"):
        pytest.skip("the 3D viewer needs a display on Linux")
    from fdcad.ui.viewport.widget import ViewportWidget

    view = ViewportWidget()
    assert view.next_view() is False
    assert view._future == []
    view._remember()
    assert view._future == []
    view.deleteLater()
