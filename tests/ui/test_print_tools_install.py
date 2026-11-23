"""The print and evaluate tools install in a fresh process (D350 to D356).

Other tests import the tool modules first, which would hide a missing import in
``print_tools.install``; a separate interpreter does not.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SCRIPT = """
import sys
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
app = QApplication([])
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.preferences.settings import Settings
win = MainWindow(Settings(QSettings(sys.argv[1], QSettings.Format.IniFormat)))
win.finish_setup()
ids = ("file.export_dxf", "file.export_svg", "print.open_slicer", "print.lay_flat",
       "print.clear_orientation", "evaluate.build_volume", "evaluate.overhang",
       "evaluate.print_estimate", "evaluate.geometry_check")
missing = [i for i in ids if i not in win.commands.actions]
print("missing", missing)
sys.exit(1 if missing else 0)
"""


def test_tools_install_in_a_fresh_process(tmp_path: Path) -> None:
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    env["FDCAD_CACHE_DIR"] = str(tmp_path / "cache")
    env["FDCAD_DATA_DIR"] = str(tmp_path / "data")
    done = subprocess.run(
        [sys.executable, "-c", SCRIPT, str(tmp_path / "prefs.ini")],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
