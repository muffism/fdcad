"""Icon audit and theme colours (UI_POLISH_SPEC U5, D670 to D672)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QIcon, QImage

from fdcad.ui import icons
from fdcad.ui.icons import audit
from fdcad.ui.preferences.settings import Theme
from fdcad.ui.themes.theme import SCHEMES

ROOT = Path(__file__).resolve().parents[2]
GOOD = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">\n'
    '<g fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"'
    ' stroke-linejoin="round">\n'
    "{body}\n</g>\n</svg>"
)


def svg(body: str) -> str:
    return GOOD.format(body=body)


def test_every_icon_passes_the_audit() -> None:
    assert audit.audit_all() == {}


def _listed() -> set[str]:
    """The icon names in NAMES.md, the list every new icon is added to."""
    import re

    text = (audit.ICON_DIR / "NAMES.md").read_text(encoding="utf-8")
    return set(re.findall(r"^- ([a-z0-9_.]+)\s*$", text, re.MULTILINE))


def test_every_icon_is_listed_in_names() -> None:
    """Was a fixed count (292), which every new icon had to change; NAMES.md is the list."""
    assert set(audit.names()) == _listed()


def test_a_good_icon_passes() -> None:
    body = '<path d="M3.75 3.75 H20.25 V20.25 H3.75 Z"/>\n<path d="M12 6 V18" stroke="#ACCENT"/>'
    assert audit.audit_text(svg(body)) == []


@pytest.mark.parametrize(
    ("body", "rule"),
    [
        ('<path d="M3.75 3.75 H20.25" stroke-width="1"/>', "stroke"),
        ('<path d="M3.75 3.75 H20.25" stroke-width="2.2"/>', "stroke"),
        ('<path d="M3.75 3.75 H20.25" stroke-linecap="butt"/>', "stroke"),
        ('<path d="M1 3.75 H20.25"/>', "bounds"),
        ('<circle cx="12" cy="12" r="10.5"/>', "bounds"),
        ('<path d="M4 4 H20"/>', "grid"),
        ('<rect x="4" y="3.75" width="12" height="12"/>', "grid"),
        ('<path d="M3.75 3.75 H20.25" stroke="#FF0000"/>', "colour"),
        ('<rect x="3.75" y="3.75" width="12" height="12" fill="currentColor"/>', "fill"),
        ('<path d="M3.75 3.75 H20.25" stroke-dasharray="2 2"/>', "dash"),
        ('<path d="M3.75 3.75 H20.25" stroke-opacity="0.3"/>', "hairline"),
        (
            '<path d="M3.75 3.75 H20.25" stroke="#ACCENT"/>\n'
            '<path d="M3.75 6.75 H20.25" stroke="#ACCENT"/>',
            "accent",
        ),
    ],
)
def test_the_audit_finds_each_broken_rule(body: str, rule: str) -> None:
    problems = audit.audit_text(svg(body))
    assert any(p.startswith(rule) for p in problems), problems


def test_a_wrong_frame_is_found() -> None:
    text = svg('<path d="M3.75 3.75 H20.25"/>').replace(
        'viewBox="0 0 24 24"', 'viewBox="0 0 32 32"'
    )
    assert any(p.startswith("frame") for p in audit.audit_text(text))


def test_small_dots_may_be_solid() -> None:
    assert (
        audit.audit_text(svg('<circle cx="12" cy="12" r="2" fill="#ACCENT" stroke="none"/>')) == []
    )


def test_grid_positions() -> None:
    """Lines sit on 0.75 + 1.5 k: a pixel centre at 16 px, an edge at 16, 32 and 48 px."""
    for value in (0.75, 2.25, 3.75, 12.75, 21.75, 12.0):
        assert audit.on_grid(value)
    for value in (2.0, 4.0, 12.5, 20.0):
        assert not audit.on_grid(value)
    for value in (2.25, 3.75, 20.25):
        assert (value * 16 / 24) % 1 == pytest.approx(0.5)  # 1 px line on a pixel centre


def test_arcs_count_towards_the_bounds() -> None:
    bulge = '<path d="M4.5 12 A8 8 0 0 1 19.5 12"/>'  # tops out near 6.8, inside
    assert audit.audit_text(svg(bulge)) == []
    too_far = '<path d="M6 12 A8 8 0 1 1 18 12"/>'  # the large arc rises to y -1.3
    assert any(p.startswith("bounds") for p in audit.audit_text(svg(too_far)))


@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.BEIGE, Theme.DARK, Theme.STEALTH])
def test_icons_take_each_themes_tokens(theme: Theme, qapp: object) -> None:
    scheme, chrome, _dark = SCHEMES[theme]
    text = icons.themed_text("feature.extrude", theme)
    assert text is not None
    assert chrome.text in text and chrome.accent in text
    warning = icons.themed_text("tree.warning_mark", theme)
    assert warning is not None and scheme.state_warning in warning
    for placeholder in ("currentColor", "#ACCENT", "#DANGER", "#WARNING"):
        assert placeholder not in text and placeholder not in warning


@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
def test_disabled_icons_use_the_disabled_colour(theme: Theme, qapp: object) -> None:
    """Disabled icons are the theme's disabled colour, not a faded accent (U5.4)."""
    icons.clear_cache()
    icon = icons._icon("feature.extrude", theme)
    image = icon.pixmap(QSize(48, 48), QIcon.Mode.Disabled).toImage()
    image = image.convertToFormat(QImage.Format.Format_ARGB32)
    data = np.frombuffer(image.constBits(), np.uint8).reshape(48, 48, 4)
    solid = data[data[:, :, 3] == 255]
    assert len(solid) > 20
    want = QColor(icons.disabled_colour(theme))
    blue, green, red = solid[:, 0], solid[:, 1], solid[:, 2]
    assert np.all(np.abs(red.astype(int) - want.red()) <= 2)
    assert np.all(np.abs(green.astype(int) - want.green()) <= 2)
    assert np.all(np.abs(blue.astype(int) - want.blue()) <= 2)
    normal = icon.pixmap(QSize(48, 48)).toImage()
    assert normal != icon.pixmap(QSize(48, 48), QIcon.Mode.Disabled).toImage()


def test_lines_are_sharp_at_16_px(qapp: object) -> None:
    """A grid line fills one whole pixel column at 16 px instead of two half ones."""
    icons.clear_cache()
    image = icons._icon("view.front", Theme.LIGHT).pixmap(QSize(16, 16)).toImage()
    image = image.convertToFormat(QImage.Format.Format_ARGB32)
    alpha = np.frombuffer(image.constBits(), np.uint8).reshape(16, 16, 4)[:, :, 3]
    # The front square's left edge is at x 3.75 of 24: pixel column 2 at 16 px.
    column = alpha[8:12, 2]
    assert np.all(column > 230)
    assert np.all(alpha[8:12, 1] < 40) and np.all(alpha[8:12, 3] < 120)


def test_app_icon_has_a_bold_small_drawing(qapp: object) -> None:
    from fdcad.ui.help.paths import app_icon, app_icon_small_path

    assert app_icon_small_path().is_file()
    from fdcad.ui.help.paths import app_icon_path

    icon = app_icon()
    assert {16, 24, 32, 48, 256} <= {s.width() for s in icon.availableSizes()}
    small = icon.pixmap(QSize(16, 16)).toImage()
    full = QIcon(str(app_icon_path())).pixmap(QSize(16, 16)).toImage()
    assert not small.isNull() and small != full
    spec = (ROOT / "packaging" / "fdcad.spec").read_text(encoding="utf-8")
    assert "fdcad/ui/app_icon_small.svg" in spec


def test_installer_icons_are_up_to_date(tmp_path: Path) -> None:
    """The committed .ico, .icns and PNGs match what tools/make_app_icon.py draws now."""
    import tools.make_app_icon as maker

    out = tmp_path / "icons"
    old = maker.OUT
    maker.OUT = out
    try:
        assert maker.main() == 0
    finally:
        maker.OUT = old
    committed = ROOT / "packaging" / "icons"
    # The drawing is compared as pixels, a few levels apart at most: Qt on Apple Silicon
    # rounds a handful of edge pixels one or two levels differently from Qt on x64 (D2709).
    pngs: dict[int, bytes] = {}
    for size in maker.SIZES:
        name = f"png/fdcad_{size}.png"
        pngs[size] = (committed / name).read_bytes()
        assert _pixel_gap(out / name, committed / name) <= ICON_LEVELS, name
    # The .ico and .icns hold the committed PNGs byte for byte.
    assert maker.ico(pngs) == (committed / "fdcad.ico").read_bytes()
    assert maker.icns(pngs) == (committed / "fdcad.icns").read_bytes()


#: Two drawings of one icon on different processors differ by at most this many levels of 255.
ICON_LEVELS = 4


def _pixel_gap(a: Path, b: Path) -> int:
    """The largest difference in any channel of any pixel; 255 when the sizes differ."""
    first, second = (
        QImage(str(path)).convertToFormat(QImage.Format.Format_RGBA8888) for path in (a, b)
    )
    if first.isNull() or second.isNull() or first.size() != second.size():
        return 255
    width = first.width() * 4
    rows = [
        np.frombuffer(image.constBits(), np.uint8)
        .reshape(image.height(), image.bytesPerLine())[:, :width]
        .astype(np.int16)
        for image in (first, second)
    ]
    return int(np.abs(rows[0] - rows[1]).max())


def test_the_icon_check_sees_a_changed_drawing(tmp_path: Path) -> None:
    """A small rounding difference passes; a real change to the drawing does not."""
    committed = ROOT / "packaging" / "icons" / "png" / "fdcad_64.png"
    image = QImage(str(committed)).convertToFormat(QImage.Format.Format_RGBA8888)
    assert _pixel_gap(committed, committed) == 0
    image.setPixelColor(32, 32, QColor(255, 0, 255))
    changed = tmp_path / "changed.png"
    assert image.save(str(changed), "PNG")
    assert _pixel_gap(changed, committed) > ICON_LEVELS
    assert _pixel_gap(ROOT / "packaging" / "icons" / "png" / "fdcad_16.png", committed) == 255


def test_icon_sheet_tool_writes_both_sheets_and_audits(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "icon_sheet.py"), "--audit", "--out", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=300,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    count = len(_listed())
    assert f"{count} of {count} icons pass" in result.stdout
    assert (tmp_path / "icons_light.png").is_file() and (tmp_path / "icons_dark.png").is_file()


def test_plain_icons_use_only_the_text_colour(qapp: object) -> None:
    text = icons.themed_text("tree.warning_mark", Theme.LIGHT, plain=True)
    assert text is not None
    chrome = SCHEMES[Theme.LIGHT][1]
    assert SCHEMES[Theme.LIGHT][0].state_warning not in text and chrome.text in text


def test_errors_tab_turns_to_the_warning_colour_only_with_problems(qapp: object) -> None:
    from PySide6.QtWidgets import QWidget

    from fdcad.ui import strings
    from fdcad.ui.main_window.left_tabs import LeftTabs

    tabs = LeftTabs()
    page = QWidget()
    tabs.addTab(page, strings.TAB_ERRORS)
    quiet = tabs.tabIcon(0).pixmap(QSize(24, 24)).toImage()
    tabs.set_count(page, strings.TAB_ERRORS, 2)
    loud = tabs.tabIcon(0).pixmap(QSize(24, 24)).toImage()
    assert quiet != loud
    tabs.set_count(page, strings.TAB_ERRORS, 0)
    assert tabs.tabIcon(0).pixmap(QSize(24, 24)).toImage() == quiet


def test_a_missing_icon_is_logged(qapp: object, caplog: pytest.LogCaptureFixture) -> None:
    import logging

    icons.clear_cache()
    with caplog.at_level(logging.INFO, logger="fdcad"):
        assert icons.icon("no.such.icon.at.all").isNull()
    assert "Missing icon no.such.icon.at.all" in caplog.text
