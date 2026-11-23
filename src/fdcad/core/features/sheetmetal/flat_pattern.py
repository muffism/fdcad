"""Flat Pattern (PHASE5_SPEC P5.5): the sheet laid flat, always last in the tree.

Type ``flatten``. While ``flattened`` is off the part passes through folded.
While it is on, the part is shown flat, with bend lines; features below it
then apply to the flat state only (D339).

Params (all optional, false when missing): ``flattened``, ``bend_lines`` and
``bounding_box``. New Flat Patterns get the last two turned on. ``bend_notches``
("none", "triangle", "circle" or "rectangle") and ``notch_size`` (length, the
thickness when missing) cut a notch at both ends of every bend line in the flat
pattern only (TR169, D1104). ``merge_faces`` (true when missing) joins the faces of
walls and bends; ``corner_trim`` cuts the square where two bend strips meet at a corner
from the flat (TR76, D1105). Refs: ``grain``, an edge whose direction sets the
orientation of the bounding box; ``leave_out``, faces whose walls (and the walls bent
from them) are left out of the flat (TR76, D1105). ``sheet_length`` and ``sheet_width``
(lengths): a warning when the flat does not fit that sheet (TR174 item 7, D1107). The
result's ``extras`` hold the quoting values of ``quote`` (TR172, D1106). ``bend_order``
(text, bend numbers in bending order) numbers the bends in the files (TR282, D1110).
``fold_percent`` (0 to 100) shows the folded part with every bend at that share of its
angle while ``flattened`` is off (TR283 item 2, D1112).

Features that add no solid (planes, axes, points, sketches, curves) never block.
Other features after the last sheet metal feature (one that keeps the sheet model,
D546) that only remove material from flat walls (cuts, holes, fillets) are taken into
the flat pattern, cut from each wall in its own frame. Any other change (added
material, or a cut that reaches a bend or a form) blocks flattening: the message
names that feature (P5.5 item 7). A flat pattern that overlaps itself gives a
warning naming the feature that causes it, with its faces highlighted.

Face roles: the flat part keeps the names of the folded part.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureState,
    FeatureType,
    Issue,
    ParamSpec,
    Vec3,
    register,
)
from fdcad.core.features.lookup import resolve_edge
from fdcad.core.features.sheetmetal.common import latest_sheet, no_sheet_message
from fdcad.core.features.sheetmetal.model import Bend, SheetModel, SheetResult, apply, volume
from fdcad.core.features.solids import compound, line_ends, transform
from fdcad.core.naming.names import NamedShape, faces_of
from fdcad.core.occ import BRepAlgoAPI_Common, BRepAlgoAPI_Cut
from fdcad.core.units import Kind

TYPE = "flatten"
#: Bend notch shapes (TR169, D1104).
NOTCHES = ("none", "triangle", "circle", "rectangle")
_OVERLAP = 1e-6  # cubic mm


@dataclass
class FlatResult(FeatureResult):
    """Result of the Flat Pattern feature, for the panel, the view and the exporters."""

    flat: NamedShape | None = None
    sheet: SheetModel | None = None
    lines: list[tuple[Vec3, Vec3, Bend]] = field(default_factory=list)
    size: tuple[float, float] | None = None  # length along the grain, width across
    grain_angle: float = 0.0  # radians, in the root wall's frame
    bend_edges: TopoDS_Shape | None = None  # bend lines for the view, when shown
    #: Cross break lines on the flat pattern (D539), and their edges for the view.
    marks: list[tuple[Vec3, Vec3, str]] = field(default_factory=list)
    mark_edges: TopoDS_Shape | None = None
    #: Bend id to its step in the bending order (TR282, D1110); empty without an order.
    order: dict[str, int] = field(default_factory=dict)


def overlaps(model: SheetModel) -> list[str]:
    """Owner feature ids of flat pieces that overlap an earlier piece."""
    pieces = model.pieces(True)
    boxes = []
    for _owner, piece in pieces:
        box = Bnd_Box()
        BRepBndLib.Add_s(piece.shape, box)
        box.Enlarge(-1e-4)
        boxes.append(box)
    out: list[str] = []
    for j in range(len(pieces)):
        for i in range(j):
            if boxes[i].IsOut(boxes[j]):
                continue
            common = BRepAlgoAPI_Common(pieces[i][1].shape, pieces[j][1].shape)
            if common.IsDone() and volume(common.Shape()) > _OVERLAP:
                owner = pieces[j][0]
                if owner not in out:
                    out.append(owner)
    return out


def flat_size(model: SheetModel, flat: NamedShape, angle: float) -> tuple[float, float]:
    """Length and width of the flat part's box, with the length along ``angle``."""
    turn = gp_Trsf()
    turn.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), -angle)
    local = turn.Multiplied(model.frame.Inverted())
    moved = transform(flat, local)
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(moved.shape, box, False, False)
    lo, hi = box.CornerMin(), box.CornerMax()
    return hi.X() - lo.X(), hi.Y() - lo.Y()


def _take_in_cuts(
    last: SheetResult, body: NamedShape | None, feature: Feature, blocker: str
) -> tuple[SheetModel | None, str]:
    """The sheet model with the material that later features removed from its walls.

    Cuts, holes and other features that only take material out of flat walls flatten
    exactly, so they do not block the Flat Pattern. Returns None and the message to
    show when the part changed in another way (added material, or a cut that reaches
    a bend or a form).
    """
    name = feature.name
    added_message = (
        f"{name}: {blocker} is not a sheet metal feature, so the part cannot be "
        f"flattened. Suppress or delete {blocker} to flatten."
    )
    if body is None or last.body is None or last.sheet is None:
        return None, added_message
    before, after = last.body.shape, body.shape
    added = BRepAlgoAPI_Cut(after, before)
    if not added.IsDone() or volume(added.Shape()) > _OVERLAP:
        return None, added_message
    bend_message = (
        f"{name}: {blocker} removes material from a bend or a form, so the part cannot be "
        f"flattened. Make cuts across bends between an Unfold and a Fold, or suppress "
        f"{blocker} to flatten."
    )
    gone = BRepAlgoAPI_Cut(before, after)
    if not gone.IsDone():
        return None, bend_message
    removed = NamedShape(gone.Shape(), [(f"{feature.id}/cut", f) for f in faces_of(gone.Shape())])
    model = last.sheet.copy()
    places = model.placements(False)
    try:
        for wid, wall in model.walls.items():
            if wid not in places:
                continue
            local = transform(removed, places[wid].Inverted())
            common = BRepAlgoAPI_Common(model.piece(wid).shape, local.shape)
            if common.IsDone() and volume(common.Shape()) > _OVERLAP:
                wall.cuts.append(local)
        folded = model.build(feature.id, name)
    except FeatureError:
        return None, bend_message
    want = volume(after)
    if abs(volume(folded.shape) - want) > max(_OVERLAP, 1e-7 * want):
        return None, bend_message
    return model, ""


def notch_outline(kind: str, p: Vec3, out: Vec3, size: float) -> list[tuple[float, float]]:
    """A notch's corners (triangle or rectangle) round bend end ``p``, in the root frame.

    ``out`` points along the bend line out of the sheet. The notch reaches ``size`` into
    the sheet and is ``size`` wide at the bend end (TR169, D1104)."""
    n = (-out[1], out[0])

    def at(a: float, b: float) -> tuple[float, float]:
        return (p[0] + out[0] * a + n[0] * b, p[1] + out[1] * a + n[1] * b)

    if kind == "triangle":
        return [at(-size, 0.0), at(size, size), at(size, -size)]
    half = size / 2
    return [at(-size, -half), at(size, -half), at(size, half), at(-size, half)]


def _notched(feature: Feature, model: SheetModel, flat: NamedShape) -> NamedShape:
    """``flat`` with a notch at both ends of every bend line (TR169, D1104)."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
    from OCP.gp import gp_Ax2, gp_Vec

    from fdcad.core.features.sheetmetal.model import cut_all

    kind = str(feature.params.get("bend_notches", "none"))
    if kind == "none":
        return flat
    t = model.thickness
    size_param = feature.params.get("notch_size")
    size = float(size_param.value) if isinstance(size_param, Param) else t
    if size <= 0:
        raise FeatureError(
            f"{feature.name}: the notch size must be greater than zero. Enter a size."
        )
    to_local = model.frame.Inverted()
    tools: list[NamedShape] = []
    for k, (a, b, _bend) in enumerate(model.bend_lines(), start=1):
        la, lb = apply(to_local, a), apply(to_local, b)
        d = (lb[0] - la[0], lb[1] - la[1], 0.0)
        length = math.hypot(d[0], d[1])
        if length < 1e-9:
            continue
        d = (d[0] / length, d[1] / length, 0.0)
        for end, out in ((la, (-d[0], -d[1], 0.0)), (lb, d)):
            if kind == "circle":
                axis = gp_Ax2(gp_Pnt(end[0], end[1], -1.0), gp_Dir(0, 0, 1))
                shape = BRepPrimAPI_MakeCylinder(axis, size / 2, t + 2.0).Shape()
            else:
                poly = BRepBuilderAPI_MakePolygon()
                for x, y in notch_outline(kind, end, out, size):
                    poly.Add(gp_Pnt(x, y, -1.0))
                poly.Close()
                face = BRepBuilderAPI_MakeFace(poly.Wire(), True).Face()
                shape = BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, t + 2.0)).Shape()
            named = NamedShape(shape, [(f"{feature.id}/notch{k}", f) for f in faces_of(shape)])
            tools.append(transform(named, model.frame))
    return cut_all(flat, tools, feature.id) if tools else flat


def _progress(feature: Feature, model: SheetModel, name: str) -> NamedShape | None:
    """The part with every bend at ``fold_percent`` of its angle (Fold Progress, TR283
    item 2, D1112), or None at 100 percent or without the param."""
    from dataclasses import replace

    pct = feature.params.get("fold_percent")
    if not isinstance(pct, Param) or pct.value >= 100 - 1e-9:
        return None
    if pct.value < 0:
        raise FeatureError(f"{name}: the fold progress must be from 0 to 100. Enter a percent.")
    part = model.copy()
    if pct.value <= 1e-9:
        return part.build(feature.id, name, flat=True)
    for bid, bend in part.bends.items():
        part.bends[bid] = replace(bend, angle=bend.angle * pct.value / 100)
    part.part_cuts, part.part_adds = [], []  # gusset shapes fit the full bend only
    return part.build(feature.id, name)


def _sheet_size_issue(feature: Feature, size: tuple[float, float], issues: list[Issue]) -> None:
    """A warning when the flat pattern does not fit the typed sheet size, either way round
    (TR174 item 7, D1107)."""
    length, width = feature.params.get("sheet_length"), feature.params.get("sheet_width")
    if not isinstance(length, Param) or not isinstance(width, Param):
        return
    stock = sorted((float(length.value), float(width.value)))
    need = sorted(size)
    if need[0] <= stock[0] + 1e-6 and need[1] <= stock[1] + 1e-6:
        return
    issues.append(
        Issue(
            FeatureState.WARNING,
            f"{feature.name}: the flat pattern ({size[0]:.1f} x {size[1]:.1f} mm) is larger than "
            f"the sheet ({stock[1]:g} x {stock[0]:g} mm). Use a larger sheet or make the part "
            "smaller.",
            code="flat_too_large",
        )
    )


def _options(feature: Feature, ctx: BuildContext, model: SheetModel) -> SheetModel:
    """The sheet with the flat options applied: walls left out and corner trims (TR76,
    D1105). Returns ``model`` itself when no option is set."""
    leave = feature.refs.get("leave_out")
    trim = feature.params.get("corner_trim") is True
    if not trim and not (isinstance(leave, list) and leave):
        return model
    model = model.copy()
    if isinstance(leave, list) and leave:
        _leave_out(feature, ctx, model, leave)
    if trim:
        from fdcad.core.features.sheetmetal.corner_relief import corner_trim, sheet_corners

        for k, corner in enumerate(sheet_corners(model), start=1):
            model.flat_cuts.append(
                (corner.wall, corner_trim(f"{feature.id}/trim{k}", corner, model))
            )
    return model


def _leave_out(feature: Feature, ctx: BuildContext, model: SheetModel, refs: list[object]) -> None:
    """Drop the walls that hold the picked faces, and the walls bent from them."""
    from fdcad.core.features.lookup import resolve_face

    name = feature.name
    gone: set[str] = set()
    for ref in refs:
        if not isinstance(ref, dict) or ctx.body is None:
            raise FeatureError(f"{name}: a face pick is damaged. Pick the faces again.")
        face, _found = resolve_face(ctx.body, ref, name)
        label = next((n for n, f in ctx.body.faces if f.IsSame(face)), "")
        owner = label.rsplit("/", 1)[0]
        if owner in model.bends:
            owner = model.bends[owner].child
        elif owner not in model.walls:
            from fdcad.core.features.sheetmetal.locate import wall_face

            try:
                owner = wall_face(model, face, name).wid
            except FeatureError:
                raise FeatureError(
                    f"{name}: a face to leave out is not on a wall or bend. "
                    "Pick a face of a flange."
                ) from None
        if owner == model.root:
            raise FeatureError(
                f"{name}: the first wall cannot be left out of the flat pattern. "
                "Pick a face of a flange."
            )
        gone.add(owner)
    todo = list(gone)
    while todo:
        wid = todo.pop()
        for bend in model.children(wid):
            if bend.child not in gone:
                gone.add(bend.child)
                todo.append(bend.child)
    for wid in gone:
        model.walls.pop(wid, None)
    for bid in [b.bid for b in model.bends.values() if b.child in gone or b.parent in gone]:
        model.bends.pop(bid)
    model.flat_cuts = [(w, c) for w, c in model.flat_cuts if w not in gone]
    model.marks = [m for m in model.marks if m[0] not in gone]


def _name(doc: Document, fid: str) -> str:
    try:
        return doc.feature(fid).name
    except KeyError:
        return fid


@register
class FlatPattern(FeatureType):
    """Shows the sheet folded or flat."""

    type_name = TYPE
    makes_solid = True
    params = (
        ParamSpec("flattened", default=False, optional=True),
        ParamSpec("bend_lines", default=False, optional=True),
        ParamSpec("bounding_box", default=False, optional=True),
        ParamSpec("bend_notches", choices=NOTCHES, default="none", optional=True),
        ParamSpec("notch_size", kind=Kind.LENGTH, optional=True),
        ParamSpec("merge_faces", default=True, optional=True),
        ParamSpec("corner_trim", default=False, optional=True),
        ParamSpec("sheet_length", kind=Kind.LENGTH, optional=True),
        ParamSpec("sheet_width", kind=Kind.LENGTH, optional=True),
        ParamSpec("bend_order", optional=True),
        ParamSpec("fold_percent", kind=Kind.NUMBER, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Lay the sheet flat, or pass the folded part through."""
        name = feature.name
        flattened = feature.params.get("flattened", False) is True
        last, blocker = latest_sheet(feature, ctx)
        if last is None or last.sheet is None:
            raise FeatureError(no_sheet_message(feature, ctx))
        model: SheetModel | None = last.sheet
        if blocker is not None:
            model, message = _take_in_cuts(last, ctx.body, feature, blocker)
            if model is None:
                if flattened:
                    raise FeatureError(message)
                return FlatResult(body=ctx.body, issues=[Issue(FeatureState.WARNING, message)])
        assert model is not None
        model = _options(feature, ctx, model)
        merge = feature.params.get("merge_faces", True) is not False
        flat = model.build(feature.id, name, flat=True, merge=merge)
        flat = _notched(feature, model, flat)
        issues: list[Issue] = []
        for owner in overlaps(model):
            culprit = _name(ctx.document, owner)
            issues.append(
                Issue(
                    FeatureState.WARNING,
                    f"{name}: the flat pattern overlaps itself because of {culprit}. "
                    f"Change {culprit} so the flat pattern has room.",
                    highlight=[n for n, _f in flat.faces if n.startswith(f"{owner}/")],
                    code="flat_overlap",
                )
            )
        angle = self._grain(feature, ctx, model, issues)
        # Always worked out: the panel shows it (audit A item 2, D727); the tick only draws
        # and exports the box.
        size = flat_size(model, flat, angle)
        _sheet_size_issue(feature, size, issues)
        from fdcad.core.features.sheetmetal.quote import quote_values

        merged = flat if merge else _notched(feature, model, model.build(feature.id, name, True))
        extras: dict[str, object] = dict(quote_values(model, merged, size))
        from fdcad.core.features.sheetmetal.bend_list import bend_order

        order = bend_order(feature, model)  # TR282 (D1110)
        lines = model.bend_lines()
        edges = None
        if flattened and feature.params.get("bend_lines") is True and lines:
            made = [BRepBuilderAPI_MakeEdge(gp_Pnt(*a), gp_Pnt(*b)).Edge() for a, b, _ in lines]
            edges = compound(made)
        marks = model.mark_lines(True)
        shown = marks if flattened else model.mark_lines(False)
        mark_edges = None
        if shown:
            made = [BRepBuilderAPI_MakeEdge(gp_Pnt(*a), gp_Pnt(*b)).Edge() for a, b, _ in shown]
            mark_edges = compound(made)
        extras["engraving"] = _engraving(feature, ctx, model)  # TR330 (D2006)
        shown_body = flat if flattened else _progress(feature, model, name) or ctx.body
        if shown_body is not ctx.body:  # flat, or part folded: the other bodies stay (D1075)
            from fdcad.core.features.sheetmetal.common import beside_other_bodies

            shown_body = beside_other_bodies(feature, ctx, shown_body)
        return FlatResult(
            body=shown_body,
            issues=issues,
            flat=flat,
            sheet=model,
            lines=lines,
            size=size,
            grain_angle=angle,
            bend_edges=edges,
            marks=marks,
            mark_edges=mark_edges,
            extras=extras,
            order=order,
        )

    @staticmethod
    def _grain(
        feature: Feature, ctx: BuildContext, model: SheetModel, issues: list[Issue]
    ) -> float:
        """Angle of the grain edge in the root wall's frame (0 without one)."""
        ref = feature.refs.get("grain")
        if not isinstance(ref, dict):
            return 0.0
        edge, found = resolve_edge(ctx.body, ref, feature.name)
        issues.extend(found)
        ends = line_ends(edge)
        if ends is None:
            raise FeatureError(
                f"{feature.name}: the grain edge must be straight. Pick a straight edge."
            )
        inv = model.frame.Inverted()
        a, b = apply(inv, ends[0]), apply(inv, ends[1])
        if abs(a[2] - b[2]) > 1e-6:
            raise FeatureError(
                f"{feature.name}: the grain edge must lie flat on the first wall. "
                "Pick an edge of the first wall."
            )
        return math.atan2(b[1] - a[1], b[0] - a[0]) % math.pi


def flat_pattern_of(doc: Document) -> Feature | None:
    """The part's Flat Pattern feature, if it has one."""
    return next((f for f in doc.features if f.type == TYPE), None)


def flat_only(doc: Document, feature: Feature) -> bool:
    """True when ``feature`` is below a Flat Pattern that is off: it applies to the
    flat state only, so it is not built while the part is folded (D339)."""
    found = False
    for f in doc.features:
        if f.id == feature.id:
            return found
        if f.type == TYPE and not f.suppressed:
            found = f.params.get("flattened", False) is not True
    return False


def _engraving(feature: Feature, ctx: BuildContext, model: SheetModel) -> list[object]:
    """Edges of earlier Mark features that lie on a face of the fixed wall, which stays
    where it is in the flat pattern (TR330, D2006). Marks on bent walls are left out."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.TopoDS import TopoDS

    to_local = model.frame.Inverted()
    t = model.thickness
    found: list[object] = []
    for other in ctx.document.features:
        if other.id == feature.id:
            break
        res = ctx.results.get(other.id)
        if other.type != "mark" or res is None:
            continue
        for edge in res.extras.get("marks", []):
            moved = TopoDS.Edge(BRepBuilderAPI_Transform(edge, to_local, True).Shape())
            curve = BRepAdaptor_Curve(moved)
            zs = [
                curve.Value(
                    curve.FirstParameter()
                    + k * (curve.LastParameter() - curve.FirstParameter()) / 4
                ).Z()
                for k in range(5)
            ]
            if all(abs(z - t) < 1e-4 for z in zs) or all(abs(z) < 1e-4 for z in zs):
                found.append(edge)
    return found
