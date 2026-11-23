"""Variables only some features use (TR91, D940)."""

from __future__ import annotations

from fdcad.core.document.model import Feature, Param, Variable, new_document
from fdcad.core.equations.orphans import only_used_by
from fdcad.core.units import Kind


def _doc():  # type: ignore[no-untyped-def]
    doc = new_document()
    doc.variables = [
        Variable("Base", Kind.LENGTH, "5mm", 5.0),
        Variable("Depth", Kind.LENGTH, "=Base * 2", 10.0),
        Variable("Width", Kind.LENGTH, "20mm", 20.0),
        Variable("Spare", Kind.LENGTH, "1mm", 1.0),
        Variable("Label", Kind.LENGTH, "3mm", 3.0),
    ]
    doc.features.append(
        Feature(
            "f10",
            "extrude",
            "Boss",
            params={"depth": Param("=Depth + Width", 30.0)},
            data={"texts": [{"text": "W {Label}"}]},
        )
    )
    doc.features.append(
        Feature("f11", "extrude", "Pad", params={"depth": Param("=Width / 2", 10.0)})
    )
    return doc


def test_only_its_own_variables_and_what_they_use() -> None:
    doc = _doc()
    # Depth and Base (used only through Depth) go; Width is shared; Spare was never used.
    assert only_used_by(doc, ["f10"]) == ["Base", "Depth", "Label"]
    assert only_used_by(doc, ["f11"]) == []
    assert only_used_by(doc, ["f10", "f11"]) == ["Base", "Depth", "Width", "Label"]


def test_a_variable_used_elsewhere_stays() -> None:
    doc = _doc()
    doc.feature("f11").params["depth"] = Param("=Base", 5.0)
    assert only_used_by(doc, ["f10"]) == ["Depth", "Width", "Label"]
    doc.feature("f11").data = {"texts": [{"text": "{Label:.1f}"}]}
    assert only_used_by(doc, ["f10"]) == ["Depth", "Width"]


def test_a_variable_also_used_by_a_kept_variable_stays() -> None:
    doc = _doc()
    doc.variables.append(Variable("Total", Kind.LENGTH, "=Depth + 1mm", 11.0))
    doc.feature("f11").params["depth"] = Param("=Total", 11.0)
    assert only_used_by(doc, ["f10"]) == ["Width", "Label"]
