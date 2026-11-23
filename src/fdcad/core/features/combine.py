"""Combine bodies: add, subtract or common (PHASE3_SPEC P3.4 item 1, DECISIONS D233).

Params: ``operation``: "add" (all picked bodies into one), "subtract" (the
main body minus the tool bodies) or "common" (only where all picked bodies overlap).

Refs: ``bodies`` (add, common: two or more; subtract: the tool bodies) and
``main`` (subtract: the body to keep). Each is a face reference to a face of the body.

``tolerance``: optional length: faces of the bodies closer than this count as
touching, for imported bodies that nearly meet (TR261, D787).

Options (TR128, D865): ``operation`` "exclusive" keeps only what lies inside an odd
number of the picked bodies; ``keep_tools`` keeps the tool bodies (subtract: the
picked tools; add, common, exclusive: every picked body but the first);
``keep_largest`` keeps only the largest piece of the result.

``reapply_fillets`` (TR259, D2302): on Add, Subtract and Common, rounds next to the
change are removed first and made again after (see ``reapply_fillets``).

``operation`` "fragments" (TR371, D999) cuts the picked bodies at every crossing and
keeps every piece as a body of its own; "at_least" keeps only the volume inside at
least ``min_bodies`` of the picked bodies (2 by default), joined.

Faces keep their names. Bodies not picked are left as they are.
"""

from __future__ import annotations

from OCP.TopoDS import TopoDS_Face

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
from fdcad.core.features.bodies import body_index, body_indices, join, rest_of, sub_body
from fdcad.core.features.booleans import boolean_named
from fdcad.core.features.solids import check_result, solids, volume_of
from fdcad.core.naming.names import NamedShape
from fdcad.core.units import Kind


def tolerance_of(feature: Feature) -> float | None:
    """The typed touching tolerance in mm, or None (TR261)."""
    from fdcad.core.document.model import Param

    value = feature.params.get("tolerance")
    return value.value if isinstance(value, Param) and value.value > 0 else None


OPERATIONS = ("add", "subtract", "common", "exclusive", "fragments", "at_least")


def _safe(
    op: str, a: NamedShape, b: NamedShape, fid: str, name: str, fuzzy: float | None
) -> NamedShape | None:
    """A boolean that gives None instead of failing when nothing is left."""
    try:
        found = boolean_named(op, a, b, fid, name, fuzzy=fuzzy)
    except FeatureError:
        return None
    return found if solids(found.shape) else None


def fragments(
    pieces: list[NamedShape], fid: str, name: str, fuzzy: float | None
) -> list[tuple[NamedShape, int]]:
    """Every piece of the bodies cut at each crossing, with how many of the bodies
    cover it (TR371, D999)."""
    cells: list[tuple[NamedShape, int]] = [(pieces[0], 1)]
    union = pieces[0]
    for body in pieces[1:]:
        next_cells: list[tuple[NamedShape, int]] = []
        for cell, count in cells:
            inside = _safe("common", cell, body, fid, name, fuzzy)
            outside = _safe("cut", cell, body, fid, name, fuzzy)
            if inside is not None:
                next_cells.append((inside, count + 1))
            if outside is not None:
                next_cells.append((outside, count))
        rest = _safe("cut", body, union, fid, name, fuzzy)
        if rest is not None:
            next_cells.append((rest, 1))
        cells = next_cells
        union = _safe("fuse", union, body, fid, name, fuzzy) or union
    return cells


@register
class Combine(FeatureType):
    """Joins, subtracts or intersects bodies of a multibody part."""

    type_name = "combine"
    makes_solid = True
    params = (
        ParamSpec("operation", choices=OPERATIONS, default="add"),
        ParamSpec("tolerance", kind=Kind.LENGTH, optional=True),
        ParamSpec("keep_tools", default=False, optional=True),
        ParamSpec("keep_largest", default=False, optional=True),
        ParamSpec("min_bodies", kind=Kind.NUMBER, optional=True),  # TR371 (D999)
        ParamSpec("reapply_fillets", default=False, optional=True),  # TR259 (D2302)
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Combine the bodies and check the result."""
        body, issues = self._build(feature, ctx)
        issues += check_result(feature.id, feature.name, ctx.body, body, None)
        return FeatureResult(body=body, issues=[i for i in issues if i.code != "separate_body"])

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The combined part, for the live preview."""
        return self._build(feature, ctx)[0]

    def _build(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        """The combined part. With Reapply Fillets (TR259, D2302) on Add, Subtract or
        Common, the rounds of the picked bodies next to another picked body are removed
        first and made again after, where their edges are left."""
        from fdcad.core.features import reapply_fillets as reapply

        operation = str(feature.params.get("operation", "add"))
        if (
            reapply.wanted(feature)
            and operation in ("add", "subtract", "common")
            and ctx.body is not None
            and len(solids(ctx.body.shape)) > 1
        ):
            rounds = self._rounds(feature, ctx, operation)
            return reapply.redo(feature, ctx, rounds, lambda c: self._build_core(feature, c))
        return self._build_core(feature, ctx)

    def _rounds(
        self, feature: Feature, ctx: BuildContext, operation: str
    ) -> list[tuple[str, TopoDS_Face, float]]:
        """The rounds next to the change: on a picked body and touching another one."""
        from fdcad.core.features import reapply_fillets as reapply

        assert ctx.body is not None
        tools, _issues = body_indices(ctx, feature.refs.get("bodies"), feature.name)
        pieces = solids(ctx.body.shape)
        if operation == "subtract":
            if not feature.refs.get("main"):
                return []
            main, _found = body_index(ctx, feature.refs.get("main"), feature.name)
            owners = [main]
            others = {main: [pieces[i] for i in tools if i != main]}
        else:
            owners = tools
            others = {i: [pieces[j] for j in tools if j != i] for i in tools}
        out: list[tuple[str, TopoDS_Face, float]] = []
        for i in owners:
            for found in reapply.near_bodies(ctx.body, pieces[i], others[i]):
                if not any(found[1].IsSame(f) for _n, f, _r in out):
                    out.append(found)
        return out

    def _build_core(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        name = feature.name
        if ctx.body is None or len(solids(ctx.body.shape)) < 2:
            raise FeatureError(
                f"{name}: the part needs two or more bodies to combine. Add another body first."
            )
        operation = str(feature.params.get("operation", "add"))
        tools, issues = body_indices(ctx, feature.refs.get("bodies"), name)
        if operation == "subtract":
            if not feature.refs.get("main"):
                raise FeatureError(f"{name}: pick the main body to subtract from in the view.")
            main, found = body_index(ctx, feature.refs.get("main"), name)
            issues += found
            tools = [i for i in tools if i != main]
            if not tools:
                raise FeatureError(
                    f"{name}: pick one or more bodies to subtract from the main body."
                )
            used = [main, *tools]
            main_body = sub_body(ctx.body, [main], feature.id)
            result = boolean_named(
                "cut",
                main_body,
                sub_body(ctx.body, tools, feature.id),
                feature.id,
                name,
                fuzzy=tolerance_of(feature),
            )
            if abs(volume_of(result.shape) - volume_of(main_body.shape)) < 1e-9 * max(
                1.0, volume_of(main_body.shape)
            ):
                # The tool missed: it was used up and nothing changed (audit B item 15).
                issues.append(
                    Issue(
                        FeatureState.WARNING,
                        f"{name}: the tool bodies do not touch the main body, so nothing "
                        "was removed and the tools are gone. Move a tool into the main body, "
                        "or undo.",
                        code="combine_missed",
                    )
                )
        elif operation in ("fragments", "at_least"):  # TR371 (D999)
            if len(tools) < 2:
                raise FeatureError(f"{name}: pick two or more bodies.")
            used = tools
            parts = [sub_body(ctx.body, [i], feature.id) for i in tools]
            cells = fragments(parts, feature.id, name, tolerance_of(feature))
            if operation == "at_least":
                from fdcad.core.document.model import Param

                need = feature.params.get("min_bodies")
                least = max(1, round(need.value)) if isinstance(need, Param) else 2
                covered = [cell for cell, count in cells if count >= least]
                if not covered:
                    raise FeatureError(
                        f"{name}: no volume is inside {least} of the picked bodies. "
                        "Enter a smaller number, or pick bodies that overlap more."
                    )
                result = covered[0]
                for cell in covered[1:]:
                    result = _safe("fuse", result, cell, feature.id, name, None) or result
            else:
                pieces_out = join([cell for cell, _count in cells], feature.id)
                if pieces_out is None:
                    raise FeatureError(f"{name}: the picked bodies left no pieces. Pick others.")
                result = pieces_out
        else:
            if len(tools) < 2:
                raise FeatureError(f"{name}: pick two or more bodies.")
            used = tools
            result = sub_body(ctx.body, [tools[0]], feature.id)
            for index in tools[1:]:
                other = sub_body(ctx.body, [index], feature.id)
                if operation == "exclusive":  # inside an odd number of bodies (TR128)
                    fuzzy = tolerance_of(feature)
                    a = boolean_named("cut", result, other, feature.id, name, fuzzy=fuzzy)
                    b = boolean_named("cut", other, result, feature.id, name, fuzzy=fuzzy)
                    result = join([a, b], feature.id) or a
                    continue
                op = "fuse" if operation == "add" else "common"
                try:
                    result = boolean_named(
                        op, result, other, feature.id, name, fuzzy=tolerance_of(feature)
                    )
                except FeatureError:
                    if operation != "common":
                        raise
                    raise FeatureError(
                        f"{name}: the picked bodies do not overlap. Pick bodies that do."
                    ) from None
            if operation == "common" and not solids(result.shape):
                raise FeatureError(
                    f"{name}: the picked bodies do not overlap. Pick bodies that do."
                )
        if not solids(result.shape):
            raise FeatureError(f"{name} removes the whole body. Pick other tool bodies.")
        if feature.params.get("keep_largest") is True and len(solids(result.shape)) > 1:
            pieces = solids(result.shape)
            biggest = max(range(len(pieces)), key=lambda i: volume_of(pieces[i]))
            result = sub_body(result, [biggest], feature.id)
        if feature.params.get("keep_tools") is True:
            kept = tools if operation == "subtract" else tools[1:]
            used = [i for i in used if i not in kept]
        if operation == "add" and len(solids(result.shape)) > 1:
            # Bodies that do not touch stay separate (audit B item 15, D716).
            issues.append(
                Issue(
                    FeatureState.WARNING,
                    f"{name}: some picked bodies do not touch, so they stay separate "
                    f"({len(solids(result.shape))} bodies). Move them so they overlap, "
                    "or pick bodies that touch.",
                    code="combine_apart",
                )
            )
        combined = join([rest_of(ctx.body, used, feature.id), result], feature.id)
        assert combined is not None
        return combined, issues
