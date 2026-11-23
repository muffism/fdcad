"""The original icon set (PHASE1_CORRECTIONS C5): names, files and theme colours."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PySide6.QtCore import QByteArray
from PySide6.QtSvg import QSvgRenderer

from fdcad.ui import icons
from fdcad.ui.input.commands import COMMANDS

SRC = Path(icons.__file__).parents[2]
#: Commands that never show as a button, so they need no icon.
NO_ICON = {
    "tree.top",
    "tree.bottom",
    "ui.next_tab",
    "ui.previous_tab",
    "ui.next_part",
    "ui.previous_part",
    "ui.confirm_corner",
}


def test_names_are_unique_and_match_the_files() -> None:
    names = icons.listed_names()
    assert len(names) == len(set(names))
    files = {p.stem for p in icons.ICON_DIR.glob("*.svg")}
    assert set(names) == files


@pytest.mark.parametrize("name", icons.listed_names())
def test_every_listed_icon_parses(name: str, qapp: object) -> None:
    path = icons.icon_path(name)
    root = ET.parse(path).getroot()
    assert root.get("viewBox") == "0 0 24 24"
    for dark in (False, True):
        text = icons.svg_text(name, dark)
        assert text is not None
        assert "#ACCENT" not in text and "currentColor" not in text
        assert QSvgRenderer(QByteArray(text.encode("utf-8"))).isValid()


def test_icon_calls_in_src_use_listed_names() -> None:
    listed = set(icons.listed_names())
    pattern = re.compile(r"""\bicon\(\s*["']([^"']+)["']""")
    used: dict[str, str] = {}
    for path in SRC.rglob("*.py"):
        for name in pattern.findall(path.read_text(encoding="utf-8")):
            used[name] = str(path)
    assert used, "no icon() calls found"
    missing = {n: p for n, p in used.items() if n not in listed}
    assert not missing


def test_every_visible_command_has_an_icon() -> None:
    listed = set(icons.listed_names())
    missing = [c.id for c in COMMANDS if c.id not in listed and c.id not in NO_ICON]
    assert not missing


def test_every_relation_has_an_icon() -> None:
    from fdcad.ui import strings

    listed = set(icons.listed_names())
    assert {f"relation.{r}" for r in strings.RELATION_NAMES} <= listed


def test_icons_follow_the_theme(qapp: object) -> None:
    light = icons.svg_text("sketch.line", dark=False)
    dark = icons.svg_text("sketch.line", dark=True)
    assert light is not None and dark is not None
    assert icons.ACCENT[False] in light and icons.ACCENT[True] in dark
    icons.clear_cache()
    assert not icons.icon("sketch.line").isNull()
    assert icons.icon("no.such.icon").isNull()


def test_icons_render_only_the_sizes_asked_for(qapp: object) -> None:
    """Icons draw on demand (startup memory budget, PLAN 11), sharp at scale 2, dim when off."""
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QIcon

    text = icons.svg_text("sketch.line", dark=False)
    assert text is not None
    engine = icons.SvgIconEngine(QByteArray(text.encode("utf-8")))
    assert engine.pixmaps == {}
    normal = engine.scaledPixmap(QSize(24, 24), QIcon.Mode.Normal, QIcon.State.Off, 2.0)
    assert normal.size() == QSize(48, 48) and normal.devicePixelRatio() == 2.0
    assert len(engine.pixmaps) == 1
    engine.scaledPixmap(QSize(24, 24), QIcon.Mode.Normal, QIcon.State.Off, 2.0)
    assert len(engine.pixmaps) == 1  # kept, not drawn again
    off = engine.pixmap(QSize(24, 24), QIcon.Mode.Disabled, QIcon.State.Off)
    on = engine.pixmap(QSize(24, 24), QIcon.Mode.Normal, QIcon.State.Off)
    assert off.toImage() != on.toImage()
    assert not icons.icon("sketch.line").pixmap(16).isNull()
