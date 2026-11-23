"""The view selector: a see through cube at the centre of the view (TOOL_SPEC T12.4,
T14.4.2, WORKFLOW_SPEC W7.2).

The cube is drawn looking from the front, right and top corner. Each visible
face is split into a 3 by 3 grid: the middle picks the face's view, the sides
pick the view across that edge and the corners pick the corner view. The three
faces at the back are drawn small, pushed out past the cube's outline, so they
can be clicked without turning the view; holding Alt makes the whole cube pick
the back instead (the opposite of each cell). Hovering shows a small preview of
that view with its name in a corner. Clicking turns the 3D view to look from
that direction. An original design: plain shaded faces, no text on the cube.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPen, QPolygonF
from PySide6.QtWidgets import QFrame, QHBoxLayout, QToolButton, QVBoxLayout, QWidget

from fdcad.ui import strings
from fdcad.ui.viewport.views import STANDARD_VIEWS, Vec3, view_for_normal, view_name

#: Screen vectors of the model X, Y and Z axes in the cube drawing (y down).
_R = (1 / math.sqrt(2), 0.0, -1 / math.sqrt(2))
_U = (-1 / math.sqrt(6), 2 / math.sqrt(6), -1 / math.sqrt(6))
#: The visible faces: (fixed axis index, the two free axis indices).
_FACES = ((2, 0, 1), (0, 1, 2), (1, 0, 2))  # front (+Z), right (+X), top (+Y)
_CUBE_PX = 46.0  # half the edge length on screen
_HIDDEN = ("back", "left", "bottom")
#: Extra buttons for the views between the faces (TR14).
_BETWEEN = ("dimetric", "trimetric")
#: How far out the small back faces sit, as a multiple of a face centre's distance.
BACK_PUSH = 2.25
#: Half size of a small back face, in cube units.
BACK_SIZE = 0.32
#: The widget is this many cube half edges across.
_SPAN = 2 * 2.4


def project(p: Vec3) -> tuple[float, float]:
    """A cube point (each coordinate -1 to 1) to drawing units, y down."""
    sx = p[0] * _R[0] + p[1] * _R[1] + p[2] * _R[2]
    sy = -(p[0] * _U[0] + p[1] * _U[1] + p[2] * _U[2])
    return sx, sy


def _cell(t: float) -> int:
    return -1 if t < -1 / 3 else (1 if t > 1 / 3 else 0)


def direction_at(sx: float, sy: float) -> Vec3 | None:
    """The view direction picked at a drawing point, or None outside the cube."""
    for fixed, a, b in _FACES:
        base = [0.0, 0.0, 0.0]
        base[fixed] = 1.0
        ea = [0.0, 0.0, 0.0]
        ea[a] = 1.0
        eb = [0.0, 0.0, 0.0]
        eb[b] = 1.0
        c = project((base[0], base[1], base[2]))
        pa = project((ea[0], ea[1], ea[2]))
        pb = project((eb[0], eb[1], eb[2]))
        det = pa[0] * pb[1] - pa[1] * pb[0]
        x, y = sx - c[0], sy - c[1]
        u = (x * pb[1] - y * pb[0]) / det
        v = (pa[0] * y - pa[1] * x) / det
        if abs(u) <= 1 and abs(v) <= 1:
            out = [0.0, 0.0, 0.0]
            out[fixed] = 1.0
            out[a] = float(_cell(u))
            out[b] = float(_cell(v))
            return out[0], out[1], out[2]
    return None


def back_face_at(sx: float, sy: float) -> Vec3 | None:
    """The back face (-X, -Y or -Z) whose small pushed out copy is at a drawing point."""
    for axis in range(3):
        centre = back_face_centre(axis)
        if abs(sx - centre[0]) <= BACK_SIZE and abs(sy - centre[1]) <= BACK_SIZE:
            out = [0.0, 0.0, 0.0]
            out[axis] = -1.0
            return out[0], out[1], out[2]
    return None


def back_face_centre(axis: int) -> tuple[float, float]:
    """Drawing point of the pushed out copy of the back face across ``axis``."""
    e = [0.0, 0.0, 0.0]
    e[axis] = -1.0
    sx, sy = project((e[0], e[1], e[2]))
    return sx * BACK_PUSH, sy * BACK_PUSH


def pick_at(sx: float, sy: float, back: bool = False) -> Vec3 | None:
    """The direction picked at a drawing point: a back face copy, else the cube cell
    (its opposite while Alt is held)."""
    found = back_face_at(sx, sy)
    if found is not None:
        return found
    d = direction_at(sx, sy)
    if d is not None and back:
        return (-d[0] + 0.0, -d[1] + 0.0, -d[2] + 0.0)
    return d


def preview_points(eye: Vec3, up: Vec3) -> list[tuple[float, float, float]]:
    """The cube's eight corners seen from ``eye`` with ``up``: screen x, y (y down) and depth.

    Corners are in the order (-1,-1,-1), (-1,-1,1), ... (1,1,1), x slowest.
    """
    ex, ey, ez = eye
    n = math.sqrt(ex * ex + ey * ey + ez * ez) or 1.0
    f = (ex / n, ey / n, ez / n)
    ux, uy, uz = up
    along = ux * f[0] + uy * f[1] + uz * f[2]
    u = (ux - along * f[0], uy - along * f[1], uz - along * f[2])
    m = math.sqrt(u[0] ** 2 + u[1] ** 2 + u[2] ** 2) or 1.0
    u = (u[0] / m, u[1] / m, u[2] / m)
    r = (u[1] * f[2] - u[2] * f[1], u[2] * f[0] - u[0] * f[2], u[0] * f[1] - u[1] * f[0])
    out = []
    for x in (-1.0, 1.0):
        for y in (-1.0, 1.0):
            for z in (-1.0, 1.0):
                sx = x * r[0] + y * r[1] + z * r[2]
                sy = -(x * u[0] + y * u[1] + z * u[2])
                depth = x * f[0] + y * f[1] + z * f[2]
                out.append((sx, sy, depth))
    return out


def view_of(direction: Vec3) -> tuple[Vec3, Vec3]:
    """Eye direction and up vector for a picked direction (Y up, D67)."""
    for eye, up in STANDARD_VIEWS.values():
        if eye == direction:
            return eye, up
    n = math.sqrt(sum(c * c for c in direction))
    return view_for_normal((direction[0] / n, direction[1] / n, direction[2] / n))


class _Cube(QWidget):
    """The cube drawing; hovering marks the cell under the cursor."""

    picked = Signal(tuple)
    hovered = Signal(object)  # a direction, or None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("view_selector_cube")
        self.setMouseTracking(True)
        size = int(_CUBE_PX * _SPAN)
        self.setFixedSize(size, size)
        self.hover: Vec3 | None = None
        #: Alt is held: the cells pick the faces at the back.
        self.back = False

    def to_cube(self, pos: QPointF) -> tuple[float, float]:
        """Widget pixels to drawing units."""
        return (pos.x() - self.width() / 2) / _CUBE_PX, (pos.y() - self.height() / 2) / _CUBE_PX

    def to_widget(self, p: Vec3) -> QPointF:
        """A cube point to widget pixels."""
        sx, sy = project(p)
        return QPointF(self.width() / 2 + sx * _CUBE_PX, self.height() / 2 + sy * _CUBE_PX)

    def back_face_point(self, axis: int) -> QPointF:
        """Widget pixels of the small back face across ``axis`` (tests click it)."""
        sx, sy = back_face_centre(axis)
        return QPointF(self.width() / 2 + sx * _CUBE_PX, self.height() / 2 + sy * _CUBE_PX)

    def _at(self, event: QMouseEvent) -> Vec3 | None:
        self.back = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
        return pick_at(*self.to_cube(event.position()), back=self.back)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Mark the cell under the cursor and preview its view."""
        back = self.back
        hover = self._at(event)
        if hover != self.hover or back != self.back:
            self.hover = hover
            self.hovered.emit(hover)
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Pick the cell under the cursor."""
        direction = self._at(event)
        if event.button() == Qt.MouseButton.LeftButton and direction is not None:
            self.picked.emit(direction)

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802
        """No preview once the cursor leaves the cube."""
        self.hover = None
        self.hovered.emit(None)
        self.update()
        super().leaveEvent(event)

    def _cell_polygon(self, fixed: int, a: int, b: int, i: int, j: int) -> QPolygonF:
        edges = (-1.0, -1 / 3, 1 / 3, 1.0)
        u0, u1 = edges[i + 1], edges[i + 2]
        v0, v1 = edges[j + 1], edges[j + 2]
        pts = []
        for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1)):
            p = [0.0, 0.0, 0.0]
            p[fixed], p[a], p[b] = 1.0, u, v
            pts.append(self.to_widget((p[0], p[1], p[2])))
        return QPolygonF(pts)

    def _back_polygon(self, axis: int) -> QPolygonF:
        c = self.back_face_point(axis)
        k = BACK_SIZE * _CUBE_PX
        return QPolygonF(
            [c + QPointF(-k, -k), c + QPointF(k, -k), c + QPointF(k, k), c + QPointF(-k, k)]
        )

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Draw three shaded faces with their 3 by 3 cells and the three small back faces."""
        from fdcad.ui.themes.theme import chrome

        colors = chrome()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        shades = (105, 120, 90)  # front, right, top: lighter or darker than the panel
        sign = -1.0 if self.back else 1.0
        for (fixed, a, b), shade in zip(_FACES, shades, strict=True):
            for i in (-1, 0, 1):
                for j in (-1, 0, 1):
                    d = [0.0, 0.0, 0.0]
                    d[fixed], d[a], d[b] = sign, sign * i, sign * j
                    on = self.hover == (d[0] + 0.0, d[1] + 0.0, d[2] + 0.0)
                    base = QColor(colors.raised).darker(shade + (25 if self.back else 0))
                    painter.setBrush(QColor(colors.accent) if on else base)
                    painter.setPen(QPen(QColor(colors.border_strong), 1))
                    painter.drawPolygon(self._cell_polygon(fixed, a, b, i, j))
        for axis in range(3):
            d = [0.0, 0.0, 0.0]
            d[axis] = -1.0
            on = self.hover == (d[0], d[1], d[2])
            painter.setBrush(QColor(colors.accent) if on else QColor(colors.raised).darker(130))
            painter.setPen(QPen(QColor(colors.border_strong), 1, Qt.PenStyle.DashLine))
            painter.drawPolygon(self._back_polygon(axis))
        painter.end()


class _Preview(QWidget):
    """A small picture of the hovered view: the cube from there, with the view's name."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("view_selector_preview")
        self.setFixedSize(int(_CUBE_PX * 2.4), int(_CUBE_PX * 2.4))
        self.direction: Vec3 | None = None
        self.name = ""

    def show_view(self, direction: Vec3 | None) -> None:
        """Preview a direction, or show nothing."""
        self.direction = direction
        self.name = view_name(direction) if direction is not None else ""
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """The cube seen from the hovered direction, faces toward the eye filled."""
        from fdcad.ui.themes.theme import chrome

        colors = chrome()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(colors.border_strong), 1))
        painter.setBrush(QColor(colors.raised))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        if self.direction is not None:
            eye, up = view_of(self.direction)
            pts = preview_points(eye, up)
            k = self.width() / 4.2
            cx, cy = self.width() / 2, self.height() / 2 + 6

            def at(i: int) -> QPointF:
                return QPointF(cx + pts[i][0] * k, cy + pts[i][1] * k)

            faces = (
                (0, 1, 3, 2, (-1, 0, 0)),
                (4, 5, 7, 6, (1, 0, 0)),
                (0, 1, 5, 4, (0, -1, 0)),
                (2, 3, 7, 6, (0, 1, 0)),
                (0, 2, 6, 4, (0, 0, -1)),
                (1, 3, 7, 5, (0, 0, 1)),
            )
            n = math.sqrt(sum(c * c for c in eye)) or 1.0
            for i0, i1, i2, i3, normal in faces:
                facing = sum(normal[c] * eye[c] for c in range(3)) / n
                if facing <= 1e-6:
                    continue
                fill = QColor(colors.accent)
                fill.setAlphaF(0.25 + 0.6 * facing)
                painter.setBrush(fill)
                painter.drawPolygon(QPolygonF([at(i0), at(i1), at(i2), at(i3)]))
            painter.setPen(QColor(colors.text))
            painter.drawText(self.rect().adjusted(4, 2, -4, -2), self.name)
        painter.end()


class ViewSelector(QFrame):
    """Popup with the cube and buttons for the hidden faces. ``chosen`` gives eye and up."""

    chosen = Signal(tuple, tuple)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("view_selector")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.cube = _Cube(self)
        self.cube.picked.connect(self._pick)
        self.preview = _Preview(self)
        self.cube.hovered.connect(self.preview.show_view)
        self.setWindowOpacity(0.9)  # see through (T14.4.2)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        top = QHBoxLayout()
        top.addWidget(self.cube, 0, Qt.AlignmentFlag.AlignHCenter)
        top.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(top)
        row = QHBoxLayout()
        self.buttons: dict[str, QToolButton] = {}
        for name in (*_HIDDEN, *_BETWEEN):
            button = QToolButton()
            button.setObjectName(f"view_selector_{name}")
            button.setText(strings.VIEW_SELECTOR_FACES[name])
            button.setAutoRaise(True)
            button.clicked.connect(lambda _c=False, n=name: self._pick(STANDARD_VIEWS[n][0]))
            row.addWidget(button)
            self.buttons[name] = button
        layout.addLayout(row)
        self.setToolTip(strings.VIEW_SELECTOR_TIP)

    def _pick(self, direction: tuple[float, float, float]) -> None:
        eye, up = view_of(direction)
        self.chosen.emit(eye, up)
        self.close()

    def open_at(self, pos: QPoint) -> None:
        """Show centred on a screen point."""
        self.adjustSize()
        self.move(pos - QPoint(self.width() // 2, self.height() // 2))
        self.show()
