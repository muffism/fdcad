"""Read lines, arcs, circles, polylines, ellipses and splines from a DXF file into a
sketch (TUTORIAL_REVIEW_SPEC TR5, DECISIONS D695).

A small reader of our own for ASCII DXF: the file is a list of group code and
value pairs; only the ENTITIES section is read, plus the drawing units
(``$INSUNITS``) from the header. Blocks, text, hatches and 3D entities are
counted as skipped. The result is plain sketch geometry, under defined: ends
that meet are tied with Coincident, nothing is fixed. It is data only: nothing
in the file is run (CLAUDE.md rule 10). No Qt, no kernel.
"""

from __future__ import annotations

import itertools
import math
from collections import Counter
from dataclasses import dataclass, field

from fdcad.core.sketch.model import Arc, Ellipse, EllipseArc, Line, Point, Sketch, Spline

Vec = tuple[float, float]
#: Millimetres per drawing unit, by ``$INSUNITS`` code. 0 (no unit) is None.
UNIT_MM: dict[int, float] = {
    1: 25.4,
    2: 304.8,
    3: 1609344.0,
    4: 1.0,
    5: 10.0,
    6: 1000.0,
    8: 0.0000254,
    9: 0.0254,
    10: 914.4,
    11: 1e-7,
    12: 1e-6,
    13: 1e-3,
    14: 100.0,
    15: 10000.0,
    16: 100000.0,
}
#: Unit names for the panel, by code.
UNIT_NAMES = {
    1: "in",
    2: "ft",
    3: "mile",
    4: "mm",
    5: "cm",
    6: "m",
    8: "microinch",
    9: "mil",
    10: "yd",
    11: "angstrom",
    12: "nm",
    13: "micron",
    14: "dm",
    15: "dam",
    16: "hm",
}
SUPPORTED = ("LINE", "ARC", "CIRCLE", "LWPOLYLINE", "POLYLINE", "ELLIPSE", "SPLINE", "INSERT")
#: Ends closer than this (in drawing units, after scaling: mm) are joined.
JOIN = 1e-6
#: Largest file read, in characters (a guard against huge files).
MAX_CHARS = 50_000_000
#: The most entities one insert adds to a sketch (D709).
MAX_ENTITIES = 50_000


class DxfError(ValueError):
    """The file cannot be read as DXF, or has nothing to insert."""


@dataclass
class DxfEntity:
    """One entity: its type, layer and group codes (code to list of values)."""

    kind: str
    layer: str
    codes: list[tuple[int, str]] = field(default_factory=list)

    def get(self, code: int, default: float = 0.0) -> float:
        """The first value of a numeric group code."""
        for c, v in self.codes:
            if c == code:
                return number(v)
        return default

    def all(self, code: int) -> list[float]:
        """Every value of a numeric group code, in order."""
        return [number(v) for c, v in self.codes if c == code]


def number(text: str) -> float:
    """A DXF number. Raises DxfError for text that is not a finite number (audit D12
    item 6, D709), so bad values never reach the sketch."""
    try:
        value = float(text)
    except ValueError as exc:
        raise DxfError(
            f'The DXF file has a value that is not a number ("{text[:20]}"). '
            "Save the drawing again from the program that made it."
        ) from exc
    if not math.isfinite(value):
        raise DxfError(
            "The DXF file has a value that is not a finite number. "
            "Save the drawing again from the program that made it."
        )
    return value


@dataclass
class DxfDrawing:
    """What was read: the units code (0 when the file has none), the entities, the
    skipped entity types with counts, and the layers in order."""

    units: int = 0
    #: ``$MEASUREMENT``: 0 imperial, 1 metric, None when absent. A hint for the unit
    #: when ``$INSUNITS`` is missing (audit D item 18, D742).
    measurement: int | None = None
    entities: list[DxfEntity] = field(default_factory=list)
    skipped: Counter[str] = field(default_factory=Counter)
    #: Block definitions by name: their base point and entities (audit D item 4, D722).
    blocks: dict[str, tuple[tuple[float, float], list[DxfEntity]]] = field(default_factory=dict)
    #: Layers that are frozen or off: their entities are not shown, so not imported.
    hidden_layers: set[str] = field(default_factory=set)

    @property
    def layers(self) -> list[str]:
        """Layers that hold supported entities, in file order."""
        return list(dict.fromkeys(e.layer for e in self.entities))


def _pairs(text: str) -> list[tuple[int, str]]:
    # Only line ends split the pairs: a form feed or other separator inside a text value
    # made the whole file fail (audit D item 11, D733).
    lines = text.replace(chr(13) + chr(10), chr(10)).replace(chr(13), chr(10)).split(chr(10))
    if len(lines) % 2:
        lines = lines[:-1]
    out = []
    for i in range(0, len(lines), 2):
        try:
            code = int(lines[i].strip())
        except ValueError as exc:
            raise DxfError(
                "The file is not an ASCII DXF file. Save it as ASCII DXF and try again."
            ) from exc
        out.append((code, lines[i + 1].strip()))
    return out


def parse(text: str) -> DxfDrawing:
    """Read a DXF file's text. Raises DxfError when it is not DXF."""
    if len(text) > MAX_CHARS:
        raise DxfError("The DXF file is too large to insert into a sketch.")
    if text.startswith("AutoCAD Binary DXF"):
        raise DxfError("Binary DXF files cannot be read. Save it as ASCII DXF and try again.")
    pairs = _pairs(text)
    drawing = DxfDrawing()
    section = ""
    current: DxfEntity | None = None
    polyline: DxfEntity | None = None
    target = drawing.entities  # where finished entities go: the drawing or a block
    header: DxfEntity | None = None  # a BLOCK or LAYER record being read
    i = 0

    def finish() -> None:
        nonlocal header, target
        if current is not None and current.kind != "VERTEX":
            target.append(current)
        if header is not None and header.kind == "LAYER":
            name = next((v for c, v in header.codes if c == 2), "")
            flags = next((v for c, v in header.codes if c == 70), "0")
            color = next((v for c, v in header.codes if c == 62), "7")
            frozen = _int(flags) & 1 == 1
            if name and (frozen or _int(color) < 0):
                drawing.hidden_layers.add(name)
            header = None
        elif header is not None and header.kind == "BLOCK":
            name = next((v for c, v in header.codes if c == 2), "")
            base = (header.get(10), header.get(20))
            items: list[DxfEntity] = []
            if name:
                drawing.blocks[name] = (base, items)
            target = items
            header = None

    while i < len(pairs):
        code, value = pairs[i]
        if code == 0 and value == "SECTION" and i + 1 < len(pairs):
            section = pairs[i + 1][1]
            i += 2
            continue
        if section in ("BLOCKS", "TABLES") and code == 0:
            finish()
            current = None
            if value in ("BLOCK", "LAYER") and (section == "BLOCKS") == (value == "BLOCK"):
                header = DxfEntity(value, "0")
                i += 1
                continue
            if value in ("ENDBLK", "ENDSEC"):
                target = drawing.entities
                if value == "ENDSEC":
                    section = ""
                i += 1
                continue
        if header is not None:
            header.codes.append((code, value))
            i += 1
            continue
        if section == "HEADER" and code == 9 and value == "$INSUNITS" and i + 1 < len(pairs):
            try:
                drawing.units = int(float(pairs[i + 1][1]))
            except ValueError:
                drawing.units = 0
            i += 2
            continue
        if section == "HEADER" and code == 9 and value == "$MEASUREMENT" and i + 1 < len(pairs):
            try:
                drawing.measurement = int(float(pairs[i + 1][1]))
            except ValueError:
                drawing.measurement = None
            i += 2
            continue
        if section not in ("ENTITIES", "BLOCKS"):
            i += 1
            continue
        if code == 0:
            if current is not None and current.kind != "VERTEX":
                target.append(current)
            current = None
            if value == "ENDSEC":
                section = ""
            elif value == "VERTEX" and polyline is not None:
                current = DxfEntity("VERTEX", polyline.layer)
                polyline.codes.append((-1, "VERTEX"))
            elif value == "SEQEND":
                polyline = None
            elif value in SUPPORTED:
                current = DxfEntity(value, "0")
                if value == "POLYLINE":
                    polyline = current
            else:
                drawing.skipped[value] += 1
            i += 1
            continue
        if current is not None:
            if code == 8 and current.kind != "VERTEX":
                current.layer = value
            elif current.kind == "VERTEX" and polyline is not None:
                if code in (10, 20, 42, 70):
                    polyline.codes.append((code + 1000, value))  # vertex codes kept apart
            else:
                current.codes.append((code, value))
        i += 1
    if current is not None and current.kind != "VERTEX":
        target.append(current)
    return drawing


def _float(text: str) -> float:
    try:
        return float(text)
    except ValueError:
        return 0.0


def _int(text: str) -> int:
    try:
        return int(float(text))
    except ValueError:
        return 0


# Building sketch geometry ---------------------------------------------------------------


@dataclass
class Placement:
    """How the drawing lands in the sketch: millimetres per drawing unit, the turn in
    radians, the offset in mm, and which layers to take (None: all)."""

    scale: float = 1.0
    angle: float = 0.0
    offset: Vec = (0.0, 0.0)
    layers: set[str] | None = None

    def at(self, x: float, y: float) -> Vec:
        """A drawing point in sketch mm."""
        c, s = math.cos(self.angle), math.sin(self.angle)
        x, y = x * self.scale, y * self.scale
        return c * x - s * y + self.offset[0], s * x + c * y + self.offset[1]


@dataclass
class Built:
    """New top level entity ids, and how many entities were left out (with why)."""

    entities: list[str] = field(default_factory=list)
    skipped: Counter[str] = field(default_factory=Counter)


class _Builder:
    def __init__(self, sketch: Sketch, place: Placement) -> None:
        self.sk, self.place = sketch, place
        self.out = Built()
        #: End points by grid cell, so joining stays linear (audit D12 item 5, D709).
        self.cells: dict[tuple[int, int], list[tuple[Vec, str]]] = {}
        self.tol = JOIN * max(1.0, self.place.scale)

    def point(self, p: Vec) -> str:
        pid = self.sk.add_point(p[0], p[1])
        cx, cy = math.floor(p[0] / self.tol), math.floor(p[1] / self.tol)
        found = next(
            (
                other
                for dx in (-1, 0, 1)
                for dy in (-1, 0, 1)
                for q, other in self.cells.get((cx + dx, cy + dy), ())
                if math.dist(p, q) <= self.tol
            ),
            None,
        )
        if found is not None:
            self.sk.relate("coincident", pid, found)
        self.cells.setdefault((cx, cy), []).append((p, pid))
        return pid

    def line(self, a: Vec, b: Vec) -> None:
        if math.dist(a, b) <= JOIN:
            self.out.skipped["zero length"] += 1
            return
        p1, p2 = self.point(a), self.point(b)
        lid = self.sk.new_id()
        self.sk.entities[lid] = Line(lid, p1, p2)
        self.out.entities.append(lid)

    def arc(self, c: Vec, r: float, a0: float, a1: float) -> None:
        """A counter clockwise arc in drawing angles (radians), already placed centre."""
        if r <= JOIN:
            self.out.skipped["zero radius"] += 1
            return
        a0 += self.place.angle
        a1 += self.place.angle
        s = (c[0] + r * math.cos(a0), c[1] + r * math.sin(a0))
        e = (c[0] + r * math.cos(a1), c[1] + r * math.sin(a1))
        centre = self.sk.add_point(*c)
        ps, pe = self.point(s), self.point(e)
        aid = self.sk.new_id()
        self.sk.entities[aid] = Arc(aid, centre, ps, pe, True)
        self.out.entities.append(aid)

    def circle(self, c: Vec, r: float) -> None:
        if r <= JOIN:
            self.out.skipped["zero radius"] += 1
            return
        self.out.entities.append(self.sk.add_circle(c[0], c[1], r))

    def bulge(self, a: Vec, b: Vec, bulge: float) -> None:
        """A polyline piece: straight, or an arc whose bulge is tan(sweep / 4)."""
        if abs(bulge) < 1e-12:
            self.line(a, b)
            return
        chord = math.dist(a, b)
        if chord <= JOIN:
            return
        sweep = 4 * math.atan(bulge)
        r = chord / (2 * math.sin(abs(sweep) / 2))
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        h = r * math.cos(abs(sweep) / 2)
        nx, ny = -(b[1] - a[1]) / chord, (b[0] - a[0]) / chord
        side = 1.0 if (bulge > 0) == (abs(sweep) < math.pi) else -1.0
        c = (mx + side * h * nx, my + side * h * ny)
        start, end = (a, b) if bulge > 0 else (b, a)
        a0 = math.atan2(start[1] - c[1], start[0] - c[0]) - self.place.angle
        a1 = math.atan2(end[1] - c[1], end[0] - c[0]) - self.place.angle
        self.arc(c, r, a0, a1)


def _poly_points(e: DxfEntity) -> tuple[list[tuple[float, float, float]], bool]:
    """Vertices (x, y, bulge) of an LWPOLYLINE or POLYLINE, and whether it is closed."""
    if e.kind == "LWPOLYLINE":
        pts: list[list[float]] = []
        for code, value in e.codes:
            if code == 10:
                pts.append([number(value), 0.0, 0.0])
            elif code == 20 and pts:
                pts[-1][1] = number(value)
            elif code == 42 and pts:
                pts[-1][2] = number(value)
        closed = int(e.get(70)) & 1 == 1
        return [(p[0], p[1], p[2]) for p in pts], closed
    out: list[list[float]] = []
    for code, value in e.codes:
        if code == -1:
            out.append([0.0, 0.0, 0.0])
        elif out and code == 1010:
            out[-1][0] = number(value)
        elif out and code == 1020:
            out[-1][1] = number(value)
        elif out and code == 1042:
            out[-1][2] = number(value)
    closed = int(e.get(70)) & 1 == 1
    return [(p[0], p[1], p[2]) for p in out], closed


def build(drawing: DxfDrawing, sketch: Sketch, place: Placement) -> Built:
    """Add the drawing's geometry to ``sketch``. Raises DxfError when nothing could be
    added."""
    b = _Builder(sketch, place)
    wanted = [e for e in drawing.entities if place.layers is None or e.layer in place.layers]
    if len(wanted) > MAX_ENTITIES:
        raise DxfError(
            f"The DXF file has more than {MAX_ENTITIES} entities, too many for one sketch. "
            "Insert one layer at a time, or simplify the drawing."
        )
    _build_all(b, drawing, drawing.entities, place, 0)
    if not b.out.entities:
        raise DxfError(
            "The DXF file has no lines, arcs, circles, polylines, ellipses or splines to insert."
        )
    return b.out


def _shown(e: DxfEntity, drawing: DxfDrawing, b: _Builder) -> bool:
    """False for paper space, invisible entities and those on frozen or off layers,
    which the drawing does not show in model space (audit D item 5, D722)."""
    codes = dict(e.codes)
    if codes.get(67, "0").strip() == "1":
        b.out.skipped["paper space"] += 1
        return False
    if codes.get(60, "0").strip() == "1":
        b.out.skipped["invisible"] += 1
        return False
    if e.layer in drawing.hidden_layers:
        b.out.skipped["hidden layer"] += 1
        return False
    return True


def _insert_place(e: DxfEntity, base: tuple[float, float], place: Placement) -> Placement | None:
    """Where a block's entities land for one INSERT (audit D item 4, D722), or None
    when it is mirrored or scaled unevenly (circles would not stay round)."""
    sx = e.get(41, 1.0)
    sy = e.get(42, sx)
    if sx <= 0 or abs(sx - sy) > 1e-9 * max(1.0, abs(sx)):
        return None
    r = math.radians(e.get(50))
    c, s = math.cos(r), math.sin(r)
    bx, by = base[0] * sx, base[1] * sx
    ox = e.get(10) - (c * bx - s * by)
    oy = e.get(20) - (s * bx + c * by)
    return Placement(place.scale * sx, place.angle + r, place.at(ox, oy), place.layers)


def _build_all(
    b: _Builder, drawing: DxfDrawing, entities: list[DxfEntity], place: Placement, depth: int
) -> None:
    """Add ``entities`` at ``place``; an INSERT adds its block's entities, nested up to
    8 deep."""
    saved = b.place
    b.place = place
    try:
        for e in entities:
            if depth == 0 and place.layers is not None and e.layer not in place.layers:
                continue
            if not _shown(e, drawing, b):
                continue
            if e.kind != "INSERT":
                _build_one(b, e, place)
                continue
            name = next((v for c, v in e.codes if c == 2), "")
            block = drawing.blocks.get(name)
            inner = _insert_place(e, block[0], place) if block is not None else None
            if block is None or depth >= 8:
                b.out.skipped["missing block"] += 1
            elif inner is None:
                b.out.skipped["mirrored or stretched block"] += 1
            else:
                _build_all(b, drawing, block[1], inner, depth + 1)
    finally:
        b.place = saved


def _build_one(b: _Builder, e: DxfEntity, place: Placement) -> None:
    """Add one LINE, CIRCLE, ARC, polyline, ELLIPSE or SPLINE."""
    at = place.at
    k = e.kind
    if any(c in (30, 31) and abs(_float(v)) > 1e-9 for c, v in e.codes):
        b.out.skipped["Z flattened"] += 1  # counted, still added at Z 0 (D733)
    if k == "LINE":
        b.line(at(e.get(10), e.get(20)), at(e.get(11), e.get(21)))
    elif k == "CIRCLE":
        # Seen from below (extrusion -Z), the entity's own X runs the other way
        # (audit D item 2, D722).
        sx = -1.0 if e.get(230, 1.0) < 0 else 1.0
        b.circle(at(sx * e.get(10), e.get(20)), e.get(40) * place.scale)
    elif k == "ARC":
        c = at(e.get(10), e.get(20))
        if e.get(230, 1.0) < 0:  # seen from below: the arc runs the other way
            c = at(-e.get(10), e.get(20))
            a0, a1 = math.radians(180 - e.get(51)), math.radians(180 - e.get(50))
        else:
            a0, a1 = math.radians(e.get(50)), math.radians(e.get(51))
        b.arc(c, e.get(40) * place.scale, a0, a1)
    elif k == "POLYLINE" and _int(str(e.get(70))) & (8 | 16 | 64):
        # 3D polylines and polygon or polyface meshes are not sketch curves (D733).
        b.out.skipped["3D polyline or mesh"] += 1
    elif k in ("LWPOLYLINE", "POLYLINE"):
        pts, closed = _poly_points(e)
        if e.get(230, 1.0) < 0:  # seen from below: mirror X, bulges turn the other way
            pts = [(-x, y, -bulge) for x, y, bulge in pts]
        pairs = list(itertools.pairwise(pts))
        if closed and len(pts) >= 2:
            # Two vertices with bulges is the usual DXF circle (audit D item 1).
            pairs.append((pts[-1], pts[0]))
        for p, q in pairs:
            b.bulge(at(p[0], p[1]), at(q[0], q[1]), p[2])
    elif k == "ELLIPSE":
        _ellipse(b, e, place)
    elif k == "SPLINE":
        _spline(b, e, place)


def _ellipse(b: _Builder, e: DxfEntity, place: Placement) -> None:
    c = place.at(e.get(10), e.get(20))
    mx, my = e.get(11), e.get(21)
    ratio = e.get(40, 1.0)
    major_end = place.at(e.get(10) + mx, e.get(20) + my)
    a = math.dist(c, major_end)
    if a <= JOIN or ratio <= 0:
        b.out.skipped["zero size"] += 1
        return
    phi = math.atan2(major_end[1] - c[1], major_end[0] - c[0])
    # Seen from below (extrusion -Z) the minor axis points the other way, so the
    # parameters run clockwise (audit D item 2).
    turn = -1.0 if e.get(230, 1.0) < 0 else 1.0
    minor_end = (c[0] - a * ratio * math.sin(phi), c[1] + a * ratio * math.cos(phi))
    sk = b.sk
    cid, ma, mi = sk.add_point(*c), sk.add_point(*major_end), sk.add_point(*minor_end)
    t0, t1 = e.get(41, 0.0), e.get(42, 2 * math.pi)
    eid = sk.new_id()
    if abs((t1 - t0) % (2 * math.pi)) < 1e-9 and abs(t1 - t0) > 1e-9:
        sk.entities[eid] = Ellipse(eid, cid, ma, mi)
    else:

        def on(t: float) -> Vec:
            x, y = a * math.cos(t), turn * a * ratio * math.sin(t)
            return c[0] + x * math.cos(phi) - y * math.sin(phi), c[1] + x * math.sin(
                phi
            ) + y * math.cos(phi)

        start, end = (on(t0), on(t1)) if turn > 0 else (on(t1), on(t0))
        sk.entities[eid] = EllipseArc(eid, cid, ma, mi, b.point(start), b.point(end))
    b.out.entities.append(eid)


def _spline(b: _Builder, e: DxfEntity, place: Placement) -> None:
    """A spline through the file's fit points, or else its control points (D695)."""
    xs, ys = e.all(11), e.all(21)
    if len(xs) < 2:
        xs, ys = e.all(10), e.all(20)
    pts = [place.at(x, y) for x, y in zip(xs, ys, strict=False)]
    pts = [p for i, p in enumerate(pts) if i == 0 or math.dist(p, pts[i - 1]) > JOIN]
    if len(pts) < 2:
        b.out.skipped["too few points"] += 1
        return
    from fdcad.core.sketch.freeform import default_handles

    handles = default_handles(pts)
    sk = b.sk
    ids = [b.point(p) if i in (0, len(pts) - 1) else sk.add_point(*p) for i, p in enumerate(pts)]
    hids = [sk.add_point(*h, construction=True) for h in handles]
    sid = sk.new_id()
    sk.entities[sid] = Spline(sid, ids, hids)
    b.out.entities.append(sid)


def extent(drawing: DxfDrawing) -> tuple[Vec, Vec] | None:
    """Lower left and upper right of the drawing (from its points), in drawing units."""
    sk = Sketch()
    try:
        build(drawing, sk, Placement())
    except DxfError:
        return None
    pts = [(p.x, p.y) for p in sk.entities.values() if isinstance(p, Point)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs), min(ys)), (max(xs), max(ys))
