"""Free disk space and memory, for the low space warnings (TR220, D968).

Plain standard library: ``shutil.disk_usage`` for disks, and on Windows the
``GlobalMemoryStatusEx`` call through ctypes for memory. Where free memory cannot
be read (other systems), the memory check says nothing rather than guess. No Qt.
"""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

#: Below these the app warns (bytes).
LOW_DISK = 500 * 1024 * 1024
LOW_MEMORY = 300 * 1024 * 1024


def free_disk(path: str | Path) -> int | None:
    """Free bytes on the disk that holds ``path`` (or its nearest existing folder)."""
    place = Path(path)
    while not place.exists() and place.parent != place:
        place = place.parent
    try:
        return int(shutil.disk_usage(place).free)
    except OSError:
        return None


def free_memory(platform: str = sys.platform) -> int | None:
    """Bytes of memory free for programs, or None where it cannot be read."""
    if platform != "win32":
        return None
    try:
        import ctypes

        class _Status(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = _Status()
        status.dwLength = ctypes.sizeof(_Status)
        kernel = getattr(ctypes, "windll").kernel32  # noqa: B009  (Windows only)
        if not kernel.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return int(status.ullAvailPhys)
    except Exception:  # the warning is a nicety; never fail because of it
        return None


def disk_of(path: str | Path) -> str:
    """A name for the disk that holds ``path``: the same text for two paths on one disk.

    A path with a drive letter gives the drive. Other paths (macOS has no drive
    letters) give the device of the nearest folder that exists, so two folders on
    one volume count once and a second volume counts by itself (D2707).
    """
    place = Path(path)
    if place.drive:
        return place.anchor
    while not place.exists() and place.parent != place:
        place = place.parent
    try:
        return f"device {place.stat().st_dev}"
    except OSError:
        return str(path)


@dataclass(frozen=True)
class Shortage:
    """What is low: "disk" or "memory", with the free bytes and where (for a disk)."""

    kind: str
    free: int
    where: str = ""


def shortages(
    folders: list[Path],
    disk_free: object = free_disk,
    memory_free: object = free_memory,
    low_disk: int = LOW_DISK,
    low_memory: int = LOW_MEMORY,
) -> list[Shortage]:
    """The low resources: each folder's disk once, then memory. The two readers can
    be replaced for tests."""
    out: list[Shortage] = []
    seen: set[str] = set()
    for folder in folders:
        free = disk_free(folder)  # type: ignore[operator]
        disk = disk_of(folder)
        if free is not None and free < low_disk and disk not in seen:
            seen.add(disk)
            out.append(Shortage("disk", int(free), str(folder)))
    memory = memory_free()  # type: ignore[operator]
    if memory is not None and memory < low_memory:
        out.append(Shortage("memory", int(memory)))
    return out
