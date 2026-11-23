"""Base of the on and off analysis overlays (build volume, overhang).

While on, the overlay is worked out again in the background after every
rebuild, orientation change and document tab change. Results that arrive
after a newer request are dropped.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject

from fdcad.ui.print_tools import jobs

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab, MainWindow


class ToggleOverlay(QObject):
    """Subclasses give ``work_for`` (UI thread, returns background work), ``show`` and ``hide``."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.window = window
        self.on = False
        self.generation = 0
        self.result: Any = None
        self._watched: set[int] = set()
        window.tabs.currentChanged.connect(lambda _i: self.refresh())

    def set_on(self, on: bool) -> None:
        """Turn the overlay on or off."""
        self.on = on
        self.generation += 1
        if on:
            self.refresh()
        else:
            tab = self.window.current
            if tab is not None:
                self.hide(tab)

    def _watch(self, tab: DocumentTab) -> None:
        session = tab.session
        if id(session) in self._watched:
            return
        self._watched.add(id(session))
        session.rebuilt.connect(lambda *_a: self.refresh())
        session.display_changed.connect(self.refresh)

    def refresh(self) -> None:
        """Work the overlay out again for the current tab, in the background."""
        if not self.on:
            return
        tab = self.window.current
        self.generation += 1
        if tab is None:
            return
        self._watch(tab)
        work = self.work_for(tab)
        if work is None:
            self.hide(tab)
            return
        generation = self.generation

        def done(result: Any) -> None:
            if generation == self.generation and self.on and self.window.current is tab:
                self.result = result
                self.show(tab, result)

        def failed(message: str) -> None:
            if generation == self.generation and self.on:
                self.hide(tab)
                self.window.status.setText(self.failed_text(message))

        jobs.start(work, done, failed)

    def work_for(self, tab: DocumentTab) -> Callable[[], Any] | None:
        """Background work for ``tab``, or None (after a status message) when there is none."""
        raise NotImplementedError

    def show(self, tab: DocumentTab, result: Any) -> None:
        """Draw ``result`` (UI thread)."""
        raise NotImplementedError

    def hide(self, tab: DocumentTab) -> None:
        """Take the overlay away."""
        raise NotImplementedError

    def failed_text(self, message: str) -> str:
        """Status text for a failed job."""
        return message
