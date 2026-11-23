"""The packaging data check finds nothing missing in the source checkout."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fdcad.ui import bundle_check


def test_source_checkout_has_everything(qtbot: QtBot) -> None:
    assert bundle_check.bundle_problems() == []


def test_missing_icons_and_samples_are_reported(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(bundle_check, "icon_path", lambda name: tmp_path / f"{name}.svg")
    monkeypatch.setattr(bundle_check, "sample_files", lambda: [])
    problems = bundle_check.bundle_problems()
    assert any("Icon files are missing" in p for p in problems)
    assert any("Sample parts are missing" in p for p in problems)


def test_app_writes_the_check_and_quits(tmp_path: Path) -> None:
    report = tmp_path / "check.json"
    env = dict(os.environ, FDCAD_BUNDLE_CHECK=str(report), QT_QPA_PLATFORM="offscreen")
    env["FDCAD_DATA_DIR"] = str(tmp_path / "data")
    env["FDCAD_CACHE_DIR"] = str(tmp_path / "cache")
    code = "from fdcad.app import main; raise SystemExit(main(['fdcad']))"
    subprocess.run([sys.executable, "-c", code], env=env, timeout=120, check=True)
    assert json.loads(report.read_text(encoding="utf-8")) == {"problems": []}


def test_missing_graph_samples_are_reported(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The built app had no samples/graphs folder (round 10e, D636).
    monkeypatch.setattr(bundle_check, "sample_dir", lambda: tmp_path)
    problems = bundle_check.bundle_problems()
    assert any("samples/graphs" in p for p in problems)
