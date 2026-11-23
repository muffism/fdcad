"""The face helper bar beside the last picked face (PHASE3_SPEC P3.1.1 item 2).

One click buttons add related faces: coplanar faces, inner loops, faces
around, tangent faces, coaxial cylinders and so on. Hovering a button
highlights what it would add. The face queries are kernel work, so they run
on the thread pool and the bar only receives finished face lists
(CLAUDE.md rule 2). The bar never takes focus and hides when the cursor moves away.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import (
    QEvent,
    QObject,
    QPoint,
    QRunnable,
    QSize,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
)
from PySide6.QtWidgets import QFrame, QHBoxLayout, QToolButton, QWidget

from fdcad.core.features.face_picks import HELPERS
from fdcad.core.kernel import kernel_job
from fdcad.ui import strings_phase3 as text
from fdcad.ui.background import start_job
from fdcad.ui.icons import icon

#: Hide the bar when the cursor is this far from it, in pixels.
FADE_PX = 200


class _Signals(QObject):
    done = Signal(str, int, list)  # helper, generation, faces


class _HelperJob(QRunnable):
    def __init__(self, body: Any, face: Any, helper: str, generation: int) -> None:
        super().__init__()
        self.body, self.face, self.helper, self.generation = body, face, helper, generation
        self.signals = _Signals()

    @kernel_job
    def run(self) -> None:
        from fdcad.core.features.face_picks import helper_faces

        try:
            faces = helper_faces(self.body, self.face, self.helper)
        except Exception:  # a failed helper just adds nothing
            faces = []
        self.signals.done.emit(self.helper, self.generation, faces)


class HelperBar(QFrame):
    """Floating row of face helper buttons."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("face_helper_bar")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        from fdcad.ui.themes.style import unit

        u = unit(self.font())
        row = QHBoxLayout(self)
        row.setContentsMargins(u, u, u, u)
        row.setSpacing(u // 2)
        self.buttons: dict[str, QToolButton] = {}
        for helper in HELPERS:
            button = QToolButton()
            button.setObjectName(f"helper_{helper}")
            button.setAutoRaise(True)
            button.setToolTip(text.HELPER_TIPS[helper])
            found = icon(f"helper.{helper}")
            if found.isNull():
                button.setText(helper[:2])
            else:
                button.setIcon(found)
                button.setIconSize(QSize(5 * u, 5 * u))
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.clicked.connect(lambda _c=False, h=helper: self._clicked(h))
            button.installEventFilter(self)
            row.addWidget(button)
            self.buttons[helper] = button
        self.body: Any = None
        self.face: Any = None
        self.results: dict[str, list[Any]] = {}
        self.hovering: str | None = None
        self._generation = 0
        self._jobs: set[_HelperJob] = set()
        self._add: Callable[[list[Any]], None] = lambda _faces: None
        self._highlight: Callable[[list[Any]], None] = lambda _faces: None
        self._timer = QTimer(self)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._fade)

    def offer(
        self,
        body: Any,
        face: Any,
        add: Callable[[list[Any]], None],
        highlight: Callable[[list[Any]], None],
        pos: QPoint,
    ) -> None:
        """Show the bar for ``face`` near ``pos`` and work out every helper in the background."""
        self.body, self.face = body, face
        self._add, self._highlight = add, highlight
        self.results = {}
        self._generation += 1
        for helper in HELPERS:
            job = _HelperJob(body, face, helper, self._generation)
            job.signals.done.connect(self._done)
            self._jobs.add(job)
            start_job(QThreadPool.globalInstance(), job)
        self.adjustSize()
        self.move(pos + QPoint(16, 16))
        parent = self.parentWidget()
        if parent is not None and parent.isVisible():
            self.show()
        self._timer.start()

    def wait(self, timeout_ms: int = 10000) -> bool:
        """Block until the helper queries finish (tests)."""
        return bool(QThreadPool.globalInstance().waitForDone(timeout_ms))

    def _done(self, helper: str, generation: int, faces: list[Any]) -> None:
        self._jobs = {j for j in self._jobs if j.generation == self._generation}
        if generation != self._generation:
            return
        self.results[helper] = faces
        button = self.buttons[helper]
        button.setEnabled(bool(faces))
        if self.hovering == helper:
            self._highlight(faces)

    def _clicked(self, helper: str) -> None:
        faces = self.results.get(helper, [])
        if faces:
            self._add(faces)
        self._highlight([])
        self.hide()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Hovering a button highlights what it would add."""
        for helper, button in self.buttons.items():
            if watched is button:
                if event.type() == QEvent.Type.Enter:
                    self.hovering = helper
                    self._highlight(self.results.get(helper, []))
                elif event.type() == QEvent.Type.Leave:
                    self.hovering = None
                    self._highlight([])
        return super().eventFilter(watched, event)

    def _fade(self) -> None:
        if not self.isVisible():
            self._timer.stop()
            return
        from PySide6.QtGui import QCursor

        cursor = QCursor.pos()
        rect = self.frameGeometry().adjusted(-FADE_PX, -FADE_PX, FADE_PX, FADE_PX)
        if not rect.contains(cursor):
            self._highlight([])
            self.hide()
            self._timer.stop()
