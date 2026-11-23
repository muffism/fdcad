"""Read pixels from a real 3D view for the six view proposals (D2820 to D2825) and
print them as one line of JSON.

Run by ``test_view_proposals.test_pixels_of_a_real_view`` on the real screen (not the
offscreen platform), so it is a script and not a test: a small window opens, shows a
few shapes and closes. ``QT_SCALE_FACTOR`` sets the screen scale it runs at. Needs a
display and a graphics card.
"""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

RED = "#C0392B"


def main() -> int:
    """Show a box, a cylinder and a sketch line; read what the test asks about."""
    os.environ.pop("QT_QPA_PLATFORM", None)
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from PySide6.QtGui import QImage
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from fdcad.ui.themes import theme
    from fdcad.ui.viewport import look, regions, triad
    from fdcad.ui.viewport import widget as widget_module
    from fdcad.ui.viewport.meshing import mesh_for_display
    from fdcad.ui.viewport.widget import ViewportWidget

    app = QApplication(sys.argv)
    view = ViewportWidget()
    scale = float(os.environ.get("QT_SCALE_FACTOR", "1") or 1)
    view.resize(round(640 / scale), round(480 / scale))
    view.show()
    QTest.qWait(300)
    if view._view is None:
        print("no 3D view")
        return 1
    folder = Path(tempfile.mkdtemp(prefix="fdcad_proposals_"))
    pal = theme.LIGHT
    widget_module.is_dark = lambda: False  # type: ignore[assignment]
    view.set_palette(pal)
    dpr = view._dpr
    out: dict[str, Any] = {"scale": dpr}

    def shot(name: str) -> QImage:
        app.processEvents()
        path = folder / f"{name}.png"
        for _ in range(8):
            if view.dump(str(path)):
                break
            QTest.qWait(150)
        return QImage(str(path))

    def rgb(image: QImage, x: float, y: float) -> list[int]:
        c = image.pixelColor(round(x), round(y))
        return [c.red(), c.green(), c.blue()]

    def close(a: list[int], hex_colour: str, limit: int = 12) -> bool:
        text = hex_colour.lstrip("#")[-6:]
        return all(abs(a[i] - int(text[2 * i : 2 * i + 2], 16)) <= limit for i in range(3))

    # P1: the samples this view draws with, and what the card says it has.
    out["samples"] = view._samples
    out["samples_asked"] = view._view.RenderingParams().NbMsaaSamples
    out["card_bytes"] = look.card_memory(view._view)
    width, height = view.view_pixels()
    out["samples_expected"] = look.msaa_samples(dpr, width * height, out["card_bytes"])

    # P3: the triad lies where the click areas say it does.
    empty = shot("empty")
    h = empty.height()
    eye_up = view.eye_up()
    assert eye_up is not None
    cx, from_bottom = triad.centre(dpr)
    cy = h - from_bottom
    side = round(80 * dpr)
    kinds = {
        "x": lambda r, g, b: r > g + 40 and r > b + 40,
        "y": lambda r, g, b: g > r + 30 and g > b + 30,
        "z": lambda r, g, b: b > r + 30 and b > g + 20,
    }
    found: dict[str, Any] = {}
    for name, is_axis in kinds.items():
        points = [
            (x, y) for y in range(h - side, h) for x in range(side) if is_axis(*rgb(empty, x, y))
        ]
        reach = max((math.hypot(x - cx, y - cy) for x, y in points), default=0.0)
        outer = [
            p for p in points if math.hypot(p[0] - cx, p[1] - cy) > 0.3 * triad.LENGTH_PX * dpr
        ]
        picked = sum(
            1 for x, y in outer if triad.axis_at(x + 0.5, y + 0.5, h, *eye_up, dpr) == name
        )
        found[name] = {"reach": reach / dpr, "picked": picked / max(1, len(outer))}
    out["triad"] = found

    # P2: a selected face of a red box has a rim beside its outline.
    box = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    mesh_for_display(box)
    view.show_part(box, RED)
    faces = []
    explorer = TopExp_Explorer(box, TopAbs_FACE)
    while explorer.More():
        faces.append(explorer.Current())
        explorer.Next()

    def top_face() -> Any:
        from OCP.BRepGProp import BRepGProp
        from OCP.GProp import GProp_GProps

        def height_of(face: Any) -> float:
            props = GProp_GProps()
            BRepGProp.SurfaceProperties_s(face, props)
            return float(props.CentreOfMass().Y())

        return max(faces, key=height_of)

    view.select_shapes([top_face()])
    image = shot("rim")
    rim = look.rim_colour(pal, pal.selection)
    # Walk from the middle of the top face over its front corner and out of the part.
    (ax, ay), (bx, by) = view._screen((5.0, 10.0, 5.0)), view._screen((10.0, 10.0, 10.0))
    steps = int(math.hypot(bx - ax, by - ay) * 1.3)
    walk = [
        rgb(image, ax + (bx - ax) * i / steps * 1.3, ay + (by - ay) * i / steps * 1.3)
        for i in range(steps)
    ]
    out["rim_pixels"] = sum(1 for c in walk if close(c, rim, 40))
    out["outline_pixels"] = sum(1 for c in walk if close(c, pal.selection, 40))
    view.clear_selection()

    # P4: a cylinder in wireframe has no line round its middle.
    tube = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 1, 0)), 5.0, 20.0).Shape()
    mesh_for_display(tube)
    view.show_part(tube, None)
    view.set_style("wireframe")
    view._view.SetProj(0.0, 0.0, 1.0)
    view._view.SetUp(0.0, 1.0, 0.0)
    view._view.FitAll(0.3, False)
    image = shot("wire")
    ground = rgb(image, 3, image.height() // 2)
    (lx, my), (rx, _y) = view._screen((-5.0, 10.0, 0.0)), view._screen((5.0, 10.0, 0.0))
    row = [rgb(image, x, my) for x in range(round(lx) + 3, round(rx) - 2)]
    out["wire_mid_row"] = len(row)
    out["wire_mid_row_lines"] = sum(
        1 for c in row if max(abs(c[i] - ground[i]) for i in range(3)) > 40
    )
    view.set_style("shaded_edges")

    # P5: a sketch line is twice as heavy as an edge at every scale.
    view.show_part(None)
    line = BRepBuilderAPI_MakeEdge(gp_Pnt(-10, 0, 0), gp_Pnt(10, 0, 0)).Edge()
    view.show_sketches([line])
    view._view.SetProj(0.0, 0.0, 1.0)
    view._view.SetUp(0.0, 1.0, 0.0)
    view._view.FitAll(0.3, False)
    image = shot("sketch")
    x, y = view._screen((0.0, 0.0, 0.0))
    column = [rgb(image, x, y + k) for k in range(-12, 13)]
    ground = rgb(image, x, y - 20)
    red_of_line = int(pal.sketch_under.lstrip("#")[0:2], 16)
    # The ink of a column across the line, in device pixels of a full line.
    out["sketch_width"] = sum(max(0, ground[0] - c[0]) for c in column) / max(
        1, ground[0] - red_of_line
    )
    view.show_sketches([])

    # P6: a region over the grey part has the colour the model says.
    view.show_part(box, None)
    view._view.SetProj(1.0, 1.0, 1.0)
    view._view.SetUp(0.0, 1.0, 0.0)
    view._view.FitAll(0.3, False)
    bare = shot("bare")
    at = view._screen((5.0, 10.0, 5.0))
    under = "#{:02x}{:02x}{:02x}".format(*rgb(bare, *at))
    view.show_regions({"r": top_face()})
    view.set_region_state({"r"}, True)
    image = shot("region")
    out["region_picked"] = rgb(image, *view._screen((5.0, 10.0, 5.0)))

    def linear(value: int) -> float:
        c = value / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    # How bright the top face is, as a part of the part's colour: the region is lit
    # the same.
    shade = linear(int(under[3:5], 16)) / linear(int(pal.face.lstrip("#")[2:4], 16))
    accent = widget_module.ACCENT[False]
    expected = look.seen_through(look.lit(accent, shade), under, regions.PICKED_TRANSPARENCY)
    out["region_expected"] = [int(expected[i : i + 2], 16) for i in (1, 3, 5)]
    view.hide_regions()

    print(json.dumps(out))
    view.release()
    view.close()
    view.deleteLater()
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
