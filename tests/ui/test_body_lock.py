"""Lock a body (TR269, D836)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.body_visibility import locked_names, set_locked_names
from fdcad.core.document.model import new_document
from fdcad.core.features.solids import solids
from fdcad.core.io import fdef
from fdcad.ui import strings_phase3 as text3
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_display import _open
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def _menu_texts(window: MainWindow, index: int) -> list[str]:  # noqa: F811
    assert window.tree is not None
    return [a.text() for a in window.tree._body_menu(index).actions()]


def test_names_are_saved() -> None:
    doc = new_document()
    set_locked_names(doc, {"f2/top"})
    assert locked_names(fdef.loads(fdef.dumps(doc))) == {"f2/top"}


def test_lock_from_the_tree_and_undo(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    session = tab.session
    assert text3.LOCK_BODY in _menu_texts(window, 1)
    window.body_display.from_tree("lock", 1)
    report = session.report
    assert report is not None and report.body is not None
    (solid,) = tab.locked_solids()
    assert solid.IsSame(solids(report.body.shape)[1])
    texts = _menu_texts(window, 1)
    assert text3.UNLOCK_BODY in texts and text3.TRANSFORM_HANDLES not in texts
    session.undo.undo()
    assert tab.locked_solids() == []


def test_the_kernel_view_greys_and_refuses_picks(qtbot: QtBot) -> None:
    """With the kernel's view (skipped offscreen)."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer

    from fdcad.core.features.solids import compound
    from tests.ui.test_view_centre import _view

    view = _view(qtbot)
    a = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 10.0, 10.0, 10.0).Shape()
    b = BRepPrimAPI_MakeBox(gp_Pnt(20, 0, 0), 10.0, 10.0, 10.0).Shape()
    view.set_locked([b])
    view.show_part(compound([a, b]))
    assert view._part.CustomAspectsMap().IsBound(b)
    face_b = TopExp_Explorer(b, TopAbs_FACE).Current()
    face_a = TopExp_Explorer(a, TopAbs_FACE).Current()
    view.select_shapes([face_a, face_b])
    picked = view.selected()
    assert any(s.IsSame(face_a) for s in picked) and not any(s.IsSame(face_b) for s in picked)
