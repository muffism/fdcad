"""Test parts for the Phase 3 features: native parts built through the rebuild,
and an imported STEP body (exported, read back and named as an import would be).

All values are our own test values.
"""

from __future__ import annotations

import math
import tempfile
from pathlib import Path
from typing import Any

from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Reader, STEPControl_Writer
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features.base import BuildContext, FeatureResult, FeatureState
from fdcad.core.features.solids import solids, volume_of
from fdcad.core.naming.names import NamedShape, faces_of, restrict
from fdcad.core.naming.resolve import face_snapshot
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Line, Sketch, sketch_to_data

# Native parts --------------------------------------------------------------------


def rect(s: Sketch, x0: float, y0: float, x1: float, y1: float) -> list[str]:
    corners = [s.add_point(x0, y0), s.add_point(x1, y0), s.add_point(x1, y1), s.add_point(x0, y1)]
    ids = []
    for p, q in zip(corners, corners[1:] + corners[:1], strict=True):
        eid = s.new_id()
        s.entities[eid] = Line(eid, p, q)
        ids.append(eid)
    return ids


def add_sketch(doc: Document, sketch: Sketch, plane: dict[str, Any]) -> str:
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(fid, "sketch", f"Sketch {fid}", refs={"plane": plane}, data=sketch_to_data(sketch))
    )
    return fid


def add_extrude(doc: Document, sketch_id: str, depth: float, **params: Any) -> str:
    fid = doc.new_feature_id()
    all_params: dict[str, Any] = {"operation": "boss", "end_condition": "blind"}
    all_params.update(params)
    all_params["depth"] = Param(str(depth), depth)
    doc.features.append(
        Feature(
            fid,
            "extrude",
            f"Extrude {fid}",
            params=all_params,
            refs={"sketch": {"feature": sketch_id}},
        )
    )
    return fid


def block_with_hole_and_boss() -> tuple[Document, dict[str, str]]:
    """A 60 x 40 x 10 block, a 10 mm hole at (45, 20), a 10 x 10 x 6 boss at (10..20, 15..25)."""
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 60, 40)
    plate = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    h = Sketch()
    h.add_circle(45, 20, 5)
    hole = add_extrude(
        doc,
        add_sketch(doc, h, {"kind": "face", "name": f"{plate}/cap/end"}),
        1.0,
        operation="cut",
        end_condition="through_all",
        reverse=True,
    )
    b = Sketch()
    rect(b, 10, 15, 20, 25)
    boss = add_extrude(doc, add_sketch(doc, b, {"kind": "face", "name": f"{plate}/cap/end"}), 6.0)
    return doc, {"plate": plate, "hole": hole, "boss": boss}


def face_ref(body: NamedShape, name: str) -> dict[str, Any]:
    face = body.face(name)
    assert face is not None, name
    return {"kind": "face", "name": name, "snapshot": face_snapshot(face)}


def ref_of(body: NamedShape, face: TopoDS_Face) -> dict[str, Any]:
    name = body.primary_name(face)
    assert name is not None
    return {"kind": "face", "name": name, "snapshot": face_snapshot(face)}


def add_feature(doc: Document, ftype: str, params: dict[str, Any], refs: dict[str, Any]) -> str:
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, ftype, f"{ftype} {fid}", params=params, refs=refs))
    return fid


def ok_body(results: dict[str, FeatureResult], fid: str) -> NamedShape:
    res = results[fid]
    assert res.state is not FeatureState.ERROR, [i.message for i in res.issues]
    assert res.body is not None
    return res.body


def messages(res: FeatureResult) -> str:
    return " ".join(i.message for i in res.issues)


def length(v: float) -> Param:
    return Param(f"{v:g}", v)


def angle(deg: float) -> Param:
    return Param(f"{deg:g}", math.radians(deg))


# Imported STEP body ----------------------------------------------------------------


def _step_round_trip(shape: TopoDS_Shape) -> TopoDS_Shape:
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "part.step")
        writer = STEPControl_Writer()
        writer.Transfer(shape, STEPControl_AsIs)
        writer.Write(path)
        reader = STEPControl_Reader()
        reader.ReadFile(path)
        reader.TransferRoots()
        return reader.OneShape()


def imported_bracket() -> NamedShape:
    """A STEP body: an 80 x 50 x 12 block with all top edges filleted (r 3), a
    16 mm through hole at (25, 25) and a 12 mm cylinder boss at (60, 25), 8 high.

    Faces are named ``imp/face#k`` as an import names them (no feature history).
    """
    block = BRepPrimAPI_MakeBox(80, 50, 12).Shape()
    fillet = BRepFilletAPI_MakeFillet(block)
    explorer = TopExp_Explorer(block, TopAbs_EDGE)
    while explorer.More():
        edge = TopoDS.Edge(explorer.Current())
        explorer.Next()
        curve = BRepAdaptor_Curve(edge)
        mid = curve.Value((curve.FirstParameter() + curve.LastParameter()) / 2)
        if abs(mid.Z() - 12) < 1e-6:
            fillet.Add(3.0, edge)
    shape = fillet.Shape()
    hole = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(25, 25, -1), gp_Dir(0, 0, 1)), 8, 20).Shape()
    shape = BRepAlgoAPI_Cut(shape, hole).Shape()
    boss = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(60, 25, 11), gp_Dir(0, 0, 1)), 6, 9).Shape()
    shape = BRepAlgoAPI_Fuse(shape, boss).Shape()
    shape = solids(_step_round_trip(shape))[0]
    return NamedShape(shape, restrict([], shape, "imp"))


def context(body: NamedShape | None) -> BuildContext:
    return BuildContext(new_document(), body, {})


def run(
    ftype: str, body: NamedShape, params: dict[str, Any], refs: dict[str, Any]
) -> FeatureResult:
    """Build one feature directly on ``body`` (an imported body has no tree before it)."""
    from fdcad.core.features import REGISTRY
    from fdcad.core.rebuild.engine import _build

    feature = Feature("f90", ftype, "Edit 1", params=params, refs=refs)
    return _build(feature, REGISTRY[ftype], context(body))


def find_faces(body: NamedShape, test: Any) -> list[TopoDS_Face]:
    return [f for f in faces_of(body.shape) if test(f)]


__all__ = ["rebuild", "volume_of"]
