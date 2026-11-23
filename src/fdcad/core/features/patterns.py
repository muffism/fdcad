"""Shared pattern and mirror engine (PHASE3_SPEC P3.2, P3.3, DECISIONS D234).

A pattern or mirror copies a seed to a list of placements. The seed is one of:

- ``refs.features``: earlier boss or cut features (``[{"feature": "f6"}]``).
  Each feature's own solid (the preview tool) is moved and added or cut again.
  With ``geometry`` on, the faces the feature made are copied instead.
- ``refs.faces``: faces that form a whole feature (a boss or a hole). The
  material they add or remove is found by patching them away, then copied.
- ``refs.bodies``: bodies (a face reference to any face of each body). Copies
  are new bodies; with ``merge`` on they are fused with the seed.

All copies of one seed go into one compound and one boolean (PLAN 11.3 item 4).
A copy that does not reach the part (it falls off the face it sits on) is an
error naming the copy; the fix "Skip copies" adds them to the skip list when
the user clicks it, and the other copies are kept (PLAN 5A items 5 and 6).

Instances are numbered ``(i, j)`` from 1: ``i`` along direction 1, ``j``
along direction 2 (1 when there is none). ``(1, 1)`` is the seed. Instances
to skip are stored in the feature's ``skip`` key as a list of ``[i, j]``
pairs (FDEF_SPEC 5.3.13).

Face roles: copies are named ``<fid>/instance<i>.<j>/<seed face name>`` for
feature and body seeds and ``<fid>/instance<i>.<j>/face#k`` for face seeds.
A mirror uses ``mirror<k>`` in place of ``instance<i>.<j>``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.gp import gp_Trsf
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import BuildContext, FeatureError, FeatureResult, Fix, Issue
from fdcad.core.features.bodies import body_indices, join, rest_of, sub_body
from fdcad.core.features.booleans import boolean_named, boolean_shape
from fdcad.core.features.direct import feature_volumes, resolve_faces
from fdcad.core.features.solids import compound, solids, volume_of
from fdcad.core.naming.names import NamedFace, NamedShape, faces_of, restrict

#: The fix action that adds instances to the skip list.
SKIP_INSTANCES = "skip_instances"
_TOUCH_TOL = 1e-4  # mm
_TINY = 1e-6


@dataclass
class Placement:
    """One copy: its instance index, its name role and its transform."""

    index: tuple[int, int]
    trsf: gp_Trsf
    role: str = ""

    def __post_init__(self) -> None:
        if not self.role:
            self.role = f"instance{self.index[0]}.{self.index[1]}"


@dataclass
class Outcome:
    """The patterned part plus warnings."""

    body: NamedShape
    issues: list[Issue] = field(default_factory=list)


def skipped(feature: Feature) -> set[tuple[int, int]]:
    """The instances the user chose to skip."""
    raw = feature.data.get("skip", [])
    out: set[tuple[int, int]] = set()
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, list) and len(item) == 2 and all(isinstance(v, int) for v in item):
                out.add((item[0], item[1]))
    return out


def _moved(shape: TopoDS_Shape, trsf: gp_Trsf) -> TopoDS_Shape:
    return BRepBuilderAPI_Transform(shape, trsf, True).Shape()


def _moved_named(named: NamedShape, trsf: gp_Trsf, prefix: str) -> NamedShape:
    maker = BRepBuilderAPI_Transform(named.shape, trsf, True)
    shape = maker.Shape()
    from OCP.TopoDS import TopoDS

    names = [(f"{prefix}/{n}", TopoDS.Face(maker.ModifiedShape(f))) for n, f in named.faces]
    return NamedShape(shape, restrict(names, shape, prefix))


def _touches(a: TopoDS_Shape, b: TopoDS_Shape) -> bool:
    try:
        dist = BRepExtrema_DistShapeShape(a, b)
        return bool(dist.IsDone() and dist.Value() <= _TOUCH_TOL)
    except Exception:
        return True  # let the boolean decide


def _overlaps(a: TopoDS_Shape, b: TopoDS_Shape) -> bool:
    common = boolean_shape("common", a, b)
    return common is not None and volume_of(common) > _TINY


#: What to change when copies fall off, by feature type (D603). Mirror has no spacing.
_CHANGE = {
    "mirror": "pick another mirror plane",
    "circular_pattern": "change the angle or the axis",
    "sketch_pattern": "move the sketch points",
    "table_pattern": "change the table",
}


def _fell_off(feature: Feature, failed: Sequence[tuple[int, int]], what: str) -> FeatureError:
    listed = ", ".join(f"{i}.{j}" if j > 1 else str(i) for i, j in failed)
    word = "Copy" if len(failed) == 1 else "Copies"
    change = _CHANGE.get(feature.type, "change the spacing")
    return FeatureError(
        f"{feature.name}: {word} {listed} {what}. "
        f"Skip those copies to keep the others, or {change}.",
        fixes=[
            Fix(
                "Skip copies that failed",
                SKIP_INSTANCES,
                {"feature": feature.id, "instances": [list(k) for k in failed]},
            )
        ],
    )


def sheet_seed_message(feature: Feature, seed_name: str) -> str:
    """Why a sheet metal feature cannot be mirrored or patterned, and what to do instead
    (audit E item 7.7, D711): copies would not be part of the sheet, so Flatten could
    not unfold them. Both the feature and the face pick give this same advice."""
    return (
        f"{feature.name}: {seed_name} is a sheet metal feature, and copies of it would not "
        "unfold with the sheet. Add the other flanges with Edge Flange (it takes several "
        "edges at once), or mirror the whole body if no flat pattern is needed."
    )


def _sheet_owner(ctx: BuildContext, names: Sequence[str]) -> str | None:
    """The name of the sheet metal feature (a flange, hem, tab and the like, not a cut
    made in the sheet) that made one of the face ``names``, if any."""
    from fdcad.core.features import REGISTRY

    for label in names:
        fid = label.split("/", 1)[0]
        try:
            seed = ctx.document.feature(fid)
        except KeyError:
            continue
        ftype = REGISTRY.get(seed.type)
        if ftype is not None and type(ftype).__module__.startswith(
            "fdcad.core.features.sheetmetal."
        ):
            return seed.name
    return None


def _no_copies(name: str, why: str) -> Issue:
    from fdcad.core.features.base import FeatureState

    return Issue(
        FeatureState.WARNING,
        f"{name}: {why}, so the part is unchanged. Raise the count or unsuppress the "
        "copied features to make copies.",
        code="no_copies",
    )


def _seed_ids(feature: Feature) -> list[str]:
    refs = feature.refs.get("features")
    if not isinstance(refs, list):
        return []
    return [r["feature"] for r in refs if isinstance(r, dict) and isinstance(r.get("feature"), str)]


def _all_seeds_off(feature: Feature, ctx: BuildContext) -> bool:
    """True when every picked seed feature is suppressed (TR345)."""
    seeds = _seed_ids(feature)
    found = [f for f in ctx.document.features if f.id in seeds]
    return bool(found) and len(found) == len(seeds) and all(f.suppressed for f in found)


def _seed_tools(feature: Feature, ctx: BuildContext) -> list[tuple[Feature, NamedShape, str]]:
    """Each seed feature with its own solid and operation ("boss" or "cut")."""
    from fdcad.core.features import REGISTRY
    from fdcad.core.features.preview import body_before

    refs = feature.refs.get("features")
    if not isinstance(refs, list) or not refs:
        return []
    out: list[tuple[Feature, NamedShape, str]] = []
    for ref in refs:
        fid = ref.get("feature") if isinstance(ref, dict) else None
        if not isinstance(fid, str):
            continue
        if any(f.id == fid and f.suppressed for f in ctx.document.features):
            continue  # a suppressed seed makes no copies (TR345)
        ctx.result(fid)  # raises when it is missing, later or failed
        seed = ctx.document.feature(fid)
        if _sheet_owner(ctx, [f"{fid}/"]) is not None:
            raise FeatureError(sheet_seed_message(feature, seed.name))
        ftype = REGISTRY.get(seed.type)
        if seed.type in NESTED_TYPES and ftype is not None:  # TR141 (D1512)
            out.extend(_nested_tools(feature, ctx, seed, ftype))
            continue
        operation = seed.params.get("operation")
        if ftype is not None and operation is None:
            operation = ftype.pattern_operation
        if seed.params.get("modeled_thread") is True:
            raise FeatureError(
                f"{feature.name}: {seed.name} has modelled threads, which a feature copy "
                "leaves out. Turn on Geometry pattern to copy the threads too."
            )
        if ftype is None or operation not in ("boss", "cut"):
            raise FeatureError(
                f"{feature.name}: {seed.name} cannot be copied as a feature. "
                "Pick its faces instead, or turn on Geometry pattern."
            )
        seed_ctx = BuildContext(
            ctx.document,
            body_before(ctx.document, seed, ctx.results),
            ctx.results,
            ctx.variables,
            ctx.cancelled,
        )
        tool = ftype.tool(seed, seed_ctx)
        if tool is None:
            raise FeatureError(
                f"{feature.name}: {seed.name} has no solid to copy. "
                "Pick a feature that adds or cuts material."
            )
        out.append((seed, tool, str(operation)))
    return out


#: Patterns that can be the seed of another pattern of features (TR141, D1512).
NESTED_TYPES = (
    "linear_pattern",
    "circular_pattern",
    "sketch_pattern",
    "table_pattern",
    "pattern_chain",  # TR141 item 1 (D1901)
    "follow_pattern",  # TR399 (D1904)
)


def _nested_tools(
    feature: Feature, ctx: BuildContext, inner: Feature, ftype: Any
) -> list[tuple[Feature, NamedShape, str]]:
    """The tools of a pattern used as a seed (TR141, D1512): each of its seed features'
    solids together with that solid at every copy the inner pattern makes, so the
    outer pattern repeats the whole inner pattern. Patterns of patterns nest."""
    from fdcad.core.features.preview import body_before

    if not _seed_ids(inner):
        raise FeatureError(
            f"{feature.name}: {inner.name} copies faces or bodies, not features, so it "
            "cannot be repeated as a feature. Turn on Geometry pattern, or pick its faces."
        )
    inner_ctx = BuildContext(
        ctx.document,
        body_before(ctx.document, inner, ctx.results),
        ctx.results,
        ctx.variables,
        ctx.cancelled,
    )
    found, _issues = ftype.placements(inner, inner_ctx)
    gone = skipped(inner) | region_skips(inner, inner_ctx, found)
    places = [p for p in found if p.index not in gone]
    out: list[tuple[Feature, NamedShape, str]] = []
    for seed, tool, operation in _seed_tools(inner, ctx):
        copies = [_moved_named(tool, p.trsf, f"{inner.id}/{p.role}") for p in places]
        shape = compound([tool.shape, *(c.shape for c in copies)])
        faces = [*tool.faces, *(f for c in copies for f in c.faces)]
        out.append((seed, NamedShape(shape, faces), operation))
    return out


#: Feature types whose own faces are only the copies; their seed is copied too (D604).
_PATTERN_TYPES = (
    "linear_pattern",
    "circular_pattern",
    "sketch_pattern",
    "table_pattern",
    "mirror",
    "curve_array",
    "pattern_chain",  # TR141 item 1 (D1901)
    "follow_pattern",  # TR399 (D1904)
)


def _feature_ids(feature: Feature) -> list[str]:
    return [
        str(r["feature"])
        for r in feature.refs.get("features", []) or []
        if isinstance(r, dict) and isinstance(r.get("feature"), str)
    ]


def _with_pattern_seeds(ctx: BuildContext, fids: list[str]) -> list[str]:
    """``fids`` plus the seed features of any pattern or mirror among them (D604).

    A pattern's own faces are only its copies, so a Geometry pattern of a pattern
    would leave out the seed it started from.
    """
    out: list[str] = []
    todo = list(fids)
    while todo:
        fid = todo.pop(0)
        if fid in out:
            continue
        out.append(fid)
        try:
            earlier = ctx.document.feature(fid)
        except KeyError:
            continue
        if earlier.type in _PATTERN_TYPES:
            todo.extend(_feature_ids(earlier))
    return out


def _feature_faces(feature: Feature, ctx: BuildContext) -> list[dict[str, Any]]:
    """Face references to the faces the seed features made (Geometry pattern)."""
    from fdcad.core.naming.resolve import face_snapshot

    assert ctx.body is not None
    prefixes = [f"{fid}/" for fid in _with_pattern_seeds(ctx, _feature_ids(feature))]
    out: list[dict[str, Any]] = []
    for name, face in ctx.body.faces:
        if any(name.startswith(p) for p in prefixes):
            out.append({"kind": "face", "name": name, "snapshot": face_snapshot(face)})
    if not out:
        raise FeatureError(
            f"{feature.name}: the picked features left no faces of their own on the part "
            "(they were merged away). Turn off Geometry pattern."
        )
    return out


#: Which copies Suppress Region leaves out (TR398, D1503).
REGION_MODES = ("inside", "outside")


def _region_faces(feature: Feature, ctx: BuildContext) -> list[TopoDS_Shape]:
    """The faces of ``refs.region``: picked faces, and the closed regions of sketches."""
    from fdcad.core.features.lookup import resolve_face

    out: list[TopoDS_Shape] = []
    for ref in feature.refs.get("region") or []:
        if isinstance(ref, dict) and ref.get("kind") == "face":
            assert ctx.body is not None
            face, _found = resolve_face(ctx.body, ref, feature.name)  # a lost face errors
            out.append(face)
            continue
        fid = ref.get("feature") if isinstance(ref, dict) else None
        sketch = ctx.result(fid).sketch if isinstance(fid, str) else None
        if sketch is None or sketch.profile is None:
            raise FeatureError(
                f"{feature.name}: the region must be a face or a sketch with a closed shape. "
                "Pick a face, or close the sketch."
            )
        out.extend(sketch.profile.faces)
    return out


def _over_face(face: TopoDS_Shape, point: Any) -> bool:
    """True when ``point`` lies over ``face`` (its nearest point on the surface is inside)."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepClass import BRepClass_FaceClassifier
    from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
    from OCP.gp import gp_Pnt2d
    from OCP.TopAbs import TopAbs_IN, TopAbs_ON
    from OCP.TopoDS import TopoDS

    f = TopoDS.Face(face)
    project = GeomAPI_ProjectPointOnSurf(point, BRep_Tool.Surface_s(f))
    if project.NbPoints() == 0:
        return False
    u, v = project.LowerDistanceParameters()
    state = BRepClass_FaceClassifier(f, gp_Pnt2d(u, v), 1e-6).State()
    return state in (TopAbs_IN, TopAbs_ON)


def region_skips(
    feature: Feature, ctx: BuildContext, placements: Sequence[Placement]
) -> set[tuple[int, int]]:
    """Copies Suppress Region leaves out (TR398, D1503): with ``refs.region`` (faces or
    sketches), every copy whose seed centre lands over a region face (``region_mode``
    "inside", the default) or over none of them ("outside")."""
    if not feature.refs.get("region"):
        return set()
    from OCP.gp import gp_Pnt

    from fdcad.core.features.seeds import seed_centre

    faces = _region_faces(feature, ctx)
    inside = feature.params.get("region_mode", "inside") != "outside"
    centre = gp_Pnt(*seed_centre(feature, ctx))
    out: set[tuple[int, int]] = set()
    for p in placements:
        moved = centre.Transformed(p.trsf)
        over = any(_over_face(face, moved) for face in faces)
        if over == inside:
            out.add(p.index)
    return out


def apply_pattern(feature: Feature, ctx: BuildContext, placements: Sequence[Placement]) -> Outcome:
    """Copy the feature's seed to every placement and combine the copies with the part."""
    name, fid = feature.name, feature.id
    if ctx.body is None:
        raise FeatureError(f"{name}: the part is empty. Add a body first.")
    skip = skipped(feature) | region_skips(feature, ctx, placements)
    placements = [p for p in placements if p.index not in skip]
    from fdcad.core.features.pattern_explode import only

    kept = only(feature)  # TR270 item 1 (D1902): an exploded copy keeps one instance
    if kept is not None:
        placements = [p for p in placements if p.index == kept]
        if not placements:
            from fdcad.core.features.base import FeatureState

            label = f"{kept[0]}" if kept[1] == 1 else f"{kept[0]}.{kept[1]}"
            why = (
                f"{name}: the pattern values no longer make copy {label}, so the part is "
                "unchanged. Raise the count, or delete this copy."
            )
            return Outcome(ctx.body, [Issue(FeatureState.WARNING, why, code="copy_gone")])
    has_features = bool(feature.refs.get("features"))
    has_faces = bool(feature.refs.get("faces"))
    has_bodies = bool(feature.refs.get("bodies"))
    if not (has_features or has_faces or has_bodies):
        raise FeatureError(f"{name}: pick features, faces or bodies to copy.")
    body = ctx.body
    issues: list[Issue] = []
    if not placements:
        # A count of 0 or 1 (or every copy skipped) leaves the part as it is, so size
        # families in configurations and design tables still build (TR345, D875).
        zero = any(
            k.startswith("count") and isinstance(v, Param) and round(v.value) == 0
            for k, v in feature.params.items()
        )
        return Outcome(body, [_no_copies(name, "a count of 0 makes no copies")] if zero else [])
    if has_features and not has_faces and not has_bodies and _all_seeds_off(feature, ctx):
        return Outcome(body, [_no_copies(name, "every feature it copies is suppressed")])
    geometry = feature.params.get("geometry") is True
    varies = bool(parse_vary(feature) or parse_instance_values(feature))  # TR59
    if varies and (geometry or not has_features):  # TR59 (D1513, D1900)
        raise FeatureError(
            f"{name}: varying values needs copies of features, each built again. Turn off "
            "Geometry pattern and pick features to copy, or clear the values to vary."
        )
    if has_features and not geometry:
        body = _pattern_features(feature, ctx, body, placements)
    elif has_features:
        refs = _feature_faces(feature, ctx)
        try:
            # The faces were listed from the part just now, not picked by the user, so
            # the notes about a picked face found by its position do not apply (D1048):
            # two faces of a seed can share a name, and each is then found by its place.
            body, _found = _pattern_faces(feature, ctx, body, refs, placements)
        except NotWholeFeatureError:
            # The faces cannot be patched away (a boss on a lofted tube, D1045): copy
            # what the seed features added and removed when they were built.
            done = _pattern_history(feature, ctx, body, placements)
            if done is None:
                raise
            body = done
    if has_faces:
        body, found = _pattern_faces(feature, ctx, body, feature.refs["faces"], placements)
        issues += found
    if has_bodies:
        body, found = _pattern_bodies(feature, ctx, body, placements)
        issues += found
    _ = fid
    return Outcome(body, issues)


#: One "name step" item of a vary list (TR59, D1513).
_VARY_ITEM = r"([A-Za-z_][A-Za-z0-9_]*)\s*[= ]\s*([-+]?[0-9.]+(?:[eE][-+]?\d+)?)"


def parse_vary(feature: Feature) -> list[tuple[str, float]]:
    """The seed values that grow from copy to copy (TR59, D1513): ``vary`` is text such
    as "depth 2; draft_angle 1", a value name of the seed feature and its step per copy
    (mm for lengths, degrees for angles). Raises FeatureError for text it cannot read."""
    import re

    text = str(feature.params.get("vary", "") or "").strip()
    out: list[tuple[str, float]] = []
    for part in re.split(r"[,;]+", text):
        part = part.strip()
        if not part:
            continue
        found = re.fullmatch(_VARY_ITEM, part)
        if found is None:
            raise FeatureError(
                f"{feature.name}: the values to vary must read like depth 2; draft_angle 1. "
                f"Fix '{part}'."
            )
        out.append((found.group(1), float(found.group(2))))
    return out


def parse_instance_values(feature: Feature) -> dict[tuple[int, int], list[tuple[str, float]]]:
    """Values of single copies (TR59 item 3, D1900): ``instance_values`` is text such as
    "3: depth 8; 2.2: depth 4, draft_angle 2", an instance number (``i`` or ``i.j``),
    a colon and value names with the value that copy uses (mm or degrees), in place
    of the seed's value and any Vary step. Raises FeatureError for text it cannot read."""
    import re

    text = str(feature.params.get("instance_values", "") or "").strip()
    out: dict[tuple[int, int], list[tuple[str, float]]] = {}
    for group in text.split(";"):
        group = group.strip()
        if not group:
            continue
        head, colon, rest = group.partition(":")
        index = re.fullmatch(r"\s*(\d+)(?:\.(\d+))?\s*", head)
        items = [part.strip() for part in rest.split(",") if part.strip()]
        found = [re.fullmatch(_VARY_ITEM, part) for part in items]
        if not colon or index is None or not items or any(m is None for m in found):
            raise FeatureError(
                f"{feature.name}: copy values must read like 3: depth 8; 2.2: depth 4. "
                f"Fix '{group}'."
            )
        key = (int(index.group(1)), int(index.group(2) or 1))
        if key == (1, 1):
            raise FeatureError(
                f"{feature.name}: instance 1 is the seed, so its values are the seed's own. "
                "Edit the seed feature, or enter another instance number."
            )
        out[key] = [(m.group(1), float(m.group(2))) for m in found if m is not None]
    return out


def counting_sketches(ctx: BuildContext, seed: Feature) -> list[Feature]:
    """The sketches ``seed`` uses whose text holds the ``{copy}`` field (TR121 item 3,
    D2203): each copy of the pattern builds them again with its own number."""
    from fdcad.core.sketch.text_fields import COPY_FIELD, FIELD

    found: list[Feature] = []
    for ref in seed.refs.values():
        for one in ref if isinstance(ref, list) else [ref]:
            fid = one.get("feature") if isinstance(one, dict) else None
            if not isinstance(fid, str):
                continue
            try:
                source = ctx.document.feature(fid)
            except KeyError:
                continue
            texts = source.data.get("texts") if source.type == "sketch" else None
            if not isinstance(texts, list) or source in found:
                continue
            if any(
                m.group(1) == COPY_FIELD
                for raw in texts
                if isinstance(raw, dict)
                for m in FIELD.finditer(str(raw.get("text", "")))
            ):
                found.append(source)
    return found


def copy_number(feature: Feature, index: tuple[int, int]) -> int:
    """The number a copy shows in ``{copy}`` text (TR121, D2203): the seed is 1, the
    copies count along the first direction, then row by row."""
    count = feature.params.get("count1")
    per_row = max(round(count.value), 1) if isinstance(count, Param) else 1
    return (index[0] - 1) + (index[1] - 1) * per_row + 1


def _counted_results(
    ctx: BuildContext, sketches: list[Feature], number: int
) -> dict[str, FeatureResult]:
    """``ctx.results`` with each of ``sketches`` built again for copy ``number``."""
    from fdcad.core.features import REGISTRY
    from fdcad.core.features.preview import body_before

    results = dict(ctx.results)
    for sketch in sketches:
        sketch_ctx = BuildContext(
            ctx.document,
            body_before(ctx.document, sketch, ctx.results),
            ctx.results,
            ctx.variables,
            ctx.cancelled,
            copy_number=number,
        )
        results[sketch.id] = REGISTRY["sketch"].execute(sketch, sketch_ctx)
    return results


def _varied_tool(
    feature: Feature,
    ctx: BuildContext,
    seed: Feature,
    steps: int,
    vary: list[tuple[str, float]],
    fixed: list[tuple[str, float]] | None = None,
    counted: tuple[list[Feature], int] | None = None,
) -> NamedShape:
    """The seed's solid with each varied value grown ``steps`` times (TR59, D1513), and
    the ``fixed`` values of one copy set outright (TR59 item 3, D1900). ``counted``
    holds the sketches with ``{copy}`` text and the copy's number (TR121, D2203)."""
    import copy
    import math

    from fdcad.core.features import REGISTRY
    from fdcad.core.features.preview import body_before
    from fdcad.core.units import Kind

    ftype = REGISTRY[seed.type]
    clone = copy.copy(seed)
    clone.params = dict(seed.params)
    for name, step in vary:
        value = seed.params.get(name)
        if not isinstance(value, Param):
            raise FeatureError(
                f"{feature.name}: {seed.name} has no value named {name} to vary. Enter one of "
                "its value names, such as depth."
            )
        kind = ftype.kind_of(name)
        delta = math.radians(step) if kind is Kind.ANGLE else step
        grown = value.value + delta * steps
        clone.params[name] = Param(f"{grown:.12g}", grown)
    for name, typed in fixed or []:
        if not isinstance(seed.params.get(name), Param):
            raise FeatureError(
                f"{feature.name}: {seed.name} has no value named {name} to set. Enter one of "
                "its value names, such as depth."
            )
        value = math.radians(typed) if ftype.kind_of(name) is Kind.ANGLE else typed
        clone.params[name] = Param(f"{typed:.12g}", value)
    results = ctx.results
    if counted is not None:
        try:
            results = _counted_results(ctx, *counted)
        except FeatureError as exc:
            raise FeatureError(
                f"{feature.name}: copy {counted[1]} fails to write its number: {exc} "
                "Check the sketch text."
            ) from None
    seed_ctx = BuildContext(
        ctx.document,
        body_before(ctx.document, seed, ctx.results),
        results,
        ctx.variables,
        ctx.cancelled,
    )
    try:
        tool = ftype.tool(clone, seed_ctx)
    except FeatureError as exc:
        raise FeatureError(
            f"{feature.name}: copy {steps + 1} with its varied values fails: {exc} Use smaller "
            "steps or fewer copies."
        ) from None
    if tool is None:
        raise FeatureError(f"{feature.name}: {seed.name} has no solid to copy. Pick another.")
    return tool


#: How carefully a pattern checks its copies (TR399, D1519).
CHECKS = ("full", "fast")


def fast_check(feature: Feature) -> bool:
    """True when the pattern skips the per copy touch and overlap tests (TR399, D1519)."""
    return feature.params.get("check") == "fast"


def _pattern_features(
    feature: Feature, ctx: BuildContext, body: NamedShape, placements: Sequence[Placement]
) -> NamedShape:
    name = feature.name
    vary = parse_vary(feature)  # TR59 (D1513)
    own = parse_instance_values(feature)  # TR59 item 3 (D1900)
    direct = set(_seed_ids(feature))
    for seed, tool, operation in _seed_tools(feature, ctx):
        pieces: list[TopoDS_Shape] = []
        names: list[NamedFace] = []
        failed: list[tuple[int, int]] = []
        counting = counting_sketches(ctx, seed) if seed.id in direct else []  # TR121
        for p in placements:
            source = tool
            fixed = own.get(p.index)
            if (vary or fixed or counting) and seed.id in direct:
                steps = max(p.index[0] - 1, 0) + max(p.index[1] - 1, 0)
                counted = (counting, copy_number(feature, p.index)) if counting else None
                source = _varied_tool(feature, ctx, seed, steps, vary, fixed, counted)
            moved = _moved_named(source, p.trsf, f"{feature.id}/{p.role}")
            ok = fast_check(feature) or (  # TR399 (D1519): Fast skips the per copy test
                _touches(moved.shape, body.shape)
                if operation == "boss"
                else _overlaps(moved.shape, body.shape)
            )
            if not ok:
                failed.append(p.index)
                continue
            pieces.append(moved.shape)
            names.extend(moved.faces)
        if failed:
            raise _fell_off(feature, failed, "would not touch the part")
        shape = compound(pieces)
        op = "fuse" if operation == "boss" else "cut"
        body = boolean_named(op, body, NamedShape(shape, names), feature.id, name)
    return body


class NotWholeFeatureError(FeatureError):
    """The picked faces cannot be patched away to find what they add and remove."""


#: Volumes below this, in mm3, are not copied by a history pattern.
_NO_VOLUME = 1e-6


def _pattern_history(
    feature: Feature, ctx: BuildContext, body: NamedShape, placements: Sequence[Placement]
) -> NamedShape | None:
    """Geometry pattern of features from the part's history (D1045).

    For each seed feature, in the order they were built: the material it added (the
    part after it less the part before it) and the material it removed are copied to
    every placement, the removed first. This needs no patching of faces, so it works
    where a boss or pocket sits on a face the kernel cannot extend under it. None when
    the seeds changed no material.
    """
    from fdcad.core.features.preview import body_before

    name = feature.name
    wanted = set(_with_pattern_seeds(ctx, _feature_ids(feature)))
    seeds = [f for f in ctx.document.features if f.id in wanted and not f.suppressed]
    current = body
    changed = False
    for seed in seeds:
        # A pattern among the seeds is taken too (D1081): its own seeds are in the list
        # (D604), and what it added and removed is only its copies, so nothing is twice.
        result = ctx.results.get(seed.id)
        after = result.body if result is not None else None
        if after is None:
            continue
        before = body_before(ctx.document, seed, ctx.results)
        if before is None:
            added, removed = after.shape, None
        else:
            added = boolean_shape("cut", after.shape, before.shape)
            removed = boolean_shape("cut", before.shape, after.shape)
        for volume, op in ((removed, "cut"), (added, "fuse")):
            if volume is None or not solids(volume) or volume_of(volume) <= _NO_VOLUME:
                continue
            failed: list[tuple[int, int]] = []
            for p in [] if fast_check(feature) else placements:
                moved = _moved(volume, p.trsf)
                near = _touches if op == "fuse" else _overlaps
                if not near(moved, current.shape):
                    failed.append(p.index)
            if failed:
                raise _fell_off(feature, failed, "would fall off the face the seed sits on")
            pieces: list[TopoDS_Shape] = []
            names: list[NamedFace] = []
            for p in placements:
                moved = _moved(volume, p.trsf)
                pieces.append(moved)
                for k, face in enumerate(faces_of(moved), start=1):
                    names.append((f"{feature.id}/{p.role}/face#{k}", face))
            tool = NamedShape(compound(pieces), names)
            current = boolean_named(op, current, tool, feature.id, name)
            changed = True
    if not changed:
        return None
    if len(solids(current.shape)) != len(solids(body.shape)):
        raise FeatureError(
            f"{name}: the copies split the body or leave it. Change the spacing or skip copies."
        )
    return current


def _pattern_faces(
    feature: Feature,
    ctx: BuildContext,
    body: NamedShape,
    refs: Any,
    placements: Sequence[Placement],
) -> tuple[NamedShape, list[Issue]]:
    name = feature.name
    local = BuildContext(
        ctx.document, body, ctx.results, ctx.variables, ctx.cancelled, owner=ctx.owner
    )
    faces, labels, issues = resolve_faces(local, refs, name)
    picked = [n for n, f in body.faces if any(f.IsSame(p) for p in faces)]
    owner = _sheet_owner(ctx, picked)
    if owner is not None:
        raise FeatureError(sheet_seed_message(feature, owner), highlight=labels)
    try:
        _patched, added, removed = feature_volumes(body, faces, feature.id, name, labels)
    except FeatureError:
        raise NotWholeFeatureError(
            f"{name}: the picked faces do not form a whole feature (such as every face of a "
            "boss or hole), so they cannot be copied. Pick the rest of its faces, or pick "
            "the feature instead.",
            highlight=labels,
        ) from None
    failed: list[tuple[int, int]] = []
    for p in [] if fast_check(feature) else placements:  # TR399 (D1519)
        ok = True
        if added is not None and not _touches(_moved(added, p.trsf), body.shape):
            ok = False
        if removed is not None and not _overlaps(_moved(removed, p.trsf), body.shape):
            ok = False
        if not ok:
            failed.append(p.index)
    if failed:
        raise _fell_off(feature, failed, "would fall off the face the seed sits on")
    current = body
    for volume, op in ((removed, "cut"), (added, "fuse")):
        if volume is None:
            continue
        pieces: list[TopoDS_Shape] = []
        names: list[NamedFace] = []
        for p in placements:
            moved = _moved(volume, p.trsf)
            pieces.append(moved)
            for k, face in enumerate(faces_of(moved), start=1):
                names.append((f"{feature.id}/{p.role}/face#{k}", face))
        current = boolean_named(op, current, NamedShape(compound(pieces), names), feature.id, name)
    before = len(solids(body.shape))
    if len(solids(current.shape)) != before:
        raise FeatureError(
            f"{name}: the copies split the body or leave it. Change the spacing or skip copies.",
            highlight=labels,
        )
    return current, issues


def _pattern_bodies(
    feature: Feature, ctx: BuildContext, body: NamedShape, placements: Sequence[Placement]
) -> tuple[NamedShape, list[Issue]]:
    name = feature.name
    local = BuildContext(
        ctx.document, body, ctx.results, ctx.variables, ctx.cancelled, owner=ctx.owner
    )
    indices, issues = body_indices(local, feature.refs.get("bodies"), name)
    seed = sub_body(body, indices, feature.id)
    copies = [_moved_named(seed, p.trsf, f"{feature.id}/{p.role}") for p in placements]
    if feature.params.get("merge") is True:
        merged = seed
        for copy in copies:
            merged = boolean_named("fuse", merged, copy, feature.id, name)
        result = join([rest_of(body, indices, feature.id), merged], feature.id)
    else:
        result = join([body, *copies], feature.id)
    assert result is not None
    return result, issues
