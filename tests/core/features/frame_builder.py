"""A road bike frame, built the way a user would: layout sketch, tubes, stays, dropouts,
mirror, bores, joint fillets and small fittings. Support for ``test_frame_part.py``.

Side view in the Front plane: X forward, Y up, Z across the bike. The bottom bracket
is at the origin.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepGProp import BRepGProp
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
from OCP.GProp import GProp_GProps

from fdcad.core.features.hole import defaults_for
from fdcad.core.naming.names import centroid
from fdcad.core.naming.select import reference_for
from fdcad.core.sketch.model import Sketch
from fdcad.core.sketch.text import SketchText
from tests.core.features.frame_harness import FRONT, TOP, Build, Fixed, deg, mm, num

Vec = tuple[float, float]
Vec3 = tuple[float, float, float]


@dataclass
class Size:
    """Frame geometry, in mm and degrees."""

    seat_angle: float = 73.0
    seat_tube: float = 520.0
    head_angle: float = 73.0
    head_tube: float = 150.0
    reach: float = 385.0
    stack: float = 565.0
    chain_stay: float = 410.0
    bb_drop: float = 70.0
    axle_half: float = 65.0  # half of the 130 mm rear hub width


SIZES = {
    "m": Size(),
    "s": Size(74.0, 480.0, 71.5, 150.0, 372.0, 540.0, 405.0, 72.0),
    "l": Size(73.0, 560.0, 73.5, 180.0, 395.0, 595.0, 410.0, 68.0),
    "xl": Size(72.5, 600.0, 74.0, 210.0, 405.0, 625.0, 415.0, 67.0),
}


def along(a: Vec, d: Vec, s: float, n: float = 0.0) -> Vec:
    """``a`` moved ``s`` along unit ``d`` and ``n`` to its left."""
    return (a[0] + s * d[0] - n * d[1], a[1] + s * d[1] + n * d[0])


def unit(a: Vec, b: Vec) -> Vec:
    length = math.dist(a, b)
    return ((b[0] - a[0]) / length, (b[1] - a[1]) / length)


def oval(sk: Fixed, c: Vec, x_is_across: bool, across: float, in_plane: float) -> str:
    """An ellipse with half width ``across`` the bike and ``in_plane`` in the frame's
    plane. The major axis is always the longer one."""
    along_x = across if x_is_across else in_plane
    along_y = in_plane if x_is_across else across
    if along_x >= along_y:
        return sk.ellipse(c, along_x, along_y, 0.0)
    return sk.ellipse(c, along_y, along_x, math.pi / 2)


def slot_arc(sk, centre: Vec, a: Vec, b: Vec):  # type: ignore[no-untyped-def]
    """The short arc about ``centre`` between ``a`` and ``b``; nothing is fixed."""
    r = math.dist(centre, a)
    a0 = math.atan2(a[1] - centre[1], a[0] - centre[0])
    a1 = math.atan2(b[1] - centre[1], b[0] - centre[0])
    if (a1 - a0) % (2 * math.pi) > math.pi + 1e-9:
        a0, a1 = a1, a0
    return sk.entities[sk.add_arc(centre[0], centre[1], r, a0, a1)]


def join(sk, arc, p_a: str, p_b: str, tangent_to: str) -> None:  # type: ignore[no-untyped-def]
    """Tie an arc's ends to the fixed points ``p_a`` and ``p_b`` (whichever is nearer
    each end) and make it tangent to a line, which fixes its centre."""

    def gap(p: str, q: str) -> float:
        return math.dist(sk.xy(p), sk.xy(q))

    if gap(arc.start, p_a) < gap(arc.start, p_b):
        sk.relate("coincident", arc.start, p_a)
        sk.relate("coincident", arc.end, p_b)
    else:
        sk.relate("coincident", arc.start, p_b)
        sk.relate("coincident", arc.end, p_a)
    sk.relate("tangent", arc.id, tangent_to)


def area(face) -> float:  # type: ignore[no-untyped-def]
    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, props)
    return props.Mass()


class Frame:
    def __init__(self, size: Size) -> None:
        self.b = Build()
        self.s = size
        sa, ha = math.radians(size.seat_angle), math.radians(size.head_angle)
        self.bb: Vec = (0.0, 0.0)
        self.seat_dir: Vec = (-math.cos(sa), math.sin(sa))
        self.seat_top = along(self.bb, self.seat_dir, size.seat_tube)
        self.head_top: Vec = (size.reach, size.stack)
        self.head_dir: Vec = (math.cos(ha), -math.sin(ha))
        self.head_bot = along(self.head_top, self.head_dir, size.head_tube)
        self.tt_seat = along(self.bb, self.seat_dir, size.seat_tube - 40.0)
        self.tt_head = along(self.head_top, self.head_dir, 40.0)
        self.dt_head = along(self.head_bot, self.head_dir, -58.0)
        self.axle: Vec = (-math.sqrt(size.chain_stay**2 - size.bb_drop**2), size.bb_drop)
        self.ss_seat = along(self.bb, self.seat_dir, size.seat_tube - 50.0)

    # Stage 1: the main triangle -----------------------------------------------------

    def layout(self) -> None:
        b = self.b
        sk = Fixed()
        self.l_seat = sk.line(self.bb, self.seat_top, construction=True)
        self.l_head = sk.line(self.head_top, self.head_bot, construction=True)
        self.l_top = sk.line(self.tt_seat, self.tt_head, construction=True)
        self.l_down = sk.line(self.bb, self.dt_head, construction=True)
        self.l_chain = sk.line(self.bb, self.axle, construction=True)
        self.l_stay = sk.line(self.ss_seat, self.axle, construction=True)
        self.lay = b.sketch("Frame Layout", {"feature": FRONT}, sk)
        self.lay_sk = sk.sk

    def lay_ref(self, eid: str) -> dict[str, str]:
        return {"feature": self.lay, "sketch_entity": eid}

    def end_point(self, line: str, end: int) -> dict[str, str]:
        ent = self.lay_sk.entities[line]
        return self.lay_ref(ent.p1 if end == 1 else ent.p2)  # type: ignore[union-attr]

    def normal_plane(self, name: str, line: str, end: int) -> str:
        """A plane square to a layout line at one of its ends."""
        return self.b.add(
            "ref_plane", name,
            {"first": self.lay_ref(line), "second": self.end_point(line, end)},
            method="normal_to_curve",
        )  # fmt: skip

    def stay_plane(self, name: str, line: str) -> str:
        """The plane through a layout line and the bike's cross direction."""
        return self.b.add(
            "ref_plane", name, {"first": {"feature": FRONT}, "second": self.lay_ref(line)},
            method="angle", angle=deg(90),
        )  # fmt: skip

    def bb_shell(self) -> None:
        b = self.b
        sk = Fixed()
        sk.circle(self.bb, 42.0)
        s = b.sketch("BB Shell Sketch", {"feature": FRONT}, sk)
        self.shell = b.add(
            "extrude", "BB Shell", {"sketch": {"feature": s}},
            operation="boss", end_condition="mid_plane", depth=mm(68), reverse=False,
        )  # fmt: skip

    def seat_tube(self) -> None:
        b = self.b
        self.p_seat = self.normal_plane("Seat Tube Top Plane", self.l_seat, 2)
        sk = Fixed()
        sk.circle(b.local(self.p_seat, (*self.seat_top, 0.0)), 32.0)
        s = b.sketch("Seat Tube Sketch", {"feature": self.p_seat}, sk)
        n = b.plane(self.p_seat).normal
        down = n[0] * self.seat_dir[0] + n[1] * self.seat_dir[1] > 0  # the normal points up
        self.seat = b.add(
            "extrude", "Seat Tube", {"sketch": {"feature": s}},
            operation="boss", end_condition="blind", depth=mm(self.s.seat_tube), reverse=down,
        )  # fmt: skip

    def head_tube(self) -> None:
        b = self.b
        sk = Fixed()
        length = self.s.head_tube
        # A straight 48 mm tube with a 2 mm lip at each end.
        profile = [(0, 0), (0, 26), (6, 26), (6, 24), (length - 8, 24), (length - 8, 26),
                   (length, 26), (length, 0)]  # fmt: skip
        pts = [along(self.head_top, self.head_dir, s, r) for s, r in profile]
        lines = sk.polygon(pts)
        axis = lines[-1]  # the side on the axis
        s = b.sketch("Head Tube Profile", {"feature": FRONT}, sk)
        self.head = b.add(
            "revolve", "Head Tube", {"sketch": {"feature": s}, "axis": {"sketch_entity": axis}},
            operation="boss", direction="one_direction", angle=deg(360), reverse=False,
        )  # fmt: skip

    def top_tube(self) -> None:
        b = self.b
        self.p_top = self.normal_plane("Top Tube Start Plane", self.l_top, 1)
        sk = Fixed()
        c = b.local(self.p_top, (*self.tt_seat, 0.0))
        across = abs(b.plane(self.p_top).x_dir[2]) > 0.5  # the sketch X axis runs across
        oval(sk, c, across, 15.0, 17.0)
        prof = b.sketch("Top Tube Profile", {"feature": self.p_top}, sk)
        path = Fixed()
        path.line(self.tt_seat, self.tt_head)
        self.top_path = b.sketch("Top Tube Path", {"feature": FRONT}, path)
        self.top = b.add(
            "sweep", "Top Tube", {"profile": {"feature": prof}, "path": {"feature": self.top_path}},
            operation="boss",
        )  # fmt: skip

    def down_tube(self) -> None:
        b = self.b
        self.p_down1 = self.normal_plane("Down Tube BB Plane", self.l_down, 1)
        self.p_down2 = self.normal_plane("Down Tube Head Plane", self.l_down, 2)
        sk1 = Fixed()
        across = abs(b.plane(self.p_down1).x_dir[2]) > 0.5
        oval(sk1, b.local(self.p_down1, (*self.bb, 0.0)), across, 24.0, 18.0)  # wide across
        s1 = b.sketch("Down Tube BB Section", {"feature": self.p_down1}, sk1)
        sk2 = Fixed()
        sk2.circle(b.local(self.p_down2, (*self.dt_head, 0.0)), 40.0)
        s2 = b.sketch("Down Tube Head Section", {"feature": self.p_down2}, sk2)
        self.down = b.add(
            "loft", "Down Tube", {"profiles": [{"feature": s1}, {"feature": s2}]},
            operation="boss",
        )  # fmt: skip

    # Stage 2: the rear triangle, right side (+Z), then mirrored ------------------------

    def end_cap_ref(self, fid: str) -> dict:
        """The flat end face of a sweep that is farthest from the bottom bracket."""
        b = self.b
        caps = b.faces(lambda n, _f: n.startswith(f"{fid}/cap/"))
        far = max(caps, key=lambda f: math.hypot(*centroid(f)[:2]))
        ref = reference_for(b.body, far)
        assert ref is not None
        return ref

    def chain_stay(self) -> None:
        b = self.b
        self.p_cs = self.stay_plane("Chain Stay Plane", self.l_chain)
        d = unit(self.bb, self.axle)
        end_s = self.s.chain_stay - 24.0
        theta, radius = math.radians(12.0), 150.0
        z0, z1 = 25.0, self.s.axle_half
        rise = 2 * radius * (1 - math.cos(theta))
        mid = (z1 - z0 - rise) / math.sin(theta)

        def at(s: float, z: float) -> Vec:
            x, y = along(self.bb, d, s)
            return b.local(self.p_cs, (x, y, z))

        s0, s1 = 14.0, 80.0
        s2, zb = s1 + radius * math.sin(theta), z0 + radius * (1 - math.cos(theta))
        s3, zc = s2 + mid * math.cos(theta), zb + mid * math.sin(theta)
        s4 = s3 + radius * math.sin(theta)
        assert s4 < end_s - 20, (s4, end_s)
        path = Fixed()
        sk = path.sk
        l1 = sk.entities[sk.add_line(*at(s0, z0), *at(s1, z0))]
        l2 = sk.entities[sk.add_line(*at(s2, zb), *at(s3, zc))]
        l3 = sk.entities[sk.add_line(*at(s4, z1), *at(end_s, z1))]
        for line in (l1, l2, l3):
            sk.relate("fixed", line.p1)
            sk.relate("fixed", line.p2)
        a1 = slot_arc(sk, at(s1, z0 + radius), at(s1, z0), at(s2, zb))
        a2 = slot_arc(sk, at(s4, z1 - radius), at(s3, zc), at(s4, z1))
        join(sk, a1, l1.p2, l2.p1, l1.id)
        join(sk, a2, l2.p2, l3.p1, l3.id)
        self.cs_path = b.sketch("Chain Stay Path", {"feature": self.p_cs}, path)
        self.p_cs0 = b.add(
            "ref_plane", "Chain Stay Start Plane",
            {"first": {"feature": self.cs_path, "sketch_entity": l1.id},
             "second": {"feature": self.cs_path, "sketch_entity": l1.p1}},
            method="normal_to_curve",
        )  # fmt: skip
        prof = Fixed()
        x, y = along(self.bb, d, s0)
        across = abs(b.plane(self.p_cs0).x_dir[2]) > 0.5
        oval(prof, b.local(self.p_cs0, (x, y, z0)), across, 7.0, 12.0)
        psk = b.sketch("Chain Stay Profile", {"feature": self.p_cs0}, prof)
        self.cs = b.add(
            "sweep", "Right Chain Stay",
            {"profile": {"feature": psk}, "path": {"feature": self.cs_path}},
            operation="boss", scale_end=num(0.62),
        )  # fmt: skip
        self.cs_dome = b.add(
            "dome", "Chain Stay End", {"faces": [self.end_cap_ref(self.cs)]},
            distance=mm(5), continuous=True,
        )  # fmt: skip

    def seat_stay(self) -> None:
        b = self.b
        self.p_ss = self.stay_plane("Seat Stay Plane", self.l_stay)
        d = unit(self.ss_seat, self.axle)
        length = math.dist(self.ss_seat, self.axle)
        path = Fixed()

        def at(s: float, z: float) -> Vec:
            x, y = along(self.ss_seat, d, s)
            return b.local(self.p_ss, (x, y, z))

        self.ss_z0, self.ss_end = 8.5, length - 24.0
        path.line(at(-4.0, self.ss_z0), at(self.ss_end, self.s.axle_half))
        self.ss_path = b.sketch("Seat Stay Path", {"feature": self.p_ss}, path)
        self.ss = b.add(
            "sweep", "Right Seat Stay", {"path": {"feature": self.ss_path}},
            operation="boss", profile_type="circular", diameter=mm(12), scale_end=num(0.85),
        )  # fmt: skip
        self.ss_dome = b.add(
            "dome", "Seat Stay End", {"faces": [self.end_cap_ref(self.ss)]}, distance=mm(4.5),
            continuous=True,
        )  # fmt: skip

    def dropout(self) -> None:
        b = self.b
        half = self.s.axle_half
        self.p_drop = b.add(
            "ref_plane", "Right Dropout Plane", {"first": {"feature": FRONT}},
            method="offset", distance=mm(half - 3.0),
        )  # fmt: skip
        z = b.plane(self.p_drop).origin[2]
        assert abs(z - (half - 3.0)) < 1e-6, z
        self.drop_z = z
        ax, ay = self.axle
        outline = [(-20, -16), (12, -16), (40, -8), (40, 10), (24, 24), (14, 46), (-4, 46),
                   (-20, 18)]  # fmt: skip
        sk = Fixed()
        sk.polygon([b.local(self.p_drop, (ax + x, ay + y, z)) for x, y in outline])
        s = b.sketch("Dropout Outline", {"feature": self.p_drop}, sk)
        self.drop = b.add(
            "extrude", "Right Dropout", {"sketch": {"feature": s}},
            operation="boss", end_condition="blind", depth=mm(6), reverse=False,
        )  # fmt: skip
        side = f"{self.drop}/side/"
        corners = b.edges_between(lambda n: n.startswith(side), lambda n: n.startswith(side))
        self.drop_fillet = b.add(
            "fillet", "Dropout Corners", {"edges": b.edge_refs(corners)},
            fillet_type="constant", radius=mm(4),
        )  # fmt: skip
        # The axle slot: a 10 mm slot open at the bottom.
        slot = Fixed()
        pts = [(5, 0), (5, -30), (-5, -30), (-5, 0)]
        loc = [b.local(self.p_drop, (ax + x, ay + y, z)) for x, y in pts]
        sk2 = slot.sk
        lines = [sk2.entities[sk2.add_line(*loc[i], *loc[i + 1])] for i in range(3)]
        for i in range(2):
            sk2.relate("coincident", lines[i].p2, lines[i + 1].p1)
        for line in lines:
            sk2.relate("fixed", line.p1)
        sk2.relate("fixed", lines[2].p2)
        arc = slot_arc(sk2, b.local(self.p_drop, (ax, ay, z)), loc[0], loc[3])
        join(sk2, arc, lines[0].p1, lines[2].p2, lines[0].id)
        ssk = b.sketch("Axle Slot Sketch", {"feature": self.p_drop}, slot)
        self.slot = b.add(
            "extrude", "Axle Slot", {"sketch": {"feature": ssk}},
            operation="cut", end_condition="blind", depth=mm(6), reverse=False,
        )  # fmt: skip

    def mirror(self) -> None:
        b = self.b
        seeds = [self.cs, self.cs_dome, self.ss, self.ss_dome, self.drop, self.drop_fillet,
                 self.slot]  # fmt: skip
        self.mir = b.add(
            "mirror", "Left Side",
            {"plane": {"feature": FRONT}, "features": [{"feature": f} for f in seeds]},
            geometry=True,
        )  # fmt: skip

    def bridges(self) -> None:
        b = self.b
        d = unit(self.ss_seat, self.axle)
        s = 110.0
        self.bridge_s = s
        zc = self.ss_z0 + (self.s.axle_half - self.ss_z0) * (s + 4.0) / (self.ss_end + 4.0)
        x, y = along(self.ss_seat, d, s)
        line = Fixed()
        line.line(b.local(self.p_ss, (x, y, -zc)), b.local(self.p_ss, (x, y, zc)))
        sk = b.sketch("Brake Bridge Path", {"feature": self.p_ss}, line)
        self.bridge = b.add(
            "pipe", "Brake Bridge", {"path": {"feature": sk}},
            operation="boss", outer_diameter=mm(9),
        )  # fmt: skip
        dc = unit(self.bb, self.axle)
        x, y = along(self.bb, dc, 62.0)
        line2 = Fixed()
        line2.line(b.local(self.p_cs, (x, y, -25.0)), b.local(self.p_cs, (x, y, 25.0)))
        sk2 = b.sketch("Chain Stay Bridge Path", {"feature": self.p_cs}, line2)
        self.cs_bridge = b.add(
            "pipe", "Chain Stay Bridge", {"path": {"feature": sk2}},
            operation="boss", outer_diameter=mm(14), inner_diameter=mm(11),
        )  # fmt: skip

    # Stage 3: bores --------------------------------------------------------------------

    def directed(
        self, ftype: str, name: str, refs: dict, probe: Vec3, solid_after: bool, **params: object
    ) -> str:
        """Add a feature and, like a user looking at the preview arrow, flip its
        direction when the probe point did not end up solid (or empty) as wanted."""
        b = self.b
        keep = b.skip_failed
        b.skip_failed = False
        fid = b.add(ftype, name, refs, reverse=False, **params)
        if not (b.ok(fid) and b.inside(probe) == solid_after):
            b.doc.feature(fid).params["reverse"] = True
            b.rows.pop()
            b.rebuild(fid)
            if b.ok(fid) and b.inside(probe) != solid_after:
                print(f"        NOTE: {name}: neither direction gave the wanted result", flush=True)
        b.skip_failed = keep
        if not b.ok(fid) and keep:
            b.doc.feature(fid).suppressed = True
            b.rebuild()
        return fid

    def bores(self) -> None:
        b = self.b
        sk = Fixed()
        sk.circle(self.bb, 34.0)
        s = b.sketch("BB Bore Sketch", {"feature": FRONT}, sk)
        self.bb_bore = b.add(
            "extrude", "BB Bore", {"sketch": {"feature": s}},
            operation="cut", end_condition="through_all_both", depth=mm(1), reverse=False,
        )  # fmt: skip
        sk = Fixed()
        sk.circle(b.local(self.p_seat, (*self.seat_top, 0.0)), 27.2)
        s = b.sketch("Seat Tube Bore Sketch", {"feature": self.p_seat}, sk)
        probe = (*along(self.bb, self.seat_dir, self.s.seat_tube - 60.0), 0.0)
        self.seat_bore = self.directed(
            "extrude", "Seat Tube Bore", {"sketch": {"feature": s}}, probe, False,
            operation="cut", end_condition="blind", depth=mm(self.s.seat_tube - 8.0),
        )  # fmt: skip
        # Head tube: the steerer bore, then the two bearing seats in one revolved cut.
        self.p_head = self.normal_plane("Head Tube Top Plane", self.l_head, 1)
        sk = Fixed()
        sk.circle(b.local(self.p_head, (*self.head_top, 0.0)), 38.0)
        s = b.sketch("Head Bore Sketch", {"feature": self.p_head}, sk)
        probe = (*along(self.head_top, self.head_dir, self.s.head_tube / 2), 0.0)
        self.head_bore = self.directed(
            "extrude", "Head Tube Bore", {"sketch": {"feature": s}}, probe, False,
            operation="cut", end_condition="blind", depth=mm(self.s.head_tube + 2.0),
        )  # fmt: skip
        length = self.s.head_tube
        sk = Fixed()
        top = [(0, 0), (0, 22), (10, 22), (10, 0)]
        bottom = [(length - 12, 0), (length - 12, 22), (length, 22), (length, 0)]
        sk.polygon([along(self.head_top, self.head_dir, a, r) for a, r in top])
        sk.polygon([along(self.head_top, self.head_dir, a, r) for a, r in bottom])
        axis = sk.line(self.head_top, self.head_bot, construction=True)
        s = b.sketch("Bearing Seats Profile", {"feature": FRONT}, sk)
        self.seats = b.add(
            "revolve", "Bearing Seats", {"sketch": {"feature": s}, "axis": {"sketch_entity": axis}},
            operation="cut", direction="one_direction", angle=deg(360), reverse=False,
        )  # fmt: skip
        # Hollow top tube: a cut sweep along the same path.
        sk = Fixed()
        across = abs(b.plane(self.p_top).x_dir[2]) > 0.5
        oval(sk, b.local(self.p_top, (*self.tt_seat, 0.0)), across, 13.8, 15.8)
        s = b.sketch("Top Tube Inside Profile", {"feature": self.p_top}, sk)
        self.top_in = b.add(
            "sweep", "Top Tube Inside",
            {"profile": {"feature": s}, "path": {"feature": self.top_path}},
            operation="cut",
        )  # fmt: skip
        # Hollow down tube: a cut loft inside the first.
        sk1 = Fixed()
        across = abs(b.plane(self.p_down1).x_dir[2]) > 0.5
        oval(sk1, b.local(self.p_down1, (*self.bb, 0.0)), across, 22.6, 16.6)
        s1 = b.sketch("Down Tube Inside BB Section", {"feature": self.p_down1}, sk1)
        sk2 = Fixed()
        sk2.circle(b.local(self.p_down2, (*self.dt_head, 0.0)), 37.2)
        s2 = b.sketch("Down Tube Inside Head Section", {"feature": self.p_down2}, sk2)
        self.down_in = b.add(
            "loft", "Down Tube Inside", {"profiles": [{"feature": s1}, {"feature": s2}]},
            operation="cut",
        )  # fmt: skip

    # Stage 4: weld fillets at the joints ----------------------------------------------

    def of(self, *fids: str):  # type: ignore[no-untyped-def]
        """A test for face names made by any of these features."""
        keys = [f"{f}/" for f in fids]
        return lambda name: any(name.startswith(k) for k in keys)

    def sides(self, *fids: str):  # type: ignore[no-untyped-def]
        """A test for the side faces (not the end caps) of these features."""
        keys = [f"{f}/side/" for f in fids]
        return lambda name: any(name.startswith(k) for k in keys)

    def weld(self, name: str, pairs: list, r: float, both_sides: bool = False) -> str:
        """Round the edges where two features meet. With ``both_sides`` the same edges
        on the mirrored (left) side are picked too, as a user would click them."""
        b = self.b
        edges = []
        for one, two in pairs:
            first = one if callable(one) else self.of(*one)
            second = two if callable(two) else self.of(*two)
            for edge in b.edges_between(first, second):
                if not any(edge.IsSame(e) for e in edges):
                    edges.append(edge)
        if both_sides:
            for edge in b.mirrored(edges):
                if not any(edge.IsSame(e) for e in edges):
                    edges.append(edge)
        refs = b.edge_refs(edges)
        if not refs:
            print(f"        NOTE: {name}: no edges found between the two features", flush=True)
            return ""
        keep = b.skip_failed
        b.skip_failed = False
        fid = b.add("fillet", name, {"edges": refs}, fillet_type="constant", radius=mm(r))
        b.rows[-1]["edges"] = len(refs)
        if not b.ok(fid):
            b.click_fix(fid, "Fillet the rest")  # what the error offers; the user clicks it
        b.skip_failed = keep
        if not b.ok(fid) and keep:
            b.doc.feature(fid).suppressed = True
            b.rows[-1]["suppressed"] = True
            b.rebuild()
        return fid

    def welds(self) -> None:
        one = lambda *f: tuple(f)  # noqa: E731
        drop_caps = lambda n: n.startswith(f"{self.drop}/cap/")  # noqa: E731
        self.w = [
            self.weld("Weld Top Tube to Head Tube", [(one(self.top), one(self.head))], 5.0),
            self.weld("Weld Top Tube to Seat Tube", [(one(self.top), one(self.seat))], 5.0),
            self.weld("Weld Down Tube to Head Tube", [(one(self.down), one(self.head))], 5.0),
            self.weld("Weld Seat Tube to BB", [(one(self.seat), one(self.shell))], 4.0),
            self.weld(
                "Weld Down Tube to BB",
                [(one(self.down), one(self.shell)), (one(self.down), one(self.seat))], 4.0,
            ),
            self.weld("Weld Chain Stays to BB", [(one(self.cs), one(self.shell))], 3.0, True),
            self.weld("Weld Seat Stays to Seat Tube", [(one(self.ss), one(self.seat))], 2.0, True),
            self.weld(
                "Weld Stays to Dropouts",
                [(one(self.cs, self.cs_dome, self.ss, self.ss_dome), drop_caps)], 1.5, True,
            ),
            self.weld(
                "Weld Bridges",
                [(one(self.bridge), one(self.ss)), (one(self.cs_bridge), one(self.cs))], 2.0, True,
            ),
        ]  # fmt: skip

    # Stage 5: fittings -----------------------------------------------------------------

    def point_sketch(self, name: str, plane: dict, points: list[Vec]) -> tuple[str, list[str]]:
        sk = Sketch()
        ids = []
        for x, y in points:
            pid = sk.add_point(x, y)
            sk.relate("fixed", pid)
            ids.append(pid)
        return self.b.sketch(name, plane, sk), ids

    def tube_face(self, fid: str) -> dict:
        """The largest face a feature made (the tube's wall)."""
        b = self.b
        faces = b.faces(lambda n, _f: n.startswith(f"{fid}/side/"))
        ref = reference_for(b.body, max(faces, key=area))
        assert ref is not None
        return ref

    def bottle_bosses(self) -> None:
        b = self.b
        self.p_dt = self.stay_plane("Down Tube Plane", self.l_down)
        d = unit(self.bb, self.dt_head)
        # A plane 30 mm above the tube, so the boss lands on the tube's upper side.
        above = along(self.bb, d, 250.0, 30.0)
        self.p_boss = b.add(
            "ref_plane", "Bottle Boss Plane", {"first": {"feature": self.p_dt}},
            method="offset", distance=mm(30),
        )  # fmt: skip
        o = b.plane(self.p_boss).origin
        if (o[0] - self.bb[0]) * -d[1] + (o[1] - self.bb[1]) * d[0] < 0:  # it went below
            b.doc.feature(self.p_boss).params["flip"] = True
            b.rows.pop()
            b.rebuild(self.p_boss)
        psk, ids = self.point_sketch(
            "Bottle Boss Position", {"feature": self.p_boss}, [b.local(self.p_boss, (*above, 0.0))]
        )
        self.boss = b.add(
            "mounting_boss", "Bottle Boss",
            {"face": [self.tube_face(self.down)],
             "position": {"feature": psk, "sketch_entity": ids[0]},
             "direction": {"feature": self.p_dt}},
            boss_type="screw_thread", boss_diameter=mm(10), boss_height=mm(2.5),
            hole_diameter=mm(4.2), hole_depth=mm(6), fin_count=num(0),
        )  # fmt: skip
        self.boss_pattern = b.add(
            "linear_pattern", "Bottle Boss Pattern",
            {"direction1": self.lay_ref(self.l_down), "features": [{"feature": self.boss}]},
            spacing1=mm(64), count1=num(2), reverse1=False, geometry=True,
        )  # fmt: skip

    def cable_guides(self) -> None:
        b = self.b
        d = unit(self.tt_seat, self.tt_head)
        sk = Fixed()
        s0 = 110.0
        box = [(s0, -15.5), (s0 + 12, -15.5), (s0 + 12, -22.0), (s0, -22.0)]
        sk.polygon([along(self.tt_seat, d, s, n) for s, n in box])
        s = b.sketch("Cable Guide Sketch", {"feature": FRONT}, sk)
        self.guide = b.add(
            "extrude", "Cable Guide", {"sketch": {"feature": s}},
            operation="boss", end_condition="mid_plane", depth=mm(8), reverse=False,
        )  # fmt: skip
        hole = Fixed()
        hole.circle(along(self.tt_seat, d, s0 + 6, -19.0), 3.0)
        hs = b.sketch("Cable Guide Slot Sketch", {"feature": FRONT}, hole)
        self.guide_hole = b.add(
            "extrude", "Cable Guide Slot", {"sketch": {"feature": hs}},
            operation="cut", end_condition="mid_plane", depth=mm(8), reverse=False,
        )  # fmt: skip
        self.guide_pattern = b.add(
            "linear_pattern", "Cable Guide Pattern",
            {"direction1": self.lay_ref(self.l_top),
             "features": [{"feature": self.guide}, {"feature": self.guide_hole}]},
            spacing1=mm(140), count1=num(3), reverse1=False,
        )  # fmt: skip

    def seat_clamp(self) -> None:
        b = self.b
        self.p_st = self.stay_plane("Seat Tube Plane", self.l_seat)
        rear = (-self.seat_dir[1], self.seat_dir[0])
        top = self.s.seat_tube

        def at(s: float, z: float) -> Vec:
            x, y = along(self.bb, self.seat_dir, s)
            return b.local(self.p_st, (x, y, z))

        sk = Fixed()
        sk.polygon([at(top - 30, -1.25), at(top + 2, -1.25), at(top + 2, 1.25), at(top - 30, 1.25)])
        s = b.sketch("Clamp Slot Sketch", {"feature": self.p_st}, sk)
        wall = along(along(self.bb, self.seat_dir, top - 10), rear, 14.8)
        self.clamp_slot = self.directed(
            "extrude", "Clamp Slot", {"sketch": {"feature": s}}, (*wall, 0.0), False,
            operation="cut", end_condition="blind", depth=mm(20),
        )  # fmt: skip
        sk = Fixed()
        sk.circle(at(top - 30, 0.0), 5.0)
        s = b.sketch("Slot Relief Sketch", {"feature": self.p_st}, sk)
        wall = along(along(self.bb, self.seat_dir, top - 30), rear, 14.8)
        # 2 mm across, where the slot (2.5 mm wide) is not: at the middle the slot had
        # already opened the wall, so a hole cut forward, into the top tube's hollow,
        # passed the test and removed nothing (D1086 said so).
        self.clamp_relief = self.directed(
            "extrude", "Slot Relief Hole", {"sketch": {"feature": s}}, (*wall, 2.0), False,
            operation="cut", end_condition="blind", depth=mm(20),
        )  # fmt: skip

    def head_badge(self) -> None:
        b = self.b
        self.p_hd = self.stay_plane("Head Tube Plane", self.l_head)
        faces = [
            f for f in b.faces(lambda n, _f: n.startswith(f"{self.head}/side/"))
            if BRepAdaptor_Surface(f).GetType() == GeomAbs_Cylinder
            and abs(BRepAdaptor_Surface(f).Cylinder().Radius() - 24.0) < 1e-6
        ]  # fmt: skip
        wall = reference_for(b.body, max(faces, key=area))
        assert wall is not None
        forward = (-self.head_dir[1], self.head_dir[0])
        if forward[0] < 0:
            forward = (-forward[0], -forward[1])
        mid = along(self.head_top, self.head_dir, self.s.head_tube * 0.47)
        want = (mid[0] + 24 * forward[0], mid[1] + 24 * forward[1], 0.0)
        # A point in front of the head tube picks the side the tangent plane touches.
        ahead = (mid[0] + 60 * forward[0], mid[1] + 60 * forward[1])
        psk, ids = self.point_sketch("Badge Side Point", {"feature": FRONT}, [ahead])
        refs = {"first": wall, "second": {"feature": psk, "sketch_entity": ids[0]}}
        self.p_badge = b.add("ref_plane", "Badge Plane", refs, method="tangent")
        o = b.plane(self.p_badge).origin
        if (o[0] - mid[0]) * forward[0] + (o[1] - mid[1]) * forward[1] < 0:
            print("        NOTE: the badge plane is behind the head tube", flush=True)
        c = b.local(self.p_badge, want)
        tip = b.local(self.p_badge, (want[0] + self.head_dir[0], want[1] + self.head_dir[1], 0.0))
        sk = Fixed()
        sk.ellipse(c, 15.0, 8.0, math.atan2(tip[1] - c[1], tip[0] - c[0]))
        s = b.sketch("Head Badge Sketch", {"feature": self.p_badge}, sk)
        self.badge = b.add(
            "wrap", "Head Badge", {"sketch": {"feature": s}, "face": [wall]},
            wrap_type="emboss", thickness=mm(0.8), method="analytical",
        )  # fmt: skip

    def down_tube_text(self) -> None:
        b = self.b
        d = unit(self.bb, self.dt_head)
        length = math.dist(self.bb, self.dt_head)
        start = along(self.bb, d, length * 0.52, -5.0)
        sk = Sketch()
        sk.texts.append(
            SketchText("t1", "FDCAD", x=start[0], y=start[1], height=10.0,
                       angle=math.atan2(d[1], d[0]), bold=True)
        )  # fmt: skip
        s = b.sketch("Down Tube Text Sketch", {"feature": FRONT}, sk)
        faces = b.faces(lambda n, _f: n.startswith(f"{self.down}/side/"))
        face = reference_for(b.body, max(faces, key=area))
        self.text = b.add(
            "wrap", "Down Tube Text", {"sketch": {"feature": s}, "face": [face]},
            wrap_type="deboss", thickness=mm(0.4), method="project",
        )  # fmt: skip

    def face_local(self, face_ref: dict, p: Vec3) -> Vec:
        """Sketch coordinates of a model point on the plane a sketch on this face gets."""
        from fdcad.core.features.sketch import face_plane
        from fdcad.core.naming.resolve import resolve_face
        from fdcad.samples.builder import to_local

        face, _issues = resolve_face(self.b.body, face_ref, "probe")
        plane = face_plane(face)
        assert plane is not None
        return to_local(plane, p)

    def hanger(self) -> None:
        b = self.b
        ax, ay = self.axle
        z = self.drop_z
        tab = [(-21, -10), (-8, -10), (-8, -40), (-14, -48), (-21, -42)]
        sk = Fixed()
        sk.polygon([b.local(self.p_drop, (ax + x, ay + y, z)) for x, y in tab])
        s = b.sketch("Hanger Sketch", {"feature": self.p_drop}, sk)
        self.hang = b.add(
            "extrude", "Derailleur Hanger", {"sketch": {"feature": s}},
            operation="boss", end_condition="blind", depth=mm(6), reverse=False,
        )  # fmt: skip
        outer = b.faces(
            lambda n, f: (
                n.startswith(f"{self.hang}/cap/")
                and BRepAdaptor_Surface(f).GetType() == GeomAbs_Plane
                and abs(centroid(f)[2] - (z + 6.0)) < 1e-6
            )
        )
        if not outer:
            print("        NOTE: the hanger has no outer face of its own", flush=True)
            return
        face = reference_for(b.body, outer[0])
        psk, _ids = self.point_sketch(
            "Hanger Hole Position", face, [self.face_local(face, (ax - 14.5, ay - 37.0, z + 6.0))]
        )
        m10 = defaults_for("tapped", "iso", "M10")
        self.hang_hole = b.add(
            "hole", "Hanger Thread M10", {"sketch": {"feature": psk}, "face": [face]},
            hole_type="tapped", standard="iso", size="M10", end_condition="through_all",
            cosmetic_thread=True, **{k: mm(round(v, 6)) for k, v in m10.items()},
        )  # fmt: skip
        edges = b.edges_between(self.sides(self.hang), self.sides(self.hang))
        keep = b.skip_failed
        b.skip_failed = False
        self.hang_fillet = b.add(
            "fillet", "Hanger Corners", {"edges": b.edge_refs(edges)},
            fillet_type="constant", radius=mm(2.5),
        )  # fmt: skip
        if not b.ok(self.hang_fillet):
            b.click_fix(self.hang_fillet, "Fillet the rest")
        b.skip_failed = keep

    def eyelets(self) -> None:
        """An M5 tapped eyelet in each dropout: the left one is put on mirrored faces."""
        b = self.b
        ax, ay = self.axle
        self.eye = []
        for side, label in ((1.0, "Right"), (-1.0, "Left")):
            zf = side * (self.drop_z + 6.0)
            found = b.faces(
                lambda _n, f, zf=zf: BRepAdaptor_Surface(f).GetType() == GeomAbs_Plane
                and abs(centroid(f)[2] - zf) < 1e-6
                and abs(centroid(f)[0] - ax) < 40 and area(f) > 300
            )  # fmt: skip
            if not found:
                print(f"        NOTE: no outer dropout face on the {label} side", flush=True)
                continue
            face = reference_for(b.body, found[0])
            at = self.face_local(face, (ax - 12.0, ay + 12.0, zf))
            psk, _ids = self.point_sketch(f"{label} Eyelet Position", face, [at])
            m5 = defaults_for("tapped", "iso", "M5")
            self.eye.append(b.add(
                "hole", f"{label} Eyelet M5", {"sketch": {"feature": psk}, "face": [face]},
                hole_type="tapped", standard="iso", size="M5", end_condition="up_to_next",
                cosmetic_thread=True, **{k: mm(round(v, 6)) for k, v in m5.items()},
            ))  # fmt: skip

    def small_cuts(self) -> None:
        b = self.b
        # A 6 mm bolt hole through the brake bridge, square to the stays.
        d = unit(self.ss_seat, self.axle)
        x, y = along(self.ss_seat, d, self.bridge_s)
        sk = Fixed()
        sk.circle(b.local(self.p_ss, (x, y, 0.0)), 5.0)
        s = b.sketch("Brake Bolt Sketch", {"feature": self.p_ss}, sk)
        self.brake_hole = b.add(
            "extrude", "Brake Bolt Hole", {"sketch": {"feature": s}},
            operation="cut", end_condition="mid_plane", depth=mm(20), reverse=False,
        )  # fmt: skip
        # A drain hole under the bottom bracket, with the Hole Tool on the Top plane.
        psk, _ids = self.point_sketch("Drain Hole Position", {"feature": TOP}, [(0.0, 0.0)])
        self.drain = b.add(
            "hole", "BB Drain Hole", {"sketch": {"feature": psk}},
            hole_type="simple", end_condition="blind", diameter=mm(6), depth=mm(30),
        )  # fmt: skip
        if b.ok(self.drain) and b.inside((0.0, -19.0, 0.0)):
            print("        NOTE: the drain hole did not open the bottom of the shell", flush=True)

    def finish(self) -> None:
        b = self.b
        # Threads in the bottom bracket shell, both sides (BSA: 1.37 in by 24 threads).
        self.threads = []
        for side, label in ((1.0, "Right"), (-1.0, "Left")):
            rims = [
                e for e in b.edges_between(self.of(self.bb_bore), self.of(self.shell))
                if abs(b.edge_mid(e)[2] - side * 34.0) < 1e-6
            ]  # fmt: skip
            if not rims:
                print(f"        NOTE: no bore rim on the {label} side", flush=True)
                continue
            self.threads.append(b.add(
                "cosmetic_thread", f"{label} BB Thread", {"edge": [b.edge_refs(rims[:1])[0]]},
                standard="iso", size="BSA", diameter=mm(34.798), pitch=mm(1.058),
                end_condition="blind", length=mm(24),
            ))  # fmt: skip
        # Break the sharp rims of the head tube.
        lips = b.faces(
            lambda n, f: (
                n.startswith(f"{self.head}/")
                and BRepAdaptor_Surface(f).GetType() == GeomAbs_Cylinder
                and abs(BRepAdaptor_Surface(f).Cylinder().Radius() - 26.0) < 1e-6
            )
        )
        ends = b.faces(
            lambda n, f: (
                n.startswith(f"{self.head}/") and BRepAdaptor_Surface(f).GetType() == GeomAbs_Plane
            )
        )
        rim = []
        for edge in b.all_edges():
            fs = b.faces_at(edge)
            if any(f.IsSame(x) for f in fs for x in lips) and any(
                f.IsSame(x) for f in fs for x in ends
            ):
                rim.append(edge)
        self.rim_chamfer = b.add(
            "chamfer", "Head Tube Rims", {"edges": b.edge_refs(rim)},
            chamfer_type="distance_distance", distance=mm(0.8),
        )  # fmt: skip

    # Place checks (idea 60) --------------------------------------------------------

    def place_checks(self) -> list[str]:
        """Points that must be solid or empty in the built frame, for the features that
        were built. A feature can build with no error in the wrong place (D1071)."""
        b, s = self.b, self.s
        wrong: list[str] = []

        self.place_count = 0

        def want(what: str, inside: list, outside: list) -> None:
            self.place_count += len(inside) + len(outside)
            bad = [f"no material at {p}" for p in inside if not b.inside(p)]
            bad += [f"material at {p}" for p in outside if b.inside(p)]
            if bad:
                wrong.append(f"{what}: " + "; ".join(bad))

        def built(*names: str) -> bool:
            return all(getattr(self, n, None) for n in names)

        def on(a: Vec, d: Vec, t: float, n: float = 0.0, z: float = 0.0) -> Vec3:
            return (*along(a, d, t, n), z)

        if built("shell", "bb_bore"):
            want("BB Shell and Bore", [(19.0, 0.0, 30.0), (0.0, 19.0, -30.0)],
                 [(0.0, 0.0, 0.0), (0.0, 0.0, 33.0), (0.0, 22.0, 0.0)])  # fmt: skip
        if built("seat", "seat_bore"):
            t = s.seat_tube * 0.55
            want("Seat Tube and Bore", [on(self.bb, self.seat_dir, t, z=14.8)],
                 [on(self.bb, self.seat_dir, t),
                  on(self.bb, self.seat_dir, t, z=16.5)])  # fmt: skip
        if built("head", "head_bore", "seats"):
            mid, top = s.head_tube / 2, 5.0
            want("Head Tube, Bore and Bearing Seats",
                 [on(self.head_top, self.head_dir, mid, z=21.5),
                  on(self.head_top, self.head_dir, top, z=23.0)],
                 [on(self.head_top, self.head_dir, mid, z=18.0),
                  on(self.head_top, self.head_dir, top, z=21.0),
                  on(self.head_top, self.head_dir, mid, z=24.5)])  # fmt: skip
        if built("top", "top_in"):
            d = unit(self.tt_seat, self.tt_head)
            t = math.dist(self.tt_seat, self.tt_head) / 2
            want("Top Tube, hollow", [on(self.tt_seat, d, t, z=14.4)],
                 [on(self.tt_seat, d, t), on(self.tt_seat, d, t, z=15.6)])  # fmt: skip
        if built("down", "down_in"):
            d = unit(self.bb, self.dt_head)
            t = math.dist(self.bb, self.dt_head) * 0.9
            want("Down Tube, hollow", [], [on(self.bb, d, t)])
        if built("cs", "ss", "mir"):
            dc, ds = unit(self.bb, self.axle), unit(self.ss_seat, self.axle)
            t = 0.5 * math.dist(self.ss_seat, self.axle)
            z = self.ss_z0 + (s.axle_half - self.ss_z0) * (t + 4.0) / (self.ss_end + 4.0)
            want("Stays on both sides",
                 [on(self.bb, dc, 40.0, z=25.0), on(self.bb, dc, 40.0, z=-25.0),
                  on(self.ss_seat, ds, t, z=z), on(self.ss_seat, ds, t, z=-z)],
                 [on(self.bb, dc, 40.0, z=0.0), on(self.ss_seat, ds, t, z=0.0)])  # fmt: skip
        if built("drop", "slot", "mir"):
            ax, ay = self.axle
            z = self.drop_z + 3.0
            want("Dropouts and axle slots on both sides",
                 [(ax + 25.0, ay, z), (ax + 25.0, ay, -z)],
                 [(ax, ay - 10.0, z), (ax, ay - 10.0, -z), (ax, ay, z), (ax, ay, -z)])  # fmt: skip
        if built("cs_bridge"):
            x, y = along(self.bb, unit(self.bb, self.axle), 62.0)
            want("Chain Stay Bridge, hollow", [(x, y + 6.25, 0.0), (x, y - 6.25, 0.0)],
                 [(x, y, 0.0), (x, y + 7.5, 0.0)])  # fmt: skip
        if built("guide", "guide_hole", "guide_pattern"):
            d = unit(self.tt_seat, self.tt_head)
            for k in range(3):
                s0 = 110.0 + 140.0 * k
                want(f"Cable Guide {k + 1}", [on(self.tt_seat, d, s0 + 1.5, -21.0)],
                     [on(self.tt_seat, d, s0 + 6.0, -19.0)])  # fmt: skip
        if built("clamp_slot", "clamp_relief"):
            rear = (-self.seat_dir[1], self.seat_dir[0])
            top = s.seat_tube
            want("Clamp Slot and Relief Hole",
                 [(*along(along(self.bb, self.seat_dir, top - 10), rear, -14.8), 0.0),
                  (*along(along(self.bb, self.seat_dir, top - 10), rear, 14.8), 2.0)],
                 [(*along(along(self.bb, self.seat_dir, top - 10), rear, 14.8), 0.0),
                  (*along(along(self.bb, self.seat_dir, top - 30), rear, 14.8), 0.0),
                  (*along(along(self.bb, self.seat_dir, top - 30), rear, 14.8), 2.0)])  # fmt: skip
        if built("hang", "hang_hole"):
            ax, ay = self.axle
            z = self.drop_z + 3.0
            want("Derailleur Hanger", [(ax - 18.0, ay - 20.0, z)], [(ax - 14.5, ay - 37.0, z)])
        if built("eye"):
            ax, ay = self.axle
            z = self.drop_z + 4.5
            want("Eyelets", [(ax - 12.0 + 3.5, ay + 12.0, z)],
                 [(ax - 12.0, ay + 12.0, z)] + ([(ax - 12.0, ay + 12.0, -z)]
                                                if len(self.eye) == 2 else []))  # fmt: skip
        if built("drain"):
            want("BB Drain Hole", [], [(0.0, -19.0, 0.0)])
        return wrong

    STEPS = ("layout", "bb_shell", "seat_tube", "head_tube", "top_tube", "down_tube",
             "chain_stay", "seat_stay", "dropout", "mirror", "bridges", "bores", "welds",
             "bottle_bosses", "cable_guides", "seat_clamp", "head_badge", "down_tube_text",
             "hanger", "eyelets", "small_cuts", "finish")  # fmt: skip

    def build(self, upto: str = "") -> None:
        for step in self.STEPS:
            getattr(self, step)()
            if step == upto:
                break
