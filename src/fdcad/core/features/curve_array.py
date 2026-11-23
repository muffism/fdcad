"""Array along curve: copies of features or bodies placed along a curve (PLAN Phase 3,
PHASE3_SPEC P3.7 item 2, DECISIONS D292).

Params:

- ``mode``: ``"count"`` (default: ``count`` instances spread over the whole curve)
  or ``"spacing"`` (``count`` instances ``spacing`` apart along the curve).
- ``count`` (a number, the seed included) and ``spacing`` (length).
- ``start_offset`` and ``end_offset``: optional lengths (TR373, D979): the copies
  start this far along the curve and stop this far before its end. The seed stays
  where it is.
- ``orient``: optional boolean, true by default: each copy turns with the curve.
  False keeps the seed's orientation (copies only move).
- ``refs.square_face`` (TR373, D1017): a face; each copy turns so the face's normal
  under it stays its up direction and the curve its forward direction, for copies
  along a curve on a curved face. It wins over ``orient``.
- ``skip``: optional text, instance numbers to leave out separated by commas,
  for example ``"3,5"``. Instance 1 is the seed and cannot be skipped.
- ``law`` (TR366, D1500): optional spacing law, "even" (default), "growing"
  (``ratio``), "random" (``jitter`` percent, ``seed``) or "fractions" (``fractions``,
  a text list), as Linear Pattern's ``law1``. The law measures from the start offset.
- ``merge``: optional boolean for bodies: join the copies to the bodies they
  touch. Off by default, so each copy is its own body.

Refs: ``path`` (a sketch chain or a curve feature) or ``path_edges`` (edge
references) for the curve; ``features`` (feature references whose own solid is
copied and added or cut like the feature) or ``bodies`` (one face reference per
body to copy).

The seed keeps its place; copy ``k`` is moved by the motion that takes the
curve's start to the point ``k`` along it. Faces of copy ``k`` are named
``instance<k>/<seed face name>`` under this feature.
"""

from __future__ import annotations

from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_CompCurve
from OCP.GCPnts import GCPnts_AbscissaPoint
from OCP.GeomFill import GeomFill_CorrectedFrenet
from OCP.gp import gp_Ax3, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS, TopoDS_Shape, TopoDS_Wire

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    REGISTRY,
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureState,
    FeatureType,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.features.solids import (
    check_result,
    combine,
    compound,
    expected_issues,
    solids,
)
from fdcad.core.naming.names import NamedFace, NamedShape, faces_of, restrict
from fdcad.core.units import Kind

#: The most instances one array may make.
MAX_INSTANCES = 1000
#: Spacing laws along the curve (TR366, D1500), as Linear Pattern's.
LAWS = ("even", "growing", "random", "fractions")


def skipped(feature: Feature) -> set[int]:
    """Instance numbers to leave out. Raises FeatureError for text that is not numbers."""
    text = feature.params.get("skip")
    if not isinstance(text, str) or not text.strip():
        return set()
    out: set[int] = set()
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if not part.isdigit():
            raise FeatureError(
                f"{feature.name}: instances to skip must be numbers separated by commas. "
                "Type them like 2, 5, 7."
            )
        out.add(int(part))
    return out


def _count(feature: Feature) -> int:
    value = feature.params.get("count")
    if not isinstance(value, Param):
        raise FeatureError(f"{feature.name}: the number of instances is missing. Enter it.")
    n = round(value.value)
    if abs(n - value.value) > 1e-9 or n < 2:
        raise FeatureError(
            f"{feature.name}: the number of instances must be a whole number of 2 or more. "
            "Enter 2 or more."
        )
    if n > MAX_INSTANCES:
        raise FeatureError(f"{feature.name}: use at most {MAX_INSTANCES} instances.")
    return int(n)


def stations(feature: Feature, path: TopoDS_Wire) -> list[float]:
    """Distance along the curve of every instance, the seed's (0) first."""
    owner = feature.name
    n = _count(feature)
    curve = BRepAdaptor_CompCurve(path)
    total = GCPnts_AbscissaPoint.Length_s(curve)
    closed = BRep_Tool.IsClosed_s(path)
    start, end = _offset(feature, "start_offset"), _offset(feature, "end_offset")
    room = total - start - end
    if room < -1e-9:
        raise FeatureError(
            f"{owner}: the start and end offsets ({start + end:g} mm together) are longer than "
            f"the curve ({total:.4g} mm). Make the offsets smaller."
        )
    if feature.params.get("mode", "count") == "spacing":
        value = feature.params.get("spacing")
        if not isinstance(value, Param) or not value.value > 0:
            raise FeatureError(f"{owner}: enter a spacing greater than zero.")
        step = value.value
        needed = step * (n if closed else n - 1)
        if needed > room * (1 + 1e-9) + 1e-9:
            raise FeatureError(
                f"{owner}: {n} instances {step:g} mm apart need {needed:g} mm, but the curve "
                f"has {room:.4g} mm between the offsets. Reduce the count or the spacing."
            )
    else:
        step = room / (n if closed else n - 1)
    law = feature.params.get("law", "even")
    if law not in LAWS:
        raise FeatureError(f"{owner}: unknown spacing law '{law}'. Choose another law.")
    if law != "even":  # TR366 (D1500)
        from fdcad.core.features.linear_pattern import law_positions

        along = law_positions(feature, "", step, list(range(n)))
        # The law measures from the start offset: copy k sits there plus its k - 1 step.
        places = [0.0] + [start + along[k - 1] for k in range(2, n + 1)]
        reach = max(places) if places else 0.0
        if min(places) < -1e-9 or (not closed and reach > total - end + 1e-6):
            raise FeatureError(
                f"{owner}: with this spacing law the copies run past the ends of the curve "
                f"(to {reach:.4g} mm of {total - end:.4g} mm). Reduce the count, the "
                "spacing or the growth ratio, or change the fractions."
            )
        return [p % total if closed and total > 0 else p for p in places]
    # Instance 1 is the seed, where it is; the copies run from the start offset (TR373).
    return (
        [0.0] + [start + (k - 1) * step for k in range(2, n + 1)]
        if start
        else [k * step for k in range(n)]
    )


def _offset(feature: Feature, name: str) -> float:
    value = feature.params.get(name)
    if not isinstance(value, Param):
        return 0.0
    if value.value < 0:
        raise FeatureError(
            f"{feature.name}: the {name.replace('_', ' ')} cannot be negative. Enter 0 or more."
        )
    return float(value.value)


class Frames:
    """Points and turning frames along a curve (least turning, so copies do not twist)."""

    def __init__(self, path: TopoDS_Wire) -> None:
        self.curve = BRepAdaptor_CompCurve(path)
        self.law = GeomFill_CorrectedFrenet()
        self.law.SetCurve(self.curve)
        self.u0 = self.curve.FirstParameter()

    def at(self, distance: float) -> gp_Ax3:
        """The frame ``distance`` mm along the curve: X along the curve."""
        u = (
            self.u0
            if distance <= 0
            else GCPnts_AbscissaPoint(self.curve, distance, self.u0).Parameter()
        )
        point = self.curve.Value(u)
        t, n, b = gp_Vec(), gp_Vec(), gp_Vec()
        self.law.D0(u, t, n, b)
        return gp_Ax3(point, gp_Dir(b), gp_Dir(t))

    def point(self, distance: float) -> gp_Pnt:
        """The point ``distance`` mm along the curve."""
        return self.at(distance).Location()

    def square_to(self, distance: float, face: TopoDS_Shape) -> gp_Ax3:
        """The frame ``distance`` mm along the curve with Z the normal of ``face`` at the
        nearest point and X along the curve, square to that normal (TR373, D1017)."""
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.BRepLProp import BRepLProp_SLProps
        from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
        from OCP.TopAbs import TopAbs_REVERSED

        along = self.at(distance)
        point = along.Location()
        surface = BRepAdaptor_Surface(TopoDS.Face(face))
        project = GeomAPI_ProjectPointOnSurf(point, BRep_Tool.Surface_s(TopoDS.Face(face)))
        if project.NbPoints() == 0:
            raise ValueError("no point of the face lies under the curve")
        u, v = project.LowerDistanceParameters()
        props = BRepLProp_SLProps(surface, u, v, 1, 1e-7)
        if not props.IsNormalDefined():
            raise ValueError("the face has no normal under the curve")
        normal = gp_Vec(props.Normal().XYZ())
        if face.Orientation() == TopAbs_REVERSED:
            normal.Reverse()
        tangent = gp_Vec(along.XDirection().XYZ())
        forward = tangent.Subtracted(normal.Multiplied(tangent.Dot(normal)))
        if forward.Magnitude() < 1e-9:
            raise ValueError("the curve runs along the face's normal")
        return gp_Ax3(point, gp_Dir(normal), gp_Dir(forward))


def motions(
    feature: Feature, path: TopoDS_Wire, face: TopoDS_Shape | None = None
) -> list[tuple[int, gp_Trsf]]:
    """Instance number and motion of every copy (the seed and skipped ones left out).
    With ``face`` every copy stays square to it (TR373, D1017)."""
    owner = feature.name
    try:
        frames = Frames(path)
        places = stations(feature, path)
        orient = feature.params.get("orient", True) is not False
        if face is not None:
            try:
                start = frames.square_to(0.0, face)
            except ValueError as exc:
                raise FeatureError(
                    f"{owner}: the copies cannot stay square to the face: {exc}. Pick the "
                    "face the curve runs on."
                ) from None
            out = []
            skip = skipped(feature)
            for k, distance in enumerate(places, start=1):
                if k == 1 or k in skip:
                    continue
                try:
                    here = frames.square_to(distance, face)
                except ValueError as exc:
                    raise FeatureError(
                        f"{owner}: copy {k} cannot stay square to the face: {exc}. Pick the "
                        "face the curve runs on."
                    ) from None
                trsf = gp_Trsf()
                trsf.SetDisplacement(start, here)
                out.append((k, trsf))
            return out
        start = frames.at(0.0)
        out = []
        skip = skipped(feature)
        for k, distance in enumerate(places, start=1):
            if k == 1 or k in skip:
                continue
            here = frames.at(distance)
            trsf = gp_Trsf()
            if orient:
                trsf.SetDisplacement(start, here)
            else:
                trsf.SetTranslation(gp_Vec(start.Location(), here.Location()))
            out.append((k, trsf))
    except FeatureError:
        raise
    except Exception as exc:
        raise FeatureError(
            f"{owner}: positions along the curve could not be found. Use a smoother curve."
        ) from exc
    return out


def moved_copy(fid: str, k: int, seed: NamedShape, trsf: gp_Trsf) -> NamedShape:
    """``seed`` moved by ``trsf``, sharing its geometry, faces renamed for instance ``k``."""
    location = TopLoc_Location(trsf)
    shape = seed.shape.Moved(location)
    names = [
        (f"{fid}/instance{k}/{name}", TopoDS.Face(face.Moved(location)))
        for name, face in seed.faces
    ]
    return NamedShape(shape, names)


def skip_notes(feature: Feature, moves: list[tuple[int, gp_Trsf]]) -> list[Issue]:
    """Warnings for instance numbers to skip that change nothing."""
    owner, n = feature.name, _count(feature)
    hint = "Remove it from Instances to skip."
    out = []
    for k in sorted(skipped(feature)):
        if k == 1:
            text = f"{owner}: instance 1 is the original and is never skipped. {hint}"
        elif k > n or k < 1:
            text = f"{owner}: there is no instance {k} to skip (the array has {n}). {hint}"
        else:
            continue
        out.append(Issue(FeatureState.WARNING, text, code="skip_unused"))
    if not moves:
        out.append(
            Issue(
                FeatureState.WARNING,
                f"{owner}: every copy is skipped, so the array adds nothing. "
                "Remove numbers from Instances to skip.",
                code="skip_unused",
            )
        )
    return out


def _seed_bodies(feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
    """The bodies the picked faces belong to, with their names."""
    from fdcad.core.features.modify import resolve_faces

    body = ctx.body
    if body is None:
        raise FeatureError(f"{feature.name}: the part is empty. Add a body to copy first.")
    found, issues = resolve_faces(feature, ctx, "bodies")
    picked: list[TopoDS_Shape] = []
    for _name, face in found:
        for solid in solids(body.shape):
            if any(f.IsSame(face) for f in faces_of(solid)) and not any(
                p.IsSame(solid) for p in picked
            ):
                picked.append(solid)
    shape = picked[0] if len(picked) == 1 else compound(picked)
    names = [(n, f) for n, f in body.faces if any(f.IsSame(g) for g in faces_of(shape))]
    return NamedShape(shape, names), issues


def _seed_tools(feature: Feature, ctx: BuildContext) -> list[tuple[str, NamedShape]]:
    """Each picked feature's operation and own solid, built where it sits in the tree."""
    from fdcad.core.features.preview import body_before

    owner = feature.name
    out = []
    refs = feature.refs.get("features")
    if not isinstance(refs, list) or not refs:
        raise FeatureError(f"{owner}: pick the features or bodies to copy.")
    for ref in refs:
        fid = str(ref.get("feature", "")) if isinstance(ref, dict) else ""
        try:
            seed = ctx.document.feature(fid)
        except KeyError as exc:
            raise FeatureError(f"{owner}: a feature to copy was deleted. Pick it again.") from exc
        ctx.result(fid)  # an error in the seed stops the array, with its message
        ftype = REGISTRY.get(seed.type)
        before = body_before(ctx.document, seed, ctx.results)
        seed_ctx = BuildContext(
            ctx.document, before, ctx.results, ctx.variables, ctx.cancelled, owner=ctx.owner
        )
        tool = ftype.tool(seed, seed_ctx) if ftype is not None else None
        if tool is None:
            raise FeatureError(
                f"{owner}: {seed.name} cannot be copied along a curve. "
                "Pick a solid feature to copy."
            )
        fixed = ftype.pattern_operation if ftype is not None else None
        out.append((str(seed.params.get("operation", fixed or "boss")), tool))
    return out


def _combine_copies(
    feature: Feature, body: NamedShape | None, copies: list[NamedShape], operation: str
) -> NamedShape:
    """One boolean for all copies of one operation (PLAN 11.3 item 4). The copies go to
    the kernel as separate tools, so copies that overlap each other fuse too."""
    if not copies:
        return body if body is not None else NamedShape(compound([]))
    shape = compound([c.shape for c in copies])
    names: list[NamedFace] = [n for c in copies for n in c.faces]
    tool = NamedShape(shape, names)
    return combine(feature.id, feature.name, body, tool, operation, pieces=True)


@register
class CurveArray(FeatureType):
    """Copies features or bodies along a curve."""

    type_name = "curve_array"
    makes_solid = True
    params = (
        ParamSpec("mode", choices=("count", "spacing"), default="count"),
        ParamSpec("count", kind=Kind.NUMBER),
        ParamSpec("spacing", kind=Kind.LENGTH, optional=True),
        ParamSpec("start_offset", kind=Kind.LENGTH, optional=True),  # TR373 (D979)
        ParamSpec("end_offset", kind=Kind.LENGTH, optional=True),
        ParamSpec("orient", default=True, optional=True),
        ParamSpec("skip", optional=True),
        ParamSpec("merge", default=False, optional=True),
        ParamSpec("law", choices=LAWS, optional=True),  # TR366 (D1500)
        ParamSpec("ratio", kind=Kind.NUMBER, optional=True),
        ParamSpec("jitter", kind=Kind.NUMBER, optional=True),
        ParamSpec("seed", kind=Kind.NUMBER, optional=True),
        ParamSpec("fractions", optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Place the copies and add them to the part."""
        from fdcad.core.features.sweep import path_wire

        owner, fid = feature.name, feature.id
        if not feature.refs.get("path") and not feature.refs.get("path_edges"):
            raise FeatureError(f"{owner} has no curve. Choose a sketch or curve, or pick edges.")
        path, issues = path_wire(feature, ctx)
        square = feature.refs.get("square_face")
        face = None
        if isinstance(square, list) and square and ctx.body is not None:  # TR373 (D1017)
            from fdcad.core.naming.resolve import resolve_face

            face = resolve_face(ctx.body, square[0], owner)[0]
        moves = motions(feature, path, face)
        body = ctx.body
        found: list[Issue] = []
        result: NamedShape | None
        if feature.refs.get("bodies"):
            seed, found = _seed_bodies(feature, ctx)
            if feature.refs.get("features"):
                # Bodies and features cannot be copied together (audit A item 5, D727).
                found = [
                    *found,
                    Issue(
                        FeatureState.WARNING,
                        f"{owner} copies the picked bodies, so the ticked features are not "
                        "copied. Untick the features, or clear the body picks to copy them.",
                        code="features_ignored",
                    ),
                ]
            copies = [moved_copy(fid, k, seed, t) for k, t in moves]
            assert body is not None
            if feature.params.get("merge", False) is True:
                result = _combine_copies(feature, body, copies, "boss")
            else:
                shape = compound([body.shape, *[c.shape for c in copies]])
                names = body.faces + [n for c in copies for n in c.faces]
                result = NamedShape(shape, restrict(names, shape, fid))
        else:
            result = body
            seeds = _seed_tools(feature, ctx)
            for operation in ("boss", "cut"):
                tools = [t for op, t in seeds if op == operation]
                copies = [moved_copy(fid, k, t, m) for t in tools for k, m in moves]
                if copies:
                    result = _combine_copies(feature, result, copies, operation)
            if result is None:
                raise FeatureError(f"{owner}: there is nothing to copy. Pick features or bodies.")
            found = check_result(fid, owner, ctx.body, result, None)
        notes = skip_notes(feature, moves)
        return FeatureResult(body=result, issues=issues + expected_issues(feature, found) + notes)
