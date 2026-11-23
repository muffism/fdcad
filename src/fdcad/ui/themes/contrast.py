"""Contrast checks for the four themes (UI_POLISH_SPEC U1, D650).

One helper, ``ratio``, computes the WCAG 2 contrast of two colours. ``pairs``
lists every text, input and view pair a theme must keep readable, with the
lowest ratio allowed. The tests run ``pairs`` for every theme, so a colour
change that makes something hard to read fails at once.
"""

from __future__ import annotations

import colorsys
from dataclasses import dataclass

from fdcad.ui.themes.theme import Chrome, Palette

#: Body text and captions (WCAG AA).
TEXT = 4.5
#: Body text on the plain backgrounds (WCAG AAA).
BODY = 7.0
#: Outlines of inputs, and marks drawn in the 3D view (WCAG non text contrast).
MARK = 3.0
#: Selection and pre-selection against a plain grey face in the dark themes. A colour
#: cannot be 3:1 against both a dark background and a light grey part, so in the dark
#: themes the highlight is lighter than the face and also drawn thicker (D651).
DARK_FACE = 1.3
#: The least colour difference (CIE76) between the fills of two states of one row: one
#: and a half times the 2.3 that an eye can just tell apart (D2840).
STATE = 3.45


def _rgb(colour: str) -> tuple[float, float, float]:
    text = colour.lstrip("#")[-6:]
    r, g, b = (int(text[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return r, g, b


def _linear(colour: str) -> list[float]:
    return [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in _rgb(colour)]


def luminance(colour: str) -> float:
    """Relative luminance of ``#RRGGBB`` (or ``#AARRGGBB``, alpha ignored)."""
    linear = _linear(colour)
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def ratio(a: str, b: str) -> float:
    """WCAG contrast ratio of two colours, from 1 to 21."""
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def hue(colour: str) -> float:
    """Hue in degrees, 0 to 360."""
    h, _l, _s = colorsys.rgb_to_hls(*_rgb(colour))
    return h * 360.0


def hue_gap(a: str, b: str) -> float:
    """Smallest angle between the hues of two colours, in degrees."""
    d = abs(hue(a) - hue(b)) % 360.0
    return min(d, 360.0 - d)


def lightness(colour: str) -> float:
    """CIE L* (0 black to 100 white), for the steps between surfaces."""
    y = luminance(colour)
    return 116.0 * y ** (1 / 3) - 16.0 if y > 216 / 24389 else y * 24389 / 27


def _lab(colour: str) -> tuple[float, float, float]:
    """CIE L*a*b* of a colour, for the white of a screen (D65)."""
    r, g, b = _linear(colour)
    xyz = (
        (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.9505,
        0.2126 * r + 0.7152 * g + 0.0722 * b,
        (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.0890,
    )
    fx, fy, fz = (v ** (1 / 3) if v > 216 / 24389 else (24389 / 27 * v + 16) / 116 for v in xyz)
    return 116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz)


def difference(a: str, b: str) -> float:
    """How far apart two colours look (CIE76): about 2.3 can just be told apart. Unlike
    ``ratio`` it counts a change of hue or of strength, not only one of lightness."""
    la, lb = _lab(a), _lab(b)
    return float(sum((x - y) ** 2 for x, y in zip(la, lb, strict=True)) ** 0.5)


@dataclass(frozen=True)
class Pair:
    """One colour on one background and the lowest contrast allowed."""

    what: str
    colour: str
    background: str
    minimum: float

    @property
    def value(self) -> float:
        """The measured contrast."""
        return ratio(self.colour, self.background)


def pairs(p: Palette, c: Chrome, dark: bool) -> list[Pair]:
    """Every pair one theme must keep readable (U1.1 to U1.5)."""
    out: list[Pair] = []

    def add(what: str, colour: str, backgrounds: dict[str, str], minimum: float) -> None:
        for name, background in backgrounds.items():
            out.append(Pair(f"{what} on {name}", colour, background, minimum))

    plain = {
        "window": c.window,
        "surface": c.surface,
        "raised": c.raised,
        "field": c.field,
    }
    rows = {"hover": c.hover, "selected": c.selected}
    add("text", c.text, plain | {"hover": c.hover}, BODY)
    add("text", c.text, {"selected": c.selected, "pressed": c.pressed}, TEXT)
    add("muted", c.muted, plain | rows, TEXT)
    # Accent text on a row under the pointer and on a selected row was open in D745
    # (4.20 to 4.48 in the colours of that day). The Datum colours (D1034) brought it
    # to 4.61 or more in every theme, so it is measured here like any other pair (D2740).
    add("accent text", c.accent, plain | rows, TEXT)
    # Pairs U1 and U3.1 name that were not measured (audit D11 item 13, D745). Edges on
    # the bare view and coloured text on a pressed fill are in ``open_pairs``, which
    # every theme meets too (D2761, D2840).
    add("tooltip text", c.text, {"tooltip": c.raised}, BODY)
    add("disabled text", c.muted, {"disabled field": c.surface, "window": c.window}, TEXT)
    add("danger text", c.danger, plain | {"hover": c.hover}, TEXT)
    add("text on accent", c.on_accent, {"accent": c.accent}, TEXT)
    add("input outline", c.input_border, plain, MARK)
    # The neutral left edge of an information bar (D2700): on its card and on the top
    # of the view, where the bars sit. A warning bar's edge is ``state_warning`` below.
    add("notice edge", c.muted, {"raised": c.raised, "view top": p.viewport_top}, MARK)
    tree = {"surface": c.surface, "raised": c.raised} | rows
    view = {"view top": p.viewport_top, "view bottom": p.viewport_bottom}
    for name in ("state_ok", "state_warning", "state_error"):
        colour = getattr(p, name)
        add(f"{name} text", colour, tree, TEXT)
        add(name, colour, view, MARK)
    add("accent", p.accent, view, MARK)
    for name in ("sketch_under", "sketch_full", "sketch_over", "sketch_reference"):
        add(name, getattr(p, name), view, MARK)
    add("handle", p.handle_idle, view, MARK)
    add("plane name", p.plane_outline, view, TEXT)
    add("view text", p.view_text, view, TEXT)
    for name in ("axis_x", "axis_y", "axis_z"):
        add(name, getattr(p, name), view, MARK)
    add("outline", p.silhouette, view, MARK)
    add("edge", p.edge, {"grey face": p.face}, MARK)
    for name in ("selection", "preselection"):
        colour = getattr(p, name)
        add(name, colour, view, MARK)
        add(name, colour, {"grey face": p.face}, DARK_FACE if dark else MARK)
    return out


def open_edge_pairs(p: Palette, c: Chrome, dark: bool) -> list[Pair]:
    """Lines against the bare view, as wireframe and the hidden line styles draw them.
    They were below 3:1 in Dark Grey and Stealth in the ``edge`` colour (audit D11 item
    13, D745); since D2761 they are drawn in the outline colour, which meets it."""
    del c, dark
    return [
        Pair(f"wireframe line on {name}", p.silhouette, colour, MARK)
        for name, colour in (("view top", p.viewport_top), ("view bottom", p.viewport_bottom))
    ]


def open_pressed_pairs(p: Palette, c: Chrome, dark: bool) -> list[Pair]:
    """Coloured text on the pressed fill, which is also the fill of a selected row
    while the pointer is on it (U1.1 names pressed fills). Measured on 2026-11-19
    (D2740), some were below 4.5:1 in Beige, Light Gray and Dark Grey. The pressed
    fills of those three themes changed on 2026-11-20 (D2840) and every pair is 4.52
    or more. Plain text on the fill is in ``pairs``."""
    del dark
    colours = {
        "muted": c.muted,
        "accent text": c.accent,
        "danger text": c.danger,
        "state_ok text": p.state_ok,
        "state_warning text": p.state_warning,
        "state_error text": p.state_error,
    }
    return [Pair(f"{what} on pressed", colour, c.pressed, TEXT) for what, colour in colours.items()]


def open_pairs(p: Palette, c: Chrome, dark: bool) -> list[Pair]:
    """The two families of pairs U1 and U3.1 name that were open after D745. Every
    theme meets both now; they keep their own lists and tests."""
    return open_edge_pairs(p, c, dark) + open_pressed_pairs(p, c, dark)


def failures(p: Palette, c: Chrome, dark: bool) -> list[str]:
    """Readable descriptions of the pairs below their limit."""
    return [
        f"{x.what}: {x.value:.2f} < {x.minimum}" for x in pairs(p, c, dark) if x.value < x.minimum
    ]
