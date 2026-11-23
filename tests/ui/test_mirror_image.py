"""Mirror image display (TR309, D926)."""

from __future__ import annotations

from typing import Any

from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

from fdcad.ui.themes.theme import palette
from fdcad.ui.viewport.mirror_image import MirrorImage


class _Context:
    def __init__(self) -> None:
        self.shown: list[Any] = []

    def Display(self, item: Any, _update: bool) -> None:  # noqa: N802
        self.shown.append(item)

    def Remove(self, item: Any, _update: bool) -> None:  # noqa: N802
        self.shown.remove(item)

    def Deactivate(self, _item: Any) -> None:  # noqa: N802
        pass


class _View:
    def __init__(self) -> None:
        self._context = _Context()
        self._part_shape: Any = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
        self._palette = palette()
        self._view = None


def test_image_follows_the_plane_and_the_part() -> None:
    view = _View()
    image = MirrorImage(view)  # type: ignore[arg-type]
    assert image.set_plane(((0, 0, 0), (1, 0, 0)))
    assert len(view._context.shown) == 1
    trsf = image.item.LocalTransformation()
    assert trsf.ScaleFactor() < 0 or trsf.IsNegative()  # a reflection
    view._part_shape = BRepPrimAPI_MakeBox(5, 5, 5).Shape()  # the part rebuilt
    assert image.refresh() and len(view._context.shown) == 1
    assert not image.set_plane(None) and view._context.shown == []
    view._part_shape = None
    assert not image.set_plane(((0, 0, 0), (0, 0, 1)))
