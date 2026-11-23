"""What the fine smoothing samples of the 3D view may cost (D2820, PLAN 11.2).

The view's smoothed buffers live in graphics memory, which the process memory budgets
of ``test_budgets.py`` do not see: on built in graphics that memory is the machine's
own. So the rule that chooses the samples is itself a budget, and this test holds it.
The figures behind it were measured on a real view with
``tools/view_smoothing_measure.py``; ``tests/ui/test_view_proposals.py`` measures them
again when asked, on a screen.
"""

from __future__ import annotations

import pytest

from fdcad.ui.viewport import look

MIB = 1024 * 1024
GIB = 1024 * MIB
#: View sizes in device pixels: most of a Full HD, a QHD and a 4K screen.
VIEWS = {"full_hd": 1650 * 800, "qhd": 2290 * 1160, "4k": 3570 * 1880}


def test_the_baseline_machines_keep_four_samples() -> None:
    """PLAN 11.1: a laptop with built in graphics, whose driver tells no memory, and
    the Mac at 200 percent. Neither pays for the fine samples."""
    for pixels in VIEWS.values():
        assert look.msaa_samples(1.0, pixels, 0) == look.MSAA_SAMPLES
        assert look.msaa_samples(1.25, pixels, 0) == look.MSAA_SAMPLES
        assert look.msaa_samples(2.0, 4 * pixels, 8 * GIB) == look.MSAA_SAMPLES


@pytest.mark.parametrize(
    ("card", "limit_mib"), [(1 * GIB, 64), (2 * GIB, 128), (4 * GIB, 256), (8 * GIB, 512)]
)
def test_the_fine_samples_cost_a_view_a_sixteenth_of_the_card_at_most(
    card: int, limit_mib: int
) -> None:
    for pixels in range(50_000, 16_000_000, 50_000):
        samples = look.msaa_samples(1.0, pixels, card)
        extra = look.smoothing_memory(pixels, samples) - look.smoothing_memory(
            pixels, look.MSAA_SAMPLES
        )
        assert extra <= limit_mib * MIB


def test_what_a_view_costs_on_the_review_pc() -> None:
    """A 4 GiB card at 100 percent: a view of 1416 by 728 pixels takes 126 MiB with
    eight samples where four took 63, and a frame of the nut and bolt took 3.8 ms
    where it took 2.5 (measured, 2026-11-20)."""
    pixels = 1416 * 728
    assert look.msaa_samples(1.0, pixels, 4 * GIB) == 8
    assert look.smoothing_memory(pixels, 8) / MIB == pytest.approx(126, abs=1)
    assert look.smoothing_memory(pixels, 4) / MIB == pytest.approx(63, abs=1)
    # Ten such views open at once stay under a third of the card.
    assert 10 * look.smoothing_memory(pixels, 8) < 4 * GIB / 3
