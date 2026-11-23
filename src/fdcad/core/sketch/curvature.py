"""Curvature combs of sketch splines (PHASE2_SPEC P2.8 item 10, DECISIONS D514).

A comb shows how sharply a spline bends along its length: at each sample a
tooth stands out from the curve along its normal, as long as the curvature
there times a scale, on the outside of the bend. The tips are joined into a
line. Whole array numpy maths over the spline's cubic Bezier pieces. No kernel,
no Qt.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from fdcad.core.sketch.freeform import bezier_poles
from fdcad.core.sketch.model import Sketch, Spline

#: Samples along a spline for its comb (about this many, whatever its pieces).
COMB_SAMPLES = 60
#: The longest tooth is this share of the spline's size (the diagonal of its box).
COMB_SHARE = 0.2
#: Below this a curvature or a speed counts as zero.
_EPS = 1e-12
#: A curvature below this share of the spline's largest is rounding noise.
_NOISE = 1e-9


@dataclass
class Comb:
    """A spline's comb: sample points on the curve, the tooth tips, and the signed
    curvature (1/mm, positive turning left) at each sample."""

    bases: NDArray[np.float64]
    tips: NDArray[np.float64]
    curvature: NDArray[np.float64]


def _weights(t: NDArray[np.float64]) -> tuple[NDArray[np.float64], ...]:
    """Cubic Bezier weights for position, first and second derivative at ``t``."""
    u = 1.0 - t
    pos = np.stack([u**3, 3 * u * u * t, 3 * u * t * t, t**3], axis=1)
    d1 = np.stack([-3 * u * u, 3 * u * u - 6 * u * t, 6 * u * t - 3 * t * t, 3 * t * t], axis=1)
    d2 = np.stack([6 * u, -12 * u + 6 * t, 6 * u - 12 * t, 6 * t], axis=1)
    return pos, d1, d2


def _joined(per_piece: NDArray[np.float64]) -> NDArray[np.float64]:
    """Samples of all pieces in order, without repeating the shared joins."""
    return np.concatenate([per_piece[0], per_piece[1:, 1:].reshape(-1, 2)])


def curvature_comb(
    sketch: Sketch,
    spline: Spline,
    samples: int = COMB_SAMPLES,
    scale: float | None = None,
) -> Comb:
    """The comb of ``spline``. ``scale`` is the tooth length per unit curvature (mm
    squared); by default the longest tooth is COMB_SHARE of the spline's size."""
    poles = np.asarray(bezier_poles(sketch, spline), dtype=np.float64)
    pieces = (len(poles) - 1) // 3
    if pieces < 1:
        empty = np.zeros((0, 2))
        return Comb(empty, empty, np.zeros(0))
    per = max(samples // pieces, 2)
    t = np.linspace(0.0, 1.0, per + 1)
    index = 3 * np.arange(pieces)[:, None] + np.arange(4)[None, :]
    ctrl = poles[index]  # pieces, 4, 2
    w_pos, w_d1, w_d2 = _weights(t)
    pos = _joined(np.einsum("mk,pkd->pmd", w_pos, ctrl))
    d1 = _joined(np.einsum("mk,pkd->pmd", w_d1, ctrl))
    d2 = _joined(np.einsum("mk,pkd->pmd", w_d2, ctrl))
    speed = np.hypot(d1[:, 0], d1[:, 1])
    moving = speed > _EPS
    safe = np.where(moving, speed, 1.0)
    cross = d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]
    curvature = np.where(moving, cross / safe**3, 0.0)
    normal = np.where(moving[:, None], np.stack([-d1[:, 1], d1[:, 0]], axis=1) / safe[:, None], 0.0)
    if scale is None:
        size = float(np.hypot(*(pos.max(axis=0) - pos.min(axis=0))))
        peak = float(np.abs(curvature).max())
        scale = COMB_SHARE * size / peak if peak > _EPS else 0.0
    # The centre of the bend is along +normal for positive curvature; teeth go outside.
    tips = pos - normal * (curvature * scale)[:, None]
    return Comb(pos, tips, curvature)


@dataclass
class SplineAids:
    """Display aids for a spline (TR44, D900): its control polygon, where its bend
    changes side (inflections) and its tightest point with that radius."""

    polygon: NDArray[np.float64]
    inflections: NDArray[np.float64]
    tightest: tuple[float, float] | None
    radius: float | None


def spline_aids(sketch: Sketch, spline: Spline, samples: int = 4 * COMB_SAMPLES) -> SplineAids:
    """The control polygon, the inflection points and the point of smallest radius."""
    poles = np.asarray(bezier_poles(sketch, spline), dtype=np.float64)
    comb = curvature_comb(sketch, spline, samples)
    pos = comb.bases
    # A sample that sits on a change of side has a curvature of zero, but rounding
    # can leave about 1e-18 with either sign, which differs between processors.
    # Such a sample counts as zero, so every platform marks the same points (D2706).
    k = comb.curvature
    if len(k):
        k = np.where(np.abs(k) < _NOISE * float(np.abs(k).max()), 0.0, k)
    inflections = np.zeros((0, 2))
    if len(k) > 1:
        flips = np.nonzero((k[:-1] * k[1:] < 0) & (np.abs(k[:-1]) + np.abs(k[1:]) > _EPS))[0]
        if len(flips):
            a, b = np.abs(k[flips]), np.abs(k[flips + 1])
            share = (a / (a + b))[:, None]
            inflections = pos[flips] + (pos[flips + 1] - pos[flips]) * share
    tightest, radius = None, None
    if len(k) and float(np.abs(k).max()) > _EPS:
        i = int(np.argmax(np.abs(k)))
        tightest = (float(pos[i, 0]), float(pos[i, 1]))
        radius = 1.0 / float(abs(k[i]))
    return SplineAids(poles, inflections, tightest, radius)


__all__ = ["COMB_SAMPLES", "COMB_SHARE", "Comb", "SplineAids", "curvature_comb", "spline_aids"]
