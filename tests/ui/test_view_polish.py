"""The 3D view polish of 2026-11-19 (docs/VIEW_REVIEW_2026-11-19.md, D2760 to D2767).

Every value the review changed is checked here as a number, a colour or a kernel
setting, so the tests run on the offscreen platform without a graphics card. The
last test reads pixels from a real view; it runs only when asked, on a screen.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from fdcad.ui.themes import contrast, theme
from fdcad.ui.viewport import look, plane_look
from fdcad.ui.viewport.views import STANDARD_VIEWS

PALETTES = [
    ("light", theme.LIGHT),
    ("beige", theme.BEIGE),
    ("dark", theme.DARK),
    ("stealth", theme.STEALTH),
]
ALL = pytest.mark.parametrize("pal", [p for _n, p in PALETTES], ids=[n for n, _p in PALETTES])


def _srgb(c: object) -> list[float]:
    from OCP.Quantity import Quantity_TOC_sRGB

    return list(c.Values(Quantity_TOC_sRGB))  # type: ignore[attr-defined]


def _same(c: object, hex_colour: str) -> bool:
    return _srgb(c) == pytest.approx(_srgb(look.colour(hex_colour)), abs=2e-3)


@pytest.fixture
def viewport(qapp: QApplication) -> Iterator[object]:
    if sys.platform.startswith("linux") and qapp.platformName() == "offscreen":
        if not os.environ.get("DISPLAY"):
            pytest.skip("the 3D viewer needs a display on Linux")
    from fdcad.ui.viewport.widget import ViewportWidget

    view = ViewportWidget()
    yield view
    view.deleteLater()


# D2760: a part is drawn in its own colour ------------------------------------------------


def test_part_colours_reach_the_kernel_as_srgb() -> None:
    """A red part was drawn salmon: its colour went to the kernel as linear RGB."""
    import inspect

    from fdcad.ui.print_tools import overlay
    from fdcad.ui.viewport import mirror_image, widget

    red = "#C0392B"
    assert _srgb(widget._hex(red)) == pytest.approx([0xC0 / 255, 0x39 / 255, 0x2B / 255], abs=2e-3)
    assert widget._srgb_hex is widget._hex
    # The analysis maps and the mirror image use the same function.
    for module in (overlay, mirror_image):
        assert "from fdcad.ui.viewport.widget import _hex" in inspect.getsource(module)
    # No colour of the view goes to the kernel as linear RGB any more.
    assert "Quantity_TOC_RGB)" not in inspect.getsource(widget).replace(
        "solid = Quantity_Color(value, value, value, Quantity_TOC_RGB)", ""
    )


def test_light_strengths() -> None:
    ambient, key, fill = look.LIGHTS
    assert (ambient.kind, ambient.strength) == ("ambient", 0.60)
    assert (key.kind, key.strength) == ("directional", 0.78)
    assert (fill.kind, fill.strength) == ("directional", 0.32)
    assert look.AMBIENT_SHARE == 0.25


def _camera(normal: tuple[float, float, float], name: str) -> tuple[float, float, float]:
    eye, up = STANDARD_VIEWS[name]

    def unit(v: tuple[float, float, float]) -> tuple[float, float, float]:
        n = math.sqrt(sum(c * c for c in v))
        return (v[0] / n, v[1] / n, v[2] / n)

    def cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, ...]:
        return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])

    z = unit(eye)
    x = unit(cross(up, z))  # type: ignore[arg-type]
    y = cross(z, x)  # type: ignore[arg-type]
    return tuple(sum(n * c for n, c in zip(normal, axis, strict=True)) for axis in (x, y, z))  # type: ignore[return-value]


def test_the_brightest_face_has_the_parts_own_colour() -> None:
    """The top face in the isometric view is close to the colour itself, and no face
    of any direction is brighter than the colour, so a white part keeps its shading."""
    top = look.face_shade(_camera((0.0, 1.0, 0.0), "iso"))
    assert 0.88 <= top <= 1.0
    highest = 0.0
    for i in range(0, 91, 2):
        for j in range(0, 360, 4):
            t, p = math.radians(i), math.radians(j)
            n = (math.sin(t) * math.cos(p), math.sin(t) * math.sin(p), math.cos(t))
            highest = max(highest, look.face_shade(n))
    assert highest <= 1.02


def test_a_face_turned_from_both_lights_keeps_the_ambient_share() -> None:
    assert look.face_shade((0.0, 0.0, -1.0)) == pytest.approx(
        look.AMBIENT_SHARE * look.LIGHTS[0].strength
    )


# D2761: lines on the bare view -----------------------------------------------------------


@ALL
def test_lines_with_no_face_behind_them_take_the_outline_colour(pal: theme.Palette) -> None:
    """Wireframe and the hidden line styles drew their lines in the part's pale grey."""
    from OCP.AIS import AIS_Shape
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

    item = AIS_Shape(BRepPrimAPI_MakeBox(1, 1, 1).Shape())
    item.SetColor(look.colour(pal.face))  # the kernel sets every line to this colour
    drawer = item.Attributes()
    look.style_part(drawer, pal, 2.0)
    for getter in (
        "WireAspect",
        "LineAspect",
        "FreeBoundaryAspect",
        "UnFreeBoundaryAspect",
        "SeenLineAspect",
    ):
        aspect = getattr(drawer, getter)().Aspect()
        assert _same(aspect.Color(), look.bare_line_colour(pal)), getter
        assert aspect.Width() == pytest.approx(look.edge_width(2.0))
    # Edges drawn on the faces keep the edge colour.
    assert _same(drawer.FaceBoundaryAspect().Aspect().Color(), pal.edge)
    # The outline colour is the one that reads against the view; the face colour is not.
    for end in (pal.viewport_top, pal.viewport_bottom):
        assert contrast.ratio(pal.silhouette, end) >= contrast.MARK


@ALL
def test_hidden_lines_fade_from_the_outline_colour_and_still_read(pal: theme.Palette) -> None:
    hidden = look.hidden_line_colour(pal)
    for end in (pal.viewport_top, pal.viewport_bottom):
        seen = contrast.ratio(pal.silhouette, end)
        faded = contrast.ratio(hidden, end)
        assert 2.5 <= faded < seen


#: Contrast of a line on the bare view against the top and the bottom of the view.
#: Before D2761 such a line had the ``edge`` colour in the dark themes: 1.55 and 1.17
#: in Dark, 1.27 and 1.56 in Stealth.
BARE_LINE_CONTRAST = {
    "light": (15.96, 10.58),
    "beige": (13.83, 9.93),
    "dark": (4.66, 8.45),
    "stealth": (5.57, 6.86),
}


@pytest.mark.parametrize("name", list(BARE_LINE_CONTRAST))
def test_lines_on_the_bare_view_read_at_three_to_one(name: str) -> None:
    """U1.3 and the open pair of D745: edges against the bare view. The view no longer
    draws them in ``edge``, which cannot read there in a dark theme."""
    pal = dict(PALETTES)[name]
    line = look.bare_line_colour(pal)
    assert line == pal.silhouette
    top = contrast.ratio(line, pal.viewport_top)
    bottom = contrast.ratio(line, pal.viewport_bottom)
    assert (round(top, 2), round(bottom, 2)) == BARE_LINE_CONTRAST[name]
    assert min(top, bottom) >= contrast.MARK


def test_body_wireframe_uses_the_outline_colour() -> None:
    """A body shown as wireframe on its own (TR216) sits on the bare view too."""
    import inspect

    from fdcad.ui.viewport.widget import ViewportWidget

    source = inspect.getsource(ViewportWidget._apply_body_modes)
    assert "look.bare_line_colour(self._palette)" in source
    assert "self._palette.edge" not in source


# D2762: text in the window's font -------------------------------------------------------


def _aliases(name: str) -> list[str]:
    from OCP.collections import Sequence_TCollection_HAsciiString
    from OCP.Font import Font_FontMgr
    from OCP.TCollection import TCollection_AsciiString

    found = Sequence_TCollection_HAsciiString()
    Font_FontMgr.GetInstance_s().GetFontAliases(found, TCollection_AsciiString(name))
    return [found.Value(i).ToCString().lower() for i in range(1, found.Length() + 1)]


def _known_fonts() -> list[str]:
    from OCP.collections import Sequence_TCollection_HAsciiString
    from OCP.Font import Font_FontMgr

    known = Sequence_TCollection_HAsciiString()
    Font_FontMgr.GetInstance_s().GetAvailableFontsNames(known)
    return [known.Value(i).ToCString() for i in range(1, known.Length() + 1)]


def test_the_kernels_own_text_uses_the_given_font() -> None:
    fonts = _known_fonts()
    if not fonts:
        pytest.skip("the kernel found no fonts on this machine")
    family = fonts[0]
    assert look.use_ui_font(family) == family
    for alias in look.KERNEL_FONT_NAMES:
        assert _aliases(alias) == [family.lower()]
    assert look.KERNEL_FONT_NAMES == ("serif", "courier")


def test_an_unknown_font_falls_back_to_sans_serif_or_changes_nothing() -> None:
    before = {alias: _aliases(alias) for alias in look.KERNEL_FONT_NAMES}
    used = look.use_ui_font("No Such Font 2760")
    if used:
        assert used.lower() in [f.lower() for f in _known_fonts()]
        for alias in look.KERNEL_FONT_NAMES:
            assert _aliases(alias) == [used.lower()]
    else:
        assert {alias: _aliases(alias) for alias in look.KERNEL_FONT_NAMES} == before


def test_the_view_sets_the_font_once(viewport: object) -> None:
    from fdcad.ui.viewport import widget

    assert widget._font_set


# D2763: values on a plate, over the preview ---------------------------------------------


@ALL
def test_a_value_sits_on_a_plate_in_the_text_layer(pal: theme.Palette) -> None:
    from OCP.AIS import AIS_TextLabel
    from OCP.Aspect import Aspect_TODT_SUBTITLE
    from OCP.Graphic3d import Graphic3d_ZLayerId_TopOSD

    label = AIS_TextLabel()
    look.style_value(label, pal, pal.accent, 2.0)
    text = label.Attributes().TextAspect()
    assert _same(text.Aspect().Color(), pal.accent)
    assert _same(text.Aspect().ColorSubTitle(), look.plate_colour(pal))
    assert text.Aspect().TextDisplayType() == Aspect_TODT_SUBTITLE
    assert text.Height() == pytest.approx(look.VALUE_TEXT_HEIGHT * 2.0)
    assert label.ZLayer() == Graphic3d_ZLayerId_TopOSD
    # The plate is the sketch editor's value plate without its alpha, and both colours
    # a value is drawn in read on it as text.
    plate = look.plate_colour(pal)
    assert plate.lstrip("#").lower() == pal.label_plate.lstrip("#")[-6:].lower()
    for colour in (pal.accent, pal.sketch_under):
        assert contrast.ratio(colour, plate) >= contrast.TEXT


def test_value_text_has_a_margin() -> None:
    assert look.value_text("40.00 mm") == " 40.00 mm "
    assert look.VALUE_TEXT_HEIGHT == 14.0


def test_the_preview_is_more_see_through_now_its_colour_is_true() -> None:
    from fdcad.ui.viewport.preview import PREVIEW_TRANSPARENCY

    assert PREVIEW_TRANSPARENCY == 0.70


def test_the_text_layer_is_drawn_after_see_through_previews(viewport: object) -> None:
    """A layer that clears the depth starts after the see-through items before it."""
    from OCP.Graphic3d import Graphic3d_ZLayerId_TopOSD

    viewer = viewport._context.CurrentViewer()  # type: ignore[attr-defined]
    settings = viewer.ZLayerSettings(Graphic3d_ZLayerId_TopOSD)
    assert settings.ToClearDepth()
    assert not settings.ToEnableDepthTest()


def test_the_three_kinds_of_value_use_the_plate() -> None:
    import inspect

    from fdcad.ui.viewport.widget import ViewportWidget

    for method in ("show_value_labels", "_show_callout", "show_labels"):
        source = inspect.getsource(getattr(ViewportWidget, method))
        assert "look.style_value(" in source, method
        assert "look.value_text(" in source, method


# D2764: highlights are a flat tint with an outline --------------------------------------


@pytest.mark.parametrize("pal", [theme.LIGHT, theme.DARK], ids=["light", "dark"])
def test_a_highlighted_face_is_a_flat_tint_with_its_outline(
    viewport: object, pal: theme.Palette
) -> None:
    from OCP.Graphic3d import Graphic3d_TOSM_UNLIT
    from OCP.Prs3d import Prs3d_TypeOfHighlight as kind

    assert look.HIGHLIGHT_TRANSPARENCY == 0.35
    viewport.set_palette(pal)  # type: ignore[attr-defined]
    context = viewport._context  # type: ignore[attr-defined]
    for which, colour, width in (
        (kind.Prs3d_TypeOfHighlight_Dynamic, pal.preselection, look.PRESELECTED_WIDTH),
        (kind.Prs3d_TypeOfHighlight_LocalDynamic, pal.preselection, look.PRESELECTED_WIDTH),
        (kind.Prs3d_TypeOfHighlight_Selected, pal.selection, look.SELECTED_WIDTH),
        (kind.Prs3d_TypeOfHighlight_LocalSelected, pal.selection, look.SELECTED_WIDTH),
    ):
        style = context.HighlightStyle(which)
        shading = style.ShadingAspect()
        assert shading.Aspect().ShadingModel() == Graphic3d_TOSM_UNLIT
        assert shading.Transparency() == pytest.approx(look.HIGHLIGHT_TRANSPARENCY)
        assert _same(shading.Color(), colour)
        assert style.FaceBoundaryDraw()
        boundary = style.FaceBoundaryAspect().Aspect()
        assert _same(boundary.Color(), colour)
        assert boundary.Width() == pytest.approx(width)


# D2765: the outline round the part -------------------------------------------------------


def test_outline_width() -> None:
    from OCP.Prs3d import Prs3d_Drawer

    assert look.SILHOUETTE_WIDTH == 1.5
    assert look.SILHOUETTE_WIDTH > look.EDGE_WIDTH == 1.0
    drawer = Prs3d_Drawer()
    look.style_part(drawer, theme.LIGHT, 2.0)
    aspect = drawer.ShadingAspect().Aspect()
    assert aspect.ToDrawSilhouette()
    assert aspect.EdgeWidth() == pytest.approx(look.SILHOUETTE_WIDTH * look.line_scale(2.0))


# D2766: planes and the origin ------------------------------------------------------------


def test_plane_outline_is_no_heavier_than_an_edge() -> None:
    assert plane_look.OUTLINE_WIDTH == 1.0
    assert plane_look.OUTLINE_WIDTH <= look.EDGE_WIDTH


def test_plane_outline_and_name_grow_with_the_screen(viewport: object) -> None:
    from OCP.AIS import AIS_Shape
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.gp import gp_Pln

    face = BRepBuilderAPI_MakeFace(gp_Pln(), -1.0, 1.0, -1.0, 1.0).Face()
    item = AIS_Shape(face)
    viewport._dpr = 2.0  # type: ignore[attr-defined]
    viewport._shown_planes = {"p": (face, item)}  # type: ignore[attr-defined]
    viewport._restyle_planes()  # type: ignore[attr-defined]
    outline = item.Attributes().FaceBoundaryAspect().Aspect()
    assert outline.Width() == pytest.approx(plane_look.OUTLINE_WIDTH * 2.0)
    assert _same(outline.Color(), viewport._palette.plane_outline)  # type: ignore[attr-defined]
    label = viewport._plane_label(face, "Front Plane")  # type: ignore[attr-defined]
    height = label.Attributes().TextAspect().Height()
    assert height == pytest.approx(plane_look.LABEL_HEIGHT * 2.0)
    viewport._shown_planes = {}  # type: ignore[attr-defined]


@ALL
def test_the_origin_has_the_triads_colours(pal: theme.Palette) -> None:
    from OCP.AIS import AIS_Trihedron
    from OCP.Geom import Geom_Axis2Placement
    from OCP.gp import gp_Ax2
    from OCP.Prs3d import (
        Prs3d_DatumParts_XArrow,
        Prs3d_DatumParts_XAxis,
        Prs3d_DatumParts_YArrow,
        Prs3d_DatumParts_YAxis,
        Prs3d_DatumParts_ZArrow,
        Prs3d_DatumParts_ZAxis,
    )

    item = AIS_Trihedron(Geom_Axis2Placement(gp_Ax2()))
    look.style_origin(item, pal, 2.0)
    datum = item.Attributes().DatumAspect()
    for axis, arrow, colour in (
        (Prs3d_DatumParts_XAxis, Prs3d_DatumParts_XArrow, pal.axis_x),
        (Prs3d_DatumParts_YAxis, Prs3d_DatumParts_YArrow, pal.axis_y),
        (Prs3d_DatumParts_ZAxis, Prs3d_DatumParts_ZArrow, pal.axis_z),
    ):
        assert _same(item.DatumPartColor(axis), colour)
        assert _same(item.DatumPartColor(arrow), colour)
        assert _same(datum.TextAspect(axis).Aspect().Color(), pal.view_text)
        assert datum.LineAspect(axis).Aspect().Width() == pytest.approx(
            look.ORIGIN_WIDTH * look.line_scale(2.0)
        )
    assert look.ORIGIN_WIDTH == 1.5


def test_the_view_styles_its_origin_and_restyles_it_with_the_theme(viewport: object) -> None:
    from OCP.Prs3d import Prs3d_DatumParts_XAxis

    viewport.set_palette(theme.LIGHT)  # type: ignore[attr-defined]
    viewport.set_origin_shown(True)  # type: ignore[attr-defined]
    origin = viewport._origin  # type: ignore[attr-defined]
    assert _same(origin.DatumPartColor(Prs3d_DatumParts_XAxis), theme.LIGHT.axis_x)
    viewport.set_palette(theme.DARK)  # type: ignore[attr-defined]
    assert _same(origin.DatumPartColor(Prs3d_DatumParts_XAxis), theme.DARK.axis_x)
    viewport.set_origin_shown(False)  # type: ignore[attr-defined]


# Unchanged on purpose -------------------------------------------------------------------


def test_what_the_review_left_alone() -> None:
    """Four samples of smoothing, 1 px edges, the highlight widths and the view's
    colours were judged right as they are. (Four is still the plain number; some views
    now draw with eight, D2820 and ``test_view_proposals.py``.)"""
    assert look.MSAA_SAMPLES == 4
    assert look.EDGE_WIDTH == 1.0
    assert (look.PRESELECTED_WIDTH, look.SELECTED_WIDTH) == (2.5, 3.0)
    assert (theme.LIGHT.viewport_top, theme.LIGHT.viewport_bottom) == ("#F4F6FA", "#C6CBD2")
    assert (theme.DARK.viewport_top, theme.DARK.viewport_bottom) == ("#414855", "#1B1E24")
    assert (theme.LIGHT.selection, theme.LIGHT.preselection) == ("#AD4200", "#00705F")
    assert (theme.DARK.selection, theme.DARK.preselection) == ("#FFD060", "#7FF0D0")


# Pixels, on a real screen only ----------------------------------------------------------


@pytest.mark.skipif(
    os.environ.get("FDCAD_VIEW_PIXELS") != "1" or sys.platform.startswith("linux"),
    reason="reads pixels from a real 3D view: set FDCAD_VIEW_PIXELS=1 on a screen",
)
def test_pixels_of_a_real_view() -> None:
    """A red box is red, wireframe lines read on the light view, and a selected face
    has the selection colour whichever way it faces."""
    probe = Path(__file__).with_name("view_pixels_probe.py")
    env = {k: v for k, v in os.environ.items() if k != "QT_QPA_PLATFORM"}
    done = subprocess.run(
        [sys.executable, str(probe)], capture_output=True, text=True, env=env, timeout=180
    )
    lines = [line for line in done.stdout.splitlines() if line.startswith("{")]
    assert lines, done.stdout + done.stderr
    seen = json.loads(lines[-1])

    def near(a: list[int], b: list[float], limit: float) -> bool:
        return max(abs(x - y) for x, y in zip(a, b, strict=True)) <= limit

    # The top face of a red box: the red itself, as bright as the lights make it.
    assert near(seen["red_top"], seen["red_top_expected"], 6), seen
    assert near(seen["grey_top"], seen["grey_top_expected"], 6), seen
    # Wireframe on the light view: the darkest pixel is a line that reads at 3:1.
    assert seen["wire_contrast_light"] >= contrast.MARK, seen
    assert seen["wire_contrast_dark"] >= contrast.MARK, seen
    # A selected face on top and one on the side differ only by the shading under them.
    top, side = seen["selected_top"], seen["selected_side"]
    assert max(abs(a - b) for a, b in zip(top, side, strict=True)) <= 45, seen
    for face in (top, side):
        assert face[0] > face[2] + 40, seen  # burnt orange: far more red than blue
