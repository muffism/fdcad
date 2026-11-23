"""Reference plane look in the 3D view (TOOL_SPEC T13, D121). Offscreen, no GPU."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.themes.theme import DARK, LIGHT, Palette
from fdcad.ui.viewport.plane_look import (
    FILL_TRANSPARENCY,
    PlaneState,
    label_anchor,
    label_corner,
    plane_state,
    plane_style,
)
from tests.ui.test_workflow import _folders, new_part, plane_id, window  # noqa: F401


def _lightness(color: str) -> float:
    r, g, b = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    return (max(r, g, b) + min(r, g, b)) / 2 / 255


def _saturation(color: str) -> int:
    r, g, b = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    return max(r, g, b) - min(r, g, b)


@pytest.mark.parametrize("palette", [LIGHT, DARK])
def test_colours_per_state(palette: Palette) -> None:
    normal = plane_style(palette, PlaneState.NORMAL)
    hover = plane_style(palette, PlaneState.HOVER)
    selected = plane_style(palette, PlaneState.SELECTED)
    assert normal.outline == palette.plane_outline
    assert hover.outline == palette.accent  # D111
    assert selected.outline == palette.selection
    for style in (normal, hover, selected):
        assert style.label == style.outline  # the label uses the outline colour
        assert style.fill == palette.plane_fill  # the fill stays light in every state
        assert 0.85 <= style.transparency <= 0.90
    # Smoke grey: no strong colour, a light fill.
    assert _saturation(palette.plane_outline) < 40 and _saturation(palette.plane_fill) < 40
    assert _lightness(palette.plane_fill) > 0.7
    assert len({normal.outline, hover.outline, selected.outline}) == 3
    assert normal.transparency == FILL_TRANSPARENCY


def test_dark_theme_has_its_own_plane_colours() -> None:
    assert DARK.plane_outline != LIGHT.plane_outline
    assert _lightness(DARK.plane_outline) > _lightness(LIGHT.plane_outline)  # reads on dark


def test_state_selection_wins_over_hover() -> None:
    assert plane_state("f2", None, set()) is PlaneState.NORMAL
    assert plane_state("f2", "f2", set()) is PlaneState.HOVER
    assert plane_state("f2", "f2", {"f2"}) is PlaneState.SELECTED
    assert plane_state("f3", "f2", {"f2"}) is PlaneState.NORMAL


def test_label_sits_inside_one_corner() -> None:
    u, v = label_corner(-50, 50, -50, 50)
    assert u == pytest.approx(-46.0) and v == pytest.approx(46.0)
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.gp import gp_Pln

    face = BRepBuilderAPI_MakeFace(gp_Pln(), -50, 50, -50, 50).Face()  # the XY plane
    x, y, z = label_anchor(face)
    assert (x, y, z) == pytest.approx((-46.0, 46.0, 0.0))


def test_a_plane_label_keeps_its_size_in_pixels() -> None:
    # IDEAS 65 (D2630): text that grew with the zoom would cover the part when zoomed in.
    from OCP.AIS import AIS_TextLabel

    label = AIS_TextLabel()
    label.SetZoomable(False)
    assert not label.Attributes().TextAspect().Aspect().IsTextZoomable()
    source = Path(__file__).resolve().parents[2] / "src" / "fdcad" / "ui" / "viewport" / "widget.py"
    assert "label.SetZoomable(False)" in source.read_text(encoding="utf-8")


def test_parallel_planes_put_their_labels_one_under_another() -> None:
    """IDEAS 65 (D2630): planes of the same size with the same axes had their labels at
    the same corner, so on the bike frame they sat on top of each other."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.gp import gp_Ax3, gp_Dir, gp_Pln, gp_Pnt

    from fdcad.ui.viewport.plane_look import LABEL_ROWS, label_rows

    def at(z: float, normal: tuple[float, float, float] = (0, 0, 1)) -> object:
        plane = gp_Pln(gp_Ax3(gp_Pnt(0, 0, z), gp_Dir(*normal)))
        return BRepBuilderAPI_MakeFace(plane, -50, 50, -50, 50).Face()

    faces = {"low": at(0), "high": at(10), "middle": at(5), "side": at(0, (1, 0, 0))}
    rows = label_rows(faces)
    assert rows == {"low": 0, "middle": 1, "high": 2, "side": 0}
    corners = {fid: label_anchor(face, rows[fid]) for fid, face in faces.items()}
    ys = sorted(round(corners[f][1], 6) for f in ("low", "middle", "high"))
    assert len(set(ys)) == 3  # three rows, apart on the screen when seen face on
    assert corners["low"] == pytest.approx((-46.0, 46.0, 0.0))  # row 0 is where it was
    assert label_corner(-50, 50, -50, 50, LABEL_ROWS) == label_corner(-50, 50, -50, 50)


def test_the_picker_gives_shown_parallel_planes_their_own_rows(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    from fdcad.core.document.model import Feature, Param, new_document
    from fdcad.ui.main_window.plane_pick import picker_faces, plane_names
    from fdcad.ui.session import DocumentSession
    from fdcad.ui.viewport.plane_look import label_rows

    doc = new_document()
    front = next(f.id for f in doc.features if f.name == "Front Plane")
    for k, d in enumerate((10.0, 20.0), start=1):
        doc.features.append(
            Feature(
                doc.new_feature_id(),
                "ref_plane",
                f"Plane {k}",
                params={"method": "offset", "distance": Param(f"{d:g}", d)},
                refs={"first": {"feature": front}},
            )
        )
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=30000):
        tab = window.add_session(session)
    faces = picker_faces(tab)
    names = plane_names(tab)
    rows = {names[fid]: row for fid, row in label_rows(faces).items()}
    assert {"Front Plane", "Plane 1", "Plane 2"} <= set(rows)
    assert len({rows["Front Plane"], rows["Plane 1"], rows["Plane 2"]}) == 3


def test_window_passes_names_and_selection(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = new_part(qtbot, window)
    calls: dict[str, object] = {}
    view = tab.viewport
    view.show_reference_planes = lambda faces, names: calls.update(shown=(set(faces), names))  # type: ignore[attr-defined]
    view.show_planes = lambda faces, names: calls.update(pick=(set(faces), names))  # type: ignore[attr-defined]
    view.set_selected_planes = lambda ids: calls.update(selected=ids)  # type: ignore[attr-defined]
    # The offscreen view is a plain label: lend it signals so the plane picker can connect.
    view.plane_picked = window.tree.currentItemChanged  # type: ignore[attr-defined,union-attr]
    view.selection_changed = window.tree.currentItemChanged  # type: ignore[attr-defined,union-attr]
    front = plane_id(tab, "Front Plane")
    assert window.tree is not None
    window.tree.select(front)
    assert calls["selected"] == {front}
    window.hide_or_show()
    faces, names = calls["shown"]  # type: ignore[misc]
    assert faces == {front} and names[front] == "Front Plane"
    window.tree.select(next(f.id for f in tab.session.document.features if f.name == "Origin"))
    assert calls["selected"] == set()
    assert window.sketch_mode is not None
    window.sketch_mode.picker.start(tab, lambda *_a: None)
    faces, names = calls["pick"]  # type: ignore[misc]
    assert {names[f] for f in faces} == {"Front Plane", "Top Plane", "Right Plane"}
    window.sketch_mode.picker.cancel()
