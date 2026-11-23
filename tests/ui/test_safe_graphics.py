"""Safe start without graphics hardware (TR219, D2016)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fdcad.ui import safe_graphics


def test_reasons_in_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(safe_graphics.ENV, raising=False)
    assert safe_graphics.wanted(["fdcad"], tmp_path, False) == (False, "")
    assert safe_graphics.wanted(["fdcad", "--safe-graphics"], tmp_path, False) == (True, "flag")
    assert safe_graphics.wanted(["fdcad"], tmp_path, True) == (True, "setting")
    monkeypatch.setenv(safe_graphics.ENV, "1")
    assert safe_graphics.wanted(["fdcad"], tmp_path, False) == (True, "env")


def test_a_start_that_did_not_finish_makes_the_next_one_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(safe_graphics.ENV, raising=False)
    safe_graphics.mark_start(tmp_path)
    assert safe_graphics.wanted(["fdcad"], tmp_path, False) == (True, "crash")
    safe_graphics.clear_start(tmp_path)
    assert safe_graphics.wanted(["fdcad"], tmp_path, False) == (False, "")


def test_preference_is_kept(tmp_path: Path) -> None:
    from PySide6.QtCore import QSettings

    from fdcad.ui.preferences.settings import Settings

    settings = Settings(QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    assert settings.safe_graphics is False
    settings.safe_graphics = True
    assert settings.safe_graphics is True


def test_error_message_says_how(qtbot: object) -> None:
    from fdcad.ui import strings_feedback

    assert "--safe-graphics" in strings_feedback.UNEXPECTED
