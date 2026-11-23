"""Sketch pictures (PHASE2_SPEC P2.9, DECISIONS D279).

A picture is an image placed in a sketch's plane. Its file is an embedded block
of the document (FDEF_SPEC 11); the sketch stores where the image sits. No Qt:
the user interface reads the image's pixel size and draws it.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import math
from dataclasses import dataclass
from typing import Any

Vec = tuple[float, float]
#: Image file types a picture accepts, by the block's ``format``.
FORMATS = {"png": "PNG", "jpeg": "JPEG", "bmp": "BMP"}


@dataclass
class Picture:
    """One picture in a sketch. ``origin`` is the lower left corner in sketch mm,
    before flips; ``angle`` turns the image about it (radians)."""

    id: str
    block: str
    origin: Vec = (0.0, 0.0)
    angle: float = 0.0
    width: float = 1.0
    height: float = 1.0
    flip_h: bool = False
    flip_v: bool = False
    #: 0 is opaque, 1 is invisible (the panel's transparency slider).
    transparency: float = 0.0
    lock_aspect: bool = True
    #: A colour shown see through, as #RRGGBB ("" for none), and how close a pixel's
    #: colour must be to count, 0 to 1 (TR116, D977). The image's own alpha always
    #: shows.
    clear_colour: str = ""
    clear_tolerance: float = 0.1

    def corners(self) -> list[Vec]:
        """Lower left, lower right, upper right, upper left, in sketch mm."""
        c, s = math.cos(self.angle), math.sin(self.angle)
        ox, oy = self.origin
        out = []
        for u, v in ((0.0, 0.0), (self.width, 0.0), (self.width, self.height), (0.0, self.height)):
            out.append((ox + u * c - v * s, oy + u * s + v * c))
        return out

    def local(self, p: Vec) -> Vec:
        """``p`` in the picture's own axes (mm from the origin along its sides)."""
        c, s = math.cos(self.angle), math.sin(self.angle)
        dx, dy = p[0] - self.origin[0], p[1] - self.origin[1]
        return dx * c + dy * s, -dx * s + dy * c

    def contains(self, p: Vec) -> bool:
        """True when ``p`` lies on the picture."""
        u, v = self.local(p)
        return 0.0 <= u <= self.width and 0.0 <= v <= self.height

    def scale_about(self, centre: Vec, factor: float) -> None:
        """Grow or shrink the picture by ``factor`` keeping ``centre`` in place."""
        ox, oy = self.origin
        self.origin = (centre[0] + (ox - centre[0]) * factor, centre[1] + (oy - centre[1]) * factor)
        self.width *= factor
        self.height *= factor


def scale_factor(a: Vec, b: Vec, true_length: float) -> float:
    """How much to scale so the line from ``a`` to ``b`` gets ``true_length``."""
    now = math.dist(a, b)
    if now < 1e-9 or true_length <= 0:
        raise ValueError("Drag the scale handles apart and type a length larger than zero.")
    return true_length / now


def block_id(data: bytes) -> str:
    """A block id from the image bytes, so the same image is stored once."""
    return "img" + hashlib.sha1(data, usedforsecurity=False).hexdigest()[:12]


def make_block(data: bytes, filename: str, fmt: str) -> dict[str, Any]:
    """An embedded image block (FDEF_SPEC 11)."""
    if fmt not in FORMATS:
        raise ValueError(f"Pictures can be PNG, JPEG or BMP files, not '{fmt}'.")
    packed = base64.b64encode(gzip.compress(data, mtime=0)).decode("ascii")
    return {
        "type": "image",
        "encoding": "gzip+base64",
        "format": fmt,
        "filename": filename,
        "data": packed,
    }


#: The most a sketch picture may unpack to (audit D12 item 3, D709).
MAX_PICTURE = 256 << 20


def block_bytes(block: dict[str, Any]) -> bytes:
    """The image file bytes of an embedded image block."""
    from fdcad.core.io.embedded import EmbeddedError, decode

    if block.get("type") != "image" or block.get("encoding") != "gzip+base64":
        raise ValueError("The picture's embedded block is not an image.")
    try:
        return decode(str(block.get("data", "")), MAX_PICTURE)
    except EmbeddedError as exc:
        raise ValueError(
            "The sketch picture is damaged or too large. Delete it and insert the image again."
        ) from exc


def new_picture(pid: str, block: str, width_px: int, height_px: int) -> Picture:
    """A picture at the sketch origin, one pixel to one millimetre (P2.9 item 1)."""
    if width_px <= 0 or height_px <= 0:
        raise ValueError("The image has no pixels.")
    return Picture(pid, block, (0.0, 0.0), 0.0, float(width_px), float(height_px))


def valid_colour(text: str) -> str | None:
    """``#RRGGBB`` in capitals for a typed colour (with or without #), "" for empty,
    None when it is not a colour."""
    text = text.strip().lstrip("#").upper()
    if not text:
        return ""
    if len(text) == 6 and all(c in "0123456789ABCDEF" for c in text):
        return "#" + text
    return None


def clear_mask(pixels: Any, colour: str, tolerance: float) -> Any:
    """For an (h, w, 3 or 4) array of R, G, B values, True where a pixel is within
    ``tolerance`` (0 to 1 of the largest colour distance) of ``colour``. numpy."""
    import numpy as np

    target = np.array([int(colour[i : i + 2], 16) for i in (1, 3, 5)], dtype=np.float32)
    rgb = np.asarray(pixels, dtype=np.float32)[..., :3]
    distance = np.sqrt(((rgb - target) ** 2).sum(axis=-1)) / (255.0 * np.sqrt(3.0))
    return distance <= max(0.0, min(1.0, tolerance))


def picture_to_json(p: Picture) -> dict[str, Any]:
    """A picture as stored in a sketch feature (FDEF_SPEC 6 item 7)."""
    return {
        "id": p.id,
        "embedded": p.block,
        "origin": [p.origin[0], p.origin[1]],
        "angle": p.angle,
        "width": p.width,
        "height": p.height,
        "flip_h": p.flip_h,
        "flip_v": p.flip_v,
        "transparency": p.transparency,
        "lock_aspect": p.lock_aspect,
        **(
            {"clear_colour": p.clear_colour, "clear_tolerance": p.clear_tolerance}
            if p.clear_colour
            else {}
        ),
    }


def picture_from_json(raw: dict[str, Any]) -> Picture:
    """Read a stored picture. Raises ValueError on bad data."""
    try:
        ox, oy = (float(v) for v in raw["origin"])
        pic = Picture(
            str(raw["id"]),
            str(raw["embedded"]),
            (ox, oy),
            float(raw.get("angle", 0.0)),
            float(raw["width"]),
            float(raw["height"]),
            bool(raw.get("flip_h", False)),
            bool(raw.get("flip_v", False)),
            float(raw.get("transparency", 0.0)),
            bool(raw.get("lock_aspect", True)),
            str(raw.get("clear_colour", "")),
            float(raw.get("clear_tolerance", 0.1)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"A sketch picture is damaged: {exc}.") from exc
    if pic.width <= 0 or pic.height <= 0 or not 0.0 <= pic.transparency <= 1.0:
        raise ValueError(f"Sketch picture {pic.id} has a bad size or transparency.")
    return pic


def referenced_blocks(features: list[Any]) -> set[str]:
    """Embedded block ids that the sketch pictures of ``features`` use."""
    out: set[str] = set()
    for f in features:
        for raw in (getattr(f, "data", {}) or {}).get("pictures", []) or []:
            out.add(str(raw.get("embedded")))
    return out
