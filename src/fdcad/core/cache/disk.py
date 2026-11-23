"""Local solid cache on disk (FDEF_SPEC section 13, DECISIONS D44).

Stores the finished part of a document in OpenCascade's binary BRep format,
with its face names and feature states, so an unchanged file opens without a
rebuild. A missing or damaged entry is never an error: the part is rebuilt.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from OCP.BinTools import BinTools
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.document.model import Document
from fdcad.core.io.fdef import to_json_data
from fdcad.core.naming.names import NamedShape, faces_of

if TYPE_CHECKING:
    from fdcad.core.features.base import FeatureResult
    from fdcad.core.rebuild.engine import RebuildReport

#: Size limit of the whole cache folder (FDEF_SPEC 13.4).
CACHE_LIMIT = 2 * 1024**3
_FORMAT = 1
_GEOMETRY_KEYS = (
    "units",
    "variables",
    "configurations",
    "features",
    "graphs",
    "rollback",
    "embedded",
)


def cache_dir() -> Path:
    """The cache folder: ``FDCAD_CACHE_DIR`` if set, else the platform cache location."""
    override = os.environ.get("FDCAD_CACHE_DIR")
    if override:
        return Path(override)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "FDCAD"
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "FDCAD" / "Cache"


def document_key(doc: Document) -> str:
    """SHA256 of the canonical JSON of everything that affects geometry (FDEF_SPEC 13.2)."""
    data = to_json_data(doc)
    payload = {k: data.get(k) for k in _GEOMETRY_KEYS}
    if "graphs" in data:  # parts without graphs keep their old keys (FDEF_SPEC 13.2)
        payload["graphs"] = data["graphs"]
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class CachedPart:
    """A part read back from the cache."""

    body: NamedShape | None
    states: dict[str, dict[str, Any]]


def _write_atomic(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def store(
    key: str,
    body: NamedShape | None,
    states: dict[str, dict[str, Any]],
    results: dict[str, FeatureResult] | None = None,
) -> None:
    """Save a finished part under ``key``, and with ``results`` each feature's result
    (``history``, D1097). Failures are ignored: the cache is optional."""
    folder = cache_dir()
    if results:
        import contextlib

        from fdcad.core.cache.history import store_history

        with contextlib.suppress(OSError, RuntimeError, ValueError):
            store_history(folder, key, results)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        names: list[list[Any]] = []
        if body is not None:
            stream = io.BytesIO()
            BinTools.Write_s(body.shape, stream)
            _write_atomic(folder / f"{key}.brep", stream.getvalue())
            # A face map gives each face's index at once; the nested search grew with
            # the square of the face count (1.2 s at 2000 faces, audit D3 item 2).
            from fdcad.core.occ import ShapeMap

            index = ShapeMap()
            for f in faces_of(body.shape):
                index.Add(f)
            for name, face in body.faces:
                k = index.FindIndex(face)
                if k:
                    names.append([name, k - 1])
        meta = {"format": _FORMAT, "has_body": body is not None, "names": names, "states": states}
        _write_atomic(folder / f"{key}.json", json.dumps(meta).encode("utf-8"))
        prune(folder)
    except OSError:
        return


def load(key: str) -> CachedPart | None:
    """Read the part saved under ``key``, or None when it is missing or damaged."""
    folder = cache_dir()
    try:
        meta = json.loads((folder / f"{key}.json").read_text(encoding="utf-8"))
        if meta.get("format") != _FORMAT:
            return None
        body = None
        if meta.get("has_body"):
            shape = TopoDS_Shape()
            BinTools.Read_s(shape, io.BytesIO((folder / f"{key}.brep").read_bytes()))
            if shape.IsNull():
                return None
            faces = faces_of(shape)
            body = NamedShape(shape, [(str(n), faces[int(i)]) for n, i in meta["names"]])
        os.utime(folder / f"{key}.json")  # mark as recently used
        return CachedPart(body, dict(meta.get("states", {})))
    except (OSError, ValueError, KeyError, IndexError, TypeError, RuntimeError):
        return None


def cached_report(doc: Document, part: CachedPart) -> RebuildReport:
    """A rebuild report made from a cached part, shown while the real rebuild runs.

    It has each feature's state and messages, and the finished part on the last
    feature that has one. Sketch and plane details come with the real rebuild.
    """
    from fdcad.core.features.base import FeatureResult, FeatureState, Issue
    from fdcad.core.features.solids import solids
    from fdcad.core.rebuild.engine import RebuildReport

    results: dict[str, FeatureResult] = {}
    for feature in doc.features:
        raw = part.states.get(feature.id)
        if raw is None:
            continue
        try:
            state = FeatureState(raw.get("state", "ok"))
        except ValueError:
            state = FeatureState.OK
        issues = (
            [Issue(state, str(m)) for m in raw.get("messages", [])]
            if state is not FeatureState.OK
            else []
        )
        results[feature.id] = FeatureResult(body=None, issues=issues)
    if part.body is not None and results:
        last = next(reversed(results))
        results[last].body = part.body
    report = RebuildReport(results=results)
    if part.body is not None:
        from fdcad.core.body_groups import identical_groups

        bodies = solids(part.body.shape)
        report.body_count = len(bodies)
        report.body_groups = identical_groups(bodies)  # TR308 (D958)
    return report


def prune(folder: Path | None = None, limit: int = CACHE_LIMIT) -> None:
    """Delete the least recently used entries until the folder is under ``limit``."""
    folder = folder or cache_dir()
    try:
        entries = sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime)
        total = sum(p.stat().st_size for p in folder.iterdir() if p.is_file())
        for meta in entries:
            if total <= limit:
                break
            for path in (meta, meta.with_suffix(".brep")):
                if path.exists():
                    total -= path.stat().st_size
                    path.unlink()
    except OSError:
        return


def clear() -> None:
    """Delete every cache entry (preferences: clear cache)."""
    folder = cache_dir()
    if not folder.exists():
        return
    for path in folder.iterdir():
        if path.suffix in (".brep", ".json"):
            path.unlink(missing_ok=True)
