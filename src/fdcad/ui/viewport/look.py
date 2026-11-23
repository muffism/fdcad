"""How the 3D view draws: smoothing, lights, edges, outlines, highlights and text (U6,
D653; reviewed on a real screen in D2760 to D2766, docs/VIEW_REVIEW_2026-11-19.md, and
again for the review's six proposals in D2820 to D2826).

The numbers live here so they are tested without a GPU, and the ``apply_*`` and
``style_*`` functions set them on the kernel objects. Every colour comes from the
theme's ``Palette``; this module only decides widths, light strengths and directions.
"""

from __future__ import annotations

from dataclasses import dataclass

from OCP.Aspect import Aspect_POM_Fill, Aspect_TOL_DASH, Aspect_TOL_SOLID
from OCP.Graphic3d import (
    Graphic3d_PolygonOffset,
    Graphic3d_TOSM_FRAGMENT,
    Graphic3d_TOSM_UNLIT,
    Graphic3d_ZLayerId_Top,
    Graphic3d_ZLayerId_TopOSD,
)
from OCP.Prs3d import Prs3d_Drawer, Prs3d_LineAspect, Prs3d_TypeOfHighlight
from OCP.Quantity import Quantity_Color, Quantity_TOC_RGB, Quantity_TOC_sRGB

from fdcad.ui.themes.theme import Palette

#: Multisample anti-aliasing samples. Drivers that cannot do it fall back to none.
MSAA_SAMPLES = 4
#: Samples where the screen and the graphics card allow it (D2820): thin lines are a
#: quarter to a third steadier than with four.
MSAA_SAMPLES_FINE = 8
#: The fine samples are for screen scales below this. From 150 percent up, lines are
#: one and a half pixels wide or more, and four samples draw them about as evenly as
#: eight do at 100 percent, while a view has 2.25 to 4 times the pixels to pay for.
MSAA_FINE_BELOW_SCALE = 1.5
#: What one sample of one pixel costs in graphics memory, in bytes: the kernel keeps
#: two smoothed buffers for a view (the scene, and what is drawn over it), each with 4
#: bytes of colour and 4 of depth. Measured on a real view: 48 bytes a pixel more than
#: no smoothing with 4 samples and 113 with 8 (tools/view_smoothing_measure.py).
MSAA_BYTES_PER_SAMPLE = 16
#: The fine samples may cost one view at most this share of the card's memory more
#: than four samples do. A card that does not tell its memory keeps four.
MSAA_FINE_CARD_SHARE = 1 / 16
#: Width of model edges and of the outline around the part, in device pixels at 100
#: percent; both grow with the display scale so they look the same on HiDPI screens.
EDGE_WIDTH = 1.0
#: The outline is the kernel's shell drawn behind the part. At 2 px the shell cut into
#: the faces beside it, which showed as a dot pattern between the turns of a thread; at
#: 1.5 px it stays clear of them and is still heavier than an edge (D2765).
SILHOUETTE_WIDTH = 1.5
#: Highlighted edges are thicker than plain ones, so selection does not rely on colour
#: alone (U1.4). Selection is the thickest. A highlighted face has its outline drawn
#: at the same width (D2764).
PRESELECTED_WIDTH = 2.5
SELECTED_WIDTH = 3.0
#: A highlighted face is a flat tint of the highlight colour over the lit face: the
#: colour is the same on every face, and the shading under it still shows (D2764).
HIGHLIGHT_TRANSPARENCY = 0.35
#: Size of the axis triad, as a part of the view height (small, in the corner: U6.7).
TRIAD_SCALE = 0.07
#: Margin around the part when the view fits it, as a part of the view. It keeps the
#: corner triad clear of the part at the default zoom.
FIT_MARGIN = 0.16


@dataclass(frozen=True)
class Light:
    """One light: kind, direction (camera space, for directional lights) and strength."""

    kind: str  # "ambient" or "directional"
    direction: tuple[float, float, float]
    strength: float


#: A key light from the upper left, a soft fill from the lower right and some ambient
#: (U6.3). The lights follow the camera, so every standard view gets the same look:
#: top faces brightest, then the left, then the right, and none flat black. The
#: strengths are set so the brightest face of a part in the isometric view has the
#: part's own colour, and a face straight toward the key light is not brighter than
#: that (D2760).
LIGHTS = (
    Light("ambient", (0.0, 0.0, 0.0), 0.60),
    Light("directional", (0.40, -0.62, -0.68), 0.78),
    Light("directional", (-0.55, 0.35, -0.76), 0.32),
)
#: The share of the ambient light a face gives back. The kernel's plain material takes
#: a quarter of a colour as its ambient colour and the whole colour as its diffuse one
#: (measured on screen: the side and top faces of a box differ as this predicts).
AMBIENT_SHARE = 0.25


def face_shade(normal: tuple[float, float, float]) -> float:
    """How bright a face is, as a part of its own colour (1 is the colour itself).

    ``normal`` is the face's unit normal in camera space: x to the right, y up and z
    toward the eye. The lights follow the camera, so this holds for every view.
    """
    total = 0.0
    for light in LIGHTS:
        if light.kind == "ambient":
            total += AMBIENT_SHARE * light.strength
            continue
        d = light.direction
        length = (d[0] * d[0] + d[1] * d[1] + d[2] * d[2]) ** 0.5
        toward = -(normal[0] * d[0] + normal[1] * d[1] + normal[2] * d[2]) / length
        total += light.strength * max(0.0, toward)
    return total


def colour(hex_colour: str) -> Quantity_Color:
    """A theme colour exactly as Qt paints it (sRGB), for lines and text in the view."""
    text = hex_colour.lstrip("#")[-6:]
    r, g, b = (int(text[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    return Quantity_Color(r, g, b, Quantity_TOC_sRGB)


def grey(value: float) -> Quantity_Color:
    """A light colour of one strength (linear RGB)."""
    return Quantity_Color(value, value, value, Quantity_TOC_RGB)


def smoothing_memory(pixels: int, samples: int) -> int:
    """Graphics memory, in bytes, of the smoothed buffers of a view of ``pixels``
    device pixels drawn with ``samples`` samples."""
    return MSAA_BYTES_PER_SAMPLE * max(0, samples) * max(0, pixels)


def msaa_samples(scale: float = 1.0, pixels: int = 0, card_bytes: int = 0) -> int:
    """How many smoothing samples a view draws with (D2820).

    ``scale`` is the screen scale, ``pixels`` the size of the view in device pixels and
    ``card_bytes`` the memory the graphics card says it has (0 when it does not say).
    Eight samples where they show and the card has room for them, four everywhere
    else: at 150 percent and up, on a card that does not tell its memory (most built
    in graphics), and for a view so large that the four extra samples would take more
    than a sixteenth of the card.
    """
    if scale >= MSAA_FINE_BELOW_SCALE or card_bytes <= 0 or pixels <= 0:
        return MSAA_SAMPLES
    extra = smoothing_memory(pixels, MSAA_SAMPLES_FINE) - smoothing_memory(pixels, MSAA_SAMPLES)
    return MSAA_SAMPLES_FINE if extra <= card_bytes * MSAA_FINE_CARD_SHARE else MSAA_SAMPLES


def parse_card_memory(text: str) -> int:
    """Bytes from the driver's words for its memory, such as ``4096 MiB``; 0 if unclear."""
    parts = text.split()
    if len(parts) != 2 or parts[1] != "MiB":
        return 0
    try:
        return max(0, int(float(parts[0]) * 1024 * 1024))
    except ValueError:
        return 0


def card_memory(view: object) -> int:
    """The memory the graphics card of a drawing view says it has, in bytes, or 0.

    The kernel reads it from the driver, which tells it on NVIDIA and AMD cards and
    not on most built in graphics. The Mac is not asked: its graphics memory is the
    machine's own, so it is no card with room of its own. Never raises.
    """
    import sys

    if sys.platform == "darwin":
        return 0
    try:
        from OCP.collections import (
            IndexedDataMap_TCollection_AsciiString_TCollection_AsciiString as Info,
        )
        from OCP.Graphic3d import Graphic3d_DiagnosticInfo_Memory
        from OCP.TCollection import TCollection_AsciiString

        found = Info()
        view.DiagnosticInformation(found, Graphic3d_DiagnosticInfo_Memory)  # type: ignore[attr-defined,unused-ignore]
        key = TCollection_AsciiString("GPU memory")
        if not found.Contains(key):
            return 0
        return parse_card_memory(found.FindFromKey(key).ToCString())
    except Exception:  # a driver that cannot answer must never stop the view
        return 0


def apply_rendering(view: object, samples: int = MSAA_SAMPLES) -> None:
    """Turn on multisampling, smooth lines and per pixel shading (U6.1).

    When the graphics card cannot multisample, the kernel quietly draws without it.
    """
    params = view.ChangeRenderingParams()  # type: ignore[attr-defined]
    params.NbMsaaSamples = samples
    params.IsAntialiasingEnabled = True  # smooth lines for edges and sketches
    view.SetShadingModel(Graphic3d_TOSM_FRAGMENT)  # type: ignore[attr-defined]


#: The kernel draws the triad ``TRIAD_SCALE`` times this many device pixels from the
#: left and bottom edges of the view, and its arrows 0.8 times that long.
TRIAD_UNIT_PX = 500.0
#: Height of the triad's letters, in pixels at 100 percent (the kernel's own size).
TRIAD_TEXT_HEIGHT = 16.0


def screen_scale(scale: float) -> float:
    """The factor a size given in pixels at 100 percent grows by on a screen of
    ``scale``. Never below 1: nothing is drawn finer than its number says."""
    return max(1.0, scale)


def show_triad(view: object, palette: Palette, scale: float = 1.0) -> None:
    """The axis triad in the lower left corner, in the theme's axis and text colours.

    It grows with the screen scale, letters and all, so it has one size on every
    screen (D2822). The kernel sizes it in device pixels; ``viewport/triad.py`` holds
    the same numbers for the click areas.
    """
    from OCP.Aspect import Aspect_TOTP_LEFT_LOWER
    from OCP.V3d import V3d_X, V3d_Y, V3d_Z, V3d_ZBUFFER

    grow = screen_scale(scale)
    view.ZBufferTriedronSetup(  # type: ignore[attr-defined]
        colour(palette.axis_x), colour(palette.axis_y), colour(palette.axis_z), 0.8, 0.06, 12
    )
    triad = view.Trihedron(True)  # type: ignore[attr-defined]
    if triad is not None:
        for axis in (V3d_X, V3d_Y, V3d_Z):
            triad.LabelAspect(axis).SetHeight(TRIAD_TEXT_HEIGHT * grow)
    view.TriedronDisplay(  # type: ignore[attr-defined]
        Aspect_TOTP_LEFT_LOWER, colour(palette.view_text), TRIAD_SCALE * grow, V3d_ZBUFFER
    )


def edge_width(scale: float) -> float:
    """Edge width in device pixels for a display scale."""
    return EDGE_WIDTH * max(1.0, scale)


#: Widths of the other lines of the view, in pixels at 100 percent. They grow with the
#: screen scale as the edges do, so a sketch is twice as heavy as an edge on every
#: screen (D2824). Sketches shown in the view, reference curves, the mark of a lost
#: pick and the preview of reference geometry:
SKETCH_WIDTH = 2.0
REFERENCE_WIDTH = 2.0
LOST_PICK_WIDTH = 2.0
PREVIEW_MARK_WIDTH = 2.0
#: Lines to pick from (a revolve axis) and the mark of a Select Other row:
CHOICE_WIDTH = 3.0
#: The shapes an error points at:
ERROR_WIDTH = 4.0
#: Curvature combs:
COMB_WIDTH = 1.0


def line_width(width: float, scale: float) -> float:
    """A line width given in pixels at 100 percent, in device pixels on a screen of
    ``scale`` (D2824)."""
    return width * screen_scale(scale)


def real_edges_only(context: object) -> None:
    """Draw nothing but real edges where the kernel draws a shape as lines (D2823).

    The kernel adds a curve across the middle of every curved face in each direction:
    a ring round a hole, a line along a fillet. They are no edges of the part, and in
    Wireframe they read as edges that are not there. With none, Wireframe shows the
    edges the shaded view draws on its faces. This is the setting of the context, for
    items with no line settings of their own; ``drop_face_curves`` is for the others.
    """
    from OCP.AIS import AIS_TOI_Both

    context.SetIsoNumber(0, AIS_TOI_Both)  # type: ignore[attr-defined]


def drop_face_curves(drawer: Prs3d_Drawer) -> None:
    """The same for one item (D2823). An item that was given a colour before it was
    shown has line settings of its own, with the kernel's one curve each way."""
    from OCP.Prs3d import Prs3d_IsoAspect

    drawer.SetUIsoAspect(Prs3d_IsoAspect(Quantity_Color(), Aspect_TOL_SOLID, 1.0, 0))
    drawer.SetVIsoAspect(Prs3d_IsoAspect(Quantity_Color(), Aspect_TOL_SOLID, 1.0, 0))


def bare_line_colour(palette: Palette) -> str:
    """The colour of a line with no face behind it: wireframe, the seen lines of the
    hidden line styles, a body shown as wireframe, the free edges of an open surface.

    It is the outline colour, the token that reads at 3:1 on both ends of the view in
    every theme. ``edge`` is for edges drawn on faces and cannot do both: no colour is
    3:1 on the grey part and on a dark view at once (D654, D2761).
    """
    return palette.silhouette


def style_part(drawer: Prs3d_Drawer, palette: Palette, scale: float = 1.0) -> None:
    """Edges in the theme's edge colour, and the outline around the part (U6.4).

    Lines with no face behind them take ``bare_line_colour``, which reads against the
    view. The kernel gives them the part's own colour, a pale grey that could not be
    seen on the light themes (D2761).
    """
    width = edge_width(scale)
    drawer.SetFaceBoundaryAspect(Prs3d_LineAspect(colour(palette.edge), Aspect_TOL_SOLID, width))
    bare = colour(bare_line_colour(palette))
    for setter in (
        "SetWireAspect",
        "SetLineAspect",
        "SetFreeBoundaryAspect",
        "SetUnFreeBoundaryAspect",
        "SetSeenLineAspect",
    ):
        getattr(drawer, setter)(Prs3d_LineAspect(bare, Aspect_TOL_SOLID, width))
    drop_face_curves(drawer)  # Wireframe draws real edges only (D2823)
    if not drawer.HasOwnShadingAspect():
        drawer.SetupOwnShadingAspect()
    aspect = drawer.ShadingAspect().Aspect()
    aspect.SetDrawSilhouette(True)
    aspect.SetEdgeColor(colour(palette.silhouette))
    aspect.SetEdgeWidth(SILHOUETTE_WIDTH * max(1.0, scale))


#: How far hidden edges move from the outline colour toward the background (TR13, D686).
HIDDEN_FADE = 0.4
#: Hidden edges are thinner than seen ones.
HIDDEN_WIDTH = 1.0


def hidden_line_colour(palette: Palette) -> str:
    """The outline colour faded toward the view background, as ``#rrggbb``. Hidden
    lines have no face behind them, so they start from the colour of the seen lines
    (D2761)."""
    line = bare_line_colour(palette).lstrip("#")[-6:]
    back = palette.viewport_top.lstrip("#")[-6:]
    mixed = [
        round(int(line[i : i + 2], 16) * (1 - HIDDEN_FADE) + int(back[i : i + 2], 16) * HIDDEN_FADE)
        for i in (0, 2, 4)
    ]
    return "#" + "".join(f"{c:02x}" for c in mixed)


def style_hidden_lines(
    drawer: Prs3d_Drawer, palette: Palette, scale: float = 1.0, solid: bool = False
) -> None:
    """Hidden edges as thin dashed lines in a lighter colour (Hidden Lines Visible, TR13),
    or solid ones when asked (TR212)."""
    line = Aspect_TOL_SOLID if solid else Aspect_TOL_DASH
    drawer.SetHiddenLineAspect(
        Prs3d_LineAspect(colour(hidden_line_colour(palette)), line, HIDDEN_WIDTH * max(1.0, scale))
    )


#: Pull of the highlight layer toward the camera, as the feature preview's (preview.py).
HIGHLIGHT_OFFSET_FACTOR = -1.0
HIGHLIGHT_OFFSET_UNITS = -4.0


def lift_highlight_layer(context: object) -> None:
    """Draw the kernel's Top layer, which holds highlights, a little nearer the camera
    than the part, so a highlight over a face never fights the face for depth (D1094).
    The layer keeps the part's depth, so parts in front still hide a highlight."""
    viewer = context.CurrentViewer()  # type: ignore[attr-defined]
    settings = viewer.ZLayerSettings(Graphic3d_ZLayerId_Top)
    offset = Graphic3d_PolygonOffset()
    offset.Mode = Aspect_POM_Fill
    offset.Factor = HIGHLIGHT_OFFSET_FACTOR
    offset.Units = HIGHLIGHT_OFFSET_UNITS
    settings.SetPolygonOffset(offset)
    viewer.SetZLayerSettings(Graphic3d_ZLayerId_Top, settings)


def style_highlights(context: object, palette: Palette, scale: float = 1.0) -> None:
    """Pre-selection and selection colours, thicker edges for both (U1.4, U6.5).

    A highlighted face is a flat tint with its outline drawn round it (D2764). Lit like
    the part, the highlight went brown on a face turned from the light, so one colour
    looked like several; flat, it is the theme's colour on every face.
    """
    kinds = {
        Prs3d_TypeOfHighlight.Prs3d_TypeOfHighlight_Dynamic: (palette.preselection, False),
        Prs3d_TypeOfHighlight.Prs3d_TypeOfHighlight_LocalDynamic: (palette.preselection, False),
        Prs3d_TypeOfHighlight.Prs3d_TypeOfHighlight_Selected: (palette.selection, True),
        Prs3d_TypeOfHighlight.Prs3d_TypeOfHighlight_LocalSelected: (palette.selection, True),
    }
    lift_highlight_layer(context)
    for kind, (hex_colour, selected) in kinds.items():
        drawer = context.HighlightStyle(kind)  # type: ignore[attr-defined]
        # In the part's own layer a selected face lay at the very depth of the face under
        # it, and the two fought over each pixel (D1094). Hover was in a layer with a
        # depth of its own, and a see-through face writes no depth, so the far side of a
        # tube showed through its near side in patches (D1095). In the Top layer both
        # keep the part's depth, a little nearer the camera.
        drawer.SetZLayer(Graphic3d_ZLayerId_Top)
        c = colour(hex_colour)
        width = (SELECTED_WIDTH if selected else PRESELECTED_WIDTH) * max(1.0, scale)
        drawer.SetColor(c)
        drawer.SetDisplayMode(1)  # shaded faces, not a wire outline only
        drawer.SetTransparency(HIGHLIGHT_TRANSPARENCY)
        drawer.SetupOwnShadingAspect()
        shading = drawer.ShadingAspect()
        shading.SetColor(c)
        shading.SetTransparency(HIGHLIGHT_TRANSPARENCY)
        shading.Aspect().SetShadingModel(Graphic3d_TOSM_UNLIT)
        for setter in ("SetWireAspect", "SetLineAspect", "SetFreeBoundaryAspect"):
            getattr(drawer, setter)(Prs3d_LineAspect(c, Aspect_TOL_SOLID, width))
        drawer.SetUnFreeBoundaryAspect(Prs3d_LineAspect(c, Aspect_TOL_SOLID, width))
        drawer.SetFaceBoundaryAspect(Prs3d_LineAspect(c, Aspect_TOL_SOLID, width))
        drawer.SetFaceBoundaryDraw(True)
        drawer.SetupOwnPointAspect()
        drawer.PointAspect().SetColor(c)
        drawer.PointAspect().SetScale(2.0 * max(1.0, scale))


# The rim: a second outline for highlights --------------------------------------------------

#: Width of the rim on each side of a highlight's outline, in pixels at 100 percent.
RIM_WIDTH = 1.0


def rim_colour(palette: Palette, highlight: str) -> str:
    """The colour of the thin line drawn beside the outline of a highlight (D2821).

    The selection and pre-selection colours are made to read on the view's ground, and
    a part can have any colour: burnt orange on a red part is weak. So the outline
    brings a sliver of ground with it: the plate colour (white in the light themes,
    black in the dark ones) or the view's text colour, whichever stands out more from
    ``highlight``. The outline then has the same strong neighbour on every part.
    """
    from fdcad.ui.themes import contrast

    return max(
        (plate_colour(palette), palette.view_text), key=lambda c: contrast.ratio(c, highlight)
    )


def rim_width(selected: bool, scale: float = 1.0) -> float:
    """Width of the line that makes the rim, in device pixels: it lies under the
    outline and shows ``RIM_WIDTH`` on each side of it."""
    outline = SELECTED_WIDTH if selected else PRESELECTED_WIDTH
    return (outline + 2.0 * RIM_WIDTH) * screen_scale(scale)


# See-through items -----------------------------------------------------------------------


def _linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _encoded(c: float) -> float:
    c = min(1.0, max(0.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _channels(hex_colour: str) -> tuple[float, float, float]:
    text = hex_colour.lstrip("#")[-6:]
    r, g, b = (_linear(int(text[i : i + 2], 16) / 255.0) for i in (0, 2, 4))
    return r, g, b


def _hex(channels: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{round(255 * _encoded(c)):02x}" for c in channels)


def lit(hex_colour: str, shade: float) -> str:
    """``hex_colour`` on a face that is ``shade`` times as bright as its colour (see
    ``face_shade``), as the view draws it."""
    r, g, b = _channels(hex_colour)
    return _hex((r * shade, g * shade, b * shade))


def seen_through(over: str, under: str, transparency: float) -> str:
    """The colour seen where an item of colour ``over``, see through by
    ``transparency`` (0 solid, 1 invisible), lies over the colour ``under``.

    The kernel mixes the two in linear light; pixels read from a real view match this
    to one step (D2825). So the see-through amounts are tested without a screen.
    """
    t = min(1.0, max(0.0, transparency))
    mixed = [(1.0 - t) * a + t * b for a, b in zip(_channels(over), _channels(under), strict=True)]
    return _hex((mixed[0], mixed[1], mixed[2]))


def colour_gap(a: str, b: str) -> float:
    """How different two colours look: their distance in CIE L*a*b* (about 2 is the
    least step an eye sees, 10 is plain). A see-through tint often has the brightness
    of what is under it, so a contrast ratio does not measure it."""

    def lab(hex_colour: str) -> tuple[float, float, float]:
        r, g, b = _channels(hex_colour)
        x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
        y = 0.2126 * r + 0.7152 * g + 0.0722 * b
        z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

        def f(t: float) -> float:
            return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

        return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))

    return float(sum((p - q) ** 2 for p, q in zip(lab(a), lab(b), strict=True)) ** 0.5)


# Text in the view ------------------------------------------------------------------------

#: The two names the kernel asks for when it draws text of its own: the default of a
#: text label, and the letters of the corner triad.
KERNEL_FONT_NAMES = ("serif", "courier")
#: Height of a value shown in the view, in pixels at 100 percent.
VALUE_TEXT_HEIGHT = 14.0


def use_ui_font(family: str) -> str:
    """Draw the kernel's own text (the triad's letters, plane names, values) in the
    window's font, so the view does not show a serif face of its own (U6.7, D2762).

    Returns the family used. When the kernel does not know ``family`` its own sans
    serif font is used, and when it has none nothing changes and "" is returned.
    """
    from OCP.collections import Sequence_TCollection_HAsciiString
    from OCP.Font import Font_FontMgr
    from OCP.TCollection import TCollection_AsciiString

    manager = Font_FontMgr.GetInstance_s()
    known = Sequence_TCollection_HAsciiString()
    manager.GetAvailableFontsNames(known)
    names = {known.Value(i).ToCString().lower() for i in range(1, known.Length() + 1)}
    chosen = family if family.lower() in names else ""
    if not chosen:
        fallback = Sequence_TCollection_HAsciiString()
        manager.GetFontAliases(fallback, TCollection_AsciiString("sans-serif"))
        for i in range(1, fallback.Length() + 1):
            name = fallback.Value(i).ToCString()
            if name.lower() in names:
                chosen = name
                break
    if not chosen:
        return ""
    for alias in KERNEL_FONT_NAMES:
        manager.RemoveFontAlias(TCollection_AsciiString(alias), TCollection_AsciiString(""))
        manager.AddFontAlias(TCollection_AsciiString(alias), TCollection_AsciiString(chosen))
    return chosen


def text_over_previews(context: object) -> None:
    """Draw the text layer after everything see through (D2763).

    The kernel draws the see-through items of several layers together when the layers
    share one depth, so a value in the text layer lay under the see-through feature
    preview and took its tint. A layer that clears the depth starts after them. The
    text layer has no depth test, so nothing else about it changes.
    """
    viewer = context.CurrentViewer()  # type: ignore[attr-defined]
    settings = viewer.ZLayerSettings(Graphic3d_ZLayerId_TopOSD)
    settings.SetClearDepth(True)
    viewer.SetZLayerSettings(Graphic3d_ZLayerId_TopOSD, settings)


def plate_colour(palette: Palette) -> str:
    """The plate behind a value in the view: the sketch editor's value plate, without
    its alpha (the kernel's plate is not see through)."""
    return "#" + palette.label_plate.lstrip("#")[-6:]


def style_value(label: object, palette: Palette, hex_colour: str, scale: float = 1.0) -> None:
    """A value shown in the view: the given colour on a plate, in the text layer, so it
    reads over the part, the preview and the drag arrow (D2763)."""
    from OCP.Aspect import Aspect_TODT_SUBTITLE

    label.SetColor(colour(hex_colour))  # type: ignore[attr-defined]
    label.SetColorSubTitle(colour(plate_colour(palette)))  # type: ignore[attr-defined]
    label.SetDisplayType(Aspect_TODT_SUBTITLE)  # type: ignore[attr-defined]
    label.SetHeight(VALUE_TEXT_HEIGHT * max(1.0, scale))  # type: ignore[attr-defined]
    label.SetZLayer(Graphic3d_ZLayerId_TopOSD)  # type: ignore[attr-defined]


def value_text(text: str) -> str:
    """``text`` with a space each side, so the plate has a margin round it."""
    return f" {text} "


#: Width of the origin's three axes, in pixels at 100 percent: a little heavier than
#: an edge, so the origin is found on a part full of edges.
ORIGIN_WIDTH = 1.5


def style_origin(item: object, palette: Palette, scale: float = 1.0) -> None:
    """The part origin (View > Origins) in the theme's axis colours, like the corner
    triad, with its letters in the view's text colour (D2766). The kernel's own are
    white lines and yellow letters, which the light themes hide."""
    from OCP.Prs3d import (
        Prs3d_DatumParts_Origin,
        Prs3d_DatumParts_XArrow,
        Prs3d_DatumParts_XAxis,
        Prs3d_DatumParts_YArrow,
        Prs3d_DatumParts_YAxis,
        Prs3d_DatumParts_ZArrow,
        Prs3d_DatumParts_ZAxis,
    )

    axes = (
        (Prs3d_DatumParts_XAxis, Prs3d_DatumParts_XArrow, palette.axis_x),
        (Prs3d_DatumParts_YAxis, Prs3d_DatumParts_YArrow, palette.axis_y),
        (Prs3d_DatumParts_ZAxis, Prs3d_DatumParts_ZArrow, palette.axis_z),
    )
    text = colour(palette.view_text)
    for axis, arrow, hex_colour in axes:
        c = colour(hex_colour)
        item.SetDatumPartColor(axis, c)  # type: ignore[attr-defined]
        item.SetDatumPartColor(arrow, c)  # type: ignore[attr-defined]
        item.SetTextColor(axis, text)  # type: ignore[attr-defined]
        # Setting a colour gives the item its own datum settings, so ask for them after.
        datum = item.Attributes().DatumAspect()  # type: ignore[attr-defined]
        datum.LineAspect(axis).SetWidth(ORIGIN_WIDTH * max(1.0, scale))
    item.SetDatumPartColor(Prs3d_DatumParts_Origin, text)  # type: ignore[attr-defined]
