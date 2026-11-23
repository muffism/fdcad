"""Type icons for feature tree rows, with a small state mark (PHASE1_CORRECTIONS L4).

Every row shows what it is (part, folder, plane, origin, sketch, feature).
A feature with a warning or an error gets a small mark at the bottom right of
its icon: a triangle for a warning, a disc for an error, both with an upright bar, so
the state never shows by colour alone (U4.4, D666). A suppressed or rolled back
feature shows a faded icon.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from fdcad.core.document.model import Feature
from fdcad.ui import icons
from fdcad.ui.strings_phase3 import TYPE_COMMANDS as PHASE3_ICONS
from fdcad.ui.strings_sheetmetal import TYPE_COMMANDS as SHEET_ICONS

ROW_ICON_SIZE = 18

#: Icon for each feature type. Extrude and revolve depend on boss or cut.
TYPE_ICONS = {
    "origin": "tree.origin",
    "plane": "tree.plane",
    "sketch": "tree.sketch",
    "import_step": "feature.import_step",
    "helix": "feature.helix",
    "projected_curve": "feature.projected_curve",
    "composite_curve": "feature.composite_curve",
    "pipe": "feature.pipe",
    "curve_array": "feature.curve_array",
    "contour": "feature.contour",
    "import_mesh": "feature.import_mesh",
    "split_for_print": "feature.split_for_print",
    "ref_plane": "feature.ref_plane",
    "ref_axis": "feature.ref_axis",
    "ref_point": "feature.ref_point",
    "coord_system": "feature.coord_system",
    "graph_body": "tree.graph_body",
    "point_curve": "feature.point_curve",  # TR61
    "sketch3d": "feature.sketch3d",  # TR7
    "measurement": "evaluate.measure",  # TR190
}
OPERATION_ICONS = {
    ("extrude", "boss"): "feature.extrude",
    ("extrude", "cut"): "feature.extruded_cut",
    ("revolve", "boss"): "feature.revolve",
    ("revolve", "cut"): "feature.revolved_cut",
    ("sweep", "boss"): "feature.sweep",
    ("sweep", "cut"): "feature.swept_cut",
    ("loft", "boss"): "feature.loft",
    ("loft", "cut"): "feature.lofted_cut",
    ("fillet", "boss"): "feature.fillet",
    ("chamfer", "boss"): "feature.chamfer",
    ("shell", "boss"): "feature.shell",
    ("draft", "boss"): "feature.draft",
}


TYPE_ICONS.update(PHASE3_ICONS)  # Phase 3 types show their command icon
TYPE_ICONS.update(SHEET_ICONS)  # and so do the sheet metal types
TYPE_ICONS["follow_pattern"] = "feature.pattern_chain"  # TR399 (D1904): no command of its own
# Phase 4 deformation features (PHASE4_SPEC P4.9) show their command icon too.
TYPE_ICONS.update({t: f"feature.{t}" for t in ("bend", "twist", "taper", "stretch", "flow")})
TYPE_ICONS.update(  # TR67 (D2412): the local deform modes
    {t: f"feature.{t}" for t in ("deform_point", "deform_curve", "surface_push")}
)


def icon_name(feature: Feature) -> str:
    """The icon name for a feature row."""
    if feature.type in TYPE_ICONS:
        return TYPE_ICONS[feature.type]
    operation = str(feature.params.get("operation", "boss"))
    return OPERATION_ICONS.get((feature.type, operation), "tree.body")


def row_icon(
    name: str,
    state_color: str | None = None,
    faded: bool = False,
    small: bool = False,
    mark: str = "error",
    commented: bool = False,
) -> QIcon:
    """The named icon, with a state mark in ``state_color`` (a smaller one with
    ``small``) and faded when asked. ``mark`` is "warning" (a triangle) or "error".
    ``commented`` adds a small accent dot at the top right (a feature comment, TR23)."""
    base = icons.icon(name)
    if state_color is None and not faded and not commented:
        return base
    result = QIcon()
    for scale in (1, 2):
        size = ROW_ICON_SIZE * scale
        pixmap = QPixmap(QSize(size, size))
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if faded:
            painter.setOpacity(0.4)
        painter.drawPixmap(0, 0, base.pixmap(QSize(size, size)))
        painter.setOpacity(1.0)
        if state_color is not None:
            _paint_mark(painter, size, state_color, small, mark)
        if commented:
            _paint_comment(painter, size)
        painter.end()
        pixmap.setDevicePixelRatio(scale)
        result.addPixmap(pixmap)
    return result


def _paint_comment(painter: QPainter, size: int) -> None:
    """A small accent dot at the top right: the feature has a comment (TR23)."""
    from fdcad.ui.themes.theme import chrome, palette

    r = size * 0.15
    painter.setPen(QPen(QColor(chrome().surface), max(1.0, size / 18)))
    painter.setBrush(QBrush(QColor(palette().accent)))
    painter.drawEllipse(QRectF(size - 2 * r, 0.0, 2 * r, 2 * r))


def _paint_mark(painter: QPainter, size: int, color: str, small: bool, mark: str) -> None:
    """A warning triangle or an error disc with a bar, at the bottom right."""
    r = size * (0.16 if small else 0.25)
    box = QRectF(size - 2 * r, size - 2 * r, 2 * r, 2 * r)
    # A thin ring in the window colour keeps the mark apart from the icon lines.
    from fdcad.ui.themes.theme import chrome

    halo = QPen(QColor(chrome().surface), max(1.0, size / 18))
    painter.setPen(halo)
    painter.setBrush(QBrush(QColor(color)))
    if mark == "warning":
        path = QPainterPath(QPointF(box.center().x(), box.top()))
        path.lineTo(box.right(), box.bottom())
        path.lineTo(box.left(), box.bottom())
        path.closeSubpath()
        painter.drawPath(path)
    else:
        painter.drawEllipse(box)
    if small:
        return
    # An upright bar, like the warning and error icons, in the surface colour.
    bar = QPen(QColor(chrome().surface), max(1.0, size / 12))
    bar.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(bar)
    cx = box.center().x()
    top = box.top() + r * (0.8 if mark == "warning" else 0.55)
    painter.drawLine(QPointF(cx, top), QPointF(cx, box.bottom() - r * 0.55))
