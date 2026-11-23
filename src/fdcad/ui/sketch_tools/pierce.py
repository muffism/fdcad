"""Sketch, Pierce (TR101, D843): keep a point where a curve or another sketch crosses this
sketch's plane. The choice is kept in the sketch feature and applied on every rebuild."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QInputDialog, QWidget

from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.core.document.model import Document
    from fdcad.ui.sketch_tools.canvas import SketchCanvas

#: Features whose curves can pierce a sketch: curve features and sketches.
_CURVES = ("helix", "projected_curve", "composite_curve", "contour", "point_curve", "sketch")


def curves_before(doc: Document, fid: str) -> list[tuple[str, str]]:
    """(id, name) of the curves and sketches above sketch ``fid`` in the tree."""
    out = []
    for f in doc.features:
        if f.id == fid:
            break
        if f.type in _CURVES:
            out.append((f.id, f.name))
    return out


def pierced(canvas: SketchCanvas, pid: str) -> bool:
    """True when point ``pid`` pierces a curve."""
    refs = canvas.edit.feature.refs.get("pierce") or []
    return any(isinstance(r, dict) and r.get("point") == pid for r in refs)


def ask(parent: QWidget | None, names: list[str]) -> str | None:
    """The chosen curve name, or None (a seam for tests)."""
    chosen, ok = QInputDialog.getItem(parent, strings.PIERCE, strings.PIERCE_ASK, names, 0, False)
    return chosen if ok and chosen else None


def pierce(canvas: SketchCanvas, pid: str, doc: Document, status: Any = None) -> bool:
    """Ask for a curve, then keep point ``pid`` on its crossing (one sketch step)."""
    found = curves_before(doc, canvas.edit.feature.id)
    say = getattr(status, "setText", None)
    if not found:
        if say is not None:
            say(strings.PIERCE_NONE)
        return False
    chosen = ask(canvas, [name for _fid, name in found])
    if chosen is None:
        return False
    fid = next(f for f, name in found if name == chosen)
    refs = [
        r
        for r in canvas.edit.feature.refs.get("pierce") or []
        if isinstance(r, dict) and r.get("point") != pid
    ]
    refs.append({"point": pid, "curve": {"feature": fid}})
    canvas.edit.feature.refs["pierce"] = refs

    def hold() -> None:
        sketch = canvas.edit.sketch
        if not any(r.type == "fixed" and r.entities == [pid] for r in sketch.relations):
            sketch.relate("fixed", pid)

    canvas.run(hold)
    if say is not None:
        say(strings.PIERCE_SET.format(name=chosen))
    return True


def unpierce(canvas: SketchCanvas, pid: str) -> None:
    """Let the point go: drop the pierce and its Fixed relation."""
    refs = [
        r
        for r in canvas.edit.feature.refs.get("pierce") or []
        if isinstance(r, dict) and r.get("point") != pid
    ]
    if refs:
        canvas.edit.feature.refs["pierce"] = refs
    else:
        canvas.edit.feature.refs.pop("pierce", None)

    def free() -> None:
        sketch = canvas.edit.sketch
        sketch.relations = [
            r for r in sketch.relations if not (r.type == "fixed" and r.entities == [pid])
        ]

    canvas.run(free)
