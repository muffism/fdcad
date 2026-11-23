"""Save pictures of the 3D view for a design review, in Light and Dark.

    uv run python tools/view_review_shots.py --out .shots/view_before
        [--themes light,dark] [--width 1440] [--height 900] [--only parts,select]
        [--scale 2] [--samples 8]

The 3D view is OpenGL and draws blank on Qt's offscreen platform, so this tool
runs on the real screen: a window opens for each theme and closes again. It
needs a display and a graphics card, so it is a tool to run by hand, never a
test. Each theme writes the sample parts, selected faces with the highlight
under the cursor, a selected edge, a red part, the five display styles, the
reference planes and the origin, two feature previews, the corner triad, a
sketch in the view and the sketch editor. Some
shots are also saved enlarged three times (``_zoom``), to judge line smoothing.
The folder is not for git.

Five more groups were added for the proposals of the review (IDEAS item 83): ``near``
(highlights on red, orange and yellow parts), ``corner`` (the triad at its true size),
``wire`` (wireframe and the hidden line styles on parts with fillets and holes),
``widths`` (sketches, reference curves and marks) and ``see`` (regions, the mirror
image and the graph ghost). ``--scale`` draws at another screen scale and
``--samples`` with another number of smoothing samples.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

PARTS = (
    "nut_and_bolt",
    "enclosure",
    "sheet_metal_bracket",
    "turned_shaft",
    "lofted_handle",
    "tapped_housing",
)
STYLES = ("shaded_edges", "shaded", "hidden_lines", "hidden_lines_visible", "wireframe")
#: A saturated part colour (the red of the X axis), to check that a part is drawn in
#: the colour it was given.
RED = "#C0392B"
#: Part colours near the selection colour, a burnt orange (P2 of the review).
NEAR_COLOURS = (("red", RED), ("orange", "#D9731A"), ("yellow", "#E3B81C"))


def _spin(app: Any, turns: int = 12) -> None:
    """Run the event loop a few turns and delete what ``deleteLater`` queued."""
    from PySide6.QtCore import QCoreApplication, QEvent

    for _ in range(turns):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


class Shots:
    """Takes the shots of one theme."""

    def __init__(self, app: Any, window: Any, out: Path, tag: str) -> None:
        self.app, self.window, self.out, self.tag = app, window, out, tag
        self.failed: list[str] = []

    @property
    def view(self) -> Any:
        """The 3D view of the open part."""
        return self.window.current.viewport

    def save(self, name: str, zoom: tuple[float, float, float, float] | None = None) -> None:
        """Dump the view into ``<name>_<theme>.png``. ``zoom`` is a part of the picture
        (left, top, width, height, each 0 to 1) saved again three times larger."""
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QImage
        from PySide6.QtTest import QTest

        _spin(self.app, 6)
        path = self.out / f"{name}_{self.tag}.png"
        for _ in range(8):  # a view that has just opened may not have its window yet
            if self.view.dump(str(path)):
                break
            QTest.qWait(150)
        else:
            raise RuntimeError(f"the view could not be saved: {path}")
        print(path)
        if zoom is not None:
            image = QImage(str(path))
            w, h = image.width(), image.height()
            part = image.copy(
                round(zoom[0] * w), round(zoom[1] * h), round(zoom[2] * w), round(zoom[3] * h)
            )
            big = part.scaled(
                part.width() * 3,
                part.height() * 3,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            big.save(str(self.out / f"{name}_{self.tag}_zoom.png"))

    def step(self, name: str, work: Callable[[], None]) -> None:
        """Run one shot; a failure is printed and the others still run."""
        try:
            work()
        except Exception:
            self.failed.append(name)
            print(f"FAILED {name}_{self.tag}")
            traceback.print_exc()
        _spin(self.app)

    def open(self, sample: str) -> Any:
        """Open a sample part and wait for its rebuild."""
        self.window.open_path(ROOT / "samples" / f"{sample}.fdprt")
        tab = self.window.current
        tab.session.wait(120000)
        _spin(self.app, 40)
        return tab

    def close_parts(self) -> None:
        """Close every part without asking."""
        w = self.window
        if w.sketch_mode is not None and w.editing == "sketch":
            w.sketch_mode.cancel()
        if w.panel is not None and w.editing == "feature":
            w.panel.cancel()
        _spin(self.app)
        while w.tabs.count():
            w.close_tab(0, ask=False)  # frees the 3D view at once (D2780)
            _spin(self.app)

    # The shots ---------------------------------------------------------------------

    def parts(self) -> None:
        for sample in PARTS:
            self.open(sample)
            self.save(f"part_{sample}", zoom=(0.35, 0.2, 0.3, 0.45))
            if sample == "nut_and_bolt":
                self.save("triad", zoom=(0.0, 0.83, 0.085, 0.17))
            self.close_parts()

    def _shapes_at(self, fx: float, fy: float) -> list[Any]:
        """Faces, edges and vertices of the part under a spot of the view, nearest first."""
        from PySide6.QtCore import QPointF

        v = self.view
        context = v._context
        x, y = v._px(QPointF(fx * v.width(), fy * v.height()))
        context.MoveTo(x, y, v._view, False)
        out = []
        context.InitDetected()
        while context.MoreDetected():
            owner = context.DetectedCurrentOwner()
            if owner is not None and owner.IsSameSelectable(v._part):
                out.append(owner.Shape())
            context.NextDetected()
        context.ClearDetected(False)
        return out

    def _faces(self, spots: list[tuple[float, float]]) -> list[Any]:
        from OCP.TopAbs import TopAbs_FACE

        faces = []
        for fx, fy in spots:
            face = next((s for s in self._shapes_at(fx, fy) if s.ShapeType() == TopAbs_FACE), None)
            if face is not None:
                faces.append(face)
        return faces

    def _hover(self, fx: float, fy: float) -> None:
        from PySide6.QtCore import QPointF

        v = self.view
        x, y = v._px(QPointF(fx * v.width(), fy * v.height()))
        v._context.MoveTo(x, y, v._view, True)
        if hasattr(v, "sync_hover_rim"):
            v.sync_hover_rim()  # the rim follows the hover (D2821)

    def select(self) -> None:
        """Two selected faces and the face under the cursor, on three parts; then a
        selected edge; then the same on a red part."""
        from OCP.TopAbs import TopAbs_EDGE
        from OCP.TopExp import TopExp_Explorer

        cases = (
            ("enclosure", [(0.62, 0.62), (0.5, 0.25)], (0.45, 0.6)),
            ("nut_and_bolt", [(0.36, 0.45), (0.5, 0.2), (0.7, 0.45)], (0.68, 0.55)),
            ("turned_shaft", [(0.3, 0.4), (0.7, 0.75)], (0.6, 0.55)),
        )
        for sample, spots, cursor in cases:
            self.open(sample)
            v = self.view
            faces = self._faces(spots)
            v.select_shapes(faces)
            self._hover(*cursor)
            self.save(f"selected_{sample}", zoom=(0.3, 0.1, 0.4, 0.55))
            v._context.ClearDetected(True)
            if sample == "enclosure" and faces:
                edge = TopExp_Explorer(faces[-1], TopAbs_EDGE)
                v.select_shapes([edge.Current()] if edge.More() else [])
                self.save("selected_edge", zoom=(0.4, 0.05, 0.3, 0.45))
                v.show_part(v._part_shape, RED)
                v.select_shapes(self._faces(spots))
                self._hover(*cursor)
                self.save("selected_red")
                v._context.ClearDetected(True)
            v.clear_selection()
            self.close_parts()

    def colours(self) -> None:
        """A part in a saturated colour: it is drawn in that colour, not a paler one."""
        self.open("bracket")
        v = self.view
        v.show_part(v._part_shape, RED)
        self.save("part_red")
        self.close_parts()

    def styles(self) -> None:
        self.open("enclosure")
        for style in STYLES:
            self.view.set_style(style)
            _spin(self.app, 10)
            self.save(f"style_{style}", zoom=(0.3, 0.3, 0.3, 0.45))
        self.view.set_style("shaded_edges")
        self.close_parts()

    def planes(self) -> None:
        from fdcad.ui.main_window.plane_pick import plane_faces, plane_names

        tab = self.open("bracket")
        v = self.view
        v.show_reference_planes(plane_faces(tab), plane_names(tab))
        v.set_origin_shown(True)
        v._view.SetZoom(0.6, True)
        self.save("planes", zoom=(0.25, 0.2, 0.35, 0.5))
        ids = list(plane_faces(tab))
        v.set_selected_planes(set(ids[:1]))
        self.save("planes_selected")
        v.set_selected_planes(set())
        v.show_reference_planes({}, {})
        v.set_style("wireframe")
        self.save("origin", zoom=(0.3, 0.3, 0.3, 0.5))
        v.set_style("shaded_edges")
        v.set_origin_shown(False)
        self.close_parts()

    def preview(self) -> None:
        from PySide6.QtTest import QTest

        w = self.window
        for sample, kind in (("bracket", "extrude"), ("enclosure", "fillet")):
            self.open(sample)
            feature = next((f for f in w.current.session.document.features if f.type == kind), None)
            if feature is not None:
                w.edit_feature(feature.id)
                QTest.qWait(800)  # the view turns to the feature first
                w.current.session.wait(60000)
                _spin(self.app, 60)
                self.save(f"preview_{kind}", zoom=(0.3, 0.4, 0.3, 0.4))
                w.panel.cancel()
                _spin(self.app, 20)
            self.close_parts()

    def sketches(self) -> None:
        """Sketches shown in the 3D view, and the sketch editor with its colours."""
        from PySide6.QtTest import QTest

        w = self.window
        tab = self.open("bracket")
        v = self.view
        v.show_sketches(list(tab.session.report.sketch_edges.values()))
        v.toggle_transparency()
        self.save("sketch_in_view", zoom=(0.3, 0.2, 0.3, 0.45))
        v.toggle_transparency()
        feature = next(f for f in tab.session.document.features if f.type == "sketch")
        w.edit_feature(feature.id)
        QTest.qWait(900)  # the view turns to the sketch plane first
        _spin(self.app, 30)
        canvas = w.sketch_mode.canvas if w.sketch_mode is not None else None
        if canvas is not None:
            path = self.out / f"sketch_editor_{self.tag}.png"
            canvas.grab().save(str(path))
            print(path)
        w.sketch_mode.cancel()
        QTest.qWait(500)
        self.close_parts()

    # The proposals of the review (IDEAS item 83) ------------------------------------

    def crop(self, name: str, box: tuple[float, float, float, float], times: int = 1) -> None:
        """Save a part of the last ``save(name)`` picture as ``<name>_<theme>_crop.png``,
        at its true size or ``times`` larger."""
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QImage

        image = QImage(str(self.out / f"{name}_{self.tag}.png"))
        w, h = image.width(), image.height()
        part = image.copy(
            round(box[0] * w), round(box[1] * h), round(box[2] * w), round(box[3] * h)
        )
        if times > 1:
            part = part.scaled(
                part.width() * times,
                part.height() * times,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        part.save(str(self.out / f"{name}_{self.tag}_crop.png"))

    def near(self) -> None:
        """Two selected faces and the face under the cursor on a red, an orange and a
        yellow part: the selection colour is a burnt orange (P2)."""
        spots, cursor = [(0.62, 0.62), (0.5, 0.25)], (0.45, 0.6)
        self.open("enclosure")
        v = self.view
        for name, colour in NEAR_COLOURS:
            v.clear_selection()
            v.show_part(v._part_shape, colour)
            v.select_shapes(self._faces(spots))
            self._hover(*cursor)
            self.save(f"near_{name}")
            self.crop(f"near_{name}", (0.3, 0.1, 0.4, 0.55))
            v._context.ClearDetected(True)
        v.clear_selection()
        self.close_parts()

    def corner(self) -> None:
        """The corner triad at its true size: a square of 110 px at 100 percent in the
        lower left of the view, larger by the screen scale (P3)."""
        self.open("bracket")
        v = self.view
        self.save("corner")
        side = 110.0
        self.crop("corner", (0.0, 1.0 - side / v.height(), side / v.width(), side / v.height()))
        self.close_parts()

    def wire(self) -> None:
        """Wireframe and the two hidden line styles on parts with fillets and holes (P4)."""
        for sample in ("enclosure", "tapped_housing", "turned_shaft"):
            self.open(sample)
            for style in ("wireframe", "hidden_lines_visible", "hidden_lines"):
                self.view.set_style(style)
                _spin(self.app, 10)
                self.save(f"wire_{sample}_{style}")
                self.crop(f"wire_{sample}_{style}", (0.25, 0.15, 0.5, 0.7))
            self.view.set_style("shaded_edges")
            self.close_parts()

    def widths(self) -> None:
        """Sketches shown in the view, a reference curve and the marks, beside the
        part's own edges (P5). Run it with ``--scale 2`` to see what a larger screen
        scale gives."""
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
        from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt
        from OCP.TopAbs import TopAbs_EDGE
        from OCP.TopExp import TopExp_Explorer

        tab = self.open("bracket")
        v = self.view
        lo, hi = _box(v._part_shape)
        mid = [(a + b) / 2 for a, b in zip(lo, hi, strict=True)]
        size = max(b - a for a, b in zip(lo, hi, strict=True))
        edges = []
        explorer = TopExp_Explorer(v._part_shape, TopAbs_EDGE)
        while explorer.More():
            edges.append(explorer.Current())
            explorer.Next()
        v.show_sketches(list(tab.session.report.sketch_edges.values()))
        ring = gp_Circ(
            gp_Ax2(gp_Pnt(mid[0], hi[1] + 0.15 * size, mid[2]), gp_Dir(0, 1, 0)), 0.3 * size
        )
        v.show_references([BRepBuilderAPI_MakeEdge(ring).Edge()])
        v.show_lost(edges[0])
        v.show_preview_marks(edges[2:4])
        v.preview_shapes(edges[5:6])
        v.show_axis_choices({"axis": edges[8]})
        v.toggle_transparency()
        v.fit_all(remember=False)
        self.save("widths")
        self.crop("widths", (0.25, 0.1, 0.5, 0.8))
        v.toggle_transparency()
        v.hide_axis_choices()
        v.preview_shapes([])
        v.show_preview_marks([])
        v.show_lost(None)
        v.show_references([])
        self.close_parts()

    def see(self) -> None:
        """The see-through things the review left: a sketch's regions (idle, under the
        cursor, picked), the mirror image and the graph ghost (P6)."""
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeSphere
        from OCP.gp import gp_Pnt

        from fdcad.ui.viewport.meshing import mesh_for_display
        from fdcad.ui.viewport.regions import make_region_shapes

        tab = self.open("plate_with_holes")
        v = self.view
        sketch = next(f for f in tab.session.document.features if f.type == "sketch")
        result = tab.session.report.results[sketch.id]
        shapes = make_region_shapes(sketch.id, result.sketch)
        names = sorted(shapes.faces)
        v.show_regions(shapes.faces)
        v.set_region_state(set(), True)
        self.save("see_regions_idle")
        v.set_region_state(set(names[:1]), True)
        v._regions.set_hover(names[1] if len(names) > 1 else None)
        v._context.UpdateCurrentViewer()
        self.save("see_regions_picked")
        self.crop("see_regions_picked", (0.2, 0.1, 0.6, 0.8))
        v._regions.set_hover(None)
        v.hide_regions()
        self.close_parts()

        self.open("bracket")
        v = self.view
        lo, hi = _box(v._part_shape)
        v.mirror_image.set_plane(((lo[0], 0.0, 0.0), (1.0, 0.0, 0.0)))
        v.fit_all(remember=False)
        self.save("see_mirror")
        self.crop("see_mirror", (0.15, 0.1, 0.7, 0.8))
        v.mirror_image.set_plane(None)
        size = max(b - a for a, b in zip(lo, hi, strict=True))
        mid = [(a + b) / 2 for a, b in zip(lo, hi, strict=True)]
        ball = BRepPrimAPI_MakeSphere(gp_Pnt(hi[0], hi[1], mid[2]), 0.3 * size).Shape()
        block = BRepPrimAPI_MakeBox(
            gp_Pnt(lo[0] - 0.2 * size, mid[1], lo[2] - 0.1 * size),
            gp_Pnt(lo[0] + 0.3 * size, hi[1] + 0.3 * size, hi[2] + 0.1 * size),
        ).Shape()
        for shape in (ball, block):
            mesh_for_display(shape)
        v.show_ghost([ball, block])
        v.fit_all(remember=False)
        self.save("see_ghost")
        self.crop("see_ghost", (0.15, 0.1, 0.7, 0.8))
        v.show_ghost([])
        self.close_parts()


def _box(shape: Any) -> tuple[list[float], list[float]]:
    """The low and high corner of a shape's bounding box."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    lo, hi = box.CornerMin(), box.CornerMax()
    return [lo.X(), lo.Y(), lo.Z()], [hi.X(), hi.Y(), hi.Z()]


def run_theme(
    app: Any, settings: Any, theme: Any, tag: str, out: Path, size: Any, only: set[str]
) -> list[str]:
    """Every shot of one theme. Returns the names of the shots that failed."""
    from fdcad.ui.main_window.window import MainWindow
    from fdcad.ui.themes.theme import apply_theme

    apply_theme(app, theme)
    window = MainWindow(settings)
    window.resize(*size)
    window.show()
    window.finish_setup()
    window.command_tabs.theme_changed()
    _spin(app, 20)
    shots = Shots(app, window, out, tag)
    steps: list[tuple[str, Callable[[], None]]] = [
        ("parts", shots.parts),
        ("select", shots.select),
        ("colours", shots.colours),
        ("styles", shots.styles),
        ("planes", shots.planes),
        ("preview", shots.preview),
        ("sketches", shots.sketches),
        ("near", shots.near),
        ("corner", shots.corner),
        ("wire", shots.wire),
        ("widths", shots.widths),
        ("see", shots.see),
    ]
    for name, work in steps:
        if not only or name in only:
            shots.step(name, work)
            shots.step("close", shots.close_parts)
    window.close()
    window.deleteLater()
    _spin(app)
    return shots.failed


def _use_samples(samples: int) -> None:
    """Draw every view of this run with ``samples`` smoothing samples."""
    from fdcad.ui.viewport import look

    look.msaa_samples = lambda *_a, **_k: samples  # type: ignore[assignment]


def main() -> int:
    """Open the main window on the real screen and save the view review pictures."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=".shots/view", help="folder for the PNG files")
    parser.add_argument("--themes", default="light,dark")
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--only", default="", help="shots to take, e.g. parts,select")
    parser.add_argument("--scale", type=float, default=0.0, help="screen scale, e.g. 1.5 or 2")
    parser.add_argument("--samples", type=int, default=-1, help="smoothing samples, e.g. 4 or 8")
    args = parser.parse_args()

    os.environ.pop("QT_QPA_PLATFORM", None)  # the real screen: the view is OpenGL
    if args.scale > 0:
        os.environ["QT_SCALE_FACTOR"] = str(args.scale)
    scratch = Path(tempfile.mkdtemp(prefix="fdcad_view_"))
    os.environ.setdefault("FDCAD_CACHE_DIR", str(scratch / "cache"))
    os.environ.setdefault("FDCAD_DATA_DIR", str(scratch / "data"))

    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from fdcad.ui.preferences.settings import Settings, Theme

    app = QApplication(sys.argv)
    if args.samples >= 0:
        _use_samples(args.samples)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    themes = {
        "light": Theme.LIGHT,
        "beige": Theme.BEIGE,
        "dark": Theme.DARK,
        "stealth": Theme.STEALTH,
    }
    failed: list[str] = []
    size = (args.width, args.height)
    only = {n.strip() for n in args.only.split(",") if n.strip()}
    for name in [n.strip() for n in args.themes.split(",") if n.strip()]:
        settings = Settings(
            QSettings(str(scratch / f"prefs_{name}.ini"), QSettings.Format.IniFormat)
        )
        settings.theme = themes[name]
        failed += [
            f"{shot}_{name}"
            for shot in run_theme(app, settings, themes[name], name, out, size, only)
        ]
    if failed:
        print("Failed shots: " + ", ".join(failed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
