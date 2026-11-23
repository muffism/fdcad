"""IGES, BREP, PLY, glTF and 3D DXF export (TR369, D989, D1010).

IGES and the kernel's own BREP keep the exact shape. PLY and glTF (as one binary
.glb file) carry a triangle mesh made with the part's mesh settings, in
millimetres; glTF has no unit of its own, so its numbers are metres as the format
asks (millimetres divided by 1000). Every writer goes through a temporary file, so
a failed export never leaves half a file. Kernel work: run off the UI thread. No Qt.
"""

from __future__ import annotations

import json
import os
import struct
from pathlib import Path

import numpy as np
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.io.export import ExportError, MeshSettings, indexed_mesh, triangles
from fdcad.core.io.temp_file import make_temp

#: The formats this module writes, by file suffix.
SUFFIXES = {
    ".igs": "iges",
    ".iges": "iges",
    ".brep": "brep",
    ".ply": "ply",
    ".glb": "glb",
    ".obj": "obj",  # TR336 (D995)
    ".dxf": "dxf3d",  # TR369 (D1010): Save As only; flat DXF has its own command
}


def _replace(tmp: str, target: Path) -> None:
    os.replace(tmp, target)


def _temp(target: Path) -> str:
    fd, tmp = make_temp(target.parent, target)
    os.close(fd)
    return tmp


def export_iges(shape: TopoDS_Shape, path: str | os.PathLike[str]) -> None:
    """Write ``shape`` as an IGES file in millimetres."""
    from OCP.IGESControl import IGESControl_Writer

    target = Path(path)
    tmp = _temp(target)
    try:
        writer = IGESControl_Writer("MM", 1)  # 1: BRep solids, not trimmed surfaces only
        if not writer.AddShape(shape) or not writer.Write(tmp):
            raise ExportError("The IGES file could not be written. Try STEP instead.")
        _replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def export_brep(shape: TopoDS_Shape, path: str | os.PathLike[str]) -> None:
    """Write ``shape`` in the kernel's own BREP format."""
    from OCP.BRepTools import BRepTools

    target = Path(path)
    tmp = _temp(target)
    try:
        if not BRepTools.Write_s(shape, tmp):
            raise ExportError("The BREP file could not be written. Check the folder and try again.")
        _replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _mesh(shape: TopoDS_Shape, settings: MeshSettings | None) -> tuple[np.ndarray, np.ndarray]:
    tris = triangles(shape, settings or MeshSettings())
    if len(tris) == 0:
        raise ExportError(
            "The part gave no triangles to write. "
            "Add a feature that makes a solid, then export again."
        )
    return indexed_mesh(tris)


def ply_bytes(vertices: np.ndarray, faces: np.ndarray) -> bytes:
    """A binary little endian PLY file of the mesh."""
    header = (
        "ply\nformat binary_little_endian 1.0\ncomment FDCAD\n"
        f"element vertex {len(vertices)}\nproperty float x\nproperty float y\nproperty float z\n"
        f"element face {len(faces)}\nproperty list uchar int vertex_indices\nend_header\n"
    ).encode("ascii")
    verts = np.asarray(vertices, dtype="<f4").tobytes()
    rows = np.zeros(len(faces), dtype=[("n", "u1"), ("i", "<i4", (3,))])
    rows["n"] = 3
    rows["i"] = np.asarray(faces, dtype="<i4")
    return header + verts + rows.tobytes()


def glb_bytes(vertices: np.ndarray, faces: np.ndarray) -> bytes:
    """A binary glTF 2.0 file with one mesh (positions in metres and indices)."""
    pos = (np.asarray(vertices, dtype=np.float64) / 1000.0).astype("<f4")
    idx = np.asarray(faces, dtype="<u4").reshape(-1)
    pos_bytes, idx_bytes = pos.tobytes(), idx.tobytes()
    pad = (4 - len(pos_bytes) % 4) % 4
    binary = pos_bytes + b"\0" * pad + idx_bytes
    binary += b"\0" * ((4 - len(binary) % 4) % 4)
    lo, hi = pos.min(axis=0).tolist(), pos.max(axis=0).tolist()
    doc = {
        "asset": {"version": "2.0", "generator": "FDCAD"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(pos_bytes), "target": 34962},
            {
                "buffer": 0,
                "byteOffset": len(pos_bytes) + pad,
                "byteLength": len(idx_bytes),
                "target": 34963,
            },
        ],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": len(pos),
                "type": "VEC3",
                "min": lo,
                "max": hi,
            },
            {"bufferView": 1, "componentType": 5125, "count": len(idx), "type": "SCALAR"},
        ],
    }
    text = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    text += b" " * ((4 - len(text) % 4) % 4)
    chunks = struct.pack("<I4s", len(text), b"JSON") + text
    chunks += struct.pack("<I4s", len(binary), b"BIN\0") + binary
    return struct.pack("<4sII", b"glTF", 2, 12 + len(chunks)) + chunks


def _write_bytes(data: bytes, path: str | os.PathLike[str]) -> None:
    target = Path(path)
    tmp = _temp(target)
    try:
        Path(tmp).write_bytes(data)
        _replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def export_ply(
    shape: TopoDS_Shape, path: str | os.PathLike[str], settings: MeshSettings | None = None
) -> None:
    """Write ``shape`` as a binary PLY mesh in millimetres."""
    _write_bytes(ply_bytes(*_mesh(shape, settings)), path)


def export_glb(
    shape: TopoDS_Shape, path: str | os.PathLike[str], settings: MeshSettings | None = None
) -> None:
    """Write ``shape`` as a binary glTF (.glb) mesh."""
    _write_bytes(glb_bytes(*_mesh(shape, settings)), path)


def obj_text(vertices: np.ndarray, faces: np.ndarray) -> str:
    """A Wavefront OBJ file of the mesh (TR336, D995): one object, millimetres."""
    lines = ["# FDCAD", "# units: millimetres", "o part"]
    lines += [f"v {x:.6g} {y:.6g} {z:.6g}" for x, y, z in np.asarray(vertices).tolist()]
    lines += [f"f {a + 1} {b + 1} {c + 1}" for a, b, c in np.asarray(faces).tolist()]
    return "\n".join(lines) + "\n"


def export_obj(
    shape: TopoDS_Shape, path: str | os.PathLike[str], settings: MeshSettings | None = None
) -> None:
    """Write ``shape`` as a Wavefront OBJ mesh in millimetres."""
    _write_bytes(obj_text(*_mesh(shape, settings)).encode("ascii"), path)


#: How far a curved edge's polyline may stray from the curve, in mm (TR369).
WIRE_DEFLECTION = 0.01


def wireframe_dxf(shape: TopoDS_Shape) -> str:
    """Every edge of ``shape`` as 3D DXF (R12) entities in millimetres (TR369, D1010):
    straight edges as LINE, curved ones as 3D POLYLINE through points along them."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GCPnts import GCPnts_QuasiUniformDeflection
    from OCP.GeomAbs import GeomAbs_Line
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp
    from OCP.TopoDS import TopoDS

    from fdcad.core.occ import ShapeMap

    def n(v: float) -> str:
        return f"{v:.6g}"

    out = [
        "0", "SECTION", "2", "HEADER",
        "9", "$ACADVER", "1", "AC1009",
        "9", "$INSUNITS", "70", "4",
        "9", "$MEASUREMENT", "70", "1",
        "0", "ENDSEC",
        "0", "SECTION", "2", "ENTITIES",
    ]  # fmt: skip
    edges = ShapeMap()
    TopExp.MapShapes_s(shape, TopAbs_EDGE, edges)
    for k in range(1, edges.Extent() + 1):
        edge = TopoDS.Edge(edges.FindKey(k))
        if BRep_Tool.Degenerated_s(edge):
            continue
        curve = BRepAdaptor_Curve(edge)
        if curve.GetType() == GeomAbs_Line:
            a, b = curve.Value(curve.FirstParameter()), curve.Value(curve.LastParameter())
            out += ["0", "LINE", "8", "0"]
            out += ["10", n(a.X()), "20", n(a.Y()), "30", n(a.Z())]
            out += ["11", n(b.X()), "21", n(b.Y()), "31", n(b.Z())]
            continue
        points = GCPnts_QuasiUniformDeflection(curve, WIRE_DEFLECTION)
        if not points.IsDone() or points.NbPoints() < 2:
            continue
        out += ["0", "POLYLINE", "8", "0", "66", "1", "70", "8"]  # 8: a 3D polyline
        out += ["10", "0", "20", "0", "30", "0"]
        for i in range(1, points.NbPoints() + 1):
            p = points.Value(i)
            out += ["0", "VERTEX", "8", "0", "70", "32"]  # 32: a 3D polyline vertex
            out += ["10", n(p.X()), "20", n(p.Y()), "30", n(p.Z())]
        out += ["0", "SEQEND", "8", "0"]
    out += ["0", "ENDSEC", "0", "EOF"]
    return "\n".join(out) + "\n"


def export_dxf3d(shape: TopoDS_Shape, path: str | os.PathLike[str]) -> None:
    """Write the edges of ``shape`` as a 3D DXF wireframe in millimetres."""
    _write_bytes(wireframe_dxf(shape).encode("ascii"), path)
