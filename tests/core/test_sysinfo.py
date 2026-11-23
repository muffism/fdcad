"""Process memory readers (PLAN 11, D491, D2711)."""

from __future__ import annotations

import sys

import pytest

from fdcad import sysinfo


def test_process_memory_is_read() -> None:
    assert sysinfo.process_memory() > 0


@pytest.mark.skipif(sys.platform != "darwin", reason="the footprint is a macOS figure")
def test_a_mac_reports_its_footprint() -> None:
    """D2711: the startup budget counts the footprint on a Mac, so it must be read."""
    held = bytearray(64 * 1024 * 1024)  # touched pages the app allocated itself
    footprint = sysinfo.private_memory()
    assert footprint > len(held)
    # The footprint leaves out mapped library files, so it is not above the peak in use.
    assert footprint <= sysinfo.process_memory()


def test_windows_has_no_private_figure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    assert sysinfo.private_memory() == 0
