"""Sketch Picture tool (PHASE2_SPEC P2.9). Pure Python, no Qt.

The panel's Insert Picture button reads the file and calls :meth:`insert`.
Dragging inside a picture moves it, dragging a corner resizes it, and with the
scale tool on, the two handles of the scale line are dragged onto known points
and the true length is typed.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from fdcad.core.sketch.ops.geom import Vec, dist
from fdcad.core.sketch.picture import (
    Picture,
    block_id,
    make_block,
    new_picture,
    scale_factor,
)
from fdcad.ui.sketch_tools.edit import SketchEdit
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.tool_options import Option
from fdcad.ui.sketch_tools.tools import Preview, Tool


class PictureTool(Tool):
    """Insert, place and scale sketch pictures."""

    name, label = "picture", "Sketch Picture"
    #: Pictures have no snaps (P2.9 item 4).
    raw_cursor = True
    construction_option = False
    options = (
        Option("insert", "Insert Picture...", "file"),
        Option("x", "Origin X", "length"),
        Option("y", "Origin Y", "length"),
        Option("angle", "Angle", "angle"),
        Option("width", "Width", "length"),
        Option("height", "Height", "length"),
        Option("lock_aspect", "Lock aspect ratio", "bool"),
        Option("flip_h", "Flip horizontally", "bool"),
        Option("flip_v", "Flip vertically", "bool"),
        Option("transparency", "Transparency (%)", "int", low=0, high=100),
        Option(  # TR116 (D977)
            "clear_colour",
            "See-through colour",
            "text",
            tip="Type a colour such as #FFFFFF to show it see through, for example a white "
            "background. Leave it empty for none.",
        ),
        Option("clear_tolerance", "Colour tolerance (%)", "int", low=0, high=100),
        Option("scale_tool", "Enable scale tool", "bool"),
        Option("scale_length", "Scale line length", "length"),
        Option("delete", "Delete Picture", "button"),
        # TR116 item 2 (D1711): trace a region into sketch lines.
        Option("trace_colour", "Trace Colour Region", "button"),
        Option("trace_box", "Trace Box", "button"),
        Option("trace_tolerance", "Trace colour tolerance (%)", "int", low=0, high=100),
    )

    def __init__(self, edit: SketchEdit) -> None:
        super().__init__(edit)
        self.message = ""
        #: The picture the panel edits.
        self.current: str | None = edit.sketch.pictures[-1].id if edit.sketch.pictures else None
        self.scale_tool = False
        #: The scale line's two handles in sketch mm.
        self.handles: list[Vec] = []
        #: The drag in progress: ("move" | "corner" | "handle", index, press point, start).
        self.drag: tuple[str, int, Vec, object] | None = None
        self._changed = False
        #: Trace (TR116 item 2): the next click picks a region by colour ("colour"),
        #: or two clicks a box ("box"); the first box corner once clicked.
        self.trace_mode: str | None = None
        self.trace_corner: Vec | None = None
        self.trace_tolerance = 20
        #: The canvas hands a way to read a picture's pixels (numpy RGBA, or None).
        self.pixels_of: Callable[[str], Any] = lambda _block: None

    # Panel values ---------------------------------------------------------------------

    @property
    def prompt(self) -> str:
        """What to do next."""
        if self.picture is None:
            return "Click Insert Picture to place a PNG, JPEG or BMP image."
        if self.trace_mode == "colour":
            return "Click the colour region of the picture to trace."
        if self.trace_mode == "box":
            if self.trace_corner is None:
                return "Click one corner of the box to trace."
            return "Click the other corner of the box."
        if self.scale_tool:
            return "Drag the two handles onto a known length, then type its true length."
        return "Drag the picture to move it, or a corner to resize it."

    @property
    def picture(self) -> Picture | None:
        """The picture being edited."""
        return next((p for p in self.edit.sketch.pictures if p.id == self.current), None)

    def _get(self, key: str, default: object) -> object:
        pic = self.picture
        return default if pic is None else getattr(pic, key)

    def _set(self, change: str, value: object) -> None:
        pic = self.picture
        if pic is None:
            return
        self.edit.checkpoint()
        if change == "x":
            pic.origin = (float(value), pic.origin[1])  # type: ignore[arg-type]
        elif change == "y":
            pic.origin = (pic.origin[0], float(value))  # type: ignore[arg-type]
        elif change in ("width", "height"):
            size = float(value)  # type: ignore[arg-type]
            if size <= 0:
                self.edit.discard_checkpoint()
                return
            if pic.lock_aspect:
                ratio = pic.height / pic.width
                pic.width, pic.height = (
                    (size, size * ratio)
                    if change == "width"
                    else (
                        size / ratio,
                        size,
                    )
                )
            else:
                setattr(pic, change, size)
        elif change == "transparency":
            pic.transparency = min(max(float(value) / 100.0, 0.0), 1.0)  # type: ignore[arg-type]
        elif change == "clear_colour":
            from fdcad.core.sketch.picture import valid_colour

            colour = valid_colour(str(value))
            if colour is None:
                self.edit.discard_checkpoint()
                self.message = (
                    "Type a colour as six hex digits, such as #FFFFFF, or leave it empty."
                )
                return
            pic.clear_colour = colour
        elif change == "clear_tolerance":
            pic.clear_tolerance = min(max(float(value) / 100.0, 0.0), 1.0)  # type: ignore[arg-type]
        else:
            setattr(pic, change, value)
        self._changed = True

    x = property(lambda self: self._get("origin", (0.0, 0.0))[0], lambda self, v: self._set("x", v))
    y = property(lambda self: self._get("origin", (0.0, 0.0))[1], lambda self, v: self._set("y", v))
    angle = property(lambda self: self._get("angle", 0.0), lambda self, v: self._set("angle", v))
    width = property(lambda self: self._get("width", 1.0), lambda self, v: self._set("width", v))
    height = property(lambda self: self._get("height", 1.0), lambda self, v: self._set("height", v))
    lock_aspect = property(
        lambda self: self._get("lock_aspect", True), lambda self, v: self._set("lock_aspect", v)
    )
    flip_h = property(
        lambda self: self._get("flip_h", False), lambda self, v: self._set("flip_h", v)
    )
    flip_v = property(
        lambda self: self._get("flip_v", False), lambda self, v: self._set("flip_v", v)
    )
    transparency = property(
        lambda self: round(float(self._get("transparency", 0.0)) * 100),
        lambda self, v: self._set("transparency", v),
    )
    clear_colour = property(
        lambda self: str(self._get("clear_colour", "")),
        lambda self, v: self._set("clear_colour", v),
    )
    clear_tolerance = property(
        lambda self: round(float(self._get("clear_tolerance", 0.1)) * 100),
        lambda self, v: self._set("clear_tolerance", v),
    )

    @property
    def scale_length(self) -> float:
        """The scale line's current length."""
        return dist(*self.handles) if len(self.handles) == 2 else 0.0

    @scale_length.setter
    def scale_length(self, value: float) -> None:
        """Scale the picture so the scale line gets this length (P2.9 item 3)."""
        pic = self.picture
        if pic is None or len(self.handles) != 2:
            self.message = "Turn on the scale tool and drag its handles first."
            return
        try:
            factor = scale_factor(self.handles[0], self.handles[1], float(value))
        except ValueError as exc:
            self.message = str(exc)
            return
        self.edit.checkpoint()
        a = self.handles[0]
        pic.scale_about(a, factor)
        b = self.handles[1]
        self.handles[1] = (a[0] + (b[0] - a[0]) * factor, a[1] + (b[1] - a[1]) * factor)
        self._changed = True

    def option_changed(self, key: str) -> bool:
        """Report whether a panel change altered the sketch."""
        if key == "scale_tool":
            self._place_handles()
            return False
        if key == "delete":
            return self.delete_current()
        if key in ("trace_colour", "trace_box"):
            if self.picture is None:
                self.message = "Insert a picture first, then trace it."
                return False
            self.trace_mode = key[6:]
            self.trace_corner = None
            return False
        changed, self._changed = self._changed, False
        return changed

    def _place_handles(self) -> None:
        pic = self.picture
        if not self.scale_tool or pic is None:
            self.handles = []
            return
        c = pic.corners()
        self.handles = [
            (c[0][0] + (c[1][0] - c[0][0]) / 4, c[0][1] + (c[1][1] - c[0][1]) / 4),
            (c[0][0] + (c[1][0] - c[0][0]) * 3 / 4, c[0][1] + (c[1][1] - c[0][1]) * 3 / 4),
        ]

    # Inserting and deleting -------------------------------------------------------------

    def insert(self, data: bytes, filename: str, fmt: str, width_px: int, height_px: int) -> bool:
        """Place an image at the sketch origin, one pixel to one millimetre, as one
        undo step. The image is embedded (P2.9 item 1)."""
        try:
            block = make_block(data, filename, fmt)
        except ValueError as exc:
            self.message = str(exc)
            return False
        key = block_id(data)
        sk = self.edit.sketch
        used = {p.id for p in sk.pictures}
        pid = next(f"p{n}" for n in range(1, len(used) + 2) if f"p{n}" not in used)
        self.edit.checkpoint()
        sk.pictures.append(new_picture(pid, key, width_px, height_px))
        self.edit.blocks[key] = block
        self.current = pid
        self._place_handles()
        return True

    def delete_current(self) -> bool:
        """Remove the picture being edited (its file leaves the document on OK if no
        other sketch uses it)."""
        pic = self.picture
        if pic is None:
            return False
        self.edit.checkpoint()
        self.edit.sketch.pictures.remove(pic)
        pictures = self.edit.sketch.pictures
        self.current = pictures[-1].id if pictures else None
        self.handles = []
        return True

    # Dragging -----------------------------------------------------------------------------

    @property
    def busy(self) -> bool:
        """True while a drag is in progress."""
        return self.drag is not None

    def _pixel(self, pic: Picture, size: tuple[int, int], at: Vec) -> tuple[int, int]:
        """The (row, column) of the image pixel under sketch point ``at``."""
        u, v = pic.local(at)
        if pic.flip_h:
            u = pic.width - u
        if pic.flip_v:
            v = pic.height - v
        w, h = size
        col = int(min(max(u / pic.width * w, 0), w - 1))
        row = int(min(max((pic.height - v) / pic.height * h, 0), h - 1))
        return row, col

    def _trace_click(self, at: Vec) -> bool:
        """A click while tracing: the colour region under it, or a box corner."""
        from fdcad.core.sketch.trace import TraceError, box_region, colour_region, trace

        pic = self.picture
        if pic is None or not pic.contains(at):
            self.message = "Click on the picture to trace it."
            return False
        pixels = self.pixels_of(pic.block)
        if pixels is None:
            self.message = "The picture's image cannot be read. Insert the picture again."
            self.trace_mode = None
            return False
        h, w = pixels.shape[:2]
        tol = self.trace_tolerance / 100.0
        if self.trace_mode == "box" and self.trace_corner is None:
            self.trace_corner = at
            return False
        if self.trace_mode == "box":
            assert self.trace_corner is not None
            a = self._pixel(pic, (w, h), self.trace_corner)
            region, step = box_region(pixels, a, self._pixel(pic, (w, h), at), tol)
        else:
            region, step = colour_region(pixels, self._pixel(pic, (w, h), at), tol)
        self.trace_mode, self.trace_corner = None, None
        self.edit.checkpoint()
        try:
            made = trace(self.edit.sketch, pic, region, step, (w, h))
        except TraceError as exc:
            self.edit.discard_checkpoint()
            self.message = str(exc)
            return False
        self.drawn = made
        self.message = f"Traced {len(made)} lines. Edit or delete them like any sketch lines."
        return True

    def click(self, snap: Snap) -> bool:
        """A press: pick a handle, a corner or a picture to drag; while tracing, pick
        the region (TR116 item 2)."""
        at = snap.xy
        self.cursor = snap
        if self.trace_mode is not None:
            return self._trace_click(at)
        for i, h in enumerate(self.handles):
            if dist(h, at) <= self.tolerance:
                self.drag = ("handle", i, at, h)
                return False
        pic = self.picture
        if pic is not None:
            for i, c in enumerate(pic.corners()):
                if dist(c, at) <= self.tolerance:
                    self.edit.checkpoint()
                    self.drag = ("corner", i, at, (pic.origin, pic.width, pic.height))
                    return False
        hit = next((p for p in reversed(self.edit.sketch.pictures) if p.contains(at)), None)
        if hit is not None:
            self.current = hit.id
            self.edit.checkpoint()
            self.drag = ("move", 0, at, hit.origin)
        return False

    def hover(self, snap: Snap) -> Snap:
        """Follow the drag."""
        self.cursor = snap
        drag, pic = self.drag, self.picture
        if drag is None:
            return snap
        kind, index, press, start = drag
        dx, dy = snap.x - press[0], snap.y - press[1]
        if kind == "handle":
            assert isinstance(start, tuple)
            self.handles[index] = (start[0] + dx, start[1] + dy)
        elif pic is not None and kind == "move":
            assert isinstance(start, tuple)
            pic.origin = (start[0] + dx, start[1] + dy)
        elif pic is not None:
            self._resize(pic, index, snap.xy, start)
        return snap

    def _resize(self, pic: Picture, corner: int, at: Vec, start: object) -> None:
        """Drag a corner; the opposite corner stays put."""
        assert isinstance(start, tuple)
        origin, w0, h0 = start
        keep = Picture("k", "", origin, pic.angle, w0, h0).corners()[(corner + 2) % 4]
        probe = Picture("k", "", keep, pic.angle, 1.0, 1.0)
        u, v = probe.local(at)
        sx = 1.0 if corner in (1, 2) else -1.0
        sy = 1.0 if corner in (2, 3) else -1.0
        w, h = max(u * sx, 1e-3), max(v * sy, 1e-3)
        if pic.lock_aspect:
            k = max(w / w0, h / h0)
            w, h = w0 * k, h0 * k
        c, s = math.cos(pic.angle), math.sin(pic.angle)
        # The new lower left corner, from the kept corner.
        lu = 0.0 if sx > 0 else -w
        lv = 0.0 if sy > 0 else -h
        pic.origin = (keep[0] + lu * c - lv * s, keep[1] + lu * s + lv * c)
        pic.width, pic.height = w, h

    def release(self, snap: Snap, moved: bool) -> bool:
        """The end of a drag: one undo step when something moved."""
        drag, self.drag = self.drag, None
        if drag is None:
            return False
        if drag[0] == "handle":
            return False
        if not moved:
            self.edit.discard_checkpoint()
            return False
        return True

    def cancel_trace(self) -> bool:
        """Escape while tracing drops the trace. True when there was one."""
        if self.trace_mode is None:
            return False
        self.trace_mode, self.trace_corner = None, None
        return True

    def cancel(self) -> bool:
        """Escape ends a drag first, then the tool."""
        if self.drag is not None:
            if self.drag[0] != "handle":
                self.edit.discard_checkpoint()
            self.drag = None
            return False
        return not self.cancel_trace()

    def take_message(self) -> str:
        """The status note, cleared once read."""
        msg, self.message = self.message, ""
        return msg

    def preview(self) -> Preview:
        """The edited picture's outline and corners, and the scale line."""
        out = Preview()
        pic = self.picture
        if pic is not None:
            c = pic.corners()
            out.lines += [(c[i], c[(i + 1) % 4]) for i in range(4)]
            out.points += c
        if len(self.handles) == 2:
            out.lines.append((self.handles[0], self.handles[1]))
            out.points += self.handles
        return out
