"""Pattern nodes: attractor, 2D Voronoi cells and strut lattices (PLAN Phase 7 item 9)."""

from __future__ import annotations

import numpy as np
import pytest

from fdcad.core.graph import geometry as geo
from fdcad.core.graph.nodes.base import NodeError
from fdcad.core.graph.nodes.patterns import strut_ends, voronoi_cells
from fdcad.core.graph.types import XY_PLANE
from tests.core.graph.test_nodes import SQUARE, run, square


def test_attractor_values_by_distance_to_points() -> None:
    pts = [(0.0, 0.0, 0.0), (5.0, 0.0, 0.0), (20.0, 0.0, 0.0)]
    out = run(
        "attractor",
        {"points": pts, "attractors": [(0.0, 0.0, 0.0)], "radius": 10.0, "near": 0.0, "far": 1.0},
    )
    assert out["values"] == pytest.approx([0.0, 0.5, 1.0])
    assert out["distances"] == pytest.approx([0, 5, 20])
    assert out["points"] == [pytest.approx(p) for p in pts]


def test_attractor_shift_changes_spacing_and_curves_attract() -> None:
    pts = [(2.0, 0.0, 0.0), (8.0, 0.0, 0.0)]
    out = run(
        "attractor", {"points": pts, "attractors": [(0.0, 0.0, 0.0)], "radius": 10.0, "shift": 2.0}
    )
    assert out["points"][0][0] == pytest.approx(2 + 2 * 0.8)
    assert out["points"][1][0] == pytest.approx(8 + 2 * 0.2)
    line = geo.line((0, -50, 0), (0, 50, 0))
    near = run("attractor", {"points": [(3.0, 10.0, 0.0)], "attractors": [line], "radius": 10.0})
    assert near["distances"][0] == pytest.approx(3.0, abs=0.05)  # curves are sampled (D374)
    with pytest.raises(NodeError, match="attractor"):
        run("attractor", {"points": pts, "attractors": []})


def test_voronoi_cells_tile_the_boundary() -> None:
    seeds = [(10.0, 10.0, 0.0), (30.0, 10.0, 0.0), (20.0, 25.0, 0.0), (99.0, 99.0, 0.0)]
    cells = run("voronoi", {"boundary": square(), "points": seeds})["cells"]
    assert len(cells) == 3  # the point outside the boundary is left out
    area = sum(geo.volume(geo.extrude(c, (0, 0, 1))) for c in cells)
    assert area == pytest.approx(40 * 30, rel=1e-6)
    gapped = run("voronoi", {"boundary": square(), "points": seeds, "gap": 2.0})["cells"]
    assert sum(geo.volume(geo.extrude(c, (0, 0, 1))) for c in gapped) < area * 0.9
    with pytest.raises(NodeError, match="inside"):
        run("voronoi", {"boundary": square(), "points": [(99.0, 99.0, 0.0)]})


def test_voronoi_cell_math_matches_nearest_seed() -> None:
    seeds = np.array([[0.0, 0.0], [10.0, 0.0]])
    cells = voronoi_cells(seeds, np.array([-10.0, -10.0]), np.array([20.0, 10.0]), 0.0)
    assert cells[0][:, 0].max() == pytest.approx(5.0)
    assert cells[1][:, 0].min() == pytest.approx(5.0)


def test_strut_layouts() -> None:
    cubic = strut_ends(np.zeros(3), np.array([10.0, 10.0, 10.0]), 10.0, "cubic")
    assert len(cubic) == 12  # the edges of one cube
    octet = strut_ends(np.zeros(3), np.array([10.0, 10.0, 10.0]), 10.0, "octet")
    lengths = np.linalg.norm(octet[:, 1] - octet[:, 0], axis=1)
    assert np.allclose(lengths, 10 / np.sqrt(2))
    assert len(octet) == 36  # 24 corner to face centre and 12 between face centres


def test_lattice_fills_and_is_cut_to_the_body() -> None:
    block = geo.box(XY_PLANE, 20, 20, 10)
    out = run("lattice", {"body": block, "cell": 10.0, "radius": 1.0})
    lo, hi = geo.bounds(out["body"])
    assert lo == pytest.approx((0, 0, 0), abs=1e-6) and hi == pytest.approx((20, 20, 10), abs=1e-6)
    assert 0 < geo.volume(out["body"]) < 4000
    assert out["count"] == 33
    octet = run("lattice", {"body": block, "cell": 10.0, "radius": 1.0}, {"type": "octet"})
    assert geo.volume(octet["body"]) > geo.volume(out["body"])
    with pytest.raises(NodeError, match="too large"):
        run("lattice", {"body": block, "cell": 10.0, "radius": 4.9})
    assert SQUARE  # shared fixture data stays in use


def test_struts_wholly_past_the_body_are_left_out() -> None:
    """D2636, found by the edit storm on the lattice block: a cell of 9.9 mm in place
    of 10 adds a row of cells past the 30 by 30 by 20 box, and the lattice asked to
    confirm a boolean of 235 bodies, 91 of them struts that the cut to the box removes
    whole. Only struts that reach the box are made and counted; the result is the
    same as with all of them."""
    from fdcad.core.graph.nodes.patterns import lattice_parts

    block = geo.box(XY_PLANE, 30, 30, 20)
    out = run("lattice", {"body": block, "cell": 9.9, "radius": 1.2})
    assert out["count"] == 144
    lo, hi = (np.array(c) for c in geo.bounds(block))
    every = strut_ends(lo, hi, 9.9, "cubic")
    assert len(every) == 235
    whole = geo.union(lattice_parts(every, 1.2, "cubic"), unify=False)
    whole = geo.boolean("common", [whole], [block], unify=False)
    assert geo.volume(out["body"]) == pytest.approx(geo.volume(whole), rel=1e-9)
    octet = strut_ends(lo, hi, 9.9, "octet", reach=2.1)
    assert len(octet) < len(strut_ends(lo, hi, 9.9, "octet"))
    assert np.all(octet.min(axis=1) <= hi + 2.1 + 1e-9)
