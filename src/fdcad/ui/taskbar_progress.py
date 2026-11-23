"""Taskbar and Dock progress for long work (TR380 item 4, DECISIONS D2506).

While the status bar shows progress for a rebuild, an export or the hand off to
the slicer, the Windows taskbar button shows it too (a moving bar, or a filled
one when the steps are known), and the Mac Dock icon shows a badge with the
percentage (or "..." while the amount is not known). Both go when the work ends.

The platform calls use only the system libraries through ctypes: the shell's
taskbar list on Windows and the application's Dock tile on a Mac. Nothing here
runs unless the system integration is on (``system_integration.enable``), so
tests never touch the taskbar; tests give a recording backend instead. A failed
platform call is ignored: progress in the taskbar is a nicety.
"""

from __future__ import annotations

import contextlib
import sys
from typing import Any, Protocol

#: States sent to a backend.
OFF, BUSY, STEPS = "off", "busy", "steps"


class Backend(Protocol):
    """Shows progress on the platform's taskbar or Dock."""

    def show(self, state: str, done: int, total: int) -> None:
        """Show ``state``: OFF, BUSY (amount not known) or STEPS (``done`` of ``total``)."""


def badge_text(state: str, done: int, total: int) -> str:
    """The Dock badge for a state: "" when off, "..." while busy, else a percentage."""
    if state == OFF:
        return ""
    if state == BUSY or total <= 0:
        return "..."
    percent = max(0, min(100, round(100 * done / total)))
    return f"{percent}%"


class _Windows:
    """The taskbar button's progress through ITaskbarList3 (shell32 COM)."""

    _NOPROGRESS, _INDETERMINATE, _NORMAL = 0, 1, 2

    def __init__(self, hwnd: int) -> None:
        import ctypes
        from ctypes import wintypes

        self.hwnd = hwnd
        self._list: Any = None
        # oledll, and WINFUNCTYPE in _call, are in ctypes on Windows only (D2704)
        ole = getattr(ctypes, "oledll").ole32  # noqa: B009
        ole.CoInitialize(None)

        class GUID(ctypes.Structure):
            _fields_ = [
                ("a", wintypes.DWORD),
                ("b", wintypes.WORD),
                ("c", wintypes.WORD),
                ("d", ctypes.c_ubyte * 8),
            ]

        def guid(text: str) -> GUID:
            g = GUID()
            ole.CLSIDFromString(ctypes.c_wchar_p(text), ctypes.byref(g))
            return g

        clsid = guid("{56FDF344-FD6D-11d0-958A-006097C9A090}")  # CLSID_TaskbarList
        iid = guid("{EA1AFB91-9E28-4B86-90E9-9E9F8A5EEFAF}")  # IID_ITaskbarList3
        pointer = ctypes.c_void_p()
        ole.CoCreateInstance(
            ctypes.byref(clsid), None, 1, ctypes.byref(iid), ctypes.byref(pointer)
        )  # 1: CLSCTX_INPROC_SERVER
        self._list = pointer
        self._call(3)  # HrInit

    def _call(self, index: int, *args: Any) -> None:
        import ctypes

        table = ctypes.cast(self._list, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        types = [ctypes.c_void_p] + [type(a) for a in args]
        winfunctype = getattr(ctypes, "WINFUNCTYPE")  # noqa: B009
        fn = winfunctype(ctypes.c_long, *types)(table[index])
        fn(self._list, *args)

    def show(self, state: str, done: int, total: int) -> None:
        import ctypes

        hwnd = ctypes.c_void_p(self.hwnd)
        if state == STEPS and total > 0:
            self._call(10, hwnd, ctypes.c_int(self._NORMAL))  # SetProgressState
            self._call(9, hwnd, ctypes.c_ulonglong(done), ctypes.c_ulonglong(total))
        elif state == BUSY:
            self._call(10, hwnd, ctypes.c_int(self._INDETERMINATE))
        else:
            self._call(10, hwnd, ctypes.c_int(self._NOPROGRESS))


class _Mac:
    """A badge on the Dock icon through NSApplication's dock tile (objc runtime)."""

    def __init__(self) -> None:
        import ctypes
        import ctypes.util

        self._objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc") or "libobjc.dylib")
        ctypes.cdll.LoadLibrary(
            ctypes.util.find_library("AppKit")
            or "/System/Library/Frameworks/AppKit.framework/AppKit"
        )
        self._objc.objc_getClass.restype = ctypes.c_void_p
        self._objc.objc_getClass.argtypes = [ctypes.c_char_p]
        self._objc.sel_registerName.restype = ctypes.c_void_p
        self._objc.sel_registerName.argtypes = [ctypes.c_char_p]

    def _send(self, receiver: Any, selector: str, *args: Any) -> Any:
        import ctypes

        send = self._objc.objc_msgSend
        send.restype = ctypes.c_void_p
        send.argtypes = [ctypes.c_void_p, ctypes.c_void_p] + [ctypes.c_void_p] * len(args)
        return send(receiver, self._objc.sel_registerName(selector.encode()), *args)

    def show(self, state: str, done: int, total: int) -> None:
        app = self._send(self._objc.objc_getClass(b"NSApplication"), "sharedApplication")
        tile = self._send(app, "dockTile")
        text = badge_text(state, done, total)
        label = None
        if text:
            label = self._send(
                self._objc.objc_getClass(b"NSString"),
                "stringWithUTF8String:",
                text.encode("utf-8"),
            )
        self._send(tile, "setBadgeLabel:", label)
        self._send(tile, "display")


def platform_backend(window: Any, platform: str = sys.platform) -> Backend | None:
    """The backend for this platform, or None (other platforms, integration off, or a
    failed start)."""
    from fdcad.ui.system_integration import enabled

    if not enabled():
        return None
    try:
        if platform == "win32":
            return _Windows(int(window.winId()))
        if platform == "darwin":
            return _Mac()
    except Exception:
        return None
    return None


class TaskbarProgress:
    """Sends progress to a backend, skipping repeats; never raises."""

    def __init__(self, backend: Backend | None) -> None:
        self.backend = backend
        self.last: tuple[str, int, int] = (OFF, 0, 0)

    def _send(self, state: str, done: int = 0, total: int = 0) -> None:
        if (state, done, total) == self.last:
            return
        self.last = (state, done, total)
        if self.backend is not None:
            with contextlib.suppress(Exception):
                self.backend.show(state, done, total)

    def busy(self) -> None:
        """Work runs, amount not known."""
        self._send(BUSY)

    def steps(self, done: int, total: int) -> None:
        """``done`` of ``total`` steps."""
        self._send(STEPS, done, total) if total > 0 else self._send(BUSY)

    def clear(self) -> None:
        """No work: remove the progress."""
        self._send(OFF)
