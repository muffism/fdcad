"""Small sheet metal parts for the tests."""

from __future__ import annotations

import itertools
import math
from typing import Any

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features.sheetmetal.params import new_sheet_metal
from fdcad.core.rebuild.engine import RebuildEngine, RebuildReport
from fdcad.samples.builder import FRONT, SketchBuilder, add_sketch


def sheet_doc(thickness: float = 2.0, radius: float = 1.0, **values: Any) -> Document:
    """A part with a Sheet Metal folder."""
    doc = new_document()
    params: dict[str, Any] = {
        "thickness": Param(f"{thickness:g}", thickness),
        "radius": Param(f"{radius:g}", radius),
    }
    params.update(values)
    doc.features.append(new_sheet_metal(doc, params))
    return doc


def folder(doc: Document) -> str:
    """Id of the Sheet Metal folder."""
    return next(f.id for f in doc.features if f.type == "sheet_metal")


def add(doc: Document, ftype: str, refs: dict[str, Any] | None = None, **params: Any) -> str:
    """Append a sheet metal feature that refers to the folder."""
    fid = doc.new_feature_id()
    all_refs: dict[str, Any] = {"sheet_metal": {"feature": folder(doc)}}
    all_refs.update(refs or {})
    name = f"{ftype.replace('_', ' ').title()} {fid}"
    doc.features.append(Feature(fid, ftype, name, params=dict(params), refs=all_refs))
    return fid


def plate(doc: Document, w: float = 100.0, h: float = 60.0, **params: Any) -> str:
    """A closed rectangle base flange on the Front plane."""
    sk = SketchBuilder()
    sk.rectangle(0, 0, w, h)
    sid = add_sketch(doc, sk, {"feature": FRONT}, "Plate Sketch")
    return add(doc, "base_flange", {"sketch": {"feature": sid}}, **params)


def open_profile(
    doc: Document, points: list[tuple[float, float]], depth: float, **params: Any
) -> str:
    """An open polyline base flange on the Front plane."""
    sk = SketchBuilder()
    ids = []
    for (x1, y1), (x2, y2) in itertools.pairwise(points):
        ids.append(sk.sk.add_line(x1, y1, x2, y2))
    sid = add_sketch(doc, sk, {"feature": FRONT}, "Profile")
    return add(
        doc, "base_flange", {"sketch": {"feature": sid}},
        depth=Param(f"{depth:g}", depth), **params,
    )  # fmt: skip


def build(doc: Document) -> RebuildReport:
    """Rebuild ``doc``."""
    return RebuildEngine().rebuild(doc)


def deg(a: float) -> Param:
    """An angle parameter in degrees."""
    return Param(f"{a:g}", math.radians(a))


def edge_ref(doc: Document, test: Any) -> dict[str, Any]:
    """Reference to the one straight edge of the rebuilt part whose ends pass ``test``."""
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp
    from OCP.TopoDS import TopoDS

    from fdcad.core.features.solids import line_ends
    from fdcad.core.naming.select import reference_for
    from fdcad.core.occ import ShapeMap

    body = build(doc).body
    assert body is not None
    emap = ShapeMap()
    TopExp.MapShapes_s(body.shape, TopAbs_EDGE, emap)
    found = []
    for i in range(1, emap.Extent() + 1):
        edge = TopoDS.Edge(emap.FindKey(i))
        ends = line_ends(edge)
        if ends is not None and test(*ends):
            found.append(edge)
    assert len(found) == 1, f"found {len(found)} edges"
    ref = reference_for(body, found[0])
    assert ref is not None
    return ref


def on(y: float | None = None, z: float | None = None, x: float | None = None) -> Any:
    """An edge test: both ends have these coordinates."""

    def test(a: tuple[float, float, float], b: tuple[float, float, float]) -> bool:
        for axis, want in enumerate((x, y, z)):
            if want is not None and (abs(a[axis] - want) > 1e-6 or abs(b[axis] - want) > 1e-6):
                return False
        return True

    return test


def flat_pattern(doc: Document, flattened: bool = True, **params: Any) -> str:
    """Append the Flat Pattern feature."""
    fid = doc.new_feature_id()
    values: dict[str, Any] = {"flattened": flattened, "bend_lines": True, "bounding_box": True}
    values.update(params)
    doc.features.append(Feature(fid, "flatten", "Flat Pattern", params=values))
    return fid


def ba(radius: float, thickness: float, degrees: float = 90.0, k: float = 0.44) -> float:
    """Bend allowance by the K-factor formula (PHASE5_SPEC P5.1 item 2)."""
    return math.pi * (radius + k * thickness) * degrees / 180
