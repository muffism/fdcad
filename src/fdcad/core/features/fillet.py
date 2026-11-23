"""Fillet: round the picked edges (PHASE2_SPEC P2.4, PLAN 5A items 4 and 5, DECISIONS D213).

Params:

- ``fillet_type``: "constant" (default), "variable", "face" or "full_round" (D518).
- ``radius``: length, the constant radius (and the default for every item).
- ``multiple_radius``: optional boolean. With it, picked edge ``k`` (1 based, the
  order of ``refs.edges``) may have its own ``radius_<k>``.
- Variable size, per picked edge ``k``: ``vr_<k>_start`` and ``vr_<k>_end`` (the
  radius at its two end points), ``control_points`` (a whole number, 0 to 5, the
  same for every edge) and ``vr_<k>_<j>`` for control point ``j`` (evenly spaced, or
  at ``vp_<j>`` percent of each edge, TR133, D1403).
  ``transition``: "smooth" (default) or "straight".

Refs: ``edges`` (edge references), ``faces`` (every edge of each face),
``features`` (``{"feature": "f6"}``: every edge of the faces that feature made) and
``auto_edges`` (fillet assistant, D519: ``{"convexity": "convex"}`` for every convex
edge of the part, or with ``"feature"`` only that feature's edges; also "concave"),
or fillet rules (``"rule"``, TR320, D1408, see ``fillet_rules``).
Partial edges (D519, constant size only): ``partial`` "distance" (``start_distance``
and ``end_distance``) or "percent" (``start_percent`` and ``end_percent``), measured
along each edge from its first end, or from the other end with ``partial_flip``;
or "reference" (TR64, D1401) with two picks in ``refs.partial_ends`` (vertices,
points or planes) for the start and the end.

Limits (TR271, D1407): ``refs.keep_edges`` (edges a round may not swallow) and
``refs.limit_plane`` with ``limit_flip`` (rounds stop at the plane); see
``fillet_limits``.

Methods and profiles (TR62, D1402, constant size): ``method`` "radius", "asymmetric"
(``distance2``, ``reverse``) or "chord"; ``profile`` "circular", "conic" (``rho``),
"curvature" or "elliptic". See ``fillet_profile``.

Face fillet: ``faces1`` and ``faces2``, the edges where they meet are rounded. With
``method`` "hold_line" and ``refs.hold_lines`` the rounds follow the hold line edges
(TR29, D1409, see ``fillet_hold``).
Full round: ``faces1``, ``centre`` and ``faces2`` (see ``fillet_faces.full_round``).
Edges tangent to a picked edge are included (the kernel works on whole smooth
chains), unless ``tangent_propagation`` is False (TR131, D1400): then the round of a
picked edge stops square at each smooth join (see ``fillet_tangent``).

Face roles: ``fillet/<edge name>`` for the face that rounds a picked edge, and
``corner/face#k`` for corner blends where fillets meet.

Before the result is used every edge is checked. When some edges fail, the
feature stops with a list of them, the largest radius each allows, and two
fixes for the user to click: fillet the rest, or use the largest radius.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.collections import Array1_gp_Pnt2d
from OCP.gp import gp_Pnt2d
from OCP.TopAbs import TopAbs_FACE
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Face

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Fix,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.features.fillet_faces import (
    edges_by_convexity,
    face_sets,
    full_round,
    shared_edges,
)
from fdcad.core.features.fillet_partial import PARTIAL_KINDS, partial_fillet
from fdcad.core.features.fillet_profile import (
    METHODS,
    PROFILES,
    built_here,
    chord_radius,
    edge_angle,
    method_of,
    profile_round,
)
from fdcad.core.features.fillet_tangent import (
    PARAM,
    find_again,
    middle,
    propagates,
    round_joined,
    split_items,
)
from fdcad.core.features.modify import (
    MakerHistory,
    PartialResultError,
    changed_faces,
    edges_of,
    length,
    piece_base,
    require_body,
    resolve_edges,
    resolve_faces,
    seam_picks,
)
from fdcad.core.features.solids import breaks_solid, check_result, is_valid
from fdcad.core.naming.names import NamedFace, NamedShape, carry, restrict
from fdcad.core.occ import shape_list
from fdcad.core.units import Kind

MAX_CONTROL_POINTS = 5
FILLET_TYPES = ("constant", "variable", "face", "full_round")
#: Bisection steps when looking for the largest radius an edge allows.
_SEARCH_STEPS = 8
#: The search stops below this share of the wanted radius (D1043). A round that small
#: is no help to the user, and the kernel can run for minutes on a round of a few
#: hundredths of a millimetre along a curved joint.
SMALLEST_SHARE = 1 / 16
#: At most this many failing chains are searched for their largest radius (D1043).
_SEARCH_CHAINS = 6
#: The extra fix buttons (other ways to split the fillet, limit the failing areas) each
#: need many trial rounds. They are looked for only while naming the failing edges has
#: taken less than this many seconds (D1043): on a part of several hundred faces one
#: trial takes half a second, and a four edge fillet took 34 s to say it had failed.
EXTRAS_SECONDS = 4.0


@dataclass
class Item:
    """One edge to round, with its name and how its radius is set."""

    name: str
    edge: TopoDS_Edge
    index: int  # 1 based position in refs.edges, or 0 for edges from faces and features
    radius: float | None = None  # a fillet rule's own radius (TR320, D1408)


def gather(feature: Feature, ctx: BuildContext) -> tuple[list[Item], list[Issue]]:
    """Every edge to round, from the picked edges, faces and features, without repeats."""
    body = require_body(feature, ctx)
    items: list[Item] = []
    issues: list[Issue] = []
    if feature.params.get("fillet_type") == "face":
        sets, issues = face_sets(feature, ctx, ("faces1", "faces2"), ("Face Set 1", "Face Set 2"))
        found = shared_edges(feature.name, body, [f for _n, f in sets[0]], [f for _n, f in sets[1]])
        return [Item(name, edge, 0) for name, edge in found], issues
    if isinstance(feature.refs.get("edges"), list) and feature.refs["edges"]:
        found, issues = resolve_edges(feature, ctx, "edges", pieces=True)
        order = [str(r.get("name", "")) for r in feature.refs["edges"] if isinstance(r, dict)]
        places = positions(order, [name for name, _edge in found])
        items = [Item(name, edge, k) for (name, edge), k in zip(found, places, strict=True)]
    faces, face_issues = resolve_faces(feature, ctx, "faces", required=False)
    issues.extend(face_issues)
    extra: list[TopoDS_Edge] = []
    for _name, face in faces:
        extra.extend(edges_of(face))
    for ref in feature.refs.get("features", []) or []:
        fid = str(ref.get("feature", "")) if isinstance(ref, dict) else ""
        made = [f for n, f in body.faces if n.startswith(f"{fid}/")]
        if not made:
            raise FeatureError(
                f"{feature.name}: feature {fid} has no faces in the part now. "
                "Pick it again or remove it from the list.",
                highlight=[fid],
            )
        edges = [e for face in made for e in edges_of(face)]
        if feature.params.get("omit_attach") is True:  # TR64 (D997)
            edges = [e for e in edges if _inside(body, e, made)]
        extra.extend(edges)
    for edge in extra:
        if any(edge.IsSame(i.edge) for i in items):
            continue
        name = body.edge_name(edge)
        if name is not None:
            items.append(Item(name, edge, 0))
    for name, edge in auto_edges(feature, body):
        if not any(edge.IsSame(i.edge) for i in items):
            items.append(Item(name, edge, 0))
    from fdcad.core.features.fillet_rules import rule_edges, rule_radius

    for ref in feature.refs.get("auto_edges", []) or []:  # TR320 (D1408): fillet rules
        if not isinstance(ref, dict) or "rule" not in ref:
            continue
        own = rule_radius(feature, ref)
        for name, edge in rule_edges(feature, body, ref):
            if not any(edge.IsSame(i.edge) for i in items):
                items.append(Item(name, edge, 0, own))
    if not items:
        raise FeatureError(
            f"{feature.name}: nothing to round. Pick edges, faces or features in the view."
        )
    return items, issues


def _inside(body: NamedShape, edge: TopoDS_Edge, made: list[TopoDS_Face]) -> bool:
    """True when both faces at ``edge`` were made by the picked feature: an edge where
    the feature meets the earlier body (an attach edge) gives False."""
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp

    from fdcad.core.occ import ShapeListMap, shape_list

    found = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(body.shape, TopAbs_EDGE, TopAbs_FACE, found)
    index = found.FindIndex(edge)
    if index == 0:
        return True
    faces = shape_list(found.FindFromIndex(index))
    return all(any(f.IsSame(m) for m in made) for f in faces)


def _index(order: list[str], name: str) -> int:
    """1 based position of the picked edge ``name`` (or the edge a piece came from)."""
    base = piece_base(name)
    return order.index(base) + 1 if base in order else 0


def positions(order: list[str], found: list[str]) -> list[int]:
    """1 based position in the picked list of each resolved edge name, in order.

    Two picked edges can have one name: an edge is named by the two faces it lies
    between, and two faces can meet in more than one edge (a tube that crosses a
    plate, a joint cut in two by a seam). Looking a name up would give both the first
    place, so each name is looked for after the place of the one before (D1043).
    The pieces of one split pick (``name#1``, ``name#2``) share its place.
    """
    out: list[int] = []
    at = 0
    split: str | None = None
    for name in found:
        base = piece_base(name)
        if name != base and split == base and out:
            out.append(out[-1])
            continue
        split = base if name != base else None
        later = next((k for k in range(at, len(order)) if order[k] == base), None)
        if later is None:
            out.append(_index(order, name))
            continue
        at = later + 1
        out.append(later + 1)
    return out


def auto_edges(feature: Feature, body: NamedShape) -> list[tuple[str, TopoDS_Edge]]:
    """Edges from the fillet assistant items in ``refs.auto_edges`` (D519 item 1)."""
    out: list[tuple[str, TopoDS_Edge]] = []
    for ref in feature.refs.get("auto_edges", []) or []:
        if not isinstance(ref, dict) or "rule" in ref:
            continue
        convexity = "concave" if ref.get("convexity") == "concave" else "convex"
        faces = None
        if "feature" in ref:
            fid = str(ref["feature"])
            faces = [f for n, f in body.faces if n.startswith(f"{fid}/")]
            if not faces:
                raise FeatureError(
                    f"{feature.name}: feature {fid} has no faces in the part now. "
                    "Remove the assistant item or pick another feature.",
                    highlight=[fid],
                )
        for name, edge in edges_by_convexity(body, convexity, faces):
            if not any(edge.IsSame(e) for _n, e in out):
                out.append((name, edge))
    return out


def _param(feature: Feature, name: str) -> float | None:
    value = feature.params.get(name)
    return value.value if isinstance(value, Param) else None


def control_count(feature: Feature) -> int:
    """Number of control points per edge for a variable fillet."""
    raw = feature.params.get("control_points", 0)
    count = int(raw) if isinstance(raw, int | float) and not isinstance(raw, bool) else 0
    return max(0, min(MAX_CONTROL_POINTS, count))


RadiusLaw = list[tuple[float, float]]  # (relative position 0..1, radius)


def point_positions(feature: Feature) -> list[float]:
    """Where control point ``j`` sits on each edge, 0 to 1 (TR133, D1403).

    ``vp_<j>`` is a percent of the edge; without it the points are evenly spaced.
    Positions must be inside the edge and differ from each other.
    """
    count = control_count(feature)
    out: list[float] = []
    for j in range(1, count + 1):
        percent = _param(feature, f"vp_{j}")
        at = j / (count + 1) if percent is None else percent / 100
        if not 0 < at < 1:
            raise FeatureError(
                f"{feature.name}: control point {j} must be inside the edge, between 0 and "
                "100 percent. Enter another position."
            )
        if any(abs(at - other) < 1e-6 for other in out):
            raise FeatureError(
                f"{feature.name}: control point {j} is at the same place as another point. "
                "Enter another position, or delete the point."
            )
        out.append(at)
    return out


def radius_law(feature: Feature, item: Item, base: float) -> RadiusLaw:
    """Radius along an edge: one value for a constant fillet, several for variable."""
    if feature.params.get("fillet_type", "constant") != "variable":
        own = None
        if feature.params.get("multiple_radius") is True and item.index:
            own = _param(feature, f"radius_{item.index}")
        if own is None and item.radius is not None:
            own = item.radius
        r = own if own is not None else base
        return [(0.0, r), (1.0, r)]
    k = item.index
    start = _param(feature, f"vr_{k}_start") if k else None
    end = _param(feature, f"vr_{k}_end") if k else None
    points = [(0.0, start if start is not None else base)]
    middle: RadiusLaw = []
    for j, at in enumerate(point_positions(feature), start=1):
        value = _param(feature, f"vr_{k}_{j}") if k else None
        middle.append((at, value if value is not None else base))
    points.extend(sorted(middle))
    points.append((1.0, end if end is not None else base))
    if feature.params.get("transition", "smooth") == "straight" and len(points) > 2:
        dense: RadiusLaw = []
        for (u0, r0), (u1, r1) in pairwise(points):
            for s in range(4):
                t = s / 4
                dense.append((u0 + (u1 - u0) * t, r0 + (r1 - r0) * t))
        dense.append(points[-1])
        return dense
    return points


def _apply(maker: BRepFilletAPI_MakeFillet, item: Item, law: RadiusLaw) -> None:
    radii = {r for _u, r in law}
    if len(radii) == 1:
        maker.Add(law[0][1], item.edge)
        return
    maker.Add(item.edge)
    contour = maker.Contour(item.edge)
    if len(law) == 2:
        maker.SetRadius(law[0][1], law[1][1], contour, 1)
        return
    array = Array1_gp_Pnt2d(1, len(law))
    for i, (u, r) in enumerate(law, start=1):
        array.SetValue(i, gp_Pnt2d(u, r))
    maker.SetRadius(array, contour, 1)


def round_edges(
    fid: str,
    body: NamedShape,
    items: list[Item],
    law_of: Callable[[Item], RadiusLaw],
) -> NamedShape | None:
    """Round ``items`` on ``body``. None when the kernel cannot, or the result is invalid."""
    if any(r <= 0 for i in items for _u, r in law_of(i)):
        return None
    maker = BRepFilletAPI_MakeFillet(body.shape)
    try:
        for item in items:
            if maker.Contour(item.edge) == 0:
                _apply(maker, item, law_of(item))
        maker.Build()
    except Exception:  # kernel failure: the caller pinpoints the edges
        return None
    if not maker.IsDone():
        return None
    shape = maker.Shape()
    names: list[NamedFace] = carry(body.faces, MakerHistory(maker))
    for item in items:
        for made in shape_list(maker.Generated(item.edge)):
            if made.ShapeType() == TopAbs_FACE:
                names.append((f"{fid}/fillet/{item.name}", TopoDS.Face(made)))
    result = NamedShape(shape, restrict(names, shape, f"{fid}/corner"))
    if not is_valid(body, result) or breaks_solid(body, result):
        return None
    return result


@dataclass
class EdgeCheck:
    """Pre check of one edge (PLAN 5A item 4)."""

    name: str
    ok: bool
    largest: float | None = None  # largest radius that works, when it fails


def largest_radius(fid: str, body: NamedShape, item: Item, wanted: float) -> float | None:
    """The largest constant radius below ``wanted`` that rounds ``item`` alone, or None."""
    low, high = 0.0, wanted
    best = None
    for _ in range(_SEARCH_STEPS):
        middle = (low + high) / 2
        if middle < wanted * SMALLEST_SHARE:
            break

        def constant(_item: Item, r: float = middle) -> RadiusLaw:
            return [(0.0, r), (1.0, r)]

        if round_edges(fid, body, [item], constant):
            best, low = middle, middle
        else:
            high = middle
    return best


def chains_of(body: NamedShape, items: list[Item]) -> list[int]:
    """For each item, the number of the smooth chain the kernel rounds it in.

    The kernel follows smooth joins, so an edge rounded "on its own" is rounded with
    its whole chain. Edges of one chain build or fail together.
    """
    maker = BRepFilletAPI_MakeFillet(body.shape)
    out: list[int] = []
    try:
        for item in items:
            chain = maker.Contour(item.edge)
            if chain == 0:
                maker.Add(item.edge)
                chain = maker.NbContours()
            out.append(chain)
    except Exception:  # the kernel cannot say: every edge is its own chain
        return list(range(1, len(items) + 1))
    return out


def check_edges(
    fid: str, body: NamedShape, items: list[Item], law_of: Callable[[Item], RadiusLaw]
) -> list[EdgeCheck]:
    """Try each smooth chain on its own; for a failing one find the largest radius.

    A chain is tried once, through its first edge, and the answer is given to every
    edge of it (D1043): trying each edge again was the same work again. Only the
    first few failing chains are searched for their largest radius.
    """
    out: list[EdgeCheck] = []
    done: dict[int, EdgeCheck] = {}
    searched = 0
    for item, chain in zip(items, chains_of(body, items), strict=True):
        first = done.get(chain)
        if first is not None:
            out.append(EdgeCheck(item.name, first.ok, first.largest))
            continue
        if round_edges(fid, body, [item], law_of) is not None:
            check = EdgeCheck(item.name, True)
        else:
            largest = None
            if searched < _SEARCH_CHAINS:
                searched += 1
                wanted = max(r for _u, r in law_of(item))
                largest = largest_radius(fid, body, item, wanted)
            check = EdgeCheck(item.name, False, largest)
        done[chain] = check
        out.append(check)
    return out


#: At most this many pairs of edges are tried to find the rounds that meet (D2680).
_PAIR_TRIALS = 24
#: A pair whose rounds meet still fails with the radius this much larger; a pair that
#: builds then failed by a kernel quirk at one size, not because the rounds meet (D2680).
_LARGER = 1.05


def _scaled(law_of: Callable[[Item], RadiusLaw], share: float) -> Callable[[Item], RadiusLaw]:
    """``law_of`` with every radius times ``share``."""

    def law(item: Item) -> RadiusLaw:
        return [(u, r * share) for u, r in law_of(item)]

    return law


def meeting_limit(
    fid: str,
    body: NamedShape,
    items: list[Item],
    law_of: Callable[[Item], RadiusLaw],
    left_out: list[Item],
    together: set[int],
) -> tuple[set[int], float] | None:
    """When edges that round alone fail together because their rounds meet: the ids
    of the kept edges they meet, and the largest radius at which every edge rounds
    in one call (audit E item 8, D2680). None when no two edges' rounds meet (the
    kernel's trouble is with the whole set or with one size, as in D2604) or no
    smaller radius works.

    Without this, four equal edges whose rounds meet were named unevenly: the ones
    added last failed "on their own" and the others not at all, with no radius.
    """
    blamed = [i for i in left_out if id(i) in together]
    kept = [i for i in items if not any(i is j for j in left_out)]
    trials = 0

    def meet(a: Item, b: Item) -> bool:
        nonlocal trials
        trials += 1
        if round_edges(fid, body, [a, b], law_of) is not None:
            return False
        return round_edges(fid, body, [a, b], _scaled(law_of, _LARGER)) is None

    partners: set[int] = set()
    for k in kept:
        if any(trials < _PAIR_TRIALS and meet(k, t) for t in blamed):
            partners.add(id(k))
    met_any = bool(partners) or any(
        trials < _PAIR_TRIALS and meet(a, b) for a, b in pairwise(blamed)
    )
    if not met_any:
        return None
    wanted = max(r for i in items for _u, r in law_of(i))
    low, high, best = 0.0, 1.0, None
    for _ in range(_SEARCH_STEPS):
        share = (low + high) / 2
        if share < SMALLEST_SHARE:
            break
        if round_edges(fid, body, items, _scaled(law_of, share)) is not None:
            best, low = share, share
        else:
            high = share
    if best is None:
        return None
    return partners, best * wanted


def edge_words(item: Item, position: int) -> str:
    """How a message names an edge: its place in the picked list, never its stored name."""
    if item.index:
        return f"edge {item.index}"
    return f"edge {position} (from the picked faces or features)"


def no_radius(feature: Feature, items: list[Item], law_of: Callable[[Item], RadiusLaw]) -> None:
    """Raise a FeatureError naming the edges whose radius is 0 or less (D2644).

    The kernel refuses such a fillet, and the message that followed said the radius
    was larger than the faces allow.
    """
    bad = [(n, i) for n, i in enumerate(items, 1) if any(r <= 0 for _u, r in law_of(i))]
    if bad:
        words = list(dict.fromkeys(edge_words(i, n) for n, i in bad))
        one = len(words) == 1
        raise FeatureError(
            f"{feature.name}: {', '.join(words)} {'has' if one else 'have'} a radius of 0 "
            f"or less. Enter a radius greater than 0, or leave {'it' if one else 'them'} out.",
            highlight=[i.name for _n, i in bad],
        )


def pinpoint(
    feature: Feature,
    body: NamedShape,
    items: list[Item],
    law_of: Callable[[Item], RadiusLaw],
    radius_param: str,
    can_skip: bool = True,
) -> PartialResultError:
    """Find the failing edges and build the result with the rest (PLAN 5A item 5)."""
    fid, owner = feature.id, feature.name
    started = time.perf_counter()
    checks = check_edges(fid, body, items, law_of)
    place = {id(i): n for n, i in enumerate(items, 1)}
    failed = [(i, c) for i, c in zip(items, checks, strict=True) if not c.ok]
    good = [i for i, c in zip(items, checks, strict=True) if c.ok]
    partial: NamedShape | None = None
    together: set[int] = set()  # edges that round alone but not with the others (D2604)
    if good:
        partial = round_edges(fid, body, good, law_of)
        if partial is None:
            # Together they still fail: keep adding edges while the result builds.
            kept: list[Item] = []
            for item in good:
                trial = round_edges(fid, body, [*kept, item], law_of)
                if trial is not None:
                    kept.append(item)
                    partial = trial
                else:
                    failed.append((item, EdgeCheck(item.name, False, None)))
                    together.add(id(item))
    left_out = [i for i, _c in failed]  # the edges the partial result leaves out
    skipped = [c.name for _i, c in failed]
    helped: list[Fix] = []
    if can_skip and time.perf_counter() - started < EXTRAS_SECONDS:
        from fdcad.core.features.fillet_help import ways

        helped = ways(feature, body, items, law_of)  # TR346 (D1405)
    met = None
    # After the other ways, which keep the radius, so a slow part still gets those.
    if together and radius_param and time.perf_counter() - started < EXTRAS_SECONDS:
        met = meeting_limit(fid, body, items, law_of, left_out, together)  # audit E8 (D2680)
        if met is not None:
            partners, largest = met
            failed = [
                (i, EdgeCheck(i.name, False, largest))
                for i in items
                if id(i) in partners or any(i is f for f, _c in failed)
            ]
            together.clear()
    names = [c.name for _i, c in failed]
    details: list[str] = []
    for item, c in failed:
        # Each edge by its own place in the list: two picked edges can share a name
        # (D1043), and the pieces of one split edge are named once.
        words = edge_words(item, place[id(item)])
        if c.largest is not None:
            # The same safe value the Reduce fix offers: the raw limit read 9.96 mm beside a
            # 9.76 mm button (audit E item 8, D746).
            words = f"{words} (largest radius {_round_down(c.largest):g} mm)"
        elif id(item) in together:
            words = f"{words} (rounds on its own)"
        if words not in details:
            details.append(words)
    fixes: list[Fix] = []
    if partial is not None and can_skip:
        skip: dict[str, Any] = {"feature": fid, "items": skipped, "keys": ["edges"]}
        if all(i.index for i in left_out):
            skip["positions"] = sorted({i.index for i in left_out})
        fixes.append(
            Fix(
                f"Fillet the rest (skip {len(skipped)} edge{'s' if len(skipped) != 1 else ''})",
                "skip_items",
                skip,
            )
        )
    limits = [c.largest for _i, c in failed if c.largest is not None]
    if limits and len(limits) == len(failed) and radius_param:
        value = _round_down(min(limits))
        fixes.append(
            Fix(
                f"Reduce the radius to {value:g} mm",
                "set_param",
                {"feature": fid, "param": radius_param, "value": value},
            )
        )
    fixes.extend(helped)
    if can_skip and time.perf_counter() - started < EXTRAS_SECONDS:
        from fdcad.core.features.fillet_limit_areas import limit_fix

        failing_items = [i for i, _c in failed]
        limited = limit_fix(feature, body, failing_items, law_of)  # TR271 (D1802)
        if limited is not None:
            fixes.append(limited)
    if failed and all(id(i) in together for i, _c in failed):
        cause = (
            "Each of these edges rounds on its own, but the kernel cannot round them "
            "together with the others in one fillet. Use a fix to round them as separate "
            "fillets, or fillet the other edges and leave these out."
        )
    elif met is not None:
        cause = (
            "At this radius the rounds of these edges run into each other. Reduce the "
            "radius, or fillet some of these edges and leave the others out."
        )
    else:
        cause = (
            "The radius is larger than the faces next to these edges allow, or the edges "
            "are too short. Reduce the radius, or fillet the other edges and leave these out."
        )
    message = f"{owner} failed on {len(names)} of {len(items)} edges: {', '.join(details)}. {cause}"
    return PartialResultError(message, partial, names, fixes)


def _round_down(value: float) -> float:
    """``value`` rounded down to three significant digits, a little under the limit."""
    import math

    if value <= 0:
        return 0.0
    power = 10 ** (math.floor(math.log10(value)) - 2)
    return float(math.floor(value * 0.98 / power) * power)


@register
class Fillet(FeatureType):
    """Rounds edges of the part with a constant or varying radius."""

    type_name = "fillet"
    makes_solid = True
    params = (
        ParamSpec("fillet_type", choices=FILLET_TYPES, default="constant"),
        ParamSpec("radius", kind=Kind.LENGTH),
        ParamSpec("multiple_radius", default=False, optional=True),
        ParamSpec("omit_attach", default=False, optional=True),  # TR64 (D997)
        ParamSpec("control_points", optional=True),
        ParamSpec("transition", choices=("smooth", "straight"), optional=True),
        ParamSpec("partial", choices=PARTIAL_KINDS, optional=True),
        ParamSpec("start_distance", kind=Kind.LENGTH, optional=True),
        ParamSpec("end_distance", kind=Kind.LENGTH, optional=True),
        ParamSpec("start_percent", kind=Kind.NUMBER, optional=True),
        ParamSpec("end_percent", kind=Kind.NUMBER, optional=True),
        ParamSpec("partial_flip", default=False, optional=True),
        ParamSpec(PARAM, default=True, optional=True),  # TR131 (D1400)
        ParamSpec("limit_flip", default=False, optional=True),  # TR271 (D1407)
        # TR62 (D1402); hold_line: face fillets only (TR29, D1409)
        ParamSpec("method", choices=(*METHODS, "hold_line"), optional=True),
        ParamSpec("profile", choices=PROFILES, optional=True),
        ParamSpec("distance2", kind=Kind.LENGTH, optional=True),
        ParamSpec("rho", kind=Kind.NUMBER, optional=True),
        ParamSpec("reverse", default=False, optional=True),
    )

    def kind_of(self, name: str) -> Kind | None:
        """Per edge radii are lengths too (``radius_<k>``, ``vr_<k>_<j>``)."""
        if name.startswith(("radius_", "vr_")):
            return Kind.LENGTH
        if name.startswith("rule_radius_"):  # TR320 (D1408)
            return Kind.LENGTH
        if name.startswith("vp_"):  # TR133 (D1403): control point positions in percent
            return Kind.NUMBER
        return super().kind_of(name)

    def _round(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        """Round, then check the edges to keep (TR271 item 2, D1407)."""
        from fdcad.core.features import fillet_limits as limits

        points, kept_issues = limits.kept_points(feature, ctx)
        result, issues = self._round_core(feature, ctx)
        if not points:
            return result, issues
        lost = limits.swallowed(result, points)
        if not lost:
            return result, issues + kept_issues
        largest = None
        radius = feature.params.get("radius")
        plain = feature.params.get("fillet_type", "constant") == "constant" and (
            feature.params.get("multiple_radius") is not True
        )
        if plain and isinstance(radius, Param):

            def build(r: float) -> NamedShape | None:
                import copy

                trial = copy.deepcopy(feature)
                trial.params["radius"] = Param(f"{r:g}", r)
                try:
                    return self._round_core(trial, ctx)[0]
                except FeatureError:
                    return None

            largest = limits.largest_keeping(build, points, radius.value)
        raise limits.keep_error(feature, lost, largest)

    def _round_core(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        body = require_body(feature, ctx)
        if feature.params.get("fillet_type") == "full_round":
            rounded, found, _tool = full_round(feature, ctx)
            return rounded, found
        base = length(feature, "radius", "radius")
        items, issues = gather(feature, ctx)

        chord = feature.params.get("fillet_type", "constant") == "constant" and (
            method_of(feature) == "chord"
        )

        def law_of(item: Item) -> RadiusLaw:
            if chord:  # TR62 (D1402): each edge's radius from the chord width
                angle = edge_angle(body, item.edge)
                if angle is None:
                    raise FeatureError(
                        f"{feature.name}: edge {item.name} has no angle to set a chord width "
                        "on. Use the Radius method."
                    )
                r = chord_radius(angle, base)
                return [(0.0, r), (1.0, r)]
            return radius_law(feature, item, base)

        from fdcad.core.features.fillet_hold import hold_round, uses_hold_line

        if not chord:
            no_radius(feature, items, law_of)
        if uses_hold_line(feature):  # TR29 (D1409)
            rounded, more = hold_round(feature, ctx, body, [(i.name, i.edge) for i in items])
            return rounded, issues + more
        if feature.refs.get("limit_plane") and (
            feature.params.get("fillet_type", "constant") == "constant"
        ):  # TR271 item 3 (D1407): the rounds stop at a plane
            return self._limited(feature, ctx, body, items, law_of), issues
        if (
            feature.params.get("partial") in PARTIAL_KINDS
            and feature.params.get("fillet_type", "constant") == "constant"
        ):
            by_name = {i.name: i for i in items}

            def radius_of(name: str) -> float:
                return law_of(by_name[name])[0][1]

            edges = [(i.name, i.edge) for i in items]
            ends = None
            if feature.params.get("partial") == "reference":  # TR64 (D1401)
                from fdcad.core.features.partial_refs import end_picks

                ends, found = end_picks(feature, ctx)
                issues = issues + found
            return partial_fillet(feature, body, edges, radius_of, ends=ends), issues
        constant = feature.params.get("fillet_type", "constant") == "constant"
        if constant and built_here(feature):  # TR62 (D1402)
            if not propagates(feature.params) or feature.params.get("multiple_radius") is True:
                raise FeatureError(
                    f"{feature.name}: this method and profile use one size for every edge "
                    "and always follow smooth edges. Turn off Multiple radius and turn on "
                    "Tangent propagation, or use the Circular profile."
                )
            picked = [(i.name, i.edge, i.index) for i in items]
            return profile_round(feature, body, picked, base), issues
        if not propagates(feature.params):
            done = self._unpropagated(feature, body, items, law_of)
            if done is not None:
                return done, issues
        result = round_edges(feature.id, body, items, law_of)
        if result is None and constant and method_of(feature) == "radius":
            result = self._overflow(feature, body, items, law_of)  # D1041
        if result is None:
            kind = feature.params.get("fillet_type", "constant")
            plain = kind != "variable" and feature.params.get("multiple_radius") is not True
            plain = plain and method_of(feature) == "radius"
            radius_param = "radius" if plain else ""
            raise pinpoint(feature, body, items, law_of, radius_param, kind != "face")
        return result, issues

    def _overflow(
        self,
        feature: Feature,
        body: NamedShape,
        items: list[Item],
        law_of: Callable[[Item], RadiusLaw],
    ) -> NamedShape | None:
        """Rounds that must run past the end of their edge, which the kernel cannot
        build, cut here (D1041). None when this is not such a case."""
        from fdcad.core.features.fillet_overflow import overflow_round

        edges: list[tuple[str, TopoDS_Edge, float]] = []
        for item in items:
            radii = {r for _u, r in law_of(item)}
            if len(radii) != 1:
                return None
            edges.append((item.name, item.edge, radii.pop()))
        by_name = {item.name: item for item in items}

        def kernel_round(names: list[str]) -> NamedShape | None:
            return round_edges(feature.id, body, [by_name[n] for n in names], law_of)

        return overflow_round(feature.id, feature.name, body, edges, kernel_round)

    def _limited(
        self,
        feature: Feature,
        ctx: BuildContext,
        body: NamedShape,
        items: list[Item],
        law_of: Callable[[Item], RadiusLaw],
    ) -> NamedShape:
        """Round each edge only behind the limiting plane (TR271 item 3, D1407)."""
        from fdcad.core.features.fillet_limits import kept_range, limit_plane

        if feature.params.get("partial") in PARTIAL_KINDS:
            raise FeatureError(
                f"{feature.name}: a limiting plane and Partial Edges cannot be used together. "
                "Turn off Partial Edges, or remove the limiting plane."
            )
        plane, _issues = limit_plane(feature, ctx)
        assert plane is not None
        ranges = {i.name: kept_range(plane, i.edge) for i in items}
        kept = [i for i in items if ranges[i.name] is not None]
        if not kept:
            raise FeatureError(
                f"{feature.name}: every picked edge is in front of the limiting plane, so "
                "nothing is rounded. Flip the limit side, or pick other edges."
            )
        by_name = {i.name: i for i in kept}

        def spans_of(name: str, _edge: TopoDS_Edge) -> tuple[float, float]:
            found = ranges[name]
            assert found is not None
            return found

        return partial_fillet(
            feature,
            body,
            [(i.name, i.edge) for i in kept],
            lambda name: law_of(by_name[name])[0][1],
            spans_of=spans_of,
        )

    def _unpropagated(
        self,
        feature: Feature,
        body: NamedShape,
        items: list[Item],
        law_of: Callable[[Item], RadiusLaw],
    ) -> NamedShape | None:
        """Tangent Propagation off (TR131, D1400): edges with a smooth join stop there.

        None when no picked edge has a smooth join, so the usual path runs."""
        joined, plain = split_items(body, [(i.name, i.edge) for i in items])
        if not joined:
            return None
        by_name = {i.name: i for i in items}

        def apply(name: str) -> Callable[[BRepFilletAPI_MakeFillet, TopoDS_Edge], None] | None:
            item = by_name[name]
            law = law_of(item)
            if len({r for _u, r in law}) == 1:
                return None
            return lambda maker, edge: _apply(maker, Item(name, edge, item.index, item.radius), law)

        current = round_joined(
            feature.id,
            feature.name,
            body,
            joined,
            "fillet",
            lambda name: law_of(by_name[name])[0][1],
            apply,
        )
        rest: list[Item] = []
        for name in plain:
            item = by_name[name]
            edge = find_again(current, middle(item.edge))
            if edge is None:
                raise FeatureError(
                    f"{feature.name}: edge {name} was swallowed by the rounds next to it. "
                    "Reduce the radius, or turn on Tangent Propagation."
                )
            rest.append(Item(name, edge, item.index, item.radius))
        if not rest:
            return current
        result = round_edges(feature.id, current, rest, law_of)
        if result is None:
            raise pinpoint(feature, current, rest, law_of, "", False)
        return result

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Round the edges, or fail with the edges that do not work."""
        result, issues = self._round(feature, ctx)
        issues = issues + check_result(feature.id, feature.name, ctx.body, result, None)
        issues += seam_picks(feature, ctx, "rounded")  # D1084
        return FeatureResult(body=result, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The new and changed faces, for the preview."""
        body = require_body(feature, ctx)
        try:
            result, _issues = self._round(feature, ctx)
        except PartialResultError as exc:
            if exc.partial is not None:
                exc.partial = changed_faces(body.shape, exc.partial, feature.id)
            raise
        return changed_faces(body.shape, result, feature.id)


# Registers Remove Fillets (TR260, D1410), which uses the round making above.
from fdcad.core.features import remove_fillets as _remove_fillets  # noqa: E402, F401
