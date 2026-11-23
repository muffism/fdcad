"""Picking and sketching helpers for building a large part feature by feature.

Everything is given in model coordinates, as a user points at the part: a sketch is
drawn through 3D points on its plane, a face or edge is picked by a point on it.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable
from typing import Any

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.gp import gp_Pnt
from OCP.GProp import GProp_GProps

from fdcad.core.features.base import FeatureState
from fdcad.core.features.sketch import face_plane
from fdcad.core.naming.resolve import resolve_face
from fdcad.core.naming.select import reference_for
from fdcad.core.sketch.model import Sketch
from fdcad.samples.builder import to_local
from tests.core.features.frame_harness import (
    FRONT,
    RIGHT,
    TOP,
    Build,
    Fixed,
    deg,
    mm,
    num,
)

Vec3 = tuple[float, float, float]
__all__ = ["FRONT", "RIGHT", "TOP", "Fixed", "Kit", "Sketch", "deg", "mm", "num"]


def area(face: Any) -> float:
    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, props)
    return props.Mass()


class Kit:
    """A part under construction, with picks by position."""

    def __init__(self) -> None:
        self.b = Build()
        self.b.rebuild()  # the base planes, so the first sketch can ask where they are
        self.used: dict[str, int] = {}
        self.watch_valid = True
        self.was_valid = True
        self.checks = 0  # place checks made by ``expect``
        self.wrong: list[str] = []

    # Features -------------------------------------------------------------------

    def add(self, ftype: str, name: str, refs: dict | None = None, data: dict | None = None,
            **params: Any) -> str:  # fmt: skip
        before = self.b.report.body_count if self.b.report is not None else 0
        fid = self.b.add(ftype, name, refs, data, **params)
        self.used[ftype] = self.used.get(ftype, 0) + 1
        after = self.b.report.body_count
        if after != before and not self.b.quiet:
            print(f"        BODIES: {before} -> {after} after {name} ({ftype})", flush=True)
        if self.watch_valid and self.b.report.body is not None:
            now = self.b.valid()
            if now != self.was_valid:
                print(
                    f"        VALIDITY: the part is {'valid' if now else 'NOT VALID'} after {name}",
                    flush=True,
                )
            self.was_valid = now
        return fid

    def ok(self, fid: str) -> bool:
        res = self.b.report.results.get(fid)
        return res is not None and res.state is not FeatureState.ERROR

    # Planes and sketches --------------------------------------------------------

    def plane_of(self, where: Any) -> Any:
        """The sketch plane of a plane feature id or of a face reference."""
        if isinstance(where, str):
            return self.b.plane(where)
        face, _issues = resolve_face(self.b.body, where, "pick")
        plane = face_plane(face)
        assert plane is not None, "the picked face is not flat"
        return plane

    def ref(self, where: Any) -> dict:
        return {"feature": where} if isinstance(where, str) else where

    def sketch(self, name: str, where: Any, draw: Callable[[Fixed, Callable], None]) -> str:
        """A sketch on a plane feature or a flat face. ``draw(sk, at)`` draws with
        ``at(x, y, z)`` turning a model point on the plane into sketch coordinates."""
        plane = self.plane_of(where)

        def at(x: float, y: float, z: float) -> tuple[float, float]:
            return to_local(plane, (x, y, z))

        sk = Fixed()
        draw(sk, at)
        fid = self.b.sketch(name, self.ref(where), sk)
        self.used["sketch"] = self.used.get("sketch", 0) + 1
        return fid

    def points(self, name: str, where: Any, pts: list[Vec3]) -> tuple[str, list[str]]:
        """A sketch of fixed points only (hole positions and the like)."""
        plane = self.plane_of(where)
        sk = Sketch()
        ids = []
        for p in pts:
            x, y = to_local(plane, p)
            pid = sk.add_point(x, y)
            sk.relate("fixed", pid)
            ids.append(pid)
        fid = self.b.sketch(name, self.ref(where), sk)
        self.used["sketch"] = self.used.get("sketch", 0) + 1
        return fid, ids

    def offset_plane(self, name: str, base: Any, distance: float, toward: Vec3) -> str:
        """A plane ``distance`` from ``base`` on the side ``toward`` points to."""
        fid = self.add("ref_plane", name, {"first": self.ref(base)}, method="offset",
                       distance=mm(distance))  # fmt: skip
        normal = self.plane_of(base).normal
        got = self.b.plane(fid).origin
        was = self.plane_of(base).origin
        moved = sum((g - w) * t for g, w, t in zip(got, was, toward, strict=True))
        if moved < 0:
            self.b.doc.feature(fid).params["flip"] = True
            self.b.rows.pop()
            self.b.rebuild(fid)
        del normal
        return fid

    def reverse_for(self, where: Any, toward: Vec3) -> bool:
        """The Reverse tick that makes an extrude from ``where`` go ``toward``."""
        n = self.plane_of(where).normal
        return sum(a * b for a, b in zip(n, toward, strict=True)) < 0

    # Picks ----------------------------------------------------------------------

    def face(self, p: Vec3, tol: float = 1e-4, flat: bool | None = None,
             of: str | None = None) -> Any:  # fmt: skip
        """The face under model point ``p`` (the largest, when it lies on a border).
        ``of``: only faces made by that feature, to tell two bodies' faces apart."""
        vertex = BRepBuilderAPI_MakeVertex(gp_Pnt(*p)).Vertex()
        found = []
        for _name, face in self.b.body.faces:
            if of is not None and not _name.startswith(f"{of}/"):
                continue
            if flat is not None:
                from OCP.GeomAbs import GeomAbs_Plane

                if (BRepAdaptor_Surface(face).GetType() == GeomAbs_Plane) != flat:
                    continue
            dist = BRepExtrema_DistShapeShape(vertex, face)
            if dist.IsDone() and dist.Value() <= tol and not any(face.IsSame(f) for f in found):
                found.append(face)
        assert found, f"no face at {p}"
        return max(found, key=area)

    def fref(self, p: Vec3, tol: float = 1e-4, flat: bool | None = None,
             of: str | None = None) -> dict:  # fmt: skip
        ref = reference_for(self.b.body, self.face(p, tol, flat, of))
        assert ref is not None
        return ref

    def edge(self, p: Vec3, tol: float = 1e-3) -> Any:
        """The edge nearest model point ``p``."""
        vertex = BRepBuilderAPI_MakeVertex(gp_Pnt(*p)).Vertex()
        best, best_d = None, 1e9
        for edge in self.b.all_edges():
            dist = BRepExtrema_DistShapeShape(vertex, edge)
            if dist.IsDone() and dist.Value() < best_d:
                best, best_d = edge, dist.Value()
        assert best is not None and best_d <= tol, f"no edge at {p} (nearest {best_d:.4f})"
        return best

    def eref(self, p: Vec3, tol: float = 1e-3) -> dict:
        ref = reference_for(self.b.body, self.edge(p, tol))
        assert ref is not None
        return ref

    def erefs(self, pts: list[Vec3], tol: float = 1e-3) -> list[dict]:
        return [self.eref(p, tol) for p in pts]

    def edges_where(self, test: Callable[[Vec3], bool]) -> list[dict]:
        """References of the edges whose middle point passes ``test``."""
        out = []
        for edge in self.b.all_edges():
            if test(self.b.edge_mid(edge)):
                ref = reference_for(self.b.body, edge)
                if ref is not None:
                    out.append(ref)
        return out

    def vref(self, p: Vec3, tol: float = 1e-3) -> dict:
        """The vertex at model point ``p``."""
        from OCP.BRep import BRep_Tool
        from OCP.TopAbs import TopAbs_VERTEX
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopoDS import TopoDS

        explorer = TopExp_Explorer(self.b.body.shape, TopAbs_VERTEX)
        while explorer.More():
            v = TopoDS.Vertex(explorer.Current())
            q = BRep_Tool.Pnt_s(v)
            if math.dist((q.X(), q.Y(), q.Z()), p) <= tol:
                ref = reference_for(self.b.body, v)
                assert ref is not None
                return ref
            explorer.Next()
        raise AssertionError(f"no vertex at {p}")

    def expect(self, what: str, inside: list = (), outside: list = (),  # type: ignore[assignment]
               some_outside: list = (), some_inside: list = ()) -> None:  # fmt: skip
        """Say so when material is not where the feature should have put or left it.

        A feature can build with no error in the wrong place (D1071): each test part
        follows its features with points that must be inside or outside the part.
        ``some_outside`` is a row of points of which at least one must be outside, for
        cuts whose exact places are the feature's own (a grid of holes, slits), and
        ``some_inside`` the same for material (the coils of a spring)."""
        wrong = [f"no material at {p}" for p in inside if not self.b.inside(p)]
        wrong += [f"material at {p}" for p in outside if self.b.inside(p)]
        if some_outside and all(self.b.inside(p) for p in some_outside):
            wrong.append(f"material all along {some_outside[0]} to {some_outside[-1]}")
        if some_inside and not any(self.b.inside(p) for p in some_inside):
            wrong.append(f"no material all along {some_inside[0]} to {some_inside[-1]}")
        self.checks += len(inside) + len(outside) + bool(some_outside) + bool(some_inside)
        if wrong:
            self.wrong.append(f"{what}: " + "; ".join(wrong))
            if not self.b.quiet:
                print(f"        WRONG PLACE: {what}: " + "; ".join(wrong), flush=True)

    def overlaps(self) -> list[str]:
        """Pairs of bodies that share material, by where they are and how much.

        Separate bodies of a test part must not overlap: on the gearbox a linked copy
        of the knob stood inside the float ball, and a lip stood inside the cover
        (D1083). Only pairs whose boxes meet are measured."""
        from OCP.Bnd import Bnd_Box
        from OCP.BRepBndLib import BRepBndLib

        from fdcad.core.features.solids import precise_volume, solids
        from fdcad.core.occ import BRepAlgoAPI_Common

        def where(box: Any) -> str:
            lo, hi = box.CornerMin(), box.CornerMax()
            return (f"({lo.X():.0f}, {lo.Y():.0f}, {lo.Z():.0f})..({hi.X():.0f}, "
                    f"{hi.Y():.0f}, {hi.Z():.0f})")  # fmt: skip

        bodies = solids(self.b.body.shape)
        boxes = []
        for solid in bodies:
            box = Bnd_Box()
            BRepBndLib.Add_s(solid, box)
            boxes.append(box)
        out = []
        for i, j in itertools.combinations(range(len(bodies)), 2):
            if boxes[i].IsOut(boxes[j]):
                continue
            shared = precise_volume(BRepAlgoAPI_Common(bodies[i], bodies[j]).Shape())
            if shared > 1e-3:
                out.append(f"bodies {where(boxes[i])} and {where(boxes[j])} share "
                           f"{shared:.1f} cubic mm")  # fmt: skip
        return out

    # Canaries ---------------------------------------------------------------------
    #
    # Four bodies that no feature of a test part works on (D1078): two blocks locked
    # together with Interlock teeth and two blocks that share a face, far from
    # everything else. A feature that hands the whole part to the kernel can join or
    # cut them without a word. Add them first, build the part, and compare.

    CANARY_X = 1200.0

    def add_canaries(self) -> list[tuple[tuple[int, ...], float]]:
        """Add the four canary bodies and return what ``canaries`` gives for them."""
        x = self.CANARY_X

        def block(name: str, y: float, z0: float, z1: float, x0: float, on: Any = None) -> str:
            where = FRONT if on is None else self.fref((x0 + 10, y + 10, z0), of=on)
            corners = [(x0, y), (x0 + 20, y), (x0 + 20, y + 20), (x0, y + 20)]

            def outline(sk: Any, at: Any) -> None:
                sk.polygon([at(a, b, z0) for a, b in corners])

            s = self.sketch(f"{name} Sketch", where, outline)
            return self.add("extrude", name, {"sketch": {"feature": s}}, operation="boss",
                            end_condition="blind", depth=mm(z1 - z0),
                            reverse=self.reverse_for(where, (0, 0, 1)), merge=False)  # fmt: skip

        lower = block("Canary Lower", 0, 0, 10, x)
        block("Canary Upper", 0, 10, 20, x, on=lower)
        self.add("interlock", "Canary Teeth", {"face": [self.fref((x + 10, 10, 10), of=lower)]},
                 tooth_size=mm(4), tooth_depth=mm(2))  # fmt: skip
        block("Canary Left", 100, 0, 10, x)
        block("Canary Right", 100, 0, 10, x + 20)
        found = self.canaries()
        assert len(found) == 4, found
        return found

    def canaries(self) -> list[tuple[tuple[int, ...], float]]:
        """Where each canary body is and its volume, for comparing before and after."""
        from OCP.Bnd import Bnd_Box
        from OCP.BRepBndLib import BRepBndLib

        from fdcad.core.features.solids import precise_volume, solids

        out = []
        for solid in solids(self.b.body.shape):
            box = Bnd_Box()
            BRepBndLib.Add_s(solid, box)
            lo, hi = box.CornerMin(), box.CornerMax()
            if lo.X() > self.CANARY_X - 5:
                corners = (lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z())
                where = tuple(round(v) for v in corners)
                out.append((where, round(precise_volume(solid), 3)))
        return sorted(out)

    # Summary --------------------------------------------------------------------

    def summary(self) -> None:
        rows = self.b.rows
        final = self.b.rebuild()
        bad = []
        for feature in self.b.doc.features:
            res = final.results.get(feature.id)
            if feature.suppressed:
                first = next((r for r in rows if r["id"] == feature.id), None)
                why = first["issues"][0][:260] if first and first["issues"] else ""
                bad.append(f"  SUPPRESSED {feature.id} {feature.type}: {feature.name}: {why}")
            elif res is not None and res.state is not FeatureState.OK:
                bad.append(f"  {res.state.name} {feature.id} {feature.type}: {feature.name}: "
                           f"{res.issues[0].message[:260]}")  # fmt: skip
        total = len(self.b.doc.features)
        live = [f for f in self.b.doc.features if not f.suppressed]
        types = sorted({f.type for f in live})
        print(f"\n{total} features ({len(live)} built), {len(types)} feature types, "
              f"bodies={final.body_count}, valid={self.b.valid()}, "
              f"build time {sum(r['seconds'] for r in rows):.0f}s", flush=True)  # fmt: skip
        print("types:", " ".join(types), flush=True)
        for line in bad:
            print(line, flush=True)
