"""First run lessons that check the result (TR291 item 2, D2505)."""

from __future__ import annotations

from fdcad.core.document.model import new_document
from fdcad.core.lessons import BY_KEY, LESSONS, Context, Lesson, Step, next_step, update
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, rect


def _ctx(doc, saved: bool = False) -> Context:  # type: ignore[no-untyped-def]
    return Context(doc, RebuildEngine().rebuild(doc), saved)


def test_first_part_steps_tick_from_the_part() -> None:
    lesson = BY_KEY["first_part"]
    doc = new_document()
    assert update(lesson, set(), _ctx(doc)) == set()
    s = Sketch()
    rect(s, 0, 0, 40, 20)
    sk = add_sketch(doc, s, {"feature": "f2"})
    done = update(lesson, set(), _ctx(doc))
    assert done == {0}  # a rectangle, not fully defined
    assert next_step(lesson, done) == 1
    add_extrude(doc, sk, 5.0)
    done = update(lesson, done, _ctx(doc))
    assert done == {0, 2}
    done = update(lesson, done, _ctx(doc, saved=True))
    assert 4 in done


def test_a_cut_is_not_a_solid_and_ticked_steps_stay() -> None:
    lesson = BY_KEY["holes_patterns"]
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 40, 20)
    sk = add_sketch(doc, s, {"feature": "f2"})
    add_extrude(doc, sk, 5.0)
    s2 = Sketch()
    rect(s2, 10, 5, 20, 15)
    sk2 = add_sketch(doc, s2, {"feature": "f2"})
    add_extrude(doc, sk2, 5.0, operation="cut")
    done = update(lesson, set(), _ctx(doc))
    assert done == {0, 1}
    assert update(lesson, done, Context(new_document())) == done  # stays ticked


def test_a_failing_check_does_not_tick() -> None:
    def broken(_ctx: Context) -> bool:
        raise RuntimeError("boom")

    lesson = Lesson("x", "X", (Step("a", broken), Step("b", lambda _c: True)))
    assert update(lesson, set(), Context(new_document())) == {1}
    assert next_step(lesson, {0, 1}) is None
    assert all(lesson.steps for lesson in LESSONS)
