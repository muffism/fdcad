"""Reduce Motion follows the system until it is set (TR294 item 1, D975)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from fdcad.ui.preferences.settings import Settings
from fdcad.ui.themes import motion
from fdcad.ui.themes.motion import system_reduce_motion as read_system


def test_default_follows_the_system(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(QSettings(str(tmp_path / "p.ini"), QSettings.Format.IniFormat))
    monkeypatch.setattr(motion, "system_reduce_motion", lambda platform=None: True)
    assert settings.reduce_motion
    monkeypatch.setattr(motion, "system_reduce_motion", lambda platform=None: False)
    assert not settings.reduce_motion
    settings.reduce_motion = True  # a choice in Preferences wins from then on
    monkeypatch.setattr(motion, "system_reduce_motion", lambda platform=None: False)
    assert settings.reduce_motion


def test_reading_the_system_never_fails() -> None:
    assert read_system("plan9") is False  # the real reader, not the test stand in
    import sys

    assert isinstance(read_system(sys.platform), bool)
