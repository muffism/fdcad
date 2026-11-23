"""Edge display options (TR212, D1602)."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from OCP.AIS import AIS_Shape
from OCP.Aspect import Aspect_TOL_DASH, Aspect_TOL_SOLID
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.GeomAbs import GeomAbs_C0, GeomAbs_CN
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from fdcad.ui.preferences.view_options import ViewOptions
from fdcad.ui.preferences.view_page import ViewPage
from fdcad.ui.themes import theme
from fdcad.ui.viewport import look


def _rounded() -> object:
    box = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
    maker = BRepFilletAPI_MakeFillet(box)
    maker.Add(2.0, TopoDS.Edge(TopExp_Explorer(box, TopAbs_EDGE).Current()))
    return maker.Shape()


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


def test_options_default_and_round_trip(tmp_path: Path, qapp: QApplication) -> None:
    store = QSettings(str(tmp_path / "p.ini"), QSettings.Format.IniFormat)
    options = ViewOptions(store)
    assert (options.smooth_edges, options.hidden_edges, options.feature_edges) == (
        "shown",
        "dashed",
        False,
    )
    store.setValue("view/smooth_edges", "odd")
    assert options.smooth_edges == "shown"
    page = ViewPage(store)
    page.smooth_box.setCurrentIndex(page.smooth_box.findData("dashed"))
    page.hidden_box.setCurrentIndex(page.hidden_box.findData("solid"))
    page.feature_edges_box.setChecked(True)
    page.apply(store)
    assert (options.smooth_edges, options.hidden_edges, options.feature_edges) == (
        "dashed",
        "solid",
        True,
    )


def test_hidden_edges_can_be_solid() -> None:
    item = AIS_Shape(BRepPrimAPI_MakeBox(1, 1, 1).Shape())
    look.style_hidden_lines(item.Attributes(), theme.LIGHT)
    assert item.Attributes().HiddenLineAspect().Aspect().Type() == Aspect_TOL_DASH
    look.style_hidden_lines(item.Attributes(), theme.LIGHT, solid=True)
    assert item.Attributes().HiddenLineAspect().Aspect().Type() == Aspect_TOL_SOLID


def test_removed_smooth_edges_leave_the_face_boundaries(viewport: object) -> None:
    edges = viewport.edge_look  # type: ignore[attr-defined]
    viewport._part_shape = _rounded()  # type: ignore[attr-defined]
    item = AIS_Shape(viewport._part_shape)  # type: ignore[attr-defined]
    edges.style(item.Attributes())
    assert item.Attributes().FaceBoundaryUpperContinuity() == GeomAbs_CN
    edges.smooth = "removed"
    edges.style(item.Attributes())
    assert item.Attributes().FaceBoundaryUpperContinuity() == GeomAbs_C0
    assert len(edges.smooth_edges()) == 2


def test_set_edge_options_and_feature_edges_do_not_fail_without_a_window(
    viewport: object,
) -> None:
    viewport.set_edge_options("dashed", "solid")  # type: ignore[attr-defined]
    assert viewport.edge_look.smooth == "dashed"  # type: ignore[attr-defined]
    assert viewport.edge_look.hidden == "solid"  # type: ignore[attr-defined]
    from fdcad.core.edge_display import edges_of

    box = BRepPrimAPI_MakeBox(1, 1, 1).Shape()
    face = TopExp_Explorer(box, TopAbs_FACE).Current()
    viewport.show_feature_edges(edges_of([face]))  # type: ignore[attr-defined]
    assert viewport.edge_look._feature_item is not None  # type: ignore[attr-defined]
    viewport.show_feature_edges([])  # type: ignore[attr-defined]
    assert viewport.edge_look._feature_item is None  # type: ignore[attr-defined]
