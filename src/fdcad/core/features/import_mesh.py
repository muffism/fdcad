"""Imported mesh: an STL, 3MF or OBJ file as a reference body, or as a faceted solid on
request (PLAN Phase 3, PHASE3_SPEC P3.9, DECISIONS D294).

Params: ``convert`` (optional boolean): turn the mesh into a faceted solid that
joins the part like an imported STEP body. Left out, the mesh is a reference
body: it is shown but is not part of the part's solid. ``merge`` (optional
boolean, converted meshes): join the solid to the part's body. ``subtract``
(optional boolean, converted meshes): cut the solid out of the part's body, so
the mesh works as a boolean tool (DECISIONS D412). ``parts`` (optional boolean,
converted 3MF meshes, TR386, D1205): one body per part of a slicer 3MF, named and
given the print role the slicer stored; ``keep_roles`` (optional boolean): keep the
modifier, negative and support parts as bodies with their roles, else they are
left out. TR186 (D1212): ``repair`` (optional boolean) fills holes, drops repeated
triangles, extra triangles on edges shared by more than two, and tiny pieces;
``reduce_percent`` (optional number, 1 to 99) or ``reduce_target`` (optional whole
number) lowers the triangle count, ``reduce_error`` (optional length) caps how far
a vertex moves and ``keep_boundary`` (optional boolean) keeps open edges in place.
Part faces are ``part<k>/face/<j>``; ``extras["body_titles"]`` and
``extras["body_roles"]`` give each part's first face name its name and role.

Refs: ``source``: ``{"embedded": "b1"}``, an embedded ``mesh`` block whose
``format`` is ``stl``, ``3mf`` or ``obj``.

Results: ``extras["mesh"]`` (the numpy mesh), ``extras["reference"]`` (a face
carrying the triangles, for the view), ``extras["triangles"]`` and
``extras["measure"]`` (sizes for the Measure box, D412). Converted
faces are named ``face/<k>``; triangles that lie in one plane are merged into
one face first, so a box mesh gives six faces.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from OCP.BRep import BRep_Builder, BRep_Tool
from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing
from OCP.ShapeFix import ShapeFix_Solid
from OCP.StlAPI import StlAPI_Reader
from OCP.TopAbs import TopAbs_SHELL
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureState,
    FeatureType,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.features.import_step import import_name, imported_faces
from fdcad.core.features.solids import combine, compound
from fdcad.core.io.embedded import EmbeddedError, block_bytes, block_of, make_block, new_block_id
from fdcad.core.io.mesh_import import (
    TRIANGLE_WARNING,
    Mesh,
    MeshImportError,
    format_of,
    read_mesh,
    stl_bytes,
    triangulation,
)
from fdcad.core.mesh_tools import measure_mesh
from fdcad.core.naming.names import NamedShape, faces_of, restrict
from fdcad.core.units import Kind, UnitSystem

#: Sewing tolerance when a mesh becomes a solid, in mm.
SEW_TOLERANCE = 1e-6


def mesh_face(mesh: Mesh) -> TopoDS_Face:
    """A face that only carries the mesh's triangles, for display."""
    face = TopoDS_Face()
    BRep_Builder().MakeFace(face, triangulation(mesh))
    return face


def faceted_solid(mesh: Mesh, owner: str) -> TopoDS_Shape:
    """The mesh as a closed solid with one flat face per group of coplanar triangles.

    Raises FeatureError when the mesh has holes or is not one closed skin.
    """
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "mesh.stl"
        path.write_bytes(stl_bytes(mesh))
        faces = TopoDS_Shape()
        if not StlAPI_Reader().Read(faces, str(path)):
            raise FeatureError(
                f"{owner}: the mesh could not be turned into faces. "
                "Keep it as a reference body or repair the mesh."
            )
    sewing = BRepBuilderAPI_Sewing(SEW_TOLERANCE)
    sewing.Add(faces)
    sewing.Perform()
    shells = []
    explorer = TopExp_Explorer(sewing.SewedShape(), TopAbs_SHELL)
    while explorer.More():
        shells.append(TopoDS.Shell(explorer.Current()))
        explorer.Next()
    open_count = sum(1 for s in shells if not BRep_Tool.IsClosed_s(s))
    if not shells or open_count:
        raise FeatureError(
            f"{owner}: the mesh has holes, so it cannot become a solid. Repair the mesh "
            "in the program that made it, or keep it as a reference body."
        )
    made = [ShapeFix_Solid().SolidFromShell(s) for s in shells]
    solid = made[0] if len(made) == 1 else compound(made)
    from fdcad.core.unify import unify_faces

    return unify_faces(solid)[0]


#: STL and OBJ units to millimetres (spec 2 section 20 item 20, audit D item 7, D715).
FILE_UNITS = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4}


def _mesh(feature: Feature, ctx: BuildContext) -> Mesh:
    owner = feature.name
    try:
        block = block_of(ctx.document, feature.refs.get("source"), "mesh", owner)
        data = block_bytes(ctx.document, feature.refs.get("source"), "mesh", owner)
        fmt = str(block.get("format", ""))
        mesh = read_mesh(data, fmt)
    except (EmbeddedError, MeshImportError) as exc:
        message = str(exc)
        if not message.startswith(owner):
            message = f"{owner}: {message}"
        raise FeatureError(message) from exc
    factor = FILE_UNITS.get(str(feature.params.get("file_unit", "mm")), 1.0)
    if fmt == "3mf" or factor == 1.0:
        return mesh  # 3MF carries its own unit
    return Mesh((mesh.vertices * factor).astype(mesh.vertices.dtype), mesh.triangles)


@register
class ImportMesh(FeatureType):
    """A mesh read from an embedded STL, 3MF or OBJ file."""

    type_name = "import_mesh"
    makes_solid = True
    params = (
        ParamSpec("convert", default=False, optional=True),
        ParamSpec("merge", default=False, optional=True),
        ParamSpec("subtract", default=False, optional=True),
        # STL and OBJ files have no unit: the unit they were saved in (D715).
        ParamSpec("file_unit", choices=tuple(FILE_UNITS), optional=True),
        ParamSpec("parts", default=False, optional=True),  # TR386 (D1205)
        ParamSpec("keep_roles", default=False, optional=True),
        ParamSpec("repair", default=False, optional=True),  # TR186 (D1212)
        ParamSpec("reduce_percent", optional=True),
        ParamSpec("reduce_target", optional=True),
        ParamSpec("reduce_error", kind=Kind.LENGTH, optional=True),
        ParamSpec("keep_boundary", default=False, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Read the mesh; show it, or turn it into a solid when asked."""
        owner, fid = feature.name, feature.id
        mesh = _mesh(feature, ctx)
        mesh, fixed = _repair_and_reduce(feature, mesh)
        issues: list[Issue] = []
        if mesh.triangle_count > TRIANGLE_WARNING:
            issues.append(
                Issue(
                    FeatureState.WARNING,
                    f"{owner} has {mesh.triangle_count:,} triangles, more than "
                    f"{TRIANGLE_WARNING:,}. It may be slow to show and to convert. "
                    "Reduce it in a mesh program if the part feels slow.",
                    code="large_mesh",
                )
            )
        body = ctx.body
        titles: dict[str, str] = {}
        roles: dict[str, str] = {}
        if feature.params.get("convert") is True:
            split = _parts(feature, ctx) if feature.params.get("parts") is True else None
            if split is not None:
                tool, titles, roles = _part_bodies(split, feature)
            else:
                shape = faceted_solid(mesh, owner)
                tool = NamedShape(shape, imported_faces(fid, shape))
            if feature.params.get("subtract") is True:
                if body is None:
                    raise FeatureError(
                        f"{owner} has nothing to subtract from. Add a body above it first, "
                        "or untick Subtract from the part."
                    )
                body = combine(fid, owner, body, tool, "cut")
            elif body is None:
                body = tool
            elif feature.params.get("merge") is True:
                body = combine(fid, owner, body, tool, "boss")
            else:
                joined = compound([body.shape, tool.shape])
                body = NamedShape(joined, restrict(body.faces + tool.faces, joined, fid))
            result = FeatureResult(body=body, issues=issues)
        else:
            result = FeatureResult(body=body, issues=issues)
            result.extras["reference"] = mesh_face(mesh)
        result.extras["mesh"] = mesh
        if fixed:
            result.extras["report"] = fixed
        if titles:
            result.extras["body_titles"] = titles
        if roles:
            result.extras["body_roles"] = roles
        result.extras["triangles"] = mesh.triangle_count
        result.extras["measure"] = measure_mesh(mesh)
        return result


def _repair_and_reduce(feature: Feature, mesh: Mesh) -> tuple[Mesh, list[str]]:
    """Repair and reduce the mesh as the params ask (TR186), with what was done."""
    from fdcad.core.mesh_repair import reduce, repair

    owner = feature.name
    notes: list[str] = []
    if feature.params.get("repair") is True:
        mesh, report = repair(mesh)
        if report.sentence():
            notes.append(report.sentence())
    percent = feature.params.get("reduce_percent")
    target = feature.params.get("reduce_target")
    wanted = None
    if isinstance(percent, int | float) and not isinstance(percent, bool):
        if not 1 <= percent <= 99:
            raise FeatureError(f"{owner}: keep between 1 and 99 percent. Enter another percent.")
        wanted = max(4, int(mesh.triangle_count * percent / 100))
    elif isinstance(target, int) and not isinstance(target, bool):
        if target < 4:
            raise FeatureError(f"{owner}: keep at least 4 triangles. Enter a larger target.")
        wanted = target
    if wanted is not None and wanted < mesh.triangle_count:
        error = feature.params.get("reduce_error")
        limit = error.value if isinstance(error, Param) and error.value > 0 else 0.0
        before = mesh.triangle_count
        mesh = reduce(mesh, wanted, limit, feature.params.get("keep_boundary") is True)
        notes.append(f"Reduced from {before:,} to {mesh.triangle_count:,} triangles.")
    return mesh, notes


def _parts(feature: Feature, ctx: BuildContext) -> list[Any] | None:
    """The parts of the import's 3MF file, or None for other files."""
    from fdcad.core.io.mesh_import import read_3mf_parts

    owner = feature.name
    try:
        block = block_of(ctx.document, feature.refs.get("source"), "mesh", owner)
        if str(block.get("format", "")) != "3mf":
            return None
        data = block_bytes(ctx.document, feature.refs.get("source"), "mesh", owner)
        return read_3mf_parts(data)
    except (EmbeddedError, MeshImportError) as exc:
        message = str(exc)
        raise FeatureError(message if message.startswith(owner) else f"{owner}: {message}") from exc


def _part_bodies(
    parts: list[Any], feature: Feature
) -> tuple[NamedShape, dict[str, str], dict[str, str]]:
    """One faceted body per part (TR386): the joined shape, and the names and roles by
    each body's first face name."""
    owner, fid = feature.name, feature.id
    keep = feature.params.get("keep_roles") is True
    shapes, faces, titles, roles = [], [], {}, {}
    for k, part in enumerate(parts, 1):
        if part.role != "part" and not keep:
            continue
        try:
            solid = faceted_solid(part.mesh, owner)
        except FeatureError:
            raise FeatureError(
                f"{owner}: the part {part.name} has holes, so it cannot become a solid. "
                "Repair the mesh in the program that made it, or untick One body per part."
            ) from None
        named = [(f"{fid}/part{k}/face/{j}", f) for j, f in enumerate(faces_of(solid), 1)]
        shapes.append(solid)
        faces += named
        titles[named[0][0]] = part.name
        if part.role != "part":
            roles[named[0][0]] = part.role
    if not shapes:
        raise FeatureError(
            f"{owner}: every part of the file is a modifier, negative or support part. "
            "Tick Keep slicer roles to bring them in."
        )
    shape = shapes[0] if len(shapes) == 1 else compound(shapes)
    return NamedShape(shape, restrict(faces, shape, fid)), titles, roles


def new_mesh_import(
    doc: Document, filename: str, data: bytes
) -> tuple[str, dict[str, Any], Feature]:
    """A mesh block holding ``data`` and an import feature that uses it, not yet in ``doc``.

    Raises MeshImportError for a file type that is not a mesh.
    """
    fmt = format_of(filename)
    bid = new_block_id(doc)
    block = make_block("mesh", filename, data, format=fmt)
    feature = Feature(
        doc.new_feature_id(),
        "import_mesh",
        import_name(doc, "Mesh"),
        refs={"source": {"embedded": bid}},
    )
    return bid, block, feature


def part_from_mesh(filename: str, data: bytes, units: UnitSystem = UnitSystem.MM) -> Document:
    """A new part whose first feature is the imported mesh (File, Open)."""
    doc = new_document(units)
    bid, block, feature = new_mesh_import(doc, filename, data)
    doc.embedded[bid] = block
    doc.features.append(feature)
    return doc
