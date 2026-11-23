"""Every colour scheme keeps readable contrast (owner request 2026-10-30, D437).

Ratios follow the WCAG 2 formula through one helper, ``themes.contrast``: body
text 7:1 (AAA), captions and error text 4.5:1 (AA), input outlines and marks in
the 3D view 3:1 against what they sit on (UI_POLISH_SPEC U1, D650).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable

import pytest
from PySide6.QtWidgets import QApplication

from fdcad.ui import icons, strings
from fdcad.ui.preferences.settings import Theme
from fdcad.ui.themes import contrast, theme

SCHEMES = list(theme.SCHEMES.items())
IDS = [t.value for t, _ in SCHEMES]


@pytest.mark.parametrize(("name", "scheme"), SCHEMES, ids=IDS)
def test_every_text_input_and_view_pair_is_readable(
    name: Theme, scheme: tuple[theme.Palette, theme.Chrome, bool]
) -> None:
    """U1.1 to U1.5 and U1.7: one helper measures every pair against its limit."""
    p, c, dark = scheme
    assert contrast.failures(p, c, dark) == [], name


@pytest.mark.parametrize(("name", "scheme"), SCHEMES, ids=IDS)
def test_the_pairs_cover_the_spec(
    name: Theme, scheme: tuple[theme.Palette, theme.Chrome, bool]
) -> None:
    p, c, dark = scheme
    what = {x.what for x in contrast.pairs(p, c, dark)}
    for needed in (
        "accent text on surface",
        "accent text on hover",
        "accent text on selected",
        "muted on selected",
        "text on pressed",
        "input outline on window",
        "outline on view top",
        "outline on view bottom",
        "edge on grey face",
        "selection on view bottom",
        "preselection on grey face",
        "state_ok on view bottom",
        "state_warning text on selected",
        "accent on view bottom",
        "tooltip text on tooltip",
        "disabled text on disabled field",
    ):
        assert needed in what, (name, needed)


@pytest.mark.parametrize(("name", "scheme"), SCHEMES, ids=IDS)
def test_open_pairs_meet_their_limits(
    name: Theme, scheme: tuple[theme.Palette, theme.Chrome, bool]
) -> None:
    """Audit D11 item 13 (D745), closed by D2740: accent text on a row under the pointer
    and on a selected row was 4.20 to 4.48 against 4.5. It is 4.61 or more in every
    theme since the Datum colours (D1034), and ``contrast.pairs`` measures it now."""
    p, c, dark = scheme
    rows = {x.what: x for x in contrast.pairs(p, c, dark) if x.what.startswith("accent text on ")}
    for fill in (c.hover, c.selected):
        assert contrast.ratio(c.accent, fill) >= contrast.TEXT, (name, fill)
    for what in ("accent text on hover", "accent text on selected"):
        assert rows[what].minimum == contrast.TEXT, (name, what)
        assert rows[what].value >= rows[what].minimum, (name, what, rows[what].value)


def _short(
    found: Callable[[theme.Palette, theme.Chrome, bool], list[contrast.Pair]],
) -> list[str]:
    """The pairs of every theme that ``found`` lists and that are below their limit."""
    return [
        f"{name}: {x.what} {x.value:.2f}"
        for name, (p, c, dark) in SCHEMES
        for x in found(p, c, dark)
        if x.value < x.minimum
    ]


def test_edges_on_the_bare_view_meet_their_limit() -> None:
    """Audit D11 item 13 (D745): edges against the bare view (wireframe) were 1.17 to
    1.56 against 3.0 in Dark Grey and Stealth. Since D2761 they are drawn in the outline
    colour, which reads on every theme's view."""
    assert _short(contrast.open_edge_pairs) == []


def test_coloured_text_on_the_pressed_fill_meets_its_limit() -> None:
    """D2740, closed by D2840: muted, accent, danger and state text on the pressed fill,
    which a selected row shows while the pointer is on it, was 3.70 to 4.49 against 4.5
    in places in Beige, Light Gray and Dark Grey. The owner approved new pressed fills
    for those three themes on 2026-11-20."""
    assert _short(contrast.open_pressed_pairs) == []


def test_the_old_pressed_fills_were_short() -> None:
    """The check above is not empty: on the fills of before D2840 it finds the eight
    pairs the review listed as P11."""
    old = {Theme.LIGHT: "#C5D6FF", Theme.BEIGE: "#C3D2F0", Theme.DARK: "#2C4886"}
    short = [
        f"{name.value}: {x.what} {x.value:.2f}"
        for name, (p, c, dark) in SCHEMES
        if name in old
        for x in contrast.open_pressed_pairs(p, dataclasses.replace(c, pressed=old[name]), dark)
        if x.value < x.minimum
    ]
    assert sorted(short) == [
        "beige: accent text on pressed 3.98",
        "beige: state_ok text on pressed 4.38",
        "dark: accent text on pressed 3.70",
        "dark: danger text on pressed 4.00",
        "dark: muted on pressed 3.95",
        "dark: state_error text on pressed 4.06",
        "light: accent text on pressed 4.16",
        "light: danger text on pressed 4.49",
    ]


@pytest.mark.parametrize(("name", "scheme"), SCHEMES, ids=IDS)
def test_a_pressed_row_is_not_a_selected_row(
    name: Theme, scheme: tuple[theme.Palette, theme.Chrome, bool]
) -> None:
    """D2840: the pressed fill came closer to the selected fill to be readable. A
    selected row under the pointer must still look different from a selected row: the
    two fills are a clear step apart, and pressed is the one further from the panel
    (U3.1: pressed changes the fill more)."""
    _p, c, dark = scheme
    assert contrast.difference(c.pressed, c.selected) >= contrast.STATE, name
    step = contrast.lightness(c.pressed) - contrast.lightness(c.selected)
    assert step > 1 if dark else step < -1, (name, step)
    # A pressed button stands out from the button under the pointer even more.
    assert contrast.difference(c.pressed, c.hover) >= 2 * contrast.STATE, name


def test_the_open_lists_are_the_whole_open_list() -> None:
    """``open_pairs`` is the two open families, so nothing open is left unlisted."""
    for _name, (p, c, dark) in SCHEMES:
        whole = contrast.open_pairs(p, c, dark)
        parts = contrast.open_edge_pairs(p, c, dark) + contrast.open_pressed_pairs(p, c, dark)
        assert whole == parts
        measured = {x.what for x in contrast.pairs(p, c, dark)}
        assert not measured & {x.what for x in whole}


def test_the_helper_matches_known_ratios() -> None:
    assert contrast.ratio("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert contrast.ratio("#777777", "#777777") == pytest.approx(1.0)
    # The manager's measurements of the old Light accent on the old surface (spec U1.1).
    assert contrast.ratio("#1F6FD1", "#F3F4F5") == pytest.approx(4.48, abs=0.01)
    assert contrast.hue_gap("#FF0000", "#00FF00") == pytest.approx(120.0)
    assert contrast.difference("#777777", "#777777") == pytest.approx(0.0)
    assert contrast.difference("#000000", "#FFFFFF") == pytest.approx(100.0, abs=0.05)
    # Red against green, both at full strength: a published value for CIE76.
    assert contrast.difference("#FF0000", "#00FF00") == pytest.approx(170.6, abs=0.5)


@pytest.mark.parametrize(("name", "scheme"), SCHEMES, ids=IDS)
def test_selection_and_preselection_are_their_own_colours(
    name: Theme, scheme: tuple[theme.Palette, theme.Chrome, bool]
) -> None:
    """U1.4: two clearly different hues, and neither is the sketch accent."""
    p, _c, _dark = scheme
    assert contrast.hue_gap(p.selection, p.preselection) >= 60, name
    for colour in (p.selection, p.preselection):
        assert contrast.hue_gap(colour, p.accent) >= 30, name


def test_the_four_themes_are_one_family() -> None:
    """U1.8: one accent hue, the same state hues and steps, and no pure black chrome."""
    palettes = [p for p, _c, _d in theme.SCHEMES.values()]
    chromes = [c for _p, c, _d in theme.SCHEMES.values()]
    base = palettes[0]
    for p in palettes:
        assert contrast.hue_gap(p.accent, base.accent) <= 6
        for token in ("state_ok", "state_warning", "state_error", "selection", "preselection"):
            assert contrast.hue_gap(getattr(p, token), getattr(base, token)) <= 30, token
    for c in chromes:
        assert contrast.hue_gap(c.accent, chromes[0].accent) <= 6
        window, surface, raised = (contrast.lightness(x) for x in (c.window, c.surface, c.raised))
        assert 2 <= surface - window <= 6
        assert 2 <= raised - surface <= 6
    for t, (_p, c, _d) in theme.SCHEMES.items():
        for token in ("surface", "raised", "field", "hover", "selected", "pressed"):
            assert getattr(c, token) != "#000000", (t, token)
        if t is not Theme.STEALTH:
            assert c.window != "#000000", t


def test_four_named_schemes_in_preferences() -> None:
    labels = [label for label, _ in strings.THEME_CHOICES]
    assert labels[:4] == ["Beige", "Light Gray", "Dark Grey", "Stealth (black)"]
    # Contrast follows a Windows contrast theme and is never chosen (TR378, D768).
    assert {Theme(v) for _, v in strings.THEME_CHOICES} == set(Theme) - {Theme.CONTRAST}


@pytest.mark.parametrize("choice", [Theme.BEIGE, Theme.LIGHT, Theme.DARK, Theme.STEALTH])
def test_apply_theme_uses_the_chosen_scheme(qapp: QApplication, choice: Theme) -> None:
    theme.apply_theme(qapp, choice)
    try:
        assert theme.current() is choice
        assert theme.palette() is theme.SCHEMES[choice][0]
        assert theme.chrome() is theme.SCHEMES[choice][1]
        assert theme.is_dark() == (choice in (Theme.DARK, Theme.STEALTH))
        # One accent per light or dark family, the same as the icons (D111).
        assert theme.chrome().accent == icons.ACCENT[theme.is_dark()]
    finally:
        theme.apply_theme(qapp, Theme.LIGHT)


@pytest.mark.parametrize(("name", "scheme"), SCHEMES, ids=[t.value for t, _ in SCHEMES])
def test_plane_outline_and_names_read_on_the_view(
    name: Theme, scheme: tuple[theme.Palette, theme.Chrome, bool]
) -> None:
    """Plane names are text in the outline colour (owner note 2026-10-30)."""
    p, _, _ = scheme
    for background in (p.viewport_top, p.viewport_bottom):
        assert contrast.ratio(p.plane_outline, background) >= 4.5, (name, background)


@pytest.mark.parametrize(("name", "scheme"), SCHEMES, ids=[t.value for t, _ in SCHEMES])
def test_temporary_axes_read_on_the_view(
    name: Theme, scheme: tuple[theme.Palette, theme.Chrome, bool]
) -> None:
    """Audit D11 item 5 (D719): the axes used the edge colour, nearly invisible on the
    dark themes. They use the accent, which must read on both ends of the gradient."""
    p, _, _ = scheme
    for background in (p.viewport_top, p.viewport_bottom):
        assert contrast.ratio(p.accent, background) >= 3.0, (name, background)
