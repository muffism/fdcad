"""The features that made one body (TR153 item 2, D972)."""

from __future__ import annotations

from fdcad.core.body_history import body_history
from tests.core.features.test_multibody import two_blocks


def test_each_block_has_its_own_history() -> None:
    doc, first, second, body = two_blocks(gap=5.0)
    histories = [body_history(doc, body, i) for i in range(2)]
    sketches = {f.id for f in doc.features if f.type == "sketch"}
    flat = [set(h) for h in histories]
    assert {first, second} == {next(iter(h - sketches)) for h in flat}
    assert all(len(h & sketches) == 1 for h in flat)  # each block's own sketch
    assert body_history(doc, body, 5) == []
