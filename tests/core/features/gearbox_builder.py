"""A gearbox housing with its cover, shaft and fittings: one part of many bodies, built
feature by feature to use as many kinds of feature as a solid part can (D1054 to D1068).

The owner asked for a part of at least 200 features using as many feature types as it
could (2026-11-12). This is that part: 318 features of 105 types in 60 bodies. It
found fifteen faults; ``test_gearbox_part.py`` builds parts of it again.

Housing: X 0..160, Y 0..100, Z 0..80. The cover lies on its flange. The shaft, the loose
bodies, the joints, the pattern plate, the imports and the print tools stand clear of it.
"""

from __future__ import annotations

import math

from fdcad.core.document.model import Param
from fdcad.core.features.hole import defaults_for
from tests.core.features.gearbox_kit import FRONT, RIGHT, TOP, Kit, Sketch, deg, mm, num


def rect(at, x0, y0, z0, x1, y1, z1):  # type: ignore[no-untyped-def]
    """Corners of an axis aligned rectangle on a plane square to one model axis."""
    if abs(z0 - z1) < 1e-9:
        return [at(x0, y0, z0), at(x1, y0, z0), at(x1, y1, z0), at(x0, y1, z0)]
    if abs(y0 - y1) < 1e-9:
        return [at(x0, y0, z0), at(x1, y0, z0), at(x1, y0, z1), at(x0, y0, z1)]
    return [at(x0, y0, z0), at(x0, y1, z0), at(x0, y1, z1), at(x0, y0, z1)]


def tapped(size: str, **more):  # type: ignore[no-untyped-def]
    values = {k: mm(round(v, 6)) for k, v in defaults_for("tapped", "iso", size).items()}
    return {"hole_type": "tapped", "standard": "iso", "size": size, "cosmetic_thread": True,
            **values, **more}  # fmt: skip


class Gear(Kit):
    # Stage A: the housing ---------------------------------------------------------

    def housing(self) -> None:
        k = self
        s = k.sketch("Housing Base", FRONT,
                     lambda sk, at: sk.polygon(rect(at, 0, 0, 0, 160, 100, 0)))  # fmt: skip
        self.block = k.add(
            "extrude",
            "Housing Block",
            {"sketch": {"feature": s}},
            operation="boss",
            end_condition="blind",
            depth=mm(80),
            reverse=False,
        )
        k.expect("Housing Block", inside=[(80, 50, 40), (1, 1, 1)], outside=[(80, 50, 81)])
        # On the plain block, before any hole or round: the line runs round the bottom
        # and crosses no face, so the sample opens with no warning. On the finished
        # housing every hole and round has both kinds of draft (a true warning, D1103).
        k.add("parting_line", "Parting Line", {"direction": {"feature": FRONT}})
        corners = [(0, 0, 40), (160, 0, 40), (160, 100, 40), (0, 100, 40)]
        k.add("fillet", "Housing Corners", {"edges": k.erefs(corners)},
              fillet_type="constant", radius=mm(8))  # fmt: skip
        k.expect("Housing Corners", inside=[(8, 1, 40), (1, 8, 40)],
                 outside=[(1, 1, 40), (159, 99, 40)])  # fmt: skip
        k.add("shell", "Housing Shell", {"faces": [k.fref((80, 50, 80))]}, thickness=mm(4))
        k.expect("Housing Shell", inside=[(2, 50, 40), (80, 50, 2), (158, 50, 79)],
                 outside=[(80, 50, 40), (80, 50, 5), (6, 50, 40)])  # fmt: skip
        self.p80 = k.offset_plane("Rim Plane", FRONT, 80, (0, 0, 1))
        self.py50 = k.offset_plane("Middle Plane", TOP, 50, (0, 1, 0))

        def flange(sk, at):  # type: ignore[no-untyped-def]
            sk.polygon(rect(at, -10, -10, 80, 170, 110, 80))
            sk.polygon(rect(at, 4, 4, 80, 156, 96, 80))

        s = k.sketch("Flange Sketch", self.p80, flange)
        self.flange = k.add("extrude", "Top Flange", {"sketch": {"feature": s}},
                            operation="boss", end_condition="blind", depth=mm(6),
                            reverse=k.reverse_for(self.p80, (0, 0, -1)))  # fmt: skip
        k.expect("Top Flange", inside=[(-5, 50, 77), (80, -5, 77), (165, 105, 75)],
                 outside=[(80, 50, 77), (-5, 50, 81), (-5, 50, 73)])  # fmt: skip
        outer = [(-10, -10, 77), (170, -10, 77), (170, 110, 77), (-10, 110, 77)]
        k.add("fillet", "Flange Corners", {"edges": k.erefs(outer)},
              fillet_type="constant", radius=mm(6))  # fmt: skip
        k.expect("Flange Corners", inside=[(-4, -9, 77)], outside=[(-9.5, -9.5, 77)])
        top = k.fref((-5, 50, 80))
        spots = [(20, -5, 80), (140, -5, 80), (20, 105, 80), (140, 105, 80), (-5, 50, 80),
                 (165, 50, 80)]  # fmt: skip
        psk, _ids = k.points("Flange Hole Positions", top, spots)
        k.add("hole", "Flange Threads M5", {"sketch": {"feature": psk}, "face": [top]},
              end_condition="up_to_next", **tapped("M5"))  # fmt: skip
        k.expect("Flange Threads M5", inside=[(23, -5, 77), (-5, 53, 77)],
                 outside=[(20, -5, 79), (20, -5, 75), (165, 50, 77), (20, 105, 75)])  # fmt: skip
        k.add("chamfer", "Flange Underside", {"edges": k.erefs([(80, -10, 74), (80, 110, 74)])},
              chamfer_type="distance_distance", distance=mm(1))  # fmt: skip
        k.expect("Flange Underside", inside=[(80, -9.8, 75.5), (80, -8.5, 74.1)],
                 outside=[(80, -9.8, 74.1), (80, 109.8, 74.1)])  # fmt: skip
        k.add("edge_profile", "Flange Top Edge", {"loop_face": [k.fref((-5, 30, 80))]},
              router_profile="round_over", profile_size=mm(1.5))  # fmt: skip
        k.expect("Flange Top Edge", inside=[(-9, 30, 79), (-5, 30, 79.9)],
                 outside=[(-9.95, 30, 79.95)])  # fmt: skip

    def bearings(self) -> None:
        k = self
        bosses = []
        for name, x, od, bore in (("Input", 55.0, 52.0, 35.0), ("Output", 110.0, 62.0, 47.0)):
            s = k.sketch(f"{name} Boss Sketch", TOP,
                         lambda sk, at, x=x, od=od: sk.circle(at(x, 0, 40), od))  # fmt: skip
            boss = k.add("extrude", f"{name} Bearing Boss", {"sketch": {"feature": s}},
                         operation="boss", end_condition="blind", depth=mm(10),
                         reverse=k.reverse_for(TOP, (0, -1, 0)), draft_angle=deg(3))  # fmt: skip
            s = k.sketch(f"{name} Bore Sketch", TOP,
                         lambda sk, at, x=x, bore=bore: sk.circle(at(x, 0, 40), bore))  # fmt: skip
            cut = k.add(
                "extrude",
                f"{name} Bearing Bore",
                {"sketch": {"feature": s}},
                operation="cut",
                end_condition="mid_plane",
                depth=mm(30),
                reverse=False,
            )
            bosses += [boss, cut]
            r = od / 2 - 1
            k.expect(f"{name} Bearing", inside=[(x + r, -5, 40), (x, -5, 40 - r)],
                     outside=[(x, -5, 40), (x, 2, 40), (x + r + 2, -9, 40)])  # fmt: skip
        self.bosses = bosses
        k.add(
            "mirror",
            "Far Side Bearings",
            {"plane": {"feature": self.py50}, "features": [{"feature": f} for f in bosses]},
        )
        k.expect("Far Side Bearings", inside=[(80, 105, 40), (55, 105, 40 + 24)],
                 outside=[(55, 105, 40), (110, 98, 40), (55, 50, 40)])  # fmt: skip
        ring = [(55, 0, 40 + 26), (110, 0, 40 + 31), (55, 100, 40 + 26), (110, 100, 40 + 31)]
        k.add("fillet", "Boss Roots", {"edges": k.erefs(ring, tol=0.05)},
              fillet_type="constant", radius=mm(2))  # fmt: skip
        k.expect("Boss Roots", inside=[(55, -0.3, 66.3), (110, 100.3, 71.3)],
                 outside=[(55, -1.8, 67.8)])  # fmt: skip
        k.add("ring_groove", "Input Retaining Ring", {"face": [k.fref((55 + 17.5, -5, 40))]},
              ring_type="ring", position=mm(2), from_end="start")  # fmt: skip
        k.expect("Input Retaining Ring", inside=[(55 + 22, -5, 40), (55 + 22, 2, 40)],
                 outside=[(55, -5, 40), (55 + 17, -5, 40), (55 + 17, 2, 40)])  # fmt: skip
        k.add("crush_ribs", "Output Crush Ribs", {"face": [k.fref((110 + 23.5, -5, 40))]},
              rib_count=num(6), rib_width=mm(2), rib_height=mm(0.3), rib_tip=mm(0.6))  # fmt: skip
        k.expect("Output Crush Ribs", inside=[(110 + 27, -5, 40)],
                 outside=[(110, -5, 40), (110 + 22.5, -5, 40 + 3)])  # fmt: skip
        face = k.fref((110, -10, 40 + 27))
        psk, _ids = k.points("Cap Screw Position", face, [(110, -10, 40 + 27)])
        screw = k.add("hole", "Cap Screw M4", {"sketch": {"feature": psk}, "face": [face]},
                      end_condition="blind", **tapped("M4"))  # fmt: skip
        k.expect("Cap Screw M4", inside=[(110, -9, 40 + 27 + 2.5)], outside=[(110, -9, 40 + 27)])
        k.add("circular_pattern", "Cap Screw Circle",
              {"axis": k.fref((110 + 23.5, -8, 40)), "features": [{"feature": screw}]},
              count1=num(4), angle1=deg(360), equal_spacing=True)  # fmt: skip
        k.expect("Cap Screw Circle", inside=[(110 + 20, -9, 40 + 20)],
                 outside=[(110, -9, 13), (137, -9, 40), (83, -9, 40)])  # fmt: skip
        self.axis_out = k.add("ref_axis", "Output Axis", {"first": k.fref((110 + 23.5, -8, 40))},
                              method="cylinder")  # fmt: skip

    def feet(self) -> None:
        k = self
        s = k.sketch("Foot Sketch", FRONT,
                     lambda sk, at: sk.polygon(rect(at, 10, -22, 0, 40, 2, 0)))  # fmt: skip
        foot = k.add(
            "extrude",
            "Foot",
            {"sketch": {"feature": s}},
            operation="boss",
            end_condition="blind",
            depth=mm(10),
            reverse=False,
            draft_angle=deg(5),
        )
        k.expect("Foot", inside=[(25, -11, 5), (25, 1, 5)], outside=[(25, -11, 11), (25, -24, 5)])
        k.add("fillet", "Foot Corners", {"edges": k.erefs([(10.44, -21.56, 5), (39.56, -21.56, 5)],
                                                          tol=0.6)},
              fillet_type="constant", radius=mm(4))  # fmt: skip
        k.expect("Foot Corners", inside=[(13, -19, 5)], outside=[(10.8, -21.2, 5)])
        top = k.fref((25, -11, 10))
        psk, _ids = k.points("Foot Hole Position", top, [(25, -11, 10)])
        hole = k.add(
            "hole",
            "Foot Hole",
            {"sketch": {"feature": psk}, "face": [top]},
            hole_type="simple",
            end_condition="through_all",
            diameter=mm(9),
        )
        k.expect("Foot Hole", inside=[(25 + 5.5, -11, 5)], outside=[(25, -11, 5), (25 + 4, -11, 9)])
        pattern = k.add("linear_pattern", "Feet Along X",
                        {"direction1": {"feature": RIGHT}, "features": [{"feature": foot}]},
                        spacing1=mm(110), count1=num(2), reverse1=False)  # fmt: skip
        k.expect("Feet Along X", inside=[(135, -11, 5), (135, -18, 5)])
        follow = k.add(
            "follow_pattern",
            "Foot Holes Follow",
            {"pattern": {"feature": pattern}, "features": [{"feature": hole}]},
        )
        k.expect("Foot Holes Follow", inside=[(135 + 5.5, -11, 5)], outside=[(135, -11, 5)])
        k.add("mirror", "Far Side Feet",
              {"plane": {"feature": self.py50},
               "features": [{"feature": f} for f in (foot, hole, pattern, follow)]},
              geometry=True)  # fmt: skip
        k.expect("Far Side Feet", inside=[(25 + 5.5, 111, 5), (135 + 5.5, 111, 5)],
                 outside=[(25, 111, 5), (135, 111, 5), (80, 111, 5)])  # fmt: skip
        k.add(
            "polygon_holes",
            "Printable Foot Holes",
            {"faces": [k.fref((25 + 4.5, -11, 5)), k.fref((135 + 4.5, -11, 5))]},
            sides=num(8),
        )
        k.expect("Printable Foot Holes", inside=[(25 + 5.5, -11, 5)],
                 outside=[(25, -11, 5), (25 + 4.4, -11, 5)])  # fmt: skip

    def walls(self) -> None:
        k = self
        wall = k.fref((160, 50, 40))
        s = k.sketch(
            "Fin Sketch", wall, lambda sk, at: sk.polygon(rect(at, 160, 25, 14, 160, 75, 17))
        )
        fin = k.add("extrude", "Cooling Fin", {"sketch": {"feature": s}}, operation="boss",
                    end_condition="blind", depth=mm(8), reverse=k.reverse_for(wall, (1, 0, 0)),
                    draft_angle=deg(4))  # fmt: skip
        k.expect("Cooling Fin", inside=[(164, 50, 15.5)], outside=[(164, 50, 19), (169, 50, 15.5)])
        k.add("linear_pattern", "Cooling Fins",
              {"direction1": {"feature": FRONT}, "features": [{"feature": fin}]},
              spacing1=mm(9), count1=num(6), reverse1=False)  # fmt: skip
        k.expect("Cooling Fins", inside=[(164, 50, 15.5 + 45), (164, 30, 15.5 + 18)],
                 outside=[(164, 50, 19 + 9), (164, 50, 15.5 + 54)])  # fmt: skip
        # The sight glass on the X = 0 wall: a window, a seal groove and four screws.
        wall = k.fref((0, 20, 70))
        s = k.sketch("Sight Glass Sketch", wall, lambda sk, at: sk.circle(at(0, 50, 45), 30))
        k.add(
            "extrude",
            "Sight Glass Window",
            {"sketch": {"feature": s}},
            operation="cut",
            end_condition="blind",
            depth=mm(4),
            reverse=k.reverse_for(wall, (1, 0, 0)),
        )
        k.expect("Sight Glass Window", inside=[(2, 50, 45 + 17)],
                 outside=[(2, 50, 45), (0.5, 50, 45 + 14)])  # fmt: skip
        wall = k.fref((0, 20, 70))
        s = k.sketch("Seal Groove Sketch", wall, lambda sk, at: sk.circle(at(0, 50, 45), 38))
        k.add("oring_groove", "Sight Glass Seal", {"sketch": {"feature": s}},
              cross_section=mm(1.5), use="face")  # fmt: skip
        k.expect("Sight Glass Seal", inside=[(2, 50, 45 + 19), (0.3, 50, 45 + 16.5)],
                 outside=[(0.3, 50, 45 + 19), (0.3, 50 + 19, 45)])  # fmt: skip
        wall = k.fref((0, 20, 70))
        psk, _ids = k.points("Glass Screw Position", wall, [(0, 50, 45 + 24)])
        screw = k.add("hole", "Glass Screw M3", {"sketch": {"feature": psk}, "face": [wall]},
                      end_condition="up_to_next", **tapped("M3"))  # fmt: skip
        k.add("circular_pattern", "Glass Screws",
              {"axis": k.fref((2, 50, 45 + 15)), "features": [{"feature": screw}]},
              count1=num(4), angle1=deg(360), equal_spacing=True)  # fmt: skip
        k.expect("Glass Screws", inside=[(2, 50, 45 + 24 + 2.5), (2, 50 + 17, 45 + 17)],
                 outside=[(2, 50, 69), (2, 50, 21), (2, 26, 45), (2, 74, 45)])  # fmt: skip
        wall = k.fref((0, 20, 70))
        psk, _ids = k.points("Drain Position", wall, [(0, 20, 12)])
        k.add("hole", "Drain Plug M12", {"sketch": {"feature": psk}, "face": [wall]},
              end_condition="up_to_next", **tapped("M12"))  # fmt: skip
        k.expect(
            "Drain Plug M12", inside=[(2, 20, 12 + 7)], outside=[(2, 20, 12), (2, 20 + 4.5, 12)]
        )
        k.add(
            "hose_fitting",
            "Breather Barb",
            {"base_face": [k.fref((0, 20, 70))]},
            fitting="barb",
            hose_diameter=mm(8),
            ring_count=num(3),
            ring_length=mm(4),
            shank_height=mm(3),
            bore_depth=mm(6),
            pos_x=mm(0),
            pos_y=mm(82),
            pos_z=mm(18),
        )
        # No bore diameter is given, so the barb is solid.
        k.expect("Breather Barb", inside=[(-2, 82 + 3.5, 18), (-14, 82, 18), (-1, 82, 18)],
                 outside=[(-2, 82 + 6, 18), (-17, 82, 18)])  # fmt: skip
        wall = k.fref((0, 20, 70))
        s = k.sketch("Nameplate Recess Sketch", wall,
                     lambda sk, at: sk.polygon(rect(at, 0, 70, 52, 0, 94, 66)))  # fmt: skip
        recess = k.add("extrude", "Nameplate Recess", {"sketch": {"feature": s}},
                       operation="cut", end_condition="blind", depth=mm(1.5),
                       reverse=k.reverse_for(wall, (1, 0, 0)))  # fmt: skip
        k.expect("Nameplate Recess", inside=[(2, 82, 59), (0.5, 82, 67)],
                 outside=[(0.5, 82, 59), (0.5, 71, 53)])  # fmt: skip
        k.add("corner_relief", "Recess Corner Relief", {"feature": {"feature": recess}},
              relief_type="dogbone", tool_diameter=mm(2))  # fmt: skip
        # A dogbone: a 2 mm cutter reaching each corner, its centre on the corner's
        # bisector 0.707 mm into the recess, so it bites 0.29 mm into both walls.
        k.expect("Recess Corner Relief", inside=[(0.75, 69.6, 52.7), (0.75, 94.4, 65.3)],
                 outside=[(0.75, 69.8, 52.7), (0.75, 70.7, 51.8), (0.75, 94.2, 65.3)])  # fmt: skip
        k.add(
            "lightening_pockets",
            "Base Pockets",
            {"plate_face": [k.fref((80, 50, 0))]},
            border=mm(8),
            web=mm(3),
            cell=mm(24),
            corner_radius=mm(1),
            pocket_depth=mm(2),
        )
        k.expect("Base Pockets", inside=[(80, 50, 3), (5, 50, 1), (80, 5, 1)])
        self.py30 = py30 = k.offset_plane("Gusset Plane", TOP, 30, (0, 1, 0))
        s = k.sketch("Gusset Line", py30, lambda sk, at: sk.line(at(8, 30, 34), at(34, 30, 8)))
        k.add("rib", "Inside Gusset", {"sketch": {"feature": s}}, thickness=mm(4), side="both",
              direction="parallel", extend="linear")  # fmt: skip
        k.expect("Inside Gusset", inside=[(15, 30, 15), (15, 31.5, 15)],
                 outside=[(15, 35, 15), (25, 30, 25)])  # fmt: skip
        # On the front wall. It stood on the flange, under the cover, where the cover's
        # lip ran round its slots (D1083).
        front = k.fref((80, 0, 20))
        psk, _ids = k.points("Cable Tie Position", front, [(80, 0, 20)])
        k.add("cable_tie", "Cable Tie Loop", {"sketch": {"feature": psk}},
              tie_width=mm(3), tie_thickness=mm(1.2), span=mm(8), cover=mm(2))  # fmt: skip
        # The tunnel (3.4 by 1.6 with the clearance) is too wide for a pointed top under a
        # 2 mm cover, so its top is flat at half the cover: Y 1.0 to 3.6.
        k.expect("Cable Tie Loop", inside=[(80, 0.6, 20), (80, 3.8, 20), (70, 2, 20)],
                 outside=[(80, 2.6, 20), (80, 1.2, 20)])  # fmt: skip

    def references(self) -> None:
        k = self
        k.add("measurement", "Whole Part Measure", {})
        k.add("sensor", "Volume Watch", {}, source="volume", high=Param("2000000", 2000000.0))
        k.add("bounding_box", "Stock Size", {}, box_shape="box", orient="axes")
        k.add("ref_point", "Centre Of Mass", {}, method="centre_of_mass")
        self.frame1 = k.add(
            "coord_system",
            "Shaft Frame",
            {},
            method="angles",
            x=mm(0),
            y=mm(-160),
            z=mm(40),
            rx=deg(0),
            ry=deg(90),
            rz=deg(0),
        )
        k.add("contour", "Level Lines", {"direction": {"feature": FRONT}}, spacing=mm(20))

    # Stage B: the cover, a second body on the flange -------------------------------

    def cover(self) -> None:
        k = self
        s = k.sketch("Cover Outline", self.p80,
                     lambda sk, at: sk.polygon(rect(at, -10, -10, 80, 170, 110, 80)))  # fmt: skip
        self.cover_id = cover = k.add(
            "extrude", "Cover Plate", {"sketch": {"feature": s}}, operation="boss",
            end_condition="blind", depth=mm(6), reverse=k.reverse_for(self.p80, (0, 0, 1)),
            merge=False)  # fmt: skip
        k.expect("Cover Plate", inside=[(80, 50, 83), (-5, -5, 83)], outside=[(80, 50, 87)])
        outer = [(-10, -10, 83), (170, -10, 83), (170, 110, 83), (-10, 110, 83)]
        k.add("fillet", "Cover Corners", {"edges": k.erefs(outer)},
              fillet_type="constant", radius=mm(6))  # fmt: skip
        k.expect("Cover Corners", inside=[(-4, -9, 83)], outside=[(-9.5, -9.5, 83)])
        # A shallow recess under the cover, so its rim is the ring of the flange below it.
        under = k.fref((80, 50, 80), of=cover)
        s = k.sketch("Cover Recess Sketch", under,
                     lambda sk, at: sk.polygon(rect(at, 4, 4, 80, 156, 96, 80)))  # fmt: skip
        k.add(
            "extrude",
            "Cover Recess",
            {"sketch": {"feature": s}},
            operation="cut",
            end_condition="blind",
            depth=mm(1),
            reverse=k.reverse_for(under, (0, 0, 1)),
        )
        k.expect("Cover Recess", inside=[(80, 50, 81.5), (1, 50, 80.5)],
                 outside=[(80, 50, 80.5), (5, 50, 80.5)])  # fmt: skip
        # The housing's opening has the rounded inside corners of its shell (radius 4),
        # so the recess gets them too, or the lip and the groove part at each corner.
        inner = [(4, 4, 80.5), (156, 4, 80.5), (156, 96, 80.5), (4, 96, 80.5)]
        k.add("fillet", "Cover Recess Corners", {"edges": k.erefs(inner)},
              fillet_type="constant", radius=mm(4))  # fmt: skip
        k.expect("Cover Recess Corners", inside=[(4.5, 4.5, 80.5), (155.5, 95.5, 80.5)],
                 outside=[(6, 6, 80.5)])  # fmt: skip
        k.add(
            "lip_groove",
            "Cover Seal Lip",
            {
                "lip_faces": [k.fref((-5, 30, 80), of=self.flange)],
                "groove_faces": [k.fref((-5, 30, 80), of=cover)],
            },
            lip_width=mm(1.5),
            lip_height=mm(2),
            spacing=mm(0.2),
            gap=mm(0.2),
            link=True,
        )
        # The lip stands on the flange along its inside edge and the groove is cut in
        # the cover over it, 0.2 mm wider and deeper.
        k.expect("Cover Seal Lip", inside=[(3.25, 50, 81), (1.5, 50, 81), (3.25, 50, 79)],
                 outside=[(3.25, 50, 82.1), (2.35, 50, 81), (5, 50, 80.5)])  # fmt: skip
        top = k.fref((80, 50, 86))
        spots = [(20, -5, 86), (140, -5, 86), (20, 105, 86), (140, 105, 86), (-5, 50, 86),
                 (165, 50, 86)]  # fmt: skip
        psk, _ids = k.points("Cover Screw Positions", top, spots)
        k.add("hole", "Cover Screw Holes", {"sketch": {"feature": psk}, "face": [top]},
              hole_type="simple", standard="iso", size="M5", end_condition="up_to_next",
              diameter=mm(5.5))  # fmt: skip
        k.expect("Cover Screw Holes", inside=[(20 + 3.5, -5, 83), (-5, 50 + 3.5, 83)],
                 outside=[(20, -5, 83), (165, 50, 81), (140, 105, 85)])  # fmt: skip

    def cover_details(self) -> None:
        k = self
        top = lambda: k.fref((80, 96, 86))  # noqa: E731  (a spot nothing else uses)

        def vent(sk, at):  # type: ignore[no-untyped-def]
            self.v_ring = sk.circle(at(110, 50, 86), 40)
            self.v_ribs = [sk.line(at(88, 44, 86), at(132, 44, 86)),
                           sk.line(at(88, 56, 86), at(132, 56, 86))]  # fmt: skip
            self.v_spar = sk.line(at(110, 28, 86), at(110, 72, 86))

        s = k.sketch("Vent Sketch", top(), vent)
        pick = lambda e: {"feature": s, "sketch_entity": e}  # noqa: E731
        k.add("vent", "Cover Vent",
              {"sketch": {"feature": s}, "face": [top()], "boundary": [pick(self.v_ring)],
               "ribs": [pick(e) for e in self.v_ribs], "spars": [pick(self.v_spar)]},
              rib_width=mm(2), rib_depth=mm(3), rib_offset=mm(0), spar_width=mm(2),
              spar_depth=mm(2), spar_offset=mm(0.5))  # fmt: skip
        k.expect("Cover Vent", inside=[(120, 44, 85), (110 + 21, 50, 83), (110, 35, 84.5)],
                 outside=[(120, 50, 83), (120, 44, 82), (100, 64, 83)])  # fmt: skip
        s = k.sketch("Grille Area", top(),
                     lambda sk, at: sk.polygon(rect(at, 14, 60, 86, 66, 92, 86)))  # fmt: skip
        k.add(
            "fill_pattern",
            "Cover Grille",
            {"sketch": {"feature": s}},
            layout="staggered",
            spacing=mm(7),
            shape="circle",
            size=mm(3),
            margin=mm(1),
        )
        k.expect("Cover Grille", inside=[(12, 76, 83), (40, 94, 83)],
                 some_outside=[(15 + i / 2, 61 + j, 83) for i in range(100)
                               for j in range(31)])  # fmt: skip
        s = k.sketch("Hinge Area", top(),
                     lambda sk, at: sk.polygon(rect(at, 78, 78, 86, 128, 92, 86)))  # fmt: skip
        k.add("living_hinge", "Flex Slits", {"sketch": {"feature": s}},
              slit_length=mm(12), slit_width=mm(1), bridge=mm(3), row_spacing=mm(3))  # fmt: skip
        k.expect("Flex Slits", inside=[(76, 85, 83), (130, 85, 83)],
                 some_outside=[(79 + i / 4, 79 + j, 83) for i in range(196)
                               for j in range(13)])  # fmt: skip
        plane = k.plane_of(top())
        sk = Sketch()
        from fdcad.core.sketch.text import SketchText
        from fdcad.samples.builder import to_local

        x, y = to_local(plane, (50.0, 8.0, 86.0))
        sk.texts.append(SketchText("t1", "GB-200", x=x, y=y, height=8.0, bold=True))
        s = k.b.sketch("Inlay Text", top(), sk)
        k.add("inlay", "Name Inlay", {"sketch": {"feature": s}}, depth=mm(1))
        # The letters are cut 1 mm deep and the cut material is a body of its own, so
        # the part is as full as before; no letter may go deeper.
        k.expect("Name Inlay", inside=[(60, 12, 84.5), (30, 12, 84.5)])
        sk = Sketch()
        x, y = to_local(plane, (14.0, 44.0, 86.0))
        sk.texts.append(SketchText("t1", "OIL", x=x, y=y, height=6.0))
        s = k.b.sketch("Oil Mark Text", top(), sk)
        k.add("mark", "Oil Mark", {"sketch": {"feature": s}})
        k.expect("Oil Mark", inside=[(14 + 3 * i / 10, 44 + 3 * j / 10, 85.9)
                                     for i in range(0, 60, 7)
                                     for j in range(0, 60, 7)])  # fmt: skip
        s = k.sketch("Roof Outline", top(),
                     lambda sk, at: sk.polygon(rect(at, 60, 24, 86, 80, 40, 86)))  # fmt: skip
        roof = k.add("roof", "Label Roof", {"sketch": {"feature": s}}, slope=deg(30),
                     max_height=mm(3), operation="boss")  # fmt: skip
        k.expect("Label Roof", inside=[(70, 32, 88.5), (61, 32, 86.3), (70, 25, 86.3)],
                 outside=[(70, 32, 89.5), (60.5, 32, 86.6), (70, 24.5, 86.6)])  # fmt: skip
        k.add("stone_setting", "Indicator Seat", {"seat_face": [k.fref((70, 32, 89), of=roof)]},
              stone_diameter=mm(3), girdle_depth=mm(0.5), prongs=num(4), prong_diameter=mm(0.8),
              prong_height=mm(1))  # fmt: skip
        # A 3 mm seat in the middle of the roof's flat top, a prong at each quarter.
        k.expect("Indicator Seat", inside=[(70, 32 + 2.5, 88.5), (73, 32, 88.5), (70, 33.7, 89.5)],
                 outside=[(70, 32, 88.8), (71, 33, 88.8), (71, 33, 89.5)])  # fmt: skip
        s = k.sketch("Breather Boss Sketch", top(), lambda sk, at: sk.circle(at(140, 88, 86), 16))
        boss = k.add(
            "extrude",
            "Breather Boss",
            {"sketch": {"feature": s}},
            operation="boss",
            end_condition="blind",
            depth=mm(6),
            reverse=False,
        )
        k.expect("Breather Boss", inside=[(140, 88, 91), (147.5, 88, 91)],
                 outside=[(148.5, 88, 91), (140, 88, 93)])  # fmt: skip
        k.add("dome", "Breather Dome", {"faces": [k.fref((140, 88, 92), of=boss)]},
              distance=mm(4), elliptical=True)  # fmt: skip
        k.expect("Breather Dome", inside=[(140, 88, 95.5), (147.5, 88, 92.2)],
                 outside=[(140, 88, 96.5), (147.5, 88, 95)])  # fmt: skip

    def filler(self) -> None:
        k = self

        def tube(sk, at):  # type: ignore[no-untyped-def]
            sk.polygon([at(36, 30, 86), at(40, 30, 86), at(40, 30, 100), at(36, 30, 100)])
            self.f_axis = sk.line(at(30, 30, 80), at(30, 30, 104), construction=True)

        s = k.sketch("Filler Neck Profile", self.py30, tube)
        self.neck = k.add("revolve", "Filler Neck",
                          {"sketch": {"feature": s}, "axis": {"sketch_entity": self.f_axis}},
                          operation="boss", direction="one_direction", angle=deg(360),
                          reverse=False)  # fmt: skip
        k.expect("Filler Neck", inside=[(38, 30, 95), (22, 30, 95), (30, 38, 99)],
                 outside=[(30, 30, 95), (41, 30, 95), (38, 30, 101)])  # fmt: skip

        def bore(sk, at):  # type: ignore[no-untyped-def]
            sk.polygon([at(30, 30, 79), at(36, 30, 79), at(36, 30, 90), at(30, 30, 90)])
            self.f_axis2 = sk.line(at(30, 30, 79), at(30, 30, 104), construction=True)

        s = k.sketch("Filler Bore Profile", self.py30, bore)
        k.add(
            "revolve",
            "Filler Bore",
            {"sketch": {"feature": s}, "axis": {"sketch_entity": self.f_axis2}},
            operation="cut",
            direction="one_direction",
            angle=deg(360),
            reverse=False,
        )
        k.expect("Filler Bore", inside=[(37, 30, 88), (20, 30, 83)],
                 outside=[(30, 30, 83), (30, 30, 80.5), (35, 30, 89), (25, 30, 84)])  # fmt: skip
        k.add("modeled_thread", "Filler Thread", {"edge": [k.eref((40, 30, 100))]},
              standard="iso", size="M20", diameter=mm(20), pitch=mm(2.5), method="cut",
              hand="right", end_condition="blind", length=mm(9), form="printable")  # fmt: skip
        k.expect("Filler Thread", inside=[(38, 30, 95), (38, 30, 90)],
                 some_outside=[(39.6, 30, 91 + 0.2 * i) for i in range(45)])  # fmt: skip
        # The handle: a pipe along a curve through typed points.
        pts = [[150, 14, 84], [150, 20, 100], [150, 42, 110], [150, 64, 100], [150, 70, 84]]
        curve = k.add("point_curve", "Handle Curve", {}, data={"points": pts})
        k.add("pipe", "Handle", {"path": {"feature": curve}}, operation="boss",
              outer_diameter=mm(8))  # fmt: skip
        k.expect("Handle", inside=[(150, 42, 110), (150, 20, 100), (150, 42, 113)],
                 outside=[(150, 42, 115), (150, 42, 105)])  # fmt: skip
        # Two snap hooks under the cover that catch in the housing's end walls.
        for name, x, back in (("Left", 7.5, False), ("Right", 152.5, True)):
            hook = k.add(
                "snap_hook", f"{name} Snap Hook",
                {"face": [k.fref((80, 50, 81))], "hook_direction": {"feature": RIGHT}},
                body_height=mm(8), base_depth=mm(3), top_depth=mm(2.5), total_width=mm(10),
                overhang=mm(1.5), hook_height=mm(2.5), lip_height=mm(0.6), top_draft=deg(30),
                hook_reverse=not back, pos_x=mm(x), pos_y=mm(70), pos_z=mm(81))  # fmt: skip
            k.add("snap_groove", f"{name} Snap Groove",
                  {"hook": {"feature": hook}, "body": [k.fref((80, 50, 0))]},
                  offset_height=mm(0.2), gap_height=mm(0.3), groove_clearance=mm(0.2),
                  gap_clearance=mm(0.2), offset_width=mm(0.3))  # fmt: skip

    # Stage C: the output shaft, a body of its own beside the housing -----------------
    # Its axis runs along X at y = -160, z = 40, from x = 0 to x = 200.

    def shaft(self) -> None:
        k = self
        ya, z = -160.0, 40.0
        self.pz40 = k.offset_plane("Shaft Plane", FRONT, 40, (0, 0, 1))
        steps = [(0, 0), (0, 10), (30, 10), (30, 12.5), (60, 12.5), (60, 17.5), (120, 17.5),
                 (120, 12.5), (160, 12.5), (160, 10), (200, 10), (200, 0)]  # fmt: skip

        def profile(sk, at):  # type: ignore[no-untyped-def]
            lines = sk.polygon([at(x, ya + r, z) for x, r in steps])
            self.s_axis = lines[-1]

        s = k.sketch("Shaft Profile", self.pz40, profile)
        self.shaft_id = k.add(
            "revolve", "Shaft", {"sketch": {"feature": s}, "axis": {"sketch_entity": self.s_axis}},
            operation="boss", direction="one_direction", angle=deg(360), reverse=False,
            merge=False)  # fmt: skip
        r = lambda x, rad, a=90: (x, ya + rad * math.cos(math.radians(a)),  # noqa: E731
                                  z + rad * math.sin(math.radians(a)))  # fmt: skip
        k.expect("Shaft", inside=[r(15, 9), r(90, 17), r(140, 12), r(190, 9, 200)],
                 outside=[r(15, 11), r(90, 18), r(140, 13), r(-1, 5), r(201, 5)])  # fmt: skip
        on = lambda x, r: (x, ya + r, z)  # noqa: E731  (a point on the shaft's near side)
        k.add("modeled_thread", "Shaft Thread", {"edge": [k.eref(on(0, 10))]},
              standard="iso", size="M20", diameter=mm(20), pitch=mm(2.5), method="cut",
              hand="right", end_condition="blind", length=mm(22), lead_in=True)  # fmt: skip
        k.expect("Shaft Thread", inside=[r(10, 8), r(25, 9.8)],
                 some_outside=[r(0.5 + 0.25 * i, 9.6) for i in range(80)])  # fmt: skip
        k.add("chamfer", "Shaft End Chamfer", {"edges": [k.eref(on(200, 10))]},
              chamfer_type="distance_distance", distance=mm(1))  # fmt: skip
        k.expect("Shaft End Chamfer", inside=[r(198.5, 9.5)], outside=[r(199.7, 9.7)])
        # The last pick is on top of the circle: on the near side lies the seam of the
        # face beyond it, which once took the pick (D1084).
        k.add("fillet", "Shaft Shoulders",
              {"edges": k.erefs([on(60, 12.5), on(120, 12.5), (160, ya, z + 10)])},
              fillet_type="constant", radius=mm(1))  # fmt: skip
        k.expect("Shaft Shoulders", inside=[r(59.8, 12.7), r(120.2, 12.7), r(160.2, 10.2)],
                 outside=[r(59.2, 13.3), r(160.8, 10.8)])  # fmt: skip
        k.add(
            "shaft_shape",
            "Gear Keyway",
            {"face": [k.fref(on(90, 17.5))]},
            shaft_form="keyway",
            key_standard="metric",
            length=mm(40),
            from_end="start",
        )
        # A 10 mm keyseat 5 deep from the face's start, on the side away from the pick.
        k.expect("Gear Keyway", inside=[r(80, 16, 0), r(105, 17, 180), r(80, 12, 180)],
                 outside=[r(80, 16, 180), r(62, 16, 180), r(98, 16, 180),
                          r(80, 16, 195)])  # fmt: skip
        k.add("shaft_shape", "Hex Drive End", {"face": [k.fref(on(185, 10))]},
              shaft_form="hex", length=mm(15), from_end="end")  # fmt: skip
        k.expect("Hex Drive End", inside=[r(192, 8.5), r(192, 9.8, 30), r(180, 9.8)],
                 outside=[r(192, 9.2, 0), r(192, 9.2, 60)])  # fmt: skip
        k.add("ring_groove", "Shaft Retaining Ring", {"face": [k.fref(on(140, 12.5))]},
              ring_type="ring", position=mm(6), from_end="end")  # fmt: skip
        k.expect("Shaft Retaining Ring", inside=[r(150, 12), r(154, 11.5)],
                 outside=[r(154, 12.2), r(154, 12.2, 270)])  # fmt: skip
        k.add("oring_groove", "Shaft Seal", {"face": [k.fref(on(45, 12.5))]},
              cross_section=mm(2), use="static", position=mm(10), from_end="start")  # fmt: skip
        k.expect("Shaft Seal", inside=[r(38, 12), r(41, 10.7), r(44, 12)],
                 outside=[r(41, 11.5), r(41, 11.5, 0)])  # fmt: skip
        k.add("cosmetic_thread", "Lock Nut Thread", {"edge": [k.eref(on(120, 17.5))]},
              standard="iso", size="M35x1.5", diameter=mm(35), pitch=mm(1.5),
              end_condition="blind", length=mm(8))  # fmt: skip
        k.expect("Lock Nut Thread", inside=[r(116, 17.4), r(116, 17.4, 270)])
        end = k.fref((200, ya + 4, z))
        psk, _ids = k.points("Centre Hole Position", end, [(200, ya, z)])
        k.add("hole", "Centre Hole", {"sketch": {"feature": psk}, "face": [end]},
              hole_type="simple", end_condition="blind", diameter=mm(4), depth=mm(8),
              bottom="drill_point", tip_angle=deg(118))  # fmt: skip
        k.expect("Centre Hole", inside=[r(198, 2.5), r(190, 0.5)],
                 outside=[r(199, 0.5), r(192.5, 0.5)])  # fmt: skip
        s = k.sketch("Cross Hole Sketch", self.pz40, lambda sk, at: sk.circle(at(110, ya, z), 5))
        k.add(
            "extrude",
            "Cross Hole",
            {"sketch": {"feature": s}},
            operation="cut",
            end_condition="through_all_both",
            depth=mm(1),
            reverse=False,
        )
        k.expect("Cross Hole", inside=[r(113, 15), r(110, 15, 0)],
                 outside=[r(110, 15), r(110, 15, 270), r(110, 0.5, 0)])  # fmt: skip
        above = k.add("ref_point", "Above The Shaft", {}, method="values",
                      x=mm(75), y=mm(ya), z=mm(z + 60))  # fmt: skip
        wall = k.fref((75, ya, z + 17.5))
        self.p_label = k.add(
            "ref_plane",
            "Shaft Label Plane",
            {"first": wall, "second": {"feature": above}},
            method="tangent",
        )
        s = k.sketch("Shaft Label Sketch", self.p_label,
                     lambda sk, at: sk.polygon(rect(at, 66, ya - 4, z + 17.5, 80, ya + 4,
                                                    z + 17.5)))  # fmt: skip
        k.add("wrap", "Shaft Label", {"sketch": {"feature": s}, "face": [wall]},
              wrap_type="deboss", thickness=mm(0.4), method="analytical")  # fmt: skip
        k.expect("Shaft Label", inside=[r(73, 16.9), r(63, 17.3), r(83, 17.3)],
                 outside=[r(73, 17.3), r(67, 17.3)])  # fmt: skip

    def spring(self) -> None:
        k = self
        ya, z = -160.0, 40.0
        px = k.offset_plane("Spring Plane", RIGHT, 215, (1, 0, 0))
        s = k.sketch("Spring Circle", px, lambda sk, at: sk.circle(at(215, ya, z), 30))
        helix = k.add("helix", "Spring Helix", {"sketch": {"feature": s}},
                      definition="pitch_turns", pitch=mm(7), turns=num(5))  # fmt: skip
        k.add("sweep", "Spring", {"path": {"feature": helix}}, operation="boss",
              profile_type="circular", diameter=mm(3), merge=False)  # fmt: skip
        coil = [(215 + i / 4, ya, z + 15) for i in range(140)]
        k.expect("Spring", outside=[(230, ya, z), (230, ya, z + 17.5), (253, ya, z + 15)],
                 some_inside=coil)  # fmt: skip
        # An oil pipe: a straight run, an easement spiral, joined into one path.
        s = k.sketch("Pipe Run", FRONT, lambda sk, at: sk.line(at(0, -215, 0), at(50, -215, 0)))
        spiral = k.add("transition_spiral", "Pipe Easement", {"sketch": {"feature": s}},
                       spiral_length=mm(70), end_radius=mm(45), hand="left")  # fmt: skip
        path = k.add(
            "composite_curve", "Pipe Path", {"items": [{"feature": s}, {"feature": spiral}]}
        )
        k.add("pipe", "Oil Pipe", {"path": {"feature": path}}, operation="boss",
              outer_diameter=mm(6), inner_diameter=mm(4), merge=False)  # fmt: skip
        k.expect("Oil Pipe", inside=[(25, -215 + 2.5, 0), (25, -215, 2.5)],
                 outside=[(25, -215, 0), (25, -215 + 3.5, 0)])  # fmt: skip
        lines = [{"kind": "line", "points": [[140, -215, 0], [140, -215, 30], [165, -215, 55]]}]
        rod = k.add("sketch3d", "Dipstick Path", {}, data={"lines": lines})
        k.add("pipe", "Dipstick", {"path": {"feature": rod}}, operation="boss",
              outer_diameter=mm(4), merge=False)  # fmt: skip
        k.expect("Dipstick", inside=[(140, -215, 15), (152.5, -215, 42.5)],
                 outside=[(140, -215 + 3, 15), (140, -215, 45)])  # fmt: skip
        s = k.sketch("Mark Line", FRONT, lambda sk, at: sk.line(at(70, -172, 0), at(110, -148, 0)))
        k.add("projected_curve", "Shaft Mark Curve",
              {"sketch": {"feature": s}, "faces": [k.fref((90, ya, z + 17.5))]},
              mode="faces", both=True)  # fmt: skip

    # Helpers for the loose bodies ---------------------------------------------------

    def box(self, name: str, x0: float, y0: float, x1: float, y1: float, h: float) -> str:
        """A block standing on the Front plane, as a body of its own."""
        s = self.sketch(f"{name} Sketch", FRONT,
                        lambda sk, at: sk.polygon(rect(at, x0, y0, 0, x1, y1, 0)))  # fmt: skip
        return self.add(
            "extrude",
            name,
            {"sketch": {"feature": s}},
            operation="boss",
            end_condition="blind",
            depth=mm(h),
            reverse=False,
            merge=False,
        )

    def frame(self, name: str, x: float, y: float, z: float) -> dict:
        fid = self.add("coord_system", name, {}, method="angles", x=mm(x), y=mm(y), z=mm(z),
                       rx=deg(0), ry=deg(0), rz=deg(0))  # fmt: skip
        return {"feature": fid}

    # Stage D: a knob, bars to deform and primitives -----------------------------------

    def knob(self) -> None:
        k = self
        s1 = k.sketch("Knob Base Section", FRONT, lambda sk, at: sk.circle(at(0, 200, 0), 30))
        p20 = k.offset_plane("Knob Middle Plane", FRONT, 20, (0, 0, 1))
        s2 = k.sketch("Knob Middle Section", p20, lambda sk, at: sk.circle(at(0, 200, 20), 40))
        p36 = k.offset_plane("Knob Top Plane", FRONT, 36, (0, 0, 1))
        s3 = k.sketch("Knob Top Section", p36, lambda sk, at: sk.circle(at(0, 200, 36), 26))
        self.knob_id = k.add("loft", "Knob",
                             {"profiles": [{"feature": s} for s in (s1, s2, s3)]},
                             operation="boss", merge=False)  # fmt: skip
        k.expect("Knob", inside=[(0, 200, 1), (19, 200, 20), (12, 200, 35)],
                 outside=[(16, 200, 1), (21, 200, 20), (0, 200, 37)])  # fmt: skip
        k.add(
            "dome", "Knob Crown", {"faces": [k.fref((0, 200, 36))]}, distance=mm(5), continuous=True
        )
        k.expect("Knob Crown", inside=[(0, 200, 40.5)], outside=[(0, 200, 41.5)])
        stem = k.add("primitive", "Knob Stem", {"frame": self.frame("Stem Frame", 0, 200, -15)},
                     kind="cylinder", operation="boss", diameter=mm(16), height=mm(15))  # fmt: skip
        k.expect("Knob Stem", inside=[(0, 200, -7), (7.5, 200, -7)],
                 outside=[(8.5, 200, -7), (0, 200, -16)])  # fmt: skip
        k.add("knurl", "Stem Knurl", {"round_face": [k.fref((8, 200, -7))]},
              knurl_pattern="straight", knurl_pitch=mm(2.5), knurl_depth=mm(0.5))  # fmt: skip
        ring = [(7.8 * math.cos(a / 50), 200 + 7.8 * math.sin(a / 50), -7) for a in range(315)]
        k.expect("Stem Knurl", inside=[(0, 200, -7), (7, 200, -7)], some_outside=ring)
        k.add("linked_copy", "Second Knob", {"bodies": [k.fref((0, 200, -15), of=stem)]},
              place="offset", dx=mm(-60), dy=mm(0), dz=mm(0))  # fmt: skip
        # The copy is the knob with its stem: one body. It once stood 60 mm along Y, in the
        # float ball.
        k.expect("Second Knob", inside=[(-60, 200, -7), (-60, 200, 20)], outside=[(-60, 200, 42)])

    def deforms(self) -> None:
        k = self
        pick = lambda x: [k.fref((x + 5, 195, 30))]  # noqa: E731  (the bar's Y = 195 side)
        k.box("Twist Bar", 40, 195, 50, 205, 60)
        k.add("twist", "Twist", {"bodies": pick(40)}, angle=deg(90))
        k.expect("Twist", inside=[(51.5, 200, 30), (45, 200, 59), (49.5, 195.5, 1)],
                 outside=[(49.6, 195.4, 30), (45, 200, 61)])  # fmt: skip
        k.box("Taper Bar", 70, 195, 80, 205, 60)
        k.add("taper", "Taper", {"bodies": pick(70)}, factor=num(0.5))
        k.expect("Taper", inside=[(74, 200, 59), (79, 200, 1)], outside=[(79, 200, 59)])
        k.box("Stretch Bar", 100, 195, 110, 205, 60)
        k.add("stretch", "Stretch", {"bodies": pick(100)}, distance=mm(10))
        k.expect("Stretch", inside=[(105, 200, 65)], outside=[(105, 200, 71)])
        k.box("Bend Bar", 130, 195, 140, 205, 60)
        k.add("bend", "Bend", {"bodies": pick(130)}, bend_by="angle", angle=deg(40))
        k.expect("Bend", inside=[(135, 200, 2)], outside=[(135, 200, 59)])
        k.box("Flow Bar", 160, 195, 170, 205, 60)
        curve = k.add("point_curve", "Flow Curve", {},
                      data={"points": [[165, 200, 0], [165, 200, 25], [175, 200, 50],
                                       [195, 200, 65]]})  # fmt: skip
        k.add("flow", "Flow Along Curve", {"bodies": pick(160), "path": {"feature": curve}},
              fit=True)  # fmt: skip
        k.expect("Flow Along Curve", inside=[(165, 200, 5)], outside=[(165, 200, 58)])
        k.box("Dent Bar", 220, 195, 230, 205, 60)
        spot = k.add("ref_point", "Dent Point", {}, method="values", x=mm(225), y=mm(195),
                     z=mm(30))  # fmt: skip
        k.add("deform_point", "Pulled Point", {"point": {"feature": spot}, "bodies": pick(220)},
              distance=mm(3), radius=mm(15), stiffness=num(0.3))  # fmt: skip
        k.expect("Pulled Point", inside=[(225, 200, 30), (225, 195.5, 50)],
                 outside=[(225, 194.5, 50)])  # fmt: skip
        k.box("Push Bar", 250, 195, 260, 205, 60)
        spot = k.add("ref_point", "Push Point", {}, method="values", x=mm(255), y=mm(195),
                     z=mm(30))  # fmt: skip
        k.add("surface_push", "Thumb Dent",
              {"point": {"feature": spot}, "direction": {"feature": TOP}, "bodies": pick(250)},
              tool="sphere", depth=mm(2), tool_x=mm(6))  # fmt: skip
        k.expect("Thumb Dent", inside=[(255, 198, 30), (255, 195.5, 40)],
                 outside=[(255, 196, 30)])  # fmt: skip
        k.box("Curve Bar", 280, 195, 290, 205, 60)
        side = k.fref((285, 195, 30))
        a = k.sketch("Curve From", side, lambda sk, at: sk.line(at(280, 195, 20), at(290, 195, 20)))
        side = k.fref((285, 195, 30))
        b = k.sketch("Curve To", side, lambda sk, at: sk.line(at(280, 195, 23), at(290, 195, 23)))
        k.add("deform_curve", "Curve To Curve",
              {"initial": {"feature": a}, "target": {"feature": b}, "bodies": pick(280)},
              radius=mm(12), tolerance=mm(0.5))  # fmt: skip
        k.expect("Curve To Curve", inside=[(285, 200, 30), (285, 200, 59)])

    def primitives(self) -> None:
        k = self
        ball = k.add(
            "primitive",
            "Float Ball",
            {"frame": self.frame("Ball Frame", 0, 280, 15)},
            kind="sphere",
            operation="boss",
            diameter=mm(30),
            centred=True,
            merge=False,
        )
        k.expect("Float Ball", inside=[(0, 280, 15), (0, 280, 29)], outside=[(0, 280, 31)])
        k.add("shell", "Hollow Float", {"body": [k.fref((0, 280, 30), of=ball)]},
              thickness=mm(2))  # fmt: skip
        k.expect("Hollow Float", inside=[(0, 280, 29), (0, 280, 1)],
                 outside=[(0, 280, 15), (0, 280, 26)])  # fmt: skip
        k.add("drain_holes", "Float Drain", {}, hole_diameter=mm(3), toward="bottom")
        k.expect("Float Drain", inside=[(0, 280, 29), (2.5, 280, 1)], outside=[(0, 280, 1)])
        cone = k.add("primitive", "Cone", {"frame": self.frame("Cone Frame", 50, 280, 0)},
                     kind="cone", operation="boss", diameter=mm(30), diameter2=mm(10),
                     height=mm(30), merge=False)  # fmt: skip
        k.add("scale", "Bigger Cone", {"bodies": [k.fref((50, 280, 0), of=cone)]},
              uniform=True, factor=num(1.2), about="centroid")  # fmt: skip
        # About the centroid of the solid, 10.4 mm up: the cone now spans Z -2.1 to 33.9.
        k.expect("Bigger Cone", inside=[(67, 280, -1.5), (50, 280, 33.5)],
                 outside=[(50, 280, 34.5), (50, 280, -2.5), (69, 280, -1)])  # fmt: skip
        torus = k.add(
            "primitive",
            "Ring",
            {"frame": self.frame("Ring Frame", 100, 280, 10)},
            kind="torus",
            operation="boss",
            ring=mm(30),
            tube=mm(8),
            centred=True,
            merge=False,
        )
        k.add("offset_body", "Thicker Ring", {"bodies": [k.fref((100 + 19, 280, 10), of=torus)]},
              distance=mm(1))  # fmt: skip
        k.expect("Thicker Ring", inside=[(119.5, 280, 10), (115, 280, 14.5)],
                 outside=[(120.5, 280, 10), (100, 280, 10), (109.5, 280, 10)])  # fmt: skip
        wedge = k.add("primitive", "Wedge", {"frame": self.frame("Wedge Frame", 140, 270, 0)},
                      kind="wedge", operation="boss", length=mm(30), width=mm(20),
                      height=mm(20), top=mm(5), merge=False)  # fmt: skip
        # Stacked above it: along Y the second copy stood in the joints' rail.
        k.add("move_copy_body", "Wedge Copies", {"bodies": [k.fref((150, 280, 0), of=wedge)]},
              mode="translate", copy=True, count=num(2), translate_by="delta", dx=mm(0),
              dy=mm(0), dz=mm(30))  # fmt: skip
        k.expect("Wedge Copies", inside=[(150, 280, 1), (150, 280, 31), (150, 280, 61)],
                 outside=[(150, 280, 25), (150, 280, 91)])  # fmt: skip
        k.add("primitive", "Hex Bar", {"frame": self.frame("Hex Frame", 200, 280, 0)},
              kind="prism", operation="boss", diameter=mm(30), sides=num(6), height=mm(20),
              merge=False)  # fmt: skip
        k.expect("Hex Bar", inside=[(200, 280 + 12, 10), (214, 280, 10)],
                 outside=[(200, 280 + 16, 10), (200, 280, 21)])  # fmt: skip
        self.tube = k.add("primitive", "Sleeve", {"frame": self.frame("Sleeve Frame", 250, 280, 0)},
                          kind="tube", operation="boss", diameter=mm(30), inner=mm(20),
                          height=mm(20), merge=False)  # fmt: skip
        k.expect("Sleeve", inside=[(262, 280, 10)], outside=[(250, 280, 10), (266, 280, 10)])

    def body_tools(self) -> None:
        k = self
        a = k.box("Block A", 300, 260, 340, 300, 20)
        tool = k.add("primitive", "Plug A", {"frame": self.frame("Plug A Frame", 340, 280, 5)},
                     kind="cylinder", operation="boss", diameter=mm(24), height=mm(30),
                     merge=False)  # fmt: skip
        k.add("combine", "Block Less Plug",
              {"main": k.fref((305, 265, 20), of=a), "bodies": [k.fref((340, 280, 35), of=tool)]},
              operation="subtract")  # fmt: skip
        k.expect("Block Less Plug", inside=[(320, 280, 10), (329, 262, 10), (339, 280, 3)],
                 outside=[(335, 280, 10), (345, 280, 30), (339, 280, 10)])  # fmt: skip
        b1 = k.box("Block B1", 360, 260, 390, 290, 15)
        b2 = k.box("Block B2", 380, 280, 410, 310, 15)
        k.add("combine", "Blocks Joined",
              {"bodies": [k.fref((365, 265, 15), of=b1), k.fref((405, 305, 15), of=b2)]},
              operation="add")  # fmt: skip
        k.expect("Blocks Joined", inside=[(365, 265, 7), (385, 285, 7), (405, 305, 7)],
                 outside=[(405, 265, 7)])  # fmt: skip
        c1 = k.box("Block C1", 430, 260, 460, 290, 15)
        c2 = k.box("Block C2", 450, 280, 480, 310, 15)
        k.add("intersect", "Blocks Overlap",
              {"bodies": [k.fref((435, 265, 15), of=c1), k.fref((475, 305, 15), of=c2)]},
              regions="overlap", merge=True)  # fmt: skip
        k.expect("Blocks Overlap", inside=[(455, 285, 7)], outside=[(435, 265, 7), (475, 305, 7)])
        d = k.box("Block D", 500, 260, 560, 300, 20)
        cut = k.offset_plane("Split Plane", RIGHT, 530, (1, 0, 0))
        k.add(
            "split",
            "Block Split",
            {"tools": [{"feature": cut}], "bodies": [k.fref((505, 265, 20), of=d)]},
        )
        k.add("delete_body", "Drop One Half", {"bodies": [k.fref((555, 295, 20))]},
              option="delete")  # fmt: skip
        k.expect("Drop One Half", inside=[(515, 280, 10)], outside=[(545, 280, 10)])
        k.add("corner_ears", "Print Ears", {"face": [k.fref((515, 280, 0))]},
              ear_diameter=mm(10), ear_thickness=mm(0.4))  # fmt: skip
        k.expect("Print Ears", inside=[(497, 257, 0.2), (533, 303, 0.2)],
                 outside=[(497, 257, 0.6), (494, 254, 0.2)])  # fmt: skip
        e = k.box("Mould Block", 580, 260, 640, 320, 40)
        part = k.add(
            "primitive",
            "Mould Part",
            {"frame": self.frame("Part Frame", 610, 290, 20)},
            kind="sphere",
            operation="boss",
            diameter=mm(24),
            centred=True,
            merge=False,
        )
        k.add("mould_cavity", "Mould Cavity",
              {"main": k.fref((585, 265, 40), of=e), "part": k.fref((610, 290, 32), of=part)},
              uniform=True, factor=num(1.02), about="centroid", keep_part=False)  # fmt: skip
        k.expect("Mould Cavity", inside=[(585, 265, 20), (610 + 12.4, 290, 20)],
                 outside=[(610, 290, 20), (610 + 12.1, 290, 20)])  # fmt: skip
        f = k.box("Tray", 660, 260, 720, 300, 6)
        peg = k.add("primitive", "Peg", {"frame": self.frame("Peg Frame", 690, 280, 3)},
                    kind="cylinder", operation="boss", diameter=mm(12), height=mm(12),
                    merge=False)  # fmt: skip
        k.add("indent", "Peg Seat",
              {"bodies": [k.fref((665, 265, 6), of=f), k.fref((690, 280, 15), of=peg)]},
              indent_mode="cut", indent_clearance=mm(0.3))  # fmt: skip
        k.expect("Peg Seat", inside=[(690, 280, 4), (690 + 6.5, 280, 4), (690, 280, 14)],
                 outside=[(690 + 6.15, 280, 4)])  # fmt: skip
        k.add("base_pad", "Print Pad", {"face": [k.fref((665, 265, 0))]},
              pad_thickness=mm(0.3), pad_margin=mm(3), air_gap=mm(0.2))  # fmt: skip
        k.expect("Print Pad", inside=[(690, 280, 1), (690, 280, -0.35), (658, 258, -0.35)],
                 outside=[(690, 280, -0.1), (655, 255, -0.35), (690, 280, -0.6)])  # fmt: skip

    # Stage E: joints between plates -------------------------------------------------

    def on_top(self, name: str, base: str, x0: float, y0: float, x1: float, y1: float,
               z: float, h: float) -> str:  # fmt: skip
        """A block standing on the top face (at height ``z``) of ``base``, its own body."""
        top = self.fref(((x0 + x1) / 2, (y0 + y1) / 2, z), of=base)
        s = self.sketch(f"{name} Sketch", top,
                        lambda sk, at: sk.polygon(rect(at, x0, y0, z, x1, y1, z)))  # fmt: skip
        return self.add(
            "extrude",
            name,
            {"sketch": {"feature": s}},
            operation="boss",
            end_condition="blind",
            depth=mm(h),
            reverse=False,
            merge=False,
        )

    def joints(self) -> None:
        k = self
        p1 = k.box("Box Floor", 0, 340, 60, 380, 3)
        p2 = k.box("Box Wall", 0, 340, 60, 343, 40)
        k.add("finger_joint", "Box Fingers",
              {"bodies": [k.fref((30, 370, 3), of=p1), k.fref((30, 343, 25), of=p2)]},
              finger_count=num(5), clearance=mm(0.1))  # fmt: skip
        k.expect("Box Fingers", inside=[(30, 370, 1.5), (30, 341.5, 20)])
        q1 = k.box("Cross Plate One", 80, 358, 140, 361, 30)
        q2 = k.box("Cross Plate Two", 108, 340, 111, 380, 30)
        k.add("half_lap", "Cross Lap",
              {"bodies": [k.fref((90, 358, 15), of=q1), k.fref((108, 345, 15), of=q2)]},
              depth_percent=num(50), clearance=mm(0.2))  # fmt: skip
        k.expect("Cross Lap", inside=[(90, 359.5, 15), (109.5, 345, 15), (109.5, 359.5, 7),
                                      (109.5, 359.5, 23)])  # fmt: skip
        r1 = k.box("Rail", 160, 340, 220, 380, 10)
        r2 = k.on_top("Post", r1, 180, 350, 200, 370, 10, 30)
        k.add("joint_helper", "Post Mortise",
              {"bodies": [k.fref((165, 345, 10), of=r1), k.fref((190, 360, 40), of=r2)]},
              joint="mortise", depth=mm(5), shoulder=mm(3), joint_clearance=mm(0.2))  # fmt: skip
        k.expect("Post Mortise", inside=[(190, 360, 7), (190, 360, 30), (165, 345, 5)])
        s1 = k.box("Hard Half", 240, 340, 280, 380, 10)
        k.on_top("Soft Half", s1, 240, 340, 280, 380, 10, 10)
        k.add("interlock", "Material Teeth", {"face": [k.fref((260, 360, 10), of=s1)]},
              tooth_size=mm(5), tooth_depth=mm(2))  # fmt: skip
        k.expect("Material Teeth", inside=[(260, 360, 5), (260, 360, 15)],
                 some_outside=[(240.5 + i / 2, 360, 10.5) for i in range(79)])  # fmt: skip
        k.box("Hinge Leaf One", 300, 340, 330, 380, 4)
        k.box("Hinge Leaf Two", 330, 340, 360, 380, 4)
        k.add("hinge", "Leaf Hinge", {"edge": [k.eref((330, 360, 4))]},
              knuckles=num(3), knuckle_diameter=mm(8), clearance=mm(0.3), form="pin",
              pin_diameter=mm(3))  # fmt: skip
        k.expect("Leaf Hinge", inside=[(315, 360, 2), (345, 360, 2)])
        spot = self.frame("Lock Frame", 400, 360, 0)
        plug = k.add(
            "primitive",
            "Lock Plug",
            {"frame": spot},
            kind="cylinder",
            operation="boss",
            diameter=mm(20),
            height=mm(20),
            merge=False,
        )
        k.add("primitive", "Lock Socket", {"frame": spot}, kind="tube", operation="boss",
              diameter=mm(32), inner=mm(20.6), height=mm(20), merge=False)  # fmt: skip
        k.add("twist_lock", "Bayonet", {"face": k.fref((410, 360, 10), of=plug)},
              lug_count=num(3), lug_width=mm(4), lug_height=mm(3), lug_depth=mm(2),
              lock_depth=mm(8), twist=deg(30), lock_clearance=mm(0.3))  # fmt: skip
        k.expect("Bayonet", inside=[(400, 360, 10), (400 + 13, 360, 10)],
                 outside=[(400 + 10.15, 360, 2)])  # fmt: skip
        drum = k.add("primitive", "Stud Drum", {"frame": self.frame("Drum Frame", 460, 360, 0)},
                     kind="cylinder", operation="boss", diameter=mm(40), height=mm(30),
                     merge=False)  # fmt: skip
        seed = k.add("primitive", "Stud Seed", {}, kind="cylinder", operation="boss",
                     diameter=mm(3), height=mm(1.5), merge=False)  # fmt: skip
        k.add(
            "face_seats",
            "Drum Studs",
            {"on_face": [k.fref((480, 360, 15), of=drum)], "seed": [k.fref((0, 0, 1.5), of=seed)]},
            count_u=num(8),
            count_v=num(3),
            sink=mm(0.3),
            operation="boss",
        )
        rows = [(460 + 20.6 * math.cos(a / 40), 360 + 20.6 * math.sin(a / 40), h)
                for a in range(252) for h in range(1, 30)]  # fmt: skip
        k.expect("Drum Studs", inside=[(460, 360, 15)], outside=[(460 + 23, 360, 15)],
                 some_inside=rows)  # fmt: skip

    # Stage F: every kind of pattern on one plate -------------------------------------

    def patterns(self) -> None:
        k = self
        plate = k.box("Pattern Plate", 0, 400, 120, 470, 6)
        top = lambda: k.fref((60, 468, 6), of=plate)  # noqa: E731

        def stud(name: str, x: float, y: float, d: float = 6.0) -> str:
            s = k.sketch(f"{name} Sketch", top(), lambda sk, at: sk.circle(at(x, y, 6), d))
            return k.add(
                "extrude",
                name,
                {"sketch": {"feature": s}},
                operation="boss",
                end_condition="blind",
                depth=mm(4),
                reverse=False,
            )

        seed = stud("Table Seed", 10, 410)
        k.add("table_pattern", "Table Studs", {"features": [{"feature": seed}]},
              data={"rows": [[30, 410], [50, 414], [70, 410, False], [90, 414]]})  # fmt: skip
        k.expect("Table Studs", inside=[(10, 410, 8), (30, 410, 8), (50, 414, 8), (90, 414, 8)],
                 outside=[(70, 410, 8), (30, 410, 11)])  # fmt: skip
        seed = stud("Sketch Seed", 10, 426)
        psk, _ids = k.points("Stud Spots", top(), [(30, 428, 6), (50, 424, 6), (70, 428, 6)])
        k.add(
            "sketch_pattern",
            "Sketch Studs",
            {"sketch": {"feature": psk}, "features": [{"feature": seed}]},
        )
        k.expect("Sketch Studs", inside=[(30, 428, 8), (50, 424, 8), (70, 428, 8)],
                 outside=[(90, 428, 8)])  # fmt: skip
        s = k.sketch("Drill Sketch", top(), lambda sk, at: sk.circle(at(110, 408, 6), 3.4))
        drill = k.add("extrude", "Drill Seed", {"sketch": {"feature": s}}, operation="cut",
                      end_condition="through_all", depth=mm(1),
                      reverse=k.reverse_for(top(), (0, 0, -1)))  # fmt: skip
        k.expect("Drill Seed", inside=[(110 + 2, 408, 3)], outside=[(110, 408, 3)])
        path = k.sketch("Drill Row Path", top(),
                        lambda sk, at: sk.line(at(110, 408, 6), at(110, 462, 6)))  # fmt: skip
        k.add("curve_array", "Drill Row", {"path": {"feature": path},
                                           "features": [{"feature": drill}]},
              mode="count", count=num(4))  # fmt: skip
        k.expect("Drill Row", inside=[(110, 435, 3)],
                 outside=[(110, 426, 3), (110, 444, 3), (110, 462, 3)])  # fmt: skip
        s = k.sketch("Counterbore Sketch", top(), lambda sk, at: sk.circle(at(110, 408, 6), 7))
        cbore = k.add("extrude", "Counterbore Seed", {"sketch": {"feature": s}}, operation="cut",
                      end_condition="blind", depth=mm(1.5),
                      reverse=k.reverse_for(top(), (0, 0, -1)))  # fmt: skip
        rims = [
            k.eref((110 + 1.7, 426, 6)),
            k.eref((110 + 1.7, 444, 6)),
            k.eref((110 + 1.7, 462, 6)),
        ]
        k.add(
            "point_pattern",
            "Counterbores At Holes",
            {"targets": rims, "features": [{"feature": cbore}]},
        )
        k.expect("Counterbores At Holes",
                 inside=[(110 + 3, 426, 4), (110 + 4, 444, 5.5)],
                 outside=[(113, 408, 5.5), (113, 426, 5.5), (113, 462, 5.5)])  # fmt: skip
        seed = stud("Chain Seed", 12, 444, 5.0)
        mid = k.offset_plane("Plate Middle Plane", RIGHT, 50, (1, 0, 0))
        k.add("pattern_chain", "Chain Of Studs",
              {"features": [{"feature": seed}], "direction": {"feature": RIGHT},
               "plane": {"feature": mid}},
              steps="linear, mirror", spacing=mm(10), instances=num(3))  # fmt: skip
        k.expect("Chain Of Studs", inside=[(12, 444, 8), (22, 444, 8), (32, 444, 8), (88, 444, 8),
                                           (78, 444, 8), (68, 444, 8)],
                 outside=[(42, 444, 8), (58, 444, 8)])  # fmt: skip
        seed = stud("Grid Seed", 12, 458, 4.0)
        k.add("linear_pattern", "Grid Of Studs",
              {"direction1": {"feature": RIGHT}, "direction2": {"feature": TOP},
               "features": [{"feature": seed}]},
              spacing1=mm(9), count1=num(4), reverse1=False, second_direction=True,
              spacing2=mm(7), count2=num(2), reverse2=False)  # fmt: skip
        k.expect("Grid Of Studs", inside=[(12, 458, 8), (39, 458, 8), (39, 465, 8)],
                 outside=[(48, 458, 8), (12, 472, 8)])  # fmt: skip

    # Stage G: imported bodies and direct editing --------------------------------------

    def imports(self) -> None:
        from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
        from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
        from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
        from OCP.TopAbs import TopAbs_EDGE
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopoDS import TopoDS

        from fdcad.core.features.import_mesh import new_mesh_import
        from fdcad.core.features.import_step import new_step_import
        from fdcad.samples.step_source import colored_step_bytes

        k = self
        block = BRepPrimAPI_MakeBox(gp_Pnt(300, 400, 0), 60.0, 40.0, 30.0).Shape()
        hole = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(330, 420, -1), gp_Dir(0, 0, 1)), 5.0,
                                        32.0).Shape()  # fmt: skip
        shape = BRepAlgoAPI_Cut(block, hole).Shape()
        rounds = BRepFilletAPI_MakeFillet(shape)
        explorer = TopExp_Explorer(shape, TopAbs_EDGE)
        while explorer.More():
            edge = TopoDS.Edge(explorer.Current())
            mid = k.b.edge_mid(edge)
            if abs(mid[0] - 300) < 1e-6 and abs(mid[1] - 400) < 1e-6:  # one upright edge
                rounds.Add(4.0, edge)
                break
            explorer.Next()
        rounds.Build()
        data = colored_step_bytes(rounds.Shape(), "#8C949C")
        bid, blockdata, feature = new_step_import(k.b.doc, "bracket.step", data)
        k.b.doc.embedded[bid] = blockdata
        k.b.doc.features.append(feature)
        k.b.rebuild(feature.id)
        k.used["import_step"] = 1
        self.step = step = feature.id
        on = lambda p: k.fref(p, of=step)  # noqa: E731
        k.add(
            "face_relation",
            "Top And Bottom Parallel",
            {"faces": [on((345, 430, 30)), on((345, 430, 0))]},
            relation="parallel",
        )
        k.add("move_face", "Raise The Top", {"faces": [on((345, 430, 30))]},
              mode="offset", distance=mm(2), reverse=False)  # fmt: skip
        k.expect("Raise The Top", inside=[(345, 430, 31.5)], outside=[(345, 430, 32.5)])
        k.add("push_pull", "Pull The End", {"faces": [k.fref((360, 420, 15))]},
              distance=mm(3))  # fmt: skip
        k.expect("Pull The End", inside=[(362, 420, 15)], outside=[(363.5, 420, 15)])
        k.add("delete_face", "Fill The Hole", {"faces": [k.fref((335, 420, 15))]},
              option="patch")  # fmt: skip
        k.expect("Fill The Hole", inside=[(330, 420, 15)])
        # The one round of the imported block. With no pick it takes every round of the part.
        k.add("remove_fillets", "Square The Corner", {"faces": [k.fref((301.1716, 401.1716, 15))]})
        k.expect("Square The Corner", inside=[(300.3, 400.3, 15)])
        level = k.offset_plane("Level Plane", FRONT, 36, (0, 0, 1))
        k.add("replace_face", "Top To Level", {"faces": [k.fref((345, 430, 32))],
                                               "target": {"feature": level}})  # fmt: skip
        k.expect("Top To Level", inside=[(345, 430, 35.5)], outside=[(345, 430, 36.5)])
        # No Heal Edges here (D1103): it heals every body, and a deformed bar of this
        # part would come out of it not valid, so it stays as it was, with a warning
        # the sample should not open with. test_heal_edges.py keeps that case (D1066).
        cross = k.offset_plane("Marking Plane", TOP, 420, (0, 1, 0))
        k.add("split_line", "Top Mark", {"faces": [k.fref((345, 430, 36))],
                                         "plane": {"feature": cross}},
              method="intersection")  # fmt: skip
        k.add(
            "merge_faces",
            "Top Joined Again",
            {"faces": [k.fref((345, 410, 36)), k.fref((345, 430, 36))]},
        )
        k.expect("Top Joined Again", inside=[(345, 430, 35.5), (330, 420, 15), (362, 420, 15)])
        import numpy as np

        from fdcad.core.io.mesh_import import Mesh, stl_bytes

        x0, y0, sx, sy, sz = 380.0, 400.0, 40.0, 40.0, 20.0
        corners = np.array(
            [[x0, y0, 0], [x0 + sx, y0, 0], [x0 + sx, y0 + sy, 0], [x0, y0 + sy, 0],
             [x0, y0, sz], [x0 + sx, y0, sz], [x0 + sx, y0 + sy, sz], [x0, y0 + sy, sz]],
            dtype=np.float32,
        )  # fmt: skip
        tris = np.array(
            [[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4],
             [1, 2, 6], [1, 6, 5], [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]],
            dtype=np.int32,
        )  # fmt: skip
        bid, blockdata, feature = new_mesh_import(
            k.b.doc, "scan.stl", stl_bytes(Mesh(corners, tris))
        )
        feature.params["convert"] = True
        k.b.doc.embedded[bid] = blockdata
        k.b.doc.features.append(feature)
        k.b.rebuild(feature.id)
        k.used["import_mesh"] = 1
        k.expect("Scan", inside=[(400, 420, 10)], outside=[(400, 420, 21)])

    # Stage H: tools for printing and casting -----------------------------------------

    def print_tools(self) -> None:
        k = self
        bar = k.box("Long Bar", 0, 500, 200, 520, 15)
        cut = k.offset_plane("Bar Cut Plane", RIGHT, 100, (1, 0, 0))
        k.add("split_for_print", "Bar In Two",
              {"planes": [{"feature": cut}], "bodies": [k.fref((50, 510, 15), of=bar)]},
              mode="planes", connector="pins", pin_diameter=mm(4), pin_length=mm(8),
              clearance=mm(0.2))  # fmt: skip
        k.expect("Bar In Two", inside=[(50, 510, 7), (150, 510, 7)])
        slab = k.box("Light Block", 220, 500, 260, 540, 10)
        k.add("lattice_fill", "Honeycomb Fill", {"bodies": [k.fref((240, 520, 10), of=slab)]},
              lattice="honeycomb", cell=mm(8), wall=mm(1), skin=mm(1))  # fmt: skip
        k.expect("Honeycomb Fill", inside=[(240, 520, 0.5), (240, 520, 9.5), (220.5, 520, 5)],
                 some_outside=[(222 + i / 2, 520, 5) for i in range(73)])  # fmt: skip
        k.box("Cast Part One", 300, 500, 312, 512, 10)
        k.box("Cast Part Two", 330, 500, 342, 512, 10)
        feeds = [k.add("ref_point", f"Feed Point {n}", {}, method="values", x=mm(x), y=mm(506),
                       z=mm(10)) for n, x in ((1, 306), (2, 336))]  # fmt: skip
        cup = k.add("ref_point", "Cup Point", {}, method="values", x=mm(321), y=mm(506),
                    z=mm(60))  # fmt: skip
        k.add("sprue_tree", "Casting Sprue",
              {"feed_points": [{"feature": f} for f in feeds], "cup": [{"feature": cup}]},
              layout="tree", cup_diameter=mm(12), cup_height=mm(8), sprue_diameter=mm(5),
              gate_diameter=mm(3))  # fmt: skip
        k.expect("Casting Sprue", inside=[(306, 506, 5), (336, 506, 5)],
                 some_inside=[(321, 506, h / 2) for h in range(11, 140)])  # fmt: skip
        k.box("Section Sample", 760, 0, 800, 40, 20)
        k.add(
            "section_cut",
            "Kept Section",
            {},
            data={"zones": [[{"origin": [780.0, 0.0, 0.0], "normal": [1.0, 0.0, 0.0]}]]},
        )
        k.expect("Kept Section", inside=[(770, 20, 10)], outside=[(790, 20, 10)])
        # A few more ways to make reference geometry, and a measurement between faces.
        k.add("ref_axis", "Diagonal Axis",
              {"first": k.vref((760, 0, 20)), "second": k.vref((780, 40, 20))},
              method="two_points")  # fmt: skip
        k.add("ref_plane", "Three Corner Plane",
              {"first": k.vref((760, 0, 0)), "second": k.vref((780, 40, 0)),
               "third": k.vref((760, 40, 20))}, method="three_points")  # fmt: skip
        k.add("ref_plane", "Between Ends",
              {"first": k.fref((760, 20, 10)), "second": k.fref((780, 20, 10))},
              method="mid_plane")  # fmt: skip
        k.add("ref_point", "Top Middle", {"first": k.fref((770, 20, 20))}, method="face_centre")
        k.add(
            "measurement", "Sample Width", {"items": [k.fref((760, 20, 10)), k.fref((780, 20, 10))]}
        )

    STAGES = ("housing", "bearings", "feet", "walls", "references", "cover", "cover_details",
              "filler", "shaft", "spring", "knob", "deforms", "primitives", "body_tools",
              "joints", "patterns", "imports", "print_tools")  # fmt: skip

    def build(self, stages: list[str]) -> None:
        for stage in stages or self.STAGES:
            if not self.b.quiet:
                print(f"--- {stage}", flush=True)
            getattr(self, stage)()
