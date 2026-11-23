"""Phase 5 sample parts: a sheet metal bracket, folded and as its flat pattern (PLAN Phase 5)."""

from __future__ import annotations

from typing import Any

from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features.sheetmetal.params import new_sheet_metal
from fdcad.core.features.solids import line_ends
from fdcad.core.naming.select import reference_for
from fdcad.core.occ import ShapeMap
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.units import UnitSystem
from fdcad.samples.builder import FRONT, SketchBuilder, add_sketch

#: Bracket sizes in mm: sheet, base plate, flange length (from the outer virtual sharp).
THICKNESS, RADIUS = 2.0, 2.0
WIDTH, DEPTH, FLANGE = 80.0, 40.0, 30.0


def _edge(doc: Document, y: float, z: float) -> dict[str, Any]:
    body = RebuildEngine().rebuild(doc).body
    assert body is not None
    emap = ShapeMap()
    TopExp.MapShapes_s(body.shape, TopAbs_EDGE, emap)
    for i in range(1, emap.Extent() + 1):
        edge = TopoDS.Edge(emap.FindKey(i))
        ends = line_ends(edge)
        if ends and all(abs(p[1] - y) < 1e-9 and abs(p[2] - z) < 1e-9 for p in ends):
            ref = reference_for(body, edge)
            assert ref is not None
            return ref
    raise AssertionError("bracket edge not found")


def sheet_metal_bracket(flattened: bool = False) -> Document:
    """An 80 by 40 mm base with two holes and a 30 mm flange, 2 mm sheet, 2 mm bend radius."""
    doc = new_document(UnitSystem.MM)
    folder = new_sheet_metal(
        doc, {"thickness": Param("2", THICKNESS), "radius": Param("2", RADIUS)}
    )
    doc.features.append(folder)
    sk = SketchBuilder()
    sk.rectangle(0, 0, WIDTH, DEPTH)
    sk.circle(20, 15, 6)
    sk.circle(60, 15, 6)
    sid = add_sketch(doc, sk, {"feature": FRONT}, "Base Sketch")
    sheet = {"sheet_metal": {"feature": folder.id}}
    base = doc.new_feature_id()
    doc.features.append(
        Feature(base, "base_flange", "Base Flange 1", refs={"sketch": {"feature": sid}, **sheet})
    )
    edge = _edge(doc, DEPTH, THICKNESS)
    doc.features.append(
        Feature(
            doc.new_feature_id(), "edge_flange", "Edge Flange 1",
            params={"length": Param("30", FLANGE), "trim_side_bends": True},
            refs={"edges": [edge], **sheet},
        )
    )  # fmt: skip
    doc.features.append(
        Feature(
            doc.new_feature_id(),
            "flatten",
            "Flat Pattern",
            params={"flattened": flattened, "bend_lines": True, "bounding_box": True},
        )
    )
    return doc


def sheet_metal_bracket_flat() -> Document:
    """The bracket with its Flat Pattern turned on."""
    return sheet_metal_bracket(flattened=True)
