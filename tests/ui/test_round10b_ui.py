"""Regression tests for the round 10b bug hunt in the property panel (docs/BUG_HUNT.md)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature, Param
from fdcad.ui.property_panel.forms.base import REMEMBERED
from fdcad.ui.property_panel.panel import PropertyPanel
from tests.core.features.test_features import plate
from tests.ui.test_property_panel import _session


def _p(v: float) -> Param:
    return Param(f"{v:g}", v)


def test_a6_vertex_chamfer_with_three_distances_reopens_unequal(qtbot: QtBot) -> None:
    REMEMBERED.clear()
    doc, ext = plate()
    vertex = {"kind": "vertex", "name": f"vertex({ext}/cap/end|{ext}/side/e5|{ext}/side/e6)"}
    params = {"chamfer_type": "vertex", "distance": _p(1), "distance2": _p(2), "distance3": _p(3)}
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(fid, "chamfer", "Chamfer 1", params=params, refs={"vertices": [vertex]})
    )
    session = _session(qtbot, doc)
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    panel.begin(session, session.document.feature(fid), is_new=False)
    assert not panel.form.equal.isChecked()
    edited = panel.current_feature()
    assert edited is not None
    assert edited.params.get("equal") is not True
    assert edited.params["distance2"].value == 2 and edited.params["distance3"].value == 3


def test_a5_fillet_radius_rows_follow_their_edges(qtbot: QtBot) -> None:
    from fdcad.core.features.base import Fix
    from fdcad.core.features.modify import edges_of
    from fdcad.core.naming.select import reference_for
    from fdcad.core.rebuild.runner import rebuild
    from tests.core.features.test_features import body

    REMEMBERED.clear()
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    refs = [reference_for(b, e) for e in edges_of(b.face(f"{ext}/cap/end"))][:3]
    params = {"fillet_type": "constant", "radius": _p(2), "multiple_radius": True}
    params.update({"radius_1": _p(3), "radius_2": _p(1.5), "radius_3": _p(1)})
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, "fillet", "Fillet 1", params=params, refs={"edges": refs}))
    session = _session(qtbot, doc)
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    panel.begin(session, session.document.feature(fid), is_new=False)
    skip = {"feature": fid, "items": [refs[0]["name"]], "keys": ["edges"]}
    panel.form.apply_fix(Fix("skip", "skip_items", skip))
    edited = panel.current_feature()
    assert edited is not None
    radii = {k: v.value for k, v in edited.params.items() if k.startswith("radius_")}
    assert radii == {"radius_1": 1.5, "radius_2": 1.0}


def test_b6_thread_size_not_in_the_table_is_kept(qtbot: QtBot) -> None:
    from tests.core.features.test_cosmetic_thread import add_thread
    from tests.core.features.test_hole import add_hole, on_top

    REMEMBERED.clear()
    doc, ext, sk, top = on_top([(25, 25)])
    hole = add_hole(doc, sk, face=top, diameter=8.5, end_condition="through_all")
    from fdcad.core.naming.select import reference_for
    from fdcad.core.rebuild.runner import rebuild
    from tests.core.features.test_features import body

    b = body(rebuild(doc), hole)
    edge = reference_for(b, b.edge(f"edge({ext}/cap/end|{hole}/hole/e1/wall)"))
    for size in ("D10x1.5", ""):
        fid = add_thread(doc, edge, size=size)
        session = _session(qtbot, doc)
        panel = PropertyPanel()
        qtbot.addWidget(panel)
        panel.begin(session, session.document.feature(fid), is_new=False)
        edited = panel.current_feature()
        assert edited is not None
        assert edited.params["size"] == size
        doc.features.pop()
