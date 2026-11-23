"""Fillet failure help: other ways to make a failing multi edge fillet (TR346, D1405).

When a fillet of several picked edges fails as one kernel call, these ways are
tried, each as a chain of separate fillets built one after the other:

1. Each chain: edges that touch each other form one fillet.
2. Smaller groups: as many edges as build together, then the next group on the
   result, and so on.
3. Larger radius first (Multiple radius): one fillet per radius, largest first.
4. One fillet per edge.

Only ways that build are offered, as fix buttons with action ``split_fillet``
(``data["groups"]``: lists of picked edge names). Clicking one splits the
feature: the first group stays in it, every other group becomes a new fillet
after it (``split_fillet``), as one undo step. Nothing changes until then
(CLAUDE.md rule 12).
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import TYPE_CHECKING

from OCP.TopAbs import TopAbs_VERTEX
from OCP.TopExp import TopExp_Explorer

from fdcad.core.document.model import Document, Feature
from fdcad.core.features.base import Fix
from fdcad.core.naming.names import NamedShape

if TYPE_CHECKING:
    from fdcad.core.features.fillet import Item, RadiusLaw

ACTION = "split_fillet"
#: More picked edges than this are not tried: each way costs kernel calls.
MAX_ITEMS = 12


def _touch(a: Item, b: Item) -> bool:
    ea = TopExp_Explorer(a.edge, TopAbs_VERTEX)
    while ea.More():
        eb = TopExp_Explorer(b.edge, TopAbs_VERTEX)
        while eb.More():
            if ea.Current().IsSame(eb.Current()):
                return True
            eb.Next()
        ea.Next()
    return False


def chains(items: list[Item]) -> list[list[Item]]:
    """Items grouped by touching (sharing an end point), in picked order."""
    groups: list[list[Item]] = []
    for item in items:
        joined = [g for g in groups if any(_touch(item, other) for other in g)]
        merged = [item]
        for g in joined:
            merged = g + merged
            groups.remove(g)
        groups.append(merged)
    order = {id(i): k for k, i in enumerate(items)}
    return sorted(
        (sorted(g, key=lambda i: order[id(i)]) for g in groups), key=lambda g: order[id(g[0])]
    )


def _again(current: NamedShape, item: Item) -> Item | None:
    from fdcad.core.features.fillet import Item as ItemClass
    from fdcad.core.features.fillet_tangent import find_again, middle

    edge = find_again(current, middle(item.edge))
    return None if edge is None else ItemClass(item.name, edge, item.index, item.radius)


def builds(
    fid: str, body: NamedShape, groups: list[list[Item]], law_of: Callable[[Item], RadiusLaw]
) -> bool:
    """True when the groups round one after the other."""
    from fdcad.core.features.fillet import round_edges

    current = body
    for group in groups:
        found = [_again(current, i) for i in group]
        if any(f is None for f in found):
            return False
        step = round_edges(fid, current, [f for f in found if f is not None], law_of)
        if step is None:
            return False
        current = step
    return True


def greedy(
    fid: str, body: NamedShape, items: list[Item], law_of: Callable[[Item], RadiusLaw]
) -> list[list[Item]] | None:
    """As many items as build together, then the next group on the result."""
    from fdcad.core.features.fillet import round_edges

    current, rest, groups = body, list(items), []
    while rest:
        group: list[Item] = []
        placed: list[Item] = []
        result = None
        for item in rest:
            found = _again(current, item)
            if found is None:
                continue
            trial = round_edges(fid, current, [*placed, found], law_of)
            if trial is not None:
                group.append(item)
                placed.append(found)
                result = trial
        if not group or result is None:
            return None
        groups.append(group)
        rest = [i for i in rest if i not in group]
        current = result
    return groups


def ways(
    feature: Feature,
    body: NamedShape,
    items: list[Item],
    law_of: Callable[[Item], RadiusLaw],
) -> list[Fix]:
    """Fix buttons for the ways that build (see the module docstring)."""
    if len(items) < 2 or len(items) > MAX_ITEMS or any(i.index == 0 for i in items):
        return []
    if len({i.name for i in items}) != len(items):  # groups are lists of names (D1043)
        return []
    if feature.params.get("partial") or feature.params.get("tangent_propagation") is False:
        return []
    fid = feature.id
    tried: list[list[list[str]]] = []
    out: list[Fix] = []

    def offer(label: str, groups: list[list[Item]] | None, check: bool = True) -> None:
        if groups is None or len(groups) < 2:
            return
        names = [[i.name for i in g] for g in groups]
        if names in tried:
            return
        tried.append(names)
        if check and not builds(fid, body, groups, law_of):
            return
        out.append(Fix(label.format(n=len(groups)), ACTION, {"feature": fid, "groups": names}))

    offer("Fillet each chain as its own feature ({n} fillets)", chains(items))
    offer("Fillet in {n} smaller groups", greedy(fid, body, items, law_of), check=False)
    if feature.params.get("multiple_radius") is True:
        by_radius: dict[float, list[Item]] = {}
        for item in items:
            by_radius.setdefault(max(r for _u, r in law_of(item)), []).append(item)
        ordered = [by_radius[r] for r in sorted(by_radius, reverse=True)]
        offer("Larger radius first ({n} fillets)", ordered)
    offer("One fillet per edge ({n} fillets)", [[i] for i in items])
    return out


def split_fillet(doc: Document, fid: str, groups: list[list[str]]) -> list[Feature]:
    """The fillet for the first group, then a new fillet for each other group.

    New fillets get new ids and the next free names; the document is not changed.
    """
    import re

    from fdcad.core.features.modify import piece_base
    from fdcad.core.features.names import name_prefix

    original = doc.feature(fid)
    refs = original.refs.get("edges", [])
    by_name = {
        str(r.get("name", "")): (k, r) for k, r in enumerate(refs, start=1) if isinstance(r, dict)
    }
    prefix = name_prefix("fillet")
    pattern = re.compile(rf"^{re.escape(prefix)} (\d+)$")
    number = max((int(m.group(1)) for f in doc.features if (m := pattern.match(f.name))), default=0)
    out: list[Feature] = []
    for n, group in enumerate(groups):
        feature = copy.deepcopy(original)
        if n:
            feature.id = doc.new_feature_id()
            number += 1
            feature.name = f"{prefix} {number}"
        picked = [by_name[piece_base(name)] for name in group if piece_base(name) in by_name]
        feature.refs = {"edges": [copy.deepcopy(r) for _k, r in picked]}
        params = {k: v for k, v in original.params.items() if not k.startswith(("radius_", "vr_"))}
        for new_k, (old_k, _r) in enumerate(picked, start=1):
            for name, value in original.params.items():
                for head in ("radius", "vr"):
                    stem = f"{head}_{old_k}"
                    if name == stem or name.startswith(stem + "_"):
                        params[f"{head}_{new_k}{name[len(stem) :]}"] = copy.deepcopy(value)
        feature.params = params
        out.append(feature)
    return out
