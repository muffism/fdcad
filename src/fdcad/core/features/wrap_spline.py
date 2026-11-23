"""Wrap, Spline surface method (PHASE4_SPEC P4.7 item 2, DECISIONS D528).

Works on any single face. The sketch origin is projected onto the face, giving
the face parameters (u0, v0). The sketch's x and y directions are turned into
the face's tangent plane there (lengths kept), and written in the face's
tangent directions ``dS/du`` and ``dS/dv``. That gives one fixed affine map
from sketch coordinates to face parameters:

    (u, v) = (u0, v0) + A (x, y)

so lengths along the face match the sketch near the origin and follow the
face's parameters further away. On planes and cylinders the map is exact.
Each sketch curve is laid in the sketch plane, made a B-spline and its poles
are moved by the map (exact, also for rational splines), giving a curve on
the face. The sketch must stay on the face: it cannot wrap all the way round.
"""

from __future__ import annotations

import math

from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakeVertex,
    BRepBuilderAPI_MakeWire,
)
from OCP.BRepClass import BRepClass_FaceClassifier
from OCP.BRepExtrema import BRepExtrema_DistShapeShape, BRepExtrema_IsInFace
from OCP.BRepLib import BRepLib
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeThickSolid
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.BRepTools import BRepTools, BRepTools_WireExplorer
from OCP.Geom import Geom_TrimmedCurve
from OCP.Geom2d import Geom2d_BSplineCurve
from OCP.Geom2dConvert import Geom2dConvert
from OCP.GeomAbs import GeomAbs_Plane
from OCP.GeomAPI import GeomAPI
from OCP.gp import gp_Pln, gp_Pnt, gp_Pnt2d, gp_Vec
from OCP.ShapeFix import ShapeFix_Face
from OCP.TopAbs import TopAbs_IN, TopAbs_ON, TopAbs_REVERSED, TopAbs_WIRE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape, TopoDS_Wire

from fdcad.core.features import fastening as fx
from fdcad.core.features.base import FeatureError
from fdcad.core.sketch.profiles import SketchPlane

#: Points checked along each wrapped curve to see that it stays on the face.
_SAMPLES = 24
_EDGE_ON = "the sketch plane is seen edge on from the face. Sketch on a plane that faces it."


def _vec(v: gp_Vec) -> fx.Vec3:
    return (v.X(), v.Y(), v.Z())


class SurfaceMap:
    """Takes sketch plane geometry onto a face through the face's parameters."""

    def __init__(self, face: TopoDS_Face, plane: SketchPlane) -> None:
        self.target = face
        self.surface = BRep_Tool.Surface_s(face)
        self.adaptor = BRepAdaptor_Surface(face)
        self.flat = gp_Pln(plane.ax3())
        self.reversed = face.Orientation() == TopAbs_REVERSED
        origin = gp_Pnt(*plane.origin)
        dist = BRepExtrema_DistShapeShape(BRepBuilderAPI_MakeVertex(origin).Vertex(), face)
        if not dist.IsDone() or dist.NbSolution() < 1:
            raise FeatureError("the sketch origin does not project onto the face. Move the sketch.")
        if dist.SupportTypeShape2(1) == BRepExtrema_IsInFace:
            u0, v0 = dist.ParOnFaceS2(1)
        else:  # nearest on the face's boundary: its parameters on the surface
            from OCP.ShapeAnalysis import ShapeAnalysis_Surface

            uv = ShapeAnalysis_Surface(self.surface).ValueOfUV(dist.PointOnShape2(1), 1e-7)
            u0, v0 = uv.X(), uv.Y()
        self.u0, self.v0 = u0, v0
        p, du, dv = gp_Pnt(), gp_Vec(), gp_Vec()
        self.adaptor.D1(u0, v0, p, du, dv)
        su, sv = _vec(du), _vec(dv)
        normal = fx.cross(su, sv)
        if math.sqrt(fx.dot(normal, normal)) < 1e-9:
            raise FeatureError("the sketch origin does not project onto the face. Move the sketch.")
        n = fx.unit(normal)
        ax = plane.ax3()
        xd, yd = ax.XDirection(), ax.YDirection()
        x_dir: fx.Vec3 = (xd.X(), xd.Y(), xd.Z())
        y_dir: fx.Vec3 = (yd.X(), yd.Y(), yd.Z())
        # The sketch axes turned into the tangent plane, lengths kept.
        x_on = fx.sub(x_dir, fx.add((0.0, 0.0, 0.0), n, fx.dot(x_dir, n)))
        y_on = fx.sub(y_dir, fx.add((0.0, 0.0, 0.0), n, fx.dot(y_dir, n)))
        if math.sqrt(fx.dot(x_on, x_on)) >= math.sqrt(fx.dot(y_on, y_on)):
            if math.sqrt(fx.dot(x_on, x_on)) < 0.1:
                raise FeatureError(_EDGE_ON)
            e1 = fx.unit(x_on)
            e2 = fx.cross(n, e1)
            if fx.dot(e2, y_dir) < 0:
                e2 = fx.neg(e2)
        else:
            if math.sqrt(fx.dot(y_on, y_on)) < 0.1:
                raise FeatureError(_EDGE_ON)
            e2 = fx.unit(y_on)
            e1 = fx.cross(e2, n)
            if fx.dot(e1, x_dir) < 0:
                e1 = fx.neg(e1)
        # Least squares: e = a * Su + b * Sv for each tangent axis.
        g11, g12, g22 = fx.dot(su, su), fx.dot(su, sv), fx.dot(sv, sv)
        det = g11 * g22 - g12 * g12
        if det <= 1e-12 * max(g11 * g22, 1e-300):
            raise FeatureError("the sketch origin does not project onto the face. Move the sketch.")

        def solve(e: fx.Vec3) -> tuple[float, float]:
            r1, r2 = fx.dot(su, e), fx.dot(sv, e)
            return ((g22 * r1 - g12 * r2) / det, (g11 * r2 - g12 * r1) / det)

        (self.a11, self.a21), (self.a12, self.a22) = solve(e1), solve(e2)
        umin, umax, vmin, vmax = BRepTools.UVBounds_s(face)
        self.bounds = (umin, umax, vmin, vmax)
        self.u_period = self.surface.UPeriod() if self.surface.IsUPeriodic() else None
        self.v_period = self.surface.VPeriod() if self.surface.IsVPeriodic() else None
        self.classifier = BRepClass_FaceClassifier()

    def uv(self, x: float, y: float) -> tuple[float, float]:
        """Face parameters of a sketch point."""
        return (
            self.u0 + self.a11 * x + self.a12 * y,
            self.v0 + self.a21 * x + self.a22 * y,
        )

    def _inside(self, u: float, v: float) -> bool:
        umin, _umax, vmin, _vmax = self.bounds
        if self.u_period:
            u = umin + (u - umin) % self.u_period
        if self.v_period:
            v = vmin + (v - vmin) % self.v_period
        self.classifier.Perform(self.target, gp_Pnt2d(u, v), 1e-6)
        return self.classifier.State() in (TopAbs_IN, TopAbs_ON)

    def curve(self, curve3d: BRepAdaptor_Curve) -> Geom2d_BSplineCurve:
        """The sketch curve in face parameters (checked to stay on the face)."""
        geom = Geom_TrimmedCurve(
            curve3d.Curve().Curve(), curve3d.FirstParameter(), curve3d.LastParameter()
        )
        flat = GeomAPI.To2d_s(geom, self.flat)
        spline = Geom2dConvert.CurveToBSplineCurve_s(flat)
        for i in range(1, spline.NbPoles() + 1):
            p = spline.Pole(i)
            spline.SetPole(i, gp_Pnt2d(*self.uv(p.X(), p.Y())))
        first, last = spline.FirstParameter(), spline.LastParameter()
        for k in range(_SAMPLES + 1):
            q = spline.Value(first + (last - first) * k / _SAMPLES)
            if not self._inside(q.X(), q.Y()):
                raise FeatureError("the sketch runs off the face. Move it or make it smaller.")
        return spline

    def check_span(self, faces: list[TopoDS_Face]) -> None:
        """Raise when the outlines would go all the way round a closed face."""
        us: list[float] = []
        vs: list[float] = []
        for face in faces:
            box = BRepTools.UVBounds_s(face)
            us += [box[0], box[1]]
            vs += [box[2], box[3]]
        if self.u_period and us and max(us) - min(us) >= self.u_period - 1e-9:
            raise FeatureError("the sketch runs off the face. Move it or make it smaller.")
        if self.v_period and vs and max(vs) - min(vs) >= self.v_period - 1e-9:
            raise FeatureError("the sketch runs off the face. Move it or make it smaller.")

    def edge(self, curve3d: BRepAdaptor_Curve) -> TopoDS_Shape:
        """The edge on the face for one sketch edge."""
        spline = self.curve(curve3d)
        edge = BRepBuilderAPI_MakeEdge(
            spline, self.surface, spline.FirstParameter(), spline.LastParameter()
        ).Edge()
        BRepLib.BuildCurves3d_s(edge, 1e-7)
        return edge

    def _wire(self, wire: TopoDS_Wire) -> TopoDS_Wire:
        maker = BRepBuilderAPI_MakeWire()
        explorer = BRepTools_WireExplorer(wire)
        while explorer.More():
            maker.Add(TopoDS.Edge(self.edge(BRepAdaptor_Curve(explorer.Current()))))
            explorer.Next()
        if not maker.IsDone():
            raise FeatureError("a wrapped contour could not be closed. Close the sketch contours.")
        return maker.Wire()

    def face(self, flat_face: TopoDS_Face) -> TopoDS_Face:
        """The wrapped face for one flat profile face (holes kept)."""
        outer = BRepTools.OuterWire_s(flat_face)
        wires = [outer]
        explorer = TopExp_Explorer(flat_face, TopAbs_WIRE)
        while explorer.More():
            wire = TopoDS.Wire(explorer.Current())
            if not wire.IsSame(outer):
                wires.append(wire)
            explorer.Next()
        maker = BRepBuilderAPI_MakeFace(self.surface, self._wire(wires[0]), True)
        for wire in wires[1:]:
            maker.Add(self._wire(wire))
        if not maker.IsDone():
            raise FeatureError(
                "the sketch could not be wrapped onto the face. Move the sketch onto the face."
            )
        fix = ShapeFix_Face(maker.Face())
        fix.FixOrientation()
        fix.Perform()
        face = fix.Face()
        BRepLib.BuildCurves3d_s(face, 1e-7)
        return face

    def outward(self, u: float, v: float) -> tuple[fx.Vec3, fx.Vec3]:
        """A point of the face's surface and the part's outward normal there."""
        p, du, dv = gp_Pnt(), gp_Vec(), gp_Vec()
        self.adaptor.D1(u, v, p, du, dv)
        n = fx.unit(fx.cross(_vec(du), _vec(dv)))
        return (p.X(), p.Y(), p.Z()), fx.neg(n) if self.reversed else n

    def thick(self, face: TopoDS_Face, thickness: float, outward: bool) -> TopoDS_Shape:
        """The wrapped face made thick along the face normal, out or in."""
        from OCP.BRepGProp import BRepGProp
        from OCP.GProp import GProp_GProps

        from fdcad.core.features.solids import right_side_out

        umin, umax, vmin, vmax = BRepTools.UVBounds_s(face)
        _p, normal = self.outward((umin + umax) / 2, (vmin + vmax) / 2)
        if self.adaptor.GetType() == GeomAbs_Plane:
            step = thickness if outward else -thickness
            return BRepPrimAPI_MakePrism(face, gp_Vec(*fx.add((0, 0, 0), normal, step))).Shape()
        # The thick shape's centre lies off the face's area centre on the side it grew.
        area = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, area)
        m = area.CentreOfMass()
        point: fx.Vec3 = (m.X(), m.Y(), m.Z())
        for sign in (1.0, -1.0):
            maker = BRepOffsetAPI_MakeThickSolid()
            maker.MakeThickSolidBySimple(face, sign * thickness)
            maker.Build()
            if not maker.IsDone():
                continue
            shape = right_side_out(maker.Shape())  # D1049
            props = GProp_GProps()
            BRepGProp.VolumeProperties_s(shape, props)
            c = props.CentreOfMass()
            side = fx.dot(fx.sub((c.X(), c.Y(), c.Z()), point), normal)
            if (side > 0) == outward:
                return shape
        raise FeatureError("the wrapped shape could not be made thick. Reduce the thickness.")


__all__ = ["SurfaceMap"]
