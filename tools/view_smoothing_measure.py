"""Measure what smoothing samples cost in a real 3D view: memory and frame time.

    uv run python tools/view_smoothing_measure.py
        [--samples 0,4,8] [--sizes 1440x900,1680x1050] [--part nut_and_bolt|empty]
        [--style shaded_edges] [--frames 300] [--scale 1]

Run by hand on a real screen, like ``tools/view_review_shots.py``: the 3D view is
OpenGL. Each setting runs in a process of its own, so the memory figures do not mix. A
window opens with the sample part, the view turns ``--frames`` times with the screen's
frame lock off, and one line is printed per setting:

- the graphics memory in use on the whole machine (from the driver, where it tells:
  NVIDIA and AMD cards), and how much more that is than the first setting of the size;
- the memory of the process (its working set and what it has committed);
- the mean and the slowest twentieth of the frame times.

It was written for proposal P1 of the view review (DECISIONS D2820).
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MB = 1024 * 1024


def _committed() -> int:
    """Bytes the process has committed (Windows: the page file use), or 0."""
    if sys.platform != "win32":
        return 0
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [  # ctypes needs a plain list
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = Counters()
    counters.cb = ctypes.sizeof(Counters)
    windll = getattr(ctypes, "windll")  # noqa: B009  # only exists on Windows
    current = windll.kernel32.GetCurrentProcess
    current.restype = wintypes.HANDLE
    info = windll.psapi.GetProcessMemoryInfo
    info.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    info.restype = wintypes.BOOL
    return (
        int(counters.PagefileUsage) if info(current(), ctypes.byref(counters), counters.cb) else 0
    )


def _graphics(view: Any) -> dict[str, str]:
    """What the graphics driver says about itself and its memory."""
    from OCP.collections import IndexedDataMap_TCollection_AsciiString_TCollection_AsciiString
    from OCP.Graphic3d import Graphic3d_DiagnosticInfo_Complete

    found = IndexedDataMap_TCollection_AsciiString_TCollection_AsciiString()
    view.DiagnosticInformation(found, Graphic3d_DiagnosticInfo_Complete)
    return {
        found.FindKey(i).ToCString(): found.FindFromIndex(i).ToCString()
        for i in range(1, found.Extent() + 1)
    }


def _mib(text: str) -> float:
    """The number of a driver value such as ``3282 MiB``, or -1."""
    try:
        return float(text.split()[0])
    except (IndexError, ValueError):
        return -1.0


def child(args: argparse.Namespace) -> int:
    """One setting: open the part, turn the view, print one line of JSON."""
    os.environ.pop("QT_QPA_PLATFORM", None)
    if args.scale > 0:
        os.environ["QT_SCALE_FACTOR"] = str(args.scale)
    scratch = Path(tempfile.mkdtemp(prefix="fdcad_smooth_"))
    os.environ.setdefault("FDCAD_CACHE_DIR", str(scratch / "cache"))
    os.environ.setdefault("FDCAD_DATA_DIR", str(scratch / "data"))

    from PySide6.QtCore import QPointF, QSettings
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from fdcad.sysinfo import process_memory
    from fdcad.ui.main_window.window import MainWindow
    from fdcad.ui.preferences.settings import Settings
    from fdcad.ui.viewport import look
    from fdcad.ui.viewport.widget import ViewportWidget

    samples = int(args.samples)
    look.msaa_samples = lambda *_a, **_k: samples  # type: ignore[assignment]

    start_view = ViewportWidget._init_view

    def unlocked(self: Any) -> None:
        # Without the screen's frame lock a frame takes as long as it takes to draw.
        self._driver.ChangeOptions().swapInterval = 0
        start_view(self)

    ViewportWidget._init_view = unlocked  # type: ignore[method-assign]

    app = QApplication(sys.argv)
    settings = Settings(QSettings(str(scratch / "prefs.ini"), QSettings.Format.IniFormat))
    window = MainWindow(settings)
    width, height = (int(n) for n in args.sizes.split("x"))
    window.resize(width, height)
    window.show()
    window.finish_setup()
    if args.part == "empty":
        from fdcad.ui.session import DocumentSession

        window.add_session(DocumentSession.new(settings.default_units, window))
    else:
        window.open_path(ROOT / "samples" / f"{args.part}.fdprt")
    tab = window.current
    tab.session.wait(300000)
    for _ in range(40):
        app.processEvents()
    QTest.qWait(500)
    v = tab.viewport
    if v._view is None:
        print(json.dumps({"error": "no 3D view"}))
        return 1
    v.set_style(args.style)
    for _ in range(10):
        app.processEvents()
    for _ in range(30):  # warm up: buffers made, shaders built
        v._rotate_by(QPointF(2.0, 1.0))
        v._view.Redraw()
    times = []
    for _ in range(args.frames):
        begin = time.perf_counter()
        v._rotate_by(QPointF(2.0, 1.0))
        v._view.Redraw()
        times.append(time.perf_counter() - begin)
    times.sort()
    info = _graphics(v._view)
    total, free = _mib(info.get("GPU memory", "")), _mib(info.get("GPU free memory", ""))
    out = {
        "samples": samples,
        "window": args.sizes,
        "view": info.get("Viewport", ""),
        "card": info.get("GLdevice", ""),
        "gpu_used_mib": total - free if total >= 0 and free >= 0 else -1.0,
        "working_set_mb": process_memory() / MB,
        "committed_mb": _committed() / MB,
        "frame_ms": 1000.0 * sum(times) / len(times),
        "frame_p95_ms": 1000.0 * times[int(0.95 * (len(times) - 1))],
    }
    print("RESULT " + json.dumps(out))
    window.close_tab(0, ask=False)
    window.close()
    return 0


def main() -> int:
    """Run every setting in a process of its own and print a table."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", default="0,4,8")
    parser.add_argument("--sizes", default="1440x900,1680x1050")
    parser.add_argument("--part", default="nut_and_bolt")
    parser.add_argument("--style", default="shaded_edges")
    parser.add_argument("--frames", type=int, default=300)
    parser.add_argument("--scale", type=float, default=0.0)
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.child:
        return child(args)
    print(
        "window      view        samples  graphics MiB  more MiB  working set MB  "
        "committed MB  frame ms  slow frame ms"
    )
    for size in [s.strip() for s in args.sizes.split(",") if s.strip()]:
        first: float | None = None
        for samples in [s.strip() for s in args.samples.split(",") if s.strip()]:
            command = [
                sys.executable, __file__, "--child", "--samples", samples, "--sizes", size,
                "--part", args.part, "--style", args.style, "--frames", str(args.frames),
                "--scale", str(args.scale),
            ]  # fmt: skip
            done = subprocess.run(command, capture_output=True, text=True, timeout=900)
            line = next((ln for ln in done.stdout.splitlines() if ln.startswith("RESULT ")), "")
            if not line:
                print(f"{size}  samples {samples}: failed\n{done.stderr[-800:]}")
                continue
            r = json.loads(line[len("RESULT ") :])
            used = r["gpu_used_mib"]
            if first is None:
                first = used
            print(
                f"{r['window']:<11} {r['view']:<11} {r['samples']:>7}  {used:>12.0f}  "
                f"{used - first:>8.0f}  {r['working_set_mb']:>14.0f}  {r['committed_mb']:>12.0f}  "
                f"{r['frame_ms']:>8.2f}  {r['frame_p95_ms']:>13.2f}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
