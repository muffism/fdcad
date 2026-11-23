"""Process memory use, for the rebuild statistics panel and the memory budgets (PLAN 11)."""

from __future__ import annotations

import ctypes
import sys


def process_memory() -> int:
    """Memory the app uses now, in bytes (on macOS, the highest use so far). 0 if unknown."""
    if sys.platform == "win32":
        return _windows()
    try:
        import resource

        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except (ImportError, OSError):
        return 0
    return int(peak if sys.platform == "darwin" else peak * 1024)


def private_memory() -> int:
    """Memory the app allocated itself, in bytes, without mapped library files.

    Linux (``RssAnon``) and macOS (the footprint, the figure Activity Monitor shows
    as Memory); 0 on Windows. On both, resident memory also counts the pages of
    library files the kernel library, VTK and Qt map, far more than on Windows, so
    the startup memory budget test uses this value there (D491, D2711).
    """
    if sys.platform == "darwin":
        return _mac_footprint()
    if not sys.platform.startswith("linux"):
        return 0
    try:
        with open("/proc/self/status", encoding="ascii") as status:
            for line in status:
                if line.startswith("RssAnon:"):
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        return 0
    return 0


class _MacUsage(ctypes.Structure):
    """``rusage_info_v0`` of macOS's libproc (``sys/resource.h``)."""

    _fields_ = [  # ctypes needs a plain list
        ("ri_uuid", ctypes.c_uint8 * 16),
        ("ri_user_time", ctypes.c_uint64),
        ("ri_system_time", ctypes.c_uint64),
        ("ri_pkg_idle_wkups", ctypes.c_uint64),
        ("ri_interrupt_wkups", ctypes.c_uint64),
        ("ri_pageins", ctypes.c_uint64),
        ("ri_wired_size", ctypes.c_uint64),
        ("ri_resident_size", ctypes.c_uint64),
        ("ri_phys_footprint", ctypes.c_uint64),
        ("ri_proc_start_abstime", ctypes.c_uint64),
        ("ri_proc_exit_abstime", ctypes.c_uint64),
    ]


def _mac_footprint() -> int:
    """The process's physical footprint from ``proc_pid_rusage``, or 0 if it cannot be read."""
    import os

    usage = _MacUsage()
    try:
        libproc = ctypes.CDLL("/usr/lib/libproc.dylib")
        failed = libproc.proc_pid_rusage(os.getpid(), 0, ctypes.byref(usage))  # 0: RUSAGE_INFO_V0
    except (AttributeError, OSError):
        return 0
    return 0 if failed else int(usage.ri_phys_footprint)


def _windows() -> int:
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [  # ctypes needs a plain list
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = Counters()
    counters.cb = ctypes.sizeof(Counters)
    try:
        windll = getattr(ctypes, "windll")  # noqa: B009  # only exists on Windows
        current = windll.kernel32.GetCurrentProcess
        current.restype = wintypes.HANDLE
        info = windll.psapi.GetProcessMemoryInfo
        info.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        info.restype = wintypes.BOOL
        ok = info(current(), ctypes.byref(counters), counters.cb)
    except (AttributeError, OSError):
        return 0
    return int(counters.WorkingSetSize) if ok else 0
