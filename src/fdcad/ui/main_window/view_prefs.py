"""Apply the View preferences to the 3D views (round 12: TR211, TR212, TR214, TR312)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fdcad.ui.preferences.view_options import ViewOptions

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow


def apply_to(viewport: Any, store: Any) -> None:
    """Give one 3D view the View preferences. Views without the 3D kernel are skipped."""
    options = ViewOptions(store)
    set_edges = getattr(viewport, "set_edge_options", None)
    if set_edges is not None:
        set_edges(options.smooth_edges, options.hidden_edges)
    if hasattr(viewport, "wheel_reverse"):  # TR211
        viewport.wheel_reverse = options.wheel_reverse
        viewport.zoom_about_cursor = options.zoom_about_cursor
        viewport.arrow_step = options.arrow_step
        viewport.turn_speed = options.turn_speed
        viewport.fit_on_view = options.fit_on_view
        viewport.mouse_preset = options.mouse_preset  # TR312


def apply_all(window: MainWindow) -> None:
    """Give every open part's 3D view the View preferences."""
    for i in range(window.tabs.count()):
        viewport = getattr(window.tabs.widget(i), "viewport", None)
        if viewport is not None:
            apply_to(viewport, window.settings.store)
    feature_edges(window)


def feature_edges_of(window: MainWindow) -> list[Any]:
    """Every edge of the feature selected in the tree, or [] (TR212)."""
    from fdcad.core.edge_display import edges_of

    tab = window.current
    tree = window.tree
    if tab is None or tree is None or not ViewOptions(window.settings.store).feature_edges:
        return []
    fid = tree.selected_id()
    report = tab.session.report
    if fid is None or report is None or report.body is None:
        return []
    prefix = f"{fid}/"
    faces = [face for name, face in report.body.faces if name.startswith(prefix)]
    return edges_of(faces) if faces else []


def feature_edges(window: MainWindow) -> list[Any]:
    """Draw the selected feature's edges in the active view; returns them."""
    tab = window.current
    show = getattr(tab.viewport, "show_feature_edges", None) if tab is not None else None
    edges = feature_edges_of(window)
    if show is not None:
        show(edges)
    return edges
