"""Stamp (TR77, D1816): a closed sketch outline pressed into a flat wall.

Type ``stamp``. Params: ``depth`` (length), ``draft`` (angle from square to the
wall, 0 to under 60 degrees, default 0), ``reverse`` (press the other way),
``punch_radius`` (the inside round at the top), ``die_radius`` (the round where the
press leaves the wall) and ``corner_radius`` (the outline's corners rounded in plan),
all optional lengths (TR77, D2309), and ``drawn_cut`` (the top is cut away, a drawn
cut out, TR283, D2311). Each closed outline of the sketch is its own stamp.
Refs: ``sketch`` (one closed outline of lines and arcs drawn on a flat face of a
wall), ``sheet_metal``.

The outline is the stamp's foot. Its top is the outline moved ``depth`` out of the
face and shrunk by ``depth * tan(draft)``; the sheet is lofted between them and the
hollow under it is the same loft one thickness lower (the way the Forming Tool
presses its dimples and ribs, D545), so the sheet keeps its thickness measured
along the press. The stamp is in the folded part only; the flat pattern shows its
outline as marks (titled "Stamp outline"), like Flat Marks (D1112).

Face roles: ``<fid>/stamp/form``.
"""

from __future__ import annotations

import math

from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeWire,
    BRepBuilderAPI_Transform,
    BRepBuilderAPI_WireDone,
)
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeOffset, BRepOffsetAPI_ThruSections
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.GeomAbs import GeomAbs_Arc
from OCP.gp import gp_Trsf, gp_Vec
from OCP.TopAbs import TopAbs_EDGE, TopAbs_VERTEX, TopAbs_WIRE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Shape, TopoDS_Wire

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    register,
)
from fdcad.core.features.curves import sketch_curve_edges
from fdcad.core.features.extrude import sketch_input_raw
from fdcad.core.features.sheetmetal.common import require_sheet, value
from fdcad.core.features.sheetmetal.model import (
    SheetModel,
    SheetResult,
    box,
    cut_all,
    frame,
    volume,
)
from fdcad.core.features.sheetmetal.sketched_bend import wall_of
from fdcad.core.features.solids import transform
from fdcad.core.naming.names import NamedShape, faces_of
from fdcad.core.occ import BRepAlgoAPI_Common
from fdcad.core.units import Kind

TITLE = "Stamp outline"
MAX_DRAFT = math.radians(60)


def _moved(shape: TopoDS_Shape, trsf: gp_Trsf) -> TopoDS_Shape:
    return BRepBuilderAPI_Transform(shape, trsf, True).Shape()


def _outline(owner: str, edges: list[TopoDS_Edge]) -> TopoDS_Wire:
    """The sketch edges joined into one closed wire, in any order they were drawn."""
    if not edges:
        raise FeatureError(f"{owner}: the stamp sketch is empty. Draw one closed outline.")
    maker = BRepBuilderAPI_MakeWire()
    maker.Add(edges[0])
    rest = list(edges[1:])
    while rest:
        for edge in rest:
            maker.Add(edge)
            if maker.IsDone() and maker.Error() == BRepBuilderAPI_WireDone:
                rest.remove(edge)
                break
        else:
            raise FeatureError(
                f"{owner}: a stamp needs one closed outline in its sketch. Draw one closed outline."
            )
    wire = maker.Wire()
    if not wire.Closed():
        raise FeatureError(f"{owner}: the stamp outline is not closed. Close the outline.")
    return wire


def _outlines(owner: str, edges: list[TopoDS_Edge]) -> list[TopoDS_Wire]:
    """The sketch edges joined into closed outlines, one stamp each (TR283, D2311)."""
    from OCP.BRep import BRep_Tool

    if not edges:
        raise FeatureError(f"{owner}: the stamp sketch is empty. Draw one closed outline.")

    def key(p: object) -> tuple[int, int, int]:
        q = BRep_Tool.Pnt_s(p)
        return (round(q.X() * 1e5), round(q.Y() * 1e5), round(q.Z() * 1e5))

    from OCP.TopExp import TopExp

    ends = []
    for edge in edges:
        ends.append((key(TopExp.FirstVertex_s(edge)), key(TopExp.LastVertex_s(edge))))
    left = list(range(len(edges)))
    groups: list[list[TopoDS_Edge]] = []
    while left:
        group = [left.pop(0)]
        points = set(ends[group[0]])
        grew = True
        while grew:
            grew = False
            for i in list(left):
                if ends[i][0] in points or ends[i][1] in points:
                    group.append(i)
                    points.update(ends[i])
                    left.remove(i)
                    grew = True
        groups.append([edges[i] for i in group])
    return [_outline(owner, g) for g in groups]


def _cap(prefix: str, high: TopoDS_Wire, depth: float, t: float) -> NamedShape:
    """The stamp's top as a block to cut away, for a drawn cut out (TR283, D2311)."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace

    drop = gp_Trsf()
    drop.SetTranslation(gp_Vec(0, 0, -t - 1e-3))
    face = BRepBuilderAPI_MakeFace(TopoDS.Wire(_moved(high, drop)), True).Face()
    shape = BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, t + 2.0)).Shape()
    return _named(f"{prefix}/opening", shape)


def _points(shape: TopoDS_Shape) -> list[tuple[float, float, float]]:
    from OCP.BRep import BRep_Tool

    out = []
    explorer = TopExp_Explorer(shape, TopAbs_VERTEX)
    while explorer.More():
        p = BRep_Tool.Pnt_s(TopoDS.Vertex(explorer.Current()))
        out.append((p.X(), p.Y(), p.Z()))
        explorer.Next()
    return out


def _shrunk(owner: str, wire: TopoDS_Wire, inset: float, height: float) -> TopoDS_Wire:
    """``wire`` (flat at z = 0) shrunk by ``inset`` and lifted to ``height``."""
    shape: TopoDS_Shape = wire
    if inset > 1e-9:
        maker = BRepOffsetAPI_MakeOffset(wire, GeomAbs_Arc)
        maker.Perform(-inset)
        if not maker.IsDone():
            raise FeatureError(
                f"{owner}: the stamp's draft closes its top. Reduce the draft or the depth."
            )
        explorer = TopExp_Explorer(maker.Shape(), TopAbs_WIRE)
        wires = []
        while explorer.More():
            wires.append(TopoDS.Wire(explorer.Current()))
            explorer.Next()
        if len(wires) != 1:
            raise FeatureError(
                f"{owner}: the stamp's draft splits or closes its top. "
                "Reduce the draft or the depth."
            )
        shape = wires[0]
    lift = gp_Trsf()
    lift.SetTranslation(gp_Vec(0, 0, height))
    return TopoDS.Wire(_moved(shape, lift))


def _loft(owner: str, low: TopoDS_Wire, high: TopoDS_Wire) -> TopoDS_Shape:
    maker = BRepOffsetAPI_ThruSections(True, True)
    maker.AddWire(low)
    maker.AddWire(high)
    maker.Build()
    if not maker.IsDone():
        raise FeatureError(f"{owner}: the stamp could not be made. Change its depth or draft.")
    return maker.Shape()


def _named(prefix: str, shape: TopoDS_Shape) -> NamedShape:
    return NamedShape(shape, [(f"{prefix}/form", f) for f in faces_of(shape)])


def _offset(owner: str, wire: TopoDS_Wire, by: float) -> TopoDS_Wire:
    maker = BRepOffsetAPI_MakeOffset(wire, GeomAbs_Arc)
    maker.Perform(by)
    explorer = TopExp_Explorer(maker.Shape(), TopAbs_WIRE) if maker.IsDone() else None
    wires = []
    while explorer is not None and explorer.More():
        wires.append(TopoDS.Wire(explorer.Current()))
        explorer.Next()
    if len(wires) != 1:
        raise FeatureError(
            f"{owner}: the corner radius is too large for the stamp outline. "
            "Enter a smaller corner radius."
        )
    return wires[0]


def _round_corners(owner: str, wire: TopoDS_Wire, radius: float) -> TopoDS_Wire:
    """The outline with every corner rounded in plan (TR77, D2309): in and out by the
    radius rounds the outward corners, out and in rounds the inward ones."""
    inward = _offset(owner, _offset(owner, wire, -radius), radius)
    return _offset(owner, _offset(owner, inward, radius), -radius)


def _rounded(
    owner: str, solid: TopoDS_Shape, foot: float, top: float, punch: float, die: float
) -> TopoDS_Shape:
    """The press solid with its top edges rounded by ``punch`` and a flare of radius
    ``die`` where it leaves the wall at height ``foot`` (TR77, D2309)."""
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet

    from fdcad.core.features.modify import edge_faces, edges_of
    from fdcad.core.naming.names import centroid
    from fdcad.core.occ import BRepAlgoAPI_Fuse

    failed = (
        f"{owner}: the stamp radii do not fit its size. "
        "Enter smaller punch, die or corner radii, or a larger depth."
    )

    def flat_at(shape: TopoDS_Shape, z: float) -> list[object]:
        return [f for f in faces_of(shape) if abs(centroid(f)[2] - z) < 1e-6]

    try:
        shape = solid
        if punch > 1e-9:
            caps = flat_at(shape, top)
            if len(caps) != 1:
                raise ValueError("no flat top")
            maker = BRepFilletAPI_MakeFillet(shape)
            for edge in edges_of(caps[0]):
                maker.Add(punch, edge)
            maker.Build()
            if not maker.IsDone():
                raise ValueError("punch")
            shape = maker.Shape()
        if die > 1e-9:
            from OCP.Bnd import Bnd_Box
            from OCP.BRepBndLib import BRepBndLib

            bb = Bnd_Box()
            BRepBndLib.Add_s(shape, bb)
            lo, hi = bb.CornerMin(), bb.CornerMax()
            m = 2 * die + 1.0
            slab = box("slab", (lo.X() - m, lo.Y() - m, foot - die - 1.0),
                       (hi.X() + m, hi.Y() + m, foot)).shape  # fmt: skip
            fuse = BRepAlgoAPI_Fuse(shape, slab)
            fuse.Build()
            if not fuse.IsDone():
                raise ValueError("die")
            joined = fuse.Shape()
            decks = flat_at(joined, foot)
            maker = BRepFilletAPI_MakeFillet(joined)
            count = 0
            for deck in decks:
                for edge in edges_of(deck):
                    others = [o for o in edge_faces(joined, edge) if not o.IsSame(deck)]
                    if others and centroid(others[0])[2] > foot + 1e-6:
                        maker.Add(die, edge)
                        count += 1
            if not count:
                raise ValueError("no foot")
            maker.Build()
            if not maker.IsDone():
                raise ValueError("die")
            keep = box("keep", (lo.X() - m, lo.Y() - m, foot), (hi.X() + m, hi.Y() + m, top + 1.0))
            common = BRepAlgoAPI_Common(maker.Shape(), keep.shape)
            common.Build()
            if not common.IsDone():
                raise ValueError("die")
            shape = common.Shape()
    except Exception as exc:  # kernel failure: tell the user what to change
        raise FeatureError(failed) from exc
    return shape


@register
class Stamp(FeatureType):
    """Presses a sketched outline into a flat wall."""

    type_name = "stamp"
    makes_solid = True
    params = (
        ParamSpec("depth", kind=Kind.LENGTH),
        ParamSpec("draft", kind=Kind.ANGLE, optional=True),
        ParamSpec("reverse", default=False, optional=True),
        # TR77 (D2309): rounds of the press.
        ParamSpec("punch_radius", kind=Kind.LENGTH, optional=True),
        ParamSpec("die_radius", kind=Kind.LENGTH, optional=True),
        ParamSpec("corner_radius", kind=Kind.LENGTH, optional=True),
        ParamSpec("drawn_cut", default=False, optional=True),  # TR283 (D2311)
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Press the stamp and rebuild the sheet."""
        model = self.model(feature, ctx)
        return SheetResult(body=model.build(feature.id, feature.name), sheet=model)

    def model(self, feature: Feature, ctx: BuildContext) -> SheetModel:
        """The sheet with the stamp pressed in and its outline marked."""
        name, fid = feature.name, feature.id
        model = require_sheet(feature, ctx)
        depth = value(feature, "depth", 0.0)
        draft = value(feature, "draft", 0.0)
        if depth <= 0:
            raise FeatureError(f"{name}: the stamp depth must be greater than zero. Enter a depth.")
        if not 0 <= draft < MAX_DRAFT:
            raise FeatureError(
                f"{name}: the stamp draft must be from 0 to under 60 degrees. "
                "Enter a smaller draft."
            )
        sketch = sketch_input_raw(feature, ctx)
        punch, die, corner = (
            value(feature, key, 0.0) for key in ("punch_radius", "die_radius", "corner_radius")
        )
        if min(punch, die, corner) < 0:
            raise FeatureError(f"{name}: a stamp radius cannot be negative. Enter zero or more.")
        worlds = _outlines(name, sketch_curve_edges(sketch, name))
        for k, world in enumerate(worlds, start=1):  # several outlines (TR283, D2311)
            prefix = f"{fid}/stamp" if k == 1 else f"{fid}/stamp{k}"
            self._press(feature, model, world, prefix, (depth, draft, punch, die, corner))
        return model

    def _press(
        self,
        feature: Feature,
        model: SheetModel,
        world: TopoDS_Wire,
        prefix: str,
        sizes: tuple[float, float, float, float, float],
    ) -> None:
        """Press one closed outline into its wall."""
        name, t = feature.name, model.thickness
        depth, draft, punch, die, corner = sizes
        pts = _points(world)
        if len(pts) < 2:
            raise FeatureError(f"{name}: the stamp outline is too small. Draw a larger outline.")
        wid, _a, _b, top = wall_of(model, pts[0], pts[1], name)
        inv = model.placements(False)[wid].Inverted()
        out = 1 if top else -1
        if feature.params.get("reverse") is True:
            out = -out
        z0 = t if out > 0 else 0.0
        place = frame((0.0, 0.0, z0), (1.0, 0.0, 0.0), (0.0, 0.0, float(out)))
        canonical = TopoDS.Wire(_moved(_moved(world, inv), place.Inverted()))
        if corner > 1e-9:  # TR77 (D2309): round the outline's corners in plan
            canonical = _round_corners(name, canonical, corner)
        inset = depth * math.tan(draft)
        low = canonical
        high = _shrunk(name, canonical, inset, depth)
        drop = gp_Trsf()
        drop.SetTranslation(gp_Vec(0, 0, -t))
        low2, high2 = TopoDS.Wire(_moved(low, drop)), TopoDS.Wire(_moved(high, drop))
        outer_solid, hollow_solid = _loft(name, low, high), _loft(name, low2, high2)
        if punch > 1e-9 or die > 1e-9:  # TR77 (D2309)
            outer_solid = _rounded(name, outer_solid, 0.0, depth, punch + t, die)
            hollow_solid = _rounded(name, hollow_solid, -t, depth - t, punch, die + t)
        outer = _named(prefix, outer_solid)
        hollow = _named(prefix, hollow_solid)
        shell = cut_all(outer, [hollow], prefix)
        if feature.params.get("drawn_cut") is True:  # TR283 (D2311): open the top
            shell = cut_all(shell, [_cap(prefix, high, depth, t)], prefix)
        self._check_room(model, wid, transform(outer, place), t, name)
        wall = model.walls[wid]
        wall.adds.append(transform(shell, place))
        wall.folded_cuts.append(transform(hollow, place))
        explorer = TopExp_Explorer(_moved(world, inv), TopAbs_EDGE)
        while explorer.More():
            ends = _points(explorer.Current())
            if len(ends) >= 2:
                p, q = ends[0], ends[-1]
                model.marks.append((wid, (p[0], p[1]), (q[0], q[1]), TITLE))
            explorer.Next()

    @staticmethod
    def _check_room(model: SheetModel, wid: str, foot: NamedShape, t: float, name: str) -> None:
        """The stamp's foot must lie on the flat wall."""
        from OCP.Bnd import Bnd_Box
        from OCP.BRepBndLib import BRepBndLib

        bb = Bnd_Box()
        BRepBndLib.Add_s(foot.shape, bb)
        lo, hi = bb.CornerMin(), bb.CornerMax()
        zone = box("zone", (lo.X(), lo.Y(), 0.0), (hi.X(), hi.Y(), t))
        common = BRepAlgoAPI_Common(model.piece(wid).shape, zone.shape)
        if not common.IsDone() or volume(common.Shape()) < volume(zone.shape) * (1 - 1e-6):
            raise FeatureError(
                f"{name}: the stamp runs off its wall or too near a bend or hole. "
                "Move it or make it smaller."
            )
