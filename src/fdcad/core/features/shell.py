"""Shell: hollow the part, leaving walls (PHASE2_SPEC P2.6, PLAN 5A item 4, DECISIONS D217).

Params:

- ``thickness``: length, the wall thickness.
- ``outward``: optional boolean, the wall grows outside the part instead of inside.
- ``thickness_<k>``: length, the wall of face ``k`` (1 based) of ``refs.thick_faces``.
- ``both_sides``: optional boolean (TR322, D1411): half the wall inside the part
  and half outside; the outer wall faces are ``outer/<face name>``.
- ``corners``: optional "sharp" or "rounded" (TR129, D825): how the wall's outside
  corners join. Without it, sharp first and rounded when sharp fails.
- ``wall_rule``: optional "never_thinner" or "never_thicker" (TR322, D1803): the
  wall is kept at least or at most the thickness; see ``shell_wall_rule``.

Refs: ``faces`` (faces to remove; none gives a hollow closed part),
``thick_faces`` (faces with their own thickness) and, in a part with several
bodies and no face to remove, ``body`` (any face of the body to shell).

``skipped_faces`` (TR278, D1406): faces left open as a fix when the kernel cannot
make their wall; Reset Skipped Faces clears it.

Face roles: ``shell/<face name>`` for the wall face made from a face of the part.
When the kernel fails, every face whose bend radius is smaller than the wall is
found and named in the message (PLAN 5A item 4).
"""

from __future__ import annotations

from collections.abc import Callable

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepLProp import BRepLProp_SLProps
from OCP.BRepOffset import BRepOffset_MakeOffset, BRepOffset_Skin
from OCP.GeomAbs import GeomAbs_Arc, GeomAbs_Intersection, GeomAbs_JoinType, GeomAbs_Plane
from OCP.Message import Message_ProgressRange
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape

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
from fdcad.core.features.modify import (
    MakerHistory,
    changed_faces,
    length,
    require_body,
    resolve_faces,
)
from fdcad.core.features.shell_gap import too_close
from fdcad.core.features.shell_wall_rule import WALL_RULES, check_rule, corners_for
from fdcad.core.features.solids import FUZZY_TOLERANCE, check_result, compound, solids
from fdcad.core.naming.names import NamedFace, NamedShape, carry, faces_of, restrict
from fdcad.core.occ import BRepAlgoAPI_Cut, ShapeMap, shape_list
from fdcad.core.units import Kind

_OFFSET_TOL = 1e-4
_SAMPLES = 5


def smallest_radius(face: TopoDS_Face, outward: bool = False) -> float | None:
    """The smallest bend radius of a face that limits a wall, sampled on a grid.

    An inward wall is limited by faces that bulge out (convex), an outward wall by
    faces that curve in (concave). None when no part of the face limits the wall.
    """
    surface = BRepAdaptor_Surface(face)
    if surface.GetType() == GeomAbs_Plane:
        return None
    u0, u1 = surface.FirstUParameter(), surface.LastUParameter()
    v0, v1 = surface.FirstVParameter(), surface.LastVParameter()
    best: float | None = None
    for i in range(_SAMPLES):
        for j in range(_SAMPLES):
            u = u0 + (u1 - u0) * (i + 0.5) / _SAMPLES
            v = v0 + (v1 - v0) * (j + 0.5) / _SAMPLES
            props = BRepLProp_SLProps(surface, u, v, 2, 1e-7)
            if not props.IsCurvatureDefined():
                continue
            flip = -1.0 if face.Orientation() == TopAbs_REVERSED else 1.0
            ks = [flip * props.MaxCurvature(), flip * props.MinCurvature()]
            # Seen from outside the part: negative bends out (convex), positive bends in.
            limiting = [abs(k) for k in ks if (k > 0 if outward else k < 0)]
            k = max(limiting, default=0.0)
            if k > 1e-12:
                radius = 1.0 / k
                best = radius if best is None else min(best, radius)
    return best


def check_walls(
    body: NamedShape, thickness: float, outward: bool = False
) -> tuple[list[tuple[str, float]], float | None]:
    """Shell's Check (TR147 item 2, D998): the faces of every body that bend tighter
    than ``thickness``, tightest first, and the smallest bend radius of any face
    that limits the wall (None when no face is curved that way)."""
    tight: list[tuple[str, float]] = []
    smallest: float | None = None
    for face in faces_of(body.shape):
        radius = smallest_radius(face, outward)
        if radius is None:
            continue
        smallest = radius if smallest is None else min(smallest, radius)
        if radius < thickness:
            tight.append((body.primary_name(face) or "a face", radius))
    tight.sort(key=lambda item: item[1])
    return tight, smallest


def diagnose(
    body: NamedShape, solid: TopoDS_Shape, thickness: float, outward: bool = False
) -> list[tuple[str, float]]:
    """Faces whose bend radius is smaller than the wall thickness (PLAN 5A item 4)."""
    out: list[tuple[str, float]] = []
    for face in faces_of(solid):
        radius = smallest_radius(face, outward)
        if radius is not None and radius < thickness:
            out.append((body.primary_name(face) or "a face", radius))
    out.sort(key=lambda item: item[1])
    return out


def tight_faces(
    owner: str, body: NamedShape, solid: TopoDS_Shape, thickness: float, outward: bool
) -> FeatureError | None:
    """The diagnosis as an error naming the tightest face, or None when all fit."""
    tight = diagnose(body, solid, thickness, outward)
    if not tight:
        return None
    name, radius = tight[0]
    more = f" and {len(tight) - 1} more" if len(tight) > 1 else ""
    return FeatureError(
        f"{owner} failed: face {name}{more} bends with a radius of {radius:.3g} mm, "
        f"smaller than the {thickness:.3g} mm wall. Use a thinner wall, or remove or "
        "round that face first.",
        highlight=[n for n, _r in tight],
    )


#: Refs key of the faces left open as a fix (TR278, D1406).
SKIPPED = "skipped_faces"
#: Faces tried one at a time to find the one the kernel cannot treat.
_SKIP_TRIES = 25
#: Bodies with more faces than this are not searched (each try is a whole shell).
_SKIP_FACES = 150
#: Most faces offset over all the tries together (D2606). A try is a whole shell, so
#: its time goes with the faces of the body: on the attractor plate (83 faces) the 25
#: tries took 33 s. A body of up to 40 faces still gets all 25 tries.
_SKIP_WORK = 1000


def skip_help(
    feature: Feature,
    body: NamedShape,
    solid: TopoDS_Shape,
    removed: list[TopoDS_Face],
    outward: bool,
    attempt: object,
    cancelled: Callable[[], bool] = lambda: False,
) -> FeatureError:
    """Find one face whose leaving out lets the shell build, and offer to skip it.

    Faces are tried tightest bend first, fewer on a large body, and the search stops
    when the build is cancelled (D2606). The fix adds the face to
    ``refs.skipped_faces``; Reset Skipped Faces clears the list (TR278, D1406). Nothing
    changes until the user clicks (CLAUDE.md rule 5 item 12).
    """
    from fdcad.core.features.base import Fix
    from fdcad.core.naming.select import reference_for

    owner = feature.name
    faces = [f for f in faces_of(solid) if not any(f.IsSame(r) for r in removed)]
    if not faces or len(faces) > _SKIP_FACES:
        return kernel_failed(owner)

    def tightness(face: TopoDS_Face) -> float:
        radius = smallest_radius(face, outward)
        return radius if radius is not None else float("inf")

    tries = min(_SKIP_TRIES, max(1, _SKIP_WORK // len(faces)))
    for face in sorted(faces, key=tightness)[:tries]:
        if cancelled():
            break
        if attempt((face,)) is None:  # type: ignore[operator]
            continue
        name = body.primary_name(face) or "a face"
        ref = reference_for(body, face)
        fixes = []
        if ref is not None:
            fixes.append(
                Fix(
                    f"Skip face {name} (leave it open)",
                    "add_refs",
                    {"feature": feature.id, "key": SKIPPED, "refs": [ref]},
                )
            )
        return FeatureError(
            f"{owner} failed: the kernel cannot make the wall of face {name}. Skip that face "
            "to leave it open, or use a thinner wall.",
            fixes=fixes,
            highlight=[name],
        )
    return kernel_failed(owner)


def narrow_gap(
    owner: str, body: NamedShape, a: TopoDS_Face, b: TopoDS_Face, gap: float, thickness: float
) -> FeatureError:
    """The error when two faces are too close for a wall on each (D2616)."""
    names = [body.primary_name(a) or "a face", body.primary_name(b) or "a face"]
    return FeatureError(
        f"{owner} failed: faces {names[0]} and {names[1]} are {gap:.3g} mm apart, too "
        f"close for a {thickness:.3g} mm wall on each. Use a wall thinner than "
        f"{gap / 2:.3g} mm, or move those faces apart.",
        highlight=names,
    )


def kernel_failed(owner: str) -> FeatureError:
    """The error when the kernel fails without a face that is too tight."""
    return FeatureError(
        f"{owner} failed: the kernel could not offset the faces by the wall thickness. "
        "Use a thinner wall or remove other faces."
    )


@register
class Shell(FeatureType):
    """Hollows a body, leaving walls of a set thickness."""

    type_name = "shell"
    makes_solid = True
    params = (
        ParamSpec("thickness", kind=Kind.LENGTH),
        ParamSpec("outward", default=False, optional=True),
        ParamSpec("corners", choices=("sharp", "rounded"), optional=True),  # TR129
        ParamSpec("both_sides", default=False, optional=True),  # TR322 (D1411)
        ParamSpec("wall_rule", choices=WALL_RULES, optional=True),  # TR322 (D1803)
    )

    def kind_of(self, name: str) -> Kind | None:
        """Per face thicknesses are lengths too."""
        if name.startswith("thickness_"):
            return Kind.LENGTH
        return super().kind_of(name)

    def _target(
        self, feature: Feature, ctx: BuildContext, removed: list[TopoDS_Face]
    ) -> tuple[TopoDS_Shape, list[TopoDS_Shape], list[Issue]]:
        """The solid to shell and the other solids of the part."""
        body = require_body(feature, ctx)
        all_solids = solids(body.shape)
        issues: list[Issue] = []
        key: TopoDS_Face | None = removed[0] if removed else None
        if key is None and len(all_solids) > 1:
            picked, issues = resolve_faces(feature, ctx, "body", required=False)
            if not picked:
                raise FeatureError(
                    f"{feature.name}: the part has {len(all_solids)} bodies. "
                    "Pick the body to shell, or a face to remove."
                )
            key = picked[0][1]
        if key is None:
            return all_solids[0], all_solids[1:], issues
        for solid in all_solids:
            fmap = ShapeMap()
            from OCP.TopExp import TopExp

            TopExp.MapShapes_s(solid, TopAbs_FACE, fmap)
            if fmap.Contains(key):
                return solid, [s for s in all_solids if not s.IsSame(solid)], issues
        raise FeatureError(f"{feature.name}: the picked face is not on a body. Pick it again.")

    def _both_sides(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        """Half the wall inside the part and half outside (TR322, D1411).

        The inward and the outward half walls are made as two shells and fused; they
        meet on the part's old surface, which goes."""
        import copy

        from fdcad.core.features.solids import combine

        body = require_body(feature, ctx)
        if len(solids(body.shape)) != 1:
            raise FeatureError(
                f"{feature.name}: Both Sides works on a part with one body. "
                "Turn off Both Sides, or split the part first."
            )
        halves: list[NamedShape] = []
        issues: list[Issue] = []
        for outward in (False, True):
            half = copy.deepcopy(feature)
            half.params.pop("both_sides", None)
            half.params["outward"] = outward
            for name, value in list(half.params.items()):
                if (name == "thickness" or name.startswith("thickness_")) and isinstance(
                    value, Param
                ):
                    half.params[name] = Param(value.expr, value.value / 2)
            made, found = self._shell(half, ctx)
            issues += found
            if outward:  # the outer wall faces get their own role
                made = NamedShape(
                    made.shape,
                    [
                        (n.replace(f"{feature.id}/shell/", f"{feature.id}/outer/", 1), f)
                        for n, f in made.faces
                    ],
                )
            halves.append(made)
        inner, outer = halves
        joined = combine(feature.id, feature.name, inner, outer, "boss")
        return joined, issues

    def _shell(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        if feature.params.get("both_sides") is True:
            return self._both_sides(feature, ctx)
        body = require_body(feature, ctx)
        owner, fid = feature.name, feature.id
        t = length(feature, "thickness", "thickness")
        outward = feature.params.get("outward") is True
        removed_named, issues = resolve_faces(feature, ctx, "faces", required=False)
        thick_named, more = resolve_faces(feature, ctx, "thick_faces", required=False)
        issues = issues + more
        # TR278 (D1406): faces the user chose to skip are left open, like removed faces.
        skipped_named, more = resolve_faces(feature, ctx, SKIPPED, required=False)
        issues = issues + more
        removed = [f for _n, f in removed_named] + [f for _n, f in skipped_named]
        solid, others, found = self._target(feature, ctx, removed)
        issues += found
        sign = 1.0 if outward else -1.0
        walls = [t] + [
            p.value
            for k in range(1, len(thick_named) + 1)
            if isinstance(p := feature.params.get(f"thickness_{k}"), Param)
        ]
        tight = tight_faces(owner, body, solid, max(walls), outward)
        if tight is not None:
            raise tight  # pre check: the wall cannot fit (PLAN 5A item 4)

        def attempt(
            join: GeomAbs_JoinType, extra: tuple[TopoDS_Face, ...] = ()
        ) -> BRepOffset_MakeOffset | None:
            maker = BRepOffset_MakeOffset()
            maker.Initialize(
                solid, sign * t, _OFFSET_TOL, BRepOffset_Skin, False, False, join, False
            )
            opened = [*removed, *extra]
            for face in opened:
                maker.AddFace(face)
            for k, (_name, face) in enumerate(thick_named, start=1):
                own = feature.params.get(f"thickness_{k}")
                if isinstance(own, Param):
                    if own.value <= 0:
                        raise FeatureError(
                            f"{owner}: face thickness {k} must be greater than zero. "
                            "Enter a larger thickness."
                        )
                    maker.SetOffsetOnFace(face, sign * own.value)
            try:
                if opened:
                    maker.MakeThickSolid(Message_ProgressRange())
                else:
                    maker.MakeOffsetShape(Message_ProgressRange())
            except Exception:
                return None
            if not maker.IsDone() or maker.Shape().IsNull() or not solids(maker.Shape()):
                return None
            if not BRepCheck_Analyzer(maker.Shape()).IsValid():
                return None  # sharp joins can come back broken; try round ones
            return maker

        # Sharp joins first (exact walls); round joins when the kernel cannot
        # intersect the offset faces, for example a fillet that meets a bore.
        rule = feature.params.get("wall_rule")
        corners = corners_for(owner, rule, feature.params.get("corners"))  # TR322 (D1803)

        def any_join(extra: tuple[TopoDS_Face, ...] = ()) -> BRepOffset_MakeOffset | None:
            if corners == "rounded":
                return attempt(GeomAbs_Arc, extra)
            if corners == "sharp":
                return attempt(GeomAbs_Intersection, extra)
            return attempt(GeomAbs_Intersection, extra) or attempt(GeomAbs_Arc, extra)

        maker = any_join()
        if maker is None:
            if not outward and not thick_named:  # D2616: a gap too narrow for two walls
                close = too_close(solid, removed, t)
                if close is not None:
                    raise narrow_gap(owner, body, *close, t)
            raise skip_help(feature, body, solid, removed, outward, any_join, ctx.cancelled)
        made = maker.Shape()
        made_from = maker.Generated
        if removed and _not_hollowed(solid, made, removed, outward):
            raise FeatureError(
                f"{owner} failed: the wall is as thick as the part, so nothing was hollowed. "
                "Use a thinner wall."
            )
        if removed:
            names: list[NamedFace] = carry(body.faces, MakerHistory(maker))
        else:
            # A closed hollow keeps the original faces; the offset ones become the wall.
            names = list(body.faces)
        for name, face in body.faces:
            for new in shape_list(made_from(face)):
                if new.ShapeType() == TopAbs_FACE:
                    names.append((f"{fid}/shell/{name}", TopoDS.Face(new)))
        if not removed:
            made, names = self._hollow(owner, solid, made, outward, names)
        shape = compound([made, *others]) if others else made
        if others:
            names = names + [(n, f) for n, f in body.faces]
        result = NamedShape(shape, restrict(names, shape, f"{fid}/wall"))
        if rule in WALL_RULES and not thick_named:  # TR322 (D1803): measure the wall
            walls = [f for n, f in result.faces if n.startswith(f"{fid}/")]
            issues = issues + check_rule(owner, rule, t, solid, removed, walls)
        return result, issues

    @staticmethod
    def _hollow(
        owner: str,
        solid: TopoDS_Shape,
        offset: TopoDS_Shape,
        outward: bool,
        names: list[NamedFace],
    ) -> tuple[TopoDS_Shape, list[NamedFace]]:
        """A closed hollow part: the part minus its inner offset, or the outer offset minus it."""
        outer, inner = (offset, solid) if outward else (solid, offset)
        cut = BRepAlgoAPI_Cut(outer, inner)
        cut.SetFuzzyValue(FUZZY_TOLERANCE)
        cut.Build()
        if not cut.IsDone():
            raise FeatureError(f"{owner} failed: the hollow could not be made. Use a thinner wall.")
        return cut.Shape(), carry(names, cut.History())

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Shell the body."""
        result, issues = self._shell(feature, ctx)
        issues = issues + check_result(feature.id, feature.name, ctx.body, result, None)
        return FeatureResult(body=result, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The new and changed faces, for the preview."""
        body = require_body(feature, ctx)
        result, _issues = self._shell(feature, ctx)
        return changed_faces(body.shape, result, feature.id)


def _not_hollowed(
    solid: TopoDS_Shape, made: TopoDS_Shape, removed: list[TopoDS_Face], outward: bool
) -> bool:
    """True when the kernel gave the part back without opening it (D607).

    With a wall as thick as the part the kernel can return the solid unchanged
    and report success: the removed faces are still there and no material went.
    """
    from fdcad.core.features.solids import volume_of
    from fdcad.core.naming.names import faces_of

    left = faces_of(made)
    if any(f.IsSame(r) for r in removed for f in left):
        return True
    return not outward and volume_of(made) >= volume_of(solid) * (1 - 1e-9)
