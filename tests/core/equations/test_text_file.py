"""Equations to and from a text file (TR25, D749)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Param
from fdcad.core.equations.edit import Row, apply_rows, rows_for
from fdcad.core.equations.text_file import (
    MAX_BYTES,
    MAX_ROWS,
    EquationFileError,
    from_text,
    merge,
    to_text,
)
from fdcad.core.units import Kind
from tests.core.equations.test_equations import _plate


def _rich_plate():
    doc = _plate()
    ext = doc.features[-1]
    ext.params["depth"] = Param('="Width" / 6', 10.0)
    ext.data["suppression"] = "=0"
    ext.data["comments"] = {"depth": "a sixth of the width"}
    doc.variables[0].comment = "plate width"
    return doc


def test_export_then_import_gives_the_same_rows() -> None:
    doc = _rich_plate()
    rows = rows_for(doc)
    text = to_text(rows)
    assert text.splitlines() == [
        "# FDCAD equations",
        "[variables]",
        '"Width" = 60  // plate width',
        "[suppression]",
        '"Extrude 1" = =0',
        "[equations]",
        f'"d1@Sketch 1" = {rows[2].expr}',
        '"depth@Extrude 1" = ="Width" / 6  // a sixth of the width',
    ]
    back = from_text(text)
    assert [(r.section, r.name, r.expr, r.comment) for r in back] == [
        (r.section, r.name, r.expr, r.comment) for r in rows
    ]


def test_reading_skips_comments_blank_lines_and_a_byte_order_mark() -> None:
    text = '﻿# my values\n\n[variables]\n  "Gap" = 0.2mm   \n# end\n'
    assert [(r.section, r.name, r.expr) for r in from_text(text)] == [("variable", "Gap", "0.2mm")]


def test_a_double_slash_inside_a_quoted_name_is_not_a_comment() -> None:
    rows = from_text('[equations]\n"depth@Cut // 2" = ="a//b" + 1  // note\n')
    assert rows[0].name == "depth@Cut // 2"
    assert rows[0].expr == '="a//b" + 1'
    assert rows[0].comment == "note"


def test_rows_before_any_section_are_variables() -> None:
    assert from_text('"Width" = 40mm\n')[0].section == "variable"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("[nothing]\n", r"line 1: unknown section \[nothing\]\. Use one of"),
        ("Width = 40\n", "line 1: a row starts with a quoted name"),
        ('"Width" 40\n', "line 1: a row needs a quoted name, then ="),
        ('"" = 40\n', "line 1: a row needs a quoted name"),
        ('\n"Width" =   // only a note\n', "line 2: the value is empty"),
    ],
)
def test_bad_lines_name_the_line_and_the_fix(text: str, message: str) -> None:
    with pytest.raises(EquationFileError, match=message):
        from_text(text)


def test_large_files_are_refused() -> None:
    with pytest.raises(EquationFileError, match="larger than"):
        from_text("#" * (MAX_BYTES + 1))
    with pytest.raises(EquationFileError, match="more than"):
        from_text("".join(f'"V{i}" = 1\n' for i in range(MAX_ROWS + 1)))


def test_merge_replaces_adds_keeps_and_skips() -> None:
    doc = _rich_plate()
    current = rows_for(doc)
    incoming = from_text(
        "[variables]\n"
        '"Width" = 80mm  // wider\n'
        '"Gap" = 0.2mm\n'
        "[suppression]\n"
        '"No Such Feature" = =1\n'
        "[equations]\n"
        '"depth@Missing" = =5mm\n'
    )
    merged = merge(doc, current, incoming)
    assert merged.changed == 2
    assert merged.skipped == ["No Such Feature", "depth@Missing"]
    by_name = {r.name: r for r in merged.rows}
    assert by_name["Width"].expr == "80mm" and by_name["Width"].comment == "wider"
    assert by_name["Width"].kind is Kind.LENGTH  # the existing kind is kept
    assert by_name["Gap"].expr == "0.2mm"
    assert "depth@Extrude 1" in by_name  # rows the file does not name stay
    variables, _features = apply_rows(doc, merged.rows, strict=True)
    assert [v.name for v in variables] == ["Width", "Gap"]


def test_merge_of_the_same_rows_changes_nothing() -> None:
    doc = _rich_plate()
    rows = rows_for(doc)
    merged = merge(doc, rows, from_text(to_text(rows)))
    assert merged.changed == 0 and merged.skipped == []


def test_a_new_variable_from_a_file_gets_its_kind_from_the_value() -> None:
    doc = _plate()
    merged = merge(doc, rows_for(doc), [Row("variable", "Holes", "4")])
    variables, _f = apply_rows(doc, merged.rows)
    assert variables[-1].kind is Kind.NUMBER


def test_the_link_is_saved_only_when_set(tmp_path) -> None:
    from fdcad.core.io import fdef

    doc = _plate()
    assert "equations_file" not in fdef.dumps(doc)
    doc.equations_file = str(tmp_path / "shared.txt")
    again = fdef.loads(fdef.dumps(doc))
    assert again.equations_file == doc.equations_file


def test_a_link_that_is_not_text_makes_the_file_damaged() -> None:
    import json

    from fdcad.core.io import fdef

    data = json.loads(fdef.dumps(_plate()))
    data["equations_file"] = 5
    with pytest.raises(fdef.FileFormatError, match="equations_file"):
        fdef.loads(json.dumps(data))


def test_read_linked_merges_the_file_and_finds_it_beside_a_moved_part(tmp_path) -> None:
    from fdcad.core.equations.text_file import read_linked, resolve

    doc = _plate()
    assert read_linked(doc, None) is None  # no link
    shared = tmp_path / "shared.txt"
    shared.write_text('[variables]\n"Width" = 75mm\n', encoding="utf-8")
    doc.equations_file = str(shared)
    merged = read_linked(doc, tmp_path / "part.fdprt")
    assert merged is not None and merged.changed == 1
    assert {r.name: r.expr for r in merged.rows}["Width"] == "75mm"
    # The folder moved: the stored path is gone, the file next to the part is used.
    moved = tmp_path / "moved"
    moved.mkdir()
    (moved / "shared.txt").write_text(shared.read_text(encoding="utf-8"), encoding="utf-8")
    shared.unlink()
    assert resolve(doc.equations_file, moved / "part.fdprt") == moved / "shared.txt"
    # A relative link is next to the part.
    assert resolve("shared.txt", moved / "part.fdprt") == moved / "shared.txt"


def test_read_linked_errors(tmp_path) -> None:
    from fdcad.core.equations.text_file import read_linked

    doc = _plate()
    doc.equations_file = str(tmp_path / "gone.txt")
    with pytest.raises(OSError):
        read_linked(doc, None)
    bad = tmp_path / "bad.txt"
    bad.write_bytes(b'"Width" = \xff\xfe40\n')
    doc.equations_file = str(bad)
    with pytest.raises(EquationFileError, match="not UTF-8"):
        read_linked(doc, None)
