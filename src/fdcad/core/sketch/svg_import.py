"""Insert SVG (TUTORIAL_REVIEW_SPEC_2 TR117, DECISIONS D863).

An SVG file is read into the same drawing data as a DXF file (``DxfDrawing``),
so Insert SVG shares Insert DXF's options, preview and placement. Lines,
rectangles, circles, ellipses, polylines, polygons and paths are read, with
group and element transforms. Straight path pieces become lines, circular arcs
become arcs, and Bezier curves and other arcs become splines through points on
them. Sizes are in millimetres (the file's width and height in mm or inches
when its view box says how big a user unit is, else 96 user units an inch). The
SVG's downward Y is turned upward. Nothing in the file is run. No Qt.
"""

from __future__ import annotations

import itertools
import math
import re
import xml.etree.ElementTree as ET

from fdcad.core.sketch.dxf_import import MAX_CHARS, DxfDrawing, DxfEntity, DxfError

Matrix = tuple[float, float, float, float, float, float]  # a, b, c, d, e, f
_ID: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
#: Points per Bezier piece for the spline through it.
CURVE_POINTS = 6
_NUM = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def _mul(m: Matrix, n: Matrix) -> Matrix:
    a, b, c, d, e, f = m
    a2, b2, c2, d2, e2, f2 = n
    return (
        a * a2 + c * b2,
        b * a2 + d * b2,
        a * c2 + c * d2,
        b * c2 + d * d2,
        a * e2 + c * f2 + e,
        b * e2 + d * f2 + f,
    )


def _apply(m: Matrix, x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = m
    return a * x + c * y + e, b * x + d * y + f


def _transform(text: str | None) -> Matrix:
    out = _ID
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", text or ""):
        v = [float(t) for t in _NUM.findall(args)]
        if name == "matrix" and len(v) == 6:
            m: Matrix = (v[0], v[1], v[2], v[3], v[4], v[5])
        elif name == "translate" and v:
            m = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0.0)
        elif name == "scale" and v:
            m = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == "rotate" and v:
            t = math.radians(v[0])
            m = (math.cos(t), math.sin(t), -math.sin(t), math.cos(t), 0, 0)
            if len(v) == 3:
                m = _mul(_mul((1, 0, 0, 1, v[1], v[2]), m), (1, 0, 0, 1, -v[1], -v[2]))
        else:
            continue
        out = _mul(out, m)
    return out


def _length(text: str | None) -> float | None:
    """An SVG length in mm, or None when it has no physical unit."""
    if not text:
        return None
    found = re.fullmatch(r"\s*([-+]?[\d.eE+-]+)\s*(mm|cm|in|pt)?\s*", text)
    if found is None or found.group(2) is None:
        return None
    value = float(found.group(1))
    return value * {"mm": 1.0, "cm": 10.0, "in": 25.4, "pt": 25.4 / 72}[found.group(2)]


def _f(el: ET.Element, key: str) -> float:
    try:
        return float(_NUM.findall(el.get(key, "0"))[0])
    except (IndexError, ValueError):
        return 0.0


class _Reader:
    def __init__(self, root_matrix: Matrix) -> None:
        self.out = DxfDrawing(units=4)  # millimetres
        self.root = root_matrix

    def add(self, kind: str, codes: list[tuple[int, float]]) -> None:
        self.out.entities.append(DxfEntity(kind, "SVG", [(c, f"{v:.10g}") for c, v in codes]))

    def line(self, m: Matrix, p: tuple[float, float], q: tuple[float, float]) -> None:
        (x1, y1), (x2, y2) = _apply(m, *p), _apply(m, *q)
        if math.dist((x1, y1), (x2, y2)) > 1e-9:
            self.add("LINE", [(10, x1), (20, y1), (11, x2), (21, y2)])

    def spline(self, m: Matrix, pts: list[tuple[float, float]]) -> None:
        moved = [_apply(m, *p) for p in pts]
        if len(moved) >= 2:
            codes: list[tuple[int, float]] = []
            for x, y in moved:
                codes += [(11, x), (21, y)]
            self.add("SPLINE", codes)

    def circle(self, m: Matrix, cx: float, cy: float, r: float) -> None:
        a, b, c, d, _e, _f2 = m
        sx, sy = math.hypot(a, b), math.hypot(c, d)
        if abs(sx - sy) < 1e-9 * max(sx, 1.0) and abs(a * c + b * d) < 1e-9 * max(sx * sy, 1.0):
            x, y = _apply(m, cx, cy)
            self.add("CIRCLE", [(10, x), (20, y), (40, r * sx)])
        else:  # skewed or squashed by its transform: a closed spline through its points
            n = 24
            self.spline(
                m,
                [
                    (cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n))
                    for k in range(n + 1)
                ],
            )

    def element(self, el: ET.Element, m: Matrix) -> None:
        tag = el.tag.rsplit("}", 1)[-1]
        m = _mul(m, _transform(el.get("transform")))
        if tag in ("g", "svg", "a"):
            for child in el:
                self.element(child, m)
        elif tag == "line":
            self.line(m, (_f(el, "x1"), _f(el, "y1")), (_f(el, "x2"), _f(el, "y2")))
        elif tag == "rect":
            x, y, w, h = _f(el, "x"), _f(el, "y"), _f(el, "width"), _f(el, "height")
            corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
            for i in range(4):
                self.line(m, corners[i], corners[(i + 1) % 4])
        elif tag == "circle":
            self.circle(m, _f(el, "cx"), _f(el, "cy"), _f(el, "r"))
        elif tag == "ellipse":
            cx, cy, rx, ry = _f(el, "cx"), _f(el, "cy"), _f(el, "rx"), _f(el, "ry")
            n = 32
            self.spline(
                m,
                [
                    (
                        cx + rx * math.cos(2 * math.pi * k / n),
                        cy + ry * math.sin(2 * math.pi * k / n),
                    )
                    for k in range(n + 1)
                ],
            )
        elif tag in ("polyline", "polygon"):
            v = [float(t) for t in _NUM.findall(el.get("points", ""))]
            pts = list(zip(v[0::2], v[1::2], strict=False))
            if tag == "polygon" and pts:
                pts.append(pts[0])
            for p, q in itertools.pairwise(pts):
                self.line(m, p, q)
        elif tag == "path":
            self.path(m, el.get("d", ""))
        else:
            self.out.skipped[tag] += 1

    def path(self, m: Matrix, d: str) -> None:
        tokens = re.findall(r"[MmLlHhVvCcSsQqTtAaZz]|" + _NUM.pattern, d)
        i, cmd = 0, ""
        x = y = sx = sy = 0.0
        last_ctrl: tuple[float, float] | None = None
        last_cmd = ""

        def take(n: int) -> list[float]:
            nonlocal i
            vals = [float(t) for t in tokens[i : i + n]]
            i += n
            if len(vals) < n:
                raise DxfError("The SVG file has a path that ends too early. Save it again.")
            return vals

        while i < len(tokens):
            if re.fullmatch(r"[A-Za-z]", tokens[i]):
                cmd = tokens[i]
                i += 1
                if cmd in "Zz":
                    self.line(m, (x, y), (sx, sy))
                    x, y = sx, sy
                    last_cmd = cmd
                    continue
            if not cmd:
                raise DxfError("The SVG file has a path without a command. Save it again.")
            rel = cmd.islower()
            ox, oy = (x, y) if rel else (0.0, 0.0)
            up = cmd.upper()
            if up == "M":
                x, y = (lambda v: (ox + v[0], oy + v[1]))(take(2))
                sx, sy = x, y
                cmd = "l" if rel else "L"  # more pairs after a move are lines
            elif up == "L":
                nx, ny = (lambda v: (ox + v[0], oy + v[1]))(take(2))
                self.line(m, (x, y), (nx, ny))
                x, y = nx, ny
            elif up == "H":
                nx = take(1)[0] + (x if rel else 0.0)
                self.line(m, (x, y), (nx, y))
                x = nx
            elif up == "V":
                ny = take(1)[0] + (y if rel else 0.0)
                self.line(m, (x, y), (x, ny))
                y = ny
            elif up in "CSQT":
                if up == "C":
                    v = take(6)
                    c1, c2, end = (
                        (ox + v[0], oy + v[1]),
                        (ox + v[2], oy + v[3]),
                        (ox + v[4], oy + v[5]),
                    )
                elif up == "S":
                    v = take(4)
                    c1 = (
                        (2 * x - last_ctrl[0], 2 * y - last_ctrl[1])
                        if last_ctrl and last_cmd.upper() in "CS"
                        else (x, y)
                    )
                    c2, end = (ox + v[0], oy + v[1]), (ox + v[2], oy + v[3])
                elif up == "Q":
                    v = take(4)
                    q, end = (ox + v[0], oy + v[1]), (ox + v[2], oy + v[3])
                    c1 = (x + 2 / 3 * (q[0] - x), y + 2 / 3 * (q[1] - y))
                    c2 = (end[0] + 2 / 3 * (q[0] - end[0]), end[1] + 2 / 3 * (q[1] - end[1]))
                else:  # T
                    v = take(2)
                    q = (
                        (2 * x - last_ctrl[0], 2 * y - last_ctrl[1])
                        if last_ctrl and last_cmd.upper() in "QT"
                        else (x, y)
                    )
                    end = (ox + v[0], oy + v[1])
                    c1 = (x + 2 / 3 * (q[0] - x), y + 2 / 3 * (q[1] - y))
                    c2 = (end[0] + 2 / 3 * (q[0] - end[0]), end[1] + 2 / 3 * (q[1] - end[1]))
                p0 = (x, y)
                pts = []
                for k in range(CURVE_POINTS + 1):
                    t = k / CURVE_POINTS
                    u = 1 - t
                    pts.append(
                        (
                            u**3 * p0[0]
                            + 3 * u * u * t * c1[0]
                            + 3 * u * t * t * c2[0]
                            + t**3 * end[0],
                            u**3 * p0[1]
                            + 3 * u * u * t * c1[1]
                            + 3 * u * t * t * c2[1]
                            + t**3 * end[1],
                        )
                    )
                self.spline(m, pts)
                last_ctrl = c2 if up in "CS" else (q if up in "QT" else None)
                x, y = end
            elif up == "A":
                v = take(7)
                end = (ox + v[5], oy + v[6])
                self.arc(m, (x, y), end, v[0], v[1], v[2], bool(v[3]), bool(v[4]))
                x, y = end
            last_cmd = cmd

    def arc(
        self,
        m: Matrix,
        p: tuple[float, float],
        q: tuple[float, float],
        rx: float,
        ry: float,
        rot: float,
        large: bool,
        sweep: bool,
    ) -> None:
        """An elliptical arc as a spline through points on it (the SVG endpoint form)."""
        rx, ry = abs(rx), abs(ry)
        if rx < 1e-12 or ry < 1e-12 or math.dist(p, q) < 1e-12:
            self.line(m, p, q)
            return
        phi = math.radians(rot)
        cp, sp = math.cos(phi), math.sin(phi)
        dx, dy = (p[0] - q[0]) / 2, (p[1] - q[1]) / 2
        x1, y1 = cp * dx + sp * dy, -sp * dx + cp * dy
        scale = x1 * x1 / (rx * rx) + y1 * y1 / (ry * ry)
        if scale > 1:
            rx, ry = rx * math.sqrt(scale), ry * math.sqrt(scale)
        num = rx * rx * ry * ry - rx * rx * y1 * y1 - ry * ry * x1 * x1
        den = rx * rx * y1 * y1 + ry * ry * x1 * x1
        k = math.sqrt(max(num / den, 0.0)) if den > 0 else 0.0
        if large == sweep:
            k = -k
        cxp, cyp = k * rx * y1 / ry, -k * ry * x1 / rx
        cx = cp * cxp - sp * cyp + (p[0] + q[0]) / 2
        cy = sp * cxp + cp * cyp + (p[1] + q[1]) / 2
        t1 = math.atan2((y1 - cyp) / ry, (x1 - cxp) / rx)
        t2 = math.atan2((-y1 - cyp) / ry, (-x1 - cxp) / rx)
        dt = t2 - t1
        if sweep and dt < 0:
            dt += 2 * math.pi
        elif not sweep and dt > 0:
            dt -= 2 * math.pi
        n = max(4, int(abs(dt) / (math.pi / 8)) + 1)
        pts = []
        for j in range(n + 1):
            t = t1 + dt * j / n
            ex, ey = rx * math.cos(t), ry * math.sin(t)
            pts.append((cx + cp * ex - sp * ey, cy + sp * ex + cp * ey))
        self.spline(m, pts)


def parse(text: str) -> DxfDrawing:
    """The SVG file's curves as a drawing in mm (see the module). Raises DxfError."""
    if len(text) > MAX_CHARS:
        raise DxfError("The SVG file is too large to insert. Simplify it and save it again.")
    if "<!ENTITY" in text:
        raise DxfError(
            "The SVG file defines its own entities, which FDCAD does not read. "
            "Save it again without them."
        )
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise DxfError(
            f"The file is not a readable SVG ({exc}). Check the file and try again."
        ) from exc
    unit = 25.4 / 96  # mm per user unit by default
    box = [float(t) for t in _NUM.findall(root.get("viewBox", ""))]
    width = _length(root.get("width"))
    if width is not None and len(box) == 4 and box[2] > 0:
        unit = width / box[2]
    elif width is not None and _f(root, "width") > 0 and not box:
        unit = width / _f(root, "width")
    reader = _Reader((unit, 0.0, 0.0, -unit, 0.0, 0.0))  # mm, and Y up
    reader.element(root, reader.root)
    if not reader.out.entities:
        raise DxfError("The SVG file has no lines or curves to insert. Check the file.")
    return reader.out
