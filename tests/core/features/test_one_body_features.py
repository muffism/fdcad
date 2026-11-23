"""Features put on one body leave the other bodies of the part alone (D1077).

Found by putting each feature that hands the whole part to the kernel on a plate, in
a part that also holds a block lying on the plate and two blocks locked together with
Interlock teeth elsewhere (2026-11-12). Lightening Pockets and Living Hinge cut on
through the block lying on the plate; Landing Pad joined the two locked blocks.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

from fdcad.core.features.solids import precise_volume, solids
from tests.core.features.gearbox_builder import Gear, rect
from tests.core.features.gearbox_kit import RIGHT, mm

#: The block lying on the plate, and the two locked blocks: where each is, its volume.
OTHERS = [
    ((60, 10, 10, 90, 50, 20), 12000.0),
    ((240, 340, 0, 280, 380, 12), 16000.0),
    ((240, 340, 8, 280, 380, 20), 16000.0),
]


def _bodies(part: Gear) -> list[tuple[tuple[int, ...], float]]:
    out = []
    for solid in solids(part.b.body.shape):
        box = Bnd_Box()
        BRepBndLib.Add_s(solid, box)
        lo, hi = box.CornerMin(), box.CornerMax()
        where = tuple(round(v) for v in (lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z()))
        out.append((where, round(precise_volume(solid), 3)))
    return sorted(out)


def _part() -> Gear:
    """A 100 by 60 by 10 plate with a round boss, a block lying on it, and two locked blocks."""
    k = Gear()
    k.b.quiet = True
    k.watch_valid = False
    plate = k.box("Plate", 0, 0, 100, 60, 10)
    k.on_top("Cap", plate, 60, 10, 90, 50, 10, 10)
    top = k.fref((20, 30, 10))
    s = k.sketch("Boss Sketch", top, lambda sk, at: sk.circle(at(20, 30, 10), 15))
    k.add("extrude", "Boss", {"sketch": {"feature": s}}, operation="boss", end_condition="blind",
          depth=mm(15), reverse=k.reverse_for(k.fref((40, 5, 10)), (0, 0, 1)))  # fmt: skip
    lower = k.box("Hard Half", 240, 340, 280, 380, 10)
    k.on_top("Soft Half", lower, 240, 340, 280, 380, 10, 10)
    k.add("interlock", "Teeth", {"face": [k.fref((260, 360, 10), of=lower)]},
          tooth_size=mm(5), tooth_depth=mm(2))  # fmt: skip
    assert [b for b in _bodies(k) if b in OTHERS] == OTHERS
    return k


def _pockets_through(k: Gear) -> None:
    k.add("lightening_pockets", "Pockets", {"plate_face": [k.fref((50, 30, 0))]},
          border=mm(8), web=mm(3), cell=mm(24))  # fmt: skip


def _hinge_under_the_block(k: Gear) -> None:
    bottom = k.fref((50, 30, 0))
    s = k.sketch("Area", bottom, lambda sk, at: sk.polygon(rect(at, 62, 14, 0, 88, 46, 0)))
    k.add("living_hinge", "Slits", {"sketch": {"feature": s}},
          slit_length=mm(8), slit_width=mm(1), bridge=mm(3), row_spacing=mm(3))  # fmt: skip


def _pad_on_the_boss(k: Gear) -> None:
    plane = k.offset_plane("Pad Plane", RIGHT, 33, (1, 0, 0))
    s = k.sketch("Pad", plane, lambda sk, at: sk.polygon(rect(at, 33, 26, 14, 33, 34, 22)))
    k.add("landing_pad", "Pad", {"wall_face": [k.fref((27.5, 30, 18))], "sketch": {"feature": s}},
          pad_mode="raise")  # fmt: skip


@pytest.mark.parametrize(
    ("feature", "plate_grows"),
    [(_pockets_through, False), (_hinge_under_the_block, False), (_pad_on_the_boss, True)],
    ids=["lightening_pockets", "living_hinge", "landing_pad"],
)
def test_the_other_bodies_stay_as_they_were(
    feature: Callable[[Gear], None], plate_grows: bool
) -> None:
    k = _part()
    plate_before = next(v for where, v in _bodies(k) if where[:3] == (0, 0, 0))
    feature(k)
    row = k.b.rows[-1]
    assert row["state"] == "OK", row["issues"]
    after = _bodies(k)
    assert len(after) == 4
    assert [b for b in after if b in OTHERS] == OTHERS
    plate_after = next(v for where, v in after if where[:3] == (0, 0, 0))
    assert (plate_after > plate_before) is plate_grows and plate_after != plate_before
