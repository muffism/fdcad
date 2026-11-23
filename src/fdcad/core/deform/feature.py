"""The shared part of the deformation features (PHASE4_SPEC P4.9, PLAN Phase 4, D393).

Common params (all optional):

- ``axis``: ``"x"``, ``"y"`` or ``"z"`` (default): the direction of the triad's
  third axis. The first axis is Y for X, Z for Y and X for Z, turned by ``spin``
  (angle) about the third axis.
- ``ox``, ``oy``, ``oz`` (lengths): the triad's origin. Default: the centre of
  the picked bodies' box.
- ``start``, ``end`` (lengths): the trim planes, measured along the third axis
  from the origin. Default: where the picked bodies begin and end.
- ``tolerance`` (length, default 0.01 mm): the largest allowed deviation from
  the exact deformation. A result that cannot meet it gets a warning.

Refs: ``bodies``: optional face references to faces of the bodies to deform;
without any, every body deforms.

Faces keep their names. Only the region between the trim planes deforms.
"""

from __future__ import annotations

import math
from typing import ClassVar

import numpy as np
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.gp import gp_Ax3, gp_Dir, gp_Pln, gp_Pnt, gp_Trsf
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.deform.maps import Frame, PointMap
from fdcad.core.deform.nurbs import DeformError, deform_shape
from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureState,
    FeatureType,
    Issue,
    ParamSpec,
    PreviewHandle,
)
from fdcad.core.features.bodies import body_indices, join, rest_of, sub_body
from fdcad.core.features.direct import valid_solid
from fdcad.core.features.solids import compound, solids
from fdcad.core.naming.names import NamedShape, restrict
from fdcad.core.units import Kind, UnitSystem
from fdcad.core.units.expressions import MM_PER_UNIT

Vec3 = tuple[float, float, float]
DEFAULT_TOLERANCE = 0.01
_AXES: dict[str, tuple[Vec3, Vec3]] = {
    "x": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    "y": ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    "z": ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
}
COMMON_PARAMS = (
    ParamSpec("axis", choices=tuple(_AXES), optional=True),
    ParamSpec("spin", kind=Kind.ANGLE, optional=True),
    *(ParamSpec(k, kind=Kind.LENGTH, optional=True) for k in ("ox", "oy", "oz")),
    ParamSpec("start", kind=Kind.LENGTH, optional=True),
    ParamSpec("end", kind=Kind.LENGTH, optional=True),
    ParamSpec("tolerance", kind=Kind.LENGTH, optional=True),
)


def box_of(shape: TopoDS_Shape) -> tuple[Vec3, Vec3]:
    """The lower and upper corners of a shape's box."""
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    lo, hi = box.CornerMin(), box.CornerMax()
    return (lo.X(), lo.Y(), lo.Z()), (hi.X(), hi.Y(), hi.Z())


def local_box(shape: TopoDS_Shape, frame: Frame) -> tuple[Vec3, Vec3]:
    """The lower and upper corners of a shape's box in triad coordinates."""
    trsf = gp_Trsf()
    trsf.SetTransformation(gp_Ax3(gp_Pnt(*frame.origin), gp_Dir(*frame.z), gp_Dir(*frame.x)))
    return box_of(shape.Moved(TopLoc_Location(trsf)))


def _rotated_first(third: Vec3, first: Vec3, spin: float) -> Vec3:
    t = np.asarray(third)
    f = np.asarray(first)
    turned = f * math.cos(spin) + np.cross(t, f) * math.sin(spin)
    return (float(turned[0]), float(turned[1]), float(turned[2]))


def _extent(frame: Frame, lo: Vec3, hi: Vec3) -> tuple[float, float]:
    corners = np.array(
        [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    )
    along = frame.to_local(corners)[:, 2]
    return float(along.min()), float(along.max())


def _text(value: float, kind: Kind, units: UnitSystem) -> str:
    if kind is Kind.LENGTH:
        return f"{value / MM_PER_UNIT[units]:.6g}"
    return f"{value:.6g}"


def default_params(
    shape: TopoDS_Shape,
    axis: str,
    units: UnitSystem,
    origin: Vec3 | None = None,
    spin: float = 0.0,
) -> dict[str, Param]:
    """Triad and trim plane values that fit ``shape``: centred, planes at its ends.

    With ``origin``, the triad stays there and only ``start`` and ``end`` are
    given: the planes at the ends of ``shape`` along ``axis`` from ``origin``.
    """
    lo, hi = box_of(shape)
    centre = tuple((a + b) / 2.0 for a, b in zip(lo, hi, strict=True))
    third, first = _AXES.get(axis, _AXES["z"])
    first = _rotated_first(third, first, spin)
    frame = Frame.from_axes(origin or centre, third, first)  # type: ignore[arg-type]
    start, end = _extent(frame, lo, hi)
    values = {"start": start, "end": end}
    if origin is None:
        values = {"ox": centre[0], "oy": centre[1], "oz": centre[2], **values}
    return {k: Param(_text(v, Kind.LENGTH, units), v) for k, v in values.items()}


class DeformFeature(FeatureType):
    """Base class: subclasses give ``point_map`` and their own params."""

    makes_solid = True
    own_params: ClassVar[tuple[ParamSpec, ...]] = ()
    #: The value to suggest changing when the result fails ("angle", "factor").
    main_value: ClassVar[str] = "values"

    # Subclass hook ------------------------------------------------------------------

    def point_map(
        self, feature: Feature, ctx: BuildContext, frame: Frame, z0: float, z1: float
    ) -> PointMap:
        """The deformation for this feature. Raises FeatureError."""
        raise NotImplementedError

    # Shared parts -------------------------------------------------------------------

    def _value(self, feature: Feature, name: str, default: float) -> float:
        value = feature.params.get(name)
        return value.value if isinstance(value, Param) else default

    def setup(
        self, feature: Feature, ctx: BuildContext
    ) -> tuple[NamedShape, list[int], list[Issue], Frame, float, float]:
        """The picked bodies, their indices, issues, the triad and the trim planes."""
        name = feature.name
        if ctx.body is None:
            raise FeatureError(f"{name}: the part has no bodies to deform. Add a boss first.")
        if feature.refs.get("bodies"):
            indices, issues = body_indices(ctx, feature.refs["bodies"], name)
        else:
            indices, issues = list(range(len(solids(ctx.body.shape)))), []
        picked = sub_body(ctx.body, indices, feature.id)
        lo, hi = box_of(picked.shape)
        axis = str(feature.params.get("axis", "z"))
        if axis not in _AXES:
            raise FeatureError(f"{name}: the axis must be x, y or z. Choose one of the three axes.")
        third, first = _AXES[axis]
        first = _rotated_first(third, first, self._value(feature, "spin", 0.0))
        centre = [(a + b) / 2.0 for a, b in zip(lo, hi, strict=True)]
        origin = (
            self._value(feature, "ox", centre[0]),
            self._value(feature, "oy", centre[1]),
            self._value(feature, "oz", centre[2]),
        )
        frame = Frame.from_axes(origin, third, first)
        low, high = _extent(frame, lo, hi)
        z0 = self._value(feature, "start", low)
        z1 = self._value(feature, "end", high)
        if z1 - z0 < 1e-6:
            raise FeatureError(
                f"{name}: the end trim plane must lie beyond the start trim plane. "
                "Drag a trim plane or change Start and End."
            )
        return picked, indices, issues, frame, z0, z1

    def build(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue], float]:
        """The deformed part, its issues and the largest deviation."""
        name = feature.name
        picked, indices, issues, frame, z0, z1 = self.setup(feature, ctx)
        tolerance = self._value(feature, "tolerance", DEFAULT_TOLERANCE)
        if tolerance <= 0:
            raise FeatureError(
                f"{name}: the tolerance must be above zero. Enter a tolerance such as 0.01 mm."
            )
        try:
            fmap = self.point_map(feature, ctx, frame, z0, z1)
        except ValueError as exc:
            raise FeatureError(f"{name}: {exc}") from exc
        try:
            deformed = deform_shape(picked.shape, fmap, tolerance, z1 - z0, ctx.cancelled)
        except DeformError as exc:
            raise FeatureError(
                f"{name} failed: {exc}. Change the {self.main_value} or the trim planes."
            ) from exc
        if not valid_solid(deformed.shape):
            raise FeatureError(
                f"{name} failed: the result is not a valid solid. Reduce the {self.main_value}, "
                "move the trim planes or raise the tolerance."
            )
        # Faces are matched by kernel identity (IsSame), as Python wrappers differ.
        names = []
        for label, face in picked.faces:
            for original, image in deformed.faces:
                if original.IsSame(face):
                    names.append((label, image))
                    break
        moved = NamedShape(deformed.shape, restrict(names, deformed.shape, feature.id))
        body = ctx.body
        assert body is not None
        result = join([rest_of(body, indices, feature.id), moved], feature.id)
        assert result is not None
        if deformed.deviation > tolerance:
            issues.append(
                Issue(
                    FeatureState.WARNING,
                    f"{name} is approximate: the surfaces are up to {deformed.deviation:.3g} mm "
                    f"from the exact shape (tolerance {tolerance:g} mm). Raise the tolerance or "
                    f"reduce the {self.main_value}.",
                    code="approximate",
                )
            )
        return result, issues, deformed.deviation

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Deform the bodies."""
        body, issues, deviation = self.build(feature, ctx)
        result = FeatureResult(body=body, issues=issues)
        result.extras["report"] = [f"Largest deviation: {deviation:.3g} mm"]
        return result

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The deformed bodies and the two trim planes, for the live preview."""
        picked, _indices, _issues, frame, z0, z1 = self.setup(feature, ctx)
        body, _found, _dev = self.build(feature, ctx)
        planes = trim_planes(picked.shape, frame, z0, z1)
        shape = compound([*solids(body.shape), *planes])
        return NamedShape(shape, list(body.faces))

    def preview_handles(self, feature: Feature, ctx: BuildContext) -> list[PreviewHandle]:
        """Triad arrows that move the origin, and an arrow on each trim plane."""
        _picked, _indices, _issues, frame, z0, z1 = self.setup(feature, ctx)
        o = frame.origin
        handles = []
        for k, (param, direction) in enumerate(
            (("ox", (1.0, 0.0, 0.0)), ("oy", (0.0, 1.0, 0.0)), ("oz", (0.0, 0.0, 1.0)))
        ):
            base = tuple(o[i] - (o[k] if i == k else 0.0) for i in range(3))
            handles.append(PreviewHandle(param, base, direction, o[k]))  # type: ignore[arg-type]
        handles.append(PreviewHandle("start", o, frame.z, z0))
        handles.append(PreviewHandle("end", o, frame.z, z1))
        return handles


def trim_planes(shape: TopoDS_Shape, frame: Frame, z0: float, z1: float) -> list[TopoDS_Shape]:
    """Two square faces at the trim planes, a little larger than the bodies."""
    lo, hi = box_of(shape)
    size = max(math.dist(lo, hi) * 0.6, 1.0)
    out: list[TopoDS_Shape] = []
    o, z = np.asarray(frame.origin), np.asarray(frame.z)
    for d in (z0, z1):
        c = o + z * d
        plane = gp_Pln(gp_Pnt(*map(float, c)), gp_Dir(*map(float, z)))
        out.append(BRepBuilderAPI_MakeFace(plane, -size, size, -size, size).Face())
    return out
