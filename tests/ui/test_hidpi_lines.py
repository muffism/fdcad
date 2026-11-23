"""Lines on high resolution screens are 0.75 pt, not 1 pt, at a scale of 2 (D2874).

The owner found 1 pt edges too heavy on a Retina screen and chose 0.75 pt. Lines keep
their width at 100 percent and grow with three quarters of the screen scale above it.
"""

from __future__ import annotations

import pytest

from fdcad.ui.themes import theme
from fdcad.ui.viewport import look


def test_lines_keep_their_width_at_100_percent() -> None:
    assert look.line_scale(1.0) == 1.0
    assert look.line_scale(0.75) == 1.0  # never finer than at 100 percent
    assert look.edge_width(1.0) == look.EDGE_WIDTH == 1.0


def test_edges_are_0_75_pt_on_a_retina_screen() -> None:
    assert look.line_scale(2.0) == pytest.approx(1.5)
    assert look.edge_width(2.0) == pytest.approx(1.5)  # 0.75 pt at 2 px per pt
    assert look.edge_width(1.5) == pytest.approx(1.125)


def test_every_view_line_thins_the_same_way() -> None:
    from OCP.Prs3d import Prs3d_Drawer

    for scale in (1.0, 1.25, 1.5, 2.0, 3.0):
        grow = look.line_scale(scale)
        assert look.line_width(look.SKETCH_WIDTH, scale) == pytest.approx(look.SKETCH_WIDTH * grow)
        assert look.rim_width(True, scale) == pytest.approx(look.rim_width(True) * grow)
        drawer = Prs3d_Drawer()
        look.style_part(drawer, theme.LIGHT, scale)
        silhouette = drawer.ShadingAspect().Aspect().EdgeWidth()
        assert silhouette == pytest.approx(look.SILHOUETTE_WIDTH * grow)
