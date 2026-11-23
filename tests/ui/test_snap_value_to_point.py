"""A depth arrow snapped to a part vertex follows it (TR395, D2207)."""

from __future__ import annotations

from OCP.TopAbs import TopAbs_VERTEX
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from pytestqt.qtbot import QtBot

from fdcad.core.naming.select import reference_for
from fdcad.ui.property_panel.panel import PropertyPanel
from fdcad.ui.viewport.preview import FeaturePreview
from tests.ui.test_extrude_phase2_panel import _second, panel  # noqa: F401  (fixture)


def _top_vertex(body):  # type: ignore[no-untyped-def]
    ex = TopExp_Explorer(body.shape, TopAbs_VERTEX)
    best = None
    while ex.More():
        v = TopoDS.Vertex(ex.Current())
        if reference_for(body, v) is not None:
            from OCP.BRep import BRep_Tool

            z = BRep_Tool.Pnt_s(v).Z()
            if best is None or z > best[0]:
                best = (z, v)
        ex.Next()
    assert best is not None
    return best[1]


def test_a_snapped_vertex_becomes_up_to_vertex(
    qtbot: QtBot,
    panel: PropertyPanel,  # noqa: F811
) -> None:
    session, _ext, fid = _second(qtbot, "boss")
    report = session.report
    assert report is not None and report.body is not None
    panel.begin(session, session.document.feature(fid), is_new=False)
    preview = FeaturePreview()
    preview.session, preview._panel = session, panel
    vertex = _top_vertex(report.body)
    assert preview.snap_to("depth", vertex)
    assert panel.choices["end_condition"].currentData() == "up_to_vertex"
    result = panel.current_feature()
    assert result is not None
    assert result.params["end_condition"] == "up_to_vertex"
    assert result.refs["end"]["kind"] == "vertex"
    assert not preview.snap_to("angle", vertex)  # not a depth arrow


def test_only_a_blind_direction_links(
    qtbot: QtBot,
    panel: PropertyPanel,  # noqa: F811
) -> None:
    session, _ext, fid = _second(qtbot, "boss")
    report = session.report
    assert report is not None and report.body is not None
    panel.begin(session, session.document.feature(fid), is_new=False)
    box = panel.choices["end_condition"]
    box.setCurrentIndex(box.findData("mid_plane"))
    ref = reference_for(report.body, _top_vertex(report.body))
    assert ref is not None
    assert not panel.link_end("depth", ref)
    assert box.currentData() == "mid_plane"
