"""View commands of TOOL_SPEC T14.4: Normal To rules, Zoom to Selection, show or hide toggles.

Normal To works on a plane, a flat face, a cylindrical or conical face (looking
along its axis) or a feature made from one sketch (looking at that sketch).
Running it again on the same item turns the view 180 degrees. Two flat faces
that are not parallel put the first toward the screen and the second at the
top. With nothing selected the view snaps to the nearest standard direction.
In a sketch the editor always looks straight at the sketch (D72).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fdcad.ui import strings
from fdcad.ui import strings_extra as text
from fdcad.ui.viewport.views import (
    Vec3,
    axis_view,
    flipped,
    nearest_standard,
    same_direction,
    two_face_view,
    view_for_normal,
)

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab, MainWindow

Target = tuple[str, Vec3, Vec3]  # what was looked at, eye direction, up


def _faces(tab: DocumentTab) -> list[tuple[str, Vec3, bool]]:
    """Selected faces as (key, direction, is_round): flat normals or round axes."""
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopoDS import TopoDS

    from fdcad.core.features.sketch import face_plane
    from fdcad.ui.main_window.context_menu import face_axis

    out: list[tuple[str, Vec3, bool]] = []
    for shape in tab.selection:
        if shape.ShapeType() != TopAbs_FACE:
            continue
        plane = face_plane(TopoDS.Face(shape))
        if plane is not None:
            n, o = plane.normal, plane.origin
            key = f"face {n[0]:.4f} {n[1]:.4f} {n[2]:.4f} {o[0]:.3f} {o[1]:.3f} {o[2]:.3f}"
            out.append((key, n, False))
            continue
        axis = face_axis(shape)
        if axis is not None:
            p, d = axis
            key = f"axis {d[0]:.4f} {d[1]:.4f} {d[2]:.4f} {p[0]:.3f} {p[1]:.3f} {p[2]:.3f}"
            out.append((key, d, True))
    return out


def _tree_normal(window: MainWindow, tab: DocumentTab) -> tuple[str, Vec3] | None:
    """The plane, sketch or sketch based feature selected in the tree, as key and normal."""
    from fdcad.ui.main_window.sketch_mode import plane_of_feature
    from fdcad.ui.main_window.visibility import sketch_of

    fid = window.tree.selected_id() if window.tree is not None else None
    if fid is None:
        return None
    doc = tab.session.document
    feature = doc.feature(fid)
    if feature.type not in ("plane", "sketch"):
        sid = sketch_of(feature)
        if sid is None or not any(f.id == sid for f in doc.features):
            return None
        feature = doc.feature(sid)
    plane = plane_of_feature(tab, feature) if feature.type != "plane" else _plane(tab, fid)
    return (f"feature {fid}", plane.normal) if plane is not None else None


def _plane(tab: DocumentTab, fid: str) -> Any:
    """Placement of a plane feature: from the last rebuild, else its default basis."""
    from fdcad.core.sketch.profiles import BASIS_PLANES

    report = tab.session.report
    result = report.results.get(fid) if report is not None else None
    if result is not None and result.plane is not None:
        return result.plane
    basis = tab.session.document.feature(fid).params.get("basis")
    return BASIS_PLANES.get(basis) if isinstance(basis, str) else None


def target(window: MainWindow, tab: DocumentTab, eye: Vec3, up: Vec3) -> Target | None:
    """Where Normal To looks for the current selection, or None with nothing usable."""
    faces = _faces(tab)
    flat = [f for f in faces if not f[2]]
    if len(flat) >= 2:
        view = two_face_view(flat[0][1], flat[1][1])
        if view is not None:
            return (f"{flat[0][0]} | {flat[1][0]}", view[0], view[1])
    if faces:
        key, direction, is_round = faces[0]
        if is_round:
            e, u = axis_view(direction, eye, up)
        else:
            e, u = view_for_normal(direction, up)
        return (key, e, u)
    tree = _tree_normal(window, tab)
    if tree is not None:
        e, u = view_for_normal(tree[1], up)
        return (tree[0], e, u)
    return None


def normal_to(window: MainWindow) -> tuple[Vec3, Vec3] | None:
    """Run Normal To in the active part. Returns the eye and up it looked from, or None."""
    tab = window.current
    mode = window.sketch_mode
    if mode is not None and mode.is_open:
        # The sketch editor always faces its plane: fit the sketch and say so (audit C
        # item 8, D719), instead of doing nothing.
        if mode.canvas is not None:
            mode.canvas.fit()
        window.status.setText(text.NORMAL_TO_SKETCH)
        return None
    if tab is None:
        return None
    view = tab.viewport
    current = getattr(view, "eye_up", None)
    pose = current() if current is not None else None
    eye, up = pose if pose is not None else ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0))
    found = target(window, tab, eye, up)
    if found is None and tab.selection:
        window.status.setText(strings.SELECT_FACE_FOR_NORMAL)
        return None
    if found is None:
        new_eye, new_up = nearest_standard(eye)
        key = ""
    else:
        key, new_eye, new_up = found
        last = getattr(window, "_normal_last", None)
        # The same item again, still looked at from there: turn round (T14.4.1).
        if last is not None and last[0] == key and same_direction(eye, last[1]):
            new_eye, new_up = flipped(last[1], last[2])
    window._normal_last = (key, new_eye, new_up)  # type: ignore[attr-defined]
    look = getattr(view, "look", None)
    if look is not None:
        look(new_eye, new_up)
    return new_eye, new_up


def zoom_to_selection(window: MainWindow) -> bool:
    """Fit the view to the selection: picked faces, edges and vertices, or sketch items."""
    mode = window.sketch_mode
    if mode is not None and mode.canvas is not None:
        if _zoom_sketch(mode.canvas):
            return True
        window.status.setText(text.ZOOM_SELECTION_NOTHING)  # was silent (audit C item 8)
        return False
    tab = window.current
    if tab is None:
        return False
    zoom = getattr(tab.viewport, "zoom_to", None)
    if not tab.selection or zoom is None:
        window.status.setText(text.ZOOM_SELECTION_NOTHING)
        return False
    return bool(zoom(list(tab.selection)))


def _zoom_sketch(canvas: Any) -> bool:
    """Centre the sketch editor on the selected items and fit them in about 80 percent."""
    sk = canvas.edit.sketch
    xs: list[float] = []
    ys: list[float] = []
    for item in canvas.selection:
        e = sk.entities.get(item)
        if e is None:
            continue
        from fdcad.core.sketch.model import Arc, Circle

        if isinstance(e, Circle | Arc):
            c, r = sk.xy(e.center), sk.radius(e.id)
            xs += [c[0] - r, c[0] + r]
            ys += [c[1] - r, c[1] + r]
            continue
        from fdcad.ui.sketch_tools.canvas import _points_of_entity

        for pid in _points_of_entity(e):
            x, y = sk.xy(pid)
            xs.append(x)
            ys.append(y)
    if not xs:
        return False
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    canvas.center = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    size = max(w / max(canvas.width(), 1), h / max(canvas.height(), 1), 1e-6)
    canvas.scale = min(1e5, 0.8 / size)
    canvas.update()
    return True


# Show or hide toggles (T14.4.3) -------------------------------------------------------------


def set_planes_shown(window: MainWindow, on: bool) -> None:
    """View > Planes: the same view state as Hide All Reference Geometry (Ctrl+H)."""
    tab = window.current
    if tab is not None and tab.reference_hidden == on:
        window.toggle_reference_geometry()


def set_sketches_shown(window: MainWindow, on: bool) -> None:
    """View > Sketches: draw no sketches in the 3D view while off (view state, not saved)."""
    from fdcad.ui.main_window.window import DocumentTab

    for i in range(window.tabs.count()):
        tab = window.tabs.widget(i)
        if isinstance(tab, DocumentTab):
            tab.sketches_hidden = not on
            tab.refresh_sketches()


def set_origins_shown(window: MainWindow, on: bool) -> None:
    """View > Origins: show the part origin as three small axes."""
    from fdcad.ui.main_window.window import DocumentTab

    for i in range(window.tabs.count()):
        tab = window.tabs.widget(i)
        if isinstance(tab, DocumentTab):
            tab.origin_shown = on
        fn = getattr(getattr(tab, "viewport", None), "set_origin_shown", None)
        if fn is not None:
            fn(on)
