"""Explode Text (TR121 item 1, D1713): the glyph outlines are worked out off the UI
thread (CLAUDE.md rule 2); the curves replace the text in one sketch undo step."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from fdcad.core.kernel import kernel_job
from fdcad.core.sketch.model import Sketch
from fdcad.ui import strings
from fdcad.ui.background import start_job

if TYPE_CHECKING:
    from fdcad.ui.sketch_tools.canvas import SketchCanvas


class _Signals(QObject):
    done = Signal(object)


class ExplodeJob(QRunnable):
    """Works out the curve pieces of every text item of a sketch copy."""

    def __init__(self, sketch: Sketch) -> None:
        super().__init__()
        self.sketch = sketch
        self.signals = _Signals()

    @kernel_job
    def run(self) -> None:
        from fdcad.core.sketch.text import TextError
        from fdcad.core.sketch.text_explode import explode_pieces

        out: dict[str, Any] = {}
        for t in self.sketch.texts:
            try:
                out[t.id] = explode_pieces(self.sketch, t.id)
            except (TextError, ValueError) as exc:
                out[t.id] = str(exc)
            except Exception:  # a kernel failure leaves that text as it is
                out[t.id] = strings.TEXT_EXPLODE_FAILED
        self.signals.done.emit(out)


_RUNNING: set[ExplodeJob] = set()


def explode_texts(canvas: SketchCanvas) -> ExplodeJob | None:
    """Start exploding every text item of the open sketch; the curves arrive later."""
    sketch = canvas.edit.sketch
    if not sketch.texts:
        return None
    job = ExplodeJob(copy.deepcopy(sketch))
    ids = [t.id for t in sketch.texts]

    def done(found: dict[str, Any]) -> None:
        _RUNNING.discard(job)
        from fdcad.core.sketch.text_explode import apply_explode

        sk = canvas.edit.sketch
        good = {k: v for k, v in found.items() if isinstance(v, list) and k in ids}
        failed = [v for v in found.values() if isinstance(v, str)]
        if good and all(any(t.id == k for t in sk.texts) for k in good):

            def change() -> None:
                for tid, pieces in good.items():
                    apply_explode(canvas.edit.sketch, tid, pieces)

            canvas.run(change)
        note = failed[0] if failed else strings.TEXT_EXPLODED.format(count=len(good))
        canvas.status_message.emit(note)

    job.signals.done.connect(done)
    _RUNNING.add(job)
    start_job(QThreadPool.globalInstance(), job)
    canvas.status_message.emit(strings.TEXT_EXPLODING)
    return job
