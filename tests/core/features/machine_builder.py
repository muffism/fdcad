"""A machine bed: one solid body of 768 features of 72 types (owner request, 2026-11-14).

After the gearbox (318 features in 60 bodies) the owner asked for a single body part,
more complex, with at least 500 features. This is a bed 1400 by 1000 by 40 mm with
twelve pod stations, three shafts on pedestals, three plates of patterns and a yard of
the rest. Every feature joins the one body, the part is one body at every step (no
second body even for a moment, so the body tools and imports are left out), and after
each feature points are checked to be inside or outside the material (``Kit.expect``,
1178 checks), as for the gearbox. It found D1104.

Bed: X 0..1400, Y 0..1000, Z 0..40. Station ``n`` takes the 200 by 200 cell with its
corner at (ox, oy); its pod stands on the bed at X ox+30..ox+170, Y oy+40..oy+160.
"""

from __future__ import annotations

from fdcad.core.document.model import Param
from tests.core.features.gearbox_builder import rect, tapped
from tests.core.features.gearbox_kit import FRONT, RIGHT, TOP, Kit, Sketch, deg, mm, num

BED_Z = 40.0


class Bed(Kit):
    """The machine bed, built one feature at a time."""

    def bed(self) -> None:
        k = self
        s = k.sketch("Bed Outline", FRONT,
                     lambda sk, at: sk.polygon(rect(at, 0, 0, 0, 1400, 1000, 0)))  # fmt: skip
        k.add("extrude", "Bed", {"sketch": {"feature": s}}, operation="boss",
              end_condition="blind", depth=mm(BED_Z), reverse=False)  # fmt: skip
        k.expect("Bed", inside=[(700, 500, 20), (1, 1, 1)], outside=[(700, 500, 41)])
        # On the plain bed the parting line runs round the bottom and crosses no face.
        k.add("parting_line", "Bed Parting Line", {"direction": {"feature": FRONT}})
        self.top_plane = k.offset_plane("Bed Top Plane", FRONT, BED_Z, (0, 0, 1))

    # A work station ---------------------------------------------------------------------

    def station(self, n: int, ox: float, oy: float, h: float) -> None:
        """About 43 features in the cell with its corner at (ox, oy); the pod is ``h`` tall."""
        k = self
        zt = BED_Z + h  # the pod's top
        mid = BED_Z + h / 2

        def p(u: float, v: float, z: float) -> tuple[float, float, float]:
            return (ox + u, oy + v, z)

        name = f"S{n}"
        bed_top = lambda u, v: k.fref(p(u, v, BED_Z))  # noqa: E731
        pod_top = lambda u=100.0, v=100.0: k.fref(p(u, v, zt))  # noqa: E731

        # The pod.
        s = k.sketch(f"{name} Pod Sketch", bed_top(100, 100),
                     lambda sk, at: sk.polygon(rect(at, ox + 30, oy + 40, BED_Z, ox + 170,
                                                    oy + 160, BED_Z)))  # fmt: skip
        k.add("extrude", f"{name} Pod", {"sketch": {"feature": s}}, operation="boss",
              end_condition="blind", depth=mm(h),
              reverse=k.reverse_for(bed_top(100, 100), (0, 0, 1)))  # fmt: skip
        k.expect(f"{name} Pod", inside=[p(100, 100, mid), p(31, 41, zt - 1)],
                 outside=[p(100, 100, zt + 1), p(29, 100, mid)])  # fmt: skip
        corners = [p(30, 40, mid), p(170, 40, mid), p(170, 160, mid), p(30, 160, mid)]
        k.add("fillet", f"{name} Pod Corners", {"edges": k.erefs(corners)},
              fillet_type="constant", radius=mm(8))  # fmt: skip
        k.expect(f"{name} Pod Corners", inside=[p(38, 41, mid)], outside=[p(30.5, 40.5, mid)])
        k.add("chamfer", f"{name} Pod Top Chamfer",
              {"edges": k.erefs([p(100, 40, zt), p(100, 160, zt)])},
              chamfer_type="distance_distance", distance=mm(1))  # fmt: skip
        k.expect(f"{name} Pod Top Chamfer", inside=[p(100, 41.5, zt - 0.2)],
                 outside=[p(100, 40.3, zt - 0.3), p(100, 159.7, zt - 0.3)])  # fmt: skip

        # Four tapped holes in the top.
        spots = [p(45, 55, zt), p(155, 55, zt), p(45, 145, zt), p(155, 145, zt)]
        psk, _ids = k.points(f"{name} Screw Spots", pod_top(), spots)
        k.add("hole", f"{name} Screws M6", {"sketch": {"feature": psk}, "face": [pod_top()]},
              end_condition="blind", **tapped("M6"))  # fmt: skip
        k.expect(f"{name} Screws M6", inside=[p(51, 55, zt - 2)],
                 outside=[p(45, 55, zt - 2), p(155, 145, zt - 2)])  # fmt: skip

        # A pocket with dogbone corners, and a bore in its floor with a ring groove.
        s = k.sketch(f"{name} Pocket Sketch", pod_top(),
                     lambda sk, at: sk.polygon(rect(at, ox + 60, oy + 70, zt, ox + 140,
                                                    oy + 130, zt)))  # fmt: skip
        pocket = k.add("extrude", f"{name} Pocket", {"sketch": {"feature": s}},
                       operation="cut", end_condition="blind", depth=mm(10),
                       reverse=k.reverse_for(pod_top(), (0, 0, -1)))  # fmt: skip
        k.expect(f"{name} Pocket", inside=[p(100, 100, zt - 11), p(55, 100, zt - 5)],
                 outside=[p(100, 100, zt - 5)])  # fmt: skip
        k.add("corner_relief", f"{name} Pocket Dogbones", {"feature": {"feature": pocket}},
              relief_type="dogbone", tool_diameter=mm(4))  # fmt: skip
        k.expect(
            f"{name} Pocket Dogbones",
            inside=[p(59.5, 75, zt - 5)],
            outside=[p(59.8, 71.414, zt - 5)],
        )  # a bite into each wall at each corner
        floor = lambda: k.fref(p(100, 100, zt - 10))  # noqa: E731
        s = k.sketch(
            f"{name} Bore Sketch", floor(), lambda sk, at: sk.circle(at(*p(100, 100, zt - 10)), 24)
        )
        k.add("extrude", f"{name} Bore", {"sketch": {"feature": s}}, operation="cut",
              end_condition="blind", depth=mm(12),
              reverse=k.reverse_for(floor(), (0, 0, -1)))  # fmt: skip
        k.expect(f"{name} Bore", inside=[p(114, 100, zt - 15), p(100, 100, zt - 23)],
                 outside=[p(100, 100, zt - 15), p(111, 100, zt - 15)])  # fmt: skip
        k.add("ring_groove", f"{name} Bore Ring Groove", {"face": [k.fref(p(112, 100, zt - 16))]},
              ring_type="ring", position=mm(2), from_end="start")  # fmt: skip
        k.expect(f"{name} Bore Ring Groove", inside=[p(116, 100, zt - 16)],
                 outside=[p(100, 100, zt - 16)])  # fmt: skip

        # A turned knob with a thread and a dome, left of the pocket.
        plane = k.offset_plane(f"{name} Middle Plane", TOP, oy + 100, (0, 1, 0))
        axis_line: list = []

        def knob(sk, at):  # type: ignore[no-untyped-def]
            sk.polygon([at(*p(45, 100, zt)), at(*p(55, 100, zt)), at(*p(55, 100, zt + 15)),
                        at(*p(45, 100, zt + 15))])  # fmt: skip
            axis_line.append(sk.line(at(*p(45, 100, zt - 1)), at(*p(45, 100, zt + 20)),
                                     construction=True))  # fmt: skip

        s = k.sketch(f"{name} Knob Profile", plane, knob)
        k.add("revolve", f"{name} Knob", {"sketch": {"feature": s},
                                          "axis": {"sketch_entity": axis_line[0]}},
              operation="boss", direction="one_direction", angle=deg(360),
              reverse=False)  # fmt: skip
        k.expect(f"{name} Knob", inside=[p(45, 100, zt + 10), p(54, 100, zt + 10)],
                 outside=[p(56, 100, zt + 10), p(45, 100, zt + 16)])  # fmt: skip
        # The dome first: on the threaded rim the kernel cannot build it.
        k.add("dome", f"{name} Knob Dome", {"faces": [k.fref(p(45, 100, zt + 15))]},
              distance=mm(3))  # fmt: skip
        k.expect(f"{name} Knob Dome", inside=[p(45, 100, zt + 17)],
                 outside=[p(45, 100, zt + 18.5)])  # fmt: skip

        # The pick is a quarter turn from the seam, which meets the rim at (55, 100) (D1084).
        k.add("modeled_thread", f"{name} Knob Thread", {"edge": [k.eref(p(45, 110, zt + 15))]},
              standard="iso", size="M20", diameter=mm(20), pitch=mm(2.5), method="cut",
              hand="right", end_condition="blind", length=mm(9), form="printable")  # fmt: skip
        k.expect(f"{name} Knob Thread", inside=[p(45, 100, zt + 10)],
                 some_outside=[p(54.6, 100, zt + 6 + 0.2 * i) for i in range(45)])  # fmt: skip
        # A boss right of the pocket, and a mounting boss in front of it.
        s = k.sketch(f"{name} Boss Sketch", pod_top(155, 100),
                     lambda sk, at: sk.circle(at(*p(155, 100, zt)), 16))  # fmt: skip
        k.add("extrude", f"{name} Boss", {"sketch": {"feature": s}}, operation="boss",
              end_condition="blind", depth=mm(6),
              reverse=k.reverse_for(pod_top(155, 100), (0, 0, 1)))  # fmt: skip
        k.expect(f"{name} Boss", inside=[p(155, 100, zt + 3)], outside=[p(155, 100, zt + 7)])
        psk, ids = k.points(f"{name} Mounting Spot", pod_top(100, 55), [p(100, 55, zt)])
        k.add("mounting_boss", f"{name} Mounting Boss",
              {"face": [pod_top(100, 55)], "position": {"feature": psk, "sketch_entity": ids[0]},
               "direction": {"feature": self.top_plane}},
              boss_type="screw_thread", boss_diameter=mm(12), boss_height=mm(8),
              hole_diameter=mm(4.2), hole_depth=mm(6), fin_count=num(0))  # fmt: skip
        k.expect(f"{name} Mounting Boss", inside=[p(105, 55, zt + 4)],
                 outside=[p(100, 55, zt + 5), p(107, 55, zt + 4)])  # fmt: skip

        # A roof with a stone seat behind the pocket.
        s = k.sketch(f"{name} Roof Outline", pod_top(100, 147),
                     lambda sk, at: sk.polygon(rect(at, ox + 85, oy + 138, zt, ox + 115,
                                                    oy + 156, zt)))  # fmt: skip
        roof = k.add("roof", f"{name} Roof", {"sketch": {"feature": s}}, slope=deg(30),
                     max_height=mm(3), operation="boss")  # fmt: skip
        k.expect(f"{name} Roof", inside=[p(100, 147, zt + 2.5)], outside=[p(100, 147, zt + 3.5)])
        k.add("stone_setting", f"{name} Stone Seat",
              {"seat_face": [k.fref(p(100, 147, zt + 3), of=roof)]},
              stone_diameter=mm(3), girdle_depth=mm(0.5), prongs=num(4), prong_diameter=mm(0.8),
              prong_height=mm(1))  # fmt: skip
        k.expect(f"{name} Stone Seat", inside=[p(103, 147, zt + 2.5)],
                 outside=[p(100, 147, zt + 2.8)])  # fmt: skip

        # On the walls: an O-ring groove, a hose barb (and its mirror), a cable tie loop.
        right = lambda: k.fref(p(170, 80, mid))  # noqa: E731
        s = k.sketch(f"{name} Seal Sketch", right(),
                     lambda sk, at: sk.circle(at(*p(170, 100, mid)), 20))  # fmt: skip
        k.add("oring_groove", f"{name} Wall Seal", {"sketch": {"feature": s}},
              cross_section=mm(1.5), use="face")  # fmt: skip
        k.expect(f"{name} Wall Seal", inside=[p(169.7, 100, mid + 7.5), p(168, 100, mid + 10)],
                 outside=[p(169.7, 100, mid + 10)])  # fmt: skip
        barb = k.add("hose_fitting", f"{name} Hose Barb", {"base_face": [k.fref(p(30, 80, mid))]},
                     fitting="barb", hose_diameter=mm(8), ring_count=num(3), ring_length=mm(4),
                     shank_height=mm(3), bore_depth=mm(6), pos_x=mm(ox + 30), pos_y=mm(oy + 120),
                     pos_z=mm(mid))  # fmt: skip
        k.expect(f"{name} Hose Barb", inside=[p(16, 120, mid), p(29, 120, mid)],
                 outside=[p(13, 120, mid), p(28, 126, mid)])  # fmt: skip
        mx = k.offset_plane(f"{name} Cross Plane", RIGHT, ox + 100, (1, 0, 0))
        k.add("mirror", f"{name} Second Barb",
              {"plane": {"feature": mx}, "features": [{"feature": barb}]},
              geometry=True)  # a fitting is copied as faces, not built again  # fmt: skip
        k.expect(f"{name} Second Barb", inside=[p(184, 120, mid)], outside=[p(187, 120, mid)])
        front = lambda: k.fref(p(70, 40, mid))  # noqa: E731
        psk, _ids = k.points(f"{name} Tie Spot", front(), [p(100, 40, mid)])
        k.add("cable_tie", f"{name} Cable Tie", {"sketch": {"feature": psk}},
              tie_width=mm(3), tie_thickness=mm(1.2), span=mm(8), cover=mm(2))  # fmt: skip
        k.expect(f"{name} Cable Tie", inside=[p(100, 40.6, mid), p(100, 43.8, mid)],
                 outside=[p(100, 42.6, mid), p(100, 41.2, mid)])  # fmt: skip

        # In the bed round the pod: a grille, living hinge slits, two printable holes.
        s = k.sketch(f"{name} Grille Area", bed_top(100, 20),
                     lambda sk, at: sk.polygon(rect(at, ox + 50, oy + 8, BED_Z, ox + 150,
                                                    oy + 32, BED_Z)))  # fmt: skip
        k.add("fill_pattern", f"{name} Grille", {"sketch": {"feature": s}}, layout="staggered",
              spacing=mm(10), shape="circle", size=mm(4), margin=mm(1))  # fmt: skip
        k.expect(f"{name} Grille", inside=[p(100, 4, 20), p(40, 20, 20)],
                 some_outside=[p(52 + i / 2, 8 + j, 20) for i in range(196)
                               for j in range(0, 24, 2)])  # fmt: skip
        s = k.sketch(f"{name} Hinge Area", bed_top(100, 180),
                     lambda sk, at: sk.polygon(rect(at, ox + 60, oy + 170, BED_Z, ox + 140,
                                                    oy + 190, BED_Z)))  # fmt: skip
        k.add("living_hinge", f"{name} Flex Slits", {"sketch": {"feature": s}},
              slit_length=mm(12), slit_width=mm(1), bridge=mm(3), row_spacing=mm(3))  # fmt: skip
        k.expect(f"{name} Flex Slits", inside=[p(55, 180, 20), p(145, 180, 20)],
                 some_outside=[p(61 + i / 4, 171 + j, 20) for i in range(316)
                               for j in range(19)])  # fmt: skip
        psk, _ids = k.points(f"{name} Bed Hole Spots", bed_top(15, 30),
                             [p(15, 30, BED_Z), p(15, 170, BED_Z)])  # fmt: skip
        k.add("hole", f"{name} Bed Holes", {"sketch": {"feature": psk}, "face": [bed_top(15, 30)]},
              hole_type="simple", end_condition="through_all", diameter=mm(9))  # fmt: skip
        k.expect(f"{name} Bed Holes", inside=[p(20.5, 30, 20)], outside=[p(15, 30, 20)])
        k.add(
            "polygon_holes",
            f"{name} Printable Bed Holes",
            {"faces": [k.fref(p(19.5, 30, 20)), k.fref(p(19.5, 170, 20))]},
            sides=num(8),
        )
        k.expect(f"{name} Printable Bed Holes", inside=[p(20.5, 30, 20)],
                 outside=[p(15, 30, 20), p(19.4, 30, 20)])  # fmt: skip

        # Text on the front wall, a snap hook on the bed, and a handle over the right side.
        plane_front = k.plane_of(front())
        sk = Sketch()
        from fdcad.core.sketch.text import SketchText
        from fdcad.samples.builder import to_local

        x, y = to_local(plane_front, p(50, 40, mid - 4))
        sk.texts.append(SketchText("t1", f"P{n}", x=x, y=y, height=8.0))
        s = k.b.sketch(f"{name} Wall Text", front(), sk)
        k.add("mark", f"{name} Wall Mark", {"sketch": {"feature": s}})
        k.expect(f"{name} Wall Mark", inside=[p(60, 41, mid)])
        k.add("snap_hook", f"{name} Snap Hook",
              {"face": [bed_top(15, 100)], "hook_direction": {"feature": RIGHT}},
              body_height=mm(8), base_depth=mm(3), top_depth=mm(2.5), total_width=mm(10),
              overhang=mm(1.5), hook_height=mm(2.5), lip_height=mm(0.6), top_draft=deg(30),
              hook_reverse=False, pos_x=mm(ox + 15), pos_y=mm(oy + 100),
              pos_z=mm(BED_Z))  # fmt: skip
        k.expect(f"{name} Snap Hook", inside=[p(16.5, 100, BED_Z + 2)],
                 outside=[p(13, 100, BED_Z + 2)])  # fmt: skip
        pts = [[ox + 185, oy + 20, BED_Z - 1], [ox + 185, oy + 45, BED_Z + 20],
               [ox + 185, oy + 100, BED_Z + 35], [ox + 185, oy + 155, BED_Z + 20],
               [ox + 185, oy + 180, BED_Z - 1]]  # fmt: skip
        curve = k.add("point_curve", f"{name} Handle Curve", {}, data={"points": pts})
        k.add("pipe", f"{name} Handle", {"path": {"feature": curve}}, operation="boss",
              outer_diameter=mm(8))  # fmt: skip
        k.expect(f"{name} Handle", inside=[p(185, 100, BED_Z + 35)],
                 outside=[p(185, 100, BED_Z + 40), p(185, 100, BED_Z + 30)])  # fmt: skip

    # A shaft on a pedestal ------------------------------------------------------------
    # The shaft's axis runs along X at (y = ya, z = za), from x0 to x0 + 200. Only its
    # left end touches the pedestal, so each of its round faces stays whole: a thread, a
    # keyway or a ring groove needs the whole round face.

    def shaft_station(self, n: int, x0: float, ya: float) -> None:
        import math

        k = self
        za = BED_Z + 30.0
        name = f"T{n}"
        s = k.sketch(f"{name} Pedestal Sketch", k.fref((x0 - 10, ya, BED_Z)),
                     lambda sk, at: sk.polygon(rect(at, x0 - 20, ya - 25, BED_Z, x0, ya + 25,
                                                    BED_Z)))  # fmt: skip
        k.add("extrude", f"{name} Pedestal", {"sketch": {"feature": s}}, operation="boss",
              end_condition="blind", depth=mm(55),
              reverse=k.reverse_for(k.fref((x0 - 10, ya, BED_Z)), (0, 0, 1)))  # fmt: skip
        k.expect(f"{name} Pedestal", inside=[(x0 - 10, ya, za)], outside=[(x0 - 10, ya, za + 26)])
        plane = k.offset_plane(f"{name} Shaft Plane", FRONT, za, (0, 0, 1))
        steps = [(0, 0), (0, 10), (30, 10), (30, 12.5), (60, 12.5), (60, 17.5), (120, 17.5),
                 (120, 12.5), (160, 12.5), (160, 10), (200, 10), (200, 0)]  # fmt: skip
        axis: list = []

        def profile(sk, at):  # type: ignore[no-untyped-def]
            lines = sk.polygon([at(x0 + x, ya + r, za) for x, r in steps])
            axis.append(lines[-1])

        s = k.sketch(f"{name} Shaft Profile", plane, profile)
        k.add("revolve", f"{name} Shaft", {"sketch": {"feature": s},
                                           "axis": {"sketch_entity": axis[0]}},
              operation="boss", direction="one_direction", angle=deg(360),
              reverse=False)  # fmt: skip

        def r(x: float, rad: float, a: float = 90) -> tuple[float, float, float]:
            return (x0 + x, ya + rad * math.cos(math.radians(a)),
                    za + rad * math.sin(math.radians(a)))  # fmt: skip

        k.expect(f"{name} Shaft", inside=[r(15, 9), r(90, 17), r(140, 12), r(1, 9.5)],
                 outside=[r(15, 11), r(90, 18), r(140, 13), r(201, 5)])  # fmt: skip
        # Picks on top of each round (a = 90): the seam of a revolved face lies on its
        # side, where the profile was drawn (D1084).
        top = lambda x, rad: (x0 + x, ya, za + rad)  # noqa: E731
        k.add("chamfer", f"{name} End Chamfer", {"edges": [k.eref(top(200, 10))]},
              chamfer_type="distance_distance", distance=mm(1))  # fmt: skip
        k.expect(f"{name} End Chamfer", inside=[r(198.5, 9.5)], outside=[r(199.7, 9.7)])
        k.add("fillet", f"{name} Shoulders",
              {"edges": k.erefs([top(60, 12.5), top(120, 12.5), top(160, 10)])},
              fillet_type="constant", radius=mm(1))  # fmt: skip
        k.expect(f"{name} Shoulders", inside=[r(59.8, 12.7), r(120.2, 12.7), r(160.2, 10.2)],
                 outside=[r(59.2, 13.3), r(160.8, 10.8)])  # fmt: skip
        k.add("knurl", f"{name} Grip Knurl", {"round_face": [k.fref(top(15, 10))]},
              knurl_pattern="straight", knurl_pitch=mm(2.5), knurl_depth=mm(0.5))  # fmt: skip
        k.expect(f"{name} Grip Knurl", inside=[r(15, 9)],
                 some_outside=[r(15, 9.8, a / 5) for a in range(1800)])  # fmt: skip
        k.add("shaft_shape", f"{name} Keyway", {"face": [k.fref(r(90, 17.5, 0))]},
              shaft_form="keyway", key_standard="metric", length=mm(40),
              from_end="start")  # fmt: skip
        k.expect(f"{name} Keyway", inside=[r(80, 16, 0), r(105, 17, 180), r(80, 12, 180)],
                 outside=[r(80, 16, 180), r(62, 16, 180), r(98, 16, 180)])  # fmt: skip
        k.add("shaft_shape", f"{name} Hex End", {"face": [k.fref(r(185, 10, 0))]},
              shaft_form="hex", length=mm(15), from_end="end")  # fmt: skip
        k.expect(f"{name} Hex End", inside=[r(192, 8.5), r(180, 9.8)],
                 outside=[r(192, 9.2, 0), r(192, 9.2, 60)])  # fmt: skip
        k.add("ring_groove", f"{name} Retaining Ring", {"face": [k.fref(r(140, 12.5, 0))]},
              ring_type="ring", position=mm(6), from_end="end")  # fmt: skip
        k.expect(f"{name} Retaining Ring", inside=[r(150, 12), r(154, 11.5)],
                 outside=[r(154, 12.2), r(154, 12.2, 270)])  # fmt: skip
        k.add("oring_groove", f"{name} Seal", {"face": [k.fref(r(45, 12.5, 0))]},
              cross_section=mm(2), use="static", position=mm(10), from_end="start")  # fmt: skip
        k.expect(f"{name} Seal", inside=[r(38, 12), r(41, 10.7), r(44, 12)],
                 outside=[r(41, 11.5), r(41, 11.5, 0)])  # fmt: skip
        k.add("cosmetic_thread", f"{name} Nut Thread", {"edge": [k.eref(top(120, 17.5))]},
              standard="iso", size="M35x1.5", diameter=mm(35), pitch=mm(1.5),
              end_condition="blind", length=mm(8))  # fmt: skip
        k.expect(f"{name} Nut Thread", inside=[r(116, 17.4), r(116, 17.4, 270)])
        end = k.fref((x0 + 200, ya + 4, za))
        psk, _ids = k.points(f"{name} Centre Spot", end, [(x0 + 200, ya, za)])
        k.add("hole", f"{name} Centre Hole", {"sketch": {"feature": psk}, "face": [end]},
              hole_type="simple", end_condition="blind", diameter=mm(4), depth=mm(8),
              bottom="drill_point", tip_angle=deg(118))  # fmt: skip
        k.expect(f"{name} Centre Hole", inside=[r(198, 2.5), r(190, 0.5)],
                 outside=[r(199, 0.5), r(192.5, 0.5)])  # fmt: skip
        s = k.sketch(f"{name} Cross Hole Sketch", plane,
                     lambda sk, at: sk.circle(at(x0 + 110, ya, za), 5))  # fmt: skip
        k.add("extrude", f"{name} Cross Hole", {"sketch": {"feature": s}}, operation="cut",
              end_condition="through_all_both", depth=mm(1), reverse=False)  # fmt: skip
        k.expect(f"{name} Cross Hole", inside=[r(113, 15), r(110, 15, 0)],
                 outside=[r(110, 15), r(110, 15, 270), (x0 + 110, ya, 20)])  # fmt: skip
        above = k.add("ref_point", f"{name} Above The Shaft", {}, method="values",
                      x=mm(x0 + 75), y=mm(ya), z=mm(za + 60))  # fmt: skip
        wall = k.fref(top(75, 17.5))
        label_plane = k.add("ref_plane", f"{name} Label Plane",
                            {"first": wall, "second": {"feature": above}},
                            method="tangent")  # fmt: skip
        s = k.sketch(f"{name} Label Sketch", label_plane,
                     lambda sk, at: sk.polygon(rect(at, x0 + 66, ya - 4, za + 17.5, x0 + 80,
                                                    ya + 4, za + 17.5)))  # fmt: skip
        k.add("wrap", f"{name} Label", {"sketch": {"feature": s}, "face": [k.fref(top(75, 17.5))]},
              wrap_type="deboss", thickness=mm(0.4), method="analytical")  # fmt: skip
        k.expect(f"{name} Label", inside=[r(73, 16.9), r(63, 17.3), r(83, 17.3)],
                 outside=[r(73, 17.3), r(67, 17.3)])  # fmt: skip

    # A plate of patterns -----------------------------------------------------------------
    # A plate 120 by 70 by 6 stands on the bed with its corner at (x0, y0); every kind of
    # pattern works on studs and holes on it.

    def pattern_station(self, n: int, x0: float, y0: float) -> None:
        k = self
        name = f"P{n}"
        zp = BED_Z + 6  # the plate's top
        s = k.sketch(f"{name} Plate Sketch", k.fref((x0 + 60, y0 + 35, BED_Z)),
                     lambda sk, at: sk.polygon(rect(at, x0, y0, BED_Z, x0 + 120, y0 + 70,
                                                    BED_Z)))  # fmt: skip
        k.add("extrude", f"{name} Plate", {"sketch": {"feature": s}}, operation="boss",
              end_condition="blind", depth=mm(6),
              reverse=k.reverse_for(k.fref((x0 + 60, y0 + 35, BED_Z)), (0, 0, 1)))  # fmt: skip
        k.expect(f"{name} Plate", inside=[(x0 + 60, y0 + 35, zp - 1)],
                 outside=[(x0 + 60, y0 + 35, zp + 1)])  # fmt: skip
        top = lambda: k.fref((x0 + 60, y0 + 68, zp))  # noqa: E731

        def at_(u: float, v: float, z: float = zp) -> tuple[float, float, float]:
            return (x0 + u, y0 + v, z)

        def stud(label: str, u: float, v: float, d: float = 6.0) -> str:
            s = k.sketch(f"{label} Sketch", top(), lambda sk, at: sk.circle(at(*at_(u, v)), d))
            return k.add("extrude", label, {"sketch": {"feature": s}}, operation="boss",
                         end_condition="blind", depth=mm(4), reverse=False)  # fmt: skip

        seed = stud(f"{name} Table Seed", 10, 10)
        k.add("table_pattern", f"{name} Table Studs", {"features": [{"feature": seed}]},
              data={"rows": [[x0 + 30, y0 + 10], [x0 + 50, y0 + 14], [x0 + 70, y0 + 10, False],
                             [x0 + 90, y0 + 14]]})  # fmt: skip
        k.expect(f"{name} Table Studs", inside=[at_(30, 10, zp + 2), at_(90, 14, zp + 2)],
                 outside=[at_(70, 10, zp + 2), at_(30, 10, zp + 5)])  # fmt: skip
        seed = stud(f"{name} Sketch Seed", 10, 26)
        psk, _ids = k.points(f"{name} Stud Spots", top(),
                             [at_(30, 28), at_(50, 24), at_(70, 28)])  # fmt: skip
        k.add("sketch_pattern", f"{name} Sketch Studs",
              {"sketch": {"feature": psk}, "features": [{"feature": seed}]})  # fmt: skip
        k.expect(f"{name} Sketch Studs", inside=[at_(30, 28, zp + 2), at_(70, 28, zp + 2)],
                 outside=[at_(90, 28, zp + 2)])  # fmt: skip
        s = k.sketch(f"{name} Drill Sketch", top(), lambda sk, at: sk.circle(at(*at_(110, 8)), 3.4))
        drill = k.add("extrude", f"{name} Drill Seed", {"sketch": {"feature": s}},
                      operation="cut", end_condition="blind", depth=mm(4),
                      reverse=k.reverse_for(top(), (0, 0, -1)))  # fmt: skip
        k.expect(f"{name} Drill Seed", inside=[at_(112, 8, zp - 2)], outside=[at_(110, 8, zp - 2)])
        path = k.sketch(f"{name} Drill Row Path", top(),
                        lambda sk, at: sk.line(at(*at_(110, 8)), at(*at_(110, 62))))  # fmt: skip
        k.add("curve_array", f"{name} Drill Row",
              {"path": {"feature": path}, "features": [{"feature": drill}]},
              mode="count", count=num(4))  # fmt: skip
        k.expect(
            f"{name} Drill Row",
            inside=[at_(110, 35, zp - 2)],
            outside=[at_(110, 26, zp - 2), at_(110, 44, zp - 2), at_(110, 62, zp - 2)],
        )
        s = k.sketch(f"{name} Counterbore Sketch", top(),
                     lambda sk, at: sk.circle(at(*at_(110, 8)), 7))  # fmt: skip
        cbore = k.add("extrude", f"{name} Counterbore Seed", {"sketch": {"feature": s}},
                      operation="cut", end_condition="blind", depth=mm(1.5),
                      reverse=k.reverse_for(top(), (0, 0, -1)))  # fmt: skip
        rims = [k.eref(at_(110 + 1.7, 26)), k.eref(at_(110 + 1.7, 44)), k.eref(at_(110 + 1.7, 62))]
        k.add("point_pattern", f"{name} Counterbores",
              {"targets": rims, "features": [{"feature": cbore}]})  # fmt: skip
        k.expect(f"{name} Counterbores", inside=[at_(113, 26, zp - 2)],
                 outside=[at_(113, 44, zp - 0.5), at_(113, 62, zp - 0.5)])  # fmt: skip
        seed = stud(f"{name} Chain Seed", 12, 44, 5.0)
        mid = k.offset_plane(f"{name} Plate Middle Plane", RIGHT, x0 + 50, (1, 0, 0))
        k.add("pattern_chain", f"{name} Chain Of Studs",
              {"features": [{"feature": seed}], "direction": {"feature": RIGHT},
               "plane": {"feature": mid}},
              steps="linear, mirror", spacing=mm(10), instances=num(3))  # fmt: skip
        k.expect(f"{name} Chain Of Studs", inside=[at_(32, 44, zp + 2), at_(88, 44, zp + 2)],
                 outside=[at_(42, 44, zp + 2), at_(58, 44, zp + 2)])  # fmt: skip
        seed = stud(f"{name} Grid Seed", 12, 58, 4.0)
        grid = k.add("linear_pattern", f"{name} Grid Of Studs",
                     {"direction1": {"feature": RIGHT}, "direction2": {"feature": TOP},
                      "features": [{"feature": seed}]},
                     spacing1=mm(9), count1=num(4), reverse1=False, second_direction=True,
                     spacing2=mm(5), count2=num(2), reverse2=False)  # fmt: skip
        k.expect(f"{name} Grid Of Studs", inside=[at_(39, 58, zp + 2), at_(39, 63, zp + 2)],
                 outside=[at_(48, 58, zp + 2), at_(12, 68, zp + 2)])  # fmt: skip
        s = k.sketch(f"{name} Pin Sketch", top(), lambda sk, at: sk.circle(at(*at_(12, 58)), 1.5))
        pin = k.add("extrude", f"{name} Grid Pin", {"sketch": {"feature": s}}, operation="boss",
                    end_condition="blind", depth=mm(7),
                    reverse=k.reverse_for(top(), (0, 0, 1)))  # fmt: skip
        k.add("follow_pattern", f"{name} Pins Follow",
              {"pattern": {"feature": grid}, "features": [{"feature": pin}]})  # fmt: skip
        k.expect(f"{name} Pins Follow", inside=[at_(39, 63, zp + 6)], outside=[at_(39, 63, zp + 8)])
        s = k.sketch(f"{name} Hub Sketch", top(), lambda sk, at: sk.circle(at(*at_(75, 52)), 16))
        k.add("extrude", f"{name} Hub", {"sketch": {"feature": s}}, operation="boss",
              end_condition="blind", depth=mm(5), reverse=False)  # fmt: skip
        s = k.sketch(f"{name} Spoke Sketch", k.fref(at_(75, 52, zp + 5)),
                     lambda sk, at: sk.circle(at(*at_(75, 58, zp + 5)), 2.5))  # fmt: skip
        spoke = k.add("extrude", f"{name} Spoke Hole", {"sketch": {"feature": s}},
                      operation="cut", end_condition="blind", depth=mm(3),
                      reverse=k.reverse_for(k.fref(at_(75, 52, zp + 5)), (0, 0, -1)))  # fmt: skip
        k.add("circular_pattern", f"{name} Spoke Circle",
              {"axis": k.fref(at_(75 + 8, 52, zp + 2.5)), "features": [{"feature": spoke}]},
              count1=num(6), angle1=deg(360), equal_spacing=True)  # fmt: skip
        k.expect(f"{name} Spoke Circle", inside=[at_(75, 52, zp + 4)],
                 outside=[at_(75, 46, zp + 4.5), at_(75 + 5.2, 55, zp + 4.5)])  # fmt: skip

    # The yard: the rest, at the back of the bed (Y 780..1000) -----------------------------

    def frame(self, name: str, x: float, y: float, z: float) -> dict:
        fid = self.add("coord_system", name, {}, method="angles", x=mm(x), y=mm(y), z=mm(z),
                       rx=deg(0), ry=deg(0), rz=deg(0))  # fmt: skip
        return {"feature": fid}

    def block(self, name: str, x0: float, y0: float, x1: float, y1: float, h: float) -> str:
        """A block standing on the bed, joined to it."""
        where = self.fref(((x0 + x1) / 2, (y0 + y1) / 2, BED_Z))
        s = self.sketch(
            f"{name} Sketch",
            where,
            lambda sk, at: sk.polygon(rect(at, x0, y0, BED_Z, x1, y1, BED_Z)),
        )
        return self.add("extrude", name, {"sketch": {"feature": s}}, operation="boss",
                        end_condition="blind", depth=mm(h),
                        reverse=self.reverse_for(where, (0, 0, 1)))  # fmt: skip

    def round_boss(self, name: str, cx: float, cy: float, d: float, h: float) -> str:
        where = self.fref((cx, cy, BED_Z))
        s = self.sketch(f"{name} Sketch", where, lambda sk, at: sk.circle(at(cx, cy, BED_Z), d))
        return self.add("extrude", name, {"sketch": {"feature": s}}, operation="boss",
                        end_condition="blind", depth=mm(h),
                        reverse=self.reverse_for(where, (0, 0, 1)))  # fmt: skip

    def yard(self) -> None:
        import math

        k = self
        z = BED_Z
        # Whole part references.
        k.add("measurement", "Whole Part Measure", {})
        k.add("sensor", "Volume Watch", {}, source="volume", high=Param("1000000000", 1e9))
        k.add("bounding_box", "Stock Size", {}, box_shape="box", orient="axes")
        k.add("ref_point", "Centre Of Mass", {}, method="centre_of_mass")
        k.add("contour", "Level Lines", {"direction": {"feature": FRONT}}, spacing=mm(20))

        # A plate with lightening pockets and a rounded top edge.
        k.block("Pocket Plate", 20, 790, 220, 910, 10)
        k.expect("Pocket Plate", inside=[(120, 850, z + 9)], outside=[(120, 850, z + 11)])
        k.add("lightening_pockets", "Plate Pockets", {"plate_face": [k.fref((120, 850, z + 10))]},
              border=mm(8), web=mm(3), cell=mm(24), corner_radius=mm(1),
              pocket_depth=mm(4))  # fmt: skip
        k.expect("Plate Pockets", inside=[(120, 850, z + 5), (22, 850, z + 9)])
        k.add("edge_profile", "Plate Top Edge", {"loop_face": [k.fref((24, 850, z + 10))]},
              router_profile="round_over", profile_size=mm(1.5))  # fmt: skip
        k.expect("Plate Top Edge", inside=[(21, 850, z + 8)], outside=[(20.05, 850, z + 9.95)])

        # Primitives standing on the bed, each joined to it.
        x = 40.0
        k.add("primitive", "Stand", {"frame": k.frame("Stand Frame", x, 960, z)},
              kind="cylinder", operation="boss", diameter=mm(30), height=mm(25))  # fmt: skip
        k.expect("Stand", inside=[(x, 960, z + 20), (x + 14, 960, z + 10)],
                 outside=[(x + 16, 960, z + 10), (x, 960, z + 26)])  # fmt: skip
        x += 60
        k.add("primitive", "Ball", {"frame": k.frame("Ball Frame", x, 960, z)}, kind="sphere",
              operation="boss", diameter=mm(30), centred=True)  # fmt: skip
        k.expect("Ball", inside=[(x, 960, z + 14)], outside=[(x, 960, z + 16)])
        x += 60
        k.add("primitive", "Cone", {"frame": k.frame("Cone Frame", x, 960, z)}, kind="cone",
              operation="boss", diameter=mm(30), diameter2=mm(10), height=mm(30))  # fmt: skip
        k.expect("Cone", inside=[(x, 960, z + 29), (x + 14, 960, z + 1)],
                 outside=[(x, 960, z + 31), (x + 14, 960, z + 25)])  # fmt: skip
        x += 60
        k.add("primitive", "Ring", {"frame": k.frame("Ring Frame", x, 960, z + 3)}, kind="torus",
              operation="boss", ring=mm(30), tube=mm(8), centred=True)  # fmt: skip
        k.expect(
            "Ring", inside=[(x + 15, 960, z + 3)], outside=[(x, 960, z + 3), (x + 15, 960, z + 8)]
        )
        x += 60
        k.add("primitive", "Wedge", {"frame": k.frame("Wedge Frame", x - 15, 950, z)},
              kind="wedge", operation="boss", length=mm(30), width=mm(20), height=mm(20),
              top=mm(5))  # fmt: skip
        k.expect("Wedge", inside=[(x - 10, 960, z + 1)], outside=[(x - 10, 960, z + 21)])
        x += 60
        k.add("primitive", "Hex Post", {"frame": k.frame("Hex Frame", x, 960, z)}, kind="prism",
              operation="boss", diameter=mm(30), sides=num(6), height=mm(20))  # fmt: skip
        k.expect("Hex Post", inside=[(x, 960 + 12, z + 10), (x + 14, 960, z + 10)],
                 outside=[(x, 960 + 16, z + 10), (x, 960, z + 21)])  # fmt: skip
        x += 60
        k.add("primitive", "Sleeve", {"frame": k.frame("Sleeve Frame", x, 960, z)}, kind="tube",
              operation="boss", diameter=mm(30), inner=mm(20), height=mm(20))  # fmt: skip
        k.expect("Sleeve", inside=[(x + 12, 960, z + 10)],
                 outside=[(x, 960, z + 10), (x + 16, 960, z + 10)])  # fmt: skip

        # A spring rising from the bed, and a lofted knob with a dome.
        s = k.sketch("Spring Circle", self.top_plane, lambda sk, at: sk.circle(at(480, 960, z), 30))
        helix = k.add("helix", "Spring Helix", {"sketch": {"feature": s}},
                      definition="pitch_turns", pitch=mm(7), turns=num(5))  # fmt: skip
        k.add("sweep", "Spring", {"path": {"feature": helix}}, operation="boss",
              profile_type="circular", diameter=mm(3))  # fmt: skip
        coil = [(480 + 15 * math.cos(a / 20), 960 + 15 * math.sin(a / 20), z + 20)
                for a in range(126)]  # fmt: skip
        k.expect("Spring", outside=[(480, 960, z + 20), (480, 960, z + 40)], some_inside=coil)
        s1 = k.sketch(
            "Knob Base Section", self.top_plane, lambda sk, at: sk.circle(at(560, 940, z), 30)
        )
        p20 = k.offset_plane("Knob Middle Plane", FRONT, z + 20, (0, 0, 1))
        s2 = k.sketch(
            "Knob Middle Section", p20, lambda sk, at: sk.circle(at(560, 940, z + 20), 40)
        )
        p36 = k.offset_plane("Knob Top Plane", FRONT, z + 36, (0, 0, 1))
        s3 = k.sketch("Knob Top Section", p36, lambda sk, at: sk.circle(at(560, 940, z + 36), 26))
        k.add("loft", "Lofted Knob", {"profiles": [{"feature": s} for s in (s1, s2, s3)]},
              operation="boss")  # fmt: skip
        k.expect("Lofted Knob", inside=[(560, 940, z + 1), (579, 940, z + 20)],
                 outside=[(576, 940, z + 1), (581, 940, z + 20), (560, 940, z + 37)])  # fmt: skip
        k.add("dome", "Knob Crown", {"faces": [k.fref((560, 940, z + 36))]}, distance=mm(5),
              continuous=True)  # fmt: skip
        k.expect("Knob Crown", inside=[(560, 940, z + 40.5)], outside=[(560, 940, z + 41.5)])
        s = k.sketch("Knob Mark Line", self.top_plane,
                     lambda sk, at: sk.line(at(540, 925, z), at(580, 955, z)))  # fmt: skip
        k.add("projected_curve", "Knob Mark Curve",
              {"sketch": {"feature": s}, "faces": [k.fref((580, 940, z + 20))]},
              mode="faces", both=True)  # fmt: skip

        # An edit block on a narrow riser, so its sides, its round and its hole are free of
        # the bed: the direct editing tools reshape the faces round what they change, and
        # a face that met the bed would have to reshape the bed's top as well.
        k.block("Edit Riser", 660, 815, 700, 835, 20)
        k.expect("Edit Riser", inside=[(680, 825, z + 19)], outside=[(650, 825, z + 10)])
        under = lambda: k.fref((680, 825, z + 20))  # noqa: E731
        s = k.sketch(
            "Edit Block Sketch",
            under(),
            lambda sk, at: sk.polygon(rect(at, 640, 800, z + 20, 720, 850, z + 20)),
        )
        k.add("extrude", "Edit Block", {"sketch": {"feature": s}}, operation="boss",
              end_condition="blind", depth=mm(30),
              reverse=k.reverse_for(under(), (0, 0, 1)))  # fmt: skip
        k.expect("Edit Block", inside=[(680, 825, z + 49), (642, 802, z + 30)],
                 outside=[(680, 825, z + 51), (642, 802, z + 19)])  # fmt: skip
        top_ = lambda h=50.0: k.fref((700, 840, z + h))  # noqa: E731
        s = k.sketch("Edit Hole Sketch", top_(), lambda sk, at: sk.circle(at(650, 840, z + 50), 10))
        k.add("extrude", "Edit Hole", {"sketch": {"feature": s}}, operation="cut",
              end_condition="blind", depth=mm(30),
              reverse=k.reverse_for(top_(), (0, 0, -1)))  # fmt: skip
        k.expect("Edit Hole", inside=[(656, 840, z + 35)], outside=[(650, 840, z + 35)])
        k.add("fillet", "Edit Corner", {"edges": [k.eref((640, 800, z + 35))]},
              fillet_type="constant", radius=mm(4))  # fmt: skip
        k.expect("Edit Corner", inside=[(642, 803, z + 35)], outside=[(640.3, 800.3, z + 35)])
        k.add("face_relation", "Edit Top And Bed Parallel",
              {"faces": [top_(), k.fref((700, 500, 0))]}, relation="parallel")  # fmt: skip
        k.add("move_face", "Raise Edit Top", {"faces": [top_()]},
              mode="offset", distance=mm(2), reverse=False)  # fmt: skip
        k.expect("Raise Edit Top", inside=[(700, 840, z + 51.5)], outside=[(700, 840, z + 52.5)])
        # Push/Pull on the Stand's top: the edit block's end face would not move (the
        # kernel said a neighbouring face would cross another), so it stays where it is.
        k.add("push_pull", "Pull Stand Top", {"faces": [k.fref((40, 960, z + 25))]},
              distance=mm(3))  # fmt: skip
        k.expect("Pull Stand Top", inside=[(40, 960, z + 27.5)], outside=[(40, 960, z + 28.5)])
        # Raising the top gave the hole a second wall face, a 2 mm band: both are picked,
        # or the band grows into the place of the other and the hole stays (D1104).
        k.add("delete_face", "Fill Edit Hole",
              {"faces": [k.fref((655, 840, z + 35)), k.fref((655, 840, z + 51))]},
              option="patch")  # fmt: skip
        k.expect("Fill Edit Hole", inside=[(650, 840, z + 35)])
        k.add("remove_fillets", "Square Edit Corner",
              {"faces": [k.fref((641.1716, 801.1716, z + 35))]})  # fmt: skip
        k.expect("Square Edit Corner", inside=[(640.3, 800.3, z + 35)])
        level = k.offset_plane("Edit Level Plane", FRONT, z + 56, (0, 0, 1))
        k.add("replace_face", "Edit Top To Level", {"faces": [top_(52)],
                                                    "target": {"feature": level}})  # fmt: skip
        k.expect("Edit Top To Level", inside=[(700, 840, z + 55.5)], outside=[(700, 840, z + 56.5)])
        cross = k.offset_plane("Edit Marking Plane", TOP, 825, (0, 1, 0))
        k.add("split_line", "Edit Top Mark", {"faces": [top_(56)], "plane": {"feature": cross}},
              method="intersection")  # fmt: skip
        k.add("merge_faces", "Edit Top Joined Again",
              {"faces": [k.fref((700, 810, z + 56)), top_(56)]})  # fmt: skip
        k.expect("Edit Top Joined Again", inside=[(700, 825, z + 55.5)])
        k.add("ref_axis", "Edit Axis", {"first": {"feature": cross}, "second": {"feature": level}},
              method="two_planes")  # fmt: skip
        ends = [k.fref((640, 825, z + 35)), k.fref((720, 825, z + 35))]
        k.add("ref_plane", "Edit Between Ends", {"first": ends[0], "second": ends[1]},
              method="mid_plane")  # fmt: skip
        k.add("ref_point", "Edit Top Middle", {"first": top_(56)}, method="face_centre")
        k.add("measurement", "Edit Block Length",
              {"items": [k.fref((640, 825, z + 35)), k.fref((720, 825, z + 35))]})  # fmt: skip

        # A drum with a landing pad, a boss with crush ribs, a vent, a drafted lug.
        k.round_boss("Drum", 800, 830, 60, 40)
        k.expect("Drum", inside=[(800, 830, z + 39)], outside=[(831, 830, z + 20)])
        plane = k.offset_plane("Pad Plane", RIGHT, 833, (1, 0, 0))
        s = k.sketch(
            "Pad Outline",
            plane,
            lambda sk, at: sk.polygon(rect(at, 833, 823, z + 13, 833, 837, z + 27)),
        )
        k.add("landing_pad", "Label Pad",
              {"wall_face": [k.fref((830, 830, z + 20))], "sketch": {"feature": s}},
              pad_mode="raise")  # fmt: skip
        k.expect("Label Pad", inside=[(832, 830, z + 20)],
                 outside=[(832, 830, z + 30), (833.5, 830, z + 20)])  # fmt: skip
        k.round_boss("Bearing Seat", 920, 830, 70, 20)
        seat_top = lambda: k.fref((950, 830, z + 20))  # noqa: E731
        s = k.sketch(
            "Seat Bore Sketch", seat_top(), lambda sk, at: sk.circle(at(920, 830, z + 20), 47)
        )
        k.add("extrude", "Seat Bore", {"sketch": {"feature": s}}, operation="cut",
              end_condition="blind", depth=mm(15),
              reverse=k.reverse_for(seat_top(), (0, 0, -1)))  # fmt: skip
        k.expect("Seat Bore", inside=[(920, 830, z + 3)], outside=[(920, 830, z + 10)])
        k.add("crush_ribs", "Seat Crush Ribs", {"face": [k.fref((920 + 23.5, 830, z + 12))]},
              rib_count=num(6), rib_width=mm(2), rib_height=mm(0.3), rib_tip=mm(0.6))  # fmt: skip
        k.expect("Seat Crush Ribs", inside=[(920 + 27, 830, z + 12)], outside=[(920, 830, z + 12)])
        k.block("Vent Plate", 980, 790, 1080, 890, 6)
        vtop = lambda: k.fref((1075, 885, z + 6))  # noqa: E731
        parts: dict = {}

        def vent(sk, at):  # type: ignore[no-untyped-def]
            parts["ring"] = sk.circle(at(1030, 840, z + 6), 40)
            parts["ribs"] = [sk.line(at(1008, 834, z + 6), at(1052, 834, z + 6)),
                             sk.line(at(1008, 846, z + 6), at(1052, 846, z + 6))]  # fmt: skip
            parts["spar"] = sk.line(at(1030, 818, z + 6), at(1030, 862, z + 6))

        s = k.sketch("Vent Sketch", vtop(), vent)
        pick = lambda e: {"feature": s, "sketch_entity": e}  # noqa: E731
        k.add("vent", "Plate Vent",
              {"sketch": {"feature": s}, "face": [vtop()], "boundary": [pick(parts["ring"])],
               "ribs": [pick(e) for e in parts["ribs"]], "spars": [pick(parts["spar"])]},
              rib_width=mm(2), rib_depth=mm(3), rib_offset=mm(0), spar_width=mm(2),
              spar_depth=mm(2), spar_offset=mm(0.5))  # fmt: skip
        k.expect("Plate Vent", inside=[(1030 + 21, 840, z + 3)], outside=[(1040, 840, z + 5)])
        lug = k.block("Draft Lug", 1110, 800, 1140, 830, 20)
        sides = [k.fref((1125, 800, z + 10)), k.fref((1140, 815, z + 10)),
                 k.fref((1125, 830, z + 10)), k.fref((1110, 815, z + 10))]  # fmt: skip
        k.add("draft", "Lug Draft", {"neutral": {"feature": self.top_plane}, "faces": sides},
              angle=deg(5))  # fmt: skip
        k.expect("Lug Draft", inside=[(1125, 800.5, z + 1)], outside=[(1125, 800.5, z + 19)])
        _ = lug

        # Pipes lying on the bed, and a rod standing up from it.
        p42 = k.offset_plane("Pipe Plane", FRONT, z + 2, (0, 0, 1))
        s = k.sketch(
            "Pipe Run", p42, lambda sk, at: sk.line(at(1160, 950, z + 2), at(1210, 950, z + 2))
        )
        spiral = k.add("transition_spiral", "Pipe Easement", {"sketch": {"feature": s}},
                       spiral_length=mm(70), end_radius=mm(45), hand="left")  # fmt: skip
        path = k.add(
            "composite_curve", "Pipe Path", {"items": [{"feature": s}, {"feature": spiral}]}
        )
        k.add("pipe", "Oil Pipe", {"path": {"feature": path}}, operation="boss",
              outer_diameter=mm(6), inner_diameter=mm(4))  # fmt: skip
        k.expect("Oil Pipe", inside=[(1185, 950 + 2.5, z + 2)],
                 outside=[(1185, 950, z + 2), (1185, 950, z + 5.5)])  # fmt: skip
        rod = k.add("sketch3d", "Dipstick Path", {},
                    data={"lines": [{"kind": "line",
                                     "points": [[1330, 960, z - 1], [1330, 960, z + 30],
                                                [1355, 960, z + 55]]}]})  # fmt: skip
        k.add("pipe", "Dipstick", {"path": {"feature": rod}}, operation="boss",
              outer_diameter=mm(4))  # fmt: skip
        k.expect("Dipstick", inside=[(1330, 960, z + 15), (1342.5, 960, z + 42.5)],
                 outside=[(1333, 960, z + 15)])  # fmt: skip

        # A casting pad with a sprue tree, ears under the bed, and a section to finish.
        k.block("Cast Pad", 640, 900, 700, 940, 10)
        feeds = [k.add("ref_point", f"Feed Point {i}", {}, method="values", x=mm(x),
                       y=mm(920), z=mm(z + 10)) for i, x in ((1, 655), (2, 685))]  # fmt: skip
        cup = k.add("ref_point", "Cup Point", {}, method="values", x=mm(670), y=mm(920),
                    z=mm(z + 60))  # fmt: skip
        k.add("sprue_tree", "Casting Sprue",
              {"feed_points": [{"feature": f} for f in feeds], "cup": [{"feature": cup}]},
              layout="tree", cup_diameter=mm(12), cup_height=mm(8), sprue_diameter=mm(5),
              gate_diameter=mm(3))  # fmt: skip
        k.expect("Casting Sprue", inside=[(655, 920, z + 5)],
                 some_inside=[(670, 920, z + h / 2) for h in range(21, 120)])  # fmt: skip
        k.add("corner_ears", "Bed Ears", {"face": [k.fref((700, 500, 0))]},
              ear_diameter=mm(30), ear_thickness=mm(0.4))  # fmt: skip
        k.add(
            "section_cut",
            "Trimmed Edge",
            {},
            data={"zones": [[{"origin": [1399.5, 0.0, 0.0], "normal": [1.0, 0.0, 0.0]}]]},
        )
        k.expect("Trimmed Edge", inside=[(1399, 500, 20)], outside=[(1399.8, 500, 20)])

    def stations(self, count: int = 12) -> None:
        for n in range(count):
            ox = 20.0 + (n % 6) * 230.0
            oy = 20.0 + (n // 6) * 240.0
            self.station(n + 1, ox, oy, (40.0, 45.0, 50.0)[n % 3])

    def build(self, stations: int = 12, shafts: int = 0, plates: int = 0, yard: int = 0) -> None:
        self.bed()
        self.stations(stations)
        for n in range(shafts):  # in the row behind the stations, y = 560
            self.shaft_station(n + 1, 60.0 + n * 330.0, 560.0)
        for n in range(plates):  # behind the shafts
            self.pattern_station(n + 1, 40.0 + n * 170.0, 640.0)
        if yard:
            self.yard()
