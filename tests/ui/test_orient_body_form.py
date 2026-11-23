"""Frame to frame in the Move and Copy Body panel (TR268 item 2, D1815)."""

from __future__ import annotations

from fdcad.ui.body_tools.forms import MOVE_COPY_BODY


def test_frame_fields_show_only_for_frame_mode() -> None:
    frame = {f.name for f in MOVE_COPY_BODY.fields() if f.shown({"mode": "frame"})}
    assert {"from_frame", "to_frame", "reverse"} <= frame
    assert "dx" not in frame
    moved = {f.name for f in MOVE_COPY_BODY.fields() if f.shown({"mode": "translate"})}
    assert "from_frame" not in moved


def test_relation_fields_show_only_for_relations_mode() -> None:
    """TR268 item 1 (D2415)."""
    shown = {f.name for f in MOVE_COPY_BODY.fields() if f.shown({"mode": "relations"})}
    assert {"rel_from", "rel_to", "relations"} <= shown
    assert "from_frame" not in shown and "dx" not in shown
    moved = {f.name for f in MOVE_COPY_BODY.fields() if f.shown({"mode": "translate"})}
    assert "relations" not in moved


def test_handle_pivot_and_axes_show_for_handle_moves() -> None:
    """TR268 item 3 (D2416)."""
    delta = {"mode": "translate", "translate_by": "delta", "pivot": "picked"}
    shown = {f.name for f in MOVE_COPY_BODY.fields() if f.shown(delta)}
    assert {"pivot", "pivot_point", "handle_axes"} <= shown
    edge = {
        f.name for f in MOVE_COPY_BODY.fields() if f.shown({"mode": "rotate", "rotate_by": "edge"})
    }
    assert "pivot" not in edge
