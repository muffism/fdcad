"""Read STL, 3MF and OBJ meshes into compact numpy arrays (PLAN Phase 3, PHASE3_SPEC
P3.9, DECISIONS D294).

Every reader works on whole arrays (CLAUDE.md 5A rule 2): numpy parses binary
data directly, and text formats are split into tokens or matched with one
regular expression over the whole file, never with a Python loop per triangle
or vertex. The one exception is OBJ faces with more than four corners, which
are rare and are fanned into triangles line by line.

A mesh is ``vertices`` (n, 3) float32 in millimetres and ``triangles`` (m, 3)
int32 corner indices. STL and OBJ files carry no unit, so they are read as
millimetres; 3MF files say their unit and are scaled.
"""

from __future__ import annotations

import io
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

#: Above this many triangles the import warns that the mesh is heavy (PLAN).
TRIANGLE_WARNING = 100_000
FORMATS = ("stl", "3mf", "obj")

_STL_RECORD = np.dtype([("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)), ("attr", "<u2")])
_3MF_UNITS = {
    "micron": 0.001,
    "millimeter": 1.0,
    "centimeter": 10.0,
    "inch": 25.4,
    "foot": 304.8,
    "meter": 1000.0,
}


class MeshImportError(Exception):
    """The mesh file cannot be used. The message is shown to the user."""


@dataclass
class Mesh:
    """An indexed triangle mesh in millimetres."""

    vertices: NDArray[np.float32]
    triangles: NDArray[np.int32]

    @property
    def triangle_count(self) -> int:
        """Number of triangles."""
        return int(self.triangles.shape[0])

    def corners(self) -> NDArray[np.float32]:
        """Triangle corner coordinates as an (m, 3, 3) array."""
        return self.vertices[self.triangles]


def format_of(filename: str) -> str:
    """``stl``, ``3mf`` or ``obj`` from the file name. Raises MeshImportError."""
    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix not in FORMATS:
        raise MeshImportError(
            "Only STL, 3MF and OBJ meshes can be imported. Choose a file of one of these types."
        )
    return suffix


def from_corners(corners: NDArray[np.float32]) -> Mesh:
    """An indexed mesh from (m, 3, 3) corners: shared corners become one vertex."""
    flat = np.ascontiguousarray(corners.reshape(-1, 3), dtype=np.float32)
    if flat.size == 0:
        return Mesh(np.zeros((0, 3), np.float32), np.zeros((0, 3), np.int32))
    vertices, inverse = np.unique(flat, axis=0, return_inverse=True)
    return Mesh(vertices.astype(np.float32), inverse.reshape(-1, 3).astype(np.int32))


def clean(mesh: Mesh) -> Mesh:
    """Drop triangles with a repeated corner or no area."""
    t = mesh.triangles
    if t.size == 0:
        return mesh
    distinct = (t[:, 0] != t[:, 1]) & (t[:, 1] != t[:, 2]) & (t[:, 0] != t[:, 2])
    c = mesh.vertices[t].astype(np.float64)
    area = np.linalg.norm(np.cross(c[:, 1] - c[:, 0], c[:, 2] - c[:, 0]), axis=1)
    return Mesh(mesh.vertices, np.ascontiguousarray(t[distinct & (area > 1e-12)]))


# STL ----------------------------------------------------------------------------------


def _is_binary_stl(data: bytes) -> bool:
    """Binary when the triangle count fits the size. Some programs add bytes at the end."""
    if len(data) < 84:
        return False
    count = int(np.frombuffer(data, dtype="<u4", count=1, offset=80)[0])
    expected = 84 + 50 * count
    if len(data) == expected:
        return True
    return count > 0 and len(data) > expected and b"vertex" not in data[84:4096]


def _cut_short_binary(data: bytes) -> bool:
    """A binary STL whose triangles stop before the count in its header, which was
    reported as "not an STL" (audit D item 21, D742)."""
    if len(data) < 84 or b"facet" in data[:4096]:
        return False
    count = int(np.frombuffer(data, dtype="<u4", count=1, offset=80)[0])
    return count > 0 and len(data) < 84 + 50 * count


_LONG_TOKEN = re.compile(rb"\S{65}")


def read_stl(data: bytes) -> Mesh:
    """Binary or ASCII STL."""
    if _is_binary_stl(data):
        count = int(np.frombuffer(data, dtype="<u4", count=1, offset=80)[0])
        records = np.frombuffer(data, dtype=_STL_RECORD, count=count, offset=84)
        return from_corners(records["vertices"])
    if _cut_short_binary(data):
        raise MeshImportError(
            "The STL file ends early: it holds fewer triangles than its header says. "
            "Export the mesh again, or copy the file again from where it came from."
        )
    if b"facet" not in data[:4096] and not data.lstrip().startswith(b"solid"):
        raise MeshImportError(
            "The file is not an STL mesh or it is damaged. "
            "Export the mesh again from the program that made it."
        )
    if _LONG_TOKEN.search(data):
        # One long word would size the whole token array (audit D12 item 4, D709).
        raise MeshImportError(
            "The STL file has a damaged line (a word longer than 64 letters). "
            "Export the mesh again from the program that made it."
        )
    tokens = np.array(data.split())
    at = np.flatnonzero(tokens == b"vertex")
    if at.size == 0 or at.size % 3:
        raise MeshImportError(
            "The STL file has no complete triangles. "
            "Export the mesh again from the program that made it."
        )
    if at[-1] + 3 >= tokens.size:
        raise MeshImportError(
            "The STL file ends in the middle of a triangle. "
            "Export the mesh again from the program that made it."
        )
    try:
        coords = tokens[at[:, None] + np.arange(1, 4)].astype(np.float32)
    except ValueError as exc:
        raise MeshImportError(
            "The STL file has a vertex that is not a number. "
            "Export the mesh again from the program that made it."
        ) from exc
    return from_corners(coords.reshape(-1, 3, 3))


def stl_bytes(mesh: Mesh) -> bytes:
    """``mesh`` as binary STL, built as one array."""
    corners = mesh.corners().astype(np.float32)
    count = corners.shape[0]
    records = np.zeros(count, dtype=_STL_RECORD)
    records["vertices"] = corners
    c = corners.astype(np.float64)
    normal = np.cross(c[:, 1] - c[:, 0], c[:, 2] - c[:, 0])
    length = np.linalg.norm(normal, axis=1, keepdims=True)
    records["normal"] = (normal / np.where(length > 0, length, 1.0)).astype(np.float32)
    header = b"FDCAD mesh".ljust(80, b" ")
    return header + np.uint32(count).tobytes() + records.tobytes()


# OBJ ----------------------------------------------------------------------------------

_OBJ_VERTEX = re.compile(rb"^[ \t]*v[ \t]+(\S+)[ \t]+(\S+)[ \t]+(\S+)", re.M)
_INDEX = rb"(-?\d+)[^\s]*"
_OBJ_TRI = re.compile(rb"^[ \t]*f[ \t]+" + rb"[ \t]+".join([_INDEX] * 3) + rb"[ \t]*$", re.M)
_OBJ_QUAD = re.compile(rb"^[ \t]*f[ \t]+" + rb"[ \t]+".join([_INDEX] * 4) + rb"[ \t]*$", re.M)
_OBJ_FACE = re.compile(rb"^[ \t]*f[ \t]+(.+?)[ \t]*$", re.M)


def _obj_indices(raw: NDArray[np.int64], count: int) -> NDArray[np.int64]:
    """OBJ indices count from 1; negative ones count back from the end."""
    return np.where(raw < 0, raw + count, raw - 1)


def read_obj(data: bytes) -> Mesh:
    """OBJ vertices and faces; quads are split in two, larger polygons fanned."""
    data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")  # Windows and old Mac lines
    try:
        vertices = np.array(_OBJ_VERTEX.findall(data), dtype=np.float64).reshape(-1, 3)
    except ValueError as exc:
        raise MeshImportError(
            "The OBJ file has a vertex that is not a number. "
            "Export the mesh again from the program that made it."
        ) from exc
    n = vertices.shape[0]
    tris = np.array(_OBJ_TRI.findall(data), dtype=np.int64).reshape(-1, 3)
    quads = np.array(_OBJ_QUAD.findall(data), dtype=np.int64).reshape(-1, 4)
    parts = [tris, quads[:, [0, 1, 2]], quads[:, [0, 2, 3]]]
    face_lines = _OBJ_FACE.findall(data)
    if len(face_lines) > tris.shape[0] + quads.shape[0]:
        parts.append(_fans(face_lines))
    raw = np.concatenate(parts)
    # Relative corners count back from the vertices read so far at that face (audit D
    # item 8, D722): such files are read line by line; they are rare.
    faces = _relative_faces(data) if (raw < 0).any() else _obj_indices(raw, n)
    if faces.size and (faces.min() < 0 or faces.max() >= n):
        raise MeshImportError(
            "The OBJ file refers to a vertex it does not have. "
            "Export the mesh again from the program that made it."
        )
    return Mesh(vertices.astype(np.float32), faces.astype(np.int32))


def _relative_faces(data: bytes) -> NDArray[np.int64]:
    """Triangles of every face, with negative corners counted back from the vertices
    defined before that face's line."""
    out: list[list[int]] = []
    seen = 0
    for line in data.splitlines():
        head = line.lstrip()[:2]
        if head in (b"v ", b"v" + bytes([9])):
            seen += 1
            continue
        if head not in (b"f ", b"f" + bytes([9])):
            continue
        try:
            corners = [int(c.split(b"/", 1)[0]) for c in line.split()[1:]]
        except ValueError as exc:
            raise MeshImportError(
                "The OBJ file has a face corner that is not a vertex number. "
                "Export the mesh again from the program that made it."
            ) from exc
        index = [c + seen if c < 0 else c - 1 for c in corners]
        out.extend([index[0], index[i], index[i + 1]] for i in range(1, len(index) - 1))
    return np.array(out, dtype=np.int64).reshape(-1, 3)


def _fans(lines: list[bytes]) -> NDArray[np.int64]:
    """Triangles of the faces with more than four corners (rare: a short loop)."""
    out: list[list[int]] = []
    for line in lines:
        try:
            corners = [int(c.split(b"/", 1)[0]) for c in line.split()]
        except ValueError as exc:
            raise MeshImportError(
                "The OBJ file has a face corner that is not a vertex number. "
                "Export the mesh again from the program that made it."
            ) from exc
        if len(corners) <= 4:
            continue
        out.extend([corners[0], corners[i], corners[i + 1]] for i in range(1, len(corners) - 1))
    return np.array(out, dtype=np.int64).reshape(-1, 3)


# 3MF ----------------------------------------------------------------------------------

_UNIT = re.compile(rb'<(?:\w+:)?model\b[^>]*\bunit="([^"]+)"')
# Each tag is read in one pass: the attributes are matched one after another with a
# possessive repeat, so a damaged tag cannot make the pattern backtrack (audit D12
# item 1, D709). The order of the attributes does not matter.
_OTHER = rb'|[\w:]+="[^"]*+"'
_OBJECT = re.compile(
    rb'<(?:\w+:)?object\b(?:\s++(?:id="([^"]*+)"|type="([^"]*+)"' + _OTHER + rb"))*+\s*+>"
    rb"(.*?)</(?:\w+:)?object>",
    re.S,
)
_VERTEX = re.compile(
    rb'<(?:\w+:)?vertex\b(?:\s++(?:x="([^"]*+)"|y="([^"]*+)"|z="([^"]*+)"' + _OTHER + rb"))*+"
)
_TRIANGLE = re.compile(
    rb'<(?:\w+:)?triangle\b(?:\s++(?:v1="(\d++)"|v2="(\d++)"|v3="(\d++)"' + _OTHER + rb"))*+"
)
_COMPONENT = re.compile(
    rb'<(?:\w+:)?component\b(?:\s++(?:objectid="([^"]*+)"|transform="([^"]*+)"' + _OTHER + rb"))*+"
)
#: How deep components may nest inside each other (a loop would never end).
_MAX_NESTING = 16
_IDENTITY = np.vstack([np.eye(3), np.zeros(3)])
#: The most a 3MF model may unpack to, and the most files a package may hold.
MAX_3MF_MODEL = 1 << 30
MAX_3MF_FILES = 10000
_ITEM = re.compile(rb"<(?:\w+:)?item\b([^>]*)>")
_ATTR = re.compile(rb'\b(objectid|transform)="([^"]*)"')


def _model_file(archive: zipfile.ZipFile) -> bytes:
    names = archive.namelist()
    preferred = [n for n in names if n.lower() == "3d/3dmodel.model"]
    models = preferred or [n for n in names if n.lower().endswith(".model")]
    if not models:
        raise MeshImportError(
            "The 3MF file has no model inside. Export the mesh again from the program that made it."
        )
    if len(names) > MAX_3MF_FILES or archive.getinfo(models[0]).file_size > MAX_3MF_MODEL:
        raise MeshImportError(
            "The 3MF file unpacks to more than FDCAD reads (1 GB, 10000 files). "
            "Export a smaller mesh, or split it into several files."
        )
    return archive.read(models[0])


def _transform(text: bytes) -> NDArray[np.float64]:
    try:
        values = np.array(text.split(), dtype=np.float64)
    except ValueError:
        values = np.zeros(0)
    if values.size != 12 or not np.isfinite(values).all():
        raise MeshImportError(
            "The 3MF file has a build item with a damaged transform. "
            "Export the mesh again from the program that made it."
        )
    return values.reshape(4, 3)


def _placed(
    key: bytes,
    place: NDArray[np.float64],
    objects: dict[bytes, Mesh],
    parts: dict[bytes, list[tuple[bytes, bytes | None]]],
    depth: int,
) -> list[tuple[Mesh, NDArray[np.float64]]]:
    """The meshes object ``key`` is made of, each with its placement in the build:
    its own triangles, then those of its components (audit D item 9, D715)."""
    if depth > _MAX_NESTING:
        raise MeshImportError(
            "The 3MF file's components nest too deeply or refer to each other. "
            "Export the mesh again from the program that made it."
        )
    out: list[tuple[Mesh, NDArray[np.float64]]] = []
    mesh = objects.get(key)
    if mesh is not None and mesh.triangles.size:
        out.append((mesh, place))
    for child, transform in parts.get(key, []):
        own = _transform(transform) if transform is not None else _IDENTITY
        combined = np.vstack([own[:3] @ place[:3], own[3] @ place[:3] + place[3]])
        out += _placed(child, combined, objects, parts, depth + 1)
    return out


def read_3mf(data: bytes) -> Mesh:
    """The meshes of the build items (all objects when there are no items), in mm."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            model = _model_file(archive)
    except zipfile.BadZipFile as exc:
        raise MeshImportError(
            "The file is not a 3MF package or it is damaged. "
            "Export the mesh again from the program that made it."
        ) from exc
    unit = _UNIT.search(model)
    scale = _3MF_UNITS.get(unit.group(1).decode() if unit else "millimeter")
    if scale is None:
        raise MeshImportError(
            "The 3MF file uses a unit FDCAD does not know. Export it again in millimetres."
        )
    objects: dict[bytes, Mesh] = {}
    parts: dict[bytes, list[tuple[bytes, bytes | None]]] = {}
    for match in _OBJECT.finditer(model):
        body = match.group(3)
        if match.group(2) in (b"support", b"solidsupport", b"surface"):
            continue  # supports and open surfaces are not part of the model (D733)
        found = [(oid, tr or None) for oid, tr in _COMPONENT.findall(body) if oid]
        if found:
            parts[match.group(1)] = found
        try:
            v = np.array(_VERTEX.findall(body), dtype=np.float64).reshape(-1, 3)
            t = np.array(_TRIANGLE.findall(body), dtype=np.int64).reshape(-1, 3)
        except ValueError as exc:
            raise MeshImportError(
                "The 3MF file has a vertex that is not a number. "
                "Export the mesh again from the program that made it."
            ) from exc
        if t.size and t.max() >= v.shape[0]:
            raise MeshImportError(
                "The 3MF file refers to a vertex it does not have. "
                "Export the mesh again from the program that made it."
            )
        objects[match.group(1)] = Mesh(v.astype(np.float32), t.astype(np.int32))
    items = []
    for item in _ITEM.findall(model):
        attrs = dict(_ATTR.findall(item))
        if b"objectid" in attrs:
            items.append((attrs[b"objectid"], attrs.get(b"transform")))
    if not items:
        items = [(key, None) for key in objects]
    vertices, triangles, offset = [], [], 0
    for key, transform in items:
        place = _transform(transform) if transform is not None else _IDENTITY
        for mesh, m in _placed(key, place, objects, parts, 0):
            v = mesh.vertices.astype(np.float64) @ m[:3] + m[3]
            tri = mesh.triangles
            if np.linalg.det(m[:3]) < 0:
                tri = tri[:, ::-1]  # a mirror turns the mesh inside out unless flipped
            vertices.append(v * scale)
            triangles.append(tri + offset)
            offset += v.shape[0]
    if not triangles:
        raise MeshImportError(
            "The 3MF file has no triangles to import. Choose a file that holds a mesh."
        )
    return Mesh(
        np.concatenate(vertices).astype(np.float32), np.concatenate(triangles).astype(np.int32)
    )


# Slicer parts (TR386, D1205) ------------------------------------------------------------

#: The most a slicer settings part of a 3MF package may unpack to; larger ones are skipped.
MAX_3MF_CONFIG = 16 << 20
_NAME_ATTR = re.compile(rb'\bname="([^"]*+)"')
_BAMBU_NAME = re.compile(rb'<metadata\b[^>]*?\bkey="name"[^>]*?\bvalue="([^"]*+)"')
_ID = re.compile(rb'\bid="(\d++)"')
_SUBTYPE = re.compile(rb'\bsubtype="([^"]*+)"')
_FIRST = re.compile(rb'\bfirstid="(\d++)"')
_LAST = re.compile(rb'\blastid="(\d++)"')
_TAGS: dict[bytes, tuple[re.Pattern[bytes], re.Pattern[bytes]]] = {}


def _blocks(text: bytes, tag: bytes) -> list[tuple[bytes, bytes]]:
    """(attributes, inside) of every ``<tag ...>...</tag>`` and ``<tag .../>`` in one
    pass: each opening tag is paired with the next closing tag after it, so a file
    with no closing tags cannot make the search go back over it (D709)."""
    if tag not in _TAGS:
        _TAGS[tag] = (
            re.compile(rb"<" + tag + rb"\b([^>]*+)>"),
            re.compile(rb"</" + tag + rb"\s*+>"),
        )
    opening, closing = _TAGS[tag]
    ends = [m.start() for m in closing.finditer(text)]
    out: list[tuple[bytes, bytes]] = []
    k = 0
    for m in opening.finditer(text):
        attrs = m.group(1)
        if attrs.endswith(b"/"):
            out.append((attrs[:-1], b""))
            continue
        while k < len(ends) and ends[k] < m.end():
            k += 1
        if k < len(ends):
            out.append((attrs, text[m.end() : ends[k]]))
        else:
            out.append((attrs, b""))
    return out


_PRUSA_META = re.compile(rb'<metadata\b[^>]*?\bkey="(name|volume_type)"[^>]*?\bvalue="([^"]*+)"')
_CURA_ROLE = re.compile(
    rb'<(?:\w+:)?metadata\b[^>]*?\bname="cura:(infill_mesh|support_mesh|anti_overhang_mesh|'
    rb'cutting_mesh)"[^>]*+>\s*+(?i:true)\s*+<'
)
#: Slicer part kinds to FDCAD print roles (``core.printing.body_roles``).
_BAMBU_ROLES = {
    b"normal_part": "part",
    b"modifier_part": "modifier",
    b"negative_part": "negative",
    b"support_enforcer": "support_enforcer",
    b"support_blocker": "support_blocker",
}
_PRUSA_ROLES = {
    b"ModelPart": "part",
    b"ParameterModifier": "modifier",
    b"NegativeVolume": "negative",
    b"SupportEnforcer": "support_enforcer",
    b"SupportBlocker": "support_blocker",
}
_CURA_ROLES = {
    b"infill_mesh": "modifier",
    b"support_mesh": "support_enforcer",
    b"anti_overhang_mesh": "support_blocker",
    b"cutting_mesh": "negative",
}


@dataclass
class MeshPart:
    """One part of a slicer 3MF: its name, mesh in mm and print role."""

    name: str
    mesh: Mesh
    role: str = "part"


def _text(raw: bytes) -> str:
    import html

    from fdcad.core.body_titles import clean

    return clean(html.unescape(raw.decode("utf-8", "replace")))


def _config(archive: zipfile.ZipFile, name: str) -> bytes:
    """A settings part of the package, or b"" when it is missing or too large."""
    try:
        info = archive.getinfo(name)
    except KeyError:
        return b""
    return archive.read(name) if info.file_size <= MAX_3MF_CONFIG else b""


def _bambu_parts(config: bytes) -> dict[bytes, tuple[str, str]]:
    """Part object id to (name, role) from ``Metadata/model_settings.config``."""
    out: dict[bytes, tuple[str, str]] = {}
    for _attrs, body in _blocks(config, b"object"):
        for attrs, inner in _blocks(body, b"part"):
            pid = _ID.search(attrs)
            if pid is None:
                continue
            sub = _SUBTYPE.search(attrs)
            role = _BAMBU_ROLES.get(sub.group(1), "part") if sub else "part"
            name = _BAMBU_NAME.search(inner)
            out[pid.group(1)] = (_text(name.group(1)) if name else "", role)
    return out


def _prusa_volumes(config: bytes) -> dict[bytes, list[tuple[int, int, str, str]]]:
    """Object id to its volumes (first, last triangle, name, role) from
    ``Metadata/Slic3r_PE_model.config``."""
    out: dict[bytes, list[tuple[int, int, str, str]]] = {}
    for attrs, body in _blocks(config, b"object"):
        found = _ID.search(attrs)
        if found is None:
            continue
        oid = found.group(1)
        volumes = []
        for vattrs, inner in _blocks(body, b"volume"):
            first, last = _FIRST.search(vattrs), _LAST.search(vattrs)
            if first is None or last is None:
                continue
            meta = dict(_PRUSA_META.findall(inner))
            role = _PRUSA_ROLES.get(meta.get(b"volume_type", b""), "part")
            volumes.append(
                (int(first.group(1)), int(last.group(1)), _text(meta.get(b"name", b"")), role)
            )
        if volumes:
            out[oid] = volumes
    return out


def read_3mf_parts(data: bytes) -> list[MeshPart]:
    """The parts of a 3MF file in mm, one per mesh object placed in the build, or one per
    volume of PrusaSlicer's one object layout, each with its name and print role from
    the slicer settings in the package (Bambu Studio and OrcaSlicer part subtypes,
    PrusaSlicer volume types, Cura mesh settings). Raises MeshImportError."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            model = _model_file(archive)
            bambu = _bambu_parts(_config(archive, "Metadata/model_settings.config"))
            prusa = _prusa_volumes(_config(archive, "Metadata/Slic3r_PE_model.config"))
    except zipfile.BadZipFile as exc:
        raise MeshImportError(
            "The file is not a 3MF package or it is damaged. "
            "Export the mesh again from the program that made it."
        ) from exc
    unit = _UNIT.search(model)
    scale = _3MF_UNITS.get(unit.group(1).decode() if unit else "millimeter")
    if scale is None:
        raise MeshImportError(
            "The 3MF file uses a unit FDCAD does not know. Export it again in millimetres."
        )
    objects: dict[bytes, Mesh] = {}
    parts: dict[bytes, list[tuple[bytes, bytes | None]]] = {}
    names: dict[bytes, str] = {}
    cura: dict[bytes, str] = {}
    for match in _OBJECT.finditer(model):
        body = match.group(3)
        if match.group(2) in (b"support", b"solidsupport", b"surface"):
            continue
        key = match.group(1)
        head = match.group(0)[: match.start(3) - match.start(0)]
        found_name = _NAME_ATTR.search(head)
        if found_name:
            names[key] = _text(found_name.group(1))
        mark = _CURA_ROLE.search(body)
        if mark:
            cura[key] = _CURA_ROLES[mark.group(1)]
        found = [(oid, tr or None) for oid, tr in _COMPONENT.findall(body) if oid]
        if found:
            parts[key] = found
        try:
            v = np.array(_VERTEX.findall(body), dtype=np.float64).reshape(-1, 3)
            t = np.array(_TRIANGLE.findall(body), dtype=np.int64).reshape(-1, 3)
        except ValueError as exc:
            raise MeshImportError(
                "The 3MF file has a vertex that is not a number. "
                "Export the mesh again from the program that made it."
            ) from exc
        if t.size and t.max() >= v.shape[0]:
            raise MeshImportError(
                "The 3MF file refers to a vertex it does not have. "
                "Export the mesh again from the program that made it."
            )
        objects[key] = Mesh(v.astype(np.float32), t.astype(np.int32))
    items = []
    for item in _ITEM.findall(model):
        attrs = dict(_ATTR.findall(item))
        if b"objectid" in attrs:
            items.append((attrs[b"objectid"], attrs.get(b"transform")))
    if not items:
        items = [
            (key, None) for key in objects if key not in {c for v in parts.values() for c, _t in v}
        ]
    found_keys = {id(mesh): key for key, mesh in objects.items()}
    out: list[MeshPart] = []
    for item_key, transform in items:
        place = _transform(transform) if transform is not None else _IDENTITY
        for mesh, m in _placed(item_key, place, objects, parts, 0):
            v = (mesh.vertices.astype(np.float64) @ m[:3] + m[3]) * scale
            tri = mesh.triangles if np.linalg.det(m[:3]) >= 0 else mesh.triangles[:, ::-1]
            key = found_keys[id(mesh)]
            volumes = [(a, b, n, r) for a, b, n, r in prusa.get(key, []) if 0 <= a <= b < len(tri)]
            pieces = (
                [(tri[a : b + 1], n, r) for a, b, n, r in volumes]
                if volumes
                else [(tri, *bambu.get(key, (names.get(key, ""), cura.get(key, "part"))))]
            )
            for k, (piece, name, kind) in enumerate(pieces, 1):
                if not len(piece):
                    continue
                used, inverse = np.unique(piece.ravel(), return_inverse=True)
                part_mesh = clean(
                    Mesh(v[used].astype(np.float32), inverse.reshape(-1, 3).astype(np.int32))
                )
                if not part_mesh.triangle_count:
                    continue
                label = name or names.get(key) or f"Object {len(out) + 1}"
                if volumes and not name:
                    label = f"{label} {k}"
                out.append(MeshPart(label, part_mesh, kind))
    if not out:
        raise MeshImportError(
            "The 3MF file has no triangles to import. Choose a file that holds a mesh."
        )
    return out


# Entry points ---------------------------------------------------------------------------


def read_mesh(data: bytes, fmt: str) -> Mesh:
    """Read mesh file contents of format ``fmt``. Raises MeshImportError."""
    readers = {"stl": read_stl, "3mf": read_3mf, "obj": read_obj}
    if fmt not in readers:
        raise MeshImportError(
            "Only STL, 3MF and OBJ meshes can be imported. Choose a file of one of these types."
        )
    raw = readers[fmt](data)
    # Checked before cleaning: triangles with such a corner have no area and would be
    # dropped without a word, leaving a hole.
    if not np.isfinite(raw.vertices[raw.triangles]).all():
        raise MeshImportError(
            "The mesh has a vertex that is not a finite number. "
            "Export the mesh again from the program that made it."
        )
    mesh = clean(raw)
    if mesh.triangle_count == 0:
        raise MeshImportError("The mesh has no triangles. Choose a file that holds a mesh.")
    return mesh


def triangulation(mesh: Mesh) -> Any:
    """The mesh as an OpenCascade triangulation, read by the kernel from binary STL."""
    from OCP.RWStl import RWStl

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "mesh.stl"
        path.write_bytes(stl_bytes(mesh))
        result = RWStl.ReadFile_s(os.fspath(path))
    if result is None:
        raise MeshImportError(
            "The mesh could not be read by the kernel. Repair the mesh in the program that made it."
        )
    return result
