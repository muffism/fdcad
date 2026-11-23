"""Rib, Roof, Vent, split connectors and the joints work on their own body (D2641, idea 52).

Each test builds a part of separate bodies, one of them touching the body the feature
is put on, and checks that the feature changes only its own body: every other body
keeps its place and its volume and stays a body of its own. Rib and Roof fused their
new material with the whole part, which joined the touching body to it (D1055); Vent
cut a little into a body lying under its wall. Split for Printing cut its connector
holes from every body of the part in one call, so a screw hole and its nut trap went
on into a body touching the end of the split bar. Interlock, Joint Helper and Twist
Lock already worked on their bodies one at a time; their tests keep it that way.
"""

from __future__ import annotations

from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

from fdcad.core.features.solids import precise_volume, solids
from tests.core.features.gearbox_builder import Gear, rect
from tests.core.features.gearbox_kit import FRONT, RIGHT, TOP, deg, mm, num

Body = tuple[tuple[int, ...], float]


def _bodies(k: Gear) -> list[Body]:
    """Every body of the part: its box (rounded to whole mm) and its volume."""
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


def _check(k: Gear, others: list[Body], count: int) -> None:
    """The last feature built, the part has ``count`` bodies and ``others`` are untouched."""
    row = k.b.rows[-1]
    assert row["state"] == "OK", row["issues"]
    after = _bodies(k)
    assert [b for b in after if b in others] == others, after
    assert len(after) == count, after


def _other(k: Gear, box: tuple[int, ...]) -> list[Body]:
    found = [b for b in _bodies(k) if b[0] == box]
    assert len(found) == 1, _bodies(k)
    return found


def test_rib_joins_only_its_own_body() -> None:
    """A gusset in the corner of an angle; a block on the angle's floor touches its side."""
    k = _kit()
    floor = k.box("Floor", 0, 0, 60, 40, 5)
    top = k.fref((30, 20, 5), of=floor)
    s = k.sketch("Wall Sketch", top, lambda sk, at: sk.polygon(rect(at, 0, 0, 5, 5, 40, 5)))
    k.add("extrude", "Wall", {"sketch": {"feature": s}}, operation="boss",
          end_condition="blind", depth=mm(35), reverse=False)  # fmt: skip
    k.on_top("Block", floor, 8, 21, 16, 30, 5, 4)
    others = _other(k, (8, 21, 5, 16, 30, 9))
    plane = k.offset_plane("Gusset Plane", TOP, 20, (0, 1, 0))
    s = k.sketch("Gusset Line", plane, lambda sk, at: sk.line(at(5, 20, 25), at(25, 20, 5)))
    k.add("rib", "Gusset", {"sketch": {"feature": s}, "body": [k.fref((30, 20, 5), of=floor)]},
          thickness=mm(2), side="both", direction="parallel", extend="linear")  # fmt: skip
    _check(k, others, 2)


def test_roof_joins_only_the_body_it_was_sketched_on() -> None:
    """A roof cut flat on a plate; a block of its own rests on the roof's flat top."""
    k = _kit()
    plate = k.box("Plate", 0, 0, 60, 40, 10)
    level = k.offset_plane("Block Plane", FRONT, 13, (0, 0, 1))
    s = k.sketch("Block Sketch", level,
                 lambda sk, at: sk.polygon(rect(at, 17, 17, 13, 23, 23, 13)))  # fmt: skip
    k.add("extrude", "Block", {"sketch": {"feature": s}}, operation="boss",
          end_condition="blind", depth=mm(5), reverse=k.reverse_for(level, (0, 0, 1)),
          merge=False)  # fmt: skip
    others = _other(k, (17, 17, 13, 23, 23, 18))
    top = k.fref((5, 5, 10), of=plate)
    s = k.sketch("Roof Outline", top, lambda sk, at: sk.polygon(rect(at, 10, 10, 10, 30, 30, 10)))
    k.add("roof", "Roof", {"sketch": {"feature": s}}, slope=deg(30), max_height=mm(3),
          operation="boss")  # fmt: skip
    _check(k, others, 2)


def test_vent_cuts_and_joins_only_its_wall() -> None:
    """A vent through a plate lying on a block: the ribs reach the block's top."""
    k = _kit()
    under = k.box("Under", 10, 10, 50, 30, 5)
    plate = k.on_top("Plate", under, 0, 0, 60, 40, 5, 5)
    others = _other(k, (10, 10, 0, 50, 30, 5))
    top = lambda: k.fref((55, 35, 10), of=plate)  # noqa: E731
    ids: dict[str, object] = {}

    def vent(sk, at):  # type: ignore[no-untyped-def]
        ids["ring"] = sk.circle(at(30, 20, 10), 8)
        ids["rib"] = sk.line(at(20, 20, 10), at(40, 20, 10))

    s = k.sketch("Vent Sketch", top(), vent)
    pick = lambda e: {"feature": s, "sketch_entity": e}  # noqa: E731
    k.add("vent", "Vent", {"sketch": {"feature": s}, "face": [top()],
                           "boundary": [pick(ids["ring"])], "ribs": [pick(ids["rib"])]},
          rib_width=mm(2), rib_depth=mm(5), rib_offset=mm(0))  # fmt: skip
    _check(k, others, 2)


def test_split_for_print_connectors_stay_in_the_split_body() -> None:
    """Screws through a bar split in two stop at the bar, not in a block at its end."""
    k = _kit()
    k.box("Bar", 0, 0, 100, 20, 15)
    k.box("End Block", 100, 0, 120, 20, 15)
    others = _other(k, (100, 0, 0, 120, 20, 15))
    cut = k.offset_plane("Cut Plane", RIGHT, 50, (1, 0, 0))
    k.add("split_for_print", "Bar In Two", {"planes": [{"feature": cut}]}, mode="planes",
          connector="screws", screw_diameter=mm(3), nut_size=mm(5.5), nut_height=mm(2.4),
          clearance=mm(0.2))  # fmt: skip
    _check(k, others, 3)


def test_split_for_print_pins_leave_a_touching_body() -> None:
    """Pins across the seam of a split bar; a block lies on the bar, away from the seam."""
    k = _kit()
    bar = k.box("Bar", 0, 0, 100, 20, 15)
    k.on_top("Lid", bar, 60, 0, 100, 20, 15, 5)
    others = _other(k, (60, 0, 15, 100, 20, 20))
    cut = k.offset_plane("Cut Plane", RIGHT, 30, (1, 0, 0))
    k.add(
        "split_for_print",
        "Bar In Two",
        {"planes": [{"feature": cut}]},
        mode="planes",
        connector="pins",
        pin_diameter=mm(4),
        pin_length=mm(8),
        clearance=mm(0.2),
    )
    _check(k, others, 4)


def test_interlock_leaves_a_third_body() -> None:
    """Teeth between two halves; a block touches the lower half's side."""
    k = _kit()
    hard = k.box("Hard Half", 0, 0, 40, 40, 10)
    k.on_top("Soft Half", hard, 0, 0, 40, 40, 10, 10)
    k.box("Side Block", 40, 0, 60, 40, 10)
    others = _other(k, (40, 0, 0, 60, 40, 10))
    k.add("interlock", "Teeth", {"face": [k.fref((20, 20, 10), of=hard)]},
          tooth_size=mm(5), tooth_depth=mm(2))  # fmt: skip
    _check(k, others, 3)


def test_joint_helper_leaves_a_third_body() -> None:
    """A mortise between a rail and a post; a block touches the rail's end."""
    k = _kit()
    rail = k.box("Rail", 0, 0, 60, 40, 10)
    post = k.on_top("Post", rail, 20, 10, 40, 30, 10, 30)
    k.box("End Block", 60, 0, 80, 40, 10)
    others = _other(k, (60, 0, 0, 80, 40, 10))
    k.add("joint_helper", "Mortise",
          {"bodies": [k.fref((5, 5, 10), of=rail), k.fref((30, 20, 40), of=post)]},
          joint="mortise", depth=mm(5), shoulder=mm(3), joint_clearance=mm(0.2))  # fmt: skip
    _check(k, others, 3)


def test_twist_lock_leaves_a_third_body() -> None:
    """Lugs on a plug in a socket; a block stands against the socket's side."""
    k = _kit()
    spot = k.frame("Lock Frame", 0, 0, 0)
    plug = k.add("primitive", "Plug", {"frame": spot}, kind="cylinder", operation="boss",
                 diameter=mm(20), height=mm(20), merge=False)  # fmt: skip
    k.add("primitive", "Socket", {"frame": spot}, kind="tube", operation="boss",
          diameter=mm(32), inner=mm(20.6), height=mm(20), merge=False)  # fmt: skip
    k.box("Side Block", 16, -10, 30, 10, 20)
    others = _other(k, (16, -10, 0, 30, 10, 20))
    k.add("twist_lock", "Bayonet", {"face": k.fref((10, 0, 10), of=plug)},
          lug_count=num(3), lug_width=mm(4), lug_height=mm(3), lug_depth=mm(2),
          lock_depth=mm(8), twist=deg(30), lock_clearance=mm(0.3))  # fmt: skip
    _check(k, others, 3)
