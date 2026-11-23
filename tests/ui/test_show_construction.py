"""Construction geometry after the sketch is closed (TR339, D1703)."""

from __future__ import annotations

from types import SimpleNamespace

from OCP.TopAbs import TopAbs_EDGE, TopAbs_VERTEX
from OCP.TopExp import TopExp_Explorer
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature, new_document
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.construction_refs import (
    reference_points,
    set_shows_construction,
    shows_construction,
)
from fdcad.core.sketch.model import Sketch, sketch_to_data
from fdcad.ui.main_window.sketch_mode import curve_sources
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import add_sketch_edges
from tests.ui.test_workflow import (  # noqa: F401  (fixtures)
    _folders,
    new_part,
    rectangle_sketch,
    window,
)


def _count(shape: object, kind: object) -> int:
    n = 0
    explorer = TopExp_Explorer(shape, kind)  # type: ignore[arg-type]
    while explorer.More():
        n += 1
        explorer.Next()
    return n


def _doc(on: bool) -> tuple[object, str]:
    doc = new_document()
    sk = Sketch()
    sk.add_line(0.0, 0.0, 20.0, 0.0)
    sk.add_line(0.0, 5.0, 20.0, 5.0, construction=True)
    sk.add_point(3.0, 9.0, construction=True)
    data = sketch_to_data(sk)
    set_shows_construction(data, on)
    front = next(f for f in doc.features if f.name == "Front Plane")
    feature = Feature(id="sk1", type="sketch", name="Sketch 1", data=data)
    feature.refs["plane"] = {"feature": front.id}
    doc.features.append(feature)
    later = Feature(id="sk2", type="sketch", name="Sketch 2", data=sketch_to_data(Sketch()))
    later.refs["plane"] = {"feature": front.id}
    doc.features.append(later)
    return doc, "sk1"


def test_the_tick_shows_construction_curves_and_points_in_the_part() -> None:
    for on, edges, vertices_extra in ((False, 1, 0), (True, 2, 1)):
        doc, sid = _doc(on)
        report = RebuildEngine().rebuild(doc)  # type: ignore[arg-type]
        add_sketch_edges(report, doc)  # type: ignore[arg-type]
        shape = report.sketch_edges[sid]
        assert _count(shape, TopAbs_EDGE) == edges
        # Two line ends per edge plus the free construction point.
        assert _count(shape, TopAbs_VERTEX) == 2 * edges + vertices_extra
        assert (sid in report.construction_edges) is on


def test_later_sketches_can_convert_the_construction_geometry() -> None:
    doc, sid = _doc(True)
    report = RebuildEngine().rebuild(doc)  # type: ignore[arg-type]
    add_sketch_edges(report, doc)  # type: ignore[arg-type]
    tab = SimpleNamespace(session=SimpleNamespace(report=report, document=doc))
    later = doc.features[-1]  # type: ignore[attr-defined]
    sources = curve_sources(tab, later)  # type: ignore[arg-type]
    assert [s[0] for s in sources] == [sid]
    off, _ = _doc(False)
    report = RebuildEngine().rebuild(off)  # type: ignore[arg-type]
    add_sketch_edges(report, off)  # type: ignore[arg-type]
    tab = SimpleNamespace(session=SimpleNamespace(report=report, document=off))
    assert curve_sources(tab, off.features[-1]) == []  # type: ignore[arg-type, attr-defined]


def test_construction_points_are_references_only_with_the_tick() -> None:
    sk = Sketch()
    normal = sk.add_point(1.0, 1.0)
    cons = sk.add_point(2.0, 2.0, construction=True)
    data = sketch_to_data(sk)
    assert reference_points(sk, data) == [normal]
    set_shows_construction(data, True)
    assert shows_construction(data)
    assert reference_points(sk, data) == [normal, cons]
    set_shows_construction(data, False)
    assert "show_construction" not in data


def test_tree_tick_is_one_undo_step(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = new_part(qtbot, window)
    sid = rectangle_sketch(qtbot, window, tab)
    session = tab.session
    tree = window.tree
    assert tree is not None
    menu = tree._context_menu(session, tree.item_for(sid))  # type: ignore[arg-type]
    assert menu is not None
    tick = next(a for a in menu.actions() if a.text() == "Show Construction in Part")
    assert tick.isCheckable() and not tick.isChecked()
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tick.trigger()
    assert shows_construction(session.document.feature(sid).data)
    session.undo.undo()
    assert not shows_construction(session.document.feature(sid).data)
