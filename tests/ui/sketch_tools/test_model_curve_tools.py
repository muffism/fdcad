"""Intersection Curves and Silhouette sketch tools (TR6, D759)."""

from __future__ import annotations

from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Line
from fdcad.core.sketch.model_curves import INTERSECTION, SILHOUETTE, intersection_curves, silhouette
from fdcad.core.sketch.profiles import SketchPlane
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.sketch_tools.model_curve_tools import IntersectionCurvesTool, SilhouetteTool
from tests.ui.sketch_tools.p2_helpers import edit_of
from tests.ui.test_main_window import _folders, window  # noqa: F401  (fixtures)

TOP = SketchPlane((0.0, 0.0, 5.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))


def _curves():  # type: ignore[no-untyped-def]
    box = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 20.0, 10.0, 10.0).Shape()
    return {INTERSECTION: intersection_curves(box, TOP), SILHOUETTE: silhouette(box, TOP)}


def test_commands_and_icons() -> None:
    from fdcad.ui.icons.audit import audit

    for cid in ("sketch.intersection_curves", "sketch.silhouette", "sketch.turned_outline"):
        assert BY_ID[cid].keys == () and audit(cid) == []


def test_add_intersection_curves_once() -> None:
    edit = edit_of()
    tool = IntersectionCurvesTool(edit)
    assert "Working out" in tool.prompt
    assert not tool.option_changed("add")
    assert "still being worked out" in tool.take_message()
    tool.model_curves = _curves()
    assert "Press Add Curves" in tool.prompt
    assert len(tool.preview().lines) >= 4
    assert tool.option_changed("add")
    assert "Added 4 curves" in tool.take_message()
    assert sum(isinstance(e, Line) for e in edit.sketch.entities.values()) == 4
    assert not tool.option_changed("add")  # the same curves again: nothing new
    assert "already in the sketch" in tool.take_message()
    edit.undo()
    assert not any(isinstance(e, Line) for e in edit.sketch.entities.values())


def test_silhouette_tool_and_an_empty_result() -> None:
    edit = edit_of()
    tool = SilhouetteTool(edit)
    tool.model_curves = _curves()
    assert tool.option_changed("add")
    assert sum(isinstance(e, Line) for e in edit.sketch.entities.values()) == 4
    from fdcad.core.sketch.curve_convert import ProjectedCurve

    empty = SilhouetteTool(edit_of())
    empty.model_curves = {SILHOUETTE: ProjectedCurve(SILHOUETTE, "Silhouette")}
    assert "no silhouette curves" in empty.prompt
    assert not empty.option_changed("add")
    assert "Move the sketch plane" in empty.take_message()


def test_silhouette_tool_says_why_there_are_no_curves() -> None:
    # D2635: a part whose mesh failed gave an empty outline with no word.
    from fdcad.core.sketch.curve_convert import ProjectedCurve

    problem = "Silhouette failed: the part's mesh is incomplete. Rebuild it and try again."
    tool = SilhouetteTool(edit_of())
    tool.model_curves = {SILHOUETTE: ProjectedCurve(SILHOUETTE, "Silhouette", problem=problem)}
    assert tool.prompt == problem
    assert not tool.option_changed("add")
    assert tool.take_message() == problem


def test_the_sketch_gets_the_curves_when_it_opens(qtbot: QtBot, window, monkeypatch) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    """In the app: a sketch on the Top Plane gets the turned outline when it opens, the
    silhouette only when the Silhouette tool asks for it (D2609) and the intersection
    curves only when Intersection Curves asks (D2683)."""
    from fdcad.core.sketch import model_curves
    from tests.ui.test_main_window import _open_plate
    from tests.ui.test_workflow import canvas_of, plane_id

    worked_out: list[object] = []
    real = model_curves.silhouette

    def counted(shape, plane):  # type: ignore[no-untyped-def]
        worked_out.append(plane)
        return real(shape, plane)

    monkeypatch.setattr(model_curves, "silhouette", counted)
    tab, _ext = _open_plate(qtbot, window)
    assert window.sketch_mode is not None
    window.sketch_mode.start(plane_id=plane_id(tab, "Top Plane"))
    canvas = canvas_of(window)
    qtbot.waitUntil(lambda: bool(canvas.model_curves), timeout=20000)
    assert set(canvas.model_curves) == {"turned"}
    assert not worked_out  # a threaded part took 28 s here, with the window held
    canvas.set_tool("intersection_curves")  # the cut along a thread took 8.3 s (D2683)
    qtbot.waitUntil(lambda: INTERSECTION in canvas.model_curves, timeout=20000)
    assert canvas.model_curves[INTERSECTION].pieces
    assert not worked_out
    canvas.set_tool("silhouette")
    qtbot.waitUntil(lambda: SILHOUETTE in canvas.model_curves, timeout=20000)
    assert len(worked_out) == 1
    assert canvas.model_curves[SILHOUETTE].pieces  # the plate seen from above
    assert canvas.tool is not None and canvas.tool.curve is not None  # type: ignore[attr-defined]
    canvas.set_tool("silhouette")  # picked again: already there, not worked out again
    assert len(worked_out) == 1
    window.sketch_mode.cancel()


def test_turned_outline_tool_adds_a_closed_profile() -> None:
    """TR319, D888."""
    from fdcad.core.sketch.turned import TURNED, turned_outline
    from fdcad.ui.sketch_tools.model_curve_tools import TurnedOutlineTool

    box = BRepPrimAPI_MakeBox(gp_Pnt(0, -5, -5), 20.0, 10.0, 10.0).Shape()
    edit = edit_of()
    tool = TurnedOutlineTool(edit)
    tool.model_curves = {TURNED: turned_outline(box, TOP)}
    assert tool.option_changed("add")
    assert sum(isinstance(e, Line) for e in edit.sketch.entities.values()) >= 4
