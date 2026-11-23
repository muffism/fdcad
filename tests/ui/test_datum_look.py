"""The Datum look (D1034): the cut colour, the icon tints, the brand tile and a
Preferences window that fits the screen."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QScrollArea
from pytestqt.qtbot import QtBot

from fdcad.ui import icons
from fdcad.ui.preferences.settings import Theme
from fdcad.ui.themes import contrast, theme

ROOT = Path(__file__).resolve().parents[2]


def _tool(name: str) -> object:
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("choice", list(theme.SCHEMES))
def test_cut_colour_reads_on_every_panel_and_is_not_the_accent(choice: Theme) -> None:
    _palette, chrome, _dark = theme.SCHEMES[choice]
    for name in ("window", "surface", "raised", "hover", "selected"):
        assert contrast.ratio(chrome.cut, getattr(chrome, name)) >= contrast.MARK, name
    assert contrast.hue_gap(chrome.cut, chrome.accent) > 90
    assert icons.colours(choice)["#CUT"] == chrome.cut


def test_tools_that_remove_material_use_the_cut_colour() -> None:
    cut = icons.icon_path("feature.extruded_cut").read_text(encoding="utf-8")
    add = icons.icon_path("feature.extrude").read_text(encoding="utf-8")
    assert "#CUT" in cut and "#ACCENT" not in cut
    assert "#ACCENT" in add and "#CUT" not in add
    themed = icons.themed_text("feature.extruded_cut", Theme.LIGHT)
    assert themed is not None and theme.LIGHT_CHROME.cut in themed and "#CUT" not in themed


def test_icon_restyle_is_stable_and_tints_closed_outlines_only() -> None:
    tool = _tool("icon_duotone")
    plain = (
        '<svg><g fill="none" stroke="currentColor">\n'
        '<rect x="3" y="3" width="18" height="18"/>\n'
        '<path d="M3 3 L21 21"/>\n'
        '<circle cx="12" cy="12" r="5" stroke-dasharray="1.5 3"/>\n'
        "</g></svg>"
    )
    once = tool.restyle("feature.extrude", plain)  # type: ignore[attr-defined]
    assert 'height="18" fill="currentColor" fill-opacity="0.12"/>' in once
    assert '<path d="M3 3 L21 21"/>' in once  # an open line stays a line
    assert 'stroke-dasharray="1.5 3"/>' in once  # hidden lines stay empty
    assert tool.restyle("feature.extrude", once) == once  # type: ignore[attr-defined]
    for path in sorted(icons.ICON_DIR.glob("*.svg")):
        text = path.read_text(encoding="utf-8")
        assert tool.restyle(path.stem, text) == text, path.name  # type: ignore[attr-defined]


def test_brand_colours_and_mark_files() -> None:
    for name in ("tile_top", "tile_bottom", "on_tile", "on_tile_soft"):
        assert theme.BRAND[name].startswith("#")
    assert contrast.ratio(theme.BRAND["on_tile"], theme.BRAND["tile_top"]) >= contrast.BODY
    assert contrast.ratio(theme.BRAND["on_tile_soft"], theme.BRAND["tile_top"]) >= contrast.TEXT
    tool = _tool("make_brand")
    made = tool.full_icon()  # type: ignore[attr-defined]
    saved = (ROOT / "src" / "fdcad" / "ui" / "app_icon.svg").read_text(encoding="utf-8")
    assert made == saved  # the committed drawing is the one the tool draws
    small = (ROOT / "src" / "fdcad" / "ui" / "app_icon_small.svg").read_text(encoding="utf-8")
    assert tool.small_icon() == small  # type: ignore[attr-defined]
    assert theme.BRAND["tile_top"] in saved and theme.BRAND["tile_bottom"] in saved
    # D1039: the front faces are an off white that still reads as white on the tile.
    for colour in (tool.FRONT_TOP, tool.FRONT_BOTTOM):  # type: ignore[attr-defined]
        assert colour in saved and colour in small
        assert contrast.ratio(colour, theme.BRAND["tile_top"]) >= contrast.BODY


def test_mark_is_an_f_at_the_corner_and_a_d_against_it() -> None:
    """D1036, D1037: two solid letters; the F is its face and the corner, the D the next face."""
    import math

    tool = _tool("make_brand")
    for drawing in (tool.full_icon(), tool.small_icon()):  # type: ignore[attr-defined]
        assert drawing.count('fill="url(#front)"') == 2  # two white front faces
        # The D is drawn first: the F stands in front of the D's left wall.
        assert drawing.index('fill-rule="evenodd"') < drawing.rindex('fill="url(#front)"')
    depth, unit = 3.0, 10.0
    step = depth * math.cos(math.radians(30)) * unit  # one depth along a face, on screen

    def solid(letter: object, right: bool, gap: float, deep: float) -> tuple[list[str], list]:
        return tool.solid(letter, right, gap, deep, unit)  # type: ignore[attr-defined,no-any-return]

    letter_f = tool.letter_f(1.9, 1.7)  # type: ignore[attr-defined]
    letter_d = tool.letter_d(1.9, 1.7)  # type: ignore[attr-defined]
    f_paths, f_points = solid(letter_f, False, 0.0, depth)
    d_paths, d_points = solid(letter_d, True, depth, depth)
    _paths, f_front = solid(letter_f, False, 0.0, 0.0)
    _paths, d_front = solid(letter_d, True, depth, 0.0)
    # The F's face ends on the corner line and its end reaches one depth past it,
    # which is where the D's face starts. The D's back stops on the corner line.
    assert max(x for x, _y in f_front) == pytest.approx(0.0, abs=1e-9)
    assert max(x for x, _y in f_points) == pytest.approx(step)
    assert min(x for x, _y in d_front) == pytest.approx(step)
    assert min(x for x, _y in d_points) == pytest.approx(0.0, abs=1e-9)
    # The F: two walls that face up (the top and the top of the middle arm), four
    # that face right (the ends of both arms and the stem between and below them)
    # and the front. All are straight and use the F's two gradients, as when it
    # stood alone. The D has curved walls too, and its side walls are darker.
    assert len(f_paths) == 7
    assert all("url(#" in path for path in f_paths)
    assert not any("url(#deep)" in path for path in f_paths)
    # The end of the F's top arm is the corner: it has a colour of its own, brighter
    # at its foot than the top of the D's side wall below it (D1038).
    assert sum("url(#corner)" in path for path in f_paths) == 1
    assert not any("url(#corner)" in path for path in d_paths)
    assert contrast.ratio(tool.CORNER_BOTTOM, tool.DEEP_TOP) >= 1.5  # type: ignore[attr-defined]
    _paths, apart = solid(letter_f, False, 1.0, depth)  # an F away from the corner has none
    assert not any("url(#corner)" in path for path in apart)
    assert any('fill="#' in path for path in d_paths)
    assert any("url(#deep)" in path for path in d_paths)
    assert not any("url(#shade)" in path for path in d_paths)
    assert 'fill-rule="evenodd"' in d_paths[-1]  # the D's opening is open


def test_preferences_fits_a_small_screen(qtbot: QtBot, tmp_path: Path) -> None:
    from PySide6.QtCore import QSettings

    from fdcad.ui.preferences.dialog import PreferencesDialog
    from fdcad.ui.preferences.settings import Settings

    store = QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat)
    dialog = PreferencesDialog(Settings(store))
    qtbot.addWidget(dialog)
    assert isinstance(dialog.tabs.widget(0), QScrollArea)
    assert dialog.minimumSizeHint().height() <= 600
    dialog.resize(720, 560)
    dialog.show()
    qtbot.waitExposed(dialog)
    assert dialog.height() <= 600
    assert dialog.buttons.geometry().bottom() <= dialog.height()
    assert isinstance(QApplication.instance(), QApplication)


def test_start_page_placeholder_is_a_theme_tile(qtbot: QtBot) -> None:
    from PySide6.QtGui import QColor

    from fdcad.ui.main_window.start_page import PICTURE, placeholder

    picture = placeholder(PICTURE, 2.0)
    assert picture.width() == PICTURE * 2
    image = picture.toImage()
    assert image.pixelColor(0, 0).alpha() == 0  # rounded tile, clear corners
    inside = image.pixelColor(PICTURE // 2, PICTURE // 2)  # left of the icon, on the tile
    assert inside == QColor(theme.chrome().surface)


def test_property_panel_header_has_two_rows_and_fits_a_narrow_panel(qtbot: QtBot) -> None:
    from fdcad.ui.property_panel.panel import PropertyPanel

    panel = PropertyPanel()
    qtbot.addWidget(panel)
    panel.resize(260, 600)
    panel.show()
    qtbot.waitExposed(panel)
    ok, cancel, pin = panel.ok_button, panel.cancel_button, panel.pin_button
    assert ok.geometry().top() >= pin.geometry().bottom()  # OK and Cancel sit under the name
    assert ok.geometry().right() < cancel.geometry().left()  # and never over each other
    assert cancel.geometry().right() <= panel.width()
    assert panel.minimumSizeHint().width() <= 260


def test_node_view_fits_when_it_is_first_shown(qtbot: QtBot) -> None:
    from fdcad.ui.node_editor.scene import NodeScene
    from fdcad.ui.node_editor.view import NodeView

    scene = NodeScene()
    scene.addRect(0, 0, 2000, 300)
    view = NodeView(scene)
    qtbot.addWidget(view)
    view.fit()  # asked for while hidden: the size is not known yet
    assert view._fit_when_shown
    view.resize(900, 500)
    view.show()
    qtbot.waitExposed(view)
    qtbot.wait(50)
    assert not view._fit_when_shown
    shown = view.mapToScene(view.viewport().rect()).boundingRect()
    assert shown.left() <= 0 and shown.right() >= 2000  # the whole graph is in view
    assert view.zoom > 0.3  # and it fills the width, not a speck in the middle
