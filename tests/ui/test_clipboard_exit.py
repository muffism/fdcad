"""A process that copied a feature exits cleanly (D2617, IDEAS 71).

On the offscreen platform Qt frees the clipboard's data after Python has shut
down. Data made in Python then ended the process with an access violation (exit
code 139) after every test had passed, so CI would see a passing run fail.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

_COPY_THEN_EXIT = """
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
app = QApplication([])
from fdcad.samples.make import SAMPLE_DIR
from tests.ui.sweep_support import close_window, make_window, open_part
win = make_window(Path(sys.argv[1]))
tab = open_part(win, SAMPLE_DIR / "plate_with_holes.fdprt")
sketch = next(f.id for f in tab.session.document.features if f.type == "sketch")
assert win.feature_clipboard.copy(sketch)
close_window(win)
print("copied", flush=True)
"""


def _run(code: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "src"), str(ROOT)])
    env["FDCAD_CACHE_DIR"] = str(tmp_path / "cache")
    env["FDCAD_DATA_DIR"] = str(tmp_path / "data")
    return subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)],
        env=env,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_copying_a_feature_then_exiting_ends_cleanly(tmp_path: Path) -> None:
    done = _run(_COPY_THEN_EXIT, tmp_path)
    assert "copied" in done.stdout, done.stderr[-2000:]
    assert done.returncode == 0, f"exit code {done.returncode}\n{done.stderr[-2000:]}"


def test_copied_data_stays_on_the_clipboard_while_the_app_runs(tmp_path: Path) -> None:
    code = """
from PySide6.QtCore import QMimeData
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication
app = QApplication([])
from fdcad.ui import clipboard
mime = QMimeData()
mime.setData("application/x-fdcad-test", b"{}")
clipboard.put(mime)
assert QGuiApplication.clipboard().mimeData().hasFormat("application/x-fdcad-test")
print("copied", flush=True)
"""
    done = _run(code, tmp_path)
    assert "copied" in done.stdout, done.stderr[-2000:]
    assert done.returncode == 0, f"exit code {done.returncode}\n{done.stderr[-2000:]}"


def test_the_app_puts_its_data_on_the_clipboard_through_one_helper() -> None:
    # Any other setMimeData call would bring the exit crash back.
    found = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "src" / "fdcad").rglob("*.py")
        if path.name != "clipboard.py" and ".setMimeData(" in path.read_text(encoding="utf-8")
    ]
    assert found == []
