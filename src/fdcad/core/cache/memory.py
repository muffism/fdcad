"""In memory cache of feature results, least recently used first out (PLAN 11.4 item 1)."""

from __future__ import annotations

import ctypes
import os
import sys
from collections import OrderedDict
from typing import TYPE_CHECKING

from fdcad.core.naming.names import faces_of

if TYPE_CHECKING:
    from fdcad.core.features.base import FeatureResult
    from fdcad.core.naming.names import NamedShape

#: Rough memory per face of a cached solid, including its naming entry (DECISIONS D71).
BYTES_PER_FACE = 16 * 1024
_TWO_GB = 2 * 1024**3


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def system_memory() -> int:
    """Physical memory in bytes, or 8 GB when it cannot be read."""
    try:
        if sys.platform == "win32":
            status = _MemoryStatus()
            status.dwLength = ctypes.sizeof(_MemoryStatus)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.ullTotalPhys)
        else:
            return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))
    except (AttributeError, OSError, ValueError):
        pass
    return 8 * 1024**3


def default_limit() -> int:
    """25 percent of system memory or 2 GB, whichever is smaller (DECISIONS D44)."""
    return min(system_memory() // 4, _TWO_GB)


def estimate_size(result: FeatureResult, before: NamedShape | None = None) -> int:
    """Approximate memory held by a result.

    With ``before``, the part the feature started from, only the faces the feature
    made or changed are counted (D1065). The kernel shares every other face between
    the two parts, so they take no memory twice. Counting all faces of the part for
    every feature charged a part of 3000 faces 50 MB per feature: at 165 features the
    2 GB limit was reached, the oldest results were dropped first, and those are the
    ones every later feature is built on, so each edit rebuilt the whole part.
    """
    if result.body is None:
        return 4 * 1024
    faces = faces_of(result.body.shape)
    if before is None:
        return 4 * 1024 + BYTES_PER_FACE * len(faces)
    if before.shape.IsSame(result.body.shape):
        return 4 * 1024
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp

    from fdcad.core.occ import ShapeMap

    old = ShapeMap()
    TopExp.MapShapes_s(before.shape, TopAbs_FACE, old)
    new = sum(1 for face in faces if not old.Contains(face))
    return 4 * 1024 + BYTES_PER_FACE * new


class ResultCache:
    """Feature results by key, with a byte limit."""

    def __init__(self, limit: int | None = None) -> None:
        self.limit = default_limit() if limit is None else limit
        self._items: OrderedDict[str, tuple[FeatureResult, int]] = OrderedDict()
        self.size = 0

    def get(self, key: str) -> FeatureResult | None:
        """The cached result for ``key``, marked as recently used."""
        item = self._items.get(key)
        if item is None:
            return None
        self._items.move_to_end(key)
        return item[0]

    def put(
        self,
        key: str,
        result: FeatureResult,
        before: NamedShape | None = None,
        size: int | None = None,
    ) -> None:
        """Store a result, then drop the oldest entries until under the limit.
        ``before`` is the part the feature started from (see ``estimate_size``);
        ``size``, when known (a stored result, D2600), is used instead."""
        if key in self._items:
            self.size -= self._items.pop(key)[1]
        if size is None:
            size = estimate_size(result, before)
        self._items[key] = (result, size)
        self.size += size
        while self.size > self.limit and len(self._items) > 1:
            _, (_, old_size) = self._items.popitem(last=False)
            self.size -= old_size

    def clear(self) -> None:
        """Free every cached result (PLAN 11.4 item 6)."""
        self._items.clear()
        self.size = 0

    def __len__(self) -> int:
        return len(self._items)
