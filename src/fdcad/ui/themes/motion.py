"""Motion rules: short animations with a purpose, none when reduced (spec U4.5, U7, D664).

* panels and menus: 150 ms (inside the 120 to 200 ms band)
* the camera: 250 ms with ease in and out
* no bounce or overshoot anywhere
* nothing animates when the Reduce motion preference is on, or while a slow
  rebuild runs

Every animation asks :func:`duration` for its length, so one switch turns them
all off. Qt's own menu, combo box and tooltip effects are turned off with it.
"""

from __future__ import annotations

import weakref
from typing import Any

from PySide6.QtCore import QEasingCurve, QObject, Qt, QTimer
from PySide6.QtWidgets import QApplication

PANEL_MS = 150
MENU_MS = 150
CAMERA_MS = 250
#: Ease in and out with no overshoot, for every animation.
EASING = QEasingCurve.Type.InOutCubic

_EFFECTS = (
    Qt.UIEffect.UI_AnimateMenu,
    Qt.UIEffect.UI_FadeMenu,
    Qt.UIEffect.UI_AnimateCombo,
    Qt.UIEffect.UI_AnimateTooltip,
    Qt.UIEffect.UI_FadeTooltip,
    Qt.UIEffect.UI_AnimateToolBox,
)
_state = {"reduced": False, "busy": False}
#: Qt's effect settings before Reduce motion turned them off, to put back.
_system: dict[Qt.UIEffect, bool] = {}


def system_reduce_motion(platform: str | None = None) -> bool:
    """True when the system asks apps to reduce motion (TR294, D975): on Windows when
    window animations are off, on a Mac when Reduce motion is on in Accessibility.
    False when it cannot be read."""
    import sys

    platform = platform or sys.platform
    try:
        if platform == "win32":
            import ctypes

            animate = ctypes.c_int(1)
            user32 = getattr(ctypes, "windll").user32  # noqa: B009  (Windows only)
            # SPI_GETCLIENTAREAANIMATION (0x1042): are window animations on?
            if user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(animate), 0):
                return not animate.value
            return False
        if platform == "darwin":
            import subprocess

            found = subprocess.run(
                ["/usr/bin/defaults", "read", "com.apple.universalaccess", "reduceMotion"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            return found.stdout.strip() == "1"
    except Exception:  # the system setting is a default only; never fail on it
        return False
    return False


def reduced() -> bool:
    """True when nothing should animate right now."""
    return _state["reduced"] or _state["busy"] or slow_rebuild()


def duration(ms: int) -> int:
    """The length to animate for: ``ms``, or 0 when motion is reduced or a rebuild runs."""
    return 0 if reduced() else ms


def set_reduce_motion(on: bool) -> None:
    """Turn the Reduce motion preference on or off, including Qt's own effects."""
    _state["reduced"] = on
    if QApplication.instance() is None:
        return
    for effect in _EFFECTS:
        if on:
            _system.setdefault(effect, QApplication.isEffectEnabled(effect))
            QApplication.setEffectEnabled(effect, False)
        elif effect in _system:
            QApplication.setEffectEnabled(effect, _system.pop(effect))


def set_busy(on: bool) -> None:
    """Mark the app as busy (animations wait) or not, for work other than rebuilds."""
    _state["busy"] = on


#: A rebuild counts as slow once it has run this long (the U8.1 limit).
SLOW_MS = 300
#: Sessions whose rebuild has run longer than ``SLOW_MS``.
_slow: weakref.WeakSet[Any] = weakref.WeakSet()


def _still_rebuilding(session: Any) -> bool:
    try:
        value = session.is_rebuilding  # a property on DocumentSession
        return bool(value() if callable(value) else value)
    except RuntimeError:  # the session was deleted
        return False


def slow_rebuild() -> bool:
    """True while a rebuild that started more than ``SLOW_MS`` ago still runs."""
    for session in list(_slow):
        if not _still_rebuilding(session):
            _slow.discard(session)
    return bool(_slow)


def rebuild_started(session: QObject) -> None:
    """A rebuild of ``session`` began; it counts as slow if it still runs after ``SLOW_MS``."""

    # A weak reference, so the pending check never keeps a closed part's session alive.
    ref = weakref.ref(session)

    def check() -> None:
        current = ref()
        if current is not None and _still_rebuilding(current):
            _slow.add(current)

    QTimer.singleShot(SLOW_MS, check)
