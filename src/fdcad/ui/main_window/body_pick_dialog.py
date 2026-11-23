"""Pick Bodies for a STEP or IGES import (TR302 item 2, DECISIONS D1203).

A list of the file's bodies with a tick box, volume and size each. The ticked
bodies are shown in the 3D view while the window is open, so the user sees
what comes in. OK stores the pick in the import's ``keep_bodies``.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fdcad.ui import strings_import

_LAYER = "step_pick"


def _size(shape: Any) -> tuple[float, float, float]:
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    lo, hi = box.CornerMin(), box.CornerMax()
    return hi.X() - lo.X(), hi.Y() - lo.Y(), hi.Z() - lo.Z()


def summaries(bodies: list[Any]) -> list[str]:
    """One line per body: its number, volume and size (bounding box queries only)."""
    from fdcad.core.features.solids import volume_of

    out = []
    for i, body in enumerate(bodies, 1):
        dx, dy, dz = _size(body)
        out.append(
            strings_import.PICK_BODY_ROW.format(
                index=i, volume=f"{volume_of(body):.6g}", size=f"{dx:.4g} x {dy:.4g} x {dz:.4g}"
            )
        )
    return out


class BodyPickDialog(QDialog):
    """Tick the bodies that come in; ``keep`` holds the pick after OK."""

    def __init__(
        self,
        name: str,
        bodies: list[Any],
        keep: list[int] | None,
        parent: QWidget | None = None,
        viewport: Any = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("body_pick_dialog")
        self.setWindowTitle(strings_import.PICK_BODIES_TITLE.format(name=name))
        self.bodies, self.viewport = bodies, viewport
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(strings_import.PICK_BODIES_PROMPT))
        self.list = QListWidget()
        self.list.setObjectName("body_pick_list")
        for i, text in enumerate(summaries(bodies)):
            item = QListWidgetItem(text)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            on = keep is None or i in keep
            item.setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
            self.list.addItem(item)
        layout.addWidget(self.list)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.list.itemChanged.connect(lambda _item: self._changed())
        self._changed()

    @property
    def picked(self) -> list[int]:
        """Indices of the ticked bodies."""
        return [
            i
            for i in range(self.list.count())
            if self.list.item(i).checkState() == Qt.CheckState.Checked
        ]

    @property
    def keep(self) -> str:
        """The ``keep_bodies`` text: empty when every body is ticked."""
        picked = self.picked
        if len(picked) == len(self.bodies):
            return ""
        return ", ".join(str(i + 1) for i in picked)

    def _changed(self) -> None:
        ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setEnabled(bool(self.picked))  # at least one body comes in
        self._preview([self.bodies[i] for i in self.picked])

    def _preview(self, shapes: list[Any]) -> None:
        if self.viewport is None:
            return
        from fdcad.ui.print_tools.overlay import show_layer
        from fdcad.ui.themes.theme import DATA

        show_layer(self.viewport, _LAYER, shapes, DATA["fits"], shaded=True)

    def clear_preview(self) -> None:
        """Take the preview out of the view."""
        self._preview([])

    def done(self, result: int) -> None:
        self.clear_preview()
        super().done(result)


def run(dialog: BodyPickDialog) -> bool:
    """Show the dialog and wait; True on OK (a seam for tests, which cannot click it)."""
    return bool(dialog.exec())
