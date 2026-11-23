"""Read pixels from a real 3D view and print them as one line of JSON.

Run by ``test_view_polish.test_pixels_of_a_real_view`` on the real screen (not the
offscreen platform), so it is a script and not a test: a small window opens, shows a
box in a few looks and closes. Needs a display and a graphics card.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

RED = "#C0392B"


def _linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _encoded(c: float) -> float:
    c = min(1.0, max(0.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def lit(hex_colour: str, shade: float) -> list[float]:
    """An sRGB colour under ``shade`` times its own brightness, as 0 to 255."""
    text = hex_colour.lstrip("#")
    return [255 * _encoded(_linear(int(text[i : i + 2], 16) / 255) * shade) for i in (0, 2, 4)]


def main() -> int:
    """Show a box, read the pixels the test asks about, print them."""
    os.environ.pop("QT_QPA_PLATFORM", None)
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from PySide6.QtGui import QImage
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from fdcad.ui.themes import contrast, theme
    from fdcad.ui.viewport import look
    from fdcad.ui.viewport.widget import ViewportWidget

    app = QApplication(sys.argv)
    view = ViewportWidget()
    view.resize(480, 360)
    view.show()
    QTest.qWait(300)
    if view._view is None:
        print("no 3D view")
        return 1
    box = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    folder = Path(tempfile.mkdtemp(prefix="fdcad_pixels_"))

    def shot(name: str) -> QImage:
        app.processEvents()
        path = folder / f"{name}.png"
        for _ in range(8):
            if view.dump(str(path)):
                break
            QTest.qWait(150)
        return QImage(str(path))

    def at(image: QImage, point: tuple[float, float, float]) -> list[int]:
        x, y = view._screen(point)
        c = image.pixelColor(round(x), round(y))
        return [c.red(), c.green(), c.blue()]

    top, side = (5.0, 10.0, 5.0), (10.0, 5.0, 5.0)
    eye_up = view.eye_up()
    assert eye_up is not None

    def camera(normal: tuple[float, float, float]) -> tuple[float, float, float]:
        """``normal`` in camera space: x to the right, y up, z toward the eye."""
        e, u = eye_up
        length = sum(c * c for c in e) ** 0.5
        z = (e[0] / length, e[1] / length, e[2] / length)
        x = (u[1] * z[2] - u[2] * z[1], u[2] * z[0] - u[0] * z[2], u[0] * z[1] - u[1] * z[0])
        n = sum(c * c for c in x) ** 0.5
        x = (x[0] / n, x[1] / n, x[2] / n)
        y = (z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0])
        return tuple(sum(a * b for a, b in zip(normal, axis, strict=True)) for axis in (x, y, z))  # type: ignore[return-value]

    shade_top = look.face_shade(camera((0.0, 1.0, 0.0)))
    out: dict[str, Any] = {}
    view.set_palette(theme.LIGHT)
    view.show_part(box, RED)
    out["red_top"] = at(shot("red"), top)
    out["red_top_expected"] = lit(RED, shade_top)
    view.show_part(box, None)
    out["grey_top"] = at(shot("grey"), top)
    out["grey_top_expected"] = lit(theme.LIGHT.face, shade_top)

    faces = []
    explorer = TopExp_Explorer(box, TopAbs_FACE)
    while explorer.More():
        faces.append(explorer.Current())
        explorer.Next()

    def centre(face: Any) -> tuple[float, float, float]:
        from OCP.BRepGProp import BRepGProp
        from OCP.GProp import GProp_GProps

        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, props)
        p = props.CentreOfMass()
        return (p.X(), p.Y(), p.Z())

    def face_at(point: tuple[float, float, float]) -> Any:
        return min(
            faces, key=lambda f: sum((a - b) ** 2 for a, b in zip(centre(f), point, strict=True))
        )

    view.select_shapes([face_at(top), face_at(side)])
    selected = shot("selected")
    out["selected_top"] = at(selected, top)
    out["selected_side"] = at(selected, side)
    view.clear_selection()

    def wire_contrast(pal: Any, name: str) -> float:
        view.set_palette(pal)
        view.show_part(box, None)
        view.set_style("wireframe")
        image = shot(name)
        view.set_style("shaded_edges")
        best = 1.0
        # A row through the middle of the box crosses its upright edges.
        y = image.height() // 2
        for x in range(image.width()):
            c = image.pixelColor(x, y)
            ground = image.pixelColor(2, y)
            best = max(best, contrast.ratio(c.name(), ground.name()))
        return best

    out["wire_contrast_light"] = wire_contrast(theme.LIGHT, "wire_light")
    out["wire_contrast_dark"] = wire_contrast(theme.DARK, "wire_dark")
    print(json.dumps(out))
    view.close()
    view.deleteLater()
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
