"""Move Face: offset, translate or rotate picked faces (PHASE3_SPEC P3.1.1, DECISIONS D232).

Params:
- ``mode``: "offset", "translate" or "rotate".
- ``distance``: length. Offset: how far each face moves along its own outward
  normal. Translate with ``translate_by`` "direction": how far along the direction;
  with "offset_from_face": the extra distance past the target.
- ``reverse``: boolean, flips Offset and the Translate direction.
- ``print_fit``: optional (Offset), "clearance", "slip" or "press", with
  ``fit_tolerance`` (length, copied from the printer profile when chosen). The
  faces move a further fit gap into the material: one tolerance for Clearance,
  half for Slip, none for Press, as a hole's diameter grows by two, one or no
  tolerances (DECISIONS D311, D413).
- ``copy``: optional boolean (Translate and Rotate): keep the faces and add a moved copy.
- ``translate_by``: optional, "direction" (default), "delta", "up_to_vertex",
  "up_to_face", "offset_from_face" or "up_to_body".
- ``dx``, ``dy``, ``dz``: lengths, for "delta".
- ``rotate_by``: optional, "axis" (default) or "origin".
- ``angle``: angle about the axis. ``rx``, ``ry``, ``rz``: angles about X, Y and
  Z through the rotation origin ``ox``, ``oy``, ``oz`` (lengths), for "origin".

Refs:
- ``faces``: list of face references (FDEF_SPEC 7).
- ``direction``: a straight edge, flat face, plane or axis (Translate by direction).
- ``from``: a face, plane or vertex; ``to``: a vertex (Up to Vertex) or a face or
  plane (Up to Face, Offset from Face). Without ``from`` the first picked face is used.
- ``body``: a face of the target body (Up to Body).
- ``axis``: a straight edge, round edge or cylinder (Rotate about axis).

Sizes (TR265, D789):
- ``mode`` "resize": ``diameter`` (length) is the new diameter of each picked
  cylinder or sphere face, or the tube diameter of a torus; the face is offset
  by the difference, so neighbouring rounds follow as for Offset.
- Offset with ``set_size`` (optional length) and ``refs.size_from`` (a vertex,
  edge or face): the one flat picked face moves until it is ``set_size`` from
  that item, measured along the face's normal (a round edge or face counts from
  its centre or axis); ``distance`` is not used.

Rules (TR263, D788): ``rule_coplanar``, ``rule_concentric``, ``rule_tangent``,
``rule_equal_radius`` (optional booleans) add the faces in that relation to the
move; ``suspend_rules`` turns them all off; ``refs.rule_exclude`` lists faces no
rule adds (see ``face_rules``).

Face roles: moved faces keep their names. Copies add ``copy1/face#k``.
Neighbouring faces keep their names while they stretch.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

from OCP.gp import gp_Trsf
from OCP.TopoDS import TopoDS, TopoDS_Face

from fdcad.core.document.model import Feature, Param
from fdcad.core.features import hole_data
from fdcad.core.features.base import (
    ANGLE_RULER_STEP,
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureState,
    FeatureType,
    Issue,
    ParamSpec,
    PreviewHandle,
    Vec3,
    register,
    ruler_step,
    value_label,
)
from fdcad.core.features.bodies import on_own_bodies
from fdcad.core.features.direct import (
    feature_volumes,
    move_volumes,
    offset_faces,
    on_target,
    outward_normal,
    patch,
    rename_moved,
    resolve_faces,
    rotation,
    short_name,
    tilt_faces,
    translation,
)
from fdcad.core.features.face_rules import (
    MAIN_PLANES,
    RULES,
    active_rules,
    facing,
    held_faces,
    rule_faces,
)
from fdcad.core.features.geometry_refs import dot, minus, resolve_placement, scaled
from fdcad.core.features.move_follow import (
    FOLLOW,
    ROUNDS,
    follow_order,
    lift_faces,
    remake_rounds,
    strip_rounds,
    tip_faces,
)
from fdcad.core.features.solids import bounding_size, check_result, extent_along, solids
from fdcad.core.naming.names import NamedShape, centroid
from fdcad.core.units import Kind

MODES = ("offset", "translate", "rotate", "resize")
TRANSLATE_BY = (
    "direction",
    "delta",
    "up_to_vertex",
    "up_to_face",
    "offset_from_face",
    "up_to_body",
)
ROTATE_BY = ("axis", "origin")
#: Names of the ways neighbours follow, for messages (TR264).
FOLLOW_LABELS = {"extend": "Extend", "tip": "Tip", "lift": "Lift"}
#: Holding rule names, for messages (D798).
HOLD_LABELS = {
    "parallel": "Keep parallel and square faces",
    "main_planes": "Keep faces on main planes",
}
#: Faces a holding rule keeps: (name, outward normal before the move, rule).
Held = tuple[tuple[str, tuple[float, float, float] | None, str], ...] | tuple[()]


def _check_held(owner: str, way: str, body: NamedShape, held: Held) -> None:
    """Raise FeatureError when ``body`` turned a face a holding rule keeps (D798)."""
    from fdcad.core.features.direct import short_name as short

    for name, before, rule in held:
        after = body.face(name)
        if before is None or after is None:
            continue
        now = facing(after)
        if now is None or sum(a * b for a, b in zip(before, now, strict=True)) < 1 - 1e-9:
            raise FeatureError(
                f"{owner}: {HOLD_LABELS.get(rule, rule)} holds {short(name)}, and {way} would "
                "turn it. Choose another way for the neighbours or untick the rule.",
                highlight=[name],
            )


@dataclass
class Motion:
    """What a move does: a rigid transform plus where its handles sit."""

    trsf: gp_Trsf
    issues: list[Issue] = field(default_factory=list)


def _require(feature: Feature, name: str) -> None:
    if name not in feature.params:
        raise FeatureError(
            f"{feature.name}: the {value_label(name)} value is missing. Enter a value."
        )


def fit_gap(feature: Feature) -> float:
    """How far a printing fit preset moves Offset faces into the material (D413)."""
    fit = str(feature.params.get("print_fit", "none"))
    if fit == "none":
        return 0.0
    found = feature.params.get("fit_tolerance")
    tol = found.value if isinstance(found, Param) else hole_data.DEFAULT_FIT_TOLERANCE
    return hole_data.fit_offset(fit, tol) / 2.0


@register
class MoveFace(FeatureType):
    """Moves faces of the part; the faces around them stretch so the body stays closed."""

    type_name = "move_face"
    makes_solid = True
    params = (
        ParamSpec("mode", choices=MODES, default="offset"),
        ParamSpec("distance", kind=Kind.LENGTH, optional=True),
        ParamSpec("reverse", default=False, optional=True),
        ParamSpec("copy", default=False, optional=True),
        ParamSpec("translate_by", choices=TRANSLATE_BY, optional=True),
        ParamSpec("dx", kind=Kind.LENGTH, optional=True),
        ParamSpec("dy", kind=Kind.LENGTH, optional=True),
        ParamSpec("dz", kind=Kind.LENGTH, optional=True),
        ParamSpec("rotate_by", choices=ROTATE_BY, optional=True),
        ParamSpec("angle", kind=Kind.ANGLE, optional=True),
        ParamSpec("rx", kind=Kind.ANGLE, optional=True),
        ParamSpec("ry", kind=Kind.ANGLE, optional=True),
        ParamSpec("rz", kind=Kind.ANGLE, optional=True),
        ParamSpec("ox", kind=Kind.LENGTH, optional=True),
        ParamSpec("oy", kind=Kind.LENGTH, optional=True),
        ParamSpec("oz", kind=Kind.LENGTH, optional=True),
        ParamSpec("print_fit", choices=hole_data.PRINT_FITS, optional=True),
        ParamSpec("fit_tolerance", kind=Kind.LENGTH, optional=True),
        *(ParamSpec(f"rule_{r}", default=False, optional=True) for r in RULES),  # TR263
        ParamSpec("suspend_rules", default=False, optional=True),
        ParamSpec("diameter", kind=Kind.LENGTH, optional=True),  # TR265
        ParamSpec("set_size", kind=Kind.LENGTH, optional=True),
        ParamSpec("offset_by", choices=("distance", "measured"), optional=True),
        ParamSpec("follow", choices=FOLLOW, optional=True),  # TR264
        ParamSpec("keep_solution", default=False, optional=True),
        ParamSpec("rounds", choices=ROUNDS, optional=True),
        ParamSpec("cone_angle", kind=Kind.ANGLE, optional=True),  # TR265 (D799)
        ParamSpec("symmetric", default=False, optional=True),  # TR265 item 3 (D800)
        ParamSpec("lock_size", default=False, optional=True),
        ParamSpec("keep_end", choices=("large", "small"), optional=True),
        ParamSpec("reapply_fillets", default=False, optional=True),  # TR259 (D1420)
    )

    def validate(self, feature: Feature) -> None:
        """Check that the values the chosen mode needs are there."""
        super().validate(feature)
        mode = str(feature.params.get("mode", "offset"))
        needs_distance = ("direction", "offset_from_face")
        if mode == "resize":
            if not isinstance(feature.params.get("cone_angle"), Param):
                _require(feature, "diameter")
        elif mode == "offset" and isinstance(feature.params.get("set_size"), Param):
            pass  # the distance comes from the measured size (TR265)
        elif mode == "offset" or (mode == "translate" and _translate_by(feature) in needs_distance):
            _require(feature, "distance")
        elif mode == "rotate" and _rotate_by(feature) == "axis":
            _require(feature, "angle")
        if mode == "offset" and feature.params.get("copy") is True:
            raise FeatureError(
                f"{feature.name}: Copy works with Translate and Rotate only. "
                "Turn off Copy or choose one of these."
            )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Move the faces and check the result. When several faces fail together, the
        ones that fail on their own are named, with a fix that keeps the others (TR400)."""
        try:
            body, issues = self.moved(feature, ctx)
        except FeatureError as exc:
            from fdcad.core.features import partial

            if exc.fixes:
                raise
            failed = partial.failing_refs(feature, "faces", lambda one: self.moved(one, ctx))
            if failed is None:
                raise
            raise partial.drop_error(feature, "faces", failed, exc) from exc
        issues += check_result(feature.id, feature.name, ctx.body, body, None)
        return FeatureResult(body=body, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The part after the move, for the live preview: moved faces in the accent
        colour, faces held still and faces that stretch in their own (TR263 item 2)."""
        from fdcad.core.features.modify import ResultPreview

        result = self.moved(feature, ctx)[0]
        if ctx.body is None:
            return result
        moved, held, stretched = _three_kinds(ctx.body, result, feature, ctx, self)
        return ResultPreview(
            result.shape,
            result.faces,
            full=result.shape,
            accent=moved,
            held=held,
            stretched=stretched,
        )

    def preview_info(self, feature: Feature, ctx: BuildContext) -> dict[str, float]:
        """How many faces each ticked rule adds or holds, for the panel (TR263 item 2)."""
        if ctx.body is None:
            return {}
        try:
            faces, _labels, _issues = resolve_faces(ctx, feature.refs.get("faces"), feature.name)
            found = self.rule_finds(feature, ctx, faces)
        except FeatureError:
            return {}
        if found is None:
            return {}
        added, held, _more = found
        out = {f"rule:{r}": 0.0 for r in active_rules(feature.params)}
        for _n, _f, rule in [*added, *held]:
            out[f"rule:{rule}"] = out.get(f"rule:{rule}", 0.0) + 1.0
        return out

    def moved(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        """The part with the faces moved, plus warnings. Raises FeatureError.

        With Reapply Fillets (TR259, D1420) the rounds next to the faces are removed
        first and made again after."""
        from fdcad.core.features import reapply_fillets as reapply

        if reapply.wanted(feature) and ctx.body is not None and feature.refs.get("faces"):
            picked, _labels, _issues = resolve_faces(ctx, feature.refs.get("faces"), feature.name)
            return reapply.around(feature, ctx, picked, lambda c: self._moved(feature, c))
        return self._moved(feature, ctx)

    def _moved(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        name = feature.name
        if ctx.body is None:
            raise FeatureError(f"{name}: the part is empty. Add a body first.")
        faces, labels, issues = resolve_faces(ctx, feature.refs.get("faces"), name)
        faces, labels, issues, held = self._with_rules(feature, ctx, faces, labels, issues)
        factors = [1.0] * len(faces)
        for face, label, factor in self.locked_partners(feature, ctx, faces):  # D800
            faces, labels, factors = [*faces, face], [*labels, label], [*factors, factor]
        from fdcad.core.features.face_relation import partners

        for face, label, factor in partners(feature, ctx, faces):  # kept relations (D2418)
            faces, labels, factors = [*faces, face], [*labels, label], [*factors, factor]
        remake = feature.params.get("rounds") == "remake" and feature.params.get("copy") is not True
        if not remake:
            return self._moved_on(feature, ctx, ctx.body, faces, labels, issues, held, factors)
        base, faces, plan = strip_rounds(ctx.body, faces, labels, feature.id, name)
        body, issues = self._moved_on(feature, ctx, base, faces, labels, issues, held, factors)
        return remake_rounds(body, plan, feature.id, name), issues

    def _moved_on(
        self,
        feature: Feature,
        ctx: BuildContext,
        base: NamedShape,
        faces: list[TopoDS_Face],
        labels: list[str],
        issues: list[Issue],
        held: Held = (),
        factors: list[float] | None = None,
    ) -> tuple[NamedShape, list[Issue]]:
        """Move ``faces`` of ``base`` (the part, or the part with its rounds taken off).
        ``factors`` scales each face's Offset distance (a locked size's other face, D800)."""
        name = feature.name
        mode = str(feature.params.get("mode", "offset"))
        if mode == "resize":
            return self._resize(feature, base, faces, labels), issues
        if mode == "offset":
            if isinstance(feature.params.get("set_size"), Param):
                distance = measured_move(feature, ctx, faces[:1])
                if feature.params.get("symmetric") is True:  # both faces, half each (D800)
                    other, other_label = symmetric_partner(feature, ctx, faces[0])
                    distance /= 2
                    faces, labels = [*faces, other], [*labels, other_label]
                    factors = [*(factors or [1.0] * (len(faces) - 1)), 1.0]
            else:
                distance = self.number(feature, "distance")
                if feature.params.get("reverse") is True:
                    distance = -distance
            distance -= fit_gap(feature)
            scale = factors if factors is not None and len(factors) == len(faces) else None
            moves = [(f, distance * (scale[i] if scale else 1.0)) for i, f in enumerate(faces)]
            whole = base

            def extend() -> NamedShape:
                return on_own_bodies(
                    whole,
                    faces,
                    feature.id,
                    lambda b: offset_faces(b, moves, feature.id, name, labels),
                )

            ways = {"extend": extend, **self._other_ways(feature, whole, faces, labels, moves)}
            return self._follow(feature, ways, issues, held)
        motion = self.motion(feature, ctx)
        issues = issues + motion.issues
        trsf = motion.trsf
        if feature.params.get("copy") is True:
            copied = on_own_bodies(
                base, faces, feature.id, lambda b: self._copy(b, faces, labels, trsf, feature)
            )
            return copied, issues
        whole = base

        def extend_move() -> NamedShape:
            return on_own_bodies(
                whole,
                faces,
                feature.id,
                lambda b: self._move(b, faces, labels, trsf, feature, mode),
            )

        ways = {
            "extend": extend_move,
            **self._other_ways(feature, whole, faces, labels, None, trsf),
        }
        return self._follow(feature, ways, issues, held)

    def locked_partners(
        self, feature: Feature, ctx: BuildContext, faces: list[TopoDS_Face]
    ) -> list[tuple[TopoDS_Face, str, float]]:
        """The other face of each locked size (an earlier Move Face set to a measured size
        with Lock) whose one face this move picks: it joins the move, so the size holds
        (TR265 item 3, D800). With each: its label and its Offset factor (the dot of the two
        faces' normals, so it moves the same way)."""
        if ctx.body is None:
            return []
        order = [f.id for f in ctx.document.features]
        mine = order.index(feature.id) if feature.id in order else len(order)
        picked = {ctx.body.primary_name(f) for f in faces}
        out: list[tuple[TopoDS_Face, str, float]] = []
        for earlier in ctx.document.features[:mine]:
            if earlier.type != "move_face" or earlier.suppressed:
                continue
            if earlier.params.get("lock_size") is not True:
                continue
            pair = _locked_pair(earlier)
            if pair is None:
                continue
            for here, there in (pair, pair[::-1]):
                if here not in picked or there in picked:
                    continue
                a, b = ctx.body.face(here), ctx.body.face(there)
                if a is None or b is None or any(b.IsSame(f) for f, _l, _k in out):
                    continue
                na, nb = outward_normal(a), outward_normal(b)
                if na is None or nb is None or abs(abs(dot(na, nb)) - 1.0) > 1e-6:
                    continue
                out.append((b, short_name(there), dot(na, nb)))
        return out

    def _resize(
        self, feature: Feature, base: NamedShape, faces: list[TopoDS_Face], labels: list[str]
    ) -> NamedShape:
        """Resize: cones to the typed angle, keeping one end (D799), then the other round
        faces to the typed diameter (D789)."""
        from fdcad.core.features.cone_resize import is_cone

        name, fid = feature.name, feature.id
        cones = [(f, n) for f, n in zip(faces, labels, strict=False) if is_cone(f)]
        rest = [(f, n) for f, n in zip(faces, labels, strict=False) if not is_cone(f)]
        body = base
        if cones:
            angle = feature.params.get("cone_angle")
            if not isinstance(angle, Param):
                raise FeatureError(
                    f"{name}: {short_name(cones[0][1])} is a cone. Type the cone angle.",
                    highlight=[cones[0][1]],
                )
            keep = str(feature.params.get("keep_end", "large"))
            names = [base.primary_name(f) for f, _n in cones]
            for (face, label), face_name in zip(cones, names, strict=True):
                current = body.face(face_name) if face_name is not None else face
                if current is None:
                    raise FeatureError(
                        f"{name}: {short_name(label)} was lost. Pick it again.", highlight=[label]
                    )
                body = on_own_bodies(
                    body, [current], fid, _cone_edit(current, angle.value, keep, fid, name, label)
                )
        if not rest:
            return body
        if not isinstance(feature.params.get("diameter"), Param):
            raise FeatureError(
                f"{name}: {short_name(rest[0][1])} is round. Type the diameter.",
                highlight=[rest[0][1]],
            )
        names = [base.primary_name(f) for f, _n in rest]
        now = [body.face(n) if n is not None else f for (f, _l), n in zip(rest, names, strict=True)]
        faces2 = [f for f in now if f is not None]
        labels2 = [n for (_f, n), f in zip(rest, now, strict=True) if f is not None]
        moves = resize_moves(feature, faces2, labels2)
        return on_own_bodies(
            body, faces2, fid, lambda b: offset_faces(b, moves, fid, name, labels2)
        )

    def _other_ways(
        self,
        feature: Feature,
        whole: NamedShape,
        faces: list[TopoDS_Face],
        labels: list[str],
        offsets: list[tuple[TopoDS_Face, float]] | None,
        trsf: gp_Trsf | None = None,
    ) -> dict[str, Callable[[], NamedShape]]:
        """Tip and Lift for this move (TR264): Offset gives each face its own move along
        its normal; Translate and Rotate give one transform."""
        from OCP.gp import gp_Vec

        name, fid = feature.name, feature.id

        def vectors() -> list[Vec3]:
            if offsets is not None:
                out = []
                for face, d in offsets:
                    n = outward_normal(face)
                    if n is None:
                        raise FeatureError(
                            f"{name}: Tip and Lift move flat faces only. Choose Extend.",
                            highlight=labels,
                        )
                    out.append((n[0] * d, n[1] * d, n[2] * d))
                return out
            assert trsf is not None
            if trsf.Form() != 2:  # gp_Translation: Lift sweeps along a straight move
                raise FeatureError(
                    f"{name}: Lift works with Translate and Offset only. Choose Extend or Tip.",
                    highlight=labels,
                )
            v = trsf.TranslationPart()
            return [(v.X(), v.Y(), v.Z())] * len(faces)

        def one_transform() -> gp_Trsf:
            if trsf is not None:
                return trsf
            moves = vectors()
            if any(max(abs(a - b) for a, b in zip(m, moves[0], strict=True)) > 1e-9 for m in moves):
                raise FeatureError(
                    f"{name}: Tip moves the picked faces together, but these faces face different "
                    "ways. Pick faces that face the same way, or choose Extend.",
                    highlight=labels,
                )
            out = gp_Trsf()
            out.SetTranslation(gp_Vec(*moves[0]))
            return out

        def tip() -> NamedShape:
            return on_own_bodies(
                whole, faces, fid, lambda b: tip_faces(b, faces, one_transform(), fid, name, labels)
            )

        def lift() -> NamedShape:
            return on_own_bodies(
                whole, faces, fid, lambda b: lift_faces(b, faces, vectors(), fid, name, labels)
            )

        return {"tip": tip, "lift": lift}

    def _follow(
        self,
        feature: Feature,
        ways: dict[str, Callable[[], NamedShape]],
        issues: list[Issue],
        held: Held = (),
    ) -> tuple[NamedShape, list[Issue]]:
        """Build the chosen way; when it fails, try the others unless Keep This Solution is
        on, and say which one was used (TR264 item 2)."""
        chosen = str(feature.params.get("follow", "extend"))
        keep = feature.params.get("keep_solution") is True
        first: FeatureError | None = None
        for way in follow_order(chosen):
            try:
                body = ways[way]()
                _check_held(feature.name, FOLLOW_LABELS[way], body, held)
            except FeatureError as exc:
                first = first or exc
                if keep:
                    raise
                continue
            if way != chosen and first is not None:
                issues = [
                    *issues,
                    Issue(
                        FeatureState.WARNING,
                        f"{feature.name}: {FOLLOW_LABELS[chosen]} did not work ({first}). "
                        f"Used {FOLLOW_LABELS[way]} instead. Tick Keep This Solution to make "
                        "this an error.",
                        code="follow_changed",
                    ),
                ]
            return body, issues
        assert first is not None
        raise first

    def _with_rules(
        self,
        feature: Feature,
        ctx: BuildContext,
        faces: list[TopoDS_Face],
        labels: list[str],
        issues: list[Issue],
    ) -> tuple[list[TopoDS_Face], list[str], list[Issue], Held]:
        """The picked faces plus the faces the ticked rules add (TR263), and the faces
        the holding rules keep facing the same way, with their direction (D798)."""
        found = self.rule_finds(feature, ctx, faces)
        if found is None:
            return faces, labels, issues, ()
        added, held, more = found
        return (
            faces + [f for _n, f, _r in added],
            labels + [short_name(n) for n, _f, _r in added],
            issues + more,
            tuple((n, facing(f), r) for n, f, r in held),
        )

    def rule_finds(
        self, feature: Feature, ctx: BuildContext, faces: list[TopoDS_Face]
    ) -> (
        tuple[list[tuple[str, TopoDS_Face, str]], list[tuple[str, TopoDS_Face, str]], list[Issue]]
        | None
    ):
        """What the ticked rules add and hold, with warnings; None with no rule on."""
        rules = active_rules(feature.params)
        if not rules or ctx.body is None:
            return None
        issues: list[Issue] = []
        exclude: list[TopoDS_Face] = []
        if feature.refs.get("rule_exclude"):
            exclude, _l, more = resolve_faces(ctx, feature.refs.get("rule_exclude"), feature.name)
            issues += more
        exclude_by: dict[str, list[TopoDS_Face]] = {}
        for rule in rules:
            refs = feature.refs.get(f"rule_exclude_{rule}")
            if refs:
                exclude_by[rule], _l, more = resolve_faces(ctx, refs, feature.name)
                issues += more
        mode = str(feature.params.get("mode", "offset"))
        if "symmetric" in rules and mode not in ("offset", "resize"):
            rules = [r for r in rules if r != "symmetric"]
            issues.append(
                Issue(
                    FeatureState.WARNING,
                    f"{feature.name}: Keep symmetry works with Offset and Resize. It was left "
                    "out of this move.",
                    code="rule_skipped",
                )
            )
        mirrors = MAIN_PLANES
        if feature.refs.get("symmetry_plane"):
            place = resolve_placement(ctx, feature.refs["symmetry_plane"], feature.name, "plane")
            issues += place.issues
            mirrors = ((place.point, place.direction),)
        added = rule_faces(ctx.body, faces, rules, exclude, exclude_by, mirrors)
        moved = faces + [f for _n, f, _r in added]
        held = held_faces(ctx.body, moved, rules, exclude, exclude_by)
        return added, held, issues

    def _move(
        self,
        body: NamedShape,
        faces: list[TopoDS_Face],
        labels: list[str],
        trsf: gp_Trsf,
        feature: Feature,
        mode: str,
    ) -> NamedShape:
        """Try each method that fits, check the faces landed where asked, keep the first."""
        name = feature.name
        flat = all(outward_normal(f) is not None for f in faces)

        def by_offsets() -> NamedShape:
            v = trsf.TranslationPart()
            delta = (v.X(), v.Y(), v.Z())
            offsets = [(f, dot(delta, _normal(f))) for f in faces]
            return offset_faces(body, offsets, feature.id, name, labels)

        def by_volumes() -> NamedShape:
            patched, added, removed = feature_volumes(body, faces, feature.id, name, labels)
            result = move_volumes(patched, added, removed, [trsf], feature.id, name, "moved")
            if len(solids(result.shape)) != len(solids(body.shape)):
                raise FeatureError(
                    f"{name} failed: the moved faces no longer join the body. Move them less far.",
                    highlight=labels,
                )
            return rename_moved(result, body, faces, trsf)

        def by_tilt() -> NamedShape:
            return tilt_faces(body, faces, trsf, feature.id, name, labels)

        methods = []
        if flat and mode == "translate":
            methods.append(by_offsets)
        methods.append(by_volumes)
        if flat and mode == "rotate":
            methods.append(by_tilt)
        first: FeatureError | None = None
        for method in methods:
            try:
                result = method()
            except FeatureError as exc:
                first = first or exc
                continue
            if on_target(result, body, faces, trsf):
                return result
            first = first or FeatureError(
                f"{name} failed: the faces around {', '.join(labels)} cannot follow the move. "
                "Use a smaller value or pick the whole feature.",
                highlight=labels,
            )
        assert first is not None
        raise first

    def _copy(
        self,
        body: NamedShape,
        faces: list[TopoDS_Face],
        labels: list[str],
        trsf: gp_Trsf,
        feature: Feature,
    ) -> NamedShape:
        name = feature.name
        try:
            _patched, added, removed = feature_volumes(body, faces, feature.id, name, labels)
        except FeatureError:
            raise FeatureError(
                f"{name}: Copy needs faces that form a whole feature, such as every face of a "
                "boss or a hole. Pick the rest of its faces.",
                highlight=labels,
            ) from None
        result = move_volumes(body, added, removed, [trsf], feature.id, name, "copy")
        result = rename_moved(result, body, faces, trsf, prefix=f"{feature.id}/copy1/")
        if len(solids(result.shape)) != len(solids(body.shape)):
            raise FeatureError(
                f"{name} failed: the copy does not join the body. Move it less far so it touches.",
                highlight=labels,
            )
        return result

    # Motion -----------------------------------------------------------------------

    def motion(self, feature: Feature, ctx: BuildContext) -> Motion:
        """The rigid transform of Translate or Rotate."""
        if str(feature.params.get("mode")) == "rotate":
            return self._rotation(feature, ctx)
        return self._translation(feature, ctx)

    def _rotation(self, feature: Feature, ctx: BuildContext) -> Motion:
        name = feature.name
        if _rotate_by(feature) == "axis":
            axis = resolve_placement(ctx, feature.refs.get("axis"), name, "axis")
            angle = self.number(feature, "angle")
            if feature.params.get("reverse") is True:
                angle = -angle
            return Motion(rotation(axis.point, axis.direction, angle), axis.issues)
        origin = tuple(_value(feature, k) for k in ("ox", "oy", "oz"))
        trsf = gp_Trsf()
        for key, direction in (("rx", (1.0, 0, 0)), ("ry", (0, 1.0, 0)), ("rz", (0, 0, 1.0))):
            angle = _value(feature, key)
            if angle:
                trsf = rotation(origin, direction, angle).Multiplied(trsf)  # type: ignore[arg-type]
        return Motion(trsf)

    def _translation(self, feature: Feature, ctx: BuildContext) -> Motion:
        name = feature.name
        how = _translate_by(feature)
        sign = -1.0 if feature.params.get("reverse") is True else 1.0
        if how == "delta":
            delta = tuple(_value(feature, k) for k in ("dx", "dy", "dz"))
            return Motion(translation(delta))  # type: ignore[arg-type]
        if how == "direction":
            d = resolve_placement(ctx, feature.refs.get("direction"), name, "direction")
            distance = self.number(feature, "distance") * sign
            return Motion(translation(scaled(d.direction, distance)), d.issues)
        start = self._start(feature, ctx)
        if how == "up_to_vertex":
            target = resolve_placement(ctx, feature.refs.get("to"), name, "point")
            if start.kind == "point":
                return Motion(translation(minus(target.point, start.point)), target.issues)
            gap = dot(minus(target.point, start.point), start.normal)
            return Motion(translation(scaled(start.normal, gap)), target.issues)
        if how in ("up_to_face", "offset_from_face"):
            target = resolve_placement(ctx, feature.refs.get("to"), name, "plane")
            if start.kind == "point":
                raise FeatureError(f"{name}: start from a face or plane for Up to Face.")
            if abs(abs(dot(target.direction, start.normal)) - 1.0) > 1e-6:
                raise FeatureError(
                    f"{name}: the target face is not parallel to the moved face. "
                    "Pick a parallel face or plane, or use Up to Vertex."
                )
            gap = dot(minus(target.point, start.point), start.normal)
            if how == "offset_from_face":
                extra = self.number(feature, "distance") * sign
                # Stop ``distance`` short of the target, on the side the face is on now.
                gap = gap - extra if gap >= 0 else gap + extra
            return Motion(translation(scaled(start.normal, gap)), target.issues)
        # Up to Body: along the start normal until the faces touch the body.
        return self._up_to_body(feature, ctx, start)

    @dataclass
    class _Start:
        kind: str
        point: Vec3
        normal: Vec3

    def _start(self, feature: Feature, ctx: BuildContext) -> MoveFace._Start:
        name = feature.name
        ref = feature.refs.get("from")
        if ref is None:
            faces, _labels, _issues = resolve_faces(ctx, feature.refs.get("faces"), name)
            normal = outward_normal(faces[0])
            if normal is None:
                raise FeatureError(
                    f"{name}: the first picked face is curved. Pick a flat face as From."
                )
            return MoveFace._Start("plane", centroid(faces[0]), normal)
        if isinstance(ref, dict) and ref.get("kind") == "vertex":
            p = resolve_placement(ctx, ref, name, "point")
            return MoveFace._Start("point", p.point, p.direction)
        p = resolve_placement(ctx, ref, name, "plane")
        return MoveFace._Start("plane", p.point, p.direction)

    def _up_to_body(self, feature: Feature, ctx: BuildContext, start: _Start) -> Motion:
        from fdcad.core.features.bodies import body_of_ref

        name = feature.name
        assert ctx.body is not None
        target, issues = body_of_ref(ctx, feature.refs.get("body"), name)
        faces, _labels, _ = resolve_faces(ctx, feature.refs.get("faces"), name)
        from fdcad.core.features.solids import compound

        mine = extent_along(compound(list(faces)), start.normal)
        theirs = extent_along(target, start.normal)
        if mine is None or theirs is None:
            raise FeatureError(f"{name}: Up to Body found nothing to reach. Pick another body.")
        gap = theirs[0] - mine[1]
        if gap < -1e-9:
            gap = theirs[1] - mine[0]
        return Motion(translation(scaled(start.normal, gap)), issues)

    # Preview handles --------------------------------------------------------------

    def preview_handles(self, feature: Feature, ctx: BuildContext) -> list[PreviewHandle]:
        """Transform handles: an arrow for distances, rings for angles (P3.1.1 item 6)."""
        if ctx.body is None:
            return []
        try:
            faces, _labels, _ = resolve_faces(ctx, feature.refs.get("faces"), feature.name)
        except FeatureError:
            return []
        from fdcad.core.features.solids import compound

        group = compound(list(faces))
        base = centroid(group) if len(faces) > 1 else centroid(faces[0])
        size = bounding_size(ctx.body.shape)
        step = ruler_step(size)
        mode = str(feature.params.get("mode", "offset"))
        sign = -1.0 if feature.params.get("reverse") is True else 1.0
        handles: list[PreviewHandle] = []
        if mode == "offset" and isinstance(feature.params.get("set_size"), Param):
            arrow = _size_handle(feature, ctx, faces[0], step)  # TR265 item 3 (D800)
            if arrow is not None:
                handles.append(arrow)
        elif mode == "offset":
            normal = outward_normal(faces[0]) or (0.0, 0.0, 1.0)
            direction = scaled(normal, sign)
            value = abs(_value(feature, "distance"))
            handles.append(PreviewHandle("distance", base, direction, value, step=step, flips=True))
        elif mode == "translate" and _translate_by(feature) == "direction":
            try:
                d = resolve_placement(ctx, feature.refs.get("direction"), feature.name, "direction")
            except FeatureError:
                return []
            value = abs(_value(feature, "distance"))
            handles.append(
                PreviewHandle(
                    "distance", base, scaled(d.direction, sign), value, step=step, flips=True
                )
            )
        elif mode == "translate" and _translate_by(feature) == "delta":
            for key, unit in zip(("dx", "dy", "dz"), _UNITS, strict=True):
                value = _value(feature, key)
                direction = scaled(unit, -1.0 if value < 0 else 1.0)
                handles.append(
                    PreviewHandle(key, base, direction, abs(value), step=step, flips=True)
                )
        elif mode == "rotate" and _rotate_by(feature) == "axis":
            try:
                axis = resolve_placement(ctx, feature.refs.get("axis"), feature.name, "axis")
            except FeatureError:
                return []
            handles.append(
                PreviewHandle(
                    "angle",
                    base,
                    scaled(axis.direction, sign),
                    abs(_value(feature, "angle")),
                    centre=axis.point,
                    step=ANGLE_RULER_STEP,
                    flips=True,
                )
            )
        elif mode == "rotate":
            origin: Vec3 = (_value(feature, "ox"), _value(feature, "oy"), _value(feature, "oz"))
            for key, unit in zip(("rx", "ry", "rz"), _UNITS, strict=True):
                value = _value(feature, key)
                direction = scaled(unit, -1.0 if value < 0 else 1.0)
                ring_base = _off_axis(base, origin, unit, size)
                handles.append(
                    PreviewHandle(
                        key,
                        ring_base,
                        direction,
                        abs(value),
                        centre=origin,
                        step=ANGLE_RULER_STEP,
                        flips=True,
                    )
                )
        return handles


_UNITS: tuple[Vec3, Vec3, Vec3] = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def resize_moves(
    feature: Feature, faces: list[TopoDS_Face], labels: list[str]
) -> list[tuple[TopoDS_Face, float]]:
    """The offset of each round face that gives it the typed diameter (TR265)."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cone

    from fdcad.core.features.direct import radius_after

    target = _value(feature, "diameter") / 2.0
    if target <= 0:
        raise FeatureError(f"{feature.name}: the diameter must be more than 0. Type a size.")
    out = []
    for face, label in zip(faces, labels, strict=False):
        now = radius_after(face, 0.0)
        if now is None or BRepAdaptor_Surface(face).GetType() == GeomAbs_Cone:  # D799
            raise FeatureError(
                f"{feature.name}: {short_name(label)} is not a cylinder, sphere or torus. "
                "Pick round faces, or use Offset.",
                highlight=[label],
            )
        step = (radius_after(face, 1.0) or now) - now  # +1 or -1: which way grows it
        out.append((face, (target - now) / step))
    return out


def _point_of(shape: object) -> Vec3:
    """A vertex's point, a round edge's centre, an edge's middle or a face's centroid."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GeomAbs import GeomAbs_Circle
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_VERTEX
    from OCP.TopoDS import TopoDS

    from fdcad.core.naming.names import centroid

    kind = shape.ShapeType()  # type: ignore[attr-defined]
    if kind == TopAbs_VERTEX:
        p = BRep_Tool.Pnt_s(TopoDS.Vertex(shape))
        return (p.X(), p.Y(), p.Z())
    if kind == TopAbs_EDGE:
        curve = BRepAdaptor_Curve(TopoDS.Edge(shape))
        if curve.GetType() == GeomAbs_Circle:
            c = curve.Circle().Location()
        else:
            c = curve.Value((curve.FirstParameter() + curve.LastParameter()) / 2)
        return (c.X(), c.Y(), c.Z())
    return centroid(TopoDS.Face(shape))


def measured_move(feature: Feature, ctx: BuildContext, faces: list[TopoDS_Face]) -> float:
    """How far the one flat face moves so it ends ``set_size`` from ``size_from`` (TR265)."""
    if len(faces) != 1 or outward_normal(faces[0]) is None:
        raise FeatureError(f"{feature.name}: Set Size moves one flat face. Pick one flat face.")
    ref = feature.refs.get("size_from")
    if isinstance(ref, list):
        ref = ref[0] if ref else None
    if not isinstance(ref, dict):
        raise FeatureError(f"{feature.name}: Set Size needs an item to measure from. Pick one.")
    from fdcad.core.naming.resolve import resolve_edge, resolve_face, resolve_vertex

    if ctx.body is None:
        raise FeatureError(f"{feature.name}: the part is empty. Add a body first.")
    if ref.get("kind") == "vertex":
        q, _issues = resolve_vertex(ctx.body, ref, feature.name)
    else:
        resolver = resolve_edge if ref.get("kind") == "edge" else resolve_face
        other, _issues = resolver(ctx.body, ref, feature.name)
        q = _point_of(other)
    from fdcad.core.naming.names import centroid

    n = _normal(faces[0])
    p = centroid(faces[0])
    now = dot((q[0] - p[0], q[1] - p[1], q[2] - p[2]), n)  # > 0: the item is in front
    target = _value(feature, "set_size")
    if target < 0:
        raise FeatureError(f"{feature.name}: the size cannot be negative. Type a size.")
    # In front: moving out brings the face nearer. Behind: moving out takes it away.
    return now - target if now > 0 else target + now


def _off_axis(base: Vec3, origin: Vec3, axis: Vec3, size: float) -> Vec3:
    """``base``, or a point beside the axis when ``base`` lies on it (a ring needs a radius)."""
    rel = minus(base, origin)
    along = dot(rel, axis)
    radial = minus(rel, scaled(axis, along))
    if math.sqrt(dot(radial, radial)) > 1e-6:
        return base
    other = (0.0, 1.0, 0.0) if abs(axis[1]) < 0.9 else (1.0, 0.0, 0.0)
    return (
        base[0] + other[0] * size * 0.25,
        base[1] + other[1] * size * 0.25,
        base[2] + other[2] * size * 0.25,
    )


def _normal(face: object) -> Vec3:
    normal = outward_normal(face)
    assert normal is not None
    return normal


def _value(feature: Feature, name: str) -> float:
    from fdcad.core.document.model import Param

    value = feature.params.get(name)
    return value.value if isinstance(value, Param) else 0.0


def _translate_by(feature: Feature) -> str:
    return str(feature.params.get("translate_by", "direction"))


def _rotate_by(feature: Feature) -> str:
    return str(feature.params.get("rotate_by", "axis"))


__all__ = ["MODES", "ROTATE_BY", "TRANSLATE_BY", "MoveFace", "patch"]


def _three_kinds(
    before: NamedShape, after: NamedShape, feature: Feature, ctx: BuildContext, ftype: MoveFace
) -> tuple[list[TopoDS_Face], list[TopoDS_Face], list[TopoDS_Face]]:
    """Faces of ``after`` that moved, that stay still next to them, and that stretched."""
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp

    from fdcad.core.naming.resolve import _matches, face_snapshot
    from fdcad.core.occ import ShapeListMap, ShapeMap, shape_list

    faces, _l, _i = resolve_faces(ctx, feature.refs.get("faces"), feature.name)
    names = {before.primary_name(f) for f in faces}
    found = ftype.rule_finds(feature, ctx, faces)
    if found is not None:
        names |= {n for n, _f, _r in found[0]}
    moved_map = ShapeMap()
    moved = []
    for name, face in after.faces:
        if name in names and not moved_map.Contains(face):
            moved_map.Add(face)
            moved.append(face)
    amap = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(after.shape, TopAbs_EDGE, TopAbs_FACE, amap)
    near = ShapeMap()
    for i in range(1, amap.Extent() + 1):
        around = shape_list(amap.FindFromIndex(i))
        if any(moved_map.Contains(f) for f in around):
            for f in around:
                if not moved_map.Contains(f):
                    near.Add(f)
    held, stretched = [], []
    for i in range(1, near.Extent() + 1):
        face = TopoDS.Face(near.FindKey(i))
        own = after.primary_name(face)
        old = before.face(own) if own is not None else None
        if old is not None and _matches(face_snapshot(old), face_snapshot(face)):
            held.append(face)
        else:
            stretched.append(face)
    return moved, held, stretched


def _cone_edit(
    face: TopoDS_Face, angle: float, keep: str, fid: str, name: str, label: str
) -> Callable[[NamedShape], NamedShape]:
    """The edit that gives one cone face its new angle (D799)."""
    from fdcad.core.features.cone_resize import resize_cone

    def run(body: NamedShape) -> NamedShape:
        return resize_cone(body, face, angle, keep, fid, name, short_name(label))

    return run


def _locked_pair(feature: Feature) -> tuple[str, str] | None:
    """The two face names a measured size of ``feature`` holds, or None (D800)."""
    if not isinstance(feature.params.get("set_size"), Param):
        return None
    faces = feature.refs.get("faces")
    other = feature.refs.get("size_from")
    if isinstance(other, list):
        other = other[0] if other else None
    if not isinstance(faces, list) or not faces or not isinstance(other, dict):
        return None
    first = faces[0]
    if not isinstance(first, dict) or other.get("kind") != "face":
        return None
    a, b = str(first.get("name", "")), str(other.get("name", ""))
    return (a, b) if a and b else None


def symmetric_partner(
    feature: Feature, ctx: BuildContext, face: TopoDS_Face
) -> tuple[TopoDS_Face, str]:
    """The measured from face, for Symmetric: a flat face facing the other way (D800)."""
    from fdcad.core.naming.resolve import resolve_face

    ref = feature.refs.get("size_from")
    if isinstance(ref, list):
        ref = ref[0] if ref else None
    if not isinstance(ref, dict) or ref.get("kind") != "face" or ctx.body is None:
        raise FeatureError(
            f"{feature.name}: Symmetric moves two faces, so measure from a flat face. "
            "Pick a face to measure from, or turn off Symmetric."
        )
    other, _issues = resolve_face(ctx.body, ref, feature.name)
    na, nb = outward_normal(face), outward_normal(other)
    if na is None or nb is None or dot(na, nb) > -1 + 1e-6:
        raise FeatureError(
            f"{feature.name}: Symmetric needs two flat faces opposite each other, such as "
            "the two sides of a slot or a plate. Pick such a face, or turn off Symmetric."
        )
    return other, short_name(str(ref.get("name", "")))


def _size_handle(
    feature: Feature, ctx: BuildContext, face: TopoDS_Face, step: float
) -> PreviewHandle | None:
    """The measured size as an arrow from the item measured from to the face that moves,
    so the arrow head shows which side moves; with Symmetric it starts from the middle
    and counts twice. Its label is edited in the view like any value (D800)."""
    from fdcad.core.naming.names import centroid as centre_of

    n = outward_normal(face)
    if n is None:
        return None
    try:
        now_move = measured_move(feature, ctx, [face])
    except FeatureError:
        return None
    p = centre_of(face)
    target = _value(feature, "set_size")
    # Where the face ends up, and the item's depth on the face's line.
    end = (p[0] + n[0] * now_move, p[1] + n[1] * now_move, p[2] + n[2] * now_move)
    symmetric = feature.params.get("symmetric") is True
    if symmetric:
        end = (p[0] + n[0] * now_move / 2, p[1] + n[1] * now_move / 2, p[2] + n[2] * now_move / 2)
    length = target / 2 if symmetric else target
    if length <= 1e-9:
        return None
    # The arrow runs from the fixed side to the moved face: its base is ``length`` back.
    away = scaled(n, -1.0)
    probe = (end[0] + away[0] * length, end[1] + away[1] * length, end[2] + away[2] * length)
    ref = feature.refs.get("size_from")
    if isinstance(ref, list):
        ref = ref[0] if ref else None
    behind = True
    if isinstance(ref, dict) and ctx.body is not None:
        try:
            q = _measured_point(ctx, ref, feature.name)
            behind = dot((q[0] - p[0], q[1] - p[1], q[2] - p[2]), n) < 0
        except FeatureError:
            pass
    if behind:
        base, direction = probe, n
    else:
        base = (end[0] + n[0] * length, end[1] + n[1] * length, end[2] + n[2] * length)
        direction = away
    return PreviewHandle(
        "set_size", base, direction, length, scale=2.0 if symmetric else 1.0, step=step
    )


def _measured_point(ctx: BuildContext, ref: dict[str, object], owner: str) -> Vec3:
    """The point a size is measured from: a vertex, or an edge's or face's own point."""
    from fdcad.core.naming.resolve import resolve_edge, resolve_face, resolve_vertex

    if ref.get("kind") == "vertex":
        q, _issues = resolve_vertex(ctx.body, ref, owner)
        return q
    resolver = resolve_edge if ref.get("kind") == "edge" else resolve_face
    other, _issues = resolver(ctx.body, ref, owner)
    return _point_of(other)
