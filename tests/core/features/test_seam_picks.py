"""A picked seam edge is named in a warning (D1084).

A seam is where a round face meets itself. There is nothing to round or bevel there,
and the kernel leaves it out with no word: on a gearbox shaft a fillet of three
shoulders, one picked on the seam, rounded two and reported no problem.
"""

from __future__ import annotations

from typing import Any

from OCP.BRep import BRep_Tool
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopoDS import TopoDS

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.naming.names import NamedShape
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, new_document


def _cylinder() -> tuple[Document, str]:
    doc = new_document()
    s = Sketch()
    s.add_circle(0, 0, 10)
    return doc, add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 20.0)


def _picks(b: NamedShape) -> tuple[dict[str, Any], dict[str, Any]]:
    """References to the top circle and to the side's seam."""
    top = seam = None
    side = next(f for n, f in b.faces if "/side/" in n)
    explorer = TopExp_Explorer(b.shape, TopAbs_EDGE)
    while explorer.More():
        edge = TopoDS.Edge(explorer.Current())
        explorer.Next()
        if BRep_Tool.IsClosed_s(edge, TopoDS.Face(side)):
            seam = edge
        else:
            if BRep_Tool.Pnt_s(TopExp.FirstVertex_s(edge)).Z() > 19.0:
                top = edge
    assert top is not None and seam is not None
    a, b2 = reference_for(b, top), reference_for(b, seam)
    assert a is not None and b2 is not None
    return a, b2


def test_a_seam_among_fillet_picks_is_named() -> None:
    doc, ext = _cylinder()
    top, seam = _picks(body(rebuild(doc), ext))
    fid = doc.new_feature_id()
    params = {"fillet_type": "constant", "radius": Param("2", 2.0)}
    doc.features.append(
        Feature(fid, "fillet", "Round 1", params=params, refs={"edges": [top, seam]})
    )
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.WARNING
    found = [i for i in res.issues if i.code == "seam_edge"]
    assert found and found[0].highlight == [seam["name"]]
    assert "the seam of a round face" in found[0].message
    # Without the seam the same fillet has nothing to say.
    doc.features[-1].refs["edges"] = [top]
    assert rebuild(doc)[fid].state is FeatureState.OK


def test_a_chamfer_already_refuses_a_seam() -> None:
    doc, ext = _cylinder()
    top, seam = _picks(body(rebuild(doc), ext))
    fid = doc.new_feature_id()
    params = {"chamfer_type": "distance_distance", "distance": Param("1", 1.0)}
    doc.features.append(
        Feature(fid, "chamfer", "Bevel 1", params=params, refs={"edges": [top, seam]})
    )
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "only one face" in res.issues[0].message
