"""Save the 3D view as a PNG (TUTORIAL_REVIEW_SPEC TR24, D689).

Without the background, the view is drawn twice, once on black and once on
white; each pixel's opacity is what the two disagree by, so smooth edges keep
their soft outline. Whole array numpy work only (CLAUDE.md 5A rule 2).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from PySide6.QtGui import QImage

#: Largest side of a saved image, in pixels.
MAX_SIDE = 8000


def qimage_rgb(image: QImage) -> NDArray[np.uint8]:
    """An image as a height by width by 3 array of 8 bit RGB."""
    img = image.convertToFormat(QImage.Format.Format_RGB888)
    w, h, row = img.width(), img.height(), img.bytesPerLine()
    raw = np.frombuffer(img.constBits(), dtype=np.uint8, count=row * h)
    return raw.reshape(h, row)[:, : w * 3].reshape(h, w, 3).copy()


def without_background(
    on_black: NDArray[np.uint8], on_white: NDArray[np.uint8]
) -> NDArray[np.uint8]:
    """RGBA from the same view drawn on black and on white.

    Where the two agree the pixel is opaque; where white shows through, the
    difference gives how much (alpha = 1 - (white - black)). The colour is the
    black picture divided by alpha.
    """
    black = on_black.astype(np.float32)
    white = on_white.astype(np.float32)
    alpha = 255.0 - np.clip((white - black).mean(axis=2), 0.0, 255.0)
    safe = np.maximum(alpha, 1.0)[..., None]
    colour = np.clip(black * 255.0 / safe, 0.0, 255.0)
    out = np.empty((*on_black.shape[:2], 4), dtype=np.uint8)
    out[..., :3] = np.rint(colour).astype(np.uint8)
    out[..., 3] = np.rint(alpha).astype(np.uint8)
    out[alpha < 0.5, :3] = 0
    return out


def rgba_image(pixels: NDArray[np.uint8]) -> QImage:
    """A QImage that owns a copy of an RGBA array."""
    h, w = pixels.shape[:2]
    data = np.ascontiguousarray(pixels)
    image = QImage(data.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
    return image.copy()


def checked_size(width: int, height: int) -> str:
    """Why a size cannot be saved, or "" when it can."""
    if width < 1 or height < 1:
        return "Type a width and height of 1 pixel or more."
    if width > MAX_SIDE or height > MAX_SIDE:
        return f"Type a width and height of {MAX_SIDE} pixels or less."
    return ""
