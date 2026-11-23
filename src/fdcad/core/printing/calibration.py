"""Guided fit calibration (TR358, DECISIONS D2000).

``calibration_part`` makes a test plate: one pin and a row of holes whose gap per
side steps from ``start`` by ``step``, each labelled with its gap cut into the
plate, and the gaps as variables (``Gap1``, ``Gap2`` ...) that the hole sizes and
the labels follow. Print it, find the tightest hole the pin turns in, and keep
that gap as the printer's fit value. No Qt.
"""

from __future__ import annotations

from fdcad.core.document.model import Document, Variable, new_document
from fdcad.core.units import Kind, UnitSystem

#: The most test holes on one plate.
MOST = 10
PIN = 5.0
PITCH = 12.0


def gaps(start: float, step: float, count: int) -> list[float]:
    """The gap per side of each hole. Raises ValueError for values that cannot print."""
    if not 1 <= count <= MOST:
        raise ValueError(f"the count is not between 1 and {MOST}")
    if start < 0 or step <= 0:
        raise ValueError("the start is negative or the step is not above zero")
    return [round(start + k * step, 6) for k in range(count)]


def calibration_part(start: float = 0.1, step: float = 0.05, count: int = 6) -> Document:
    """The test plate with ``count`` labelled holes and one pin."""
    from fdcad.core.sketch.text import SketchText
    from fdcad.samples.builder import (
        FRONT,
        SketchBuilder,
        add_feature,
        add_sketch,
        face_ref,
        length,
        to_local,
    )

    values = gaps(start, step, count)
    doc = new_document(UnitSystem.MM)
    doc.variables.append(Variable("Pin", Kind.LENGTH, f"{PIN:g}mm", PIN))
    for k, gap in enumerate(values, 1):
        doc.variables.append(Variable(f"Gap{k}", Kind.LENGTH, f"{gap:g}mm", gap))
    wide = PITCH * (count + 1) + 4
    base = SketchBuilder()
    base.rectangle(0, 0, wide, 26)
    sk = add_sketch(doc, base, {"feature": FRONT}, "Plate Sketch")
    add_feature(
        doc, "extrude", "Plate", sk, operation="boss", end_condition="blind",
        depth=length("3", 3.0), reverse=False,
    )  # fmt: skip
    top, plane = face_ref(doc, (0.0, 0.0, 1.0))
    holes = SketchBuilder()
    for k, gap in enumerate(values, 1):
        u, v = to_local(plane, (PITCH * k, 16.0, 3.0))
        holes.circle(u, v, PIN + 2 * gap, f"=Pin + 2 * Gap{k}")
    hsk = add_sketch(doc, holes, top, "Hole Sketch")
    add_feature(
        doc, "extrude", "Holes", hsk, operation="cut", end_condition="through_all",
        depth=length("1", 1.0), reverse=True,
    )  # fmt: skip
    top, plane = face_ref(doc, (0.0, 0.0, 1.0))
    pin = SketchBuilder()
    u, v = to_local(plane, (PITCH * (count + 1), 16.0, 3.0))
    pin.circle(u, v, PIN, "=Pin")
    psk = add_sketch(doc, pin, top, "Pin Sketch")
    add_feature(
        doc, "extrude", "Pin", psk, operation="boss", end_condition="blind",
        depth=length("8", 8.0), reverse=False,
    )  # fmt: skip
    top, plane = face_ref(doc, (0.0, 0.0, 1.0), _on_plate)
    labels = SketchBuilder()
    for k, gap in enumerate(values, 1):
        u, v = to_local(plane, (PITCH * k - 4.5, 3.0, 3.0))
        labels.sk.texts.append(SketchText(f"t{k}", f"{gap:g}", u, v, height=4.0))
    lsk = add_sketch(doc, labels, top, "Label Sketch")
    add_feature(
        doc, "extrude", "Labels", lsk, operation="cut", end_condition="blind",
        depth=length("0.4", 0.4), reverse=True,
    )  # fmt: skip
    return doc


def _on_plate(face: object) -> bool:
    """True for the plate's top face, not the pin's end."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, props)
    return bool(abs(props.CentreOfMass().Z() - 3.0) < 1e-6)
