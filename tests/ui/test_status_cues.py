"""Status without colour alone (TR292, D769)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from fdcad.ui.preferences.settings import Theme
from fdcad.ui.sketch_tools.status_style import POINT_SHAPES, line_style
from fdcad.ui.themes import theme
from fdcad.ui.themes.contrast import MARK, failures, ratio

FOUR = [Theme.BEIGE, Theme.LIGHT, Theme.DARK, Theme.STEALTH]


def test_each_sketch_status_has_its_own_line() -> None:
    under, full, over = (line_style(s, construction=False) for s in ("under", "full", "over"))
    assert under != full != over != under
    assert under[1] is Qt.PenStyle.SolidLine and under[0] < full[0]
    assert over[1] is Qt.PenStyle.DotLine
    construction = line_style("under", construction=True)
    assert construction[1] is Qt.PenStyle.DashDotLine  # unlike every status
    assert line_style("full", construction=False, selected=True)[0] > full[0]


def test_points_have_a_shape_per_status() -> None:
    assert len(set(POINT_SHAPES.values())) == 3


@pytest.mark.parametrize("choice", FOUR)
@pytest.mark.parametrize("safe", [False, True])
def test_selection_hover_focus_and_sketch_lines_read_at_three_to_one(
    choice: Theme, safe: bool
) -> None:
    """Item 2, in every theme, with and without the colour vision safe colours."""
    p, c, dark = theme.scheme_for(choice)
    if safe:
        p = theme.colour_safe(p, dark)
    assert failures(p, c, dark) == []
    for background in (p.viewport_top, p.viewport_bottom):
        for colour in (
            p.selection,
            p.preselection,
            p.accent,
            p.sketch_under,
            p.sketch_full,
            p.sketch_over,
        ):
            assert ratio(colour, background) >= MARK
    for background in (c.window, c.surface, c.raised, c.field):
        assert ratio(c.accent, background) >= MARK  # the keyboard focus ring


def test_sketch_hover_uses_the_preselection_colour(qapp: QApplication) -> None:
    from fdcad.core.units import UnitSystem
    from fdcad.ui.sketch_tools.canvas import SketchCanvas
    from tests.ui.sketch_tools.p2_helpers import edit_of

    canvas = SketchCanvas(edit_of(), UnitSystem.MM)
    assert canvas.hover_color().name().upper() == canvas.palette_colors.preselection.upper()


def test_colour_safe_changes_the_status_hues_only() -> None:
    p, _c, dark = theme.scheme_for(Theme.LIGHT)
    safe = theme.colour_safe(p, dark)
    assert safe.sketch_under != p.sketch_under and safe.sketch_over != p.sketch_over
    assert safe.state_error != p.state_error
    assert safe.viewport_top == p.viewport_top and safe.accent == p.accent


def test_colour_safe_switch_reaches_the_palette(qapp: QApplication) -> None:
    try:
        theme.set_colour_safe(True)
        theme.apply_theme(qapp, Theme.LIGHT)
        base = theme.SCHEMES[Theme.LIGHT][0]
        assert theme.palette().sketch_over != base.sketch_over
    finally:
        theme.set_colour_safe(False)
        theme.apply_theme(qapp, Theme.LIGHT)
    assert theme.palette() is theme.SCHEMES[Theme.LIGHT][0]
