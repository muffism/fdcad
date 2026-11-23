"""3MF exports checked against the 3MF Consortium's schema and test files (TR381 item 5).

The schema and sample files in ``tests/data/3mf_conformance`` come from the
consortium's test suite (BSD 2-Clause, see its LICENSE there, DECISIONS D794).
"""

from __future__ import annotations

import zipfile
from functools import cache
from pathlib import Path
from typing import Any

import pytest
import xmlschema
from OCP.BRep import BRep_Builder
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt, gp_Trsf, gp_Vec
from OCP.TopoDS import TopoDS_Compound

from fdcad.core.io.export import MeshSettings, export_3mf, transform_of
from fdcad.core.io.mesh_import import MeshImportError, read_3mf
from fdcad.core.naming.names import faces_of

DATA = Path(__file__).resolve().parents[2] / "data" / "3mf_conformance"
SCHEMA = DATA / "schema"
_XML_NS = "http://www.w3.org/XML/1998/namespace"
#: The consolidated schema asks every object, component and item for a Production
#: extension UUID, a compromise its README notes; the consortium's own core samples fail
#: it too, so it does not apply to a core file.
_NOT_CORE = "production/2015/06}UUID"


@cache
def _schema(name: str) -> xmlschema.XMLSchema:
    return xmlschema.XMLSchema(str(SCHEMA / name), locations=[(_XML_NS, str(SCHEMA / "xml.xsd"))])


def _problems(name: str, text: str) -> list[str]:
    return [
        f"{e.path}: {e.reason}"
        for e in _schema(name).iter_errors(text)
        if _NOT_CORE not in str(e.reason)
    ]


def _check(path: Path) -> zipfile.ZipFile:
    """Every XML part of the package is valid; returns the open package."""
    package = zipfile.ZipFile(path)
    assert _problems("qli_3MF.xsd", package.read("3D/3dmodel.model").decode("utf-8")) == []
    types = package.read("[Content_Types].xml").decode("utf-8")
    assert _problems("opc-contentTypes.xsd", types) == []
    assert _problems("opc-relationships.xsd", package.read("_rels/.rels").decode("utf-8")) == []
    return package


def _two_boxes() -> Any:
    compound = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(compound)
    builder.Add(compound, BRepPrimAPI_MakeBox(10, 20, 30).Shape())
    builder.Add(compound, BRepPrimAPI_MakeBox(gp_Pnt(20, 0, 0), 5, 5, 5).Shape())
    return compound


def test_the_schema_accepts_the_consortium_samples() -> None:
    """The check itself works: the consortium's valid core samples pass."""
    for sample in sorted((DATA / "positive").glob("*.3mf"))[:4]:
        with zipfile.ZipFile(sample) as package:
            model = next(n for n in package.namelist() if n.endswith(".model"))
            assert _problems("qli_3MF.xsd", package.read(model).decode("utf-8")) == [], sample


def test_the_schema_catches_a_broken_model() -> None:
    broken = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<model unit="furlong" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
        "<resources/><build/></model>"
    )
    assert _problems("qli_3MF.xsd", broken)


def test_a_plain_export_is_valid(tmp_path: Path) -> None:
    out = tmp_path / "plain.3mf"
    export_3mf(BRepPrimAPI_MakeBox(10, 20, 30).Shape(), out)
    _check(out)


def test_colours_bodies_orientation_and_thumbnail_are_valid(tmp_path: Path) -> None:
    shape = _two_boxes()
    faces = [(f, "#D04020") for f in faces_of(shape)[:3]]
    move = gp_Trsf()
    move.SetTranslation(gp_Vec(1, 2, 3))
    for unit in ("mm", "in"):
        out = tmp_path / f"full_{unit}.3mf"
        export_3mf(
            shape,
            out,
            name='Bracket <A> & "B"',
            faces=faces,
            transform=transform_of(move),
            thumbnail=b"\x89PNG\r\n\x1a\n",
            settings=MeshSettings(unit=unit),
        )
        package = _check(out)
        assert "Metadata/thumbnail.png" in package.namelist()


@pytest.mark.parametrize("sample", sorted((DATA / "positive").glob("*.3mf")), ids=lambda p: p.stem)
def test_valid_samples_import(sample: Path) -> None:
    mesh = read_3mf(sample.read_bytes())
    assert len(mesh.triangles) > 0


@pytest.mark.parametrize("sample", sorted((DATA / "negative").glob("*.3mf")), ids=lambda p: p.stem)
def test_invalid_samples_never_crash_the_import(sample: Path) -> None:
    """A file that breaks the standard imports what it can or gives a clear message."""
    try:
        read_3mf(sample.read_bytes())
    except MeshImportError as exc:
        assert str(exc).endswith(".")
