"""How the 3D view draws: lights, edges, highlights and view turns (UI_POLISH_SPEC U6).

The light and width rules are pure numbers and run everywhere. The checks that
need the kernel's viewer skip when it cannot open a display (Linux without X).
"""

from __future__ import annotations

import math
import re
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from fdcad.ui.themes import theme
from fdcad.ui.viewport import look
from fdcad.ui.viewport.views import STANDARD_VIEWS, TURN_MS, Vec3

# Lights --------------------------------------------------------------------------------


def _unit(v: Vec3) -> Vec3:
    n = math.sqrt(sum(c * c for c in v))
    return (v[0] / n, v[1] / n, v[2] / n)


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _shade(normal: Vec3, eye: Vec3, up: Vec3) -> float:
    """Brightness of a face of a plain part under ``look.LIGHTS`` (lights follow the camera),
    as a part of the face's own colour. ``look.face_shade`` holds the kernel's rule: a
    face gives back a quarter of the ambient light (D2760)."""
    z = _unit(eye)
    x = _unit(_cross(up, z))
    y = _cross(z, x)
    return look.face_shade((_dot(normal, x), _dot(normal, y), _dot(normal, z)))


_AXES: list[Vec3] = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]


@pytest.mark.parametrize("name", list(STANDARD_VIEWS))
def test_no_face_is_flat_black_or_blown_out(name: str) -> None:
    """U6.3: every face a standard view shows is lit, and none is pure white."""
    eye, up = STANDARD_VIEWS[name]
    for normal in _AXES:
        if _dot(normal, _unit(eye)) > 1e-6:  # faces toward the camera
            shade = _shade(normal, eye, up)
            assert 0.45 <= shade <= 1.0, (name, normal, shade)


def test_iso_view_shows_three_clearly_different_shades() -> None:
    """Top brightest, then the front, then the side, so a box reads as a solid."""
    eye, up = STANDARD_VIEWS["iso"]
    top, front, side = (_shade(n, eye, up) for n in ((0, 1, 0), (0, 0, 1), (1, 0, 0)))
    assert top > front > side
    assert min(top - front, front - side) >= 0.05


def test_lights_are_a_key_a_fill_and_some_ambient() -> None:
    kinds = [light.kind for light in look.LIGHTS]
    assert kinds.count("ambient") == 1 and kinds.count("directional") == 2
    key, fill = (light for light in look.LIGHTS if light.kind == "directional")
    assert key.strength > 2 * fill.strength
    for light in look.LIGHTS:
        assert all(abs(c) <= 1 for c in light.direction)


def test_edges_and_highlights_have_ordered_widths() -> None:
    """U1.4: a selected edge is thicker, so selection does not rely on colour alone."""
    assert look.SELECTED_WIDTH > look.PRESELECTED_WIDTH > look.EDGE_WIDTH
    assert look.SILHOUETTE_WIDTH > look.EDGE_WIDTH
    assert look.MSAA_SAMPLES >= 4
    assert look.edge_width(2.0) == 2 * look.edge_width(1.0)  # HiDPI keeps the look
    assert look.TRIAD_SCALE <= 0.08  # a small corner triad, clear of the part (U6.7)
    assert look.FIT_MARGIN > look.TRIAD_SCALE * 2


def test_theme_colours_reach_the_kernel_exactly() -> None:
    """Lines and text use sRGB, as Qt paints, so the view matches the panels."""
    from OCP.Quantity import Quantity_TOC_sRGB

    values = look.colour("#336699").Values(Quantity_TOC_sRGB)
    assert values == pytest.approx([0x33 / 255, 0x66 / 255, 0x99 / 255], abs=1e-3)
    assert look.colour("#80336699").Values(Quantity_TOC_sRGB) == pytest.approx(values)


# The widget, when the kernel's viewer can start ----------------------------------------


@pytest.fixture
def viewport(qapp: QApplication) -> Iterator[object]:
    if sys.platform.startswith("linux") and qapp.platformName() == "offscreen":
        import os

        if not os.environ.get("DISPLAY"):
            pytest.skip("the 3D viewer needs a display on Linux")
    from fdcad.ui.viewport.widget import ViewportWidget

    view = ViewportWidget()
    yield view
    view.deleteLater()


def _srgb(c: object) -> list[float]:
    from OCP.Quantity import Quantity_TOC_sRGB

    return list(c.Values(Quantity_TOC_sRGB))  # type: ignore[attr-defined]


@pytest.mark.parametrize("pal", [theme.LIGHT, theme.DARK])
def test_highlight_styles_follow_the_theme(viewport: object, pal: theme.Palette) -> None:
    from OCP.Prs3d import Prs3d_TypeOfHighlight as kind

    viewport.set_palette(pal)  # type: ignore[attr-defined]
    context = viewport._context  # type: ignore[attr-defined]
    for which, colour in (
        (kind.Prs3d_TypeOfHighlight_Dynamic, pal.preselection),
        (kind.Prs3d_TypeOfHighlight_LocalDynamic, pal.preselection),
        (kind.Prs3d_TypeOfHighlight_Selected, pal.selection),
        (kind.Prs3d_TypeOfHighlight_LocalSelected, pal.selection),
    ):
        style = context.HighlightStyle(which)
        assert _srgb(style.Color()) == pytest.approx(_srgb(look.colour(colour)), abs=1e-3)
        assert style.DisplayMode() == 1
    local = context.HighlightStyle(kind.Prs3d_TypeOfHighlight_LocalSelected)
    assert local.WireAspect().Aspect().LineWidth() == pytest.approx(look.SELECTED_WIDTH)


def test_a_selected_face_never_fights_the_face_under_it(viewport: object) -> None:
    # D1094: a selected cylinder was covered in blotches. Its highlight lay in the part's
    # own layer at the face's very depth; now it is in the Top layer, drawn nearer the
    # camera but still hidden by parts in front.
    from OCP.Graphic3d import Graphic3d_ZLayerId_Top
    from OCP.Prs3d import Prs3d_TypeOfHighlight as kind

    viewport.set_palette(theme.DARK)  # type: ignore[attr-defined]
    context = viewport._context  # type: ignore[attr-defined]
    # D1095: hover too; in a layer with its own depth the far side of a see-through
    # tube highlight showed through its near side.
    for which in (
        kind.Prs3d_TypeOfHighlight_Selected,
        kind.Prs3d_TypeOfHighlight_LocalSelected,
        kind.Prs3d_TypeOfHighlight_Dynamic,
        kind.Prs3d_TypeOfHighlight_LocalDynamic,
    ):
        assert context.HighlightStyle(which).ZLayer() == Graphic3d_ZLayerId_Top
    settings = context.CurrentViewer().ZLayerSettings(Graphic3d_ZLayerId_Top)
    assert settings.ToEnableDepthTest() and not settings.ToClearDepth()
    assert settings.PolygonOffset().Units < 0 and settings.PolygonOffset().Factor < 0


def test_part_gets_edges_and_an_outline(viewport: object) -> None:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

    viewport.set_palette(theme.DARK)  # type: ignore[attr-defined]
    viewport.show_part(BRepPrimAPI_MakeBox(10, 10, 10).Shape())  # type: ignore[attr-defined]
    # Without a native window the part waits; style a drawer the same way to check it.
    from OCP.AIS import AIS_Shape

    item = AIS_Shape(BRepPrimAPI_MakeBox(1, 1, 1).Shape())
    item.SetColor(look.colour(theme.DARK.face))
    look.style_part(item.Attributes(), theme.DARK)
    aspect = item.Attributes().ShadingAspect().Aspect()
    assert aspect.ToDrawSilhouette()
    assert _srgb(aspect.EdgeColor()) == pytest.approx(_srgb(look.colour(theme.DARK.silhouette)))
    edges = item.Attributes().FaceBoundaryAspect()
    assert _srgb(edges.Aspect().Color()) == pytest.approx(_srgb(look.colour(theme.DARK.edge)))


def test_view_turns_are_off_until_the_window_sets_them(viewport: object) -> None:
    assert viewport.turn_ms == 0  # type: ignore[attr-defined]
    done: list[bool] = []
    viewport._turn_to((0.0, 0.0, 1.0), (0.0, 1.0, 0.0), 250, lambda: done.append(True))  # type: ignore[attr-defined]
    assert done == [True]  # no 3D view yet: it turns (and finishes) at once


# The window wiring and the colour rule -------------------------------------------------


def test_window_turn_time_follows_reduce_motion(qapp: QApplication) -> None:
    from types import SimpleNamespace

    from fdcad.ui.main_window.window import MainWindow

    fake = SimpleNamespace(settings=SimpleNamespace(animations=True))
    assert MainWindow.view_turn_ms(fake) == TURN_MS  # type: ignore[arg-type]
    fake.settings.animations = False
    assert MainWindow.view_turn_ms(fake) == 0  # type: ignore[arg-type]
    assert 200 <= TURN_MS <= 300  # about 250 ms (U6.6)


#: Files that may write colours: the theme itself, the icon palette, and user data
#: (the appearance swatches a user picks from).
_ALLOWED = {
    "themes/theme.py",
    # Sample system contrast colours for tests and screenshots (TR378): system data.
    "themes/system_contrast.py",
    "icons/__init__.py",
    "appearance/panel.py",
    "bundle_check.py",
}
_HEX = re.compile(r"""["']#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?["']|QColor\(\s*\d""")


def test_widgets_take_every_colour_from_the_theme() -> None:
    """U1.6: no hex colour in a widget file, except user chosen data."""
    root = Path(__file__).resolve().parents[2] / "src" / "fdcad" / "ui"
    found = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if rel in _ALLOWED:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _HEX.search(line):
                found.append(f"{rel}:{number}: {line.strip()}")
    assert found == []


def test_select_shapes_highlights_only_the_picked_item(
    viewport: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D655: owners come from a decomposition, so only the face or edge lights up."""
    from OCP import StdSelect
    from OCP.AIS import AIS_Shape
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

    made: list[tuple[object, ...]] = []
    monkeypatch.setattr(StdSelect, "StdSelect_BRepOwner", lambda *a: made.append(a) or a)

    class Context:
        def ClearSelected(self, _update: bool) -> None:  # noqa: N802
            pass

        def AddOrRemoveSelected(self, _owner: object, _update: bool) -> None:  # noqa: N802
            pass

    box = BRepPrimAPI_MakeBox(1, 1, 1).Shape()
    monkeypatch.setattr(viewport, "_part", AIS_Shape(box))
    monkeypatch.setattr(viewport, "_context", Context())
    monkeypatch.setattr(viewport, "selected", lambda: [])
    viewport.select_shapes([box])  # type: ignore[attr-defined]
    assert made and made[0][2:] == (0, True)
