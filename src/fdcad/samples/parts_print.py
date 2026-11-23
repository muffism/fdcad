"""Printing sample parts with tutorials (TR188, DECISIONS D1217).

A fit test plate (pins and holes with stepped gaps), a living hinge strip, and a
storage bin sized on a grid with variables. TR188 (D2003) adds a nut and bolt
with printable threads, a print in place hinge, and the base grid the bins sit
on. Each rebuilds in the sample tests
and has a tutorial in ``docs/user_guide/tutorials``.
"""

from __future__ import annotations

from collections.abc import Callable

from fdcad.core.document.model import Document, Feature, Param, Variable, new_document
from fdcad.core.units import Kind, UnitSystem
from fdcad.samples.builder import (
    FRONT,
    SketchBuilder,
    add_feature,
    add_sketch,
    add_variables,
    edge_ref,
    face_ref,
    length,
    to_local,
)

#: Gap steps of the fit test plate, in units of the variable Step.
FIT_STEPS = (1, 2, 3, 4, 5)


def fit_test_plate() -> Document:
    """A 70 x 30 x 4 plate: a row of pins of diameter Pin, and a row of holes Pin plus
    2, 4, 6, 8 and 10 times Step wide, so the gap per side steps by Step."""
    doc = new_document(UnitSystem.MM)
    add_variables(doc, Pin=("5mm", 5.0), Step=("0.1mm", 0.1), Plate=("4mm", 4.0))
    base = SketchBuilder()
    base.rectangle(0, 0, 70, 30)
    sk = add_sketch(doc, base, {"feature": FRONT}, "Plate Sketch")
    add_feature(
        doc, "extrude", "Plate", sk, operation="boss", end_condition="blind",
        depth=length("=Plate", 4.0), reverse=False,
    )  # fmt: skip
    top, plane = face_ref(doc, (0.0, 0.0, 1.0))
    holes = SketchBuilder()
    for k in FIT_STEPS:
        x = 12.0 * k - 1.0
        u, v = to_local(plane, (x, 9.0, 4.0))
        holes.circle(u, v, 5.0 + 2 * k * 0.1, f"=Pin + {2 * k} * Step")
    hsk = add_sketch(doc, holes, top, "Hole Sketch")
    add_feature(
        doc, "extrude", "Holes", hsk, operation="cut", end_condition="through_all",
        depth=length("1", 1.0), reverse=True,
    )  # fmt: skip
    top, plane = face_ref(doc, (0.0, 0.0, 1.0))
    pins = SketchBuilder()
    for k in FIT_STEPS:
        u, v = to_local(plane, (12.0 * k - 1.0, 22.0, 4.0))
        pins.circle(u, v, 5.0, "=Pin")
    psk = add_sketch(doc, pins, top, "Pin Sketch")
    add_feature(
        doc, "extrude", "Pins", psk, operation="boss", end_condition="blind",
        depth=length("6", 6.0), reverse=False,
    )  # fmt: skip
    return doc


def living_hinge_strip() -> Document:
    """An 80 x 20 x 1.2 strip that bends in the middle: a 24 mm band of staggered slits."""
    doc = new_document(UnitSystem.MM)
    base = SketchBuilder()
    base.rectangle(0, 0, 80, 20)
    sk = add_sketch(doc, base, {"feature": FRONT}, "Strip Sketch")
    add_feature(
        doc, "extrude", "Strip", sk, operation="boss", end_condition="blind",
        depth=length("1.2", 1.2), reverse=False,
    )  # fmt: skip
    top, plane = face_ref(doc, (0.0, 0.0, 1.0))
    band = SketchBuilder()
    u, v = to_local(plane, (28.0, 1.0, 1.2))
    band.rectangle(u, v, 24, 18)
    bsk = add_sketch(doc, band, top, "Hinge Band")
    doc.features.append(
        Feature(
            doc.new_feature_id(),
            "living_hinge",
            "Living Hinge 1",
            params={
                "slit_length": Param("10", 10.0),
                "slit_width": Param("0.6", 0.6),
                "bridge": Param("2", 2.0),
                "row_spacing": Param("1.5", 1.5),
            },
            refs={"sketch": {"feature": bsk}},
        )
    )
    return doc


def storage_bin() -> Document:
    """A bin 2 by 1 grid units of Grid (42 mm) with Wall thick sides and a Floor, as tall
    as Height: change the variables to make another size."""
    doc = new_document(UnitSystem.MM)
    add_variables(
        doc,
        Grid=("42mm", 42.0),
        Height=("30mm", 30.0),
        Wall=("1.6mm", 1.6),
        Floor=("2mm", 2.0),
    )
    doc.variables += [
        Variable("Wide", Kind.NUMBER, "2", 2.0),
        Variable("Deep", Kind.NUMBER, "1", 1.0),
    ]
    outer = SketchBuilder()
    outer.rectangle(0, 0, 84, 42, "=Grid * Wide", "=Grid * Deep")
    sk = add_sketch(doc, outer, {"feature": FRONT}, "Bin Sketch")
    add_feature(
        doc, "extrude", "Bin", sk, operation="boss", end_condition="blind",
        depth=length("=Height", 30.0), reverse=False,
    )  # fmt: skip
    top, plane = face_ref(doc, (0.0, 0.0, 1.0))
    inner = SketchBuilder()
    u, v = to_local(plane, (1.6, 1.6, 30.0))
    inner.rectangle(
        u, v, 84 - 3.2, 42 - 3.2, "=Grid * Wide - 2 * Wall", "=Grid * Deep - 2 * Wall",
        ("=Wall", "=Wall"),
    )  # fmt: skip
    isk = add_sketch(doc, inner, top, "Cavity Sketch")
    add_feature(
        doc, "extrude", "Cavity", isk, operation="cut", end_condition="blind",
        depth=length("=Height - Floor", 28.0), reverse=True,
    )  # fmt: skip
    return doc


def _round_edge(radius: float, z: float, x: float = 0.0) -> Callable[[object], bool]:
    """A test for the circle edge of ``radius`` at height ``z`` centred on x = ``x``."""

    def test(edge: object) -> bool:
        from OCP.BRepAdaptor import BRepAdaptor_Curve
        from OCP.GeomAbs import GeomAbs_Circle
        from OCP.TopoDS import TopoDS

        curve = BRepAdaptor_Curve(TopoDS.Edge(edge))
        if curve.GetType() != GeomAbs_Circle:
            return False
        circle = curve.Circle()
        c = circle.Location()
        return bool(
            abs(circle.Radius() - radius) < 1e-6 and abs(c.Z() - z) < 1e-6 and abs(c.X() - x) < 1e-6
        )

    return test


#: The nut and bolt's thread: M8 coarse.
BOLT_DIAMETER, BOLT_PITCH = 8.0, 1.25


def nut_and_bolt() -> Document:
    """An M8 bolt (13 mm hexagon head, 17 mm of thread) and its nut beside it, as two
    bodies, with modelled threads and a printing clearance (TR188, D2003)."""
    doc = new_document(UnitSystem.MM)
    add_variables(doc, Flats=("13mm", 13.0), Head=("5.5mm", 5.5), NutHeight=("6.5mm", 6.5))
    head = SketchBuilder()
    head.hexagon(0, 0, 13.0, "=Flats")
    hsk = add_sketch(doc, head, {"feature": FRONT}, "Head Sketch")
    add_feature(
        doc, "extrude", "Head", hsk, operation="boss", end_condition="blind",
        depth=length("=Head", 5.5), reverse=False,
    )  # fmt: skip
    top, plane = face_ref(doc, (0.0, 0.0, 1.0))
    shaft = SketchBuilder()
    u, v = to_local(plane, (0.0, 0.0, 5.5))
    shaft.circle(u, v, BOLT_DIAMETER, "8")
    ssk = add_sketch(doc, shaft, top, "Shaft Sketch")
    add_feature(
        doc, "extrude", "Shaft", ssk, operation="boss", end_condition="blind",
        depth=length("20", 20.0), reverse=False,
    )  # fmt: skip
    nut = SketchBuilder()
    nut.hexagon(25.0, 0.0, 13.0, "=Flats")
    nut.circle(25.0, 0.0, 7.25, "7.25")
    nsk = add_sketch(doc, nut, {"feature": FRONT}, "Nut Sketch")
    add_feature(
        doc, "extrude", "Nut", nsk, operation="boss", end_condition="blind",
        depth=length("=NutHeight", 6.5), reverse=False, merge=False,
    )  # fmt: skip
    for name, edge in (
        ("Bolt Thread", _round_edge(BOLT_DIAMETER / 2, 25.5)),
        ("Nut Thread", _round_edge(7.25 / 2, 6.5, 25.0)),
    ):
        doc.features.append(
            Feature(
                doc.new_feature_id(),
                "modeled_thread",
                name,
                params={
                    "diameter": length("8", BOLT_DIAMETER),
                    "pitch": length("1.25", BOLT_PITCH),
                    "method": "cut",
                    "hand": "right",
                    "end_condition": "blind",
                    "length": length(
                        "6.5" if name == "Nut Thread" else "17",
                        6.5 if name == "Nut Thread" else 17.0,
                    ),
                    "clearance": length("0.1", 0.1),
                },
                refs={"edge": [edge_ref(doc, edge)]},
            )
        )
    return doc


def _offset_plane(doc: Document, name: str, expr: str, value: float) -> str:
    """A reference plane parallel to the Front plane, ``value`` above it."""
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "ref_plane",
            name,
            params={"method": "offset", "distance": length(expr, value)},
            refs={"first": {"feature": FRONT}},
        )
    )
    return fid


def print_in_place_hinge() -> Document:
    """Two leaves joined by three knuckles round a pin, with a Gap all round the moving
    leaf so it prints as one piece and turns once off the bed (TR188, D2003). Print it
    standing on the knuckle ends."""
    doc = new_document(UnitSystem.MM)
    add_variables(doc, Gap=("0.4mm", 0.4), Knuckle=("10mm", 10.0))
    # Leaf A: plate and knuckle the whole height, then room cut for leaf B's knuckle.
    plate = SketchBuilder()
    plate.rectangle(-35.0, -1.5, 35.0, 3.0, None, None, ("35", "1.5"))
    psk = add_sketch(doc, plate, {"feature": FRONT}, "Leaf A Sketch")
    add_feature(
        doc, "extrude", "Leaf A", psk, operation="boss", end_condition="blind",
        depth=length("=3 * Knuckle", 30.0), reverse=False,
    )  # fmt: skip
    knuckle = SketchBuilder()
    knuckle.circle(0.0, 0.0, 10.0)
    ksk = add_sketch(doc, knuckle, {"feature": FRONT}, "Knuckle Sketch")
    add_feature(
        doc, "extrude", "Knuckles", ksk, operation="boss", end_condition="blind",
        depth=length("=3 * Knuckle", 30.0), reverse=False,
    )  # fmt: skip
    room_plane = _offset_plane(doc, "Room Plane", "=Knuckle - Gap", 9.6)
    room = SketchBuilder()
    room.circle(0.0, 0.0, 10.8, "=10mm + 2 * Gap")
    rsk = add_sketch(doc, room, {"feature": room_plane}, "Room Sketch")
    add_feature(
        doc, "extrude", "Room", rsk, operation="cut", end_condition="blind",
        depth=length("=Knuckle + 2 * Gap", 10.8), reverse=False,
    )  # fmt: skip
    pin = SketchBuilder()
    pin.circle(0.0, 0.0, 5.0)
    nsk = add_sketch(doc, pin, {"feature": room_plane}, "Pin Sketch")
    add_feature(
        doc, "extrude", "Pin", nsk, operation="boss", end_condition="blind",
        depth=length("=Knuckle + 2 * Gap", 10.8), reverse=False,
    )  # fmt: skip
    # Leaf B: a ring round the pin with its plate, a separate body.
    leaf_plane = _offset_plane(doc, "Leaf B Plane", "=Knuckle", 10.0)
    leaf = SketchBuilder()
    leaf.circle(0.0, 0.0, 10.0)
    leaf.circle(0.0, 0.0, 5.8, "=5mm + 2 * Gap")
    lsk = add_sketch(doc, leaf, {"feature": leaf_plane}, "Leaf B Knuckle Sketch")
    add_feature(
        doc, "extrude", "Leaf B Knuckle", lsk, operation="boss", end_condition="blind",
        depth=length("=Knuckle", 10.0), reverse=False, merge=False,
    )  # fmt: skip
    web = SketchBuilder()
    web.rectangle(4.0, -1.5, 31.0, 3.0, None, None, ("4", "1.5"))
    wsk = add_sketch(doc, web, {"feature": leaf_plane}, "Leaf B Sketch")
    add_feature(
        doc, "extrude", "Leaf B", wsk, operation="boss", end_condition="blind",
        depth=length("=Knuckle", 10.0), reverse=False,
    )  # fmt: skip
    return doc


def bin_base_grid() -> Document:
    """The base plate the storage bins sit on: Wide by Deep cells of Grid (42 mm), each a
    pocket Lip in from the cell's sides, so a bin's foot drops in (TR188, D2003)."""
    doc = new_document(UnitSystem.MM)
    add_variables(doc, Grid=("42mm", 42.0), Lip=("1.2mm", 1.2), Base=("5mm", 5.0))
    wide, deep = 3, 2
    outer = SketchBuilder()
    outer.rectangle(0, 0, 42.0 * wide, 42.0 * deep, f"=Grid * {wide}", f"=Grid * {deep}")
    sk = add_sketch(doc, outer, {"feature": FRONT}, "Base Sketch")
    add_feature(
        doc, "extrude", "Base", sk, operation="boss", end_condition="blind",
        depth=length("=Base", 5.0), reverse=False,
    )  # fmt: skip
    top, plane = face_ref(doc, (0.0, 0.0, 1.0))
    cells = SketchBuilder()
    for i in range(wide):
        for j in range(deep):
            u, v = to_local(plane, (42.0 * i + 1.2, 42.0 * j + 1.2, 5.0))
            cells.rectangle(
                u, v, 42.0 - 2.4, 42.0 - 2.4, "=Grid - 2 * Lip", "=Grid - 2 * Lip",
                (f"=Grid * {i} + Lip" if i else "=Lip", f"=Grid * {j} + Lip" if j else "=Lip"),
            )  # fmt: skip
    csk = add_sketch(doc, cells, top, "Cell Sketch")
    add_feature(
        doc, "extrude", "Cells", csk, operation="cut", end_condition="blind",
        depth=length("3", 3.0), reverse=True,
    )  # fmt: skip
    return doc


#: The hex fastener set's size, from the ISO screw table (TR162 item 1, D2409).
FASTENER_SIZE = "M6"
#: ISO 4017 hexagon head height for M6 (the screw table holds socket heads only).
HEX_HEAD_HEIGHT = 4.0


def hex_fasteners() -> Document:
    """An ISO M6 hexagon head bolt, hexagon nut and plain washer, each its own body, sized
    from FDCAD's screw and washer tables, with cosmetic threads (TR162 item 1, D2409)."""
    from fdcad.core.features.hole_data import find
    from fdcad.core.features.hole_heads import washer

    size = find("iso", FASTENER_SIZE)
    plain = washer(FASTENER_SIZE)
    assert size is not None and plain is not None
    flats, d, pitch = size.nut_flats, size.diameter, size.pitch
    hole = size.clearance[0]  # ISO 7089 washer hole: the close clearance
    doc = new_document(UnitSystem.MM)
    add_variables(
        doc,
        Flats=(f"{flats:g}mm", flats),
        HeadHeight=(f"{HEX_HEAD_HEIGHT:g}mm", HEX_HEAD_HEIGHT),
        NutHeight=(f"{size.nut_height:g}mm", size.nut_height),
        WasherOD=(f"{plain[0]:g}mm", plain[0]),
        WasherThickness=(f"{plain[1]:g}mm", plain[1]),
    )
    head = SketchBuilder()
    head.hexagon(0, 0, flats, "=Flats")
    hsk = add_sketch(doc, head, {"feature": FRONT}, "Head Sketch")
    add_feature(
        doc, "extrude", "Head", hsk, operation="boss", end_condition="blind",
        depth=length("=HeadHeight", HEX_HEAD_HEIGHT), reverse=False,
    )  # fmt: skip
    top, plane = face_ref(doc, (0.0, 0.0, 1.0))
    shaft = SketchBuilder()
    u, v = to_local(plane, (0.0, 0.0, HEX_HEAD_HEIGHT))
    shaft.circle(u, v, d, f"{d:g}")
    ssk = add_sketch(doc, shaft, top, "Shank Sketch")
    add_feature(
        doc, "extrude", "Shank", ssk, operation="boss", end_condition="blind",
        depth=length("20", 20.0), reverse=False,
    )  # fmt: skip
    # The nut and washer sit below the bolt on planes of their own, centred on their
    # sketch origins like the head, so the saved hexagon points solve exactly in place.
    nut_plane = _offset_plane(doc, "Nut Plane", "-15", -15.0)
    nut = SketchBuilder()
    nut.hexagon(0.0, 0.0, flats, "=Flats")
    nsk = add_sketch(doc, nut, {"feature": nut_plane}, "Nut Sketch")
    add_feature(
        doc, "extrude", "Nut", nsk, operation="boss", end_condition="blind",
        depth=length("=NutHeight", size.nut_height), reverse=False, merge=False,
    )  # fmt: skip
    bore = SketchBuilder()
    bore.circle(0.0, 0.0, size.tap_drill, f"{size.tap_drill:g}")
    bsk = add_sketch(doc, bore, {"feature": nut_plane}, "Nut Hole Sketch")
    add_feature(
        doc, "extrude", "Nut Hole", bsk, operation="cut", end_condition="blind",
        depth=length("=NutHeight", size.nut_height), reverse=False,
    )  # fmt: skip
    washer_plane = _offset_plane(doc, "Washer Plane", "-25", -25.0)
    ring = SketchBuilder()
    ring.circle(0.0, 0.0, plain[0], "=WasherOD")
    ring.circle(0.0, 0.0, hole, f"{hole:g}")
    wsk = add_sketch(doc, ring, {"feature": washer_plane}, "Washer Sketch")
    add_feature(
        doc, "extrude", "Washer", wsk, operation="boss", end_condition="blind",
        depth=length("=WasherThickness", plain[1]), reverse=False, merge=False,
    )  # fmt: skip
    for name, edge, run in (
        ("Bolt Thread", _round_edge(d / 2, HEX_HEAD_HEIGHT + 20.0), 16.0),
        ("Nut Thread", _round_edge(size.tap_drill / 2, size.nut_height - 15.0), size.nut_height),
    ):
        doc.features.append(
            Feature(
                doc.new_feature_id(),
                "cosmetic_thread",
                name,
                params={
                    "diameter": length(f"{d:g}", d),
                    "pitch": length(f"{pitch:g}", pitch),
                    "end_condition": "blind",
                    "length": length(f"{run:g}", run),
                },
                refs={"edge": [edge_ref(doc, edge)]},
            )
        )
    return doc


PRINT_SAMPLES: dict[str, Callable[[], Document]] = {
    "fit_test_plate": fit_test_plate,
    "living_hinge_strip": living_hinge_strip,
    "storage_bin": storage_bin,
    "nut_and_bolt": nut_and_bolt,
    "print_in_place_hinge": print_in_place_hinge,
    "bin_base_grid": bin_base_grid,
    "hex_fasteners": hex_fasteners,  # TR162 item 1 (D2409)
}
