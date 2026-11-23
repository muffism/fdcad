"""The rebuild cache counts what a feature added, not the whole part (D1065).

Found on a gearbox of 318 features (2026-11-12): past about 165 features every edit
rebuilt the whole part, 100 seconds each time. Each kept result was charged for every
face of the part, though the kernel shares all but the changed ones between results.
The limit was reached, the oldest results went first, and the oldest are the ones
every later feature is built on.
"""

from __future__ import annotations

from fdcad.core.cache.memory import BYTES_PER_FACE, ResultCache, estimate_size
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import Circle, Sketch
from tests.core.features.test_features import add_extrude, add_sketch, plate
from tests.core.features.test_hole import face_ref


def _plate_with_holes(count: int):  # type: ignore[no-untyped-def]
    """The plate with ``count`` holes, one cut feature each."""
    doc, ext = plate()
    for k in range(count):
        s = Sketch()
        c = s.add_point(5 + 4 * (k % 10), 5 + 6 * (k // 10))
        eid = s.new_id()
        s.entities[eid] = Circle(eid, c, 1.0)
        sk = add_sketch(doc, s, face_ref(doc, ext, "cap/end"))
        add_extrude(doc, sk, 10.0, operation="cut", reverse=True)
    return doc


def test_a_result_is_charged_for_the_faces_it_made() -> None:
    doc = _plate_with_holes(2)
    report = RebuildEngine().rebuild(doc)
    cuts = [f for f in doc.features if f.type == "extrude"][1:]
    before = report.results[cuts[0].id]
    after = report.results[cuts[1].id]
    whole = estimate_size(after)
    added = estimate_size(after, before.body)
    assert whole == 4 * 1024 + BYTES_PER_FACE * 8  # six faces of the plate, two holes
    # The second hole: its own wall, and the top and bottom faces it changed.
    assert added == 4 * 1024 + BYTES_PER_FACE * 3
    assert estimate_size(before, before.body) == 4 * 1024  # nothing new


def test_a_long_tree_stays_in_the_cache_under_a_limit_the_old_count_broke() -> None:
    """Thirty holes. Counted whole, the results need about 10 MB and a 3 MB limit
    dropped the first features, so nothing after them could be reused. Counted by
    what each added they need under 2 MB, and a second rebuild builds nothing."""
    doc = _plate_with_holes(30)
    cache = ResultCache(limit=3 * 1024 * 1024)
    engine = RebuildEngine(cache)
    engine.rebuild(doc)
    assert cache.size < 2 * 1024 * 1024
    again = engine.rebuild(doc)
    assert again.rebuilt == [], again.rebuilt[:5]
    assert len(again.reused) >= 60


def test_the_engine_uses_the_cache_it_is_given() -> None:
    """An empty cache is falsy, and ``cache or ResultCache()`` made a new one: a cache
    passed in with its own limit was never used (D1065)."""
    cache = ResultCache(limit=1024 * 1024)
    assert RebuildEngine(cache).cache is cache
