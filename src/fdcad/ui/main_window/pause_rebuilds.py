"""Pause Rebuilds and checkpoints (TR276, D835).

Edit, Pause Rebuilds collects edits without rebuilding; the status bar says the
part is out of date. Rebuild applies them and leaves the pause; Rebuild and
Stay Paused applies them and stays; Discard Paused Edits undoes them. A feature
marked as a checkpoint (tree right click) stops every rebuild after it until
Continue Rebuild.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow


def install(window: MainWindow, menu: Any) -> None:
    """Add the commands to the Edit menu."""
    a = window.commands

    def session() -> Any:
        tab = window.current
        return tab.session if tab is not None else None

    def toggle() -> None:
        s = session()
        if s is not None:
            s.set_paused(window.pause_action.isChecked())
            show(window)

    window.pause_action = a.add("edit.pause_rebuilds", toggle, checkable=True)
    menu.addAction(window.pause_action)
    menu.addAction(a.add("edit.rebuild_stay", lambda: _call(session(), "rebuild_paused", True)))
    menu.addAction(a.add("edit.discard_paused", lambda: _call(session(), "discard_paused")))
    menu.addAction(a.add("edit.continue_rebuild", lambda: _call(session(), "continue_rebuild")))


def _call(target: Any, name: str, *args: Any) -> None:
    if target is not None:
        getattr(target, name)(*args)


def show(window: MainWindow) -> str:
    """Tick the menu item for the current part and say its state in the status bar."""
    tab = window.current
    s = tab.session if tab is not None else None
    action = getattr(window, "pause_action", None)
    if action is not None:
        action.blockSignals(True)
        action.setChecked(bool(s is not None and s.paused))
        action.blockSignals(False)
    text = ""
    if s is not None and s.paused:
        text = strings.PAUSE_OUT_OF_DATE if s.out_of_date else strings.PAUSE_ON
    elif s is not None and s.stopped_at is not None:
        try:
            name = s.document.feature(s.stopped_at).name
        except KeyError:
            name = s.stopped_at
        text = strings.CHECKPOINT_STOPPED.format(name=name)
    if text:
        window.status.setText(text)
    bars = getattr(tab, "message_bars", None)
    if bars is not None:  # TR203: the pause stays in sight until it ends
        if s is not None and s.paused:
            bars.show_message("rebuilds_paused", text, "warning")
        else:
            bars.close_message("rebuilds_paused")
    return text
