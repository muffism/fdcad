"""Light and dark themes, and sketch colours (PLAN section 8 items 5 and 6, D111).

A theme is two sets of colours: ``Palette`` for what FDCAD paints itself (the
view background, sketches, feature states) and ``Chrome`` for Qt's widgets
(panels, tabs, the tree, buttons). ``apply_theme`` turns the chrome colours into
a Qt palette plus the application style sheet from ``themes.style``.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

from fdcad.ui.preferences.settings import Theme


@dataclass(frozen=True)
class Palette:
    """Colours used outside Qt's own widgets (hex strings)."""

    viewport_top: str
    viewport_bottom: str
    edge: str
    sketch_under: str
    sketch_full: str
    sketch_over: str
    state_ok: str
    state_warning: str
    state_error: str
    #: Sketch grid lines, with alpha (``#AARRGGBB``), drawn over the gradient.
    grid: str = "#1CFFFFFF"
    #: The one accent colour (D111), also for selected sketch items (T1.4.1).
    accent: str = "#1F54E6"
    #: Reference planes (T13): smoke grey outline and label, a light fill (D121).
    #: The outline and name read at 4.5:1 or more on both ends of the view gradient.
    plane_outline: str = "#3E4550"
    plane_fill: str = "#C9CDD2"
    #: Selected items in the 3D view, such as a plane selected in the tree. Selection and
    #: pre-selection read at 3:1 on the view and are two different hues, neither of them
    #: the accent (U1.4, D651).
    selection: str = "#AD4200"
    #: The highlight under the cursor before a click (pre-selection).
    preselection: str = "#00705F"
    #: FDCAD's plain grey part, the face the view colours are checked against (U1.3).
    face: str = "#B4BCC4"
    #: The outline drawn around the part (U6.4). It reads at 3:1 on both ends of the view
    #: gradient, so the part's shape is clear from any angle. ``edge`` is for the edges
    #: drawn on the faces and reads at 3:1 on the grey face (D654).
    silhouette: str = "#1A1F26"
    #: Projected part edges and reference geometry in a sketch.
    sketch_reference: str = "#5E6670"
    #: Drag arrows that are not the active one (T5.2).
    handle_idle: str = "#5E6670"
    #: Text drawn in the view: axis letters and the triad (U6.7).
    view_text: str = "#2B3038"
    #: Reference geometry made from a mesh.
    mesh_reference: str = "#7C8792"
    #: Axis colours: sketch origin marks and the triad in the view corner.
    axis_x: str = "#C0392B"
    axis_y: str = "#24733A"
    axis_z: str = "#2457C5"
    #: Relation tags in a sketch: fill, outline and text.
    tag_fill: str = "#FFF1B8"
    tag_line: str = "#6B5A00"
    #: Plate behind dimension values, with alpha (``#AARRGGBB``), and a fainter one for
    #: the dimension that follows the cursor.
    label_plate: str = "#A0FFFFFF"
    label_plate_faint: str = "#6EFFFFFF"
    #: The see through plate behind the view toolbar, its outline and button hover.
    view_plate: str = "#B3FFFFFF"
    view_plate_line: str = "#14000000"
    view_plate_hover: str = "#10000000"


@dataclass(frozen=True)
class Chrome:
    """Colours of the window chrome: panels, tabs, lists and buttons (hex strings)."""

    window: str  # menu bar, command tab bar, status bar
    surface: str  # command tab body, panels, the tree
    raised: str  # group headers, buttons, plates
    field: str  # text fields and drop down boxes
    border: str
    border_strong: str
    text: str
    muted: str  # captions and disabled text
    accent: str  # the one accent colour: focus, current tab, selection mark
    on_accent: str  # text on an accent fill
    hover: str
    selected: str  # selected row fill
    pressed: str
    danger: str
    #: Outline of text fields, drop downs, check boxes, spin boxes and slider grooves:
    #: 3:1 against what is around it (U1.2). ``border`` stays for quiet dividers.
    input_border: str = "#7D838B"
    #: Material a tool takes away, in icons (cuts, holes, trims): the second colour of
    #: the Datum language (D1034). It reads at 3:1 on every panel colour.
    cut: str = "#CF5409"


#: Light (the default, D437), in the Datum colours (D1034): cool paper greys, cobalt.
LIGHT = Palette(
    viewport_top="#F4F6FA",
    viewport_bottom="#C6CBD2",
    edge="#161B24",
    sketch_under="#1B50D8",
    sketch_full="#101216",
    sketch_over="#B42020",
    state_ok="#1A6A30",
    state_warning="#7A5600",
    state_error="#A32626",
    grid="#14000A1E",
    accent="#1F54E6",
    plane_outline="#3A4252",
    plane_fill="#C6CCD6",
    selection="#AD4200",
    preselection="#00705F",
    silhouette="#161B24",
    sketch_reference="#596273",
    handle_idle="#596273",
    view_text="#262C38",
)
#: Beige: warm paper tones (D437), with the same cobalt.
BEIGE = Palette(
    viewport_top="#F8F4EB",
    viewport_bottom="#DAD0BD",
    edge="#2A251F",
    silhouette="#2A251F",
    sketch_under="#1B50D8",
    sketch_full="#111111",
    sketch_over="#B42020",
    state_ok="#1D6A2E",
    state_warning="#735100",
    state_error="#9E231C",
    grid="#16000000",
    accent="#1F54E6",
    plane_outline="#55493A",
    plane_fill="#D3C8B2",
    selection="#AD4200",
    preselection="#00705F",
    sketch_reference="#665C4E",
    handle_idle="#665C4E",
    view_text="#2F2922",
    tag_line="#5E4F00",
    view_plate="#B3FFFDF8",
)
#: Dark: graphite with a cool cast.
DARK = Palette(
    viewport_top="#414855",
    viewport_bottom="#1B1E24",
    edge="#262B33",
    silhouette="#B2B9C4",
    sketch_under="#8FB4FF",
    sketch_full="#F2F4F7",
    sketch_over="#FF9090",
    state_ok="#6FD07F",
    state_warning="#F0C040",
    state_error="#FF9090",
    grid="#1CFFFFFF",
    accent="#7FA6FF",
    plane_outline="#E1E5EC",
    plane_fill="#D3D8E0",
    selection="#FFD060",
    preselection="#7FF0D0",
    sketch_reference="#A7AFBB",
    handle_idle="#A7AFBB",
    view_text="#E4E8EE",
    mesh_reference="#8E98A6",
    axis_x="#FF7A6B",
    axis_y="#6FD07F",
    axis_z="#7FA8FF",
    label_plate="#5A000000",
    label_plate_faint="#3C000000",
    view_plate="#8C15181D",
    view_plate_line="#1FFFFFFF",
    view_plate_hover="#1AFFFFFF",
)
#: Stealth: black (D437).
STEALTH = Palette(
    viewport_top="#1A1C21",
    viewport_bottom="#000000",
    edge="#2B2F35",
    silhouette="#8E949B",
    sketch_under="#7FA6FF",
    sketch_full="#F2F2F2",
    sketch_over="#FF6B6B",
    state_ok="#6FD07F",
    state_warning="#F0C040",
    state_error="#FF8A8A",
    grid="#18FFFFFF",
    accent="#7FA6FF",
    plane_outline="#C3C8CF",
    plane_fill="#C8CCD2",
    selection="#FFD060",
    preselection="#7FF0D0",
    sketch_reference="#8C9299",
    handle_idle="#8C9299",
    view_text="#DADDE2",
    mesh_reference="#7C8792",
    axis_x="#FF7A6B",
    axis_y="#6FD07F",
    axis_z="#7FA8FF",
    label_plate="#6E000000",
    label_plate_faint="#46000000",
    view_plate="#A60C0C0E",
    view_plate_line="#1FFFFFFF",
    view_plate_hover="#1AFFFFFF",
)

LIGHT_CHROME = Chrome(
    window="#E9ECF1",
    surface="#F5F6F9",
    raised="#FFFFFF",
    field="#FFFFFF",
    border="#D8DCE3",
    border_strong="#B3BAC6",
    text="#14171C",
    muted="#525A68",
    accent="#1F54E6",
    on_accent="#FFFFFF",
    hover="#E4E8EF",
    selected="#DAE5FF",
    pressed="#D1DFFF",
    danger="#B3261E",
    input_border="#788190",
    cut="#CF5409",
)
BEIGE_CHROME = Chrome(
    window="#EAE3D4",
    surface="#F6F1E7",
    raised="#FFFCF5",
    field="#FFFDF8",
    border="#D9CFBB",
    border_strong="#B3A68C",
    text="#2A251F",
    muted="#5E5547",
    accent="#1F54E6",
    on_accent="#FFFFFF",
    hover="#E9E0CD",
    selected="#DAE3F6",
    pressed="#D1DFFD",
    danger="#9E231C",
    input_border="#7C7262",
    cut="#BF4E08",
)
DARK_CHROME = Chrome(
    window="#16181C",
    surface="#1E2126",
    raised="#292D34",
    field="#111317",
    border="#333842",
    border_strong="#4B525E",
    text="#ECEEF2",
    muted="#A6AEBA",
    accent="#7FA6FF",
    on_accent="#06122B",
    hover="#2C3139",
    selected="#22386B",
    pressed="#1B3980",
    danger="#FF8F85",
    input_border="#808998",
    cut="#FF9D5C",
)
STEALTH_CHROME = Chrome(
    window="#000000",
    surface="#0A0A0C",
    raised="#15161A",
    field="#050506",
    border="#25272C",
    border_strong="#3C3F46",
    text="#EDEEF1",
    muted="#A0A4AC",
    accent="#7FA6FF",
    on_accent="#000000",
    hover="#1D1F24",
    selected="#14274E",
    pressed="#1C376B",
    danger="#FF8A8A",
    input_border="#747982",
    cut="#FF9D5C",
)

#: The brand colours (D1034): the app icon's tile, and the start picture and About
#: window that sit on it. The same in every theme. ``tools/make_brand.py`` draws the
#: mark in them.
BRAND: dict[str, str] = {
    "tile_top": "#24388F",
    "tile_bottom": "#0A1030",
    "on_tile": "#FFFFFF",
    "on_tile_soft": "#B8C4EE",
    "tile_line": "#3C52B0",
    "ember": "#F4680E",
}

#: Colours that mean the same thing in every theme (U1.6, D652): analysis maps painted
#: on the part, the node editor's category bands and port types, and the cursor.
#: They are FDCAD's own choices and do not change with the theme.
DATA: dict[str, str] = {
    "draft_positive": "#3FA34D",
    "draft_negative": "#D03B3B",
    "before_after": "#7A4FB8",  # TR289 (D2019): the shape from before a change
    "draft_needs": "#E8C33A",
    "draft_straddle": "#3C7DD9",
    "overhang_full": "#D03B3B",
    "overhang_partial": "#F0A030",
    "wall_full": "#8E3FC8",
    "wall_partial": "#E58FC8",
    "fits": "#2E8B57",
    "too_big": "#D03B3B",
    "pull_side": "#9AA0A6",
    "edge_sharp": "#D03B3B",
    "edge_nearly_smooth": "#E8C33A",
    "node_band_text": "#FFFFFF",
    "node_unknown": "#888888",
    "cursor_fill": "#1B1E23",
    "cursor_line": "#FFFFFF",
    "mesh_preview": "#4A90C8",  # TR336 (D1200)
}
#: Node editor band colour per category.
NODE_CATEGORIES: dict[str, str] = {
    "Input": "#3E8E7E",
    "Math": "#7A6BB0",
    "List": "#B07A3E",
    "Point and Vector": "#3E74B0",
    "Curve": "#2F9AA8",
    "Solid": "#7C8A99",
    "Pattern": "#A85C8A",
    "Output": "#C2563F",
    "Display": "#9A9A5A",
}
#: Node editor port colour per port type (the type's value).
NODE_PORTS: dict[str, str] = {
    "number": "#9AA4AE",
    "length": "#5AA9E6",
    "angle": "#E6B35A",
    "boolean": "#E67A5A",
    "point": "#6FCF97",
    "vector": "#4FB3A0",
    "plane": "#B39DDB",
    "curve": "#4DD0E1",
    "body": "#C0C7CF",
    "list": "#F2C94C",
}


def css(colour: str) -> str:
    """A token as a style sheet colour: ``#AARRGGBB`` becomes ``rgba()``."""
    text = colour.lstrip("#")
    if len(text) != 8:
        return colour
    a, r, g, b = (int(text[i : i + 2], 16) for i in (0, 2, 4, 6))
    return f"rgba({r}, {g}, {b}, {a / 255:.2f})"


#: Each colour scheme: its view palette, its chrome and whether it is dark.
SCHEMES: dict[Theme, tuple[Palette, Chrome, bool]] = {
    Theme.BEIGE: (BEIGE, BEIGE_CHROME, False),
    Theme.LIGHT: (LIGHT, LIGHT_CHROME, False),
    Theme.DARK: (DARK, DARK_CHROME, True),
    Theme.STEALTH: (STEALTH, STEALTH_CHROME, True),
}

#: The theme chosen with ``apply_theme``; None follows the system colour scheme.
_forced: Theme | None = None
_listening = False
#: The system's contrast colours while a Windows contrast theme is on (TR378), else None.
#: Tests set it with ``set_system_contrast``; ``apply_theme`` reads it from Windows.
_contrast: object | None = None
_contrast_override = False
#: The colour sets made from ``_contrast``; kept out of ``SCHEMES``, which holds the four
#: themes users choose.
_contrast_scheme: tuple[Palette, Chrome, bool] | None = None


#: Colour vision safe status colours (TR292, D769): a preference, off by default.
_colour_safe = False


def set_colour_safe(on: bool) -> None:
    """Use the colour vision safe status colours (the caller restyles)."""
    global _colour_safe
    _colour_safe = on


def colour_safe(p: Palette, dark: bool) -> Palette:
    """``p`` with sketch status and feature state colours that stay apart for the common
    kinds of colour blindness: blue and orange in place of green and red."""
    from dataclasses import replace

    if dark:
        return replace(
            p,
            sketch_under="#6CC0EC",
            sketch_over="#EBA51A",
            state_ok="#6CC0EC",
            state_warning="#F0E442",
            state_error="#EBA51A",
        )
    return replace(
        p,
        sketch_under="#005A8E",
        sketch_over="#A84600",
        state_ok="#005A8E",
        state_warning="#6B5A00",
        state_error="#A84600",
    )


def _scheme() -> tuple[Palette, Chrome, bool]:
    p, c, dark = scheme_for(current())
    if _colour_safe and current() is not Theme.CONTRAST:
        return colour_safe(p, dark), c, dark
    return p, c, dark


def scheme_for(theme: Theme) -> tuple[Palette, Chrome, bool]:
    """The view palette, chrome and darkness of ``theme``, including the system contrast
    colours (TR378). Use this instead of ``SCHEMES[...]`` for the current theme."""
    if theme is Theme.CONTRAST:
        if _contrast_scheme is not None:
            return _contrast_scheme
        return SCHEMES[Theme.LIGHT]
    if theme is Theme.SYSTEM:
        return SCHEMES[Theme.LIGHT]
    return SCHEMES[theme]


def set_system_contrast(colors: object | None) -> None:
    """Use these system contrast colours (a ``SystemColors``) instead of asking Windows,
    or None to stop (tests and the screenshot tool)."""
    global _contrast_override, _contrast
    _contrast_override = colors is not None
    _contrast = colors


def _read_contrast() -> None:
    global _contrast, _contrast_scheme
    if not _contrast_override:
        from fdcad.ui.themes.system_contrast import read

        _contrast = read()
    _contrast_scheme = None
    if _contrast is not None:
        from fdcad.ui.themes.system_contrast import SystemColors, scheme

        assert isinstance(_contrast, SystemColors)
        _contrast_scheme = scheme(_contrast)


def is_dark() -> bool:
    """True when the app currently shows the dark colour scheme."""
    return _scheme()[2]


def current() -> Theme:
    """The colour scheme in use: the system contrast colours while a Windows contrast
    theme is on (TR378), else the chosen one, or light or dark from the system."""
    if _contrast_scheme is not None:
        return Theme.CONTRAST
    if _forced is not None:
        return _forced
    hints = QGuiApplication.styleHints()
    return Theme.DARK if hints.colorScheme() == Qt.ColorScheme.Dark else Theme.LIGHT


def palette() -> Palette:
    """The palette for the current colour scheme."""
    return _scheme()[0]


def chrome() -> Chrome:
    """The chrome colours for the current colour scheme."""
    return _scheme()[1]


def qt_palette(c: Chrome) -> QPalette:
    """A Qt palette from the chrome colours, so widgets without style rules match too."""
    roles = QPalette.ColorRole
    colors = {
        roles.Window: c.window,
        roles.WindowText: c.text,
        roles.Base: c.field,
        roles.AlternateBase: c.surface,
        roles.Text: c.text,
        roles.Button: c.raised,
        roles.ButtonText: c.text,
        roles.BrightText: c.danger,
        roles.Light: c.raised,
        roles.Midlight: c.border,
        roles.Mid: c.border_strong,
        roles.Dark: c.border_strong,
        roles.Shadow: "#000000",
        roles.Highlight: c.accent,
        roles.HighlightedText: c.on_accent,
        roles.Link: c.accent,
        roles.ToolTipBase: c.raised,
        roles.ToolTipText: c.text,
        roles.PlaceholderText: c.muted,
        roles.Accent: c.accent,
    }
    result = QPalette()
    for role, value in colors.items():
        result.setColor(role, QColor(value))
    disabled = QPalette.ColorGroup.Disabled
    for role in (roles.WindowText, roles.Text, roles.ButtonText):
        result.setColor(disabled, role, QColor(c.muted))
    result.setColor(disabled, roles.Highlight, QColor(c.border_strong))
    return result


def restyle(app: QApplication) -> None:
    """Set the Qt palette and style sheet of the current colour scheme."""
    from fdcad.ui.themes.style import stylesheet
    from fdcad.ui.themes.typography import apply_type_scale

    apply_type_scale(app)  # one type scale (U2.1)
    c = chrome()
    app.setPalette(qt_palette(c))
    app.setStyleSheet(stylesheet(c, palette(), app.font()))


def apply_theme(app: QApplication, theme: Theme) -> None:
    """Use the Fusion style with the chosen colour scheme, palette and style sheet."""
    global _forced, _listening
    from fdcad.ui.themes.app_style import install

    install(app)  # Fusion with FDCAD's menu rows, focus ring and names (D661)
    _read_contrast()
    if theme is Theme.SYSTEM or theme is Theme.CONTRAST:
        color_scheme = Qt.ColorScheme.Unknown
        _forced = None
    else:
        color_scheme = Qt.ColorScheme.Dark if SCHEMES[theme][2] else Qt.ColorScheme.Light
        _forced = theme
    if _contrast_scheme is not None:
        color_scheme = Qt.ColorScheme.Dark if _contrast_scheme[2] else Qt.ColorScheme.Light
    if not _listening:
        # Following the system: restyle when the system switches light and dark.
        app.styleHints().colorSchemeChanged.connect(lambda _s: restyle(app))
        _listening = True
    app.styleHints().setColorScheme(color_scheme)
    restyle(app)
