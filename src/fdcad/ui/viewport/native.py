"""Pass a Qt native window id to OpenCascade in the form the OCP build expects."""

import ctypes
import sys
from typing import Protocol

_capsule_new = ctypes.pythonapi.PyCapsule_New
_capsule_new.restype = ctypes.py_object
_capsule_new.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p]


class _HasNativeHandle(Protocol):
    def SetNativeHandle(self, handle: object, /) -> bool: ...  # noqa: N802 (OCCT name)


def native_window_usable(qt_platform: str, os_name: str = sys.platform) -> bool:
    """False when OpenCascade must not be given this Qt platform's window id (D2705).

    On macOS the kernel uses the id as an NSView. Qt's offscreen and minimal
    platforms give a made up number, and using it ends the process.
    """
    return not (os_name == "darwin" and qt_platform in ("offscreen", "minimal"))


def window_handle_capsule(win_id: int) -> object:
    """Wrap a native window id (HWND on Windows, NSView on macOS) in a capsule."""
    return _capsule_new(win_id, None, None)


def set_native_handle(window: _HasNativeHandle, win_id: int) -> None:
    """Give ``window`` the native window id.

    OCP binds the handle differently per platform: the Windows build takes a
    capsule, the macOS build takes a plain integer. Try the capsule first and
    fall back to the integer.
    """
    try:
        window.SetNativeHandle(window_handle_capsule(win_id))
    except TypeError:
        window.SetNativeHandle(win_id)
