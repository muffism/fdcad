"""Each feature's result on disk, beside the finished part (PLAN 11.3 item 2, D1097).

The local solid cache (FDEF_SPEC 13) holds the finished part, so a saved part shows at
once; the rebuild behind it still built every feature again (40 s for the bike frame).
This file holds the results of the features that make solids, so that rebuild finds them
in the engine's memory cache and only sketches, planes and other quick features are
built again (2.6 s for the bike frame).

One file per part: the bodies go in one BinTools compound, so the faces the steps share
are written once (1.7 MB for the 103 features of the bike frame). Results are keyed by
the engine's feature keys, which hash the feature and everything it is built on. The
file is tied to the build of FDCAD that wrote it (``code_stamp``): a result of older
code is never reused, so a fixed feature is always built again.

A result is stored only when all of it can be written: its body and names, its issues
with their fixes, its cosmetic threads and its display extras (plain values, tuples,
lists, dicts and shapes). Sketches, planes and reference geometry are left to the
rebuild. Kernel work: rebuild thread or a background thread only.

Format 2 (D2600), for parts of thousands of faces: on the 768 feature machine bed the
face names of format 1 (one JSON pair per name and result, 1.4 million) took 7.6 s to
turn back into faces and the memory cache 6.4 s to size the results, all in the app
while the rebuild helper (``rebuild/remote.py``) had done the real work. Names are now
two arrays of numbers (name number, face number) and a table of the distinct names; a
result's named faces are made only when something asks for them (``LazyNamedShape``),
and each result's memory size is stored with it.
"""

from __future__ import annotations

import base64
import functools
import hashlib
import io
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from OCP.BinTools import BinTools, BinTools_FormatVersion
from OCP.BRep import BRep_Builder
from OCP.TopAbs import TopAbs_ShapeEnum
from OCP.TopoDS import TopoDS, TopoDS_Compound, TopoDS_Iterator, TopoDS_Shape

from fdcad.core.naming.names import NamedFace, NamedShape, faces_of

if TYPE_CHECKING:
    from fdcad.core.cache.memory import ResultCache
    from fdcad.core.features.base import FeatureResult

_FORMAT = 2
SUFFIX = ".history"


@functools.cache
def code_stamp() -> str:
    """A fingerprint of this build of FDCAD: its version and, run from source, the size
    and time of every core module; in a packaged app, the program file."""
    import fdcad

    parts: list[str] = [str(getattr(fdcad, "__version__", ""))]
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        try:
            info = exe.stat()
            parts.append(f"{exe.name}:{info.st_size}:{info.st_mtime_ns}")
        except OSError:
            parts.append(exe.name)
    else:
        core = Path(__file__).resolve().parents[1]
        for path in sorted(core.rglob("*.py")):
            try:
                info = path.stat()
            except OSError:
                continue
            parts.append(f"{path.relative_to(core).as_posix()}:{info.st_size}:{info.st_mtime_ns}")
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


class LazyNamedShape(NamedShape):
    """A stored result's body whose named faces are made on first use (D2600)."""

    def __init__(
        self,
        shape: TopoDS_Shape,
        faces: list[NamedFace] | None = None,
        make: Callable[[], list[NamedFace]] | None = None,
    ) -> None:
        self.shape = shape
        self.__dict__["_faces"] = faces
        self.__dict__["_make"] = make

    @property
    def faces(self) -> list[NamedFace]:
        """The named faces, made from the stored numbers the first time."""
        found: list[NamedFace] | None = self.__dict__["_faces"]
        if found is None:
            make = self.__dict__["_make"]
            found = make() if make is not None else []
            self.__dict__["_faces"], self.__dict__["_make"] = found, None
        return found

    @faces.setter
    def faces(self, value: list[NamedFace]) -> None:
        self.__dict__["_faces"], self.__dict__["_make"] = value, None


def _storable(result: FeatureResult) -> bool:
    return (
        result.body is not None
        and bool(result.key)
        and result.sketch is None
        and result.plane is None
        and result.datum is None
    )


def _issue_data(result: FeatureResult) -> list[dict[str, Any]]:
    return [
        {
            "state": i.state.value,
            "message": i.message,
            "fixes": [{"label": f.label, "action": f.action, "data": f.data} for f in i.fixes],
            "highlight": list(i.highlight),
            "code": i.code,
        }
        for i in result.issues
    ]


def _encode(value: Any, add_shape: Callable[[TopoDS_Shape], int]) -> Any:
    """Plain data for a display extra; raises TypeError for anything else."""
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, list):
        return [_encode(v, add_shape) for v in value]
    if isinstance(value, tuple):
        return {"$t": [_encode(v, add_shape) for v in value]}
    if isinstance(value, dict):
        if not all(isinstance(k, str) for k in value):
            raise TypeError("extras keys must be text")
        return {"$d": {k: _encode(v, add_shape) for k, v in value.items()}}
    if isinstance(value, TopoDS_Shape):
        if value.IsNull():
            raise TypeError("null shape")
        return {"$s": add_shape(value)}
    raise TypeError(f"cannot store {type(value).__name__}")


_DOWNCAST: dict[TopAbs_ShapeEnum, Callable[[TopoDS_Shape], TopoDS_Shape]] = {
    TopAbs_ShapeEnum.TopAbs_COMPOUND: TopoDS.Compound,
    TopAbs_ShapeEnum.TopAbs_COMPSOLID: TopoDS.CompSolid,
    TopAbs_ShapeEnum.TopAbs_SOLID: TopoDS.Solid,
    TopAbs_ShapeEnum.TopAbs_SHELL: TopoDS.Shell,
    TopAbs_ShapeEnum.TopAbs_FACE: TopoDS.Face,
    TopAbs_ShapeEnum.TopAbs_WIRE: TopoDS.Wire,
    TopAbs_ShapeEnum.TopAbs_EDGE: TopoDS.Edge,
    TopAbs_ShapeEnum.TopAbs_VERTEX: TopoDS.Vertex,
}


def _typed(shape: TopoDS_Shape) -> TopoDS_Shape:
    cast = _DOWNCAST.get(shape.ShapeType())
    return cast(shape) if cast is not None else shape


def _decode(raw: Any, shapes: list[TopoDS_Shape]) -> Any:
    if isinstance(raw, list):
        return [_decode(v, shapes) for v in raw]
    if isinstance(raw, dict):
        if "$t" in raw:
            return tuple(_decode(v, shapes) for v in raw["$t"])
        if "$d" in raw:
            return {str(k): _decode(v, shapes) for k, v in raw["$d"].items()}
        if "$s" in raw:
            return _typed(shapes[int(raw["$s"])])
        raise ValueError("unknown stored value")
    return raw


def _thread_data(result: FeatureResult) -> list[dict[str, Any]]:
    from dataclasses import asdict

    return [asdict(t) for t in result.threads]


def history_files(folder: Path, key: str) -> tuple[Path, Path]:
    """The data and shape files of the history stored under ``key``."""
    return folder / f"{key}{SUFFIX}.json", folder / f"{key}{SUFFIX}.brep"


def _b64(array: np.ndarray[Any, Any]) -> str:
    return base64.b64encode(np.ascontiguousarray(array, dtype="<i4").tobytes()).decode("ascii")


def _from_b64(text: str) -> np.ndarray[Any, Any]:
    return np.frombuffer(base64.b64decode(text), dtype="<i4")


def store_history(folder: Path, key: str, results: dict[str, FeatureResult]) -> int:
    """Write the storable results of a finished rebuild under the part's ``key``.

    Returns how many were written. Raises OSError when the files cannot be written.
    """
    from fdcad.core.cache.disk import _write_atomic
    from fdcad.core.cache.memory import estimate_size
    from fdcad.core.occ import ShapeMap

    builder, compound = BRep_Builder(), TopoDS_Compound()
    builder.MakeCompound(compound)
    shapes: list[TopoDS_Shape] = []

    def add_shape(shape: TopoDS_Shape) -> int:
        index = next((i for i, s in enumerate(shapes) if s.IsSame(shape)), -1)
        if index < 0:
            builder.Add(compound, shape)
            shapes.append(shape)
            index = len(shapes) - 1
        return index

    table: dict[str, int] = {}
    name_ids: list[np.ndarray[Any, Any]] = []
    face_ids: list[np.ndarray[Any, Any]] = []
    at = 0
    entries: list[dict[str, Any]] = []
    before: NamedShape | None = None
    maps: dict[int, Any] = {}  # body index to its face map, made once per body
    for result in results.values():
        if not _storable(result):
            continue
        body = result.body
        assert body is not None
        try:
            issues, threads = _issue_data(result), _thread_data(result)
            json.dumps([issues, threads])  # every value must be plain data
            _encode(result.extras, lambda _shape: 0)  # all of it can be written
        except (TypeError, ValueError):
            continue
        extras = _encode(result.extras, add_shape)
        index = add_shape(body.shape)
        faces = maps.get(index)
        if faces is None:
            faces = ShapeMap()
            for face in faces_of(body.shape):
                faces.Add(face)
            maps[index] = faces
        named = body.faces
        ids = np.fromiter(
            (table.setdefault(name, len(table)) for name, _f in named), "<i4", len(named)
        )
        where = np.fromiter((faces.FindIndex(f) - 1 for _n, f in named), "<i4", len(named))
        name_ids.append(ids)
        face_ids.append(where)
        entries.append(
            {
                "key": result.key,
                "body": index,
                "names": [at, len(named)],
                "issues": issues,
                "threads": threads,
                "extras": extras,
                "seconds": result.seconds,
                "size": estimate_size(result, before),
            }
        )
        at += len(named)
        before = body
    if not entries:
        return 0
    stream = io.BytesIO()
    # With the display meshes there are (the finished part's, D2600): meshing the machine
    # bed again took 2.7 s in the app, checking a stored mesh 0.6 s. Normals are made
    # again by the viewer.
    BinTools.Write_s(
        compound, stream, True, False, BinTools_FormatVersion.BinTools_FormatVersion_CURRENT
    )
    meta_path, shape_path = history_files(folder, key)
    folder.mkdir(parents=True, exist_ok=True)
    _write_atomic(shape_path, stream.getvalue())
    empty = np.zeros(0, "<i4")
    meta = {
        "format": _FORMAT,
        "stamp": code_stamp(),
        "shapes": len(shapes),
        "name_table": list(table),
        "name_ids": _b64(np.concatenate(name_ids) if name_ids else empty),
        "face_ids": _b64(np.concatenate(face_ids) if face_ids else empty),
        "results": entries,
    }
    _write_atomic(meta_path, json.dumps(meta).encode("utf-8"))
    return len(entries)


def _maker(
    body: TopoDS_Shape,
    body_faces: dict[int, list[Any]],
    index: int,
    names: list[str],
    ids: np.ndarray[Any, Any],
    where: np.ndarray[Any, Any],
) -> Callable[[], list[NamedFace]]:
    def make() -> list[NamedFace]:
        faces = body_faces.get(index)
        if faces is None:
            faces = body_faces[index] = faces_of(body)
        return [
            (names[n], faces[i])
            for n, i in zip(ids.tolist(), where.tolist(), strict=True)
            if i >= 0
        ]

    return make


def load_history(folder: Path, key: str) -> list[FeatureResult]:
    """The results stored under the part's ``key``, in build order; empty when there is
    none, it is damaged, or another build of FDCAD wrote it."""
    from fdcad.core.features.base import FeatureResult, FeatureState, Fix, Issue, ThreadMark

    meta_path, shape_path = history_files(folder, key)
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("format") != _FORMAT or meta.get("stamp") != code_stamp():
            return []
        shape = TopoDS_Shape()
        BinTools.Read_s(shape, io.BytesIO(shape_path.read_bytes()))
        if shape.IsNull():
            return []
        shapes: list[TopoDS_Shape] = []
        children = TopoDS_Iterator(shape)
        while children.More():
            shapes.append(children.Value())
            children.Next()
        if len(shapes) != int(meta["shapes"]):
            return []
        names = [str(n) for n in meta["name_table"]]
        all_ids, all_where = _from_b64(meta["name_ids"]), _from_b64(meta["face_ids"])
        body_faces: dict[int, list[Any]] = {}  # each body's faces, shared by its results
        out: list[FeatureResult] = []
        for entry in meta["results"]:
            index = int(entry["body"])
            body = shapes[index]
            start, count = (int(v) for v in entry["names"])
            ids, where = all_ids[start : start + count], all_where[start : start + count]
            if len(ids) != count or len(where) != count:
                return []
            named = LazyNamedShape(body, make=_maker(body, body_faces, index, names, ids, where))
            issues = [
                Issue(
                    FeatureState(i["state"]),
                    str(i["message"]),
                    [Fix(str(f["label"]), str(f["action"]), dict(f["data"])) for f in i["fixes"]],
                    [str(h) for h in i["highlight"]],
                    str(i["code"]),
                )
                for i in entry["issues"]
            ]
            threads = [
                ThreadMark(
                    tuple(t["origin"]),
                    tuple(t["direction"]),
                    float(t["diameter"]),
                    float(t["pitch"]),
                    float(t["length"]),
                    float(t["surface"]),
                    bool(t["internal"]),
                    str(t.get("label", "")),
                )
                for t in entry["threads"]
            ]
            result = FeatureResult(
                body=named,
                issues=issues,
                key=str(entry["key"]),
                seconds=float(entry.get("seconds", 0.0)),
            )
            result.threads = threads
            result.extras = _decode(entry.get("extras", {"$d": {}}), shapes)
            result.__dict__["_stored_size"] = int(entry.get("size", 0)) or None
            out.append(result)
        meta_path.touch()  # recently used, for pruning
        return out
    except Exception:  # the kernel raises its own types on a damaged file
        return []


def seed(cache: ResultCache, results: list[FeatureResult]) -> None:
    """Put stored results in the engine's memory cache, in build order, so each is sized
    by the faces it changed (``memory.estimate_size``), or by its stored size."""
    before: NamedShape | None = None
    for result in results:
        cache.put(result.key, result, before, result.__dict__.get("_stored_size"))
        before = result.body
