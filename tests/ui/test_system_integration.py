"""System recent list and one running FDCAD (TR379, D948)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from pytestqt.qtbot import QtBot

from fdcad.ui import system_integration as system


def test_off_unless_the_app_turns_it_on(tmp_path: Path) -> None:
    assert not system.enabled()
    assert not system.add_to_system_recent(tmp_path / "a.fdprt", platform="win32")
    assert system.dock_menu(lambda: None, list, lambda _p: None) is None
    assert system.server_name().startswith("FDCAD-")


def test_a_second_launch_hands_its_parts_over(qtbot: QtBot, tmp_path: Path) -> None:
    name = f"FDCAD-test-{uuid.uuid4().hex[:8]}"
    opened: list[Path] = []
    raised: list[bool] = []
    server = system.InstanceServer(opened.append, lambda: raised.append(True), name)
    assert server.listen()
    try:
        part = tmp_path / "bracket.fdprt"
        part.write_text("{}", encoding="utf-8")
        assert not system.hand_off([part], name=name + "-none", timeout_ms=200)
        import subprocess
        import sys

        code = (
            "import sys; from pathlib import Path; "
            "from PySide6.QtCore import QCoreApplication; "
            "from fdcad.ui.system_integration import hand_off; "
            "app = QCoreApplication([]); "
            "sys.exit(0 if hand_off([Path(sys.argv[1])], sys.argv[2]) else 3)"
        )
        sender = subprocess.Popen([sys.executable, "-c", code, str(part), name])
        qtbot.waitUntil(lambda: bool(opened), timeout=15000)
        assert sender.wait(15) == 0
        assert opened == [part.resolve()] and raised == [True]
    finally:
        server.close()
        qtbot.wait(50)  # let Qt finish with the connection before the server goes


def test_bad_messages_open_nothing() -> None:
    server = system.InstanceServer(lambda _p: None, lambda: None, "unused")
    assert server.received(b"not json") == 0
    assert server.received(json.dumps({"open": [1, "x.fdprt"]}).encode()) == 1
