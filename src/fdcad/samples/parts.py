"""The Phase 1 sample parts: plate with holes, turned shaft, bracket, and a 200 feature part.

Every sketch is fully defined. The plate is driven by global variables, so
changing one value updates the whole part (owner review, PLAN section 13).
"""

from __future__ import annotations

import math
from collections.abc import Callable

from fdcad.core.document.model import Document, Param, new_document
from fdcad.core.units import UnitSystem
from fdcad.samples.builder import (
    FRONT,
    TOP,
    SketchBuilder,
    add_feature,
    add_sketch,
    add_variables,
    face_ref,
    length,
    to_local,
)

_FULL_TURN = Param("360", 2 * math.pi)


def plate_with_holes() -> Document:
    """A 100 by 60 by 10 mm plate with four corner holes and a centre hole."""
    doc = new_document(UnitSystem.MM)
    add_variables(
        doc,
        Width=("100mm", 100.0),
        Height=("60mm", 60.0),
        Thickness=("10mm", 10.0),
        Inset=("10mm", 10.0),
        HoleDiameter=("8mm", 8.0),
    )
    base = SketchBuilder()
    base.rectangle(0, 0, 100, 60, "=Width", "=Height")
    sk = add_sketch(doc, base, {"feature": FRONT}, "Plate Sketch")
    plate = add_feature(
        doc, "extrude", "Plate", sk, operation="boss", end_condition="blind",
        depth=length("=Thickness", 10.0), reverse=False,
    )  # fmt: skip
    top, _plane = face_ref(doc, (0.0, 0.0, 1.0))
    holes = SketchBuilder()
    for x, y, xe, ye in (
        (10, 10, "=Inset", "=Inset"),
        (90, 10, "=Width - Inset", "=Inset"),
        (90, 50, "=Width - Inset", "=Height - Inset"),
        (10, 50, "=Inset", "=Height - Inset"),
    ):
        holes.circle(x, y, 8, "=HoleDiameter", (xe, ye))
    holes.circle(50, 30, 20, "20", ("=Width/2", "=Height/2"))
    hsk = add_sketch(doc, holes, top, "Hole Sketch")
    add_feature(
        doc, "extrude", "Holes", hsk, operation="cut", end_condition="through_all",
        depth=length("1", 1.0), reverse=True,
    )  # fmt: skip
    del plate
    return doc


def turned_shaft() -> Document:
    """A stepped shaft revolved about the X axis, with a groove."""
    doc = new_document(UnitSystem.MM)
    profile = SketchBuilder()
    # Steps: 40 mm at 30 mm diameter, 30 mm at 20 mm, 50 mm at 25 mm.
    points = [(0, 0), (120, 0), (120, 12.5), (70, 12.5), (70, 10), (40, 10), (40, 15), (0, 15)]
    profile.outline(points)
    axis = profile.centerline(-10, 0, 130, 0)
    sk = add_sketch(doc, profile, {"feature": FRONT}, "Shaft Profile")
    add_feature(
        doc, "revolve", "Shaft", sk, refs={"axis": {"sketch_entity": axis}},
        operation="boss", direction="one_direction", angle=_FULL_TURN, reverse=False,
    )  # fmt: skip
    groove = SketchBuilder()
    groove.rectangle(55, 8.5, 4, 3)
    gaxis = groove.centerline(-10, 0, 130, 0)
    gsk = add_sketch(doc, groove, {"feature": FRONT}, "Groove Profile")
    add_feature(
        doc, "revolve", "Groove", gsk, refs={"axis": {"sketch_entity": gaxis}},
        operation="cut", direction="one_direction", angle=_FULL_TURN, reverse=False,
    )  # fmt: skip
    return doc


def bracket() -> Document:
    """An L bracket, 40 mm wide, with two holes in each leg."""
    doc = new_document(UnitSystem.MM)
    profile = SketchBuilder()
    profile.outline([(0, 0), (60, 0), (60, 8), (8, 8), (8, 50), (0, 50)])
    sk = add_sketch(doc, profile, {"feature": FRONT}, "Bracket Profile")
    add_feature(
        doc, "extrude", "Bracket", sk, operation="boss", end_condition="mid_plane",
        depth=length("40", 40.0), reverse=False,
    )  # fmt: skip

    def flange(face: object) -> bool:
        from OCP.BRepGProp import BRepGProp
        from OCP.GProp import GProp_GProps

        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, props)
        return bool(abs(props.CentreOfMass().Y() - 8.0) < 1e-6)

    base_ref, base_plane = face_ref(doc, (0.0, 1.0, 0.0), flange)
    base_holes = SketchBuilder()
    for z in (-10.0, 10.0):
        u, v = to_local(base_plane, (38.0, 8.0, z))
        base_holes.circle(u, v, 6)
    bsk = add_sketch(doc, base_holes, base_ref, "Base Holes Sketch")
    add_feature(
        doc, "extrude", "Base Holes", bsk, operation="cut", end_condition="through_all",
        depth=length("1", 1.0), reverse=True,
    )  # fmt: skip
    leg_ref, leg_plane = face_ref(doc, (-1.0, 0.0, 0.0))
    leg_holes = SketchBuilder()
    for z in (-10.0, 10.0):
        u, v = to_local(leg_plane, (0.0, 34.0, z))
        leg_holes.circle(u, v, 6)
    lsk = add_sketch(doc, leg_holes, leg_ref, "Leg Holes Sketch")
    add_feature(
        doc, "extrude", "Leg Holes", lsk, operation="cut", end_condition="through_all",
        depth=length("1", 1.0), reverse=True,
    )  # fmt: skip
    return doc


def generated_200() -> Document:
    """A block with 98 blind holes, each its own sketch and cut: 200 features after the
    origin and default planes, for the performance budgets (PLAN 11.2)."""
    doc = new_document(UnitSystem.MM)
    base = SketchBuilder()
    base.rectangle(0, 0, 210, 110)
    sk = add_sketch(doc, base, {"feature": TOP}, "Block Sketch")
    add_feature(
        doc, "extrude", "Block", sk, operation="boss", end_condition="blind",
        depth=length("20", 20.0), reverse=False,
    )  # fmt: skip
    top, plane = face_ref(doc, (0.0, 1.0, 0.0))
    for i in range(98):
        col, row = i % 14, i // 14
        u, v = to_local(plane, (10.0 + col * 15.0, 20.0, -(10.0 + row * 15.0)))
        hole = SketchBuilder()
        hole.circle(u, v, 6)
        hsk = add_sketch(doc, hole, top, f"Hole Sketch {i + 1}")
        add_feature(
            doc, "extrude", f"Hole {i + 1}", hsk, operation="cut", end_condition="blind",
            depth=length("8", 8.0), reverse=True,
        )  # fmt: skip
    return doc


#: File name to builder.
SAMPLES: dict[str, Callable[[], Document]] = {
    "plate_with_holes": plate_with_holes,
    "turned_shaft": turned_shaft,
    "bracket": bracket,
    "generated_200": generated_200,
}

# Phase 3 samples for imports, curves and print tools live in their own module.
from fdcad.samples.parts_phase3 import PHASE3_SAMPLES  # noqa: E402

SAMPLES.update(PHASE3_SAMPLES)


def _phase5() -> None:
    """Add the Phase 5 sheet metal samples (``fdcad.samples.sheet_metal``)."""
    from fdcad.samples.sheet_metal import sheet_metal_bracket, sheet_metal_bracket_flat

    SAMPLES["sheet_metal_bracket"] = sheet_metal_bracket
    SAMPLES["sheet_metal_bracket_flat"] = sheet_metal_bracket_flat


_phase5()

# Phase 2 samples: enclosure with shell and fillets, lofted handle, swept spring.
from fdcad.samples.parts_phase2 import PHASE2_SAMPLES  # noqa: E402

SAMPLES.update(PHASE2_SAMPLES)

# Phase 4 samples for configurations and deformation (PLAN Phase 4).
from fdcad.samples.parts_phase4 import PHASE4_SAMPLES  # noqa: E402

SAMPLES.update(PHASE4_SAMPLES)

# The last Phase 3 and Phase 4 samples (PLAN Phase 3 and 4, D415).
from fdcad.samples.parts_phase34 import PHASE34_SAMPLES  # noqa: E402

SAMPLES.update(PHASE34_SAMPLES)

# Printing samples with tutorials (TR188, D1217).
from fdcad.samples.parts_print import PRINT_SAMPLES  # noqa: E402

SAMPLES.update(PRINT_SAMPLES)
