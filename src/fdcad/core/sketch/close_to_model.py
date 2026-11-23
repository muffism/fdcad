"""Close Sketch to Model (TUTORIAL_REVIEW_SPEC_2 TR106, D1704). No Qt, no kernel.

An open profile whose two ends sit on the part's edges in the sketch plane (the
intersection curves, D759) can be closed by those edges. The edge loop the ends
sit on is cut at the two ends; its two halves each close the profile, so there are
two possible shapes. The user picks one, and its edge pieces are copied into the
sketch as fixed curves (as Convert Entities does), joined to the profile's ends.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from fdcad.core.sketch.curve_convert import CurvePiece, add_piece
from fdcad.core.sketch.model import Arc, Line, Point, Sketch, Spline, curve_ends
from fdcad.core.sketch.open_ends import open_end_points
from fdcad.core.sketch.topology import _Nodes, curve_points, point_in_polygon

Vec = tuple[float, float]
#: How near (mm) a profile end must be to a part edge to sit on it.
ON_EDGE = 1e-3


class CloseError(ValueError):
    """The profile cannot be closed by the part's edges; the message says why."""


@dataclass
class Closing:
    """One way to close the profile: the edge pieces and the closed outline."""

    pieces: list[CurvePiece]
    outline: list[Vec]

    @property
    def area(self) -> float:
        """The area the closed shape encloses."""
        pts = self.outline
        return abs(
            sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1], strict=True)) / 2
        )

    def contains(self, p: Vec) -> bool:
        """True when ``p`` is inside the closed shape."""
        return point_in_polygon(p, self.outline)


def _angle(c: Vec, p: Vec) -> float:
    return math.atan2(p[1] - c[1], p[0] - c[0])


def _ccw_between(a0: float, a1: float, a: float) -> bool:
    """True when angle ``a`` lies on the counter clockwise sweep from ``a0`` to ``a1``."""
    sweep = (a1 - a0) % math.tau or math.tau
    return (a - a0) % math.tau <= sweep + 1e-9


def _param(piece: CurvePiece, p: Vec) -> float | None:
    """Where ``p`` lies along ``piece`` (0 to 1, or the angle for a circle), or None
    when it is not on it."""
    if piece.kind == "line":
        (x1, y1), (x2, y2) = piece.points
        length2 = (x2 - x1) ** 2 + (y2 - y1) ** 2
        if length2 < 1e-18:
            return None
        t = ((p[0] - x1) * (x2 - x1) + (p[1] - y1) * (y2 - y1)) / length2
        q = (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
        return t if -1e-9 <= t <= 1 + 1e-9 and math.dist(p, q) <= ON_EDGE else None
    if piece.kind in ("circle", "arc"):
        if abs(math.dist(p, piece.centre) - piece.radius) > ON_EDGE:
            return None
        a = _angle(piece.centre, p)
        if piece.kind == "circle":
            return a
        a0, a1 = piece.angles
        if not _ccw_between(a0, a1, a):
            return None
        sweep = (a1 - a0) % math.tau or math.tau
        return ((a - a0) % math.tau) / sweep
    pts = piece.points
    best: tuple[float, float] | None = None
    for i in range(len(pts) - 1):
        (x1, y1), (x2, y2) = pts[i], pts[i + 1]
        length2 = (x2 - x1) ** 2 + (y2 - y1) ** 2 or 1e-18
        t = min(max(((p[0] - x1) * (x2 - x1) + (p[1] - y1) * (y2 - y1)) / length2, 0.0), 1.0)
        d = math.dist(p, (x1 + t * (x2 - x1), y1 + t * (y2 - y1)))
        if best is None or d < best[0]:
            best = (d, (i + t) / (len(pts) - 1))
    return best[1] if best is not None and best[0] <= ON_EDGE else None


def _split(piece: CurvePiece, p: Vec, u: float) -> list[CurvePiece]:
    """``piece`` cut at ``p`` (place ``u`` along it), dropping empty parts."""
    if piece.kind == "line":
        a, b = piece.points
        parts = [CurvePiece("line", (a, p)), CurvePiece("line", (p, b))]
        return [q for q in parts if math.dist(*q.points) > ON_EDGE]
    if piece.kind == "arc":
        a0, a1 = piece.angles
        sweep = (a1 - a0) % math.tau or math.tau
        am = a0 + u * sweep
        s, e = piece.points
        parts = [
            CurvePiece("arc", (s, p), piece.centre, piece.radius, (a0, am)),
            CurvePiece("arc", (p, e), piece.centre, piece.radius, (am, a0 + sweep)),
        ]
        return [q for q in parts if math.dist(*q.points) > ON_EDGE]
    pts = list(piece.points)
    i = min(int(u * (len(pts) - 1)), len(pts) - 2)
    first = [*pts[: i + 1], p]
    second = [p, *pts[i + 1 :]]
    return [
        CurvePiece("spline", tuple(q)) if len(q) > 2 else CurvePiece("line", (q[0], q[-1]))
        for q in (first, second)
        if math.dist(q[0], q[-1]) > ON_EDGE or len(q) > 2
    ]


def _circle_halves(piece: CurvePiece, a: Vec, b: Vec) -> list[list[CurvePiece]]:
    aa, ab = _angle(piece.centre, a), _angle(piece.centre, b)
    one = CurvePiece("arc", (a, b), piece.centre, piece.radius, (aa, ab))
    two = CurvePiece("arc", (b, a), piece.centre, piece.radius, (ab, aa))
    return [[one], [two]]


def _ends(piece: CurvePiece) -> tuple[Vec, Vec]:
    return piece.points[0], piece.points[-1]


def edge_paths(pieces: list[CurvePiece], a: Vec, b: Vec) -> list[list[CurvePiece]]:
    """The runs of edge pieces from ``a`` to ``b`` along the loop they sit on: two for
    a closed loop, fewer when the edges branch or stop."""
    on_a = [(i, u) for i, q in enumerate(pieces) if (u := _param(q, a)) is not None]
    on_b = [(i, u) for i, q in enumerate(pieces) if (u := _param(q, b)) is not None]
    if not on_a or not on_b:
        return []
    for i, _u in on_a:
        if pieces[i].kind == "circle" and any(j == i for j, _v in on_b):
            return _circle_halves(pieces[i], a, b)
    work = [q for q in pieces if q.kind != "circle"]
    for p in (a, b):
        out: list[CurvePiece] = []
        done = False
        for q in work:
            u = _param(q, p)
            if u is not None and not done:
                out += _split(q, p, u)
                done = True
            else:
                out.append(q)
        work = out
    # Nodes: piece ends that meet.
    nodes: list[Vec] = []

    def node(p: Vec) -> int:
        for k, n in enumerate(nodes):
            if math.dist(n, p) <= ON_EDGE:
                return k
        nodes.append(p)
        return len(nodes) - 1

    links = [(node(_ends(q)[0]), node(_ends(q)[1])) for q in work]
    start, goal = node(a), node(b)
    paths: list[list[CurvePiece]] = []
    for first in [k for k, (s, e) in enumerate(links) if start in (s, e)]:
        path, at, used = [work[first]], start, {first}
        s, e = links[first]
        at = e if s == start else s
        ok = True
        while at != goal:
            nxt = [k for k, (s2, e2) in enumerate(links) if at in (s2, e2) and k not in used]
            if len(nxt) != 1:
                ok = False
                break
            k = nxt[0]
            used.add(k)
            path.append(work[k])
            s2, e2 = links[k]
            at = e2 if s2 == at else s2
        if ok:
            paths.append(path)
    return paths


def _chain_outline(sketch: Sketch, start: str) -> tuple[list[Vec], str]:
    """Points along the open profile from end point ``start``, and its other end."""
    nodes = _Nodes(sketch)
    curves = [
        c
        for c in sketch.curves()
        if not c.construction and isinstance(c, Line | Arc | Spline) and curve_ends(c)
    ]
    out: list[Vec] = []
    at, used, last = nodes.find(start), set(), start
    while True:
        nxt = [
            c
            for c in curves
            if c.id not in used and at in {nodes.find(p) for p in curve_ends(c) or ()}
        ]
        if not nxt:
            return out, last
        c = nxt[0]
        used.add(c.id)
        s, e = curve_ends(c) or ("", "")
        forward = nodes.find(s) == at
        out += curve_points(sketch, c, reverse=not forward)
        last = e if forward else s
        at = nodes.find(last)


def _piece_points(piece: CurvePiece, start: Vec) -> list[Vec]:
    pts = piece.polyline()
    return pts if math.dist(pts[0], start) <= math.dist(pts[-1], start) else pts[::-1]


def closings(sketch: Sketch, pieces: list[CurvePiece]) -> tuple[str, str, list[Closing]]:
    """The profile's two open end points and the ways the part's edges can close it."""
    ends = open_end_points(sketch)
    if len(ends) != 2:
        raise CloseError(
            "Close Sketch to Model needs one open profile with two open ends. "
            f"This sketch has {len(ends)} open ends. Delete or join curves until one "
            "open profile is left."
        )
    a, b = ends
    pa, pb = sketch.xy(a), sketch.xy(b)
    paths = edge_paths(pieces, pa, pb)
    if not paths:
        raise CloseError(
            "The profile's ends are not both on one loop of the part's edges in the "
            "sketch plane. Move each end onto a part edge, then try again."
        )
    chain, far = _chain_outline(sketch, a)
    if far != b and sketch.xy(far) != pb:
        raise CloseError(
            "The two open ends are on different profiles. Join them into one open "
            "profile, then try again."
        )
    out: list[Closing] = []
    for path in paths:
        outline = list(chain)
        at = pb
        for piece in path[::-1]:  # the path runs from a; the outline comes back from b
            pts = _piece_points(piece, at)
            outline += pts
            at = pts[-1]
        out.append(Closing(path, outline))
    return a, b, out


def close(sketch: Sketch, a: str, b: str, closing: Closing) -> list[str]:
    """Copy ``closing``'s edge pieces into the sketch as fixed curves and join them to
    the profile's ends ``a`` and ``b``. Returns the new curve ids."""
    made = [add_piece(sketch, piece) for piece in closing.pieces]
    for end in (a, b):
        at = sketch.xy(end)
        for cid in made:
            for pid in curve_ends(sketch.entities[cid]) or ():  # type: ignore[arg-type]
                if math.dist(sketch.xy(pid), at) <= ON_EDGE and isinstance(
                    sketch.entities.get(pid), Point
                ):
                    sketch.relate("coincident", end, pid)
    return made
