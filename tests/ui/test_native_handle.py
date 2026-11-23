"""The window handle must reach OpenCascade in the form this platform's OCP build accepts."""

import pytest
from OCP.Aspect import Aspect_NeutralWindow
from pytestqt.qtbot import QtBot

from fdcad.ui.viewport.native import set_native_handle


def test_real_binding_accepts_handle() -> None:
    # Runs on the Windows and macOS CI runners, so each OCP build is checked.
    window = Aspect_NeutralWindow()
    set_native_handle(window, 0x1234)


class _CapsuleOnly:
    def __init__(self) -> None:
        self.received: object = None

    def SetNativeHandle(self, handle: object) -> bool:  # noqa: N802
        if isinstance(handle, int):
            raise TypeError("capsule expected")
        self.received = handle
        return True


class _IntOnly:
    def __init__(self) -> None:
        self.received: object = None

    def SetNativeHandle(self, handle: object) -> bool:  # noqa: N802
        if not isinstance(handle, int):
            raise TypeError("int expected")
        self.received = handle
        return True


def test_capsule_binding_gets_capsule() -> None:
    window = _CapsuleOnly()
    set_native_handle(window, 42)
    assert type(window.received).__name__ == "PyCapsule"


def test_int_binding_gets_int() -> None:
    window = _IntOnly()
    set_native_handle(window, 42)
    assert window.received == 42


def test_other_errors_are_not_hidden() -> None:
    class _Broken:
        def SetNativeHandle(self, handle: object) -> bool:  # noqa: N802
            raise TypeError("always fails")

    with pytest.raises(TypeError, match="always fails"):
        set_native_handle(_Broken(), 42)


def test_a_mac_without_a_real_window_is_not_usable() -> None:
    """D2705: on macOS the kernel treats the id as an NSView, so a made up id ends the process."""
    from fdcad.ui.viewport.native import native_window_usable

    assert not native_window_usable("offscreen", "darwin")
    assert not native_window_usable("minimal", "darwin")
    assert native_window_usable("cocoa", "darwin")
    assert native_window_usable("offscreen", "win32")  # unchanged: the kernel refuses it there
    assert native_window_usable("windows", "win32")


def test_the_view_never_hands_an_unusable_window_to_the_kernel(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D2705: the view says it could not start; it does not pass the id on."""
    from fdcad.ui.viewport import widget

    handed: list[int] = []
    monkeypatch.setattr(widget, "native_window_usable", lambda _platform: False)
    monkeypatch.setattr(widget, "set_native_handle", lambda _w, win_id: handed.append(win_id))
    view = widget.ViewportWidget()
    qtbot.addWidget(view)
    said: list[str] = []
    view.failed.connect(said.append)
    view.show()
    assert handed == []
    assert view._view is None
    assert len(said) == 1 and "could not start" in said[0]
