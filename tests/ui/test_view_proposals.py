"""The six proposals of the 3D view review (IDEAS item 83, D2820 to D2825).

P1 smoothing samples, P2 the rim of a highlight, P3 the triad grows with the screen,
P4 Wireframe draws real edges only, P5 line widths grow with the screen, P6 the
see-through amounts. Every value is checked as a number, a colour or a kernel setting,
so the tests run on the offscreen platform without a graphics card: where a kernel
item is needed the view gets a kernel view with no window, as in ``test_view_detect``.
The last tests read pixels and memory from a real view; they run only when asked, on
a screen.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from OCP.AIS import AIS_TOI_IsoU, AIS_TOI_IsoV, AIS_WireFrame
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
from OCP.TopExp import TopExp_Explorer
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from fdcad.ui.icons import ACCENT
from fdcad.ui.themes import contrast, theme
from fdcad.ui.viewport import look, mirror_image, regions, triad
from fdcad.ui.viewport import widget as widget_module
from fdcad.ui.viewport.preview import PREVIEW_TRANSPARENCY
from fdcad.ui.viewport.views import STANDARD_VIEWS

PALETTES = [
    ("light", theme.LIGHT, False),
    ("beige", theme.BEIGE, False),
    ("dark", theme.DARK, True),
    ("stealth", theme.STEALTH, True),
]
ALL = pytest.mark.parametrize(
    ("pal", "dark"), [(p, d) for _n, p, d in PALETTES], ids=[n for n, _p, _d in PALETTES]
)
MIB = 1024 * 1024
GIB = 1024 * MIB
#: The part colours the review asked about: near the burnt orange of the selection.
NEAR = {"red": "#C0392B", "orange": "#D9731A", "yellow": "#E3B81C"}
FRONT = ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0))
ISO = ((1.0, 1.0, 1.0), (0.0, 1.0, 0.0))
SCALES = pytest.mark.parametrize("scale", [1.0, 1.5, 2.0])


def _srgb(c: object) -> list[float]:
    from OCP.Quantity import Quantity_TOC_sRGB

    return list(c.Values(Quantity_TOC_sRGB))  # type: ignore[attr-defined]


def _same(c: object, hex_colour: str) -> bool:
    return _srgb(c) == pytest.approx(_srgb(look.colour(hex_colour)), abs=2e-3)


def _shapes(shape: Any, kind: Any) -> list[Any]:
    out = []
    explorer = TopExp_Explorer(shape, kind)
    while explorer.More():
        out.append(explorer.Current())
        explorer.Next()
    return out


class _Aimed:
    """The view's interactive context, with ``MoveTo`` at a pixel turned into a ray
    (picking at a pixel needs a window; picking along a ray does not)."""

    def __init__(self, context: Any) -> None:
        self.context = context
        self.ray = gp_Ax1(gp_Pnt(5, 5, 100), gp_Dir(0, 0, -1))

    def MoveTo(self, *_args: Any) -> Any:  # noqa: N802 (the kernel's name)
        return self.context.MoveTo(self.ray, _args[2], False)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.context, name)


@pytest.fixture
def view(qapp: QApplication) -> Iterator[Any]:
    """A 3D view with a kernel view and no window: items are made and styled, nothing
    is drawn."""
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        pytest.skip("the 3D viewer needs a display on Linux")
    from fdcad.ui.viewport.widget import ViewportWidget

    v = ViewportWidget()
    v._view = v._viewer.CreateView()
    v._context = _Aimed(v._context)
    yield v
    v.release()  # free the kernel view while the widget exists (D2780)
    v.deleteLater()


def _shades() -> dict[str, float]:
    """How bright the top, front and side face of a box are in the isometric view."""
    eye, up = STANDARD_VIEWS["iso"]
    n = math.sqrt(sum(c * c for c in eye))
    z = (eye[0] / n, eye[1] / n, eye[2] / n)
    x = (up[1] * z[2] - up[2] * z[1], up[2] * z[0] - up[0] * z[2], up[0] * z[1] - up[1] * z[0])
    n = math.sqrt(sum(c * c for c in x))
    x = (x[0] / n, x[1] / n, x[2] / n)
    y = (z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0])

    def shade(normal: tuple[float, float, float]) -> float:
        cam = tuple(sum(a * b for a, b in zip(normal, axis, strict=True)) for axis in (x, y, z))
        return look.face_shade(cam)  # type: ignore[arg-type]

    return {"top": shade((0, 1, 0)), "front": shade((0, 0, 1)), "side": shade((1, 0, 0))}


# P1 (D2820): eight samples where they show and the card has room ------------------------


def test_sample_numbers() -> None:
    assert (look.MSAA_SAMPLES, look.MSAA_SAMPLES_FINE) == (4, 8)
    assert look.MSAA_FINE_BELOW_SCALE == 1.5
    assert look.MSAA_BYTES_PER_SAMPLE == 16
    assert pytest.approx(1 / 16) == look.MSAA_FINE_CARD_SHARE


@pytest.mark.parametrize(
    ("scale", "pixels", "card", "samples"),
    [
        (1.0, 1_000_000, 4 * GIB, 8),  # this PC: a 1.0 megapixel view, a 4 GiB card
        (1.25, 1_000_000, 4 * GIB, 8),  # lines are as thin and as uneven as at 100
        (1.5, 1_000_000, 4 * GIB, 4),  # from 150 percent four samples are as even
        (2.0, 1_000_000, 4 * GIB, 4),
        (1.0, 1_000_000, 0, 4),  # a card that does not tell its memory
        (1.0, 0, 4 * GIB, 4),  # a view with no size yet
        (1.0, 1920 * 1080, 2 * GIB, 8),  # a whole Full HD screen on a 2 GiB card
        (1.0, 2560 * 1440, 2 * GIB, 4),  # more than a 2 GiB card has room for
        (1.0, 2560 * 1440, 4 * GIB, 8),
        (1.0, 3840 * 2160, 4 * GIB, 4),
        (1.0, 3840 * 2160, 8 * GIB, 8),
    ],
)
def test_samples_follow_scale_view_size_and_card(
    scale: float, pixels: int, card: int, samples: int
) -> None:
    assert look.msaa_samples(scale, pixels, card) == samples


def test_smoothing_memory_matches_what_was_measured() -> None:
    """On the review PC a view of 1416 by 728 pixels took 52 MiB more with 4 samples
    than with none and 119 MiB more with 8; one of 1176 by 597 took 31 and 77."""
    for pixels, four, eight in ((1416 * 728, 52, 119), (1176 * 597, 31, 77)):
        plain = look.smoothing_memory(pixels, 1)  # with no samples one plain buffer stays
        model4 = (look.smoothing_memory(pixels, 4) - plain) / MIB
        model8 = (look.smoothing_memory(pixels, 8) - plain) / MIB
        assert model4 == pytest.approx(four, abs=6)
        assert model8 == pytest.approx(eight, abs=9)
    assert look.smoothing_memory(1_000_000, 8) == 2 * look.smoothing_memory(1_000_000, 4)
    assert look.smoothing_memory(-5, 8) == 0


def test_the_fine_samples_never_take_more_than_their_share_of_the_card() -> None:
    for card in (1 * GIB, 2 * GIB, 4 * GIB, 8 * GIB, 24 * GIB):
        for pixels in range(100_000, 12_000_000, 150_000):
            samples = look.msaa_samples(1.0, pixels, card)
            extra = look.smoothing_memory(pixels, samples) - look.smoothing_memory(pixels, 4)
            assert extra <= card / 16


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("4096 MiB", 4096 * MIB),
        ("512 MiB", 512 * MIB),
        ("", 0),
        ("plenty", 0),
        ("4096", 0),
        ("4 GiB", 0),
        ("-3 MiB", 0),
    ],
)
def test_card_memory_words(text: str, value: int) -> None:
    assert look.parse_card_memory(text) == value


def test_card_memory_is_zero_when_the_view_cannot_say() -> None:
    assert look.card_memory(object()) == 0


def test_the_mac_is_not_asked_for_card_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    """Its graphics memory is the machine's own (PLAN 11.1: 8 GB in all)."""

    class Telling:
        def DiagnosticInformation(self, _found: object, _flags: object) -> None:  # noqa: N802
            raise AssertionError("the Mac's driver must not be asked")

    monkeypatch.setattr(sys, "platform", "darwin")
    assert look.card_memory(Telling()) == 0


class _Drawn:
    """Stands in for a kernel view that draws: it only keeps its rendering settings."""

    def __init__(self) -> None:
        self.params = SimpleNamespace(NbMsaaSamples=4, IsAntialiasingEnabled=True)
        self.redrawn = 0

    def ChangeRenderingParams(self) -> Any:  # noqa: N802
        return self.params

    def Redraw(self) -> None:  # noqa: N802
        self.redrawn += 1


@pytest.fixture
def plain_view(qapp: QApplication) -> Iterator[Any]:
    """A 3D view with no kernel view, as on the offscreen platform."""
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        pytest.skip("the 3D viewer needs a display on Linux")
    from fdcad.ui.viewport.widget import ViewportWidget

    v = ViewportWidget()
    yield v
    v.deleteLater()


def test_a_view_takes_the_samples_of_its_screen_and_card(
    plain_view: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    v = plain_view
    assert v._samples == 4 and not v._drawing
    v._apply_smoothing()  # nothing to do before the view draws
    monkeypatch.setattr(widget_module, "_CARD_MEMORY", [4 * GIB])
    monkeypatch.setattr(v, "view_pixels", lambda: (1400, 730))
    drawn = _Drawn()
    v._view, v._drawing, v._dpr = drawn, True, 1.0
    v._apply_smoothing()
    assert (v._samples, drawn.params.NbMsaaSamples) == (8, 8)
    v._dpr = 2.0  # the window moved to a screen at 200 percent
    v._apply_smoothing()
    assert (v._samples, drawn.params.NbMsaaSamples) == (4, 4)
    v._dpr = 1.0
    monkeypatch.setattr(widget_module, "_CARD_MEMORY", [0])  # built in graphics
    v._apply_smoothing()
    assert drawn.params.NbMsaaSamples == 4
    v._view = None  # so the fixture has no kernel view to free


def test_a_large_part_turns_without_samples_and_gets_its_own_back(
    plain_view: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    v = plain_view
    monkeypatch.setattr(widget_module, "_CARD_MEMORY", [4 * GIB])
    monkeypatch.setattr(v, "view_pixels", lambda: (1400, 730))
    drawn = _Drawn()
    v._view, v._drawing, v._dpr, v._large_part = drawn, True, 1.0, True
    v._apply_smoothing()
    v._simple_while_turning(True)
    assert drawn.params.NbMsaaSamples == 0
    v._dpr = 1.0
    v._apply_smoothing()  # a resize while turning keeps the view simple
    assert drawn.params.NbMsaaSamples == 0
    v._simple_while_turning(False)
    assert drawn.params.NbMsaaSamples == 8 and drawn.redrawn == 1
    v._view = None


def test_a_saved_picture_takes_the_samples_of_its_own_size(
    plain_view: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Save Image draws into buffers of the picture's size: a large picture must not
    take eight samples because the view on screen has them."""
    v = plain_view
    monkeypatch.setattr(widget_module, "_CARD_MEMORY", [4 * GIB])
    used: list[int] = []

    class Picture(_Drawn):
        def ToPixMap(self, _pixmap: object, _width: int, _height: int) -> bool:  # noqa: N802
            used.append(self.params.NbMsaaSamples)
            return False

    drawn = Picture()
    drawn.params.NbMsaaSamples = 8
    v._view = drawn
    assert v.render_image(800, 600) is None  # the stand in draws nothing
    assert v.render_image(8000, 6000) is None
    assert used == [8, 4] and drawn.params.NbMsaaSamples == 8
    drawn.params.NbMsaaSamples = 4  # a view at 200 percent
    v.render_image(800, 600)
    assert used[-1] == 4 and drawn.params.NbMsaaSamples == 4
    v._view = None


def test_the_card_is_asked_once(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[object] = []
    monkeypatch.setattr(widget_module, "_CARD_MEMORY", [])
    monkeypatch.setattr(look, "card_memory", lambda view: asked.append(view) or 2 * GIB)
    assert widget_module._card_memory("a") == 2 * GIB
    assert widget_module._card_memory("b") == 2 * GIB
    assert asked == ["a"]


# P2 (D2821): the rim of a highlight ------------------------------------------------------


@ALL
def test_the_rim_is_the_far_end_of_the_ground(pal: theme.Palette, dark: bool) -> None:
    for highlight in (pal.selection, pal.preselection):
        rim = look.rim_colour(pal, highlight)
        assert rim == look.plate_colour(pal) == ("#000000" if dark else "#FFFFFF")
        # The outline reads against its own rim, far above the 3:1 of a mark (U1.4).
        assert contrast.ratio(rim, highlight) >= 5.5


@ALL
@pytest.mark.parametrize("name", sorted(NEAR))
def test_a_highlight_reads_on_red_orange_and_yellow_parts(
    pal: theme.Palette, dark: bool, name: str
) -> None:
    """Burnt orange on a red part was 1.1:1. One of the two lines of a highlight, the
    outline or its rim, is now 3:1 or more against the part."""
    part = NEAR[name]
    for highlight in (pal.selection, pal.preselection):
        rim = look.rim_colour(pal, highlight)
        assert max(contrast.ratio(highlight, part), contrast.ratio(rim, part)) >= contrast.MARK


def test_what_the_outline_alone_gave_on_a_red_part() -> None:
    assert contrast.ratio(theme.LIGHT.selection, NEAR["red"]) < 1.2
    assert contrast.ratio(look.rim_colour(theme.LIGHT, theme.LIGHT.selection), NEAR["red"]) > 5


@ALL
def test_a_highlight_reads_on_a_part_of_any_brightness(pal: theme.Palette, dark: bool) -> None:
    """Greys from black to white, and the lit faces of the three near colours: the
    better of outline and rim is never under 2.4:1, and the two lines are 6:1 or more
    from each other, so the pair is seen where one line alone would be weak."""
    colours = [f"#{v:02x}{v:02x}{v:02x}" for v in range(0, 256, 5)]
    colours += [look.lit(c, s) for c in NEAR.values() for s in _shades().values()]
    for highlight in (pal.selection, pal.preselection):
        rim = look.rim_colour(pal, highlight)
        worst = min(max(contrast.ratio(highlight, c), contrast.ratio(rim, c)) for c in colours)
        assert worst >= 2.4, (highlight, worst)


def test_rim_widths() -> None:
    assert look.RIM_WIDTH == 1.0
    assert look.rim_width(True) == look.SELECTED_WIDTH + 2.0 == 5.0
    assert look.rim_width(False) == look.PRESELECTED_WIDTH + 2.0 == 4.5
    assert look.rim_width(True, 2.0) == 10.0
    assert look.rim_width(False, 0.5) == 4.5  # never finer than at 100 percent


def test_a_selected_face_gets_its_rim(view: Any) -> None:
    from OCP.PrsMgr import PrsMgr_TOP_AllView

    box = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    view.set_palette(theme.LIGHT)
    view.show_part(box, NEAR["red"])
    face, other = _shapes(box, TopAbs_FACE)[:2]
    assert view.rim.shapes("selected") == []
    view.select_shapes([face])
    item = view.rim._items["selected"]
    assert item is not None and view.rim.shapes("selected")[0].IsSame(face)
    assert view._context.IsDisplayed(item)
    manager = view._context.MainPrsMgr()
    assert manager.IsDisplayed(item, 0)  # as lines
    assert not manager.IsDisplayed(item, 1)  # not as faces
    assert item.Width() == pytest.approx(look.rim_width(True, view._dpr))
    colour = item.Attributes().WireAspect().Aspect().Color()
    assert _same(colour, "#FFFFFF")
    # Its outline only, also on a curved face, and no part in the hidden line pass.
    assert item.Attributes().UIsoAspect().Number() == 0
    assert item.Attributes().VIsoAspect().Number() == 0
    assert item.TypeOfPresentation3d() == PrsMgr_TOP_AllView
    # In the part's own layer: the kernel draws the highlight after it, on top.
    assert item.ZLayer() == view._part.ZLayer()
    # Two faces are one item; the dark themes rim in black.
    view.select_shapes([face, other])
    assert len(view.rim.shapes("selected")) == 2
    view.set_palette(theme.DARK)
    item = view.rim._items["selected"]
    assert _same(item.Attributes().WireAspect().Aspect().Color(), "#000000")
    view.clear_selection()
    assert view.rim._items["selected"] is None and view.rim.shapes("selected") == []


def test_an_edge_has_a_rim_and_a_vertex_has_none(view: Any) -> None:
    box = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    view.show_part(box, None)
    edge = _shapes(box, TopAbs_EDGE)[0]
    vertex = _shapes(box, TopAbs_VERTEX)[0]
    view.rim.set_selected([edge, vertex])
    assert len(view.rim.shapes("selected")) == 1
    view.rim.set_selected([vertex])
    assert view.rim._items["selected"] is None


def test_the_rim_follows_the_cursor(view: Any) -> None:
    box = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    view.show_part(box, None)
    view.filters = {"face"}
    view._activate()
    view._hover_pos = QPointF(10.0, 10.0)
    view._context.ray = gp_Ax1(gp_Pnt(5, 5, 100), gp_Dir(0, 0, -1))  # down on the top face
    view._hover()
    hovered = view.rim.shapes("hover")
    assert len(hovered) == 1 and hovered[0].ShapeType() == TopAbs_FACE
    item = view.rim._items["hover"]
    assert item.Width() == pytest.approx(look.rim_width(False, view._dpr))
    assert not view.rim.sync_hover()  # the same face: nothing to draw again
    view._context.ray = gp_Ax1(gp_Pnt(500, 500, 100), gp_Dir(0, 0, -1))  # off the part
    view._hover()
    assert view.rim.shapes("hover") == [] and view.rim._items["hover"] is None


def test_a_new_part_drops_the_rims_of_the_old_one(view: Any) -> None:
    box = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    view.show_part(box, None)
    view.select_shapes(_shapes(box, TopAbs_FACE)[:1])
    assert view.rim._items["selected"] is not None
    view.show_part(BRepPrimAPI_MakeBox(5.0, 5.0, 5.0).Shape(), None)
    assert view.rim._items == {"hover": None, "selected": None}


def test_the_split_panes_sync_the_rim_too() -> None:
    import inspect

    from fdcad.ui.viewport import view_pane

    assert "self.main.sync_hover_rim()" in inspect.getsource(view_pane)


# P3 (D2822): the triad grows with the screen ---------------------------------------------


def test_the_click_areas_use_the_kernels_numbers() -> None:
    assert pytest.approx(triad.OFFSET_PX) == look.TRIAD_SCALE * look.TRIAD_UNIT_PX
    assert triad.centre(1.0) == triad.CENTRE_PX == (34.5, 35.5)
    # The kernel cuts its offset to a whole pixel: 52 at 150 percent, not 52.5.
    assert triad.centre(1.5) == (51.5, 52.5)
    assert triad.centre(2.0) == (69.5, 70.5)
    assert triad.centre(0.5) == triad.CENTRE_PX  # never smaller than at 100 percent


@SCALES
def test_front_view_arrows_are_picked_at_every_scale(scale: float) -> None:
    h = 900.0
    from_left, from_bottom = triad.centre(scale)
    cx, cy = from_left, h - from_bottom
    length = triad.LENGTH_PX * scale
    assert triad.axis_at(cx + 0.8 * length, cy, h, *FRONT, scale) == "x"
    assert triad.axis_at(cx, cy - 0.8 * length, h, *FRONT, scale) == "y"
    assert triad.axis_at(cx + scale, cy + scale, h, *FRONT, scale) == "z"  # points at the eye
    # The room round an arrow grows too: 6 px beside it at 100 percent still picks it.
    assert triad.axis_at(cx + 0.5 * length, cy + 6.0 * scale, h, *FRONT, scale) == "x"
    assert triad.axis_at(cx + 0.5 * length, cy + 8.0 * scale, h, *FRONT, scale) is None
    assert triad.axis_at(cx + length + 8.0 * scale, cy, h, *FRONT, scale) is None
    assert triad.axis_at(cx + 0.77 * length, cy - 0.77 * length, h, *FRONT, scale) is None


@SCALES
def test_iso_view_arrows_are_picked_at_every_scale(scale: float) -> None:
    h = 700.0
    from_left, from_bottom = triad.centre(scale)
    cx, cy = from_left, h - from_bottom
    assert triad.axis_at(cx + 15 * scale, cy + 8.5 * scale, h, *ISO, scale) == "x"
    assert triad.axis_at(cx - 15 * scale, cy + 8.5 * scale, h, *ISO, scale) == "z"
    assert triad.axis_at(cx, cy - 18 * scale, h, *ISO, scale) == "y"


def test_a_click_meant_for_the_small_triad_misses_the_large_one() -> None:
    """At 200 percent the tip of the X arrow is 52 px from the centre, at 139 px from
    the left. The old areas ended 33 px from a centre at 34.5 px."""
    h = 800.0
    old_tip_x = triad.CENTRE_PX[0] + triad.LENGTH_PX
    assert triad.axis_at(old_tip_x, h - triad.CENTRE_PX[1], h, *FRONT) == "x"
    cx, from_bottom = triad.centre(2.0)
    tip = (cx + 2.0 * triad.LENGTH_PX, h - from_bottom)
    assert triad.axis_at(*tip, h, *FRONT, 2.0) == "x"
    assert triad.axis_at(*tip, h, *FRONT) is None  # the unscaled areas never reached it


@SCALES
def test_the_kernel_draws_the_triad_at_the_scale(view: Any, scale: float) -> None:
    from OCP.V3d import V3d_X, V3d_Y, V3d_Z

    look.show_triad(view._view, theme.LIGHT, scale)
    drawn = view._view.Trihedron(False)
    assert drawn.Scale() == pytest.approx(look.TRIAD_SCALE * scale)
    for axis in (V3d_X, V3d_Y, V3d_Z):
        assert drawn.LabelAspect(axis).Height() == pytest.approx(look.TRIAD_TEXT_HEIGHT * scale)
    offset = drawn.TransformPersistence().Offset2d()
    centre = triad.centre(scale)
    assert (offset.x() - 0.5, offset.y() + 0.5) == centre


def test_a_split_pane_shows_the_triad_at_its_scale() -> None:
    import inspect

    from fdcad.ui.viewport import view_pane

    assert "look.show_triad(view, self.main._palette, self._dpr)" in inspect.getsource(view_pane)


def test_the_view_asks_for_the_triad_at_its_scale(view: Any) -> None:
    view._dpr = 2.0
    view.set_palette(theme.LIGHT)
    assert view._view.Trihedron(False).Scale() == pytest.approx(look.TRIAD_SCALE * 2.0)
    # A click is turned into device pixels and tested at the same scale.
    view._view.SetProj(0.0, 0.0, 1.0)
    view._view.SetUp(0.0, 1.0, 0.0)
    view.resize(400, 300)
    cx, from_bottom = triad.centre(2.0)
    tip_x = (cx + 2.0 * triad.LENGTH_PX * 0.9) / 2.0
    y = view.height() - from_bottom / 2.0
    assert view._triad_axis(QPointF(tip_x, y)) == "x"
    assert view._triad_axis(QPointF(tip_x + 12.0, y)) is None


def test_a_screen_of_another_scale_restyles_the_view(
    view: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The window moved to a screen at 200 percent: the triad, the part's edges and
    the rim take the new scale."""
    monkeypatch.setattr(widget_module, "_CARD_MEMORY", [0])
    box = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    view.show_part(box, None)
    view.select_shapes(_shapes(box, TopAbs_FACE)[:1])
    view._window = SimpleNamespace(SetSize=lambda _w, _h: False)
    view._drawing = True
    monkeypatch.setattr(view, "devicePixelRatioF", lambda: 2.0)
    view._sync_size()
    assert view._dpr == 2.0
    assert view._view.Trihedron(False).Scale() == pytest.approx(look.TRIAD_SCALE * 2.0)
    edges = view._part.Attributes().FaceBoundaryAspect().Aspect()
    assert edges.Width() == pytest.approx(look.edge_width(2.0))
    assert view.rim._items["selected"].Width() == pytest.approx(look.rim_width(True, 2.0))
    view._window = None


# P4 (D2823): Wireframe draws real edges only ---------------------------------------------


def test_the_context_draws_no_curves_across_faces(plain_view: Any) -> None:
    context = plain_view._context
    assert context.IsoNumber(AIS_TOI_IsoU) == 0
    assert context.IsoNumber(AIS_TOI_IsoV) == 0


def test_the_kernel_draws_one_curve_each_way_unless_told() -> None:
    """What Wireframe showed: an item coloured before it is shown takes the kernel's
    own count, one curve each way across every curved face."""
    from OCP.AIS import AIS_Shape

    item = AIS_Shape(BRepPrimAPI_MakeCylinder(5.0, 20.0).Shape())
    item.SetColor(look.colour("#B4BCC4"))
    drawer = item.Attributes()
    assert (drawer.UIsoAspect().Number(), drawer.VIsoAspect().Number()) == (1, 1)
    look.drop_face_curves(drawer)
    assert (drawer.UIsoAspect().Number(), drawer.VIsoAspect().Number()) == (0, 0)


def test_style_part_drops_the_curves() -> None:
    from OCP.Prs3d import Prs3d_Drawer

    drawer = Prs3d_Drawer()
    look.style_part(drawer, theme.LIGHT)
    assert (drawer.UIsoAspect().Number(), drawer.VIsoAspect().Number()) == (0, 0)


def test_the_shown_part_and_its_line_items_have_real_edges_only(view: Any) -> None:
    from fdcad.core.features.solids import compound

    tube = BRepPrimAPI_MakeCylinder(5.0, 20.0).Shape()
    other = BRepPrimAPI_MakeBox(gp_Pnt(20, 0, 0), gp_Pnt(30, 10, 10)).Shape()
    both = compound([tube, other])
    view.set_body_modes([(other, "wireframe", 0.0)])
    view.show_part(both, None)
    view.set_style("wireframe")

    def curves(item: Any) -> tuple[int, int]:
        drawer = item.Attributes()
        return drawer.UIsoAspect().Number(), drawer.VIsoAspect().Number()

    assert curves(view._part) == (0, 0)
    assert view._part.DisplayMode() == AIS_WireFrame
    assert curves(view._body_wire) == (0, 0)  # a body shown as wireframe by itself
    view.show_isolate_others(tube, "wireframe")
    assert curves(view._isolate_others) == (0, 0)
    view.show_isolate_others(tube, "transparent")
    assert curves(view._isolate_others) == (0, 0)
    view.show_isolate_others(None, "hidden")


def test_wireframe_stays_a_still_drawing() -> None:
    """The outlines of curved faces are worked out again for every frame in the hidden
    line styles: 9 to 179 ms a frame on the sample parts, where Wireframe takes 2 ms.
    So Wireframe is not one of them."""
    assert widget_module.HIDDEN_LINE_STYLES == ("hidden_lines", "hidden_lines_visible")
    assert "wireframe" not in widget_module.HIDDEN_LINE_STYLES


@ALL
def test_wireframe_and_the_hidden_line_styles_share_their_lines(
    pal: theme.Palette, dark: bool
) -> None:
    """One colour and one width for a line with no face behind it, in all three."""
    from OCP.Prs3d import Prs3d_Drawer

    drawer = Prs3d_Drawer()
    look.style_part(drawer, pal, 2.0)
    look.style_hidden_lines(drawer, pal, 2.0)
    wire, seen = drawer.WireAspect().Aspect(), drawer.SeenLineAspect().Aspect()
    assert _same(wire.Color(), look.bare_line_colour(pal))
    assert _srgb(wire.Color()) == _srgb(seen.Color())
    assert wire.Width() == seen.Width() == pytest.approx(2.0)
    hidden = drawer.HiddenLineAspect().Aspect()
    assert _same(hidden.Color(), look.hidden_line_colour(pal))
    assert hidden.Width() == pytest.approx(look.HIDDEN_WIDTH * 2.0)


# P5 (D2824): line widths grow with the screen ---------------------------------------------


def test_line_width_numbers() -> None:
    assert look.SKETCH_WIDTH == look.REFERENCE_WIDTH == 2.0
    assert look.LOST_PICK_WIDTH == look.PREVIEW_MARK_WIDTH == 2.0
    assert (look.CHOICE_WIDTH, look.ERROR_WIDTH, look.COMB_WIDTH) == (3.0, 4.0, 1.0)
    assert look.line_width(2.0, 1.0) == 2.0
    assert look.line_width(2.0, 1.5) == 3.0
    assert look.line_width(3.0, 2.0) == 6.0
    assert look.line_width(2.0, 0.75) == 2.0  # never finer than at 100 percent
    # A sketch is twice as heavy as an edge on every screen.
    for scale in (1.0, 1.25, 1.5, 2.0, 3.0):
        assert look.line_width(look.SKETCH_WIDTH, scale) == 2.0 * look.edge_width(scale)


@pytest.mark.parametrize("scale", [1.0, 2.0])
def test_sketches_curves_and_marks_grow_with_the_screen(view: Any, scale: float) -> None:
    from fdcad.ui.print_tools import overlay

    view._dpr = scale
    box = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    view.show_part(box, None)
    line = BRepBuilderAPI_MakeEdge(gp_Pnt(0, 0, 0), gp_Pnt(10, 0, 0)).Edge()
    edges = _shapes(box, TopAbs_EDGE)
    view.show_sketches([line])
    assert view._sketches[0].Width() == pytest.approx(2.0 * scale)
    view.show_references([line])
    assert view._reference_items[0].Width() == pytest.approx(2.0 * scale)
    view.show_combs([line])
    assert view._comb_items[0].Width() == pytest.approx(1.0 * scale)
    view.show_lost(edges[0])
    assert view._ghost.Width() == pytest.approx(2.0 * scale)
    view.show_preview_marks(edges[1:2])
    assert view._preview_marks.Width() == pytest.approx(2.0 * scale)
    view.preview_shapes(edges[2:3])
    assert view._marked.Width() == pytest.approx(3.0 * scale)
    view.highlight(edges[3:4])
    assert view._highlight.Width() == pytest.approx(4.0 * scale)
    view.show_axis_choices({"a": line})
    assert view._axes["a"][1].Width() == pytest.approx(3.0 * scale)
    overlay.show_layer(view, "test", [line], "#C0392B")
    assert view.print_layer_items["test"][0].Width() == pytest.approx(2.0 * scale)
    overlay.show_layer(view, "test", [line], "#C0392B", width=3.0)
    assert view.print_layer_items["test"][0].Width() == pytest.approx(3.0 * scale)


def test_no_fixed_line_width_is_left_in_the_view() -> None:
    """Every width the view sets goes through ``look`` or the screen scale."""
    import inspect
    import re

    from fdcad.ui.print_tools import overlay
    from fdcad.ui.viewport import edge_look, rim

    for module in (widget_module, overlay, edge_look, mirror_image, rim):
        source = inspect.getsource(module)
        assert re.findall(r"SetWidth\(\s*[0-9.]+\s*\)", source) == [], module.__name__


# P6 (D2825): the see-through amounts ------------------------------------------------------


def test_the_kernel_mixes_in_linear_light() -> None:
    """Read from a real view: a picked region (45 percent see through) on the front
    face of the grey part, in Light, was (95, 107, 163) over a face of (136, 142, 148)."""
    front = _shades()["front"]
    mixed = look.seen_through(look.lit(ACCENT[False], front), "#888e94", 0.45)
    measured = (95, 107, 163)
    got = tuple(int(mixed[i : i + 2], 16) for i in (1, 3, 5))
    assert max(abs(a - b) for a, b in zip(got, measured, strict=True)) <= 3
    assert look.seen_through("#102030", "#C0D0E0", 1.0) == "#c0d0e0"
    assert look.seen_through("#102030", "#C0D0E0", 0.0) == "#102030"
    assert look.lit("#B4BCC4", 1.0) == "#b4bcc4"


def test_colour_gap() -> None:
    assert look.colour_gap("#808080", "#808080") == 0.0
    assert look.colour_gap("#000000", "#FFFFFF") == pytest.approx(100.0, abs=0.1)
    # A tint of the brightness of what is under it: no contrast, a plain colour gap.
    a, b = "#9eadce", "#abb3bb"
    assert contrast.ratio(a, b) < 1.1
    assert look.colour_gap(a, b) > 10


def test_region_amounts() -> None:
    assert regions.IDLE_TRANSPARENCY == 0.85
    assert regions.HOVER_TRANSPARENCY == 0.7
    assert regions.PICKED_TRANSPARENCY == 0.45
    assert regions.PICKED_HOVER_TRANSPARENCY == 0.3
    assert regions.region_transparency(False, False) == 0.85
    assert regions.region_transparency(True, True) == 0.3


def _region_steps(pal: theme.Palette, dark: bool, amounts: tuple[float, ...]) -> list[float]:
    """The smallest colour gap of each state of a region from the state before, over
    the three faces of the grey part: bare to idle, to hover, to picked, to both."""
    worst = [1000.0] * len(amounts)
    for shade in _shades().values():
        bare = look.lit(pal.face, shade)
        over = look.lit(ACCENT[dark], shade)
        states = [bare] + [look.seen_through(over, bare, t) for t in amounts]
        for i in range(len(amounts)):
            worst[i] = min(worst[i], look.colour_gap(states[i], states[i + 1]))
    return worst


@ALL
def test_each_state_of_a_region_is_a_plain_step(pal: theme.Palette, dark: bool) -> None:
    amounts = (
        regions.IDLE_TRANSPARENCY,
        regions.HOVER_TRANSPARENCY,
        regions.PICKED_TRANSPARENCY,
        regions.PICKED_HOVER_TRANSPARENCY,
    )
    assert min(_region_steps(pal, dark, amounts)) >= 5.5


def test_the_old_region_amounts_were_weak_in_the_dark_themes() -> None:
    idle, _hover, _picked, both = _region_steps(theme.DARK, True, (0.9, 0.7, 0.45, 0.35))
    assert idle < 4.0  # an idle region all but unseen
    assert both < 4.5  # the cursor over a picked region changed little


@ALL
def test_the_mirror_image_reads_on_the_view_and_needs_its_edges(
    pal: theme.Palette, dark: bool
) -> None:
    """Every face of the image stands off the view. Its faces do not stand off each
    other on the light themes, whatever the amount: so it is drawn with its edges."""
    assert mirror_image.MIRROR_TRANSPARENCY == 0.65
    shades = _shades()
    for ground in (pal.viewport_top, pal.viewport_bottom):
        faces = {
            name: look.seen_through(look.lit(pal.sketch_reference, s), ground, 0.65)
            for name, s in shades.items()
        }
        assert min(look.colour_gap(c, ground) for c in faces.values()) >= 9.0
        if not dark:
            for amount in (0.65, 0.5, 0.35):
                top, front = (
                    look.seen_through(look.lit(pal.sketch_reference, shades[n]), ground, amount)
                    for n in ("top", "front")
                )
                assert look.colour_gap(top, front) < 3.0


class _Context:
    def __init__(self) -> None:
        self.shown: list[Any] = []

    def Display(self, item: Any, _update: bool) -> None:  # noqa: N802
        self.shown.append(item)

    def Remove(self, item: Any, _update: bool) -> None:  # noqa: N802
        self.shown.remove(item)

    def Deactivate(self, _item: Any) -> None:  # noqa: N802
        pass


@pytest.mark.parametrize("scale", [1.0, 2.0])
def test_the_mirror_image_is_drawn_with_its_edges(scale: float) -> None:
    pal = theme.LIGHT
    fake = SimpleNamespace(
        _context=_Context(),
        _part_shape=BRepPrimAPI_MakeBox(10, 10, 10).Shape(),
        _palette=pal,
        _view=None,
        _dpr=scale,
    )
    image = mirror_image.MirrorImage(fake)  # type: ignore[arg-type]
    assert image.set_plane(((0, 0, 0), (1, 0, 0)))
    drawer = image.item.Attributes()
    assert drawer.FaceBoundaryDraw()
    edges = drawer.FaceBoundaryAspect().Aspect()
    assert _same(edges.Color(), pal.sketch_reference)
    assert edges.Width() == pytest.approx(look.edge_width(scale))
    assert image.item.Transparency() == pytest.approx(0.65, abs=0.01)


@ALL
def test_the_graph_ghost_keeps_its_amount(pal: theme.Palette, dark: bool) -> None:
    """Looked at again and kept: every face of a ghost stands off the view at both its
    ends, and the part shows through it."""
    assert PREVIEW_TRANSPARENCY == 0.70
    assert widget_module.PREVIEW_TRANSPARENCY == 0.70
    shades = _shades()
    for ground in (pal.viewport_top, pal.viewport_bottom):
        for shade in shades.values():
            ghost = look.seen_through(look.lit(ACCENT[dark], shade), ground, 0.70)
            assert look.colour_gap(ghost, ground) >= 12.0
    part = look.lit(pal.face, shades["top"])
    over = look.seen_through(look.lit(ACCENT[dark], shades["top"]), part, 0.70)
    assert 10.0 <= look.colour_gap(over, part) <= 25.0


# On a real screen only ---------------------------------------------------------------------

ON_SCREEN = pytest.mark.skipif(
    os.environ.get("FDCAD_VIEW_PIXELS") != "1" or sys.platform.startswith("linux"),
    reason="reads a real 3D view: set FDCAD_VIEW_PIXELS=1 on a screen",
)


@ON_SCREEN
@pytest.mark.parametrize("scale", ["1", "1.5", "2"])
def test_pixels_of_a_real_view(scale: str) -> None:
    probe = Path(__file__).with_name("view_proposals_probe.py")
    env = {k: v for k, v in os.environ.items() if k != "QT_QPA_PLATFORM"}
    env["QT_SCALE_FACTOR"] = scale
    done = subprocess.run(
        [sys.executable, str(probe)], capture_output=True, text=True, env=env, timeout=180
    )
    lines = [line for line in done.stdout.splitlines() if line.startswith("{")]
    assert lines, done.stdout + done.stderr
    seen = json.loads(lines[-1])
    grow = float(scale)
    assert seen["scale"] == pytest.approx(grow)
    # P1: the view draws with the samples the rule gives for this screen and card.
    assert seen["samples"] == seen["samples_asked"] == seen["samples_expected"], seen
    if grow >= look.MSAA_FINE_BELOW_SCALE:
        assert seen["samples"] == look.MSAA_SAMPLES
    # P3: the arrows reach as far at every scale, and every pixel of an arrow picks it.
    for axis in "xyz":
        drawn = seen["triad"][axis]
        assert 19.0 <= drawn["reach"] <= 24.0, seen  # of 26: the isometric view shortens
        assert drawn["picked"] >= 0.98, seen
    # P2: a walk across the outline of a selected face of a red box meets the rim.
    assert seen["rim_pixels"] >= 1, seen
    # P4: across the middle of a cylinder in Wireframe there is its seam, not a ring.
    assert seen["wire_mid_row_lines"] <= 0.1 * seen["wire_mid_row"], seen
    # P5: a sketch line is 2 px times the scale.
    assert seen["sketch_width"] == pytest.approx(2.0 * grow, rel=0.2), seen
    # P6: a picked region has the colour the model gives.
    gap = max(
        abs(a - b) for a, b in zip(seen["region_picked"], seen["region_expected"], strict=True)
    )
    assert gap <= 4, seen


@ON_SCREEN
def test_smoothing_cost_on_this_card() -> None:
    """Eight samples cost what the model says, and a frame of the nut and bolt stays
    far inside a sixtieth of a second (PLAN 11.2 budget 6)."""
    tool = Path(__file__).resolve().parents[2] / "tools" / "view_smoothing_measure.py"
    env = {k: v for k, v in os.environ.items() if k != "QT_QPA_PLATFORM"}
    results = {}
    settings = ("--sizes", "1440x900", "--frames", "120")
    for samples in ("4", "8"):
        done = subprocess.run(
            [sys.executable, str(tool), "--child", "--samples", samples, *settings],
            capture_output=True,
            text=True,
            env=env,
            timeout=600,
        )
        line = next((ln for ln in done.stdout.splitlines() if ln.startswith("RESULT ")), "")
        assert line, done.stdout + done.stderr
        results[samples] = json.loads(line[len("RESULT ") :])
    width, height = (int(n) for n in results["8"]["view"].split("x"))
    model = (
        look.smoothing_memory(width * height, 8) - look.smoothing_memory(width * height, 4)
    ) / MIB
    if results["8"]["gpu_used_mib"] >= 0 and results["4"]["gpu_used_mib"] >= 0:
        more = results["8"]["gpu_used_mib"] - results["4"]["gpu_used_mib"]
        # Other programs use the card too, so the figure moves by a few MiB.
        assert more <= 1.5 * model + 24, (more, model)
    assert results["8"]["frame_ms"] < 1000.0 / 60.0, results
    assert results["8"]["frame_p95_ms"] < 1000.0 / 30.0, results
