"""First run lessons that check the result (TR291 item 2, DECISIONS D2505).

Help, Lessons opens a small window beside the part. It lists a lesson's steps;
each is ticked when the part shows it (read after every rebuild and save), so
the user may work any way they like. Resume Later closes the window and keeps
the progress; Help, Lessons opens it again at the same place. Start Over clears
the lesson's ticks. Progress is kept in the settings, never in the part.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from fdcad.core.lessons import BY_KEY, LESSONS, Context, Lesson, next_step, update

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab, MainWindow

TITLE = "Lessons"
MENU = "&Lessons"
START_LESSONS = "Start Lessons"
CHOOSE = "Lesson"
INTRO = "Do each step in your own way. A step is ticked when the part shows it."
RESUME_LATER = "Resume Later"
START_OVER = "Start Over"
FINISHED = "Lesson done. Pick another lesson, or close this window."
NO_PART = "Open or make a part to start. Use File, New Part."
RESUMED = "Lesson kept: use Help, Lessons to go on."
TICK, NEXT, TODO = "☑", "▶", "☐"
_PROGRESS = "help/lessons"
_CURRENT = "help/lesson_current"


def load_progress(store: Any) -> dict[str, set[int]]:
    """Ticked steps of each lesson from the settings store."""
    raw = store.value(_PROGRESS, "")
    try:
        data = json.loads(raw) if isinstance(raw, str) and raw else {}
    except ValueError:
        data = {}
    out: dict[str, set[int]] = {}
    if isinstance(data, dict):
        for key, steps in data.items():
            if key in BY_KEY and isinstance(steps, list):
                out[key] = {int(i) for i in steps if isinstance(i, int)}
    return out


def save_progress(store: Any, progress: dict[str, set[int]]) -> None:
    """Keep the ticked steps in the settings store."""
    store.setValue(_PROGRESS, json.dumps({k: sorted(v) for k, v in progress.items()}))


class LessonPanel(QWidget):
    """The lesson window: a lesson chooser, its steps, Resume Later and Start Over."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window, Qt.WindowType.Tool)
        self.main = window
        self.setObjectName("lesson_panel")
        self.setWindowTitle(TITLE)
        self.store = window.settings.store
        self.progress = load_progress(self.store)
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel(CHOOSE))
        self.choice = QComboBox()
        self.choice.setObjectName("lesson_choice")
        for lesson in LESSONS:
            self.choice.addItem(lesson.title, lesson.key)
        current = self.store.value(_CURRENT, LESSONS[0].key)
        self.choice.setCurrentIndex(max(0, self.choice.findData(current)))
        top.addWidget(self.choice, 1)
        layout.addLayout(top)
        intro = QLabel(INTRO)
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.step_labels: list[QLabel] = []
        self.steps_box = QVBoxLayout()
        layout.addLayout(self.steps_box)
        self.note = QLabel()
        self.note.setObjectName("lesson_note")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        buttons = QHBoxLayout()
        self.resume_button = QPushButton(RESUME_LATER)
        self.resume_button.setObjectName("lesson_resume_later")
        self.over_button = QPushButton(START_OVER)
        self.over_button.setObjectName("lesson_start_over")
        buttons.addWidget(self.over_button)
        buttons.addStretch(1)
        buttons.addWidget(self.resume_button)
        layout.addLayout(buttons)
        layout.addStretch(1)
        self.choice.currentIndexChanged.connect(lambda _i: self._chosen())
        self.resume_button.clicked.connect(self.resume_later)
        self.over_button.clicked.connect(self.start_over)
        self._watched: set[int] = set()
        window.tabs.currentChanged.connect(lambda _i: self.check())
        self._fill()

    @property
    def lesson(self) -> Lesson:
        """The lesson shown."""
        return BY_KEY[str(self.choice.currentData())]

    def done(self) -> set[int]:
        """The ticked steps of the lesson shown."""
        return self.progress.get(self.lesson.key, set())

    def _chosen(self) -> None:
        self.store.setValue(_CURRENT, self.lesson.key)
        self._fill()
        self.check()

    def _fill(self) -> None:
        for label in self.step_labels:
            self.steps_box.removeWidget(label)
            label.deleteLater()
        self.step_labels = []
        for _step in self.lesson.steps:
            label = QLabel()
            label.setWordWrap(True)
            self.steps_box.addWidget(label)
            self.step_labels.append(label)
        self._show()

    def _show(self) -> None:
        done = self.done()
        upcoming = next_step(self.lesson, done)
        for i, (label, step) in enumerate(zip(self.step_labels, self.lesson.steps, strict=True)):
            mark = TICK if i in done else NEXT if i == upcoming else TODO
            text = f"{mark}  {step.text}"
            label.setText(f"<b>{text}</b>" if i == upcoming else text)
            label.setEnabled(i not in done)
        if upcoming is None:
            self.note.setText(FINISHED)
        elif self.main.current is None:
            self.note.setText(NO_PART)
        else:
            self.note.setText("")

    def _watch(self, tab: DocumentTab) -> None:
        session = tab.session
        if id(session) in self._watched:
            return
        self._watched.add(id(session))
        session.rebuilt.connect(lambda *_a: self.check())
        session.undo.cleanChanged.connect(lambda _clean: self.check())

    def check(self) -> None:
        """Tick the steps the current part now shows."""
        tab = self.main.current
        if tab is not None and self.isVisible():
            self._watch(tab)
            session = tab.session
            saved = session.path is not None and not session.is_dirty
            ctx = Context(session.document, session.report, saved)
            done = update(self.lesson, self.done(), ctx)
            if done != self.done():
                self.progress[self.lesson.key] = done
                save_progress(self.store, self.progress)
        self._show()

    def start_over(self) -> None:
        """Clear the ticks of the lesson shown."""
        self.progress.pop(self.lesson.key, None)
        save_progress(self.store, self.progress)
        self._show()

    def resume_later(self) -> None:
        """Close the window; the progress stays for next time."""
        save_progress(self.store, self.progress)
        self.store.setValue(_CURRENT, self.lesson.key)
        self.hide()
        self.main.status.setText(RESUMED)

    def open(self) -> None:
        """Show the window and check the part at once."""
        self.show()
        self.raise_()
        self.check()
