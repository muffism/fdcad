"""Save bodies to separate files (Split, PHASE3_SPEC P3.4 item 3, DECISIONS D528).

Each body goes to its own file in one folder. Formats:

- ``fdef``: a new FDCAD part whose only feature is an Imported STEP body
  (DECISIONS D290) holding the body, so it opens and can be edited directly.
- ``step``, ``stl`` and ``3mf``: the existing export writers.

Kernel work: call this off the UI thread. The part is never changed.
"""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Sequence
from pathlib import Path

from OCP.TopoDS import TopoDS_Shape

from fdcad.core.io.export import ExportError, MeshSettings, export_3mf, export_step, export_stl
from fdcad.core.units import UnitSystem

#: Format key to file extension, in the order the panel lists them.
FORMATS: dict[str, str] = {"fdef": ".fdprt", "step": ".step", "stl": ".stl", "3mf": ".3mf"}

_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


#: Device names Windows reserves, with or without a suffix ("CON.step" cannot be written).
_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {f"{d}{n}" for d in ("COM", "LPT") for n in range(10)}


def file_stem(text: str, fallback: str) -> str:
    """A name that is safe as a file name on Windows and macOS (no folder parts)."""
    stem = _BAD.sub("_", text).strip().strip(".").strip()
    head, dot, rest = stem.partition(".")
    if head.strip().upper() in _RESERVED:  # Windows looks at the name before the first dot
        stem = f"{head.strip()}_{dot}{rest}"
    return stem or fallback


def step_bytes(shape: TopoDS_Shape) -> bytes:
    """``shape`` as STEP file data in millimetres."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "body.step"
        export_step(shape, path)
        return path.read_bytes()


def body_part(shape: TopoDS_Shape, name: str, units: UnitSystem = UnitSystem.MM) -> str:
    """A new part holding ``shape`` as an Imported STEP body, as part file text."""
    from fdcad.core.features.import_step import part_from_step
    from fdcad.core.io import fdef

    doc = part_from_step(f"{name}.step", step_bytes(shape), units)
    return fdef.dumps(doc)


def save_bodies(
    bodies: Sequence[tuple[str, TopoDS_Shape]],
    folder: str | os.PathLike[str],
    fmt: str,
    units: UnitSystem = UnitSystem.MM,
    color: str = "#B4BCC4",
    settings: MeshSettings | None = None,
) -> list[Path]:
    """Write each ``(name, shape)`` to ``folder/<name><extension>``; the written paths.

    Names used twice get `` 2``, `` 3`` added. Raises ExportError naming the
    body that failed.
    """
    if fmt not in FORMATS:
        raise ExportError(f"Unknown format '{fmt}'. Choose FDCAD Part, STEP, STL or 3MF.")
    target = Path(folder)
    if not target.is_dir():
        raise ExportError(f"The folder {target} does not exist. Pick another folder.")
    used: set[str] = set()
    written: list[Path] = []
    for index, (name, shape) in enumerate(bodies, start=1):
        stem = file_stem(name, f"Body {index}")
        unique, k = stem, 2
        while unique.lower() in used:
            unique, k = f"{stem} {k}", k + 1
        used.add(unique.lower())
        path = target / f"{unique}{FORMATS[fmt]}"
        try:
            if fmt == "fdef":
                path.write_text(body_part(shape, unique, units), encoding="utf-8", newline="\n")
            elif fmt == "step":
                export_step(shape, path)
            elif fmt == "stl":
                export_stl(shape, path, settings)
            else:
                export_3mf(shape, path, color, settings, name=unique)
        except ExportError as exc:
            raise ExportError(f"{unique} could not be saved: {exc}") from exc
        except OSError as exc:
            raise ExportError(
                f"{unique} could not be saved ({exc.strerror}). Check the folder and try again."
            ) from exc
        except Exception as exc:  # a kernel failure never crashes the app
            raise ExportError(
                f"{unique} could not be saved ({type(exc).__name__}). Rebuild and try again."
            ) from exc
        written.append(path)
    return written


def linked_part(
    master: Path,
    number: int,
    name: str,
    units: UnitSystem = UnitSystem.MM,
    path: Path | None = None,
) -> str:
    """A new part whose only feature inserts body ``number`` (from 1) of ``master``,
    linked to it (TR280, D2421), as part file text. With ``path``, the text is for a
    file there, so a master in its folder tree is named relative to it (D2625)."""
    from fdcad.core.document.model import Feature, new_document
    from fdcad.core.io import fdef

    doc = new_document(units)
    doc.features.append(
        Feature(
            doc.new_feature_id(),
            "insert_part",
            name,
            params={"part_file": str(master), "link": True, "keep_bodies": str(number)},
            refs={},
        )
    )
    return fdef.dumps(doc, path)


def save_linked_parts(
    master: str | os.PathLike[str],
    bodies: Sequence[tuple[str, int]],
    folder: str | os.PathLike[str],
    units: UnitSystem = UnitSystem.MM,
) -> list[Path]:
    """Write a linked part file for each ``(name, body number)`` of the saved part
    ``master`` into ``folder`` (TR280, D2421): each holds an Insert Part linked to the
    master, so changes saved to the master flow on. No kernel work. Raises ExportError."""
    source = Path(master).resolve()
    if not source.is_file():
        raise ExportError("Save the part first, so the linked parts can find it.")
    target = Path(folder)
    if not target.is_dir():
        raise ExportError(f"The folder {target} does not exist. Pick another folder.")
    used: set[str] = set()
    written: list[Path] = []
    for index, (name, number) in enumerate(bodies, start=1):
        stem = file_stem(name, f"Body {index}")
        unique, k = stem, 2
        while unique.lower() in used:
            unique, k = f"{stem} {k}", k + 1
        used.add(unique.lower())
        path = target / f"{unique}{FORMATS['fdef']}"
        if path.resolve() == source:
            raise ExportError(f"{unique} would replace the master part. Pick another folder.")
        try:
            text = linked_part(source, number, unique, units, path)
            path.write_text(text, encoding="utf-8", newline="\n")
        except OSError as exc:
            raise ExportError(
                f"{unique} could not be saved ({exc.strerror}). Check the folder and try again."
            ) from exc
        written.append(path)
    return written


__all__ = [
    "FORMATS",
    "body_part",
    "file_stem",
    "linked_part",
    "save_bodies",
    "save_linked_parts",
    "step_bytes",
]
