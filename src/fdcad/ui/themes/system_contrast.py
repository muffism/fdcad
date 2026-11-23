"""Windows contrast themes (TR378, DECISIONS D768).

When a Windows contrast theme is on, FDCAD draws with the system's own colours
instead of its themes: the window, text, highlight, button, disabled text and
link colours the user chose. ``read`` asks Windows (``SystemParametersInfo`` and
``GetSysColor``, through ctypes) and gives None on other platforms or when the
setting is off. ``scheme`` turns the system colours into FDCAD's two colour sets.
Every FDCAD colour comes from one of the system colours; where a system colour
would not meet FDCAD's contrast limits on its background (``contrast.pairs``),
the text colour, which a contrast theme always keeps far from the window colour,
is used instead.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, replace

from fdcad.ui.themes.contrast import BODY, MARK, TEXT, luminance, ratio
from fdcad.ui.themes.theme import Chrome, Palette


@dataclass(frozen=True)
class SystemColors:
    """The colours of a contrast theme (hex strings)."""

    window: str
    text: str
    highlight: str
    highlight_text: str
    button: str
    button_text: str
    gray_text: str
    hotlight: str  # links


#: Four typical contrast colour sets, FDCAD's own samples (not any platform's named
#: themes): light text on black, black on white, and two coloured ones. The tests and
#: the screenshot tool (``tools/screenshot_tabs.py --contrast``) use them.
SAMPLES: dict[str, SystemColors] = {
    "white_on_black": SystemColors(
        "#000000", "#FFFFFF", "#1AEBFF", "#000000", "#000000", "#FFFFFF", "#3FF23F", "#FFFF00"
    ),
    "black_on_white": SystemColors(
        "#FFFFFF", "#000000", "#37006E", "#FFFFFF", "#FFFFFF", "#000000", "#600000", "#00009F"
    ),
    "yellow_on_dark": SystemColors(
        "#202020", "#FFFF00", "#8080FF", "#000000", "#202020", "#FFFF00", "#A6A6A6", "#75E9FC"
    ),
    "dark_on_cream": SystemColors(
        "#FFFAEF", "#3D3D3D", "#903909", "#FFF5E3", "#FFFAEF", "#202020", "#676767", "#1C5E75"
    ),
}

#: Windows system colour indexes (GetSysColor).
_INDEX = {
    "window": 5,
    "text": 8,
    "highlight": 13,
    "highlight_text": 14,
    "button": 15,
    "button_text": 18,
    "gray_text": 17,
    "hotlight": 26,
}
_SPI_GETHIGHCONTRAST = 0x0042
_HCF_HIGHCONTRASTON = 0x0001


def _hex(colorref: int) -> str:
    r, g, b = colorref & 0xFF, (colorref >> 8) & 0xFF, (colorref >> 16) & 0xFF
    return f"#{r:02X}{g:02X}{b:02X}"


def read() -> SystemColors | None:
    """The system contrast colours when a Windows contrast theme is on, else None."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class _HighContrast(ctypes.Structure):
            _fields_ = (
                ("cbSize", wintypes.UINT),
                ("dwFlags", wintypes.DWORD),
                ("lpszDefaultScheme", wintypes.LPWSTR),
            )

        info = _HighContrast()
        info.cbSize = ctypes.sizeof(_HighContrast)
        user32 = ctypes.windll.user32  # type: ignore[attr-defined,unused-ignore]
        if not user32.SystemParametersInfoW(
            _SPI_GETHIGHCONTRAST, info.cbSize, ctypes.byref(info), 0
        ):
            return None
        if not info.dwFlags & _HCF_HIGHCONTRASTON:
            return None
        return SystemColors(**{name: _hex(user32.GetSysColor(i)) for name, i in _INDEX.items()})
    except Exception:  # never let a missing call stop the app from starting
        return None


def _readable(background: str, minimum: float, *candidates: str) -> str:
    """The first candidate that meets ``minimum`` on ``background``; else black or white."""
    for colour in candidates:
        if ratio(colour, background) >= minimum:
            return colour
    return "#000000" if luminance(background) > 0.18 else "#FFFFFF"


def scheme(s: SystemColors) -> tuple[Palette, Chrome, bool]:
    """FDCAD's view palette, chrome colours and darkness from the system colours."""
    dark = luminance(s.window) < 0.18
    text = _readable(s.window, BODY, s.text)
    accent = _readable(s.window, TEXT, s.highlight, s.hotlight, text)
    muted = _readable(s.window, TEXT, s.gray_text, text)
    raised = (
        s.button
        if ratio(_readable(s.button, BODY, s.button_text, text), s.button) >= BODY
        else s.window
    )
    chrome = Chrome(
        window=s.window,
        surface=s.window,
        raised=raised,
        field=s.window,
        border=text,
        border_strong=text,
        text=text,
        muted=muted,
        accent=accent,
        on_accent=_readable(accent, TEXT, s.highlight_text, s.window, text),
        hover=raised,
        selected=raised,
        pressed=raised,
        danger=_readable(s.window, TEXT, s.hotlight, s.highlight, text),
        input_border=text,
    )
    if ratio(text, raised) < BODY:  # rows and buttons in the window colour then
        chrome = replace(
            chrome, raised=s.window, hover=s.window, selected=s.window, pressed=s.window
        )
    mark = _readable(s.window, MARK, s.text)
    other = _readable(s.window, MARK, s.hotlight, s.highlight, mark)
    face = s.window
    palette = Palette(
        viewport_top=s.window,
        viewport_bottom=s.window,
        edge=_readable(face, MARK, s.text),
        sketch_under=other,
        sketch_full=mark,
        sketch_over=_readable(s.window, MARK, s.highlight, other, mark),
        state_ok=_readable(s.window, TEXT, s.text),
        state_warning=_readable(s.window, TEXT, s.hotlight, s.text),
        state_error=_readable(s.window, TEXT, s.highlight, s.text),
        grid="#33" + mark.lstrip("#"),
        accent=accent,
        plane_outline=_readable(s.window, TEXT, s.text),
        plane_fill=s.window,
        selection=_readable(face, MARK, s.highlight, other, mark),
        preselection=_readable(face, MARK, s.hotlight, mark),
        face=face,
        silhouette=mark,
        sketch_reference=_readable(s.window, MARK, s.gray_text, mark),
        handle_idle=_readable(s.window, MARK, s.gray_text, mark),
        view_text=_readable(s.window, TEXT, s.text),
        mesh_reference=_readable(s.window, MARK, s.gray_text, mark),
        axis_x=mark,
        axis_y=mark,
        axis_z=mark,
        tag_fill=s.window,
        tag_line=_readable(s.window, TEXT, s.text),
        label_plate="#E6" + s.window.lstrip("#"),
        label_plate_faint="#B3" + s.window.lstrip("#"),
        view_plate="#E6" + s.window.lstrip("#"),
        view_plate_line="#FF" + mark.lstrip("#"),
        view_plate_hover="#33" + mark.lstrip("#"),
    )
    return palette, chrome, dark
