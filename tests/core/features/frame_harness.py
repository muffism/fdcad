"""Build a part feature by feature, as a user would, and log what every feature did.

Support for ``test_frame_part.py`` (D1043 to D1052): the bike frame that found those
faults was built with this. No Qt."""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from typing import Any

from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Face, TopoDS_Shape

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.naming.names import NamedShape, centroid
from fdcad.core.naming.select import reference_for
from fdcad.core.occ import ShapeListMap, shape_list
from fdcad.core.rebuild.engine import RebuildEngine, RebuildReport
from fdcad.core.sketch.model import Ellipse, Sketch, sketch_to_data
from fdcad.core.sketch.profiles import SketchPlane
from fdcad.core.units import UnitSystem
from fdcad.samples.builder import to_local

Vec = tuple[float, float]
Vec3 = tuple[float, float, float]
FRONT, TOP, RIGHT = "f2", "f3", "f4"


def mm(value: float) -> Param:
    return Param(f"{value:g}", value)


def deg(value: float) -> Param:
    return Param(f"{value:g}", math.radians(value))


def num(value: float) -> Param:
    return Param(f"{value:g}", float(value))


class Fixed:
    """A sketch drawn at known places, every point fixed, sizes dimensioned where simple."""

    def __init__(self) -> None:
        self.sk = Sketch()

    def _fix(self, *pids: str) -> None:
        for pid in pids:
            self.sk.relate("fixed", pid)

    def point(self, x: float, y: float, construction: bool = False) -> str:
        pid = self.sk.add_point(x, y, construction)
        self._fix(pid)
        return pid

    def line(self, a: Vec, b: Vec, construction: bool = False) -> str:
        lid = self.sk.add_line(a[0], a[1], b[0], b[1], construction)
        line = self.sk.entities[lid]
        self._fix(line.p1, line.p2)  # type: ignore[union-attr]
        return lid

    def circle(self, c: Vec, diameter: float) -> str:
        cid = self.sk.add_circle(c[0], c[1], diameter / 2)
        self._fix(self.sk.entities[cid].center)  # type: ignore[union-attr]
        self.sk.dimension("diameter", [cid], mm(diameter))
        return cid

    def ellipse(self, c: Vec, a: float, b: float, angle: float = 0.0) -> str:
        """Half axes ``a`` (along ``angle``, radians) and ``b``."""
        ux, uy = math.cos(angle), math.sin(angle)
        sk = self.sk
        pc = sk.add_point(c[0], c[1])
        pa = sk.add_point(c[0] + a * ux, c[1] + a * uy)
        pb = sk.add_point(c[0] - b * uy, c[1] + b * ux)
        eid = sk.new_id()
        sk.entities[eid] = Ellipse(eid, pc, pa, pb)
        self._fix(pc, pa)
        sk.dimension("distance", [pc, pb], mm(b))
        return eid

    def polygon(self, points: list[Vec]) -> list[str]:
        """A closed outline of straight lines; shared corners are joined."""
        sk = self.sk
        lines = []
        for i, a in enumerate(points):
            b = points[(i + 1) % len(points)]
            lines.append(sk.entities[sk.add_line(a[0], a[1], b[0], b[1])])
        for i, line in enumerate(lines):
            sk.relate("coincident", line.p2, lines[(i + 1) % len(lines)].p1)  # type: ignore[union-attr]
            self._fix(line.p1)  # type: ignore[union-attr]
        return [line.id for line in lines]

    def arc(self, c: Vec, radius: float, a0: float, a1: float) -> str:
        aid = self.sk.add_arc(c[0], c[1], radius, a0, a1)
        arc = self.sk.entities[aid]
        self._fix(arc.center, arc.start, arc.end)  # type: ignore[union-attr]
        return aid


class Build:
    """A document under construction. Every added feature is rebuilt and logged."""

    def __init__(self) -> None:
        self.doc: Document = new_document(UnitSystem.MM)
        self.engine = RebuildEngine()
        self.report: RebuildReport | None = None
        self.rows: list[dict[str, Any]] = []
        self.quiet = False
        #: A feature that fails is suppressed (and stays in the log) so the ones after
        #: it are judged on their own.
        self.skip_failed = True

    # Adding ---------------------------------------------------------------------------

    def add(
        self,
        ftype: str,
        name: str,
        refs: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        **params: Any,
    ) -> str:
        fid = self.doc.new_feature_id()
        feature = Feature(fid, ftype, name, params=dict(params), refs=dict(refs or {}))
        if data is not None:
            feature.data = data
        self.doc.features.append(feature)
        self.rebuild(fid)
        return fid

    def sketch(self, name: str, plane: dict[str, Any], sk: Fixed | Sketch) -> str:
        model = sk.sk if isinstance(sk, Fixed) else sk
        return self.add("sketch", name, {"plane": plane}, data=sketch_to_data(model))

    def rebuild(self, fid: str | None = None) -> RebuildReport:
        start = time.perf_counter()
        self.report = self.engine.rebuild(self.doc)
        took = time.perf_counter() - start
        if fid is not None:
            result = self.report.results[fid]
            feature = self.doc.feature(fid)
            row = {
                "id": fid,
                "type": feature.type,
                "name": feature.name,
                "state": result.state.name,
                "seconds": round(took, 2),
                "bodies": self.report.body_count,
                "issues": [i.message for i in result.issues],
            }
            self.rows.append(row)
            if not self.quiet:
                flag = "" if result.state is FeatureState.OK else f"  <<< {result.state.name}"
                print(
                    f"{fid:>4} {feature.type:<16} {feature.name:<34} {took:6.2f}s "
                    f"bodies={self.report.body_count}{flag}",
                    flush=True,
                )
                for issue in result.issues:
                    print(f"        {issue.state.name}: {issue.message[:400]}", flush=True)
            if result.state is FeatureState.ERROR and self.skip_failed and feature.type != "sketch":
                feature.suppressed = True
                row["suppressed"] = True
                self.report = self.engine.rebuild(self.doc)
        return self.report

    # Looking --------------------------------------------------------------------------

    @property
    def body(self) -> NamedShape:
        assert self.report is not None and self.report.body is not None
        return self.report.body

    def plane(self, fid: str) -> SketchPlane:
        assert self.report is not None
        plane = self.report.results[fid].plane
        assert plane is not None, fid
        return plane

    def local(self, fid: str, p: Vec3) -> Vec:
        return to_local(self.plane(fid), p)

    def ok(self, fid: str) -> bool:
        assert self.report is not None
        return self.report.results[fid].state is not FeatureState.ERROR

    def faces(self, test: Callable[[str, TopoDS_Face], bool]) -> list[TopoDS_Face]:
        found: list[TopoDS_Face] = []
        for name, face in self.body.faces:
            if test(name, face) and not any(face.IsSame(f) for f in found):
                found.append(face)
        return found

    def face_ref(self, test: Callable[[str, TopoDS_Face], bool], count: int = 1) -> Any:
        found = self.faces(test)
        assert len(found) == count, f"expected {count} faces, found {len(found)}"
        refs = [reference_for(self.body, f) for f in found]
        assert all(r is not None for r in refs)
        return refs[0] if count == 1 else refs

    def named(self, prefix: str) -> list[dict[str, Any]]:
        """References of every face whose name starts with ``prefix``."""
        refs = [reference_for(self.body, f) for f in self.faces(lambda n, _f: n.startswith(prefix))]
        return [r for r in refs if r is not None]

    def edges_between(
        self, a: Callable[[str], bool], b: Callable[[str], bool]
    ) -> list[TopoDS_Edge]:
        """Edges with a face whose name passes ``a`` on one side and ``b`` on the other."""
        body = self.body
        found = ShapeListMap()
        TopExp.MapShapesAndAncestors_s(body.shape, TopAbs_EDGE, TopAbs_FACE, found)
        out: list[TopoDS_Edge] = []
        for i in range(1, found.Extent() + 1):
            faces = [TopoDS.Face(f) for f in shape_list(found.FindFromIndex(i))]
            if len(faces) != 2 or faces[0].IsSame(faces[1]):
                continue
            n0 = body.names_of(faces[0])
            n1 = body.names_of(faces[1])
            hit = (any(a(n) for n in n0) and any(b(n) for n in n1)) or (
                any(a(n) for n in n1) and any(b(n) for n in n0)
            )
            if hit:
                out.append(TopoDS.Edge(found.FindKey(i)))
        return out

    def edge_refs(self, edges: list[TopoDS_Edge]) -> list[dict[str, Any]]:
        refs = [reference_for(self.body, e) for e in edges]
        return [r for r in refs if r is not None]

    def edge_mid(self, edge: TopoDS_Edge) -> Vec3:
        from OCP.BRepAdaptor import BRepAdaptor_Curve

        c = BRepAdaptor_Curve(edge)
        p = c.Value((c.FirstParameter() + c.LastParameter()) / 2)
        return (p.X(), p.Y(), p.Z())

    def all_edges(self) -> list[TopoDS_Edge]:
        found = ShapeListMap()
        TopExp.MapShapesAndAncestors_s(self.body.shape, TopAbs_EDGE, TopAbs_FACE, found)
        return [TopoDS.Edge(found.FindKey(i)) for i in range(1, found.Extent() + 1)]

    def faces_at(self, edge: TopoDS_Edge) -> list[TopoDS_Face]:
        found = ShapeListMap()
        TopExp.MapShapesAndAncestors_s(self.body.shape, TopAbs_EDGE, TopAbs_FACE, found)
        index = found.FindIndex(edge)
        return [TopoDS.Face(f) for f in shape_list(found.FindFromIndex(index))] if index else []

    def mirrored(self, edges: list[TopoDS_Edge]) -> list[TopoDS_Edge]:
        """The edges of the part that are the mirror images (about z = 0) of ``edges``."""
        every = [(self.edge_mid(e), e) for e in self.all_edges()]
        out = []
        for edge in edges:
            x, y, z = self.edge_mid(edge)
            for mid, other in every:
                if math.dist(mid, (x, y, -z)) < 1e-4 and not other.IsSame(edge):
                    out.append(other)
                    break
        return out

    def click_fix(self, fid: str, label: str) -> bool:
        """Apply the fix button whose text starts with ``label``, as a click would."""
        from fdcad.core.features.fixes import fixed_feature

        assert self.report is not None
        for issue in self.report.results[fid].issues:
            for fix in issue.fixes:
                if not fix.label.startswith(label):
                    continue
                new = fixed_feature(self.doc, fid, fix)
                if new is None:
                    continue
                index = next(i for i, f in enumerate(self.doc.features) if f.id == fid)
                self.doc.features[index] = new
                self.rows[-1]["state"] = "ERROR, then fixed by a click"
                self.rows[-1]["fix"] = fix.label
                if not self.quiet:
                    print(f"        CLICKED: {fix.label}", flush=True)
                self.rebuild(fid)
                return True
        if not self.quiet:
            offered = [f.label for i in self.report.results[fid].issues for f in i.fixes]
            print(f"        no '{label}' button; offered: {offered}", flush=True)
        return False

    def inside(self, p: Vec3) -> bool:
        """True when ``p`` is inside one of the part's bodies. Each body is asked on its
        own: asked of the whole compound, the kernel said a point in the middle of the
        gearbox cover was outside it (2026-11-13)."""
        from OCP.Bnd import Bnd_Box
        from OCP.BRepBndLib import BRepBndLib
        from OCP.BRepClass3d import BRepClass3d_SolidClassifier
        from OCP.gp import gp_Pnt
        from OCP.TopAbs import TopAbs_IN

        from fdcad.core.features.solids import solids

        point = gp_Pnt(*p)
        for solid in solids(self.body.shape):
            box = Bnd_Box()
            BRepBndLib.Add_s(solid, box)
            if box.IsOut(point):
                continue
            if BRepClass3d_SolidClassifier(solid, point, 1e-6).State() == TopAbs_IN:
                return True
        return False

    def volume(self) -> float:
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(self.body.shape, props)
        return props.Mass()

    def valid(self) -> bool:
        return bool(BRepCheck_Analyzer(self.body.shape, True, True).IsValid())

    def summary(self) -> None:
        bad = [r for r in self.rows if r["state"] != "OK"]
        total = sum(r["seconds"] for r in self.rows)
        print(
            f"\n{len(self.rows)} features, {len(bad)} not OK, bodies={self.rows[-1]['bodies']}, "
            f"volume={self.volume():.1f} mm3, valid={self.valid()}, build time {total:.1f}s",
            flush=True,
        )
        for r in bad:
            print(f"  {r['id']} {r['name']} [{r['state']}]: {r['issues'][0][:300]}", flush=True)


def face_centre(face: TopoDS_Shape) -> Vec3:
    return centroid(face)


def near(p: Vec3, q: Vec3, tol: float = 1e-3) -> bool:
    return math.dist(p, q) < tol
