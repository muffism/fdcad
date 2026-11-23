"""Wrap, analytical method (PHASE4_SPEC P4.7, PLAN Phase 4, DECISIONS D322).

Wraps the closed contours of a sketch onto a cylindrical or flat face and
embosses (raises), debosses (sinks) or scribes (splits the face along) them.

On a cylinder the sketch plane must touch the cylinder along a line. A sketch
point at distance ``c`` across that line and ``s`` along the axis goes to the
point turned ``c / R`` about the axis and ``s`` along it, so lengths along the
surface are kept. Each sketch curve becomes a curve on the cylinder: it is laid
in the sketch plane in (c, s), made a B-spline, and its poles are scaled by
``1 / R`` across (an exact affine change of a rational spline).

Params (FDEF_SPEC 5.3.31):

- ``wrap_type``: ``emboss``, ``deboss`` or ``scribe``.
- ``thickness``: length (emboss and deboss).
- ``reverse``: optional boolean, wrap the sketch the other way round the axis.
- ``method``: optional, ``spline`` for the Spline surface method (any face,
  ``core/features/wrap_spline.py``, DECISIONS D528), or ``project`` (any face, the
  sketch projected along a direction, ``core/features/wrap_project.py``, TR156,
  D2113); left out for analytical.

Refs: ``sketch`` (closed contours only) and ``face`` (one face reference);
``pull``: optional, a line, edge or plane (TR75 item 2, D2112). With it, emboss and
deboss walls run along that direction instead of square to the face.

Face roles: ``wrap/face#k``.
"""

from __future__ import annotations

from typing import Any

from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakeWire,
)
from OCP.BRepLib import BRepLib
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeThickSolid
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.BRepTools import BRepTools, BRepTools_WireExplorer
from OCP.Geom import Geom_CylindricalSurface, Geom_TrimmedCurve
from OCP.Geom2dConvert import Geom2dConvert
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
from OCP.GeomAPI import GeomAPI
from OCP.gp import gp_Ax3, gp_Dir, gp_Lin, gp_Pln, gp_Pnt, gp_Pnt2d, gp_Vec
from OCP.ShapeFix import ShapeFix_Face
from OCP.TopAbs import TopAbs_WIRE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape, TopoDS_Wire

from fdcad.core.document.model import Feature
from fdcad.core.features import fastening as fx
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.features.modify import require_body
from fdcad.core.features.sketch import face_plane, sketch_input
from fdcad.core.features.solids import (
    FUZZY_TOLERANCE,
    check_result,
    combine,
    compound,
    right_side_out,
)
from fdcad.core.naming.names import NamedShape, carry, restrict
from fdcad.core.occ import BRepAlgoAPI_Splitter, ShapeList
from fdcad.core.sketch.profiles import SketchPlane
from fdcad.core.units import Kind

WRAP_TYPES = ("emboss", "deboss", "scribe")
#: Wrap methods (D528); ``analytical`` is the default and is not written.
WRAP_METHODS = ("analytical", "spline", "project")  # project: TR156 (D2113)
_TOUCH_TOL = 1e-4


class CylinderMap:
    """Takes sketch plane geometry onto a cylinder the plane touches."""

    def __init__(
        self, axis_origin: fx.Vec3, axis: fx.Vec3, radius: float, touch: fx.Vec3, mirror: bool
    ) -> None:
        self.axis = fx.unit(axis)
        self.radius = radius
        foot = fx.add(axis_origin, self.axis, fx.dot(fx.sub(touch, axis_origin), self.axis))
        self.origin = foot
        self.out = fx.unit(fx.sub(touch, foot))
        self.around = fx.cross(self.axis, self.out)
        self.touch = touch
        self.mirror = mirror
        self.surface = Geom_CylindricalSurface(
            gp_Ax3(gp_Pnt(*foot), gp_Dir(*self.axis), gp_Dir(*self.out)), radius
        )
        # The sketch plane as a 2D frame: x across (round the axis), y along the axis.
        x_dir = fx.neg(self.around) if mirror else self.around
        self.plane = gp_Pln(
            gp_Ax3(gp_Pnt(*touch), gp_Dir(*fx.cross(x_dir, self.axis)), gp_Dir(*x_dir))
        )
        self.height0 = fx.dot(fx.sub(touch, foot), self.axis)

    def edge(self, curve3d: BRepAdaptor_Curve) -> TopoDS_Shape:
        """The edge on the cylinder for one sketch edge."""
        geom = Geom_TrimmedCurve(
            curve3d.Curve().Curve(), curve3d.FirstParameter(), curve3d.LastParameter()
        )
        flat = GeomAPI.To2d_s(geom, self.plane)
        spline = Geom2dConvert.CurveToBSplineCurve_s(flat)
        for i in range(1, spline.NbPoles() + 1):
            p = spline.Pole(i)
            u = p.X() / self.radius
            if self.mirror:
                u = -u
            spline.SetPole(i, gp_Pnt2d(u, p.Y() + self.height0))
        edge = BRepBuilderAPI_MakeEdge(
            spline, self.surface, spline.FirstParameter(), spline.LastParameter()
        ).Edge()
        BRepLib.BuildCurves3d_s(edge, 1e-7)
        return edge

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

    def _wire(self, wire: TopoDS_Wire) -> TopoDS_Wire:
        maker = BRepBuilderAPI_MakeWire()
        explorer = BRepTools_WireExplorer(wire)
        while explorer.More():
            maker.Add(TopoDS.Edge(self.edge(BRepAdaptor_Curve(explorer.Current()))))
            explorer.Next()
        if not maker.IsDone():
            raise FeatureError("a wrapped contour could not be closed. Close the sketch contours.")
        return maker.Wire()


@register
class Wrap(FeatureType):
    """Emboss, deboss or scribe a sketch on a cylindrical or flat face."""

    type_name = "wrap"
    makes_solid = True
    params = (
        ParamSpec("wrap_type", choices=WRAP_TYPES, default="emboss"),
        ParamSpec("method", choices=WRAP_METHODS, default="analytical"),
    )

    def kind_of(self, name: str) -> Kind | None:
        """The thickness is a length."""
        if name == "thickness":
            return Kind.LENGTH
        return super().kind_of(name)

    def _target(self, feature: Feature, ctx: BuildContext) -> tuple[TopoDS_Face, list[Issue]]:
        return fx.face_of(feature, ctx)

    def _faces(
        self, feature: Feature, ctx: BuildContext
    ) -> tuple[list[TopoDS_Face], str, fx.Vec3 | None, list[Issue]]:
        """Wrapped (or laid) faces, the face kind and the outward normal on flat faces."""
        name = feature.name
        sketch = sketch_input(feature, ctx)
        assert sketch.profile is not None
        target, issues = self._target(feature, ctx)
        if feature.params.get("method") == "spline":
            wrapped, _mapper = self._spline_faces(
                feature, target, sketch.plane, list(sketch.profile.faces)
            )
            return wrapped, "spline", None, issues
        surface = BRepAdaptor_Surface(target)
        kind = surface.GetType()
        plane = sketch.plane
        if kind == GeomAbs_Plane:
            on = face_plane(target)
            assert on is not None
            if abs(fx.dot(on.normal, plane.normal)) < 1 - 1e-6:
                raise FeatureError(f"{name}: the sketch must lie on the flat face. Sketch on it.")
            gap = fx.dot(fx.sub(plane.origin, on.origin), on.normal)
            if abs(gap) > _TOUCH_TOL:
                raise FeatureError(f"{name}: the sketch plane must touch the face. Sketch on it.")
            return list(sketch.profile.faces), "plane", on.normal, issues
        if kind != GeomAbs_Cylinder:
            raise FeatureError(
                f"{name}: the analytical wrap works on cylindrical and flat faces. Pick one, "
                "or choose the Spline method for other faces such as cones."
            )
        cylinder = surface.Cylinder()
        axis = cylinder.Axis()
        o, d = axis.Location(), axis.Direction()
        axis_origin, axis_dir = (o.X(), o.Y(), o.Z()), (d.X(), d.Y(), d.Z())
        radius = cylinder.Radius()
        n = fx.unit(plane.normal)
        if abs(fx.dot(n, axis_dir)) > 1e-6:
            raise FeatureError(
                f"{name}: the sketch plane must be parallel to the cylinder axis. "
                "Pick a parallel plane."
            )
        to_plane = fx.dot(fx.sub(plane.origin, axis_origin), n)
        if abs(abs(to_plane) - radius) > _TOUCH_TOL:
            raise FeatureError(
                f"{name}: the sketch plane must touch the cylinder. Move it to a plane tangent "
                "to the face."
            )
        touch = fx.add(axis_origin, n, to_plane)
        mapper = CylinderMap(
            axis_origin, axis_dir, radius, touch, feature.params.get("reverse") is True
        )
        try:
            wrapped = [mapper.face(f) for f in sketch.profile.faces]
        except FeatureError as exc:
            raise FeatureError(f"{name}: {exc}") from exc
        except Exception as exc:
            raise FeatureError(
                f"{name}: the sketch could not be wrapped onto the face. "
                "Move the sketch onto the face."
            ) from exc
        return wrapped, "cylinder", None, issues

    def _spline_faces(
        self, feature: Feature, target: TopoDS_Face, plane: SketchPlane, flat: list[TopoDS_Face]
    ) -> tuple[list[TopoDS_Face], Any]:
        """Spline surface method (D528): the sketch through the face's parameters."""
        from fdcad.core.features.wrap_spline import SurfaceMap

        name = feature.name
        try:
            mapper = SurfaceMap(target, plane)
            wrapped = [mapper.face(f) for f in flat]
            mapper.check_span(wrapped)
        except FeatureError as exc:
            raise FeatureError(f"{name}: {exc}") from exc
        except Exception as exc:
            raise FeatureError(
                f"{name}: the sketch could not be wrapped onto the face. "
                "Move the sketch onto the face."
            ) from exc
        return wrapped, mapper

    def _spline_solids(
        self, feature: Feature, ctx: BuildContext
    ) -> tuple[list[NamedShape], list[Issue]]:
        """Spline surface method: the wrapped faces made thick along the face normal."""
        sketch = sketch_input(feature, ctx)
        assert sketch.profile is not None
        target, issues = self._target(feature, ctx)
        faces, mapper = self._spline_faces(
            feature, target, sketch.plane, list(sketch.profile.faces)
        )
        thickness = self.number(feature, "thickness")
        if thickness <= 0:
            raise FeatureError(
                f"{feature.name}: the thickness must be greater than zero. "
                "Enter a larger thickness."
            )
        outward = feature.params.get("wrap_type", "emboss") == "emboss"
        out: list[NamedShape] = []
        for face in faces:
            try:
                solid = mapper.thick(face, thickness, outward)
            except FeatureError as exc:
                raise FeatureError(f"{feature.name}: {exc}") from exc
            out.append(NamedShape(solid, restrict([], solid, f"{feature.id}/wrap")))
        return out, issues

    def _solids(self, feature: Feature, ctx: BuildContext) -> tuple[list[NamedShape], list[Issue]]:
        if feature.params.get("method") == "spline":
            return self._spline_solids(feature, ctx)
        if feature.params.get("method") == "project":
            return self._projected(feature, ctx)
        faces, kind, normal, issues = self._faces(feature, ctx)
        thickness = self.number(feature, "thickness")
        if thickness <= 0:
            raise FeatureError(
                f"{feature.name}: the thickness must be greater than zero. "
                "Enter a larger thickness."
            )
        outward = feature.params.get("wrap_type", "emboss") == "emboss"
        out: list[NamedShape] = []
        pull = self._pull(feature, ctx)
        for face in faces:
            if pull is not None:  # TR75 item 2 (D2112): walls along the pull direction
                from fdcad.core.features.wrap_pull import pulled

                solid = pulled(feature.name, face, kind, normal, pull, thickness, outward)
            elif kind == "plane":
                assert normal is not None
                vector = fx.add((0, 0, 0), normal, thickness if outward else -thickness)
                solid = BRepPrimAPI_MakePrism(face, gp_Vec(*vector)).Shape()
            else:
                solid = self._thick(feature, face, thickness, outward)
            out.append(NamedShape(solid, restrict([], solid, f"{feature.id}/wrap")))
        return out, issues

    def _projected(
        self, feature: Feature, ctx: BuildContext
    ) -> tuple[list[NamedShape], list[Issue]]:
        """Project method (TR156, D2113): along the pull direction or the sketch normal."""
        from fdcad.core.features.wrap_project import projected

        body = require_body(feature, ctx)
        sketch = sketch_input(feature, ctx)
        assert sketch.profile is not None
        target, issues = self._target(feature, ctx)
        thickness = self.number(feature, "thickness")
        if thickness <= 0:
            raise FeatureError(
                f"{feature.name}: the height must be greater than zero. Enter a larger height."
            )
        direction = self._pull(feature, ctx) or fx.unit(sketch.plane.normal)
        outward = feature.params.get("wrap_type", "emboss") == "emboss"
        shapes = projected(
            feature.name,
            list(sketch.profile.faces),
            direction,
            target,
            body.shape,
            thickness,
            outward,
            sketch.plane.origin,
        )
        return [NamedShape(s, restrict([], s, f"{feature.id}/wrap")) for s in shapes], issues

    @staticmethod
    def _pull(feature: Feature, ctx: BuildContext) -> fx.Vec3 | None:
        """The pull direction, or None for walls square to the face."""
        ref = feature.refs.get("pull")
        if isinstance(ref, list):
            ref = ref[0] if ref else None
        if not isinstance(ref, dict):
            return None
        from fdcad.core.features.geometry_refs import resolve_placement

        return fx.unit(resolve_placement(ctx, ref, feature.name, "direction").direction)

    @staticmethod
    def _thick(
        feature: Feature, face: TopoDS_Face, thickness: float, outward: bool
    ) -> TopoDS_Shape:
        """The wrapped face made thick outward (emboss) or inward (deboss)."""
        surface = BRepAdaptor_Surface(face)
        cylinder = surface.Cylinder()
        radius = cylinder.Radius()
        axis = cylinder.Axis()
        for sign in (1.0, -1.0):
            maker = BRepOffsetAPI_MakeThickSolid()
            maker.MakeThickSolidBySimple(face, sign * thickness)
            maker.Build()
            if not maker.IsDone():
                continue
            shape = right_side_out(maker.Shape())  # the kernel can return it inside out (D1049)
            from OCP.BRepGProp import BRepGProp
            from OCP.GProp import GProp_GProps

            props = GProp_GProps()
            BRepGProp.VolumeProperties_s(shape, props)
            c = props.CentreOfMass()
            distance = gp_Lin(axis).Distance(c)
            if (distance > radius) == outward:
                return shape
        raise FeatureError(
            f"{feature.name}: the wrapped shape could not be made thick. Reduce the thickness."
        )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Emboss, deboss or scribe."""
        body = require_body(feature, ctx)
        kind = feature.params.get("wrap_type", "emboss")
        if kind == "scribe" and feature.params.get("method") == "project":
            raise FeatureError(
                f"{feature.name}: the Project method raises or sinks the shape. "
                "Choose Emboss or Deboss, or another method to scribe."
            )
        # The wrap changes the body of the picked face only (D2622). It changed the whole
        # part: an emboss that touched a block standing on the face joined the block.
        from fdcad.core.features.bodies import in_body_of

        if kind == "scribe":
            faces, _k, _n, issues = self._faces(feature, ctx)
            target, _found = self._target(feature, ctx)
            result = in_body_of(body, target, feature.id, lambda part: scribe(feature, part, faces))
        else:
            solids_, issues = self._solids(feature, ctx)
            target, _found = self._target(feature, ctx)
            operation = "boss" if kind == "emboss" else "cut"
            tool = NamedShape(compound([s.shape for s in solids_]), [])
            tool = NamedShape(tool.shape, restrict([], tool.shape, f"{feature.id}/wrap"))
            result = in_body_of(
                body,
                target,
                feature.id,
                lambda part: combine(feature.id, feature.name, part, tool, operation),
            )
        issues = issues + check_result(feature.id, feature.name, ctx.body, result, None)
        return FeatureResult(body=result, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The wrapped shapes, for the preview."""
        if feature.params.get("wrap_type", "emboss") == "scribe":
            faces, _k, _n, _issues = self._faces(feature, ctx)
            return NamedShape(compound(faces), [])
        solids_, _issues = self._solids(feature, ctx)
        return NamedShape(compound([s.shape for s in solids_]), [])


def scribe(feature: Feature, body: NamedShape, faces: list[TopoDS_Face]) -> NamedShape:
    """Split the part's faces along the wrapped outlines; the volume is unchanged."""
    op = BRepAlgoAPI_Splitter()
    args, tools = ShapeList(), ShapeList()
    args.Append(body.shape)
    for f in faces:
        tools.Append(f)
    op.SetArguments(args)
    op.SetTools(tools)
    op.SetFuzzyValue(FUZZY_TOLERANCE)
    op.Build()
    if not op.IsDone():
        raise FeatureError(
            f"{feature.name} failed: the outlines could not be scribed. "
            "Change the sketch slightly or pick another face."
        )
    shape = op.Shape()
    names = carry(body.faces, op.History())
    return NamedShape(shape, restrict(names, shape, f"{feature.id}/wrap"))
