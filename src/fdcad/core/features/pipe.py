"""Pipe: a round solid along a curve or a chain of edges (PLAN Phase 3,
PHASE3_SPEC P3.7 item 1, DECISIONS D292).

Params:

- ``operation``: ``"boss"`` (default) or ``"cut"``. ``merge``: optional boolean.
- ``outer_diameter`` (length).
- ``inner_diameter`` (length, optional): a hollow pipe when set above zero.
- ``cap_ends`` (optional boolean, hollow pipes only): close both ends with a wall
  as thick as the pipe wall, so the tube is sealed.

Refs: ``path``: a sketch whose curves form one chain or a curve feature
(``{"feature": "f9"}``), or ``path_edges``: a chain of edge references.

Sharp corners in the path get mitred corners, like a welded frame. Face roles: ``pipe/outer``,
``pipe/inner`` (with ``#k`` per path segment after the first), ``cap/start``,
``cap/end``, and ``cap/inner_start``, ``cap/inner_end`` for capped ends.
"""

from __future__ import annotations

from OCP.BRep import BRep_Tool
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeWire,
    BRepBuilderAPI_RightCorner,
)
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt, gp_Vec
from OCP.TopAbs import TopAbs_FACE
from OCP.TopoDS import TopoDS, TopoDS_Shape, TopoDS_Wire

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
from fdcad.core.features.solids import (
    FUZZY_TOLERANCE,
    check_result,
    combine_or_keep,
    expected_issues,
    is_valid,
)
from fdcad.core.naming.names import NamedFace, NamedShape, carry, faces_of, restrict
from fdcad.core.occ import BRepAlgoAPI_Cut, shape_list
from fdcad.core.units import Kind


def _diameter(feature: Feature, name: str, label: str) -> float:
    value = feature.params.get(name)
    if not isinstance(value, Param) or not value.value > 0:
        raise FeatureError(f"{feature.name}: enter an {label} greater than zero.")
    return value.value


def _ends(path: TopoDS_Wire) -> tuple[tuple[gp_Pnt, gp_Vec], tuple[gp_Pnt, gp_Vec]]:
    """Start and end points of the path with the tangent pointing along it."""
    from OCP.BRepAdaptor import BRepAdaptor_CompCurve

    curve = BRepAdaptor_CompCurve(path)
    out = []
    for u in (curve.FirstParameter(), curve.LastParameter()):
        p, t = gp_Pnt(), gp_Vec()
        curve.D1(u, p, t)
        out.append((p, t.Normalized()))
    return out[0], out[1]


def _tube(owner: str, path: TopoDS_Wire, diameter: float) -> BRepOffsetAPI_MakePipeShell:
    """A round section of ``diameter`` swept along ``path`` and closed into a solid."""
    (start, tangent), _end = _ends(path)
    circle = gp_Circ(gp_Ax2(start, gp_Dir(tangent)), diameter / 2)
    section = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(circle).Edge()).Wire()
    maker = BRepOffsetAPI_MakePipeShell(path)
    maker.SetMode(False)  # least turning frame
    maker.SetTransitionMode(BRepBuilderAPI_RightCorner)
    maker.Add(section, False, False)
    try:
        maker.Build()
        if maker.IsDone():
            maker.MakeSolid()
    except Exception as exc:
        raise FeatureError(
            f"{owner}: the pipe could not follow the path. Use a smaller diameter or a "
            "gentler path."
        ) from exc
    if not maker.IsDone():
        raise FeatureError(
            f"{owner}: the pipe could not follow the path. Use a smaller diameter or a "
            "gentler path."
        )
    return maker


def _named(fid: str, maker: BRepOffsetAPI_MakePipeShell, side: str, caps: bool) -> list[NamedFace]:
    """Names for the swept faces (``pipe/<side>``) and, when asked, the end caps."""
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer

    names: list[NamedFace] = []
    shape = maker.Shape()
    section_edges = []
    for profile in (maker.FirstShape(),):
        explorer = TopExp_Explorer(profile, TopAbs_EDGE)
        while explorer.More():
            section_edges.append(explorer.Current())
            explorer.Next()
    made: list[TopoDS_Shape] = []
    for edge in section_edges:
        made += [s for s in shape_list(maker.Generated(edge)) if s.ShapeType() == TopAbs_FACE]
    if not made:  # some kernel versions only report the side faces by elimination
        caps_faces = faces_of(maker.FirstShape()) + faces_of(maker.LastShape())
        made = [f for f in faces_of(shape) if not any(c.IsSame(f) for c in caps_faces)]
    for k, face in enumerate(made, start=1):
        names.append((f"{fid}/pipe/{side}{'' if k == 1 else f'#{k}'}", TopoDS.Face(face)))
    if caps:
        for role, end in (("start", maker.FirstShape()), ("end", maker.LastShape())):
            for face in faces_of(end):
                names.append((f"{fid}/cap/{role}", face))
    return names


def _end_box(point: gp_Pnt, tangent: gp_Vec, depth: float, size: float) -> TopoDS_Shape:
    """A box ``size`` wide reaching ``depth`` from ``point`` along ``tangent``."""
    axis = gp_Ax2(point, gp_Dir(tangent))
    x, y = axis.XDirection(), axis.YDirection()
    corner = gp_Pnt(
        point.X() - (x.X() + y.X()) * size / 2,
        point.Y() - (x.Y() + y.Y()) * size / 2,
        point.Z() - (x.Z() + y.Z()) * size / 2,
    )
    frame = gp_Ax2(corner, gp_Dir(tangent), x)
    return BRepPrimAPI_MakeBox(frame, size, size, depth).Shape()


def _cap_names(
    fid: str, void: TopoDS_Shape, named: list[NamedFace], start: gp_Pnt
) -> list[NamedFace]:
    """The void's new end faces: ``cap/inner_start`` nearest the path start, then
    ``cap/inner_end``."""
    from fdcad.core.naming.names import centroid

    new = [f for f in faces_of(void) if not any(f.IsSame(g) for _n, g in named)]

    def gap(face: TopoDS_Shape) -> float:
        c = centroid(face)
        return float(start.Distance(gp_Pnt(*c)))

    ordered = sorted(new, key=gap)
    roles = ["cap/inner_start", "cap/inner_end"]
    return [(f"{fid}/{roles[min(k, 1)]}", f) for k, f in enumerate(ordered)]


def _cut(owner: str, a: TopoDS_Shape, b: TopoDS_Shape) -> BRepAlgoAPI_Cut:
    cut = BRepAlgoAPI_Cut(a, b)
    cut.SetFuzzyValue(FUZZY_TOLERANCE)
    cut.Build()
    if not cut.IsDone():
        raise FeatureError(f"{owner}: the pipe's hollow could not be made. Change the diameters.")
    return cut


def pipe_solid(feature: Feature, path: TopoDS_Wire) -> NamedShape:
    """The named pipe solid along ``path``."""
    fid, owner = feature.id, feature.name
    outer_d = _diameter(feature, "outer_diameter", "outer diameter")
    inner = feature.params.get("inner_diameter")
    inner_d = inner.value if isinstance(inner, Param) else 0.0
    if inner_d < 0:
        raise FeatureError(f"{owner}: the inner diameter cannot be negative. Enter 0 or more.")
    if inner_d >= outer_d:
        raise FeatureError(
            f"{owner}: the inner diameter must be smaller than the outer diameter. "
            "Reduce the inner diameter."
        )
    closed = BRep_Tool.IsClosed_s(path)
    outer = _tube(owner, path, outer_d)
    names = _named(fid, outer, "outer", not closed)
    shape = outer.Shape()
    if inner_d > 0:
        hollow = _tube(owner, path, inner_d)
        void = hollow.Shape()
        void_names = _named(fid, hollow, "inner", False)
        if feature.params.get("cap_ends") is True and not closed:
            wall = (outer_d - inner_d) / 2
            (p0, t0), (p1, t1) = _ends(path)
            size = outer_d * 1.5
            for point, tangent in ((p0, t0), (p1, t1.Reversed())):
                trimmed = _cut(owner, void, _end_box(point, tangent, wall, size))
                void_names = carry(void_names, trimmed.History())
                void = trimmed.Shape()
            void_names += _cap_names(fid, void, void_names, p0)
        cut = _cut(owner, shape, void)
        names = carry(names + void_names, cut.History())
        shape = cut.Shape()
    named = NamedShape(shape, restrict(names, shape, fid))
    if not is_valid(None, named):
        raise FeatureError(
            f"{owner}: the pipe intersects itself. Use a smaller diameter or a gentler path."
        )
    return named


@register
class Pipe(FeatureType):
    """A round solid, solid or hollow, along a path."""

    type_name = "pipe"
    makes_solid = True
    params = (
        ParamSpec("operation", choices=("boss", "cut"), default="boss"),
        ParamSpec("merge", default=True, optional=True),
        ParamSpec("outer_diameter", kind=Kind.LENGTH),
        ParamSpec("inner_diameter", kind=Kind.LENGTH, optional=True),
        ParamSpec("cap_ends", default=False, optional=True),
    )

    def _tool(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        from fdcad.core.features.sweep import path_wire

        if not feature.refs.get("path") and not feature.refs.get("path_edges"):
            raise FeatureError(
                f"{feature.name} has no path. Choose a sketch or curve, or pick edges."
            )
        path, issues = path_wire(feature, ctx)
        return pipe_solid(feature, path), issues

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Make the pipe and add it to the part (or cut it away)."""
        operation = str(feature.params.get("operation", "boss"))
        tool, issues = self._tool(feature, ctx)
        body = combine_or_keep(feature, ctx.body, tool, operation)
        found = check_result(feature.id, feature.name, ctx.body, body, None)
        return FeatureResult(body=body, issues=issues + expected_issues(feature, found))

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The pipe on its own, for the preview."""
        return self._tool(feature, ctx)[0]
