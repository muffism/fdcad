"""The lessons window ticks steps from the part (TR291 item 2, D2505)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.document.model import new_document
from fdcad.core.sketch.model import Sketch
from fdcad.ui.help.lessons import FINISHED, RESUMED, TICK, load_progress, save_progress
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.features.test_features import add_extrude, add_sketch, rect
from tests.ui.test_main_window import _folders, window

__all__ = ["_folders", "window"]


def test_progress_round_trip(window: MainWindow) -> None:
    store = window.settings.store
    save_progress(store, {"first_part": {0, 2}, "unknown": {1}})
    assert load_progress(store) == {"first_part": {0, 2}}
    store.setValue("help/lessons", "{broken")
    assert load_progress(store) == {}


def test_steps_tick_and_resume_later(qtbot: QtBot, window: MainWindow) -> None:
    assert "lessons" in window.help.actions
    panel = window.help.show_lessons()
    assert panel.isVisible() and panel.lesson.key == "first_part"
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 30, 20)
    sk = add_sketch(doc, s, {"feature": "f2"})
    add_extrude(doc, sk, 4.0)
    session = DocumentSession(doc, None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.add_session(session)
    qtbot.waitUntil(lambda: panel.done() == {0, 2}, timeout=5000)
    assert panel.step_labels[0].text().startswith(TICK)
    panel.resume_later()
    assert not panel.isVisible() and window.status.text() == RESUMED
    again = window.help.show_lessons()
    assert again is panel and again.done() == {0, 2}
    assert load_progress(window.settings.store)["first_part"] == {0, 2}
    panel.start_over()
    assert panel.done() == set()
    panel.progress["first_part"] = set(range(len(panel.lesson.steps)))
    panel.check()
    assert panel.note.text() == FINISHED
    session.wait()


def test_welcome_offers_the_lessons(window: MainWindow) -> None:
    dialog = window.help.show_welcome()
    assert dialog is not None and not dialog.lessons_button.isHidden()
    dialog.lessons_button.click()
    assert not dialog.isVisible()
    assert window.help.lessons is not None and window.help.lessons.isVisible()
    window.help.lessons.resume_later()
