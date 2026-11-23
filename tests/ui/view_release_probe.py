"""Open and close parts on the real screen and check that every 3D view draws.

Run by ``test_view_release.test_views_keep_drawing_while_parts_open_and_close``
on the real screen (not the offscreen platform), so it is a script and not a test.
One part stays open while others are opened and closed quickly; after each open
the new view is saved, and after each close the part that stayed open is saved.
Every drawing error the kernel reports is counted, also those reported while the
garbage collector runs. Prints one line of JSON. Needs a display and a graphics
card. Usage: ``view_release_probe.py [cycles]`` (18 cycles make 37 checks).
"""

from __future__ import annotations

import gc
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
KEPT = "bracket"
OTHERS = ("enclosure", "plate_with_holes", "swept_spring")


def main() -> int:
    """Open and close parts, save the views, print what failed."""
    cycles = int(sys.argv[1]) if len(sys.argv) > 1 else 18
    os.environ.pop("QT_QPA_PLATFORM", None)  # the real screen: the view is OpenGL
    scratch = Path(tempfile.mkdtemp(prefix="fdcad_release_"))
    os.environ.setdefault("FDCAD_CACHE_DIR", str(scratch / "cache"))
    os.environ.setdefault("FDCAD_DATA_DIR", str(scratch / "data"))

    from OCP.Message import Message, Message_Gravity
    from PySide6.QtCore import QCoreApplication, QEvent, QSettings
    from PySide6.QtGui import QImage
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from fdcad.ui.main_window.window import MainWindow
    from fdcad.ui.preferences.settings import Settings

    report = Message.DefaultReport_s(True)  # the kernel's messages, to count errors
    report.ActivateInMessenger(True)
    errors: list[str] = []

    def drain(where: str) -> int:
        found = 0
        for gravity in (Message_Gravity.Message_Fail, Message_Gravity.Message_Alarm):
            for alert in report.GetAlerts(gravity):
                found += 1
                errors.append(f"{where}: {alert.GetMessageKey().strip()[-120:]}")
        report.Clear()
        return found

    def collected(phase: str, info: dict[str, int]) -> None:
        drain("before a collection" if phase == "start" else "while collecting")

    gc.callbacks.append(collected)
    app = QApplication(sys.argv)
    settings = Settings(QSettings(str(scratch / "prefs.ini"), QSettings.Format.IniFormat))
    window = MainWindow(settings)
    window.resize(1000, 700)
    window.show()
    window.finish_setup()

    def spin(turns: int = 12) -> None:
        for _ in range(turns):
            app.processEvents()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    spin(20)

    def open_part(name: str) -> Any:
        window.open_path(ROOT / "samples" / f"{name}.fdprt")
        tab = window.current
        tab.session.wait(120000)
        spin(20)
        return tab

    checks: list[str] = []
    failed: list[str] = []

    def check(tab: Any, label: str) -> None:
        drain("before " + label)
        window.tabs.setCurrentWidget(tab)
        spin(6)
        path = scratch / f"{label}.png"
        saved = False
        for _ in range(3):
            if tab.viewport.dump(str(path)):
                saved = True
                break
            QTest.qWait(100)
        image = QImage(str(path))
        drawn = saved and not image.isNull()
        if drawn:  # a view that could not draw saves black
            c = image.pixelColor(image.width() // 2, 3)
            drawn = (c.red(), c.green(), c.blue()) != (0, 0, 0)
        if drain(label) or not drawn:
            failed.append(label)
        checks.append(label)

    kept = open_part(KEPT)
    check(kept, "kept_start")
    for i in range(cycles):
        tab = open_part(OTHERS[i % len(OTHERS)])
        check(tab, f"new_{i}")
        window.close_tab(window.tabs.indexOf(tab), ask=False)
        spin()
        QTest.qWait(30)
        check(kept, f"kept_{i}")
    window.close()
    spin()
    gc.collect()
    drain("closing")
    gc.callbacks.remove(collected)
    print(
        json.dumps(
            {
                "checks": len(checks),
                "failed": failed,
                "kernel_errors": len(errors),
                "first_errors": errors[:5],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
