"""Select Previous and Invert Selection (TR93, D915), on a stand in view."""

from __future__ import annotations

from typing import Any

from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from PySide6.QtCore import QObject, Signal

from fdcad.ui.viewport.select_more import SelectionMemory, invert


class _View(QObject):
    selection_changed = Signal(list)

    def __init__(self, part: Any) -> None:
        super().__init__()
        self._part_shape = part
        self.picked: list[Any] = []

    def selected(self) -> list[Any]:
        return list(self.picked)

    def select_shapes(self, shapes: list[Any], add: bool = False) -> None:
        self.picked = list(shapes)
        self.selection_changed.emit(self.selected())


def _faces(shape: Any, kind: Any = TopAbs_FACE) -> list[Any]:
    out = []
    exp = TopExp_Explorer(shape, kind)
    while exp.More():
        out.append(exp.Current())
        exp.Next()
    return out


def test_previous_comes_back_until_a_rebuild() -> None:
    box = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
    view = _View(box)
    memory = SelectionMemory(view)  # type: ignore[arg-type]
    assert not memory.restore()
    first = _faces(box)[:2]
    view.select_shapes(first)
    view.select_shapes([])  # a click in empty space
    assert memory.restore() and view.picked == first
    view.select_shapes([])
    view._part_shape = BRepPrimAPI_MakeBox(5, 5, 5).Shape()  # the part rebuilt
    view.selection_changed.emit([])
    assert not memory.restore()


def test_invert_keeps_to_the_kinds() -> None:
    box = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
    view = _View(box)
    view.picked = _faces(box)[:1]
    assert invert(view, None) == 5  # type: ignore[arg-type]
    assert not any(f.IsSame(_faces(box)[0]) for f in view.picked)
    view.picked = []
    assert invert(view, {"edge"}) == 12  # type: ignore[arg-type]
    assert all(s.ShapeType() == TopAbs_EDGE for s in view.picked)


def test_select_all_takes_the_kind_picked() -> None:
    """TR380, TR224 (D934)."""
    from fdcad.ui.viewport.select_more import select_all

    box = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
    view = _View(box)
    assert select_all(view, None) == 6  # type: ignore[arg-type]
    view.picked = _faces(box, TopAbs_EDGE)[:1]
    assert select_all(view, None) == 12  # type: ignore[arg-type]
    assert select_all(view, {"vertex"}) == 8  # type: ignore[arg-type]
