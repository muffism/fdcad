"""Windows contrast themes (TR378, D768)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from fdcad.ui.preferences.settings import Theme
from fdcad.ui.themes import system_contrast as sc
from fdcad.ui.themes import theme
from fdcad.ui.themes.contrast import failures

SAMPLES = sc.SAMPLES


@pytest.mark.parametrize("name", list(SAMPLES))
def test_every_pair_is_readable_in_each_contrast_set(name: str) -> None:
    palette, chrome, dark = sc.scheme(SAMPLES[name])
    assert failures(palette, chrome, dark) == []


def test_colours_come_from_the_system() -> None:
    s = SAMPLES["white_on_black"]
    palette, chrome, dark = sc.scheme(s)
    assert dark and chrome.window == s.window and chrome.text == s.text
    assert palette.viewport_top == palette.viewport_bottom == s.window
    assert chrome.accent == s.highlight


def test_reading_gives_none_off_windows_or_when_off() -> None:
    import sys

    if sys.platform != "win32":
        assert sc.read() is None
    else:
        result = sc.read()  # off on a normal test machine
        assert result is None or isinstance(result, sc.SystemColors)


def test_apply_theme_follows_the_system_contrast(qapp: QApplication) -> None:
    s = SAMPLES["yellow_on_dark"]
    try:
        theme.set_system_contrast(s)
        theme.apply_theme(qapp, Theme.LIGHT)
        assert theme.current() is Theme.CONTRAST
        assert theme.chrome().text == s.text and theme.is_dark()
        theme.set_system_contrast(None)
        theme.apply_theme(qapp, Theme.LIGHT)
        assert theme.current() is Theme.LIGHT
    finally:
        theme.set_system_contrast(None)
        theme.apply_theme(qapp, Theme.LIGHT)


def test_contrast_is_not_a_choice_in_preferences() -> None:
    from fdcad.ui import strings

    assert "contrast" not in {value for _label, value in strings.THEME_CHOICES}


def test_icons_take_the_contrast_colours(qapp: QApplication) -> None:
    """The screenshot tool found icons looking the theme up in the table of chosen
    themes, which has no contrast entry: the app would not start under one."""
    from fdcad.ui import icons

    s = SAMPLES["white_on_black"]
    try:
        theme.set_system_contrast(s)
        theme.apply_theme(qapp, Theme.LIGHT)
        assert icons.colours()["currentColor"] == s.text
        assert not icons.icon("corner.ok").isNull()
    finally:
        theme.set_system_contrast(None)
        theme.apply_theme(qapp, Theme.LIGHT)
