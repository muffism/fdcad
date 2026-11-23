"""Round Corners (TR64 item 2, D1801): where three rounded edges meet, the corner is a
smooth blend that joins each round without a crease."""

from __future__ import annotations

from OCP.BRep import BRep_Tool
from OCP.GeomAbs import GeomAbs_C0
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS

from fdcad.core.occ import ShapeListMap, shape_list
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, plate
from tests.core.features.test_fillet import add_fillet


def test_three_rounds_meet_in_a_smooth_corner_blend() -> None:
    doc, ext = plate()
    fid = add_fillet(doc, 1.0, features=[{"feature": ext}])
    res = body(rebuild(doc), fid)
    corners = [f for n, f in res.faces if n.startswith(f"{fid}/corner/")]
    assert len(corners) == 8  # one blend at each corner of the plate
    found = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(res.shape, TopAbs_EDGE, TopAbs_FACE, found)
    checked = 0
    for corner in corners:
        for i in range(1, found.Extent() + 1):
            faces = shape_list(found.FindFromIndex(i))
            if len(faces) != 2 or not any(f.IsSame(corner) for f in faces):
                continue
            edge = TopoDS.Edge(found.FindKey(i))
            a, b = (TopoDS.Face(f) for f in faces)
            assert BRep_Tool.Continuity_s(edge, a, b) != GeomAbs_C0
            checked += 1
    assert checked >= 3 * len(corners)
