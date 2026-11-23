"""Values typed in the sketch canvas (TOOL_SPEC T15.5 to T15.7, DECISIONS D442 to D444).

Two kinds of value:

- Tool options (T15.5): a tool whose panel has a length, angle or count shows
  each of them as a label beside its first pick (or the cursor) once there is
  something to preview. Clicking a label, or typing a digit, minus, dot or
  ``=``, opens the value box there. Enter applies the value to the tool, the
  same way the panel field does, and the tool keeps going. Tab and Shift+Tab
  move to the next and previous label; Escape puts back what the box changed.
- Sizes while drawing (T15.6): with no tool labels, typing a number while a
  line, rectangle, circle, arc or slot is being drawn opens the box for its
  length, size or radius at the cursor. Enter locks it (``typed_size``); the
  next click, or Enter again, finishes the shape with its dimension.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen

from fdcad.core.document.model import Param
from fdcad.core.units import ExpressionError, Kind, UnitSystem, evaluate
from fdcad.ui import strings
from fdcad.ui.sketch_tools import tool_text
from fdcad.ui.sketch_tools.tool_options import Option
from fdcad.ui.sketch_tools.typed_size import RECTANGLES, next_target, size_target
from fdcad.ui.sketch_tools.value_box import ValueBox
from fdcad.ui.themes.typography import Role, type_font

if TYPE_CHECKING:
    from fdcad.ui.sketch_tools.canvas import SketchCanvas

#: Option kinds that get a label: lengths, angles and counts.
NUMBER_KINDS = ("length", "angle", "int", "number")
#: Gap between the anchor and the first label, in pixels.
LABEL_OFFSET = QPointF(14.0, 14.0)


def value_options(tool: Any) -> list[Option]:
    """The tool's length, angle and count options, in panel order."""
    options: tuple[Option, ...] = getattr(tool, "options", ()) or ()
    return [o for o in options if o.kind in NUMBER_KINDS and o.in_sketch and hasattr(tool, o.key)]


def option_kind(opt: Option) -> Kind:
    """The expression kind of an option."""
    if opt.kind == "angle":
        return Kind.ANGLE
    if opt.kind in ("int", "number"):
        return Kind.NUMBER
    return Kind.LENGTH


def option_display(opt: Option, value: float, units: UnitSystem) -> str:
    """The value as the label shows it."""
    if opt.kind == "number":
        return f"{value:.6g}"
    if opt.kind == "int":
        return f"{int(value)}"
    if opt.kind == "angle":
        return f"{math.degrees(value):.2f}°"
    shown = value / 25.4 if units is UnitSystem.IN else value
    return f"{shown:.{3 if units is UnitSystem.IN else 2}f} {units.value}"


def option_text(opt: Option, value: float, units: UnitSystem) -> str:
    """The value as it is put in the box to edit (the same text the panel field shows)."""
    if opt.kind == "number":
        return f"{value:.6g}"
    if opt.kind == "int":
        return f"{int(value)}"
    if opt.kind == "angle":
        return f"{math.degrees(value):.6g}deg"
    if units is UnitSystem.IN:
        return f"{value / 25.4:.6g}in"
    return f"{value:.6g}mm"


def parse_option(
    opt: Option,
    text: str,
    units: UnitSystem,
    variables: dict[str, tuple[Kind, float]] | None = None,
) -> tuple[float | int | None, str]:
    """The typed value of ``opt`` (mm, radians or a whole count), or None and what is wrong."""
    try:
        value = evaluate(text, option_kind(opt), units, variables)
    except ExpressionError as exc:
        return None, str(exc)
    if opt.kind == "int":
        if abs(value - round(value)) > 1e-9:
            return None, tool_text.WHOLE_NUMBER
        count = round(value)
        if not opt.low <= count <= opt.high:
            return None, tool_text.COUNT_RANGE.format(low=opt.low, high=opt.high)
        return count, ""
    return value, ""


def has_preview(tool: Any) -> bool:
    """True once the tool has something to preview: a pick, a first click or a hot curve."""
    if tool is None:
        return False
    if tool.busy or getattr(tool, "picks", None) or tool.clicks:
        return True
    shown = tool.preview()
    return bool(shown.lines or shown.circles or shown.arcs)


def first_pick(tool: Any) -> str | None:
    """The entity the tool's labels sit beside: its first pick, else the curve under the cursor."""
    picks = getattr(tool, "picks", None)
    if picks and isinstance(picks[0], str):
        return str(picks[0])
    first = getattr(tool, "first", None)
    if isinstance(first, tuple) and first and isinstance(first[0], str):
        return first[0]
    hot = getattr(tool, "hot", None)
    return hot if isinstance(hot, str) else None


class CanvasValues(QObject):
    """The value labels and the value box of the canvas's tool (one per canvas)."""

    def __init__(self, canvas: SketchCanvas) -> None:
        super().__init__(canvas)
        self.canvas = canvas
        self.box: ValueBox | None = None
        #: The option key the box edits, or "size:<target>" for a typed size.
        self.key: str | None = None
        #: The option label last used, so typing opens it again (T15.4).
        self.last_key: str | None = None
        self._before: dict[str, object] = {}
        self._tool: object | None = None
        #: The box was opened by itself (on screen value input, T11.6, D513).
        self.auto = False

    # Labels -----------------------------------------------------------------------------

    def anchor(self) -> QPointF | None:
        """Where the labels start, in widget pixels: the first pick, click or cursor."""
        canvas, tool = self.canvas, self.canvas.tool
        if tool is None:
            return None
        sk = canvas.edit.sketch
        first = first_pick(tool)
        if first is not None and first in sk.entities:
            from fdcad.ui.sketch_tools.canvas import _anchor_of

            return canvas.to_screen(_anchor_of(sk, sk.entities[first]))
        if tool.clicks:
            return canvas.to_screen(tool.clicks[0].xy)
        if tool.cursor is not None:
            return canvas.to_screen(tool.cursor.xy)
        return None

    def labels(self) -> list[tuple[str, QRectF, str]]:
        """The labels to show: (option key, screen box, text). Empty with nothing to preview."""
        canvas, tool = self.canvas, self.canvas.tool
        options = value_options(tool)
        if not options or not has_preview(tool):
            return []
        at = self.anchor()
        if at is None:
            return []
        metrics = QFontMetrics(self.font())
        height = metrics.height() + 4
        out = []
        x, y = at.x() + LABEL_OFFSET.x(), at.y() + LABEL_OFFSET.y()
        for opt in options:
            value = getattr(tool, opt.key)
            text = f"{opt.label}: {option_display(opt, float(value), canvas.units)}"
            box = QRectF(x, y, metrics.horizontalAdvance(text) + 8, height)
            out.append((opt.key, box, text))
            y += height + 2
        return out

    def font(self) -> QFont:
        """The label font."""
        return type_font(Role.BODY, self.canvas.font())

    def label_at(self, pos: QPointF) -> str | None:
        """The option key of the label under ``pos``, or None."""
        for key, rect, _text in self.labels():
            if rect.adjusted(-2, -2, 2, 2).contains(pos):
                return key
        return None

    def paint(self, painter: QPainter, color: str) -> None:
        """Draw the labels (a light box with the value, in the selection colour)."""
        labels = self.labels()
        if not labels:
            return
        painter.setFont(self.font())
        for key, rect, text in labels:
            fill = QColor(self.canvas.palette_colors.viewport_top)
            fill.setAlpha(220)
            painter.setPen(QPen(QColor(color), 1.4 if key == self.key else 1.0))
            painter.setBrush(fill)
            painter.drawRoundedRect(rect, 3, 3)
            painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), text)

    # Opening ----------------------------------------------------------------------------

    def is_open(self) -> bool:
        """True while the box is open."""
        return self.box is not None

    def wants_typing(self) -> bool:
        """True when a typed digit would open the box (labels shown, or a size to type)."""
        return bool(self.labels()) or size_target(self.canvas.tool) is not None

    def type_key(self, text: str) -> bool:
        """A digit, minus, dot or = was typed: open the box with it. False when nothing opens."""
        labels = self.labels()
        if labels:
            keys = [key for key, _r, _t in labels]
            key = self.last_key if self.last_key in keys else keys[0]
            return self.open_option(key, text) is not None
        target = size_target(self.canvas.tool)
        if target is not None:
            return self.open_size(target, text) is not None
        return False

    def open_option(self, key: str, typed: str | None = None) -> ValueBox | None:
        """Open the box on the label of option ``key``."""
        canvas, tool = self.canvas, self.canvas.tool
        opt = next((o for o in value_options(tool) if o.key == key), None)
        if tool is None or opt is None:
            return None
        rect = next((r for k, r, _t in self.labels() if k == key), None)
        keep = dict(self._before) if self.box is not None and self._tool is tool else {}
        self.close(restore=False)
        self._before, self._tool = keep, tool
        value = getattr(tool, key)
        box = self._make(option_text(opt, float(value), canvas.units), option_kind(opt))
        at = rect.topLeft() if rect is not None else self._mouse()
        self._show(box, at, typed)
        self.key, self.last_key = key, key
        return box

    def auto_open(self) -> ValueBox | None:
        """Open the size box by itself when the preference asks for it (T11.6, D513).

        Only when the tool is ready for a size it has not locked yet and no box is
        open. The box is empty and gives way to clicks (:meth:`click_through`).
        """
        canvas, tool = self.canvas, self.canvas.tool
        if not canvas.options.value_input or tool is None or self.box is not None:
            return None
        if self.labels():
            return None  # a tool with value labels types into them instead
        target = size_target(tool)
        if target is None or target in tool.locks:
            return None
        box = self.open_size(target)
        self.auto = box is not None
        return box

    def untouched(self) -> bool:
        """True while the box opened by itself and nothing was typed in it."""
        return self.auto and self.box is not None and not self.box.text().strip()

    def click_through(self) -> None:
        """A click in the sketch while the box is open: an untouched automatic box
        closes without locking anything; a typed value is applied as before."""
        if self.untouched():
            self.close(restore=False)
        else:
            self.apply()

    def follow(self, at: QPointF) -> None:
        """Keep an untouched automatic box beside the cursor."""
        from fdcad.ui.sketch_tools.canvas import beside

        box, canvas = self.box, self.canvas
        if box is None or not self.untouched():
            return
        p = at + LABEL_OFFSET
        x, y = beside(QRectF(p, p), box.width(), box.height(), canvas.width(), canvas.height())
        box.move(x, y)

    def open_size(self, target: str, typed: str | None = None) -> ValueBox | None:
        """Open the box for a size of the shape being drawn, at the cursor (T15.6)."""
        canvas, tool = self.canvas, self.canvas.tool
        if tool is None:
            return None
        self.close(restore=False)
        self._tool = tool
        lock = tool.locks.get(target)
        box = self._make(lock.expr if lock is not None else "", Kind.LENGTH)
        box.setToolTip(tool_text.SIZE_NAMES.get(target, target))
        at = canvas.to_screen(tool.cursor.xy) if tool.cursor is not None else self._mouse()
        self._show(box, at + LABEL_OFFSET, typed)
        self.key = f"size:{target}"
        return box

    def _mouse(self) -> QPointF:
        canvas = self.canvas
        return canvas.mouse or QPointF(canvas.width() / 2, canvas.height() / 2)

    def _make(self, text: str, kind: Kind) -> ValueBox:
        canvas = self.canvas
        box = ValueBox(text, canvas, kind, canvas.units, canvas.variables)
        box.tab_moves = True
        box.accepted.connect(lambda: self.apply(close=True))
        box.applied.connect(lambda: self.apply(close=False))
        box.rejected.connect(self.cancel)
        box.tabbed.connect(self.move)
        return box

    def _show(self, box: ValueBox, at: QPointF, typed: str | None) -> None:
        from fdcad.ui.sketch_tools.canvas import beside

        canvas = self.canvas
        box.adjustSize()
        x, y = beside(QRectF(at, at), box.width(), box.height(), canvas.width(), canvas.height())
        box.open_at(x, y)
        if typed:
            box.start_typing(typed)
        self.box = box

    # Applying ---------------------------------------------------------------------------

    def apply(self, close: bool = True) -> bool:
        """Apply the box. A wrong value keeps it open and red with the message (T15.7)."""
        box, key, canvas = self.box, self.key, self.canvas
        tool = canvas.tool
        if box is None or key is None or tool is None:
            return False
        if key.startswith("size:"):
            return self._apply_size(key[len("size:") :], close)
        opt = next((o for o in value_options(tool) if o.key == key), None)
        if opt is None:
            self.close()
            return False
        value, error = parse_option(opt, box.text().strip(), canvas.units, canvas.variables)
        if value is None:
            box.show_error(error)
            canvas.status_message.emit(error)
            return False
        self._before.setdefault(key, getattr(tool, key))
        if getattr(tool, key) != value:
            canvas.set_tool_option(key, value)
        if close:
            self.close(restore=False)
            canvas.setFocus()
        return True

    def _apply_size(self, target: str, close: bool) -> bool:
        box, canvas = self.box, self.canvas
        tool = canvas.tool
        assert box is not None and tool is not None
        if self.untouched():
            # Enter in an empty automatic box (D513) just closes it.
            self.close(restore=False)
            canvas.setFocus()
            return False
        text = box.text().strip()
        try:
            value = evaluate(text, Kind.LENGTH, canvas.units, canvas.variables)
        except ExpressionError as exc:
            box.show_error(str(exc))
            canvas.status_message.emit(str(exc))
            return False
        if value <= 0:
            box.show_error(strings.DIMENSION_POSITIVE)
            canvas.status_message.emit(strings.DIMENSION_POSITIVE)
            return False
        tool.locks[target] = Param(text, value)
        if tool.cursor is not None:
            canvas.snap = tool.track(tool.cursor)
        name = tool_text.SIZE_NAMES.get(target, target)
        canvas.status_message.emit(tool_text.SIZE_LOCKED.format(name=name, value=text))
        canvas.update()
        if close:
            self.close(restore=False)
            following = next_target(tool)
            if following is not None:
                self.open_size(following)  # a rectangle asks for its height next
            else:
                canvas.setFocus()
        return True

    def move(self, step: int) -> ValueBox | None:
        """Apply, then open the next (``step`` 1) or previous (-1) label (T15.3)."""
        key = self.key
        if key is None or not self.apply(close=False):
            return self.box
        tool = self.canvas.tool
        if key.startswith("size:"):
            current = key[len("size:") :]
            if tool is not None and tool.name in RECTANGLES and current in ("width", "height"):
                return self.open_size("height" if current == "width" else "width")
            return self.box
        keys = [k for k, _r, _t in self.labels()]
        if key not in keys or len(keys) < 2:
            return self.box
        return self.open_option(keys[(keys.index(key) + step) % len(keys)])

    def finish(self) -> bool:
        """Enter with no box: finish a shape whose size was typed. False when there is none."""
        canvas, tool = self.canvas, self.canvas.tool
        if self.box is not None or tool is None or not tool.locks or tool.cursor is None:
            return False
        if tool.click(tool.track(tool.cursor)):
            canvas.changed()
        canvas.snap = tool.cursor
        self.auto_open()
        canvas.update()
        return True

    def cancel(self) -> None:
        """Escape or the cross: close and put back what the box changed (T15.9)."""
        self.close(restore=True)
        self.canvas.setFocus()

    def close(self, restore: bool = False) -> None:
        """Close the box. With ``restore`` the tool options it changed go back."""
        before, self._before = self._before, {}
        tool = self.canvas.tool
        if restore and tool is not None and tool is self._tool:
            for key, value in before.items():
                if getattr(tool, key, None) != value:
                    self.canvas.set_tool_option(key, value)
        if self.box is not None:
            self.box.hide()
            self.box.deleteLater()
        self.box, self.key = None, None
        self.auto = False
        self.canvas.update()

    def tool_changed(self) -> None:
        """A new tool: close the box and forget the last label."""
        self.close(restore=False)
        self.last_key = None
