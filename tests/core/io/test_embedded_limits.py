"""Embedded blocks and sketch pictures unpack with a size limit (audit D12 item 3, D709)."""

from __future__ import annotations

import base64
import gzip

import pytest

from fdcad.core.io.embedded import EmbeddedError, decode, encode, gunzip
from fdcad.core.sketch.picture import block_bytes


def test_round_trip_and_damage() -> None:
    assert decode(encode(b"hello")) == b"hello"
    with pytest.raises(EmbeddedError, match="damaged"):
        decode("not base64!")
    with pytest.raises(EmbeddedError, match="damaged"):
        decode(base64.b64encode(gzip.compress(b"x" * 100)[:-8]).decode())  # cut short


def test_a_small_block_that_unpacks_huge_is_refused() -> None:
    bomb = encode(b"\0" * 5_000_000)  # about 5 KB of text
    assert len(bomb) < 20_000
    with pytest.raises(EmbeddedError, match="more than FDCAD reads"):
        decode(bomb, limit=1_000_000)
    with pytest.raises(ValueError, match="unpacks to more"):
        gunzip(gzip.compress(b"\0" * 2_000), 1_000)


def test_picture_blocks_use_the_limit_and_say_what_to_do(monkeypatch: pytest.MonkeyPatch) -> None:
    import fdcad.core.sketch.picture as pic

    block = {"type": "image", "encoding": "gzip+base64", "data": encode(b"\0" * 10_000)}
    assert len(block_bytes(block)) == 10_000
    monkeypatch.setattr(pic, "MAX_PICTURE", 1_000)
    with pytest.raises(ValueError, match="insert the image again"):
        block_bytes(block)
    with pytest.raises(ValueError, match="insert the image again"):
        block_bytes({**block, "data": "%%%"})  # was a raw base64 error
