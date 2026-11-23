"""The system's recent files and a single running FDCAD (TR379, D948).

- Opened and saved parts go on the system's recent list: on Windows through the
  shell, so they show in the taskbar jump list and in Start; on a Mac the Dock menu
  lists FDCAD's own recent parts with a New Part entry.
- A second launch with part files hands them to the FDCAD that is running, through a
  local socket of this user, and then quits, so a double clicked part opens in the
  window already open.

Nothing here runs unless the app turns it on (``enable``), so tests never touch the
system's lists or sockets.
"""

from __future__ import annotations

import getpass
import json
import sys
from collections.abc import Callable
from pathlib import Path

import shiboken6
from PySide6.QtCore import QObject
from PySide6.QtNetwork import QLocalServer, QLocalSocket

_enabled = False


def enable(on: bool = True) -> None:
    """Turn the system integration on (the app does this at start)."""
    global _enabled
    _enabled = on


def enabled() -> bool:
    """True when the app turned the integration on."""
    return _enabled


def add_to_system_recent(path: str | Path, platform: str = sys.platform) -> bool:
    """Put ``path`` on the system's recent documents list. True when it was sent."""
    if not _enabled or platform != "win32":
        return False
    try:
        import ctypes

        # windll is in ctypes on Windows only (D2704)
        shell = getattr(ctypes, "windll").shell32  # noqa: B009
        shell.SHAddToRecentDocs(3, str(Path(path).resolve()))  # 3: a wide string path
    except Exception:  # the list is a nicety; it never stops a save or an open
        return False
    return True


def server_name() -> str:
    """The local socket name, one per user, so two users never share a window."""
    try:
        user = getpass.getuser()
    except Exception:
        user = "user"
    safe = "".join(c if c.isalnum() else "_" for c in user)
    return f"FDCAD-{safe}"


def hand_off(paths: list[Path], name: str | None = None, timeout_ms: int = 1500) -> bool:
    """Send ``paths`` to a running FDCAD. True when one took them (this launch then
    quits); False when none is running."""
    socket = QLocalSocket()
    socket.connectToServer(name or server_name())
    if not socket.waitForConnected(timeout_ms):
        return False
    data = json.dumps({"open": [str(p.resolve()) for p in paths]}).encode("utf-8")
    socket.write(data + b"\n")
    socket.flush()
    if socket.bytesToWrite() and not socket.waitForBytesWritten(timeout_ms):
        return False
    # The running FDCAD closes the connection once it has read the message.
    socket.waitForDisconnected(timeout_ms)
    return True


class InstanceServer(QObject):
    """Listens for later launches and opens the parts they send."""

    def __init__(
        self,
        open_path: Callable[[Path], object],
        bring_forward: Callable[[], object],
        name: str | None = None,
    ) -> None:
        super().__init__()
        self.open_path, self.bring_forward = open_path, bring_forward
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._connected)
        self.name = name or server_name()
        self._sockets: list[QLocalSocket] = []

    def listen(self) -> bool:
        """Start listening. A stale socket left by a crash is removed first."""
        if self.server.listen(self.name):
            return True
        QLocalServer.removeServer(self.name)
        return self.server.listen(self.name)

    def _connected(self) -> None:
        socket = self.server.nextPendingConnection()
        if socket is None:
            return
        # Kept here until it disconnects, so nothing reads a socket Qt already deleted.
        self._sockets.append(socket)
        buffer = bytearray()
        handled = [False]

        def read() -> None:
            if handled[0] or not shiboken6.isValid(socket):
                return
            buffer.extend(bytes(socket.readAll().data()))
            if b"\n" not in buffer:
                return
            handled[0] = True
            line = bytes(buffer).split(b"\n", 1)[0]
            self.received(line)
            socket.disconnectFromServer()

        def gone() -> None:
            if socket in self._sockets:
                self._sockets.remove(socket)
            if shiboken6.isValid(socket):
                socket.deleteLater()

        socket.readyRead.connect(read)
        socket.disconnected.connect(gone)
        if socket.bytesAvailable():
            read()

    def received(self, line: bytes) -> int:
        """Open the parts in one message. Returns how many."""
        try:
            message = json.loads(line.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return 0
        paths = message.get("open", []) if isinstance(message, dict) else []
        count = 0
        for item in paths:
            if isinstance(item, str):
                self.open_path(Path(item))
                count += 1
        self.bring_forward()
        return count

    def close(self) -> None:
        """Stop listening and let go of any open connection."""
        for socket in list(self._sockets):
            if shiboken6.isValid(socket):
                socket.abort()
        self._sockets.clear()
        self.server.close()


def dock_menu(
    new_part: Callable[[], object],
    recent: Callable[[], list[str]],
    open_path: Callable[[Path], object],
) -> object | None:
    """The Mac Dock menu: New Part and the recent parts. None on other systems."""
    if not _enabled or sys.platform != "darwin":
        return None
    from PySide6.QtWidgets import QMenu

    from fdcad.ui import strings

    menu = QMenu()

    def fill() -> None:
        menu.clear()
        menu.addAction(strings.DOCK_NEW_PART).triggered.connect(lambda: new_part())
        files = recent()[:10]
        if files:
            menu.addSeparator()
        for item in files:
            action = menu.addAction(Path(item).name)
            action.triggered.connect(lambda _c=False, p=item: open_path(Path(p)))

    menu.aboutToShow.connect(fill)
    fill()
    menu.setAsDockMenu()
    return menu
