"""Standard 3MF metadata from the part's properties (TR183, D960)."""

from __future__ import annotations

import zipfile
from pathlib import Path

from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

from fdcad.core.io.export import export_3mf, standard_metadata


def test_known_properties_map_to_standard_names() -> None:
    props = {"Designer": "Sam", "licence": "CC BY 4.0", "Part Number": "P-1", "Note": ""}
    items = dict(standard_metadata("Bracket", props, "2026-11-06"))
    assert items == {
        "Title": "Bracket",
        "Designer": "Sam",
        "LicenseTerms": "CC BY 4.0",
        "ModificationDate": "2026-11-06",
    }
    assert dict(standard_metadata("Bracket", {"Title": "Shelf bracket"}, "x"))["Title"] == (
        "Shelf bracket"
    )


def test_written_into_the_model(tmp_path: Path) -> None:
    box = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    path = tmp_path / "part.3mf"
    export_3mf(box, path, name="Bracket", metadata={"Description": "A & B"})
    with zipfile.ZipFile(path) as zf:
        model = zf.read("3D/3dmodel.model").decode("utf-8")
    assert '<metadata name="Title">Bracket</metadata>' in model
    assert '<metadata name="Description">A &amp; B</metadata>' in model
    assert '<metadata name="ModificationDate">' in model
    assert '<metadata name="fdcad:Description">' in model  # the custom one stays too
