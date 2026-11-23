"""How reference planes look in the 3D view (TOOL_SPEC T13, D121).

Shown planes (D114) and planes offered for picking (W1) share one look: a thin
outline, a light smoke grey fill that is mostly see through, and the plane's
tree name as small text just inside one corner, in the outline colour. The
plane under the cursor while picking uses the accent colour; a selected plane
uses the selection colour. The fill never changes. No Qt, and OCP only in
``label_anchor``, so the rules are tested without a GPU.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from fdcad.ui.themes.theme import Palette

#: How see through the fill is (0 opaque, 1 invisible); T13 asks for 85 to 90 percent.
FILL_TRANSPARENCY = 0.88
#: Outline width in pixels.
OUTLINE_WIDTH = 1.0
#: Label text height in pixels.
LABEL_HEIGHT = 12.0
#: The label sits this share of the plane's size inside its corner.
LABEL_INSET = 0.04
#: Labels of parallel planes step down their corner by this share of the plane's size, one
#: row per plane, so they do not sit on top of each other (D2630).
LABEL_STEP = 0.035
#: After this many rows the labels start again at the corner.
LABEL_ROWS = 20


class PlaneState(Enum):
    """What the user is doing with a plane."""

    NORMAL = "normal"
    HOVER = "hover"
    SELECTED = "selected"


@dataclass(frozen=True)
class PlaneStyle:
    """Colours (hex strings) of one plane in one state."""

    outline: str
    fill: str
    label: str
    transparency: float = FILL_TRANSPARENCY


def plane_style(palette: Palette, state: PlaneState) -> PlaneStyle:
    """The look of a plane. The label always has the outline colour; the fill stays light."""
    outline = {
        PlaneState.NORMAL: palette.plane_outline,
        PlaneState.HOVER: palette.accent,
        PlaneState.SELECTED: palette.selection,
    }[state]
    return PlaneStyle(outline=outline, fill=palette.plane_fill, label=outline)


def plane_state(fid: str, hover: str | None, selected: set[str]) -> PlaneState:
    """Selection wins over hover."""
    if fid in selected:
        return PlaneState.SELECTED
    if fid == hover:
        return PlaneState.HOVER
    return PlaneState.NORMAL


def label_corner(
    umin: float, umax: float, vmin: float, vmax: float, row: int = 0
) -> tuple[float, float]:
    """Plane coordinates of the label: just inside the corner of low u and high v, ``row``
    steps further down for the labels of parallel planes (D2630)."""
    du, dv = umax - umin, vmax - vmin
    step = LABEL_INSET + LABEL_STEP * (row % LABEL_ROWS)
    return umin + LABEL_INSET * du, vmax - step * dv


def label_anchor(face: object, row: int = 0) -> tuple[float, float, float]:
    """Model point of a plane face's label (tiny kernel work, like ``plane_faces``, D75)."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface

    surface = BRepAdaptor_Surface(face)
    u, v = label_corner(
        surface.FirstUParameter(),
        surface.LastUParameter(),
        surface.FirstVParameter(),
        surface.LastVParameter(),
        row,
    )
    p = surface.Value(u, v)
    return p.X(), p.Y(), p.Z()


def label_rows(faces: dict[str, object]) -> dict[str, int]:
    """The label row of each plane face (D2630).

    Every plane is drawn the same size round its own origin, so planes with the same
    axes put their labels at the same corner, apart only along the normal: on the bike
    frame, with 17 construction planes, the labels sat on top of each other. Planes with
    the same axes get rows in the order they lie along the normal; any other plane keeps
    row 0. The labels themselves are drawn at a fixed height in pixels.
    """
    from OCP.BRepAdaptor import BRepAdaptor_Surface

    groups: dict[tuple[float, ...], list[tuple[float, str]]] = {}
    for fid, face in faces.items():
        position = BRepAdaptor_Surface(face).Plane().Position()
        n, x, o = position.Direction(), position.XDirection(), position.Location()
        key = tuple(round(c, 6) + 0.0 for c in (n.X(), n.Y(), n.Z(), x.X(), x.Y(), x.Z()))
        groups.setdefault(key, []).append((o.X() * n.X() + o.Y() * n.Y() + o.Z() * n.Z(), fid))
    rows: dict[str, int] = {}
    for members in groups.values():
        for row, (_offset, fid) in enumerate(sorted(members)):
            rows[fid] = row
    return rows
