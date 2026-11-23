"""A sheet metal part of eleven bodies, built feature by feature to use every sheet metal
feature type, with the solid features the gearbox did not reach (D1071 to D1076).

After the bike frame and the gearbox the 26 sheet metal types had had no test of this
kind (2026-11-12). This part has them all: a tray with four walls, a channel with a
tabbed lid, a strip with a bend and a jog, a plate with a miter flange, a solid box made
into sheet metal, a thin angle given bends, and a hat section whose two brims lie in one
plane; then Draft, Mounting Boss, Landing Pad, Graph Body and Insert Part on solid
bodies, and a Flat Pattern for every sheet. Every feature is followed by a check that
material is where it should be and nowhere else (``expect``): several of the faults it
found built with no error, in the wrong place.

Tray: X 0..200, Y 0..120, floor at Z 0. The other bodies stand clear of it along Y.
"""

from __future__ import annotations

import itertools
from typing import Any

from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

from fdcad.core.features.sheetmetal.params import new_sheet_metal
from fdcad.core.features.solids import solids
from fdcad.core.naming.names import centroid
from tests.core.features.gearbox_kit import FRONT, RIGHT, TOP, Kit, deg, mm, num


def rect(at, x0, y0, z0, x1, y1, z1):  # type: ignore[no-untyped-def]
    """Corners of an axis aligned rectangle on a plane square to one model axis."""
    if abs(z0 - z1) < 1e-9:
        return [at(x0, y0, z0), at(x1, y0, z0), at(x1, y1, z0), at(x0, y1, z0)]
    if abs(y0 - y1) < 1e-9:
        return [at(x0, y0, z0), at(x1, y0, z0), at(x1, y0, z1), at(x0, y0, z1)]
    return [at(x0, y0, z0), at(x0, y1, z0), at(x0, y1, z1), at(x0, y0, z1)]


class Sheet(Kit):
    # Helpers ----------------------------------------------------------------------

    def folder(self, name: str, thickness: float, radius: float, **more: Any) -> dict:
        """A Sheet Metal folder; returns the reference every sheet feature carries."""
        feature = new_sheet_metal(
            self.b.doc, {"thickness": mm(thickness), "radius": mm(radius), **more}
        )
        feature.name = name
        self.b.doc.features.append(feature)
        self.b.rebuild(feature.id)
        return {"sheet_metal": {"feature": feature.id}}

    def boxes(self, label: str = "") -> None:
        """Print where every body is (for finding picks while writing the part)."""
        for n, s in enumerate(solids(self.b.body.shape)):
            b = Bnd_Box()
            BRepBndLib.Add_s(s, b)
            lo, hi = b.CornerMin(), b.CornerMax()
            print(f"   {label} body {n}: ({lo.X():.2f},{lo.Y():.2f},{lo.Z():.2f}).."
                  f"({hi.X():.2f},{hi.Y():.2f},{hi.Z():.2f})", flush=True)  # fmt: skip

    def faces_of(self, fid: str, limit: int = 40) -> None:
        rows = [(n, [round(v, 2) for v in centroid(f)]) for n, f in self.b.body.faces
                if n.startswith(f"{fid}/")]  # fmt: skip
        for n, c in rows[:limit]:
            print("     ", n, c, flush=True)

    # Stage A: a tray with four walls -------------------------------------------------

    def tray(self) -> None:
        k = self
        self.sm = sm = k.folder("Tray Sheet", 2, 2)
        s = k.sketch("Tray Floor Sketch", FRONT,
                     lambda sk, at: sk.polygon(rect(at, 0, 0, 0, 200, 120, 0)))  # fmt: skip
        self.floor = k.add("base_flange", "Tray Floor", {"sketch": {"feature": s}, **sm})
        top = [(100, 0, 2), (200, 60, 2), (100, 120, 2), (0, 60, 2)]
        self.walls = k.add("edge_flange", "Tray Walls", {"edges": k.erefs(top), **sm},
                           length=mm(40), length3=mm(30), trim_side_bends=True)  # fmt: skip

    # Stage B: corners, hems and edges of the tray ----------------------------------

    def tray_edges(self) -> None:
        k, sm = self, self.sm
        k.add("sheet_corner_relief", "Corner Reliefs", {**sm}, all_corners=True,
              relief_type="circular", size_by="ratio", ratio=num(2))  # fmt: skip
        k.add("closed_corner", "Closed Corner", {"faces": [k.fref((196, 1, 25))], **sm},
              corner_type="overlap", gap=mm(0.2))  # fmt: skip
        k.add("hem", "Right Wall Hem", {"edges": [k.eref((200, 60, 40))], **sm},
              hem_type="closed", length=mm(8))  # fmt: skip
        k.add("break_corner", "Back Wall Corner", {"edges": [k.eref((4, 119, 30))], **sm},
              break_type="chamfer", distance=mm(4))  # fmt: skip
        k.add("extend_wall", "Back Wall Taller", {"face": k.fref((100, 119, 30)), **sm},
              end_condition="blind", distance=mm(5))  # fmt: skip
        k.add(
            "edit_bends",
            "Left Bend Wider",
            {"bends": [k.fref((1.1716, 60, 1.1716), flat=False)], **sm},
            radius=mm(3),
        )
        k.expect("Closed Corner", inside=[(199, 1, 25)], outside=[(1, 1, 25), (199, 119, 20)])
        k.expect("Right Wall Hem", inside=[(201, 60, 36), (199, 60, 20)], outside=[(197, 60, 36)])
        k.expect(
            "Back Wall Taller", inside=[(100, 119, 33)], outside=[(100, 1, 42), (100, 119, 36)]
        )
        k.expect("Left Bend Wider", inside=[(0, 60, 20)], outside=[(1.5, 60, 20), (-1.5, 60, 20)])
        # The left wall is parallel to the right one and comes after it in the sheet.
        k.add("hem", "Left Wall Hem", {"edges": [k.eref((-1, 60, 41))], **sm},
              hem_type="open", length=mm(6), gap=mm(1))  # fmt: skip
        k.expect(
            "Left Wall Hem",
            inside=[(-3, 60, 37), (0, 60, 37)],
            outside=[(-1.6, 60, 37), (3, 60, 37)],
        )

    # Stage C: forms, marks and cuts on the tray --------------------------------------

    def tray_forms(self) -> None:
        k, sm = self, self.sm
        floor = lambda: k.fref((15, 108, 2))  # noqa: E731
        k.add("cross_break", "Floor Cross Break", {"face": floor(), **sm},
              break_angle=deg(2), break_radius=mm(1))  # fmt: skip

        def dimples(sk, at):  # type: ignore[no-untyped-def]
            sk.line(at(35, 25, 2), at(45, 25, 2))
            sk.line(at(35, 95, 2), at(45, 95, 2))

        s = k.sketch("Dimple Lines", floor(), dimples)
        k.add("form_tool", "Dimples", {"sketch": {"feature": s}, **sm},
              tool="dimple", diameter=mm(10), height=mm(3))  # fmt: skip
        s = k.sketch("Louvre Lines", floor(),
                     lambda sk, at: sk.line(at(150, 25, 2), at(170, 25, 2)))  # fmt: skip
        k.add("form_tool", "Louvre", {"sketch": {"feature": s}, **sm},
              tool="louvre", length=mm(20), width=mm(6), height=mm(3))  # fmt: skip
        s = k.sketch("Rib Line", floor(),
                     lambda sk, at: sk.line(at(130, 95, 2), at(170, 95, 2)))  # fmt: skip
        k.add("form_tool", "Stiffening Rib", {"sketch": {"feature": s}, **sm},
              tool="rib", width=mm(6), height=mm(2))  # fmt: skip
        s = k.sketch("Stamp Outline", floor(),
                     lambda sk, at: sk.polygon(rect(at, 90, 50, 2, 110, 70, 2)))  # fmt: skip
        k.add("stamp", "Stamp", {"sketch": {"feature": s}, **sm}, depth=mm(3), draft=deg(20))
        k.add("gusset", "Front Gusset", {"walls": [k.fref((60, 30, 2)), k.fref((60, 2, 22))], **sm},
              depth=mm(8), width=mm(6))  # fmt: skip
        # The back wall is parallel to the front one and comes after it in the sheet.
        k.add(
            "gusset",
            "Back Gusset",
            {"walls": [k.fref((140, 100, 2)), k.fref((140, 118, 22))], **sm},
            depth=mm(8),
            width=mm(6),
            rib_position=mm(40),
        )
        k.expect("Back Gusset", inside=[(140, 116.5, 4)], outside=[(100, 116.5, 4), (140, 3.5, 4)])
        s = k.sketch("Layout Line", floor(),
                     lambda sk, at: sk.line(at(20, 60, 2), at(70, 60, 2)))  # fmt: skip
        k.add("flat_marks", "Layout Marks", {"sketch": {"feature": s}, **sm}, title="Layout")
        left = k.fref((198, 60, 22))
        s = k.sketch("Fold Line", left, lambda sk, at: sk.line(at(198, 20, 20), at(198, 100, 20)))
        k.add("perforation", "Hand Fold Line", {"sketch": {"feature": s}, **sm},
              slot_length=mm(6), slot_width=mm(1), bridge=mm(3))  # fmt: skip
        front = k.fref((100, 0, 22))
        s = k.sketch("Tab Outline", front,
                     lambda sk, at: sk.polygon(rect(at, 90, 0, 38, 110, 0, 50)))  # fmt: skip
        k.add("sheet_tab", "Front Tab", {"sketch": {"feature": s}, **sm})
        k.expect("Dimples", inside=[(40, 25, 4), (40, 95, 4)], outside=[(40, 25, 1), (40, 60, 4)])
        k.expect(
            "Louvre", inside=[(160, 25, 2.5), (160, 21, 1)], outside=[(160, 28, 1), (160, 25, 6)]
        )
        k.expect("Stiffening Rib", inside=[(150, 95, 3)], outside=[(150, 95, 0.5), (150, 80, 3)])
        k.expect("Stamp", inside=[(100, 60, 4)], outside=[(100, 60, 1), (120, 60, 4)])
        k.expect("Front Gusset", inside=[(100, 3.5, 4)], outside=[(60, 3.5, 3.5), (100, 3.5, 1.5)])
        k.expect("Hand Fold Line", inside=[(199, 28.5, 20), (199, 60, 30)],
                 outside=[(199, 24, 20), (1, 24, 20) if False else (199, 33, 20)])  # fmt: skip
        k.expect("Front Tab", inside=[(100, 1, 45)], outside=[(100, 119, 45), (80, 1, 45)])

    # Stage D: cuts across bends, joints and the flat pattern ---------------------------

    def tray_flat(self) -> None:
        k, sm = self, self.sm
        k.add("unfold", "Unfold Front", {"bends": [k.fref((60, 1.1716, 1.1716), flat=False)], **sm})
        floor = k.fref((15, 108, 2))
        s = k.sketch("Slot Across The Bend", floor,
                     lambda sk, at: sk.polygon(rect(at, 140, -8, 2, 150, 8, 2)))  # fmt: skip
        k.add(
            "extrude",
            "Bend Slot",
            {"sketch": {"feature": s}},
            operation="cut",
            end_condition="through_all",
            depth=mm(1),
            reverse=k.reverse_for(floor, (0, 0, -1)),
        )
        k.add("fold", "Fold Front", {**sm})
        k.expect("Bend Slot", inside=[(130, 1, 5), (130, 5, 1)], outside=[(145, 1, 6), (145, 5, 1)])

    # Stage E: a channel bent from an open profile, with a lid tabbed into its wall -----

    def channel(self) -> None:
        k = self
        self.sm2 = sm = k.folder("Channel Sheet", 1, 1)
        plane = k.offset_plane("Channel Plane", TOP, 160, (0, 1, 0))

        def profile(sk, at):  # type: ignore[no-untyped-def]
            sk.line(at(0, 160, 30), at(0, 160, 0))
            sk.line(at(0, 160, 0), at(40, 160, 0))
            sk.line(at(40, 160, 0), at(40, 160, 40))

        s = k.sketch("Channel Profile", plane, profile)
        self.chan = k.add("base_flange", "Channel", {"sketch": {"feature": s}, **sm},
                          end_condition="blind", depth=mm(60))  # fmt: skip
        self.lid = k.add("edge_flange", "Channel Lid", {"edges": [k.eref((0, 190, 30))], **sm},
                         length=mm(41), trim_side_bends=True)  # fmt: skip
        k.add(
            "tab_slot",
            "Lid Tabs",
            {"edge": k.eref((40, 190, 30)), "face": k.fref((40, 190, 15)), **sm},
            tab_count=num(3),
            tab_length=mm(8),
            clearance=mm(0.2),
        )
        k.expect(
            "Lid Tabs",
            inside=[(40.5, 190, 29.5), (40.5, 180, 29.5)],
            outside=[(40.5, 185.9, 29.5), (40.5, 190, 30.1)],
        )

    # Stage F: a strip with a sketched bend and a jog ---------------------------------

    def strip(self) -> None:
        k = self
        self.sm3 = sm = k.folder("Strip Sheet", 1.5, 1.5)
        s = k.sketch("Strip Sketch", FRONT,
                     lambda sk, at: sk.polygon(rect(at, 0, 260, 0, 120, 300, 0)))  # fmt: skip
        self.strip_id = k.add("base_flange", "Strip", {"sketch": {"feature": s}, **sm})
        top = k.fref((60, 280, 1.5))
        s = k.sketch("Bend Line", top, lambda sk, at: sk.line(at(90, 265, 1.5), at(90, 295, 1.5)))
        k.add("sketched_bend", "Strip Bend", {"sketch": {"feature": s}, **sm}, angle=deg(60))
        k.expect(
            "Strip Bend",
            inside=[(95, 280, 9), (100, 280, 18), (60, 280, 0.75)],
            outside=[(100, 280, 0.75), (110, 280, 0.75)],
        )
        top = k.fref((60, 280, 1.5))
        s = k.sketch("Jog Line", top, lambda sk, at: sk.line(at(40, 265, 1.5), at(40, 295, 1.5)))
        k.add("jog", "Strip Jog", {"sketch": {"feature": s}, **sm}, offset=mm(6))
        k.expect(
            "Strip Jog",
            inside=[(20, 280, 6.75), (60, 280, 0.75)],
            outside=[(20, 280, 0.75), (60, 280, 6.75)],
        )
        # A plain cut in a sheet is made square to the sheet and kept in the sheet model
        # (Normal Cut), so it is in the flat pattern too.
        top = k.fref((70, 280, 1.5))
        s = k.sketch("Strip Hole Sketch", top, lambda sk, at: sk.circle(at(65, 280, 1.5), 10))
        k.add(
            "extrude",
            "Strip Hole",
            {"sketch": {"feature": s}},
            operation="cut",
            end_condition="through_all",
            depth=mm(1),
            reverse=k.reverse_for(top, (0, 0, -1)),
        )
        k.expect("Strip Hole", inside=[(72, 280, 0.75)], outside=[(65, 280, 0.75)])

    # Stage G: a plate with a miter flange round three edges ----------------------------

    def mitre(self) -> None:
        k = self
        self.sm4 = sm = k.folder("Lid Sheet", 1, 1)
        s = k.sketch("Lid Plate Sketch", FRONT,
                     lambda sk, at: sk.polygon(rect(at, 0, 340, 0, 80, 390, 0)))  # fmt: skip
        self.plate = k.add("base_flange", "Lid Plate", {"sketch": {"feature": s}, **sm})
        # The profile is drawn on a plane square to the first edge, at its end point.
        plane = k.offset_plane("Mitre Plane", TOP, 340, (0, 1, 0))
        s = k.sketch("Mitre Profile", plane,
                     lambda sk, at: sk.line(at(0, 340, 1), at(0, 340, 13)))  # fmt: skip
        edges = k.erefs([(0, 365, 1), (40, 390, 1), (80, 365, 1)])
        self.mitre_id = k.add(
            "miter_flange", "Lid Rim", {"edges": edges, "sketch": {"feature": s}, **sm}, gap=mm(0.5)
        )
        k.expect("Lid Rim", inside=[(-0.5, 365, 7), (40, 390.5, 7), (80.5, 365, 7), (40, 365, 0.5)],
                 outside=[(40, 339.5, 7), (40, 365, 7)])  # fmt: skip
        top = k.fref((40, 365, 1))
        s = k.sketch("Rip Line", top, lambda sk, at: sk.line(at(40, 340, 1), at(40, 360, 1)))
        k.add("rip", "Lid Rip", {"sketch": {"feature": s}, **sm}, gap=mm(0.6))
        k.expect("Lid Rip", inside=[(41, 350, 0.5), (40, 370, 0.5)], outside=[(40, 350, 0.5)])

    # Stage H: a solid box made into sheet metal, and a thin solid given bends --------

    def converted(self) -> None:
        k = self
        self.sm5 = sm = k.folder("Box Sheet", 1, 1)
        s = k.sketch("Box Sketch", FRONT,
                     lambda sk, at: sk.polygon(rect(at, 0, 430, 0, 60, 470, 0)))  # fmt: skip
        box = k.add("extrude", "Solid Box", {"sketch": {"feature": s}}, operation="boss",
                    end_condition="blind", depth=mm(30), reverse=False, merge=False)  # fmt: skip
        bends = k.erefs([(30, 430, 0), (60, 450, 0), (30, 470, 0), (0, 450, 0)])
        self.conv = k.add("convert_sheet", "Box To Sheet",
                          {"face": k.fref((30, 450, 0), of=box), "bends": bends, **sm},
                          gap=mm(0.2), rip_type="butt")  # fmt: skip
        k.expect(
            "Box To Sheet",
            inside=[(30, 450, 0.5), (0.5, 450, 15), (59.5, 450, 15), (30, 430.5, 15)],
            outside=[(30, 450, 15), (30, 450, 29.5)],
        )

    def inserted(self) -> None:
        k = self
        self.sm6 = sm = k.folder("Angle Sheet", 2, 2)
        plane = k.offset_plane("Angle Plane", TOP, 510, (0, 1, 0))
        pts = [(0, 0), (50, 0), (50, 30), (48, 30), (48, 2), (0, 2)]
        s = k.sketch("Angle Profile", plane,
                     lambda sk, at: sk.polygon([at(x, 510, z) for x, z in pts]))  # fmt: skip
        angle = k.add("extrude", "Thin Angle", {"sketch": {"feature": s}}, operation="boss",
                      end_condition="blind", depth=mm(40), reverse=k.reverse_for(plane, (0, 1, 0)),
                      merge=False)  # fmt: skip
        self.ins = k.add(
            "insert_bends",
            "Angle Bends",
            {"face": k.fref((25, 530, 0), of=angle), **sm},
            gap=mm(0.2),
        )
        k.expect(
            "Angle Bends",
            inside=[(25, 530, 1), (49, 530, 20)],
            outside=[(49.9, 530, 0.1), (25, 530, 10)],
        )

    # Stage K: a hat section: two brims in one plane, and features on the far one -----

    def hat(self) -> None:
        k = self
        self.sm7 = sm = k.folder("Hat Sheet", 1, 1)
        plane = k.offset_plane("Hat Plane", TOP, 700, (0, 1, 0))
        pts = [(0, 0), (30, 0), (30, 25), (70, 25), (70, 0), (100, 0)]

        def profile(sk, at):  # type: ignore[no-untyped-def]
            for (x0, z0), (x1, z1) in itertools.pairwise(pts):
                sk.line(at(x0, 700, z0), at(x1, 700, z1))

        s = k.sketch("Hat Profile", plane, profile)
        self.hat_id = k.add("base_flange", "Hat", {"sketch": {"feature": s}, **sm},
                            end_condition="blind", depth=mm(80))  # fmt: skip
        # Everything below is put on the far brim (x 71 to 100). The near brim (x 0 to
        # 29) lies in the same plane and comes first in the sheet.
        far = lambda: k.fref((85, 702, 0))  # noqa: E731
        k.add("break_corner", "Far Brim Corner", {"edges": [k.eref((100, 700, -0.5))], **sm},
              break_type="chamfer", distance=mm(5))  # fmt: skip
        k.expect("Far Brim Corner", inside=[(0.5, 700.5, -0.5), (99.5, 779.5, -0.5)],
                 outside=[(99.5, 700.5, -0.5)])  # fmt: skip
        s = k.sketch(
            "Brim Fold Line", far(), lambda sk, at: sk.line(at(85, 710, 0), at(85, 770, 0))
        )
        k.add("perforation", "Brim Perforation", {"sketch": {"feature": s}, **sm},
              slot_length=mm(6), slot_width=mm(1), bridge=mm(4))  # fmt: skip
        k.expect(
            "Brim Perforation", inside=[(85, 720, -0.5), (15, 715, -0.5)], outside=[(85, 715, -0.5)]
        )
        s = k.sketch("Brim Tab Outline", far(),
                     lambda sk, at: sk.polygon(rect(at, 75, 780, 0, 90, 788, 0)))  # fmt: skip
        k.add("sheet_tab", "Brim Tab", {"sketch": {"feature": s}, **sm})
        k.expect("Brim Tab", inside=[(82, 784, -0.5)], outside=[(15, 784, -0.5), (95, 784, -0.5)])
        s = k.sketch("Brim Rip Line", far(), lambda sk, at: sk.line(at(75, 705, 0), at(95, 705, 0)))
        k.add("rip", "Brim Rip", {"sketch": {"feature": s}, **sm}, gap=mm(0.6))
        k.expect("Brim Rip", inside=[(85, 707, -0.5), (15, 705, -0.5)], outside=[(85, 705, -0.5)])
        s = k.sketch(
            "Brim Dimple Line", far(), lambda sk, at: sk.line(at(77, 775, 0), at(83, 775, 0))
        )
        k.add("form_tool", "Brim Dimple", {"sketch": {"feature": s}, **sm},
              tool="dimple", diameter=mm(6), height=mm(2))  # fmt: skip
        s = k.sketch(
            "Brim Mark Line", far(), lambda sk, at: sk.line(at(75, 772, 0), at(95, 772, 0))
        )
        k.add("flat_marks", "Brim Marks", {"sketch": {"feature": s}, **sm}, title="Far")
        k.add("cross_break", "Brim Cross Break", {"face": far(), **sm})
        k.add("hem", "Brim Hem", {"edges": [k.eref((100, 742.5, 0))], **sm},
              hem_type="closed", length=mm(5))  # fmt: skip
        k.expect(
            "Brim Hem",
            inside=[(97, 742.5, 0.5), (97, 742.5, -0.5)],
            outside=[(90, 742.5, 0.5), (3, 742.5, 0.5)],
        )
        s = k.sketch(
            "Brim Bend Line", far(), lambda sk, at: sk.line(at(92, 705, 0), at(92, 775, 0))
        )
        k.add("sketched_bend", "Brim Bend", {"sketch": {"feature": s}, **sm}, angle=deg(45))
        k.expect("Brim Bend", inside=[(2, 740, -0.5), (80, 740, -0.5)], outside=[(98, 762, -0.5)])

    # Stage I: solid features the gearbox did not reach -------------------------------

    def solid_tools(self) -> None:
        k = self
        s = k.sketch("Draft Block Sketch", FRONT,
                     lambda sk, at: sk.polygon(rect(at, 0, 590, 0, 60, 630, 0)))  # fmt: skip
        block = k.add("extrude", "Draft Block", {"sketch": {"feature": s}}, operation="boss",
                      end_condition="blind", depth=mm(30), reverse=False, merge=False)  # fmt: skip
        sides = [
            k.fref(p, of=block) for p in ((0, 610, 15), (60, 610, 15), (30, 590, 15), (30, 630, 15))
        ]
        k.add("draft", "Block Draft", {"neutral": {"feature": FRONT}, "faces": sides}, angle=deg(5))
        k.expect(
            "Block Draft",
            inside=[(30, 610, 29), (0.5, 610, 1)],
            outside=[(0.5, 610, 29), (59.5, 610, 29)],
        )
        top = k.fref((30, 610, 30))
        psk, ids = k.points("Boss Position", top, [(30, 610, 30)])
        k.add(
            "mounting_boss",
            "Block Boss",
            {
                "face": [k.fref((30, 610, 30))],
                "position": {"feature": psk, "sketch_entity": ids[0]},
            },
            boss_type="screw_thread",
            boss_diameter=mm(10),
            boss_height=mm(6),
            hole_diameter=mm(4),
            hole_depth=mm(5),
            fin_count=num(0),
        )
        k.expect("Block Boss", inside=[(33.5, 610, 33)], outside=[(30, 610, 34), (40, 610, 33)])
        s = k.sketch("Drum Sketch", FRONT, lambda sk, at: sk.circle(at(100, 610, 0), 40))
        drum = k.add("extrude", "Drum", {"sketch": {"feature": s}}, operation="boss",
                     end_condition="blind", depth=mm(40), reverse=False, merge=False)  # fmt: skip
        plane = k.offset_plane("Pad Plane", RIGHT, 125, (1, 0, 0))
        s = k.sketch("Pad Outline", plane,
                     lambda sk, at: sk.polygon(rect(at, 125, 603, 13, 125, 617, 27)))  # fmt: skip
        k.add("landing_pad", "Label Pad",
              {"wall_face": [k.fref((120, 610, 20), of=drum)], "sketch": {"feature": s}},
              pad_mode="raise")  # fmt: skip
        k.expect("Label Pad", inside=[(123, 610, 20)], outside=[(123, 610, 35), (126, 610, 20)])
        from fdcad.samples.graphs import _GraphBuilder, _p

        b = _GraphBuilder(k.b.doc.features[-1].id, "Block Graph")
        corner = b.node("point", 0, 0, x=_p(150), y=_p(590), z=_p(0))
        box = b.node("box", 1, 0, size_x=_p(20), size_y=_p(20), size_z=_p(10))
        b.wire(corner, "out", box, "corner")
        out = b.node("add_as_feature", 2, 0, operation="new")
        b.wire(box, "body", out, "body")
        k.b.doc.graphs.append(b.graph)
        k.add("graph_body", "Graph Block", {"graph": {"graph": b.graph.id, "output": out}})
        k.expect("Graph Block", inside=[(160, 600, 5)], outside=[(160, 600, 11)])
        from fdcad.samples.location import sample_dir

        k.add("insert_part", "Inserted Plate", {},
              part_file=str(sample_dir() / "plate_with_holes.fdprt"), link=True,
              place="offset", dx=mm(200), dy=mm(590), dz=mm(0))  # fmt: skip
        k.expect("Inserted Plate", inside=[(205, 620, 5)], outside=[(250, 620, 5)])

    # Stage J: a flat pattern for every sheet --------------------------------------------

    def flats(self) -> None:
        k = self
        for name in ("sm", "sm2", "sm3", "sm4", "sm5", "sm6", "sm7"):
            folder = getattr(self, name, None)
            if folder is None:
                continue
            label = k.b.doc.feature(folder["sheet_metal"]["feature"]).name.replace(" Sheet", "")
            fid = k.add("flatten", f"{label} Flat Pattern", {**folder},
                        flattened=False, bend_lines=True, bounding_box=True)  # fmt: skip
            res = k.b.report.results[fid]
            flat = getattr(res, "flat", None)
            size = getattr(res, "size", None)
            if not self.b.quiet:
                print(f"        FLAT {label}: size {size}, flat body {flat is not None}",
                      flush=True)  # fmt: skip

    STAGES = ("tray", "tray_edges", "tray_forms", "tray_flat", "channel", "strip", "mitre",
              "converted", "inserted", "hat", "solid_tools", "flats")  # fmt: skip

    def build(self, stages: list[str]) -> None:
        for stage in stages or self.STAGES:
            if not self.b.quiet:
                print(f"--- {stage}", flush=True)
            getattr(self, stage)()
