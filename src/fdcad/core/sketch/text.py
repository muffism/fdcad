"""Sketch text (PHASE4_SPEC P4.8, DECISIONS D323).

A sketch can hold text items. Each is laid out from the system font's glyph
outlines (the kernel's font support), placed in sketch coordinates and becomes
closed regions of the sketch profile, so it can be extruded, cut or wrapped.

Text items are stored in the sketch data under ``texts`` (FDEF_SPEC 6 item 10).
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field
from typing import Any

from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_Transform
from OCP.gp import gp_Ax1, gp_Ax3, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape

ALIGNS = ("left", "center", "right", "full")


@dataclass
class SketchText:
    """One text item. Lengths in mm, angles in radians.

    ``curve`` names a sketch line or arc to follow (empty for a straight base
    line from ``x``, ``y`` turned by ``angle``). ``box`` is the width of the
    text box for alignment (0 for none). ``width`` and ``spacing`` are percent.
    """

    id: str
    text: str
    x: float = 0.0
    y: float = 0.0
    height: float = 5.0
    angle: float = 0.0
    font: str = "sans-serif"
    bold: bool = False
    italic: bool = False
    align: str = "left"
    box: float = 0.0
    width: float = 100.0
    spacing: float = 100.0
    char_angle: float = 0.0
    flip_h: bool = False
    flip_v: bool = False
    curve: str = ""
    #: How far along the curve the text starts, in mm (TR230, D976).
    offset: float = 0.0
    #: Stencil (TR297 item 3, D802): a bridge across every closed counter (the inside of
    #: an O or an A), so the island stays joined when the text is cut through. ``bridge``
    #: is its width in mm; 0 picks 12 percent of the height.
    stencil: bool = False
    bridge: float = 0.0
    #: Character styles (TR121 item 2, D2202): runs, each a dict with ``start`` and
    #: ``end`` (character positions, end not included) and any of ``bold`` and
    #: ``italic`` (true or false, over the whole text's setting) and ``angle`` (radians,
    #: added to ``char_angle``). A later run wins where runs overlap.
    styles: list[dict[str, Any]] = field(default_factory=list)


def char_style(t: SketchText, index: int) -> tuple[bool, bool, float]:
    """Bold, italic and own turn (radians) of character ``index`` of ``t`` (TR121)."""
    bold, italic, angle = t.bold, t.italic, t.char_angle
    for run in t.styles:
        if int(run.get("start", 0)) <= index < int(run.get("end", 0)):
            bold = bool(run.get("bold", bold))
            italic = bool(run.get("italic", italic))
            if "angle" in run:
                angle = t.char_angle + float(run["angle"])
    return bold, italic, angle


def set_style(t: SketchText, start: int, end: int, **style: Any) -> None:
    """Add a style run over characters ``start`` to ``end`` (TR121, D2202). Keys are
    ``bold``, ``italic`` and ``angle``; an empty range does nothing."""
    start, end = max(0, start), min(len(t.text), end)
    if end <= start:
        return
    run: dict[str, Any] = {"start": start, "end": end}
    for key in ("bold", "italic"):
        if key in style:
            run[key] = bool(style[key])
    if "angle" in style:
        run["angle"] = float(style["angle"])
    t.styles.append(run)


def _check_styles(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise ValueError("text styles must be a list")
    out: list[dict[str, Any]] = []
    for run in raw:
        item: dict[str, Any] = {"start": int(run["start"]), "end": int(run["end"])}
        for key in ("bold", "italic"):
            if key in run:
                item[key] = bool(run[key])
        if "angle" in run:
            item["angle"] = float(run["angle"])
        out.append(item)
    return out


_DEFAULTS = SketchText("", "")


def text_to_json(t: SketchText) -> dict[str, Any]:
    """File form: ``id`` and ``text`` always, other keys only when not the default."""
    out: dict[str, Any] = {"id": t.id, "text": t.text}
    for key in (
        "x",
        "y",
        "height",
        "angle",
        "font",
        "bold",
        "italic",
        "align",
        "box",
        "width",
        "spacing",
        "char_angle",
        "flip_h",
        "flip_v",
        "curve",
        "stencil",
        "bridge",
        "offset",
    ):
        value = getattr(t, key)
        if key in ("x", "y") or value != getattr(_DEFAULTS, key):
            out[key] = value
    if t.styles:  # TR121 (D2202)
        out["styles"] = [dict(run) for run in t.styles]
    return out


def text_from_json(raw: dict[str, Any]) -> SketchText:
    """Read one text item. Raises ValueError on bad data."""
    try:
        t = SketchText(str(raw["id"]), str(raw["text"]))
        for key in (
            "x",
            "y",
            "height",
            "angle",
            "box",
            "width",
            "spacing",
            "char_angle",
            "bridge",
            "offset",
        ):
            if key in raw:
                setattr(t, key, float(raw[key]))
        for key in ("bold", "italic", "flip_h", "flip_v", "stencil"):
            if key in raw:
                setattr(t, key, bool(raw[key]))
        for key in ("font", "align", "curve"):
            if key in raw:
                setattr(t, key, str(raw[key]))
        if "styles" in raw:
            t.styles = _check_styles(raw["styles"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"A sketch text item is damaged: {exc}") from exc
    if t.align not in ALIGNS:
        raise ValueError(f"Unknown text alignment '{t.align}'.")
    return t


class TextError(ValueError):
    """The text cannot be laid out (no font, empty text, bad curve)."""


def _font(t: SketchText, bold: bool | None = None, italic: bool | None = None) -> Any:
    from OCP.Font import (
        Font_FA_Bold,
        Font_FA_BoldItalic,
        Font_FA_Italic,
        Font_FA_Regular,
        Font_StrictLevel_Any,
    )
    from OCP.StdPrs import StdPrs_BRepFont
    from OCP.TCollection import TCollection_AsciiString

    aspect = {
        (False, False): Font_FA_Regular,
        (True, False): Font_FA_Bold,
        (False, True): Font_FA_Italic,
        (True, True): Font_FA_BoldItalic,
    }[(t.bold if bold is None else bold, t.italic if italic is None else italic)]
    if t.height <= 0:
        raise TextError("The text height must be greater than zero. Enter a larger height.")
    font = StdPrs_BRepFont()
    name = TCollection_AsciiString(t.font or "sans-serif")
    if not font.FindAndInit(name, aspect, t.height, Font_StrictLevel_Any):
        raise TextError(f"The font '{t.font}' is not installed. Choose another font.")
    if t.width <= 0 or t.spacing <= 0:
        raise TextError(
            "Text width and spacing must be greater than zero. "
            "Enter a width and spacing above zero."
        )
    font.SetWidthScaling(t.width / 100.0)
    return font


@dataclass(frozen=True)
class _Path:
    """Where a distance along the base line lands: point and direction (sketch coords)."""

    kind: str
    origin: tuple[float, float]
    angle: float
    length: float
    centre: tuple[float, float] = (0.0, 0.0)
    radius: float = 0.0
    start: float = 0.0
    sign: float = 1.0
    #: A spline's sampled points and the length up to each (TR230).
    points: tuple[tuple[float, float], ...] = ()
    lengths: tuple[float, ...] = ()

    def at(self, s: float) -> tuple[float, float, float]:
        """Point and base line angle ``s`` mm along the path."""
        if self.kind == "poly":
            return self._along_points(s)
        if self.kind == "arc":
            a = self.start + self.sign * s / self.radius
            x = self.centre[0] + self.radius * math.cos(a)
            y = self.centre[1] + self.radius * math.sin(a)
            return x, y, a + self.sign * math.pi / 2
        c, d = math.cos(self.angle), math.sin(self.angle)
        return self.origin[0] + c * s, self.origin[1] + d * s, self.angle

    def _along_points(self, s: float) -> tuple[float, float, float]:
        import bisect

        pts, lens = self.points, self.lengths
        k = min(max(bisect.bisect_right(lens, s) - 1, 0), len(pts) - 2)
        (x0, y0), (x1, y1) = pts[k], pts[k + 1]
        piece = max(lens[k + 1] - lens[k], 1e-12)
        f = (s - lens[k]) / piece  # past either end the end piece goes on straight
        return x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, math.atan2(y1 - y0, x1 - x0)


def _path(t: SketchText, sketch: Any) -> _Path:
    from fdcad.core.sketch.freeform import sample
    from fdcad.core.sketch.model import Arc, Circle, Line, Spline

    if not t.curve:
        return _Path("line", (t.x, t.y), t.angle, t.box)
    entity = sketch.entities.get(t.curve)
    if isinstance(entity, Line):
        x0, y0 = sketch.xy(entity.p1)
        x1, y1 = sketch.xy(entity.p2)
        return _Path("line", (x0, y0), math.atan2(y1 - y0, x1 - x0), math.hypot(x1 - x0, y1 - y0))
    if isinstance(entity, Arc):
        cx, cy = sketch.xy(entity.center)
        sx, sy = sketch.xy(entity.start)
        ex, ey = sketch.xy(entity.end)
        radius = math.hypot(sx - cx, sy - cy)
        a0, a1 = math.atan2(sy - cy, sx - cx), math.atan2(ey - cy, ex - cx)
        span = (a1 - a0) % (2 * math.pi) if entity.ccw else (a0 - a1) % (2 * math.pi)
        sign = 1.0 if entity.ccw else -1.0
        # Text runs along the arc in its own direction, its top to the left of it.
        return _Path("arc", (sx, sy), 0.0, radius * span, (cx, cy), radius, a0, sign)
    if isinstance(entity, Circle):  # TR230: round from the bottom, so centred is on top
        cx, cy = sketch.xy(entity.center)
        r = entity.radius
        a0 = -math.pi / 2
        start = (cx + r * math.cos(a0), cy + r * math.sin(a0))
        return _Path("arc", start, 0.0, 2 * math.pi * r, (cx, cy), r, a0, -1.0)
    if isinstance(entity, Spline):
        pts = tuple(sample(sketch, entity, 400))
        lens = [0.0]
        for a, b in itertools.pairwise(pts):
            lens.append(lens[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        if len(pts) < 2 or lens[-1] <= 0:
            raise TextError(f"The spline {t.curve} has no length. Pick another curve to follow.")
        return _Path("poly", pts[0], 0.0, lens[-1], points=pts, lengths=tuple(lens))
    raise TextError(
        f"Text can follow a sketch line, arc, circle or spline; {t.curve} is none of these. "
        "Pick one of them to follow."
    )


def layout(t: SketchText, sketch: Any) -> list[TopoDS_Face]:
    """The text's glyph faces in sketch coordinates (the XY plane)."""
    if not t.text.strip():
        raise TextError("The text is empty. Type some text.")
    fonts: dict[tuple[bool, bool], Any] = {(t.bold, t.italic): _font(t)}
    path = _path(t, sketch)
    chars = list(t.text)
    styles = [char_style(t, i) for i in range(len(chars))]  # TR121 (D2202)
    for bold, italic, _turn in styles:
        if (bold, italic) not in fonts:
            fonts[(bold, italic)] = _font(t, bold, italic)
    advances = []
    for i, ch in enumerate(chars):
        nxt = chars[i + 1] if i + 1 < len(chars) else " "
        font = fonts[styles[i][:2]]
        advances.append(float(font.AdvanceX(ch, nxt)) * t.spacing / 100.0)
    total = sum(advances)
    room = path.length if path.length > 0 else total
    start, extra = 0.0, 0.0
    if t.align == "center":
        start = (room - total) / 2
    elif t.align == "right":
        start = room - total
    elif t.align == "full" and len(chars) > 1 and room > total:
        extra = (room - total) / (len(chars) - 1)
    faces: list[TopoDS_Face] = []
    s = start + (t.offset if t.curve else 0.0)  # TR230: a start offset along the curve
    for ch, advance, (bold, italic, turn) in zip(chars, advances, styles, strict=True):
        glyph = fonts[(bold, italic)].RenderGlyph(ch)
        if not glyph.IsNull():
            x, y, a = path.at(s)
            if t.stencil:
                glyph = _bridged(glyph, t.bridge if t.bridge > 0 else 0.12 * t.height)
            faces.extend(_placed(glyph, x, y, a, turn))
        s += advance + extra
    if not faces:
        raise TextError("The text has no visible characters. Type some text.")
    if t.flip_h or t.flip_v:
        faces = [_flipped(f, t, path) for f in faces]
    return faces


def _bridged(glyph: TopoDS_Shape, width: float) -> TopoDS_Shape:
    """``glyph`` with an upright strip ``width`` wide taken out through the middle of each
    closed counter, so the island inside stays joined to the sheet (D802). The glyph is
    in its own upright coordinates, so the strips stand square to the base line."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon
    from OCP.BRepTools import BRepTools
    from OCP.TopAbs import TopAbs_WIRE
    from OCP.TopExp import TopExp_Explorer

    from fdcad.core.features.solids import compound
    from fdcad.core.occ import BRepAlgoAPI_Cut

    strips = []
    for face in _faces(glyph):
        outer = BRepTools.OuterWire_s(face)
        whole = Bnd_Box()
        BRepBndLib.Add_s(face, whole)
        top, bottom = whole.CornerMax().Y() + 1.0, whole.CornerMin().Y() - 1.0
        ex = TopExp_Explorer(face, TopAbs_WIRE)
        while ex.More():
            wire = ex.Current()
            ex.Next()
            if wire.IsSame(outer):
                continue
            box = Bnd_Box()
            BRepBndLib.Add_s(wire, box)
            cx = (box.CornerMin().X() + box.CornerMax().X()) / 2
            half = min(width / 2, (box.CornerMax().X() - box.CornerMin().X()) / 2)
            poly = BRepBuilderAPI_MakePolygon()
            for px, py in ((cx - half, bottom), (cx + half, bottom), (cx + half, top),
                           (cx - half, top)):  # fmt: skip
                poly.Add(gp_Pnt(px, py, 0.0))
            poly.Close()
            strip = BRepBuilderAPI_MakeFace(poly.Wire(), True).Face()
            strips.append(strip)
    if not strips:
        return glyph
    try:
        cut = BRepAlgoAPI_Cut(glyph, compound(strips))
        return cut.Shape() if cut.IsDone() else glyph
    except Exception:  # a glyph the kernel cannot cut keeps its counters
        return glyph


def _faces(shape: TopoDS_Shape) -> list[TopoDS_Face]:
    from fdcad.core.naming.names import faces_of

    return list(faces_of(shape))


def _placed(glyph: TopoDS_Shape, x: float, y: float, angle: float, own: float) -> list[TopoDS_Face]:
    """A glyph turned by its own angle, then by the base line angle, then moved."""
    z = gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))
    turn = gp_Trsf()
    turn.SetRotation(z, angle + own)
    move = gp_Trsf()
    move.SetTranslation(gp_Vec(x, y, 0.0))
    shape = BRepBuilderAPI_Transform(glyph, move.Multiplied(turn), True).Shape()
    return _faces(shape)


def _flipped(face: TopoDS_Face, t: SketchText, path: _Path) -> TopoDS_Face:
    """Mirror about the text's start: horizontal flip reads backward, vertical upside down."""
    x, y, a = path.at(0.0)
    trsf = gp_Trsf()
    if t.flip_h:
        mirror = gp_Trsf()
        mirror.SetMirror(gp_Ax1(gp_Pnt(x, y, 0), gp_Dir(-math.sin(a), math.cos(a), 0)))
        trsf = mirror.Multiplied(trsf)
    if t.flip_v:
        mirror = gp_Trsf()
        mirror.SetMirror(gp_Ax1(gp_Pnt(x, y, 0), gp_Dir(math.cos(a), math.sin(a), 0)))
        trsf = mirror.Multiplied(trsf)
    return TopoDS.Face(BRepBuilderAPI_Transform(face, trsf, True).Shape())


def text_faces(sketch: Any, plane: Any) -> list[TopoDS_Face]:
    """Every text item of ``sketch`` as faces on ``plane`` (a SketchPlane)."""
    move = gp_Trsf()
    move.SetDisplacement(gp_Ax3(), plane.ax3())
    out: list[TopoDS_Face] = []
    for t in sketch.texts:
        for face in layout(t, sketch):
            out.append(TopoDS.Face(BRepBuilderAPI_Transform(face, move, True).Shape()))
    return out
