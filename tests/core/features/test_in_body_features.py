"""Features put on one body change that body only (IDEAS 62, D2622).

Edge Profile, Ring Groove, O Ring Groove, Shaft Shape, Mark, Lattice Fill and Wrap
handed the whole part to the kernel for their cut or join, the pattern behind D1055,
D1056 and D1078. Each is put here on a body that has a second body touching or near
it; the second body must stay as it was: the same volume, and not joined.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

from fdcad.core.features.solids import precise_volume, solids
from tests.core.features.gearbox_builder import Gear, rect
from tests.core.features.gearbox_kit import FRONT, mm

Box = tuple[int, int, int, int, int, int]


def _bodies(k: Gear) -> list[tuple[Box, float]]:
    out = []
    for solid in solids(k.b.body.shape):
        box = Bnd_Box()
        BRepBndLib.Add_s(solid, box)
        lo, hi = box.CornerMin(), box.CornerMax()
        where = tuple(round(v) for v in (lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z()))
        out.append((where, round(precise_volume(solid), 3)))
    return sorted(out)


def _kit() -> Gear:
    k = Gear()
    k.b.quiet = True
    k.watch_valid = False
    return k


def _round(k: Gear, name: str, inner: float, outer: float, h: float) -> str:
    """A round bar (``inner`` 0) or a tube about the Z axis, standing on the Front plane."""

    def draw(sk, at):  # type: ignore[no-untyped-def]
        sk.circle(at(0, 0, 0), 2 * outer)
        if inner > 0:
            sk.circle(at(0, 0, 0), 2 * inner)

    s = k.sketch(f"{name} Sketch", FRONT, draw)
    return k.add("extrude", name, {"sketch": {"feature": s}}, operation="boss",
                 end_condition="blind", depth=mm(h), reverse=False, merge=False)  # fmt: skip


def _shaft_in_a_hub(k: Gear) -> tuple[str, Box]:
    """A 20 mm shaft 60 long, with a hub round its lower 30 mm as a body of its own."""
    shaft = _round(k, "Shaft", 0, 10, 60)
    _round(k, "Hub", 10, 20, 30)
    return shaft, (-20, -20, 0, 20, 20, 30)


def _edge_profile(k: Gear) -> Box:
    plate = k.box("Plate", 0, 0, 40, 40, 10)
    k.box("Neighbour", 40, 0, 60, 40, 10)  # stands against the plate's side
    k.add("edge_profile", "Round Over", {"loop_face": [k.fref((20, 20, 10), of=plate)]},
          router_profile="round_over", profile_size=mm(3))  # fmt: skip
    return (40, 0, 0, 60, 40, 10)


def _ring_groove(k: Gear) -> Box:
    shaft, hub = _shaft_in_a_hub(k)
    k.add("ring_groove", "Ring", {"face": [k.fref((10, 0, 45), of=shaft)]},
          ring_type="ring", position=mm(10), from_end="end")  # fmt: skip
    return hub


def _oring_groove(k: Gear) -> Box:
    shaft, hub = _shaft_in_a_hub(k)
    k.add("oring_groove", "Seal", {"face": [k.fref((10, 0, 45), of=shaft)]},
          cross_section=mm(2), use="static", position=mm(10), from_end="end")  # fmt: skip
    return hub


def _shaft_flat(k: Gear) -> Box:
    shaft, hub = _shaft_in_a_hub(k)
    k.add("shaft_shape", "Flat", {"face": [k.fref((10, 0, 45), of=shaft)]},
          shaft_form="d_flat", length=mm(20), from_end="end")  # fmt: skip
    return hub


def _bore_hex(k: Gear) -> Box:
    """A hex made in a plate's bore, with a pin standing in the bore as its own body."""
    s = k.sketch("Plate Sketch", FRONT, lambda sk, at: (
        sk.polygon(rect(at, -30, -30, 0, 30, 30, 0)), sk.circle(at(0, 0, 0), 20)))  # fmt: skip
    plate = k.add("extrude", "Plate", {"sketch": {"feature": s}}, operation="boss",
                  end_condition="blind", depth=mm(10), reverse=False, merge=False)  # fmt: skip
    _round(k, "Pin", 0, 10, 30)
    k.add("shaft_shape", "Hex Bore", {"face": [k.fref((10, 0, 5), of=plate)]},
          shaft_form="hex", clearance=mm(0.1))  # fmt: skip
    return (-10, -10, 0, 10, 10, 30)


def _mark(k: Gear) -> Box:
    plate = k.box("Thin Plate", 0, 0, 40, 40, 0.8)
    k.on_top("Block", plate, 10, 10, 30, 30, 0.8, 5)
    s = k.sketch("Mark Sketch", k.fref((5, 5, 0.8), of=plate),
                 lambda sk, at: sk.polygon(rect(at, 15, 15, 0.8, 25, 25, 0.8)))  # fmt: skip
    k.add("mark", "Mark", {"sketch": {"feature": s}}, depth=mm(1))
    return (10, 10, 1, 30, 30, 6)


def _wrap(k: Gear) -> Box:
    plate = k.box("Plate", 0, 0, 40, 40, 10)
    k.on_top("Block", plate, 20, 0, 40, 40, 10, 10)
    s = k.sketch("Label Sketch", k.fref((5, 5, 10), of=plate),
                 lambda sk, at: sk.polygon(rect(at, 5, 10, 10, 20, 30, 10)))  # fmt: skip
    k.add("wrap", "Label", {"sketch": {"feature": s}, "face": [k.fref((5, 5, 10), of=plate)]},
          wrap_type="emboss", thickness=mm(2), method="analytical")  # fmt: skip
    return (20, 0, 10, 40, 40, 20)


def _lattice_one(k: Gear) -> Box:
    slab = k.box("Slab", 0, 0, 20, 20, 20)
    k.box("Neighbour", 20, 0, 40, 20, 20)
    k.add("lattice_fill", "Fill", {"bodies": [k.fref((10, 10, 20), of=slab)]},
          lattice="honeycomb", cell=mm(6), wall=mm(1), skin=mm(1))  # fmt: skip
    return (20, 0, 0, 40, 20, 20)


CASES: dict[str, Callable[[Gear], Box]] = {
    "edge_profile": _edge_profile,
    "ring_groove": _ring_groove,
    "oring_groove": _oring_groove,
    "shaft_shape": _shaft_flat,
    "shaft_shape_bore": _bore_hex,
    "mark": _mark,
    "wrap": _wrap,
    "lattice_fill": _lattice_one,
}


@pytest.mark.parametrize("case", list(CASES))
def test_the_other_body_stays_as_it_was(case: str) -> None:
    k = _kit()
    build = CASES[case]
    # Build the part without the feature first, to know the other body as it was.
    other = build(k)
    row = k.b.rows[-1]
    assert row["state"] != "ERROR", row["issues"]
    after = _bodies(k)
    k.b.doc.features[-1].suppressed = True
    k.b.rebuild()
    before = _bodies(k)
    kept = [b for b in before if b[0] == other]
    assert len(kept) == 1, before
    assert len(after) == len(before), after
    assert kept[0] in after, after
    # The feature did change its own body.
    assert sorted(after) != sorted(before)


def test_lattice_fill_fills_touching_bodies_each_on_its_own() -> None:
    """Two touching blocks filled together stay two bodies, each inside its own box."""
    k = _kit()
    k.box("Left", 0, 0, 20, 20, 20)
    k.box("Right", 20, 0, 40, 20, 20)
    k.add("lattice_fill", "Fill", {}, lattice="honeycomb", cell=mm(6), wall=mm(1),
          skin=mm(1))  # fmt: skip
    row = k.b.rows[-1]
    assert row["state"] != "ERROR", row["issues"]
    after = _bodies(k)
    assert [where for where, _v in after] == [(0, 0, 0, 20, 20, 20), (20, 0, 0, 40, 20, 20)]
    assert all(v < 8000 for _w, v in after)
