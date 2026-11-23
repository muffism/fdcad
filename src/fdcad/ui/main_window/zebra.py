"""Zebra stripes (TR18, DECISIONS D754).

An evaluate display that draws black and white stripes over the faces, as if a
striped room were reflected in them. Smooth joins show unbroken stripes; a sharp
change in the surface shows a kink or a jump. The stripes are the kernel view's
environment texture, so they follow the view as it turns, with no work per
frame in Python. Stripe count and direction are set in a small window. Display
only: the part does not change, nothing is saved and nothing goes on the undo
list.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QComboBox, QFormLayout, QSpinBox, QWidget

from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow

DEFAULT_COUNT = 12
COUNT_RANGE = (4, 48)
DIRECTIONS = ("vertical", "horizontal")
#: The texture size in pixels: wide enough for crisp stripes, small enough to build at once.
_SIZE = 256


def stripe_rows(count: int, vertical: bool, size: int = _SIZE) -> list[list[bool]]:
    """Which pixels of the square texture are white: ``count`` white and ``count``
    black stripes across it, running up and down (vertical) or side to side."""
    band = [(i * 2 * count // size) % 2 == 0 for i in range(size)]
    if vertical:
        return [band[:] for _ in range(size)]
    return [[on] * size for on in band]


def stripe_texture(count: int, vertical: bool) -> Any:
    """The stripes as a kernel environment texture."""
    from OCP.Graphic3d import Graphic3d_TextureEnv
    from OCP.Image import Image_Format, Image_PixMap
    from OCP.Quantity import Quantity_ColorRGBA

    white, black = Quantity_ColorRGBA(1.0, 1.0, 1.0, 1.0), Quantity_ColorRGBA(0.0, 0.0, 0.0, 1.0)
    pixmap = Image_PixMap()
    pixmap.InitZero(Image_Format.Image_Format_RGB, _SIZE, _SIZE)
    # 65 thousand pixels of a texture, not model data: built once per change of setting.
    for y, row in enumerate(stripe_rows(count, vertical)):
        for x, on in enumerate(row):
            pixmap.SetPixelColor(x, y, white if on else black)
    return Graphic3d_TextureEnv(pixmap)


class ZebraStripes(QObject):
    """Turns the stripes on and off and keeps them on the current part."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.window = window
        self.on = False
        self.panel = QWidget(window, Qt.WindowType.Tool)
        self.panel.setObjectName("zebra_panel")
        self.panel.setWindowTitle(strings.ZEBRA_TITLE)
        layout = QFormLayout(self.panel)
        self.count = QSpinBox()
        self.count.setRange(*COUNT_RANGE)
        self.count.setValue(DEFAULT_COUNT)
        self.count.setToolTip(strings.ZEBRA_COUNT_TIP)
        self.direction = QComboBox()
        for key in DIRECTIONS:
            self.direction.addItem(strings.ZEBRA_DIRECTIONS[key], key)
        layout.addRow(strings.ZEBRA_COUNT, self.count)
        layout.addRow(strings.ZEBRA_DIRECTION, self.direction)
        self.count.valueChanged.connect(lambda _v: self.refresh())
        self.direction.currentIndexChanged.connect(lambda _i: self.refresh())
        window.tabs.currentChanged.connect(lambda _i: self.refresh())

    @property
    def vertical(self) -> bool:
        """True for stripes that run up and down."""
        return bool(self.direction.currentData() == "vertical")

    def set_on(self, on: bool) -> None:
        """Show or hide the stripes and their window."""
        self.on = on
        self.panel.setVisible(on)
        self.refresh()

    def refresh(self) -> None:
        """Stripes on the current part only; every other part goes back to normal."""
        texture = None
        for i in range(self.window.tabs.count()):
            viewport = getattr(self.window.tabs.widget(i), "viewport", None)
            set_zebra = getattr(viewport, "set_zebra", None)
            if set_zebra is None:
                continue
            current = self.window.tabs.widget(i) is self.window.current
            if self.on and current:
                if texture is None:
                    texture = stripe_texture(self.count.value(), self.vertical)
                set_zebra(texture)
            else:
                set_zebra(None)


def install(window: MainWindow) -> ZebraStripes:
    """Create the controller and its checkable command."""
    zebra = ZebraStripes(window)
    action = window.commands.add(
        "evaluate.zebra", lambda: zebra.set_on(action.isChecked()), checkable=True
    )
    return zebra
