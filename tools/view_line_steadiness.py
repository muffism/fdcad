"""Measure how evenly a real 3D view draws thin lines, for a number of smoothing samples.

    uv run python tools/view_line_steadiness.py
        [--samples 4,8] [--scales 1,1.25,1.5,2] [--style wireframe]

Run by hand on a real screen, like ``tools/view_review_shots.py``. Each setting runs in
a process of its own. A small window shows a box from three sides, in Light and in
Dark. For every slanted edge of the box the ink of each pixel column across the line
is added up (how far the pixels are from the empty view). A steady line has the same
ink all along it; a line that looks beaded does not. The figure printed is the spread
of that ink, its standard deviation over its mean, averaged over the edges: lower is
steadier.

It was written for proposal P1 of the view review (DECISIONS D2820).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def child(samples: int, scale: float, style: str) -> int:
    """One setting: print one line of JSON."""
    os.environ.pop("QT_QPA_PLATFORM", None)
    os.environ["QT_SCALE_FACTOR"] = str(scale)

    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from PySide6.QtGui import QImage
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from fdcad.ui.themes import theme
    from fdcad.ui.viewport import look

    look.msaa_samples = lambda *_a, **_k: samples  # type: ignore[assignment]
    from fdcad.ui.viewport.widget import ViewportWidget

    app = QApplication(sys.argv)
    view = ViewportWidget()
    view.resize(round(900 / scale), round(700 / scale))
    view.show()
    QTest.qWait(400)
    if view._view is None:
        print("RESULT " + json.dumps({"error": "no 3D view"}))
        return 1
    folder = Path(tempfile.mkdtemp(prefix="fdcad_steady_"))

    def shot(name: str) -> QImage:
        app.processEvents()
        path = folder / f"{name}.png"
        for _ in range(8):
            if view.dump(str(path)):
                break
            QTest.qWait(150)
        return QImage(str(path))

    def brightness(image: QImage, x: int, y: int) -> float:
        c = image.pixelColor(x, y)
        return 0.2126 * c.red() + 0.7152 * c.green() + 0.0722 * c.blue()

    size = (10.0, 6.0, 3.0)
    corners = [(x, y, z) for x in (0.0, size[0]) for y in (0.0, size[1]) for z in (0.0, size[2])]
    edges = [
        (a, b)
        for i, a in enumerate(corners)
        for b in corners[i + 1 :]
        if sum(p != q for p, q in zip(a, b, strict=True)) == 1
    ]
    out: dict[str, Any] = {"samples": samples, "scale": scale}
    for tag, pal in (("light", theme.LIGHT), ("dark", theme.DARK)):
        view.set_palette(pal)
        view.show_part(None)
        empty = shot("empty")
        spreads: list[float] = []
        for eye in ((1.0, 0.7, 0.45), (0.3, 1.0, 0.8), (0.9, 0.2, 1.0)):
            view.show_part(BRepPrimAPI_MakeBox(*size).Shape())
            view.set_style(style)
            view._view.SetProj(*eye)
            view._view.FitAll(0.3, False)
            image = shot("box")
            w, h = image.width(), image.height()
            for a, b in edges:
                (x0, y0), (x1, y1) = view._screen(a), view._screen(b)
                dx, dy = x1 - x0, y1 - y0
                n = int(max(abs(dx), abs(dy)))
                if n < 60 or min(abs(dx), abs(dy)) < 3:
                    continue  # short, or along the pixel grid: nothing to smooth
                steep = abs(dy) > abs(dx)
                band = 4 + int(scale)
                sums = []
                for i in range(int(0.12 * n), int(0.88 * n)):
                    x, y = x0 + i / n * dx, y0 + i / n * dy
                    total = 0.0
                    for k in range(-band, band + 1):
                        px, py = (round(x) + k, round(y)) if steep else (round(x), round(y) + k)
                        if 0 <= px < w and 0 <= py < h:
                            total += abs(brightness(image, px, py) - brightness(empty, px, py))
                    sums.append(total)
                middle = sorted(sums)[len(sums) // 2] if sums else 0.0
                if middle <= 1:
                    continue  # the edge is hidden in this style
                kept = [s for s in sums if s < 1.5 * middle]  # not where another edge crosses
                mean = sum(kept) / len(kept)
                spreads.append(math.sqrt(sum((s - mean) ** 2 for s in kept) / len(kept)) / mean)
        out[tag] = sum(spreads) / max(1, len(spreads))
        out[f"{tag}_edges"] = len(spreads)
    print("RESULT " + json.dumps(out))
    view.release()
    view.close()
    return 0


def main() -> int:
    """Run every setting in a process of its own and print a table."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", default="4,8")
    parser.add_argument("--scales", default="1,1.25,1.5,2")
    parser.add_argument("--style", default="wireframe")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.child:
        return child(int(args.samples), float(args.scales), args.style)
    print("scale  samples  spread in Light  spread in Dark  edges")
    for scale in [s.strip() for s in args.scales.split(",") if s.strip()]:
        for samples in [s.strip() for s in args.samples.split(",") if s.strip()]:
            command = [
                sys.executable, __file__, "--child", "--samples", samples, "--scales", scale,
                "--style", args.style,
            ]  # fmt: skip
            done = subprocess.run(command, capture_output=True, text=True, timeout=600)
            line = next((ln for ln in done.stdout.splitlines() if ln.startswith("RESULT ")), "")
            if not line:
                print(f"{scale}  {samples}: failed\n{done.stderr[-800:]}")
                continue
            r = json.loads(line[len("RESULT ") :])
            if "error" in r:
                print(f"{scale}  {samples}: {r['error']}")
                continue
            print(
                f"{scale:<5}  {samples:>7}  {r['light']:>15.3f}  {r['dark']:>14.3f}  "
                f"{r['light_edges']:>5}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
