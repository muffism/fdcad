"""Event filters do nothing off the GUI thread (IDEAS 48, D2659).

When another program ends FDCAD from outside, Git Bash's ``kill`` among them, the
exit can run on a thread of its own. Qt then still delivers a few events there
while it shuts down, the C++ events behind them are already gone, and the first
look at one (``event.type()``) ended the process with an access violation in
``crash.log``. Every event filter FDCAD installs on the whole app asks
``off_gui_thread`` first, before it touches the event. The check is plain
Python and never calls into Qt.
"""

from __future__ import annotations

import threading

#: The thread FDCAD's QApplication runs on: Python's main thread, in the app and in tests.
_GUI_THREAD = threading.main_thread().ident


def off_gui_thread() -> bool:
    """True when called on any thread but the GUI thread."""
    return threading.get_ident() != _GUI_THREAD
