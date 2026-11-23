"""Forming Tool (PHASE5_SPEC P5.6, DECISIONS D545): built in pressed forms made by parameters.

Type ``form_tool``. Params:
- ``tool``: "dimple" (default), "louvre" or "rib".
- ``diameter`` (dimple), ``length`` (louvre), ``width`` (louvre and rib), ``height``.
- ``reverse``: press the form the other way.
- ``rib_ends``: "round" (default) or "square" ends of a rib (TR283, D2311).
- ``tool`` "custom" (TR279, D2313): the shape of a tool body of the part, with
  ``refs.tool_face`` (its stop face), ``refs.remove_faces``, ``refs.insert``,
  ``tool_angle`` and ``mirror``; see ``custom_form``.

Refs: ``sketch`` (lines on flat faces of walls: each places one form, centred on
the line and turned along it; a rib runs from end to end), ``sheet_metal``.

The forms are in the folded part only. In the flat pattern a louvre leaves its
lance, a 0.02 mm slit; dimples and ribs leave nothing.

Face roles: ``<fid>/form<k>/<role>``, ``<fid>/lance<k>/<role>``.
"""

from __future__ import annotations

import math

from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakePolygon,
    BRepBuilderAPI_MakeWire,
)
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
from OCP.TopoDS import TopoDS_Wire

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureState,
    FeatureType,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.features.extrude import sketch_input_raw
from fdcad.core.features.sheetmetal.common import require_sheet, value
from fdcad.core.features.sheetmetal.model import (
    SheetModel,
    SheetResult,
    box,
    cut_all,
    frame,
    fuse_all,
    unit2,
    volume,
)
from fdcad.core.features.sheetmetal.params import TEAR_WIDTH
from fdcad.core.features.sheetmetal.sketched_bend import wall_of
from fdcad.core.features.solids import transform
from fdcad.core.naming.names import NamedShape, faces_of
from fdcad.core.occ import BRepAlgoAPI_Common
from fdcad.core.sketch.model import Line
from fdcad.core.units import Kind

TOOLS = ("dimple", "louvre", "rib", "custom")  # custom: TR279 (D2313)
_TOL = 1e-6


def _named(prefix: str, shape: object) -> NamedShape:
    return NamedShape(shape, [(f"{prefix}/form", f) for f in faces_of(shape)])


def _circle(r: float, z: float) -> TopoDS_Wire:
    edge = BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(0, 0, z), gp_Dir(0, 0, 1)), r)).Edge()
    return BRepBuilderAPI_MakeWire(edge).Wire()


def _stadium(length: float, width: float, z: float) -> TopoDS_Wire:
    """A slot outline along x, ``length`` end to end and ``width`` across."""
    r = width / 2
    half = length / 2 - r
    maker = BRepBuilderAPI_MakeWire()
    maker.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(-half, -r, z), gp_Pnt(half, -r, z)).Edge())
    right = gp_Circ(gp_Ax2(gp_Pnt(half, 0, z), gp_Dir(0, 0, 1)), r)
    maker.Add(BRepBuilderAPI_MakeEdge(right, gp_Pnt(half, -r, z), gp_Pnt(half, r, z)).Edge())
    maker.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(half, r, z), gp_Pnt(-half, r, z)).Edge())
    left = gp_Circ(gp_Ax2(gp_Pnt(-half, 0, z), gp_Dir(0, 0, 1)), r)
    maker.Add(BRepBuilderAPI_MakeEdge(left, gp_Pnt(-half, r, z), gp_Pnt(-half, -r, z)).Edge())
    return maker.Wire()


def _rectangle(length: float, width: float, z: float) -> TopoDS_Wire:
    """A rectangle along x, for a rib with square ends (TR283, D2311)."""
    poly = BRepBuilderAPI_MakePolygon()
    hl, hw = length / 2, width / 2
    for x, y in ((-hl, -hw), (hl, -hw), (hl, hw), (-hl, hw)):
        poly.Add(gp_Pnt(x, y, z))
    poly.Close()
    return poly.Wire()


def _loft(low: TopoDS_Wire, high: TopoDS_Wire) -> object:
    maker = BRepOffsetAPI_ThruSections(True, True)
    maker.AddWire(low)
    maker.AddWire(high)
    maker.Build()
    if not maker.IsDone():
        raise FeatureError("The form could not be made. Change its sizes slightly.")
    return maker.Shape()


def _prism_yz(points: list[tuple[float, float]], x0: float, x1: float) -> object:
    """A prism along x from ``x0`` to ``x1`` of a polygon given in (y, z)."""
    poly = BRepBuilderAPI_MakePolygon()
    for y, z in points:
        poly.Add(gp_Pnt(x0, y, z))
    poly.Close()
    face = BRepBuilderAPI_MakeFace(poly.Wire(), True).Face()
    return BRepPrimAPI_MakePrism(face, gp_Vec(x1 - x0, 0, 0)).Shape()


def pressing(
    prefix: str, outline: str, size: tuple[float, float], height: float, thickness: float
) -> tuple[NamedShape, NamedShape]:
    """A hollow pressing in the form frame (sheet between z = -thickness and 0): the
    shell to add and the hollow to cut, with 45 degree sides (D545)."""
    length, width = size
    if outline == "circle":
        if width - 2 * height <= _TOL:
            raise FeatureError(
                f"{prefix}: the dimple is too high for its diameter. "
                "Reduce the height or increase the diameter."
            )
        low, high = _circle(width / 2, 0.0), _circle(width / 2 - height, height)
        low2, high2 = (
            _circle(width / 2, -thickness),
            _circle(width / 2 - height, height - thickness),
        )
    else:
        if width - 2 * height <= _TOL or length - width <= _TOL:
            raise FeatureError(
                f"{prefix}: the rib is too high for its width, or shorter than it is wide. "
                "Reduce the height or make the rib longer."
            )
        shape = _rectangle if outline == "rectangle" else _stadium
        low = shape(length, width, 0.0)
        high = shape(length - 2 * height, width - 2 * height, height)
        low2 = shape(length, width, -thickness)
        high2 = shape(length - 2 * height, width - 2 * height, height - thickness)
    outer = _named(prefix, _loft(low, high))
    hollow = _named(prefix, _loft(low2, high2))
    return cut_all(outer, [hollow], prefix), hollow


def louvre(
    prefix: str, length: float, width: float, height: float, thickness: float
) -> tuple[NamedShape, NamedShape]:
    """The hood (with its closed sides) to add and the opening to cut, in the form frame."""
    t, hl, hw = thickness, length / 2, width / 2
    hood = _prism_yz([(-hw, -t), (-hw, 0.0), (hw, height), (hw, height - t)], -hl, hl)
    cheek = [(-hw, -t), (hw, -t), (hw, height)]
    sides = [_prism_yz(cheek, -hl, -hl + t), _prism_yz(cheek, hl - t, hl)]
    parts = [_named(prefix, hood), *(_named(prefix, s) for s in sides)]
    opening = box(prefix, (-hl, -hw, -t - 1.0), (hl, hw, 1.0))
    return fuse_all(prefix, prefix, parts), opening


@register
class FormTool(FeatureType):
    """Presses dimples, louvres or ribs into flat walls."""

    type_name = "form_tool"
    makes_solid = True
    params = (
        ParamSpec("tool", choices=TOOLS, optional=True),
        ParamSpec("diameter", kind=Kind.LENGTH, optional=True),
        ParamSpec("length", kind=Kind.LENGTH, optional=True),
        ParamSpec("width", kind=Kind.LENGTH, optional=True),
        ParamSpec("height", kind=Kind.LENGTH, optional=True),
        ParamSpec("reverse", default=False, optional=True),
        ParamSpec("rib_ends", choices=("round", "square"), optional=True),  # D2311
        ParamSpec("tool_angle", kind=Kind.ANGLE, optional=True),  # TR279 (D2313)
        ParamSpec("mirror", default=False, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Add the forms and rebuild the sheet."""
        model = self.model(feature, ctx)
        issues: list[Issue] = []
        sketch = sketch_input_raw(feature, ctx)
        curves = sketch.model.curves()
        others = sum(1 for c in curves if not isinstance(c, Line))
        if others:
            # Only lines place forms; say what was left out (audit A item 7, D727).
            issues.append(
                Issue(
                    FeatureState.WARNING,
                    f"{feature.name} places a form on each line only, so {others} other "
                    f"curve{'s' if others != 1 else ''} in the sketch "
                    f"{'were' if others != 1 else 'was'} left out. Draw a line for each form.",
                    code="form_curves_left_out",
                )
            )
        return SheetResult(body=model.build(feature.id, feature.name), issues=issues, sheet=model)

    def model(self, feature: Feature, ctx: BuildContext) -> SheetModel:
        """The sheet with the forms pressed in."""
        name, fid = feature.name, feature.id
        model = require_sheet(feature, ctx)
        t = model.thickness
        tool = str(feature.params.get("tool", "dimple"))
        height = value(feature, "height", 0.0)
        custom = None
        if tool == "custom":  # TR279 (D2313): the shape of a tool body
            from fdcad.core.features.sheetmetal.custom_form import custom_tool

            custom = custom_tool(
                feature, ctx, value(feature, "tool_angle", 0.0),
                feature.params.get("mirror") is True,
            )  # fmt: skip
            height = 1.0  # not used
        if height <= 0:
            raise FeatureError(
                f"{name}: the form height must be greater than zero. Enter a larger height."
            )
        sketch = sketch_input_raw(feature, ctx)
        curves = sketch.model.curves()
        lines = [c for c in curves if isinstance(c, Line)]
        if not lines:
            # Points alone gave the same short message (audit B item 27, D740).
            raise FeatureError(
                f"{name}: forms are placed by sketch lines, not points. "
                "Draw a line on a flat face for each form."
            )

        for k, line in enumerate(lines, start=1):
            ends = []
            for pid in (line.p1, line.p2):
                p = sketch.plane.to_3d(*sketch.model.xy(pid))
                ends.append((p.X(), p.Y(), p.Z()))
            wid, a, b, top = wall_of(model, ends[0], ends[1], name)
            d = unit2((b[0] - a[0], b[1] - a[1]))
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            out = 1 if top else -1
            if feature.params.get("reverse") is True:
                out = -out
            z0 = t if out > 0 else 0.0
            place = frame((mid[0], mid[1], z0), (d[0], d[1], 0.0), (0.0, 0.0, float(out)))
            prefix = f"{fid}/form{k}"
            lance: NamedShape | None = None
            if custom is not None:
                from fdcad.core.features.sheetmetal.custom_form import foot_box, named

                shape, holes = custom
                outer = named(prefix, shape)
                drop = gp_Trsf()
                drop.SetTranslation(gp_Vec(0, 0, -t))
                hollow = transform(outer, drop)
                shell = cut_all(outer, [hollow], prefix)
                if holes:
                    shell = cut_all(shell, [named(f"{prefix}/hole", h) for h in holes], prefix)
                x0, y0, x1, y1 = foot_box(shape)
                self._check_room(model, wid, place, (x1 - x0, y1 - y0), t, name, k,
                                 ((x0 + x1) / 2, (y0 + y1) / 2))  # fmt: skip
                wall = model.walls[wid]
                wall.adds.append(transform(shell, place))
                wall.folded_cuts.append(transform(hollow, place))
                continue
            if tool == "dimple":
                diameter = value(feature, "diameter", 0.0)
                foot = (diameter, diameter)
                shell, hollow = pressing(prefix, "circle", foot, height, t)
            elif tool == "rib":
                foot = (math.dist(a, b), value(feature, "width", 0.0))
                kind = "rectangle" if feature.params.get("rib_ends") == "square" else "stadium"
                shell, hollow = pressing(prefix, kind, foot, height, t)
            else:
                length, width = value(feature, "length", 0.0), value(feature, "width", 0.0)
                if length <= 2 * t or width <= 0:
                    raise FeatureError(
                        f"{name}: the louvre needs a length above twice the thickness "
                        "and a width. Increase the length or the width."
                    )
                shell, hollow = louvre(prefix, length, width, height, t)
                foot = (length, width)
                half = TEAR_WIDTH / 2
                lance = box(
                    f"{fid}/lance{k}",
                    (-length / 2, width / 2 - half, -t - 1.0),
                    (length / 2, width / 2 + half, 1.0),
                )
            self._check_room(model, wid, place, foot, t, name, k)
            wall = model.walls[wid]
            wall.adds.append(transform(shell, place))
            wall.folded_cuts.append(transform(hollow, place))
            if lance is not None:
                wall.cuts.append(transform(lance, place))
        return model

    @staticmethod
    def _check_room(
        model: SheetModel,
        wid: str,
        place: object,
        foot: tuple[float, float],
        t: float,
        name: str,
        k: int,
        centre: tuple[float, float] = (0.0, 0.0),
    ) -> None:
        """The form and a margin of the thickness must lie on the flat wall."""
        length, width = foot
        if length <= 0 or width <= 0:
            raise FeatureError(f"{name}: enter the form sizes.")
        cx, cy = centre
        zone = box(
            "zone",
            (cx - length / 2 - t, cy - width / 2 - t, -t),
            (cx + length / 2 + t, cy + width / 2 + t, 0),
        )
        local = transform(zone, place)
        common = BRepAlgoAPI_Common(model.piece(wid).shape, local.shape)
        if not common.IsDone() or volume(common.Shape()) < volume(local.shape) * (1 - 1e-6):
            raise FeatureError(
                f"{name}: form {k} runs off its wall or too near a bend or hole. "
                "Move it or make it smaller."
            )
