"""Embedded data blocks of a `.fdef` file (FDEF_SPEC section 11).

Imported STEP files and meshes are stored inside the part, gzip compressed and
base64 encoded, so the part never reads the original file again. Blocks are
decoded only when a feature needs them (PLAN 11.4 item 4).
"""

from __future__ import annotations

import base64
import binascii
import gzip
import zlib
from typing import Any

from fdcad.core.document.model import Document

ENCODING = "gzip+base64"


class EmbeddedError(Exception):
    """An embedded block is missing or damaged. The message is shown to the user."""


def encode(data: bytes) -> str:
    """``data`` gzip compressed and base64 encoded.

    The gzip header has no time stamp, so the same bytes always give the same text
    and a saved part does not change when nothing changed.
    """
    return base64.b64encode(gzip.compress(data, compresslevel=6, mtime=0)).decode("ascii")


#: The most one embedded block may unpack to (audit D12 item 3, D709).
MAX_BLOCK = 1 << 30


def gunzip(data: bytes, limit: int) -> bytes:
    """``data`` gzip decompressed in steps, never past ``limit`` bytes.

    Raises ValueError when the data is damaged or unpacks to more than ``limit``,
    so a small block cannot fill the memory.
    """
    inflater = zlib.decompressobj(wbits=31)
    out = inflater.decompress(data, limit + 1)
    if len(out) > limit or inflater.unconsumed_tail:
        raise ValueError(f"unpacks to more than {limit} bytes")
    out += inflater.flush()
    if len(out) > limit:
        raise ValueError(f"unpacks to more than {limit} bytes")
    if not inflater.eof:
        raise ValueError("the compressed data ends early")
    return out


def decode(text: str, limit: int = MAX_BLOCK) -> bytes:
    """The bytes of an encoded block. Raises EmbeddedError when the text is damaged
    or unpacks to more than ``limit`` bytes."""
    try:
        packed = base64.b64decode(text.encode("ascii"), validate=True)
    except (binascii.Error, ValueError, UnicodeEncodeError) as exc:
        raise EmbeddedError("The embedded data is damaged. Import the file again.") from exc
    try:
        return gunzip(packed, limit)
    except (zlib.error, ValueError) as exc:
        if "unpacks to more" in str(exc):
            raise EmbeddedError(
                "The embedded data unpacks to more than FDCAD reads (1 GB). Import a smaller file."
            ) from exc
        raise EmbeddedError("The embedded data is damaged. Import the file again.") from exc


def new_block_id(doc: Document) -> str:
    """The next free block id: ``b1``, ``b2`` and so on. Ids are never reused in a file."""
    used = {int(k[1:]) for k in doc.embedded if k.startswith("b") and k[1:].isdigit()}
    return f"b{max(used, default=0) + 1}"


def make_block(kind: str, filename: str, data: bytes, **extra: Any) -> dict[str, Any]:
    """A block of ``kind`` (``step``, ``mesh`` or ``image``) holding ``data``.

    Keys follow FDEF_SPEC 11: ``type``, then extra keys such as ``format``, then
    ``encoding``, ``filename`` and ``data``.
    """
    block: dict[str, Any] = {"type": kind}
    block.update(extra)
    block.update({"encoding": ENCODING, "filename": filename, "data": encode(data)})
    return block


def block_of(doc: Document, ref: Any, kind: str, owner: str) -> dict[str, Any]:
    """The block a ``{"embedded": "b1"}`` reference points at. Raises EmbeddedError."""
    if not isinstance(ref, dict) or not isinstance(ref.get("embedded"), str):
        raise EmbeddedError(f"{owner} has no embedded file. Import the file again.")
    block = doc.embedded.get(ref["embedded"])
    if not isinstance(block, dict) or block.get("type") != kind:
        raise EmbeddedError(
            f"{owner}: the embedded file {ref['embedded']} is missing. Import the file again."
        )
    if block.get("encoding") != ENCODING or not isinstance(block.get("data"), str):
        raise EmbeddedError(f"{owner}: the embedded file is damaged. Import the file again.")
    return block


def block_bytes(doc: Document, ref: Any, kind: str, owner: str) -> bytes:
    """The decoded bytes of the block ``ref`` points at. Raises EmbeddedError."""
    block = block_of(doc, ref, kind, owner)
    try:
        return decode(block["data"])
    except EmbeddedError as exc:
        raise EmbeddedError(
            f"{owner}: the embedded file is damaged. Import the file again."
        ) from exc
