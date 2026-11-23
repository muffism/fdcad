"""Phase 3 sample parts for imports, curves and print tools (PLAN Phase 3).

Each builder makes a fully defined part in code, like ``parts.py``. Imported
files are made in code too and embedded, so the samples need no files on disk.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features.import_step import part_from_step
from fdcad.core.naming.names import centroid, faces_of
from fdcad.core.naming.select import reference_for
from fdcad.core.occ import BRepAlgoAPI_Fuse
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.units import UnitSystem
from fdcad.samples.builder import (
    FRONT,
    TOP,
    SketchBuilder,
    add_feature,
    add_sketch,
    face_ref,
    length,
    to_local,
)
from fdcad.samples.step_source import colored_step_bytes


def _bracket_step() -> bytes:
    """An L shaped block, 60 by 40 by 10 mm with a 10 mm upright, grey with a blue top."""
    base = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 60.0, 40.0, 10.0).Shape()
    wall = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 10), 10.0, 40.0, 30.0).Shape()
    fuse = BRepAlgoAPI_Fuse(base, wall)
    fuse.Build()
    shape = fuse.Shape()
    top = [f for f in faces_of(shape) if abs(centroid(f)[2] - 10.0) < 1e-9]
    return colored_step_bytes(shape, "#8C949C", [(f, "#2F6FD0") for f in top])


def imported_step_with_features() -> Document:
    """An imported L bracket with a boss and a hole added on its blue top face."""
    doc = part_from_step("l_bracket.step", _bracket_step(), UnitSystem.MM)
    doc.features[-1].name = "Imported Bracket"
    top, plane = face_ref(doc, (0.0, 0.0, 1.0), lambda f: abs(centroid(f)[2] - 10.0) < 1e-9)
    boss = SketchBuilder()
    u, v = to_local(plane, (35.0, 20.0, 10.0))
    boss.circle(u, v, 16)
    bsk = add_sketch(doc, boss, top, "Boss Sketch")
    add_feature(
        doc, "extrude", "Boss", bsk, operation="boss", end_condition="blind",
        depth=length("8", 8.0), reverse=False,
    )  # fmt: skip
    hole_top, hole_plane = face_ref(
        doc, (0.0, 0.0, 1.0), lambda f: abs(centroid(f)[2] - 18.0) < 1e-9
    )
    hole = SketchBuilder()
    hu, hv = to_local(hole_plane, (35.0, 20.0, 18.0))
    hole.circle(hu, hv, 6)
    hsk = add_sketch(doc, hole, hole_top, "Hole Sketch")
    add_feature(
        doc, "extrude", "Hole", hsk, operation="cut", end_condition="through_all",
        depth=length("1", 1.0), reverse=True,
    )  # fmt: skip
    return doc


def piped_frame() -> Document:
    """A hollow tube frame: a 20 mm pipe with 2 mm walls around a 120 by 80 mm rectangle."""
    doc = new_document(UnitSystem.MM)
    path = SketchBuilder()
    path.rectangle(0, 0, 120, 80)
    psk = add_sketch(doc, path, {"feature": FRONT}, "Frame Path")
    pid = doc.new_feature_id()
    doc.features.append(
        Feature(
            pid, "pipe", "Frame Tube",
            params={"operation": "boss", "outer_diameter": length("20", 20.0),
                    "inner_diameter": length("16", 16.0)},
            refs={"path": {"feature": psk}},
        )
    )  # fmt: skip
    return doc


def _link(doc: Document, plane: str, x: float, name: str) -> str:
    """A 14 by 8 mm link: a 2 mm pipe around a rectangle, kept as its own body."""
    path = SketchBuilder()
    path.rectangle(x, -4, 14, 8)
    sk = add_sketch(doc, path, {"feature": plane}, f"{name} Path")
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid, "pipe", name,
            params={"operation": "boss", "merge": False, "outer_diameter": length("2", 2.0)},
            refs={"path": {"feature": sk}},
        )
    )  # fmt: skip
    return fid


def chain_along_curve() -> Document:
    """Two linked links copied 15 times along a rising helix: a chain of 30 links.

    Link A lies in the XZ plane and link B in the XY plane through it; each pair
    is 22 mm long, so a copy's first link passes through the last link before it.
    """
    doc = new_document(UnitSystem.MM)
    first = _link(doc, TOP, 0.0, "Link A")
    second = _link(doc, FRONT, 11.0, "Link B")
    guide = SketchBuilder()
    guide.circle(0, 150, 300)
    gsk = add_sketch(doc, guide, {"feature": FRONT}, "Chain Guide Circle")
    hid = doc.new_feature_id()
    doc.features.append(
        Feature(
            hid, "helix", "Chain Path",
            params={"definition": "pitch_turns", "pitch": length("30", 30.0),
                    "turns": Param("1", 1.0), "start_angle": Param("270", 1.5 * math.pi)},
            refs={"sketch": {"feature": gsk}},
        )
    )  # fmt: skip
    report = RebuildEngine().rebuild(doc)
    body = report.body
    assert body is not None
    bodies = []
    for fid in (first, second):
        face = next(f for n, f in body.faces if n.startswith(f"{fid}/"))
        ref = reference_for(body, face)
        assert ref is not None
        bodies.append(ref)
    aid = doc.new_feature_id()
    doc.features.append(
        Feature(
            aid, "curve_array", "Chain",
            params={"mode": "spacing", "count": Param("15", 15.0),
                    "spacing": length("22", 22.0)},
            refs={"path": {"feature": hid}, "bodies": bodies},
        )
    )  # fmt: skip
    return doc


def split_with_pins() -> Document:
    """A 300 by 120 by 30 mm block, too long for a 220 mm printer, split in two with pins."""
    doc = new_document(UnitSystem.MM)
    base = SketchBuilder()
    base.rectangle(0, 0, 300, 120)
    sk = add_sketch(doc, base, {"feature": FRONT}, "Block Sketch")
    add_feature(
        doc, "extrude", "Block", sk, operation="boss", end_condition="blind",
        depth=length("30", 30.0), reverse=False,
    )  # fmt: skip
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid, "split_for_print", "Print Split",
            params={
                "mode": "auto", "build_x": length("220", 220.0),
                "build_y": length("220", 220.0), "build_z": length("250", 250.0),
                "connector": "pins", "pin_diameter": length("5", 5.0),
                "pin_length": length("10", 10.0), "clearance": length("0.2", 0.2),
            },
        )
    )  # fmt: skip
    return doc


def _box_stl(x: float, y: float, z: float) -> bytes:
    """A closed box mesh written in code, so the sample does not depend on a mesher."""
    import numpy as np

    from fdcad.core.io.mesh_import import Mesh, stl_bytes

    corners = np.array(
        [[0, 0, 0], [x, 0, 0], [x, y, 0], [0, y, 0], [0, 0, z], [x, 0, z], [x, y, z], [0, y, z]],
        dtype=np.float32,
    )
    faces = np.array(
        [
            [0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4],
            [1, 2, 6], [1, 6, 5], [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7],
        ],
        dtype=np.int32,
    )  # fmt: skip
    return stl_bytes(Mesh(corners, faces))


def imported_mesh_with_cut() -> Document:
    """A box mesh converted to a solid, with a slot cut through it."""
    from fdcad.core.features.import_mesh import part_from_mesh

    doc = part_from_mesh("block.stl", _box_stl(60.0, 40.0, 20.0), UnitSystem.MM)
    mesh = doc.features[-1]
    mesh.name = "Scanned Block"
    mesh.params["convert"] = True
    top, plane = face_ref(doc, (0.0, 0.0, 1.0))
    slot = SketchBuilder()
    u, v = to_local(plane, (15.0, 15.0, 20.0))
    slot.rectangle(u, v, 30, 10)
    ssk = add_sketch(doc, slot, top, "Slot Sketch")
    add_feature(
        doc, "extrude", "Slot", ssk, operation="cut", end_condition="through_all",
        depth=length("1", 1.0), reverse=True,
    )  # fmt: skip
    return doc


#: File name to builder, added to ``parts.SAMPLES``.
PHASE3_SAMPLES: dict[str, Callable[[], Document]] = {
    "imported_step_with_features": imported_step_with_features,
    "piped_frame": piped_frame,
    "chain_along_curve": chain_along_curve,
    "split_with_pins": split_with_pins,
    "imported_mesh_with_cut": imported_mesh_with_cut,
}

__all__ = ["PHASE3_SAMPLES"]
