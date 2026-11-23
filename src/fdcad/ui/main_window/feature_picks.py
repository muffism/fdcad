"""Picks in the 3D view for an open Phase 2 feature panel (PHASE2_SPEC common rules).

While an extrude end condition waits for a face, plane or vertex, or a fillet,
chamfer, shell, draft, sweep or loft panel collects edges and faces, a click in
the view goes to it. Every pick becomes a stored reference (FDEF_SPEC 7).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab, MainWindow


def route_pick(window: MainWindow, tab: DocumentTab, shapes: list[Any]) -> None:
    """Give a selection in the view to the open feature panel, when it takes one."""
    from fdcad.core.naming.select import reference_for

    panel, report = window.panel, tab.session.report
    if panel is None or panel.feature is None or report is None or report.body is None:
        return
    if not shapes:
        return
    if getattr(panel, "bodies_want_pick", lambda: False)():
        # Selected bodies (TR33): a face picks its body.
        problem = panel.bodies_box.take(report.body, shapes)
        if problem:
            window.status.setText(problem)
        else:
            panel._changed()
        return
    form = getattr(panel, "form", None)
    if form is not None:
        take_point = getattr(form, "take_point", None)
        point = getattr(tab, "cursor_model", None)
        if take_point is not None and take_point(report.body, shapes, point):
            return  # a hole placed by clicking (PHASE4_SPEC P4.1 item 3)
        problem = form.take_shapes(report.body, shapes)
        if problem:
            window.status.setText(problem)
        return
    start = getattr(panel, "start", None)
    if start is not None and start.current in ("surface", "vertex"):
        return  # the From pick route already handled it (window._pick_for_start)
    if len(shapes) != 1 or not panel.end_wants_pick():
        return
    ref = reference_for(report.body, shapes[0])
    if ref is None:
        return
    problem = panel.set_start_pick(ref)
    if problem:
        window.status.setText(problem)
