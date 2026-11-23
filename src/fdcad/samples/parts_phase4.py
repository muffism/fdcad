"""Phase 4 sample parts for configurations and deformation (PLAN Phase 4).

- ``configured_bolt_family``: a socket head bolt driven by variables, with
  three configurations from a design table (ISO 4762 nominal head sizes for
  M6, M8 and M10, from the published standard).
- ``twisted_bar``: a square bar twisted a quarter turn.
- ``flowed_strap``: a strap with two holes flowed along a quarter circle.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from fdcad.core import design_table as dt
from fdcad.core.deform.feature import default_params
from fdcad.core.document.model import (
    Document,
    Feature,
    Param,
    ParamValue,
    Variable,
    new_document,
)
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import Arc
from fdcad.core.units import Kind, UnitSystem
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

#: Configuration name to (D, L, dk, k) in millimetres: shank diameter, length,
#: head diameter and head height (ISO 4762 nominal values).
BOLT_SIZES: dict[str, tuple[float, float, float, float]] = {
    "M6 x 20": (6.0, 20.0, 10.0, 6.0),
    "M8 x 30": (8.0, 30.0, 13.0, 8.0),
    "M10 x 40": (10.0, 40.0, 16.0, 10.0),
}
ACTIVE_BOLT = "M8 x 30"

#: Golden tolerances for deformed samples (PLAN 10 item 8): the NURBS fit can
#: differ in its last digits between kernels and platforms.
GOLDEN_TOLERANCES: dict[str, dict[str, float]] = {
    "twisted_bar": {"volume_rel": 1e-4, "bbox_abs": 1e-3},
    "flowed_strap": {"volume_rel": 1e-4, "bbox_abs": 1e-3},
    # Helical threads come back from STEP a few millionths smaller (TR188, D2003).
    "nut_and_bolt": {"volume_rel": 1e-5},
}


def _var(doc: Document, name: str, value: float) -> None:
    doc.variables.append(Variable(name, Kind.LENGTH, f"{value:g}", value))


def configured_bolt_family() -> Document:
    """A bolt (head and shank) whose sizes come from a design table."""
    doc = new_document()
    d, shank, dk, k = BOLT_SIZES["M6 x 20"]
    for name, value in (("D", d), ("L", shank), ("DK", dk), ("K", k)):
        _var(doc, name, value)
    head = SketchBuilder()
    head.circle(0, 0, dk, dexpr="=DK")
    hsk = add_sketch(doc, head, {"feature": FRONT}, "Head Sketch")
    add_feature(
        doc, "extrude", "Head", hsk, operation="boss", end_condition="blind",
        depth=length("=K", k), reverse=False,
    )  # fmt: skip
    top, plane = face_ref(doc, (0.0, 0.0, 1.0))
    body = SketchBuilder()
    u, v = to_local(plane, (0.0, 0.0, k))
    body.circle(u, v, d, dexpr="=D")
    ssk = add_sketch(doc, body, top, "Shank Sketch")
    add_feature(
        doc, "extrude", "Shank", ssk, operation="boss", end_condition="blind",
        depth=length("=L", shank), reverse=False,
    )  # fmt: skip
    rows = [(name, [f"{v:g}" for v in sizes]) for name, sizes in BOLT_SIZES.items()]
    table = dt.Table(["var.D", "var.L", "var.DK", "var.K"], rows)
    dt.apply(doc, table, delete_missing=True)
    from fdcad.core import configurations

    configurations.activate(doc, ACTIVE_BOLT)
    from fdcad.core.rebuild.values import refresh_values

    refresh_values(doc)
    return doc


def twisted_bar() -> Document:
    """A 20 x 20 x 120 bar twisted a quarter turn along its length."""
    doc = new_document()
    base = SketchBuilder()
    base.rectangle(-10, -10, 20, 20)
    sk = add_sketch(doc, base, {"feature": FRONT}, "Bar Sketch")
    add_feature(
        doc, "extrude", "Bar", sk, operation="boss", end_condition="blind",
        depth=length("120", 120.0), reverse=False,
    )  # fmt: skip
    body = RebuildEngine().rebuild(doc).body
    assert body is not None
    params: dict[str, ParamValue] = dict(default_params(body.shape, "z", UnitSystem.MM))
    params["angle"] = Param("90", math.pi / 2)
    doc.features.append(Feature(doc.new_feature_id(), "twist", "Twist 1", params=params))
    return doc


def flowed_strap() -> Document:
    """A 12 x 4 x 100 strap with two holes, laid along a quarter circle of radius 80."""
    doc = new_document()
    base = SketchBuilder()
    base.rectangle(-6, -2, 12, 4)
    sk = add_sketch(doc, base, {"feature": FRONT}, "Strap Sketch")
    add_feature(
        doc, "extrude", "Strap", sk, operation="boss", end_condition="blind",
        depth=length("100", 100.0), reverse=False,
    )  # fmt: skip
    top = RebuildEngine().rebuild(doc).results[TOP].plane
    assert top is not None
    holes = SketchBuilder()
    for z in (25.0, 75.0):
        u, v = to_local(top, (0.0, 0.0, z))
        holes.circle(u, v, 5.0)
    hsk = add_sketch(doc, holes, {"feature": TOP}, "Hole Sketch")
    add_feature(
        doc, "extrude", "Holes", hsk, operation="cut", end_condition="mid_plane",
        depth=length("20", 20.0), reverse=False,
    )  # fmt: skip
    path = SketchBuilder()
    sk_path = path.sk
    radius = 80.0
    arc = sk_path.add_arc(-radius, 0.0, radius, 0.0, math.pi / 2)
    entity = sk_path.entities[arc]
    assert isinstance(entity, Arc)
    centre, start, end = entity.center, entity.start, entity.end
    sk_path.relate("coincident", start, path.origin)
    sk_path.relate("horizontal", centre, path.origin)
    sk_path.relate("vertical", end, centre)
    sk_path.dimension("radius", [arc], length("80", radius))
    psk = add_sketch(doc, path, {"feature": TOP}, "Path Sketch")
    body = RebuildEngine().rebuild(doc).body
    assert body is not None
    params: dict[str, ParamValue] = dict(default_params(body.shape, "z", UnitSystem.MM))
    feature = Feature(
        doc.new_feature_id(), "flow", "Flow 1", params=params, refs={"path": {"feature": psk}}
    )
    doc.features.append(feature)
    return doc


PHASE4_SAMPLES: dict[str, Callable[[], Document]] = {
    "configured_bolt_family": configured_bolt_family,
    "twisted_bar": twisted_bar,
    "flowed_strap": flowed_strap,
}
