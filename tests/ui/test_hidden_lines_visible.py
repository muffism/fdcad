"""Hidden Lines Visible display style (TR13, D686)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.input.commands import BY_ID, ShortcutMap
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.viewport.look import hidden_line_colour
from tests.ui.test_main_window import _folders, _open_plate, window

__all__ = ["_folders", "window"]


def test_command_key_icon_and_menu_name() -> None:
    from fdcad.ui.icons.audit import audit
    from fdcad.ui.strings import TOOLTIP_TEXT
    from fdcad.ui.strings_extra import STYLE_NAMES

    assert BY_ID["view.hidden_lines_visible"].label == "Hidden Lines Visible"
    assert ShortcutMap().keys("view.hidden_lines_visible") == ["Shift+H"]
    assert audit("view.hidden_lines_visible") == []
    assert TOOLTIP_TEXT["view.hidden_lines_visible"]
    assert list(STYLE_NAMES).index("hidden_lines_visible") == 3


def test_hidden_lines_are_lighter_than_edges() -> None:
    from fdcad.ui.themes.theme import palette

    pal = palette()
    faded = hidden_line_colour(pal)

    def lum(c: str) -> float:
        c = c.lstrip("#")[-6:]
        return sum(int(c[i : i + 2], 16) for i in (0, 2, 4))

    # The seen lines of the hidden line styles have the outline colour (D2761), so the
    # hidden ones fade from it.
    seen, back = lum(pal.silhouette), lum(pal.viewport_top)
    assert min(seen, back) <= lum(faded) <= max(seen, back)
    assert faded.lower() != pal.silhouette.lower()[-7:]


def test_drawer_gets_thin_dashed_hidden_lines() -> None:
    from OCP.Aspect import Aspect_TOL_DASH
    from OCP.Prs3d import Prs3d_Drawer

    from fdcad.ui.themes.theme import palette
    from fdcad.ui.viewport.look import HIDDEN_WIDTH, style_hidden_lines

    drawer = Prs3d_Drawer()
    style_hidden_lines(drawer, palette())
    aspect = drawer.HiddenLineAspect().Aspect()
    assert aspect.Type() == Aspect_TOL_DASH
    assert aspect.Width() == HIDDEN_WIDTH


def test_command_sets_the_style(qtbot: QtBot, window: MainWindow) -> None:
    tab, _ext = _open_plate(qtbot, window)
    action = window.commands.actions["view.hidden_lines_visible"]
    assert not action.isChecked()
    assert window.commands.trigger("view.hidden_lines_visible")
    assert action.isChecked()
    viewport = tab.viewport
    if not hasattr(viewport, "display_style"):
        return  # no 3D view on the offscreen test platform
    assert viewport.display_style == "hidden_lines_visible"
    part = getattr(viewport, "_part", None)
    if part is not None:
        drawer = part.Attributes()
        assert drawer.DrawHiddenLine()
        assert window.commands.trigger("view.hidden_lines")
        assert not drawer.DrawHiddenLine()
