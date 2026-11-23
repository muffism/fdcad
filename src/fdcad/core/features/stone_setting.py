"""Stone Setting: a seat and prongs for a round stone (TR408 item 2, DECISIONS D2410).

Type ``stone_setting``, for ring and pendant masters. Refs: ``seat_face`` (one flat
face the stone sits in) and ``seat_point`` (optional: a vertex, sketch point or reference
point on it; the face's middle without one). Params, lengths unless noted:

- ``stone_diameter``: the stone's girdle diameter.
- ``girdle_depth``: how deep the seat's straight wall is below the face.
- ``pavilion_angle``: optional angle of the stone's underside to the girdle plane
  (default 41 degrees, a round brilliant): the seat narrows below the wall at that
  angle to a point.
- ``prongs``: a number, 0 to 12: prongs round the seat, evenly spaced from the
  face's first direction. ``prong_diameter``, ``prong_height`` (above the face).
  Each prong stands with its middle a quarter of its diameter outside the girdle, so
  it holds the stone's edge, sinks a diameter into the part, and has a round tip.

The seat is cut and the prongs are added, in the body of the face. Faces:
``seat/wall``, ``seat/cone`` and ``prong<k>/side`` (k from 1). No Qt.
"""

from __future__ import annotations

import math

from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Vec
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.features.solids import check_result, compound
from fdcad.core.naming.names import NamedShape, faces_of
from fdcad.core.occ import BRepAlgoAPI_Fuse
from fdcad.core.units import Kind

MOST_PRONGS = 12
DEFAULT_PAVILION = math.radians(41.0)


def _value(feature: Feature, name: str, default: float | None = None) -> float:
    v = feature.params.get(name)
    if isinstance(v, Param):
        return v.value
    if default is None:
        raise FeatureError(f"{feature.name}: the {name.replace('_', ' ')} is missing. Enter it.")
    return default


def _frame(feature: Feature, ctx: BuildContext) -> tuple[gp_Pnt, gp_Dir, gp_Dir, list[Issue]]:
    """The seat's centre on the face, the face's outward normal and its first direction."""
    from fdcad.core.features.geometry_refs import resolve_placement
    from fdcad.core.features.lookup import resolve_face
    from fdcad.core.features.sketch import face_plane
    from fdcad.core.naming.names import centroid

    owner = feature.name
    ref = feature.refs.get("seat_face")
    ref = ref[0] if isinstance(ref, list) and ref else ref
    if ctx.body is None or not isinstance(ref, dict):
        raise FeatureError(f"{owner}: pick the flat face the stone sits in.")
    face, issues = resolve_face(ctx.body, ref, owner)
    plane = face_plane(face)
    if plane is None:
        raise FeatureError(f"{owner}: the face is not flat. Pick a flat face.")
    from OCP.TopAbs import TopAbs_REVERSED

    normal = plane.normal
    if face.Orientation() == TopAbs_REVERSED:
        normal = (-normal[0], -normal[1], -normal[2])
    centre = centroid(face)
    point = feature.refs.get("seat_point")
    point = point[0] if isinstance(point, list) and point else point
    if isinstance(point, dict):
        from fdcad.core.features.sprue_tree import _is_feature

        datum = ctx.result(point["feature"]).datum if _is_feature(point) else None
        if datum is not None and datum.kind == "point":
            p = datum.origin
        else:
            place = resolve_placement(ctx, point, owner, "point")
            issues += place.issues
            p = place.point
        off = sum((p[i] - plane.origin[i]) * normal[i] for i in range(3))
        centre = tuple(p[i] - off * normal[i] for i in range(3))  # type: ignore[assignment]
    return gp_Pnt(*centre), gp_Dir(*normal), gp_Dir(*plane.x_dir), issues


@register
class StoneSetting(FeatureType):
    """A round stone's seat and the prongs that hold it."""

    type_name = "stone_setting"
    makes_solid = True
    params = (
        ParamSpec("stone_diameter", kind=Kind.LENGTH),
        ParamSpec("girdle_depth", kind=Kind.LENGTH, optional=True),
        ParamSpec("pavilion_angle", kind=Kind.ANGLE, optional=True),
        ParamSpec("prongs", kind=Kind.NUMBER, optional=True),
        ParamSpec("prong_diameter", kind=Kind.LENGTH, optional=True),
        ParamSpec("prong_height", kind=Kind.LENGTH, optional=True),
    )

    def _parts(
        self, feature: Feature, ctx: BuildContext
    ) -> tuple[TopoDS_Shape, list[TopoDS_Shape], list[Issue]]:
        owner = feature.name
        centre, up, x_dir, issues = _frame(feature, ctx)
        d = _value(feature, "stone_diameter")
        girdle = _value(feature, "girdle_depth", 0.3)
        angle = _value(feature, "pavilion_angle", DEFAULT_PAVILION)
        count = round(_value(feature, "prongs", 4.0))
        prong_d = _value(feature, "prong_diameter", max(d * 0.12, 0.6))
        prong_h = _value(feature, "prong_height", d * 0.4)
        if d <= 0 or girdle < 0:
            raise FeatureError(
                f"{owner}: the stone diameter must be above zero and the girdle depth not "
                "negative. Enter other values."
            )
        if not math.radians(10) <= angle <= math.radians(80):
            raise FeatureError(
                f"{owner}: the pavilion angle must be 10 to 80 degrees. Enter another angle."
            )
        if not 0 <= count <= MOST_PRONGS:
            raise FeatureError(f"{owner}: use 0 to {MOST_PRONGS} prongs. Enter another count.")
        if count and (prong_d <= 0 or prong_h <= 0):
            raise FeatureError(
                f"{owner}: the prong diameter and height must be above zero. Enter larger values."
            )
        r = d / 2
        down = gp_Dir(-up.X(), -up.Y(), -up.Z())
        lift = 0.01  # the seat opens just above the face so the cut leaves no skin
        top = centre.Translated(gp_Vec(up).Multiplied(lift))
        wall = BRepPrimAPI_MakeCylinder(gp_Ax2(top, down, x_dir), r, girdle + lift).Shape()
        bottom = centre.Translated(gp_Vec(down).Multiplied(girdle))
        cone_h = r * math.tan(angle)
        cone = BRepPrimAPI_MakeCone(gp_Ax2(bottom, down, x_dir), r, 0.0, cone_h).Shape()
        seat = BRepAlgoAPI_Fuse(wall, cone).Shape()
        prongs: list[TopoDS_Shape] = []
        y_dir = up.Crossed(x_dir)
        reach = r + prong_d / 4
        for k in range(count):
            a = 2 * math.pi * k / count
            offset = gp_Vec(x_dir).Multiplied(reach * math.cos(a)) + gp_Vec(y_dir).Multiplied(
                reach * math.sin(a)
            )
            foot = centre.Translated(offset).Translated(gp_Vec(down).Multiplied(prong_d))
            rod = BRepPrimAPI_MakeCylinder(
                gp_Ax2(foot, up, x_dir), prong_d / 2, prong_h + prong_d
            ).Shape()
            tip = BRepPrimAPI_MakeSphere(
                foot.Translated(gp_Vec(up).Multiplied(prong_h + prong_d)), prong_d / 2
            ).Shape()
            prongs.append(BRepAlgoAPI_Fuse(rod, tip).Shape())
        return seat, prongs, issues

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Cut the seat, then add the prongs."""
        body = ctx.body
        if body is None:
            raise FeatureError(f"{feature.name}: the part is empty. Add a body first.")
        seat, prongs, issues = self._parts(feature, ctx)
        # Cut and join through ``combine`` (D1055). A plain fuse of the prongs with the
        # whole part also joined every other body that shared a face with it: the
        # letters of an inlay in their pockets, a cover on its housing. Twelve bodies
        # became part of one, with no word. ``combine`` joins the prongs only to the
        # bodies they touch.
        from fdcad.core.features.solids import combine, compound

        seat_faces = faces_of(seat)
        seat_tool = NamedShape(
            seat,
            [(f"{feature.id}/seat/wall", f) for f in seat_faces[:1]]
            + [(f"{feature.id}/seat/cone", f) for f in seat_faces[1:]],
        )
        try:
            result = combine(feature.id, feature.name, body, seat_tool, "cut")
        except FeatureError:
            raise FeatureError(
                f"{feature.name}: the seat could not be cut. Use a smaller stone."
            ) from None
        if prongs:
            prong_names = [
                (f"{feature.id}/prong{k}/side", f)
                for k, p in enumerate(prongs, start=1)
                for f in faces_of(p)
            ]
            try:
                result = combine(
                    feature.id, feature.name, result, NamedShape(compound(prongs), prong_names),
                    "boss", pieces=True,
                )  # fmt: skip
            except FeatureError:
                raise FeatureError(
                    f"{feature.name}: the prongs could not be joined. Use fewer or thinner prongs."
                ) from None
        issues += check_result(feature.id, feature.name, ctx.body, result, None)
        return FeatureResult(body=result, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The seat and prongs, for the preview."""
        seat, prongs, _issues = self._parts(feature, ctx)
        shape = compound([seat, *prongs])
        return NamedShape(shape, [])
