"""See through for one body (TR21, D753)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.body_visibility import see_through_names, set_see_through_names
from fdcad.core.document.model import new_document
from fdcad.core.features.solids import solids
from fdcad.core.io import fdef
from fdcad.ui import strings_phase3 as text3
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_display import _body_row, _open
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def test_names_are_saved_in_the_appearance() -> None:
    doc = new_document()
    assert see_through_names(doc) == set()
    set_see_through_names(doc, {"f3/side/2", "f2/top"})
    assert doc.appearance["see_through_bodies"] == ["f2/top", "f3/side/2"]
    assert see_through_names(fdef.loads(fdef.dumps(doc))) == {"f2/top", "f3/side/2"}
    set_see_through_names(doc, set())
    assert "see_through_bodies" not in doc.appearance


def _menu_texts(window: MainWindow, index: int) -> list[str]:  # noqa: F811
    assert window.tree is not None
    return [a.text() for a in window.tree._body_menu(index).actions()]


def test_body_row_menu_makes_one_body_see_through(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = _open(qtbot, window)
    session = tab.session
    assert text3.SEE_THROUGH_BODY in _menu_texts(window, 1)
    assert tab.see_through_solids() == []
    window.body_display.from_tree("see_through", 1)
    report = session.report
    assert report is not None and report.body is not None
    (solid,) = tab.see_through_solids()
    assert solid.IsSame(solids(report.body.shape)[1])
    assert session.is_dirty  # saved in the part, on the undo list
    assert session.undo.undoText() == text3.SEE_THROUGH_ONE_UNDO.format(index=2)
    assert text3.SOLID_BODY in _menu_texts(window, 1)  # the item now turns it back
    assert text3.SEE_THROUGH_BODY in _menu_texts(window, 0)
    window.body_display.from_tree("solid", 1)
    assert tab.see_through_solids() == []
    session.undo.undo()
    assert len(tab.see_through_solids()) == 1
    session.undo.undo()
    assert tab.see_through_solids() == []


def test_a_hidden_body_has_no_see_through_item(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    _open(qtbot, window)
    window.body_display.from_tree("hide", 1)
    texts = _menu_texts(window, 1)
    assert text3.SEE_THROUGH_BODY not in texts and text3.SOLID_BODY not in texts


def test_the_view_gets_the_see_through_bodies(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = _open(qtbot, window)
    got: list[list[object]] = []
    tab.viewport.set_see_through = got.append  # type: ignore[attr-defined]
    window.body_display.from_tree("see_through", 0)
    assert got and len(got[-1]) == 1
    _body_row(window, 0)  # the row is still there


def test_the_kernel_view_draws_one_body_see_through(qtbot: QtBot) -> None:
    """With the kernel's view (skipped offscreen): one solid of a compound gets its own
    transparency, the other stays solid."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt

    from fdcad.core.features.solids import compound
    from tests.ui.test_view_centre import _view

    view = _view(qtbot)
    a = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 10.0, 10.0, 10.0).Shape()
    b = BRepPrimAPI_MakeBox(gp_Pnt(20, 0, 0), 10.0, 10.0, 10.0).Shape()
    view.set_see_through([b])
    view.show_part(compound([a, b]))
    aspects = view._part.CustomAspectsMap()
    assert aspects.Size() == 1 and aspects.IsBound(b) and not aspects.IsBound(a)
