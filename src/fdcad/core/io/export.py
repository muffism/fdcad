"""STEP, STL and 3MF export (PLAN Phase 1).

Meshes never pass through Python loops (CLAUDE.md 5A rule 2): OpenCascade
meshes and writes binary STL in C++, and 3MF reads that STL back as one numpy
array. Export meshes are made on demand and freed afterwards (PLAN 11.4 item 7).
"""

from __future__ import annotations

import os
import tempfile
import threading
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepTools import BRepTools
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
from OCP.StlAPI import StlAPI_Writer
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.features.solids import solids
from fdcad.core.io.temp_file import make_temp

STEP_SCHEMAS = {"AP214": "AP214IS", "AP242": "AP242DIS"}

_STL_DTYPE = np.dtype([("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)), ("attr", "<u2")])


class ExportError(Exception):
    """Export failed. The message is shown to the user."""


@dataclass(frozen=True)
class MeshSettings:
    """Mesh quality for STL and 3MF: chord deviation in mm and angle in radians, and
    (TR182, D776) text or binary STL and the file's unit, "mm" or "in"."""

    deviation: float = 0.01
    angle: float = 0.5
    ascii: bool = False
    unit: str = "mm"
    #: 3MF only: ``default`` (Bambu Studio, OrcaSlicer, Cura) or ``prusa`` (TR382, D796).
    slicer: str = "default"
    #: Overlapping bodies (TR411, D907): ``warn``, ``join`` or ``first`` (earlier wins).
    overlaps: str = "warn"
    #: Refining (TR336, D1200): the largest edge length in mm, 0 for no limit.
    max_edge: float = 0.0
    #: Refining (TR336, D2001): the largest aspect ratio, 0 for no limit (else 2 or more).
    max_aspect: float = 0.0

    @property
    def refines(self) -> bool:
        """True when an edge length or aspect ratio limit is set."""
        return self.max_edge > 0 or self.max_aspect > 0

    def validate(self) -> None:
        """Raise ExportError for settings that cannot work."""
        if self.deviation <= 0 or self.angle <= 0:
            raise ExportError("Deviation and angle must be greater than zero. Enter larger values.")
        if self.unit not in ("mm", "in"):
            raise ExportError("The unit must be mm or in. Choose one of them.")
        from fdcad.core.printing.body_roles import SLICER_TARGETS

        if self.slicer not in SLICER_TARGETS:  # TR385 (D1206)
            raise ExportError("Unknown slicer target. Choose one of the listed slicers.")
        if self.overlaps not in ("warn", "join", "first"):
            raise ExportError("Overlapping bodies must be warn, join or first. Choose one.")
        if self.max_edge < 0:
            raise ExportError("The largest edge length cannot be negative. Enter 0 or more.")
        if self.max_aspect < 0:
            raise ExportError("The largest aspect ratio cannot be negative. Enter 0 or more.")

    def to_data(self) -> dict[str, Any]:
        """The settings as saved in the part's print setup (TR182)."""
        return {
            "deviation": self.deviation,
            "angle": self.angle,
            "ascii": self.ascii,
            "unit": self.unit,
            "slicer": self.slicer,
            **({"overlaps": self.overlaps} if self.overlaps != "warn" else {}),
            **({"max_edge": self.max_edge} if self.max_edge else {}),
            **({"max_aspect": self.max_aspect} if self.max_aspect else {}),
        }

    @classmethod
    def from_data(cls, raw: Any) -> MeshSettings:
        """Settings saved with :meth:`to_data`; anything missing or wrong is the default."""
        base = cls()
        if not isinstance(raw, dict):
            return base
        try:
            out = cls(
                float(raw.get("deviation", base.deviation)),
                float(raw.get("angle", base.angle)),
                bool(raw.get("ascii", base.ascii)),
                str(raw.get("unit", base.unit)),
                str(raw.get("slicer", base.slicer)),
                str(raw.get("overlaps", base.overlaps)),
                float(raw.get("max_edge", base.max_edge)),
                float(raw.get("max_aspect", base.max_aspect)),
            )
            out.validate()
        except (TypeError, ValueError, ExportError):
            return base
        return out


#: Quality presets (TR182): chord deviation in mm and angle in radians.
PRESETS: dict[str, tuple[float, float]] = {
    "coarse": (0.1, 0.6),
    "standard": (0.01, 0.5),
    "fine": (0.002, 0.2),
}


def _in_unit(shape: TopoDS_Shape, unit: str) -> TopoDS_Shape:
    """A copy of ``shape`` scaled for a file in inches (the model is in mm)."""
    if unit != "in":
        return shape
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Pnt, gp_Trsf

    scale = gp_Trsf()
    scale.SetScale(gp_Pnt(0, 0, 0), 1 / 25.4)
    return BRepBuilderAPI_Transform(shape, scale, True).Shape()


def mesh_stats(shape: TopoDS_Shape, settings: MeshSettings, kind: str) -> tuple[int, int]:
    """The triangle count and the file size in bytes (3MF about) before saving."""
    count = len(triangles(shape, settings))
    BRepTools.Clean_s(shape)
    return count, file_size(count, settings, kind)


def file_size(count: int, settings: MeshSettings, kind: str) -> int:
    """About how many bytes a mesh file of ``count`` triangles takes."""
    if kind == "stl":
        # Binary: an 80 byte header, a count, 50 bytes a triangle; text: about 260 a triangle.
        return (count * 260 + 40) if settings.ascii else (84 + 50 * count)
    return 200 + count * 30  # 3MF is zipped XML: about 30 bytes a triangle


@dataclass(frozen=True)
class MeshPreview:
    """The export mesh before saving (TR336, D1200): its triangles and quality."""

    vertices: NDArray[np.float64]
    triangles: NDArray[np.int64]
    #: The longest edge in mm and the worst aspect ratio (1 is equilateral).
    longest: float
    worst: float
    #: Triangles with an aspect ratio above :data:`THIN`.
    thin: int


#: Triangles thinner than this aspect ratio are counted in the preview.
THIN = 20.0


def mesh_preview(shape: TopoDS_Shape, settings: MeshSettings) -> MeshPreview:
    """The mesh that export would write for ``shape``, with its quality (TR336)."""
    from fdcad.core.io.mesh_refine import aspect_ratios, quality

    vertices, tri = indexed_mesh(triangles(shape, settings))
    BRepTools.Clean_s(shape)
    longest, worst = quality(vertices, tri)
    ratios = aspect_ratios(vertices, tri) if len(tri) else np.zeros(0)
    thin = int((np.isfinite(ratios) & (ratios > THIN)).sum())
    return MeshPreview(vertices, tri, longest, worst, thin)


FaceColors = list[tuple[TopoDS_Shape, str]]


def export_step(
    shape: TopoDS_Shape,
    path: str | os.PathLike[str],
    schema: str = "AP214",
    color: str | None = None,
    faces: FaceColors | None = None,
    notes: Sequence[str] = (),
    unit: str = "mm",
    y_up: bool = False,
    names: Sequence[str] | None = None,
) -> None:
    """Write ``shape`` as STEP. ``schema`` is "AP214" (default) or "AP242".

    With ``color`` (the part colour) or ``faces`` (face colours), the colours are
    written too (PHASE2_SPEC P2.11 item 2, D254). ``notes`` are added to the file
    description (cosmetic threads, P4.2). TR302 (D1202): ``unit`` is the file's unit
    ("mm", "in" or "m"; the writer converts the lengths), ``y_up`` turns the model so
    its Z up is Y up, and ``names`` writes each body as a product of that name.
    """
    from fdcad.core.io.step_options import UNITS, turned

    if schema not in STEP_SCHEMAS:
        raise ExportError(f"Unknown STEP schema '{schema}'. Choose AP214 or AP242.")
    if unit not in UNITS:
        raise ExportError(f"Unknown STEP unit '{unit}'. Choose mm, in or m.")
    if y_up:
        shape = turned(shape)
        faces = [(turned(f), c) for f, c in faces] if faces else faces
    # The schema and unit are settings for the whole process: hold them until the file
    # is written, so two exports on the worker pool cannot mix them (audit D item 14,
    # D733).
    with _STEP_SETTINGS:
        from OCP.STEPControl import STEPControl_Controller

        # The settings exist only once the STEP controller is set up: before that the
        # first export of a session silently kept the defaults (TR302, D1202).
        STEPControl_Controller.Init_s()
        Interface_Static.SetCVal_s("write.step.schema", STEP_SCHEMAS[schema])
        Interface_Static.SetCVal_s("write.step.unit", UNITS[unit])
        _write_step(shape, Path(path), color, faces, notes, names)


#: Held while the process wide STEP writer settings are set and used.
_STEP_SETTINGS = threading.Lock()


def _write_step(
    shape: TopoDS_Shape,
    target: Path,
    color: str | None,
    faces: FaceColors | None,
    notes: Sequence[str],
    names: Sequence[str] | None = None,
) -> None:
    if color is not None or faces or names:
        _export_step_colored(shape, target, color, faces or [], notes, names)
        return
    writer = STEPControl_Writer()
    if writer.Transfer(shape, STEPControl_AsIs) != IFSelect_RetDone:
        raise ExportError("The part could not be converted to STEP. Rebuild it and try again.")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_file = Path(tmp) / "export.step"
        if writer.Write(str(tmp_file)) != IFSelect_RetDone:
            raise ExportError(f"Could not write {target.name}. Check the folder and try again.")
        _finish_step(tmp_file, target, notes)


def _finish_step(tmp_file: Path, target: Path, notes: Sequence[str]) -> None:
    """Add the notes to the written file, then copy it to ``target``."""
    if notes:
        from fdcad.core.io.step_notes import add_notes

        text = tmp_file.read_text(encoding="latin-1")
        tmp_file.write_text(add_notes(text, notes), encoding="latin-1")
    _copy(tmp_file, target)


def _quantity(hex_color: str) -> object:
    from OCP.Quantity import Quantity_Color, Quantity_TOC_sRGB

    text = _color(hex_color)[1:7]
    r, g, b = (int(text[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    return Quantity_Color(r, g, b, Quantity_TOC_sRGB)


def _export_step_colored(
    shape: TopoDS_Shape,
    target: Path,
    color: str | None,
    faces: FaceColors,
    notes: Sequence[str] = (),
    names: Sequence[str] | None = None,
) -> None:
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFDoc import XCAFDoc_ColorGen, XCAFDoc_ColorSurf, XCAFDoc_DocumentTool

    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    shapes = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    colors = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    if names:  # TR302 (D1202): one named product per body
        from OCP.TDataStd import TDataStd_Name

        labels = []
        for solid, title in zip(solids(shape) or [shape], names, strict=False):
            body_label = shapes.AddShape(solid, False)
            TDataStd_Name.Set_s(body_label, TCollection_ExtendedString(title))
            labels.append(body_label)
    else:
        labels = [shapes.AddShape(shape, False)]
    if color is not None:
        for label in labels:
            colors.SetColor(label, _quantity(color), XCAFDoc_ColorGen)
    for face, face_color in faces:
        for label in labels:
            sub = shapes.AddSubShape(label, face)
            if not sub.IsNull():
                colors.SetColor(sub, _quantity(face_color), XCAFDoc_ColorSurf)
                break
    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(bool(names))
    if not writer.Transfer(doc, STEPControl_AsIs):
        raise ExportError("The part could not be converted to STEP. Rebuild it and try again.")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_file = Path(tmp) / "export.step"
        if writer.Write(str(tmp_file)) != IFSelect_RetDone:
            raise ExportError("The STEP file could not be written. Check the folder and try again.")
        _finish_step(tmp_file, target, notes)


def _copy(src: Path, target: Path) -> None:
    """Copy through Python, so folders with any characters work."""
    data = src.read_bytes()
    fd, tmp = make_temp(target.parent, target)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _mesh(shape: TopoDS_Shape, settings: MeshSettings) -> None:
    settings.validate()
    mesher = BRepMesh_IncrementalMesh(shape, settings.deviation, False, settings.angle, True)
    if not mesher.IsDone():
        raise ExportError("The part could not be meshed. Try a larger deviation.")


def _stl_bytes(shape: TopoDS_Shape, ascii: bool = False) -> bytes:
    writer = StlAPI_Writer()
    writer.ASCIIMode = ascii
    with tempfile.TemporaryDirectory() as tmp:
        tmp_file = Path(tmp) / "mesh.stl"
        if not writer.Write(shape, str(tmp_file)):
            raise ExportError("The mesh could not be written. Rebuild the part and try again.")
        return tmp_file.read_bytes()


def triangles(shape: TopoDS_Shape, settings: MeshSettings) -> NDArray[np.float32]:
    """Triangles of ``shape`` as an (n, 3, 3) array of corner coordinates in mm, refined
    by the settings' largest edge length (TR336, D1200) and aspect ratio (D2001)."""
    tris = _raw_triangles(shape, settings)
    if not settings.refines or len(tris) == 0:
        return tris
    from fdcad.core.io.mesh_refine import refine

    vertices, tri = indexed_mesh(tris)
    done = refine(vertices, tri, settings.max_edge, max_aspect=settings.max_aspect)
    return np.ascontiguousarray(done.vertices[done.triangles], dtype=np.float32)


def _raw_triangles(shape: TopoDS_Shape, settings: MeshSettings) -> NDArray[np.float32]:
    """The kernel's triangles of ``shape``, not refined."""
    _mesh(shape, settings)
    data = _stl_bytes(shape)
    count = int(np.frombuffer(data, dtype="<u4", count=1, offset=80)[0])
    records = np.frombuffer(data, dtype=_STL_DTYPE, count=count, offset=84)
    return np.ascontiguousarray(records["vertices"])


def export_stl(
    shape: TopoDS_Shape, path: str | os.PathLike[str], settings: MeshSettings | None = None
) -> None:
    """Write ``shape`` as STL: binary unless ``settings.ascii``, in millimetres unless
    ``settings.unit`` is "in" (STL has no unit, so the numbers are inches then)."""
    settings = settings or MeshSettings()
    settings.validate()
    shape = _in_unit(shape, settings.unit)
    if settings.unit == "in":
        settings = in_inches(settings)
    if settings.refines:  # TR336 (D1200): the refined triangles, written from numpy
        data = stl_from_triangles(triangles(shape, settings), settings.ascii)
    else:
        _mesh(shape, settings)
        data = _stl_bytes(shape, settings.ascii)
    target = Path(path)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_file = Path(tmp) / "export.stl"
        tmp_file.write_bytes(data)
        _copy(tmp_file, target)
    BRepTools.Clean_s(shape)  # free the export mesh


def in_inches(settings: MeshSettings) -> MeshSettings:
    """``settings`` for a model scaled to inches: the same deviation and edge limit."""
    from dataclasses import replace

    return replace(
        settings, deviation=settings.deviation / 25.4, max_edge=settings.max_edge / 25.4, unit="in"
    )


def stl_from_triangles(tris: NDArray[np.float32], ascii: bool = False) -> bytes:
    """STL bytes from (n, 3, 3) corners: binary, or text when ``ascii`` (one format call)."""
    c = np.asarray(tris, dtype=np.float64).reshape(-1, 3, 3)
    normal = np.cross(c[:, 1] - c[:, 0], c[:, 2] - c[:, 0])
    length = np.linalg.norm(normal, axis=1, keepdims=True)
    normal = normal / np.where(length > 0, length, 1.0)
    if not ascii:
        records = np.zeros(len(c), dtype=_STL_DTYPE)
        records["normal"] = normal.astype(np.float32)
        records["vertices"] = c.astype(np.float32)
        return b"FDCAD".ljust(80, b" ") + np.uint32(len(c)).tobytes() + records.tobytes()
    facet = (
        " facet normal %e %e %e\n  outer loop\n"
        + "   vertex %e %e %e\n" * 3
        + "  endloop\n endfacet\n"
    )
    rows = np.concatenate([normal, c.reshape(-1, 9)], axis=1)
    body = (facet * len(c)) % tuple(rows.ravel().tolist())
    return f"solid FDCAD\n{body}endsolid FDCAD\n".encode("ascii")


# 3MF -------------------------------------------------------------------------------------

_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" '
    'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="model" '
    'ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
    "</Types>"
)
_RELS = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
    'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
    "</Relationships>"
)


#: A placement as gp_Trsf's 3 by 4 matrix: three rows of rotation then translation.
Transform = tuple[tuple[float, float, float, float], ...]
#: Colour group ids start above the object ids of any part.
_GROUP_BASE = 100000
_CONTENT_TYPES_THUMB = _CONTENT_TYPES.replace(
    "</Types>", '<Default Extension="png" ContentType="image/png"/></Types>'
)
_RELS_THUMB = _RELS.replace(
    "</Relationships>",
    '<Relationship Target="/Metadata/thumbnail.png" Id="rel1" '
    'Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail"/>'
    "</Relationships>",
)


def transform_of(trsf: Any) -> Transform:
    """A gp_Trsf as the rows used by ``export_3mf``."""
    return tuple(
        (trsf.Value(r, 1), trsf.Value(r, 2), trsf.Value(r, 3), trsf.Value(r, 4)) for r in (1, 2, 3)
    )


def _matrix(t: Transform) -> str:
    """The 3MF item transform: x' = m00 x + m10 y + m20 z + m30, and so on, written as
    m00 m01 m02 m10 m11 m12 m20 m21 m22 m30 m31 m32."""
    (a, b, c, tx), (d, e, f, ty), (g, h, i, tz) = t
    values = (a, d, g, b, e, h, c, f, i, tx, ty, tz)
    return " ".join(f"{v:.9g}" for v in values)


def indexed_mesh(tris: NDArray[np.float32]) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """Shared vertices and triangle indices from loose triangles (whole array operations)."""
    corners = np.round(tris.reshape(-1, 3).astype(np.float64), 6)
    vertices, inverse = np.unique(corners, axis=0, return_inverse=True)
    faces = inverse.reshape(-1, 3)
    keep = (
        (faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 0] != faces[:, 2])
    )
    return vertices, faces[keep]


def _vertex_xml(vertices: NDArray[np.float64]) -> str:
    template = '<vertex x="%.6f" y="%.6f" z="%.6f"/>' * len(vertices)
    return template % tuple(vertices.ravel().tolist())


def _triangle_xml(faces: NDArray[np.int64]) -> str:
    template = '<triangle v1="%d" v2="%d" v3="%d"/>' * len(faces)
    return template % tuple(faces.ravel().tolist())


def _color(hex_color: str) -> str:
    text = hex_color.strip().upper()
    if not (text.startswith("#") and len(text) in (7, 9)):
        raise ExportError(f"Invalid colour '{hex_color}'. Use #RRGGBB.")
    int(text[1:], 16)
    return text


def _colored_triangles(
    body: TopoDS_Shape, settings: MeshSettings, faces: FaceColors, palette: list[str]
) -> tuple[NDArray[np.float64], NDArray[np.int64], NDArray[np.int64]]:
    """Vertices, triangles and a colour index per triangle (0 is the part colour)."""
    from OCP.BRep import BRep_Builder
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS_Compound

    from fdcad.core.occ import ShapeMap

    fmap = ShapeMap()
    for f, _c in faces:
        fmap.Add(f)
    wanted = [palette.index(_color(c)) for _f, c in faces]
    groups: dict[int, list[TopoDS_Shape]] = {}
    exp = TopExp_Explorer(body, TopAbs_FACE)
    while exp.More():
        face = exp.Current()
        exp.Next()
        found = fmap.FindIndex(face)
        index = wanted[found - 1] if found else 0
        groups.setdefault(index, []).append(face)
    _mesh(body, settings)
    parts, marks = [], []
    builder = BRep_Builder()
    for index, members in sorted(groups.items()):
        compound = TopoDS_Compound()
        builder.MakeCompound(compound)
        for face in members:
            builder.Add(compound, face)
        tris = _raw_triangles(compound, settings)
        parts.append(tris)
        marks.append(np.full(len(tris), index, dtype=np.int64))
    tris = np.concatenate(parts) if parts else np.zeros((0, 3, 3), dtype=np.float32)
    mark = np.concatenate(marks) if marks else np.zeros(0, dtype=np.int64)
    corners = np.round(tris.reshape(-1, 3).astype(np.float64), 6)
    vertices, inverse = np.unique(corners, axis=0, return_inverse=True)
    tri = inverse.reshape(-1, 3)
    keep = (tri[:, 0] != tri[:, 1]) & (tri[:, 1] != tri[:, 2]) & (tri[:, 0] != tri[:, 2])
    tri, mark = tri[keep], mark[keep]
    if settings.refines:  # TR336 (D1200): the whole body at once, so colour seams stay closed
        from fdcad.core.io.mesh_refine import refine

        done = refine(vertices, tri, settings.max_edge, max_aspect=settings.max_aspect, group=mark)
        return done.vertices, done.triangles, mark[done.parent]
    return vertices, tri, mark


def _colored_triangle_xml(faces: NDArray[np.int64], marks: NDArray[np.int64]) -> str:
    template = '<triangle v1="%d" v2="%d" v3="%d" pid="1" p1="%d"/>' * len(faces)
    data = np.concatenate([faces, marks[:, None]], axis=1)
    return template % tuple(data.ravel().tolist())


def xml_text(text: str) -> str:
    """``text`` safe inside an XML attribute: ``&``, ``<``, ``>`` and quotes escaped, and
    characters XML 1.0 cannot hold dropped (spec 2 section 20 item 11, audit D item 10,
    D714)."""
    from xml.sax.saxutils import escape

    clean = "".join(c for c in text if ord(c) >= 0x20 or c in (chr(9), chr(10), chr(13)))
    return escape(clean, {'"': "&quot;", "'": "&apos;"})


#: Standard 3MF metadata names and the custom property names (any case) they come
#: from (TR183, D960). Title falls back to the part name.
STANDARD_METADATA = {
    "Title": ("title",),
    "Designer": ("designer", "author", "drawn by", "drawnby"),
    "Description": ("description",),
    "Copyright": ("copyright",),
    "LicenseTerms": ("licence", "license", "licence terms", "license terms"),
    "CreationDate": ("created", "creation date", "date created"),
}


def standard_metadata(
    name: str, properties: dict[str, str] | None, today: str
) -> list[tuple[str, str]]:
    """The standard 3MF metadata items for a part: from its custom properties where
    one has a known name, Title from the part name otherwise, and ModificationDate as
    ``today`` (YYYY-MM-DD)."""
    found = {k.strip().lower(): str(v) for k, v in (properties or {}).items() if str(v).strip()}
    out: list[tuple[str, str]] = []
    for key, names in STANDARD_METADATA.items():
        value = next((found[n] for n in names if n in found), None)
        if value is None and key == "Title" and name.strip():
            value = name
        if value is not None:
            out.append((key, value))
    out.append(("ModificationDate", today))
    return out


def export_3mf(
    shape: TopoDS_Shape,
    path: str | os.PathLike[str],
    color: str = "#B4BCC4",
    settings: MeshSettings | None = None,
    name: str = "Part",
    faces: FaceColors | None = None,
    transform: Transform | None = None,
    thumbnail: bytes | None = None,
    roles: Sequence[str] | None = None,
    metadata: dict[str, str] | None = None,
    titles: Sequence[str | None] | None = None,
    body_settings: Sequence[dict[str, Any]] | None = None,
    heights: Sequence[dict[str, Any]] | None = None,
) -> None:
    """Write ``shape`` as 3MF: one mesh object per body, as components of one assembly
    object, so slicers keep them together as parts of one object (TR381, D777).

    ``metadata`` (the part's custom properties, TR82, D810) is written as ``fdcad:``
    metadata items, names with spaces turned to underscores.

    ``roles`` gives each body's print role (``core.printing.body_roles``, TR382, D796),
    written in the forms the slicers read. ``settings.slicer`` ``prusa`` writes every
    body into one mesh object instead, with triangle ranges per body, the layout
    PrusaSlicer needs.

    Each body gets a colour group with one colour (its most used face colour, else
    ``color``) as its object colour, which slicers map to a filament; ``faces`` also
    gives faces their own colours as base materials per triangle, for viewers
    (PHASE2_SPEC P2.11 item 2, D254). ``transform`` places the assembly on the build
    plate (the print orientation) instead of moving the vertices, and ``thumbnail``
    (PNG bytes) is the package picture. ``titles`` gives bodies their own names
    (``core.body_titles``, TR183, D1201); others are "title body N". ``body_settings``
    gives bodies slicer settings (``core.printing.body_settings``, TR383, D1207), and
    ``heights`` pauses, colour changes and settings by height (``core.printing.heights``,
    TR384, D1208), in mm above the bed.
    """
    settings = settings or MeshSettings()
    settings.validate()
    inch = settings.unit == "in"
    if inch:  # the file holds inches: scale the model and keep the same chord deviation
        shape = _in_unit(shape, "in")
        faces = [(_scaled_face(shape, f), c) for f, c in faces or []] if faces else faces
        settings = in_inches(settings)
    bodies = solids(shape) or [shape]
    palette = [_color(color)]
    for _face, face_color in faces or []:
        if _color(face_color) not in palette:
            palette.append(_color(face_color))
    from fdcad.core.printing import body_roles as br

    wanted = list(roles or [])
    names_given = list(titles or [])
    per_body = list(body_settings or [])
    meshes: list[_BodyMesh] = []
    for index, body in enumerate(bodies, start=1):
        if faces:
            vertices, tri, marks = _colored_triangles(body, settings, faces, palette)
        else:
            vertices, tri = indexed_mesh(triangles(body, settings))
            marks = None
        BRepTools.Clean_s(body)
        if len(tri) == 0:
            continue
        role = wanted[index - 1] if index - 1 < len(wanted) else br.PART
        own = names_given[index - 1] if index - 1 < len(names_given) else None
        meshes.append(
            _BodyMesh(
                index,
                vertices,
                tri,
                marks,
                role if role in br.ROLES else br.PART,
                xml_text(own) if own else f"{xml_text(name)} body {index}",
                dict(per_body[index - 1]) if index - 1 < len(per_body) else {},
            )
        )
    if not meshes:
        raise ExportError("The part has no geometry to export. Add a feature first.")
    plain = settings.slicer == br.SLICER_PLAIN
    marked = br.any_role([m.role for m in meshes]) and not plain
    tuned = any(m.settings for m in meshes) and not plain  # TR383 (D1207)
    from fdcad.core.printing import body_settings as bs

    title = xml_text(name)
    configs: dict[str, str] = {}
    if settings.slicer == "prusa":
        objects, groups, item_id = _prusa_object(meshes, palette, title)
        if marked or tuned:
            configs["Metadata/Slic3r_PE_model.config"] = _prusa_config(meshes, title, item_id)
    else:
        objects, groups = [], []
        components = []
        for mesh in meshes:
            group = _GROUP_BASE + mesh.index
            groups.append(
                f'<m:colorgroup id="{group}"><m:color color="{mesh.main(palette)}FF"/>'
                "</m:colorgroup>"
            )
            cura = br.CURA_SETTINGS.get(mesh.role) if marked else None
            entries = [(cura, "True")] if cura is not None else []
            if not plain:
                entries += bs.cura_keys(mesh.settings)
            extra = (
                "<metadatagroup>"
                + "".join(
                    f'<metadata name="{k}" preserve="true">{xml_text(v)}</metadata>'
                    for k, v in entries
                )
                + "</metadatagroup>"
                if entries
                else ""
            )
            objects.append(
                f'<object id="{mesh.index + 1}" type="model" pid="{group}" pindex="0" '
                f'name="{mesh.title}">{extra}{mesh.xml()}</object>'
            )
            components.append(f'<component objectid="{mesh.index + 1}"/>')
        item_id = len(bodies) + 2
        objects.append(
            f'<object id="{item_id}" type="model" name="{title}">'
            f"<components>{''.join(components)}</components></object>"
        )
        if (marked or tuned) and settings.slicer == br.SLICER_DEFAULT:
            configs["Metadata/model_settings.config"] = _bambu_config(meshes, title, item_id)
    changes = [] if plain else list(heights or [])
    if changes and settings.slicer in (br.SLICER_DEFAULT, br.SLICER_PRUSA):
        from fdcad.core.printing import heights as hz

        top = _top(meshes, transform) * (25.4 if inch else 1.0)
        maker = hz.prusa_files if settings.slicer == br.SLICER_PRUSA else hz.bambu_files
        made = maker(hz.clean(changes), item_id, top)
        configs.update(made)
    if transform is not None and inch:  # the move is in mm; the file holds inches
        transform = tuple((a, b, c, t / 25.4) for a, b, c, t in transform)
    where = f' transform="{_matrix(transform)}"' if transform is not None else ""
    items = [f'<item objectid="{item_id}"{where}/>']
    bases = f'<base name="Part" displaycolor="{palette[0]}"/>'
    bases += "".join(
        f'<base name="Color {i}" displaycolor="{c}"/>' for i, c in enumerate(palette[1:], 1)
    )
    extra_meta = "".join(
        f'<metadata name="fdcad:{xml_text(_qname(k))}">{xml_text(v)}</metadata>'
        for k, v in (metadata or {}).items()
        if _qname(k)
    )
    import datetime

    today = datetime.date.today().isoformat()
    standard = "".join(  # TR183: title, designer, licence and dates for file browsers
        f'<metadata name="{k}">{xml_text(v)}</metadata>'
        for k, v in standard_metadata(name, metadata, today)
    )
    fdcad_ns = f' xmlns:fdcad="{FDCAD_NAMESPACE}"' if extra_meta else ""
    cura_ns = (
        f' xmlns:cura="{br.CURA_NAMESPACE}"'
        if (marked or tuned) and settings.slicer != "prusa"
        else ""
    )
    model = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<model unit="{"inch" if inch else "millimeter"}" xml:lang="en-US" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
        f'xmlns:m="http://schemas.microsoft.com/3dmanufacturing/material/2015/02"'
        f"{cura_ns}{fdcad_ns}>"
        '<metadata name="Application">FDCAD</metadata>'
        f"{standard}{extra_meta}"
        f'<resources><basematerials id="1">{bases}'
        f"</basematerials>{''.join(groups)}{''.join(objects)}</resources>"
        f"<build>{''.join(items)}</build></model>"
    )
    target = Path(path)
    fd, tmp = make_temp(target.parent, target)
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            types = _CONTENT_TYPES_THUMB if thumbnail else _CONTENT_TYPES
            if configs:
                types = types.replace("</Types>", _CONFIG_TYPE + "</Types>")
            zf.writestr("[Content_Types].xml", types)
            if thumbnail:
                zf.writestr("_rels/.rels", _RELS_THUMB)
                zf.writestr("Metadata/thumbnail.png", thumbnail)
            else:
                zf.writestr("_rels/.rels", _RELS)
            zf.writestr("3D/3dmodel.model", model)
            for part_name, text in configs.items():
                zf.writestr(part_name, text)
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _top(meshes: list[_BodyMesh], transform: Transform | None) -> float:
    """The height of the meshes once placed on the bed (the file's unit)."""
    v = np.concatenate([m.vertices for m in meshes])
    if transform is not None:
        rows = np.array(transform, dtype=np.float64)
        v = v @ rows[:, :3].T + rows[:, 3]
    return float(v[:, 2].max() - v[:, 2].min())


#: The content type of the slicer settings parts (TR382): plain XML.
_CONFIG_TYPE = (
    '<Default Extension="config" ContentType="text/xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
)


@dataclass
class _BodyMesh:
    """One body's indexed mesh for 3MF, with its colour marks and print role."""

    index: int
    vertices: NDArray[np.float64]
    triangles: NDArray[np.int64]
    marks: NDArray[np.int64] | None
    role: str
    #: The object name, escaped for XML (TR183, D1201).
    title: str = ""
    #: Slicer settings of the body (TR383, D1207).
    settings: dict[str, Any] = field(default_factory=dict)

    def main(self, palette: list[str]) -> str:
        """The body's most used colour, else the part colour."""
        if self.marks is None or not len(self.marks):
            return palette[0]
        return palette[int(np.bincount(self.marks).argmax())]

    def xml(self) -> str:
        """The ``<mesh>`` element."""
        return _mesh_xml(self.vertices, self.triangles, self.marks)


def _mesh_xml(
    vertices: NDArray[np.float64], tri: NDArray[np.int64], marks: NDArray[np.int64] | None
) -> str:
    triangle_xml = _triangle_xml(tri) if marks is None else _colored_triangle_xml(tri, marks)
    return (
        f"<mesh><vertices>{_vertex_xml(vertices)}</vertices>"
        f"<triangles>{triangle_xml}</triangles></mesh>"
    )


def _prusa_object(
    meshes: list[_BodyMesh], palette: list[str], title: str
) -> tuple[list[str], list[str], int]:
    """Every body in one mesh object, one block of vertices and triangles per body, in
    order (spec TR382 file forms item 13). Returns objects, colour groups, object id."""
    offset = 0
    tris, marks = [], []
    for mesh in meshes:
        tris.append(mesh.triangles + offset)
        offset += len(mesh.vertices)
        if mesh.marks is not None:
            marks.append(mesh.marks)
    vertices = np.concatenate([m.vertices for m in meshes])
    tri = np.concatenate(tris)
    mark = np.concatenate(marks) if len(marks) == len(meshes) else None
    main = palette[int(np.bincount(mark).argmax())] if mark is not None else palette[0]
    group = _GROUP_BASE + 1
    groups = [f'<m:colorgroup id="{group}"><m:color color="{main}FF"/></m:colorgroup>']
    objects = [
        f'<object id="2" type="model" pid="{group}" pindex="0" name="{title}">'
        f"{_mesh_xml(vertices, tri, mark)}</object>"
    ]
    return objects, groups, 2


def _prusa_config(meshes: list[_BodyMesh], title: str, object_id: int) -> str:
    """``Metadata/Slic3r_PE_model.config``: one volume per body with its triangle range
    and role (spec TR382 file forms items 14 to 17)."""
    from fdcad.core.printing.body_roles import PRUSA_TYPES
    from fdcad.core.printing.body_settings import prusa_keys

    volumes = []
    first = 0
    for mesh in meshes:
        last = first + len(mesh.triangles) - 1
        volumes.append(
            f'<volume firstid="{first}" lastid="{last}">'
            f'<metadata type="volume" key="name" value="{mesh.title}"/>'
            f'<metadata type="volume" key="volume_type" value="{PRUSA_TYPES[mesh.role]}"/>'
            + "".join(
                f'<metadata type="volume" key="{k}" value="{xml_text(v)}"/>'
                for k, v in prusa_keys(mesh.settings)
            )
            + "</volume>"
        )
        first = last + 1
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<config><object id="{object_id}" instances_count="1">'
        f'<metadata type="object" key="name" value="{title}"/>'
        f"{''.join(volumes)}</object></config>"
    )


def _bambu_config(meshes: list[_BodyMesh], title: str, assembly: int) -> str:
    """``Metadata/model_settings.config``: one part per body with its role (spec TR382
    file forms items 4 to 7)."""
    from fdcad.core.printing.body_roles import BAMBU_SUBTYPES
    from fdcad.core.printing.body_settings import bambu_keys

    parts = "".join(
        f'<part id="{mesh.index + 1}" subtype="{BAMBU_SUBTYPES[mesh.role]}">'
        f'<metadata key="name" value="{mesh.title}"/>'
        + "".join(
            f'<metadata key="{k}" value="{xml_text(v)}"/>' for k, v in bambu_keys(mesh.settings)
        )
        + "</part>"
        for mesh in meshes
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<config><object id="{assembly}"><metadata key="name" value="{title}"/>'
        f"{parts}</object></config>"
    )


def _scaled_face(scaled: TopoDS_Shape, face: TopoDS_Shape) -> TopoDS_Shape:
    """The face of ``scaled`` (a copy scaled to inches) where ``face`` was: matched by its
    middle, since the copy has new faces. Unmatched faces keep the part colour."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    from fdcad.core.naming.names import faces_of

    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, props)
    c = props.CentreOfMass()
    target = (c.X() / 25.4, c.Y() / 25.4, c.Z() / 25.4)
    best, gap = face, float("inf")
    for candidate in faces_of(scaled):
        p = GProp_GProps()
        BRepGProp.SurfaceProperties_s(candidate, p)
        m = p.CentreOfMass()
        d = (m.X() - target[0]) ** 2 + (m.Y() - target[1]) ** 2 + (m.Z() - target[2]) ** 2
        if d < gap:
            best, gap = candidate, d
    return best


#: The namespace of FDCAD's own 3MF metadata (custom properties, D810).
FDCAD_NAMESPACE = "https://fdcad.org/3mf/properties/2026"


def _qname(name: str) -> str:
    """A property name as the local part of an XML name: letters, digits and underscores."""
    import re

    clean = re.sub(r"[^A-Za-z0-9_]", "_", name.strip())
    return clean if clean and clean[0].isalpha() else ""
