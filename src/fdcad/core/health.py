"""Model health report (TR286, DECISIONS D775).

One advisory list for the part. It never changes geometry; the only fix it
offers, Move to End for an early fillet, is a button the user confirms
(CLAUDE.md 5.12). Each item names the feature it is about, for Zoom to Item.

Checks:

- ``untied``: a sketch with curves but nothing tying it to the sketch origin, a
  fixed point or part geometry, so it can float when edited.
- ``level_lines``: lines that are exactly horizontal or vertical with no
  Horizontal or Vertical relation, in a sketch that is fully defined: dimensions
  hold what one relation would.
- ``on_rounding``: a feature that uses a face or edge made by a fillet or
  chamfer, so it breaks when the round changes.
- ``early_round``: a fillet or chamfer with solid features after it; rounds last
  keep the model easy to change.
- ``no_effect``: a cut that removes nothing; ``hole_through``: a blind hole that
  came out through the part.
- ``default_names``: features still called by their default name.
- ``repeated_sketch``: three or more sketches that each hold one circle of the
  same size, which one sketch and a pattern would do.
- ``unlinked_value`` (TR351, D905): a feature value or sketch dimension typed as a
  plain number equal to a global variable of the same kind, not linked to it; the
  fix (Link to Variable, ``LINK_VARIABLE``) types the variable's name instead.

Volumes for ``no_effect`` are kernel queries, so ``report`` runs in a kernel job.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

from fdcad.core.document.model import Document, Feature
from fdcad.core.features.base import FeatureState
from fdcad.core.features.names import name_prefix

ROUNDS = ("fillet", "chamfer")
_BUILT_IN = ("origin", "plane")
MOVE_TO_END = "move_to_end"
LINK_VARIABLE = "link_variable"
_PLAIN = re.compile(r"^\s*-?\d+(\.\d*)?\s*(mm|in|deg|°)?\s*$")
_OWNER = re.compile(r"\b(f\d+)/")


@dataclass
class HealthItem:
    """One advice row: its kind, what it says, the feature it is about, and a fix."""

    kind: str
    message: str
    fid: str | None = None
    fix: str | None = None  # MOVE_TO_END, or None
    extra: dict[str, Any] = field(default_factory=dict)


def _names_in(refs: Any) -> list[str]:
    out: list[str] = []
    if isinstance(refs, dict):
        name = refs.get("name")
        if isinstance(name, str):
            out.append(name)
        for v in refs.values():
            out += _names_in(v)
    elif isinstance(refs, list):
        for v in refs:
            out += _names_in(v)
    return out


def _sketch_checks(doc: Document, f: Feature, results: dict[str, Any]) -> list[HealthItem]:
    from fdcad.core.sketch.model import Line, Point, sketch_from_data
    from fdcad.core.sketch.solver import SketchStatus

    try:
        sk = sketch_from_data(f.data)
    except ValueError:
        return []
    curves = sk.curves()
    if not curves:
        return []
    out: list[HealthItem] = []
    fixed = {r.entities[0] for r in sk.relations if r.type == "fixed" and r.entities}
    origin = {
        e.id
        for e in sk.entities.values()
        if isinstance(e, Point) and e.id in fixed and e.construction and math.hypot(e.x, e.y) < 1e-9
    }
    tied = any(
        set(r.entities) & (fixed | origin) and r.type != "fixed" for r in sk.relations
    ) or any(set(d.entities) & (fixed | origin) for d in sk.dimensions)
    tied = tied or any(getattr(e, "source", None) for e in sk.entities.values())
    tied = tied or bool(fixed - origin)
    if not tied:
        out.append(
            HealthItem(
                "untied",
                f"{f.name} is not tied to the sketch origin or anything fixed. Add a relation "
                "or dimension to the origin, so the sketch cannot float when edited.",
                f.id,
            )
        )
    result = results.get(f.id)
    status = result.sketch.solve.status if result is not None and result.sketch else None
    if status is SketchStatus.FULL:
        related = {r.entities[0] for r in sk.relations if r.type in ("horizontal", "vertical")}
        level = 0
        for c in curves:
            if isinstance(c, Line) and c.id not in related:
                (x1, y1), (x2, y2) = sk.xy(c.p1), sk.xy(c.p2)
                if abs(x1 - x2) < 1e-9 or abs(y1 - y2) < 1e-9:
                    level += 1
        if level:
            out.append(
                HealthItem(
                    "level_lines",
                    f"{f.name} has {level} level lines held by dimensions. A Horizontal or "
                    "Vertical relation would hold each one with one dimension less.",
                    f.id,
                )
            )
    return out


def _default_named(f: Feature) -> bool:
    if f.type in _BUILT_IN:
        return False
    operation = str(f.params.get("operation", "boss"))
    prefix = name_prefix(f.type, operation)
    return bool(re.fullmatch(rf"{re.escape(prefix)} (f?\d+)", f.name))


def report(doc: Document, results: dict[str, Any]) -> list[HealthItem]:
    """The advice for the part as last rebuilt (``results`` by feature id)."""
    from fdcad.core.features import REGISTRY
    from fdcad.core.features.solids import volume_of

    out: list[HealthItem] = []
    active = [f for f in doc.features if not f.suppressed]
    kinds = {f.id: f.type for f in doc.features}
    for f in active:
        if f.type == "sketch":
            out += _sketch_checks(doc, f, results)
    for f in active:
        if f.type in ROUNDS:
            continue
        rounds = {
            m.group(1)
            for n in _names_in(f.refs)
            if (m := _OWNER.search(n)) and kinds.get(m.group(1)) in ROUNDS
        }
        if rounds:
            names = ", ".join(sorted(doc.feature(r).name for r in rounds))
            out.append(
                HealthItem(
                    "on_rounding",
                    f"{f.name} uses faces or edges made by {names}. It breaks when the round "
                    "changes; pick faces of the model before the round instead.",
                    f.id,
                )
            )
    for i, f in enumerate(active):
        if f.type not in ROUNDS:
            continue
        later = [
            g
            for g in active[i + 1 :]
            if g.type not in ROUNDS and getattr(REGISTRY.get(g.type), "makes_solid", False)
        ]
        if later:
            out.append(
                HealthItem(
                    "early_round",
                    f"{f.name} comes before {len(later)} solid features. Rounds near the end "
                    "keep the part easy to change: move it to the end if nothing after it "
                    "needs it.",
                    f.id,
                    fix=MOVE_TO_END,
                )
            )
    previous_volume: float | None = None
    for f in active:
        result = results.get(f.id)
        body = result.body if result is not None else None
        volume = volume_of(body.shape) if body is not None else None
        operation = f.params.get("operation")
        is_cut = operation == "cut" or f.type == "hole"
        ok = result is not None and result.state is not FeatureState.ERROR
        unchanged = (
            volume is not None
            and previous_volume is not None
            and abs(previous_volume - volume) <= 1e-6 * max(previous_volume, 1.0)
        )
        if is_cut and ok and unchanged and True:
            out.append(
                HealthItem(
                    "no_effect",
                    f"{f.name} removes nothing from the part. Check its direction and depth, "
                    "or delete it.",
                    f.id,
                )
            )
        if (
            f.type == "hole"
            and f.params.get("end_condition") == "blind"
            and ok
            and body is not None
        ) and not any(
            "/bottom" in n or "/tip" in n for n, _ in body.faces if n.startswith(f"{f.id}/")
        ):
            out.append(
                HealthItem(
                    "hole_through",
                    f"{f.name} is a blind hole but came out through the part. Make its depth "
                    "smaller, or make it Through All.",
                    f.id,
                )
            )
        if volume is not None:
            previous_volume = volume
    named = [f for f in active if _default_named(f)]
    if named:
        sample = ", ".join(f.name for f in named[:4])
        more = f" and {len(named) - 4} more" if len(named) > 4 else ""
        out.append(
            HealthItem(
                "default_names",
                f"{len(named)} features keep their default names ({sample}{more}). Rename them "
                "so the tree says what each one is for.",
                named[0].id,
            )
        )
    out += _repeated_sketches(active)
    out += unlinked_values(doc, active)
    return out


def unlinked_values(doc: Document, active: list[Feature]) -> list[HealthItem]:
    """Typed plain numbers that equal a variable's value (TR351, D905)."""
    from fdcad.core.document.model import Param
    from fdcad.core.features import REGISTRY
    from fdcad.core.units import Kind

    variables = [v for v in doc.variables if v.kind in (Kind.LENGTH, Kind.ANGLE, Kind.NUMBER)]
    if not variables:
        return []

    def match(value: float, kind: Kind | None) -> Any:
        for v in variables:
            same_kind = kind is None or v.kind is kind
            if same_kind and abs(v.value - value) <= 1e-9 * max(1.0, abs(value)):
                return v
        return None

    out: list[HealthItem] = []
    for f in active:
        ftype = REGISTRY.get(f.type)
        kinds = {p.name: p.kind for p in getattr(ftype, "params", ())} if ftype else {}
        for key, param in f.params.items():
            if not isinstance(param, Param) or not _PLAIN.match(param.expr):
                continue
            var = match(param.value, kinds.get(key))
            if var is not None and param.value != 0:
                out.append(
                    HealthItem(
                        "unlinked_value",
                        f"{f.name}: {key} is typed as {param.expr.strip()}, the value of "
                        f"variable {var.name}. Link it so it follows the variable.",
                        f.id,
                        fix=LINK_VARIABLE,
                        extra={"param": key, "variable": var.name},
                    )
                )
        if f.type == "sketch":
            for dim in (f.data or {}).get("dimensions", []) or []:
                p = dim.get("param") if isinstance(dim, dict) else None
                expr = p.expr if isinstance(p, Param) else (p or {}).get("expr")
                value = p.value if isinstance(p, Param) else (p or {}).get("value")
                if not isinstance(expr, str) or not _PLAIN.match(expr) or not value:
                    continue
                kind = Kind.ANGLE if dim.get("type") == "angle" else Kind.LENGTH
                var = match(float(value), kind)
                if var is not None:
                    out.append(
                        HealthItem(
                            "unlinked_value",
                            f"{f.name}: dimension {dim.get('id')} is typed as {expr.strip()}, "
                            f"the value of variable {var.name}. Link it so it follows the "
                            "variable.",
                            f.id,
                            fix=LINK_VARIABLE,
                            extra={"dimension": dim.get("id"), "variable": var.name},
                        )
                    )
    return out


def linked(doc: Document, item: HealthItem) -> Feature | None:
    """A copy of the item's feature with the value typed as the variable's name, or None
    when it no longer applies (TR351)."""
    import copy

    from fdcad.core.document.model import Param

    if item.fix != LINK_VARIABLE or item.fid is None:
        return None
    try:
        f = copy.deepcopy(doc.feature(item.fid))
    except KeyError:
        return None
    name = str(item.extra.get("variable", ""))
    var = next((v for v in doc.variables if v.name == name), None)
    if var is None:
        return None
    key = item.extra.get("param")
    if isinstance(key, str) and isinstance(f.params.get(key), Param):
        f.params[key] = Param(name, var.value)
        return f
    did = item.extra.get("dimension")
    for dim in (f.data or {}).get("dimensions", []) or []:
        if isinstance(dim, dict) and dim.get("id") == did:
            dim["param"] = Param(name, var.value)
            return f
    return None


def _repeated_sketches(active: list[Feature]) -> list[HealthItem]:
    from fdcad.core.sketch.model import Circle, sketch_from_data

    sizes: dict[float, list[Feature]] = {}
    for f in active:
        if f.type != "sketch":
            continue
        try:
            curves = sketch_from_data(f.data).curves()
        except ValueError:
            continue
        if len(curves) == 1 and isinstance(curves[0], Circle):
            sizes.setdefault(round(curves[0].radius, 6), []).append(f)
    out: list[HealthItem] = []
    for radius, sketches in sizes.items():
        if len(sketches) >= 3:
            out.append(
                HealthItem(
                    "repeated_sketch",
                    f"{len(sketches)} sketches each hold one circle of radius {radius:g} mm "
                    f"({', '.join(s.name for s in sketches[:3])}). One sketch with a pattern "
                    "keeps them in step.",
                    sketches[0].id,
                )
            )
    return out
