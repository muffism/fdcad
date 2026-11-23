"""The Phase 7 sample graphs (PLAN Phase 7): a plate with an attractor driven hole
pattern, a Voronoi cut panel, a slider driven bracket and a lattice filled block.

Run ``uv run python -m fdcad.samples.graphs`` after changing a sample. The test
suite checks that the saved files match these builders and the golden results.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.graph.model import Graph, Node, Wire
from fdcad.core.units import UnitSystem
from fdcad.samples.builder import (
    FRONT,
    SketchBuilder,
    add_feature,
    add_sketch,
    add_variables,
    length,
)

ROOT = Path(__file__).resolve().parents[3]
SAMPLE_DIR = ROOT / "samples" / "graphs"
GOLDEN = ROOT / "tests" / "golden" / "graph_samples.json"


def _p(value: float, expr: str | None = None) -> Param:
    return Param(expr if expr is not None else f"{value:g}", float(value))


class _GraphBuilder:
    """Adds nodes in columns so the samples open tidy in the editor."""

    def __init__(self, position: str, name: str = "Graph 1") -> None:
        self.graph = Graph("g1", name, position=position)

    def node(self, ntype: str, column: int, row: int, **params: Any) -> str:
        nid = self.graph.new_node_id()
        self.graph.nodes.append(Node(nid, ntype, params, column * 220.0, row * 130.0))
        return nid

    def wire(self, source: str, output: str, target: str, port: str) -> None:
        self.graph.wires.append(Wire(source, output, target, port))


def _plate(doc: Document, w: float, h: float, t: float, name: str) -> str:
    sk = SketchBuilder()
    sk.rectangle(0, 0, w, h, f"{w:g}", f"{h:g}")
    sid = add_sketch(doc, sk, {"feature": FRONT}, f"{name} Sketch")
    return add_feature(
        doc, "extrude", name, sid, operation="boss", end_condition="blind",
        depth=length(f"{t:g}", t), reverse=False,
    )  # fmt: skip


def _graph_body(doc: Document, graph: Graph, output: str, name: str = "Graph Body 1") -> str:
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(fid, "graph_body", name, refs={"graph": {"graph": graph.id, "output": output}})
    )
    return fid


def attractor_plate() -> Document:
    """A 120 by 80 by 6 mm plate with a grid of holes that grow away from a point."""
    doc = new_document(UnitSystem.MM)
    plate = _plate(doc, 120, 80, 6, "Plate")
    b = _GraphBuilder(plate)
    origin = b.node("point", 0, 0, x=_p(10), y=_p(10), z=_p(-5))
    plane = b.node("plane", 1, 0)
    b.wire(origin, "out", plane, "origin")
    grid = b.node(
        "point_grid", 2, 0, count_x=_p(11), count_y=_p(7), spacing_x=_p(10), spacing_y=_p(10)
    )
    b.wire(plane, "out", grid, "plane")
    target = b.node("point", 2, 1, x=_p(35), y=_p(40), z=_p(-5))
    field = b.node("attractor", 3, 0, radius=_p(70), near=_p(1), far=_p(4))
    b.wire(grid, "out", field, "points")
    b.wire(target, "out", field, "attractors")
    holes = b.node("cylinder", 4, 0, height=_p(16))
    b.wire(field, "points", holes, "base")
    b.wire(field, "values", holes, "radius")
    out = b.node("add_as_feature", 5, 0, operation="subtract")
    b.wire(holes, "body", out, "body")
    b.node("comment", 0, 2, text="Holes grow from 1 mm radius near the point to 4 mm far away.")
    doc.graphs.append(b.graph)
    _graph_body(doc, b.graph, out)
    return doc


def voronoi_panel() -> Document:
    """A 120 by 80 by 4 mm panel with seeded random Voronoi cells cut through it."""
    doc = new_document(UnitSystem.MM)
    panel = _plate(doc, 120, 80, 4, "Panel")
    b = _GraphBuilder(panel)
    corners = [[8, 8, -1], [112, 8, -1], [112, 72, -1], [8, 72, -1]]
    boundary = b.node("polyline", 0, 0, points=corners, closed=True)
    seeds = b.node("populate_region", 1, 1, count=_p(24), seed=2)
    b.wire(boundary, "out", seeds, "boundary")
    cells = b.node("voronoi", 2, 0, gap=_p(3))
    b.wire(boundary, "out", cells, "boundary")
    b.wire(seeds, "out", cells, "points")
    up = b.node("vector", 2, 1)
    cut = b.node("extrude", 3, 0, distance=_p(6))
    b.wire(cells, "cells", cut, "curve")
    b.wire(up, "out", cut, "direction")
    out = b.node("add_as_feature", 4, 0, operation="subtract")
    b.wire(cut, "body", out, "body")
    doc.graphs.append(b.graph)
    _graph_body(doc, b.graph, out)
    return doc


def slider_bracket() -> Document:
    """An L bracket whose leg lengths and width are set by sliders in the graph."""
    doc = new_document(UnitSystem.MM)
    add_variables(doc, Length=("60mm", 60.0), Height=("50mm", 50.0), Thick=("8mm", 8.0))
    profile = SketchBuilder()
    profile.outline(
        [(0, 0), (60, 0), (60, 8), (8, 8), (8, 50), (0, 50)],
        ["=Length", "=Thick", "=Length - Thick", "=Height - Thick", None, None],
    )
    sk = add_sketch(doc, profile, {"feature": FRONT}, "Bracket Profile")
    bracket = add_feature(
        doc, "extrude", "Bracket", sk, operation="boss", end_condition="mid_plane",
        depth=length("40", 40.0), reverse=False,
    )  # fmt: skip
    b = _GraphBuilder("f4")  # above the bracket, so the sliders can drive it
    long_leg = b.node("slider", 0, 0, kind="length", min=30, max=100, step=5, value=_p(80))
    set_length = b.node("set_variable", 1, 0, variable="Length")
    b.wire(long_leg, "out", set_length, "value")
    short_leg = b.node("slider", 0, 1, kind="length", min=20, max=80, step=5, value=_p(35))
    set_height = b.node("set_variable", 1, 1, variable="Height")
    b.wire(short_leg, "out", set_height, "value")
    width = b.node("slider", 0, 2, kind="length", min=10, max=60, step=2, value=_p(24))
    set_width = b.node("set_param", 1, 2, feature=bracket, param="depth")
    b.wire(width, "out", set_width, "value")
    doc.graphs.append(b.graph)
    return doc


def lattice_block() -> Document:
    """A 30 by 30 mm base with a cubic strut lattice filling a 20 mm high block on it."""
    doc = new_document(UnitSystem.MM)
    base = _plate(doc, 30, 30, 3, "Base")
    b = _GraphBuilder(base)
    corner = b.node("point", 0, 0, z=_p(3))
    block = b.node("box", 1, 0, size_x=_p(30), size_y=_p(30), size_z=_p(20))
    b.wire(corner, "out", block, "corner")
    lattice = b.node("lattice", 2, 0, cell=_p(10), radius=_p(1.2), type="cubic")
    b.wire(block, "body", lattice, "body")
    out = b.node("add_as_feature", 3, 0, operation="add")
    b.wire(lattice, "body", out, "body")
    doc.graphs.append(b.graph)
    _graph_body(doc, b.graph, out)
    return doc


GRAPH_SAMPLES: dict[str, Callable[[], Document]] = {
    "attractor_plate": attractor_plate,
    "voronoi_panel": voronoi_panel,
    "slider_bracket": slider_bracket,
    "lattice_block": lattice_block,
}


def main() -> None:
    """Save every graph sample and its golden result."""
    from fdcad.core.io import fdef
    from fdcad.core.rebuild.engine import RebuildEngine
    from fdcad.samples.make import measure

    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    golden: dict[str, Any] = {}
    for name, build in GRAPH_SAMPLES.items():
        doc = build()
        fdef.save(doc, SAMPLE_DIR / f"{name}{fdef.PART_SUFFIX}")
        report = RebuildEngine().rebuild(doc)
        assert report.body is not None, name
        golden[name] = measure(report.body.shape)
        golden[name]["bodies"] = report.body_count
        print(f"{name}: {golden[name]}")
    GOLDEN.write_text(json.dumps(golden, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
